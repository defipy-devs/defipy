# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2026 Ian Moore
# Email: defipy.devs@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

from collections import defaultdict

from uniswappy.utils.data import UniswapExchangeData

from balancerpy.cwpt.exchg import BalancerExchange
from stableswappy.cst.exchg import StableswapExchange

from ..position import (
    AnalyzePosition,
    AnalyzeBalancerPosition,
    AnalyzeStableswapPosition,
)
from ...utils.data import PortfolioAnalysis, PositionSummary


class AggregatePortfolio:

    """ Aggregate N LP positions into a single portfolio-level view.

        Cross-protocol. Accepts a mix of V2, V3, Balancer, and
        Stableswap positions in one call. Dispatches per-position to
        the appropriate Analyze*Position primitive, extracts common
        scalars (net_pnl, il_percentage, fee_income), and sums them
        in a shared first-token numeraire.

        Answers Q6.1 (total IL), Q6.2 (worst-to-best PnL ranking),
        Q6.3 (shared token exposure) from DEFIMIND_TIER1_QUESTIONS.md.

        Composition pattern: depth-chain per position, breadth-combine
        across positions. The cross-protocol extension (from V2/V3-
        only in earlier versions) is pure dispatch — the per-protocol
        analyzers do the real work, this primitive stays thin.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Numeraire enforcement
        ---------------------
        All positions must share a common first-token symbol. For V2/V3
        this is lp.token0; for Balancer/Stableswap it's the first token
        in the pool's insertion order. A portfolio mixing ETH/USDC
        (V2), ETH/DAI (V3), and ETH/WBTC (Balancer 80/20) works — all
        have ETH as token0. A portfolio mixing ETH/USDC and BTC/USDT
        does not — the "total" would conflate ETH-units and BTC-units.

        Stableswap numeraire subtlety: stableswap values are denominated
        at peg (1:1 across assets). When aggregating a stableswap
        position into a portfolio where the numeraire is something
        like ETH, the at-peg valuation is NOT comparable to an
        ETH-denominated value. In v1, stableswap positions must have
        their first token's symbol match the portfolio numeraire —
        which in practice means the portfolio is denominated in one
        of the stableswap's tokens (e.g., USDC/DAI stableswap
        aggregated with V2 USDC pairs). Mixed ETH-and-stableswap
        portfolios work only if one of the stableswap tokens is
        treated as the numeraire by the caller; otherwise the caller
        should group by numeraire and call once per group. This is
        enforced by the common first-token check; the limitation is
        documented here rather than silently producing bad totals.

        Stableswap unreachable-alpha handling
        -------------------------------------
        When a stableswap position is in the unreachable-alpha regime
        (StableswapPositionAnalysis with il_percentage = None), its
        contribution to totals is 0.0 and a note is appended to
        shared_exposure_warnings flagging the position. This keeps
        aggregation meaningful for the reachable positions and makes
        the skip explicit rather than silent. Callers can detect the
        notes string pattern to filter affected portfolios.

        Fee income scope
        ----------------
        In v1, only V2/V3 positions contribute non-zero fee_income
        (inherited from AnalyzePosition's fee-from-net-vs-IL derivation).
        Balancer and Stableswap positions report fee_income = 0.0
        because their respective Analyze primitives don't attribute
        fees at the per-LP level. total_fees therefore reflects V2/V3
        fees only; Balancer/Stableswap fee yield must be tracked
        externally by the caller. Documented here because the aggregate
        number is easy to misread otherwise.

        Why no "exit_priority" label on pnl_ranking. The primitive
        reports ranking, not verdict. A bad-PnL position might be at
        the bottom and due to mean-revert; an exit might cost more
        than the hold. The caller decides. Matches DetectRugSignals.

        Why positions stay in input order. Callers know which position
        is which by index. Exposing ranking via pnl_ranking (names,
        not indices) gives both views without either rewriting the
        other.
    """

    def __init__(self):
        pass

    def apply(self, positions):

        """ apply

            Compute the portfolio-level aggregate.

            Parameters
            ----------
            positions : list[PortfolioPosition]
                One per LP position. At least 1. All positions must
                share a common first-token symbol (see class docstring).

            Returns
            -------
            PortfolioAnalysis

            Raises
            ------
            ValueError
                If positions is empty; if positions have mismatched
                first-token symbols; if any stableswap position lacks
                entry_amounts; if any V2/V3/Balancer position lacks
                entry_x_amt/entry_y_amt.
        """

        if not positions:
            raise ValueError(
                "AggregatePortfolio: positions must be a non-empty list"
            )

        # Determine numeraire from first position's protocol-appropriate
        # first-token symbol, then enforce consistency.
        protocols = [self._detect_protocol(p.lp) for p in positions]
        first_tokens = [
            self._first_token_name(p.lp, proto)
            for p, proto in zip(positions, protocols)
        ]

        numeraires = set(first_tokens)
        if len(numeraires) > 1:
            raise ValueError(
                "AggregatePortfolio: positions must share a common "
                "first-token numeraire. Got mixed first tokens: {}. "
                "Either group positions by first-token symbol and "
                "call once per group, or rebase values externally "
                "before aggregation.".format(sorted(numeraires))
            )

        numeraire = next(iter(numeraires))

        # Run the appropriate analyzer per position.
        summaries = []
        unreachable_notes = []
        for p, proto in zip(positions, protocols):
            summary = self._analyze_one(p, proto)
            summaries.append(summary)

            # Flag any stableswap unreachable-alpha skips.
            if proto == "stableswap":
                analysis = summary.analysis
                if analysis.il_percentage is None:
                    unreachable_notes.append(
                        "{} is in the unreachable-alpha regime "
                        "(A={}, alpha={}); skipped from totals"
                        .format(
                            summary.name, analysis.A, analysis.alpha,
                        )
                    )

        # Scalar totals. Each PositionSummary already carries
        # numeraire-denominated scalars; unreachable stableswap
        # positions contribute 0 (enforced in _analyze_one).
        total_value = sum(
            self._current_value(s) for s in summaries
        )
        total_hold_value = sum(
            self._hold_value(s) for s in summaries
        )
        total_fees = sum(s.fee_income for s in summaries)
        total_net_pnl = sum(s.net_pnl for s in summaries)

        # PnL ranking: worst first, tiebreak on worst IL first.
        pnl_ranking = [
            s.name for s in sorted(
                summaries,
                key = lambda s: (s.net_pnl, s.il_percentage),
            )
        ]

        # Shared-exposure + unreachable notes merged.
        shared_exposure_warnings = (
            self._detect_shared_exposure(summaries) + unreachable_notes
        )

        return PortfolioAnalysis(
            numeraire = numeraire,
            total_value = total_value,
            total_hold_value = total_hold_value,
            total_fees = total_fees,
            total_net_pnl = total_net_pnl,
            positions = summaries,
            pnl_ranking = pnl_ranking,
            shared_exposure_warnings = shared_exposure_warnings,
        )

    # ─── Protocol dispatch ──────────────────────────────────────────────

    def _detect_protocol(self, lp):

        """ _detect_protocol

            Map an lp to one of the four protocol strings. Mirrors the
            dispatch pattern in CompareProtocols so the two primitives
            report consistent labels.
        """

        if isinstance(lp, BalancerExchange):
            return "balancer"
        if isinstance(lp, StableswapExchange):
            return "stableswap"
        if hasattr(lp, 'version'):
            if lp.version == UniswapExchangeData.VERSION_V3:
                return "uniswap_v3"
            if lp.version == UniswapExchangeData.VERSION_V2:
                return "uniswap_v2"
        raise ValueError(
            "AggregatePortfolio: unrecognized lp type {}. Supported: "
            "UniswapExchange (V2/V3), BalancerExchange, "
            "StableswapExchange.".format(type(lp).__name__)
        )

    def _first_token_name(self, lp, protocol):

        """ _first_token_name

            Protocol-aware first-token extraction for numeraire matching.
        """

        if protocol in ("uniswap_v2", "uniswap_v3"):
            return lp.token0
        # Balancer and Stableswap expose tokens via tkn_reserves in
        # insertion order.
        return list(lp.tkn_reserves.keys())[0]

    def _analyze_one(self, p, protocol):

        """ _analyze_one

            Route one PortfolioPosition to the protocol-appropriate
            analyzer and wrap the result in a PositionSummary.

            Validates that the required entry-shape fields are present
            for the protocol: V2/V3/Balancer need entry_x_amt and
            entry_y_amt; Stableswap needs entry_amounts.
        """

        if protocol in ("uniswap_v2", "uniswap_v3"):
            return self._analyze_uniswap(p, protocol)
        if protocol == "balancer":
            return self._analyze_balancer(p, protocol)
        if protocol == "stableswap":
            return self._analyze_stableswap(p, protocol)

        raise ValueError(
            "AggregatePortfolio: unhandled protocol {!r}".format(protocol)
        )

    def _analyze_uniswap(self, p, protocol):

        if p.entry_x_amt is None or p.entry_y_amt is None:
            raise ValueError(
                "AggregatePortfolio: {} positions require "
                "entry_x_amt and entry_y_amt on PortfolioPosition"
                .format(protocol)
            )

        analysis = AnalyzePosition().apply(
            p.lp, p.lp_init_amt, p.entry_x_amt, p.entry_y_amt,
            lwr_tick = p.lwr_tick, upr_tick = p.upr_tick,
            holding_period_days = p.holding_period_days,
        )

        display_name = p.name if p.name is not None \
                       else "{}/{}".format(p.lp.token0, p.lp.token1)

        return PositionSummary(
            name = display_name,
            protocol = protocol,
            net_pnl = analysis.net_pnl,
            il_percentage = analysis.il_percentage,
            fee_income = analysis.fee_income,
            tokens = [p.lp.token0, p.lp.token1],
            analysis = analysis,
        )

    def _analyze_balancer(self, p, protocol):

        if p.entry_x_amt is None or p.entry_y_amt is None:
            raise ValueError(
                "AggregatePortfolio: Balancer positions require "
                "entry_x_amt and entry_y_amt on PortfolioPosition "
                "(map base and opp tokens to x and y respectively)"
            )

        analysis = AnalyzeBalancerPosition().apply(
            p.lp, p.lp_init_amt, p.entry_x_amt, p.entry_y_amt,
            holding_period_days = p.holding_period_days,
        )

        display_name = p.name if p.name is not None else "{}/{}".format(
            analysis.base_tkn_name, analysis.opp_tkn_name,
        )

        return PositionSummary(
            name = display_name,
            protocol = protocol,
            net_pnl = analysis.net_pnl,
            il_percentage = analysis.il_percentage,
            fee_income = analysis.fee_income,
            tokens = [analysis.base_tkn_name, analysis.opp_tkn_name],
            analysis = analysis,
        )

    def _analyze_stableswap(self, p, protocol):

        if p.entry_amounts is None:
            raise ValueError(
                "AggregatePortfolio: Stableswap positions require "
                "entry_amounts on PortfolioPosition (list of per-token "
                "deposit amounts in pool's insertion order)"
            )

        analysis = AnalyzeStableswapPosition().apply(
            p.lp, p.lp_init_amt, p.entry_amounts,
            holding_period_days = p.holding_period_days,
        )

        display_name = p.name if p.name is not None else "/".join(
            analysis.token_names
        )

        # Unreachable positions contribute 0 to totals — flag happens
        # upstream in .apply(). For scalar fields we substitute 0 for
        # None so the sums work; the original analysis is preserved on
        # PositionSummary.analysis for callers who want the detail.
        net_pnl = analysis.net_pnl if analysis.net_pnl is not None else 0.0
        il_pct = (
            analysis.il_percentage if analysis.il_percentage is not None
            else 0.0
        )

        return PositionSummary(
            name = display_name,
            protocol = protocol,
            net_pnl = net_pnl,
            il_percentage = il_pct,
            fee_income = analysis.fee_income,
            tokens = list(analysis.token_names),
            analysis = analysis,
        )

    # ─── Scalar extractors ──────────────────────────────────────────────

    def _current_value(self, summary):

        """ _current_value

            Pull current_value from any of the three analysis shapes.
            For stableswap unreachable, current_value is hold_value
            (set in StableswapPositionAnalysis's unreachable branch),
            which zeros the pnl contribution correctly.
        """

        a = summary.analysis
        # All three analysis types carry current_value as a float.
        return float(a.current_value)

    def _hold_value(self, summary):

        """ _hold_value

            Pull hold_value from any of the three analysis shapes.
        """

        a = summary.analysis
        return float(a.hold_value)

    # ─── Shared-exposure detection ──────────────────────────────────────

    def _detect_shared_exposure(self, summaries):

        """ _detect_shared_exposure

            Flag tokens that appear in more than one position's
            token list.

            Cross-protocol note: the common-numeraire enforcement
            guarantees every position shares its first token. That
            warning always fires in a multi-position portfolio and
            restates a constraint the caller already knows. We keep
            it anyway for consistency — filtering it would make the
            output context-dependent.
        """

        occurrences = defaultdict(list)
        for s in summaries:
            for token in s.tokens:
                occurrences[token].append(s.name)

        warnings = []
        for token, names in occurrences.items():
            if len(names) > 1:
                warnings.append(
                    "{} appears in {} positions: {}".format(
                        token, len(names), ", ".join(names)
                    )
                )
        return warnings
