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

from ..position import AnalyzePosition
from ...utils.data import PortfolioAnalysis, PositionSummary


class AggregatePortfolio:

    """ Aggregate N LP positions into a single portfolio-level view.

        Chains AnalyzePosition across each input position, sums the
        scalar metrics in a shared token0 numeraire, ranks by net_pnl
        ascending, and flags tokens that appear in more than one
        position as shared-exposure warnings.

        Answers Q6.1 (total IL across positions), Q6.2 (worst-to-best
        PnL ranking), Q6.3 (shared token exposure across positions)
        from DEFIMIND_TIER1_QUESTIONS.md.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        Mixed-numeraire rejection. All positions must share a common
        token0 symbol. Portfolios mixing token0 currencies (e.g.,
        ETH-pair positions alongside BTC-pair positions) are rejected
        with a ValueError rather than silently summing incompatible
        units. Callers with mixed portfolios should group by token0
        and call once per group.

        Ranking semantics. pnl_ranking on the result is ordered by
        net_pnl ascending (worst-first), tiebroken on il_percentage
        ascending. The primitive does not call the worst position an
        "exit candidate" — the ranking is information; the verdict
        belongs to the caller. See DetectRugSignals for the same
        signal-surfacer-not-verdict-generator pattern.

        Composition discipline. This primitive reads only what
        AnalyzePosition returns on each position. It does not poke
        at lp internals. If a per-position metric isn't on
        PositionAnalysis, it doesn't appear on PortfolioAnalysis — a
        missing aggregate means AnalyzePosition needs to expose the
        underlying scalar first.

        Shared-exposure definition. A token counts as "shared" when it
        appears in two or more position pairs. The warning lists the
        token and the pair names that include it. This is token overlap,
        not statistical correlation — the risk concept LPs actually
        reason about ("if ETH drops, both my positions take the hit")
        rather than a ρ value DeFiPy has no price history to compute.
    """

    def __init__(self):
        pass

    def apply(self, positions):

        """ apply

            Compute the portfolio-level aggregate of N positions.

            Parameters
            ----------
            positions : list[PortfolioPosition]
                One PortfolioPosition per LP position to include.
                Must contain at least one entry. All positions must
                share a common token0 symbol (the portfolio numeraire).

            Returns
            -------
            PortfolioAnalysis
                Structured aggregate with totals in the common
                numeraire, per-position summaries in input order,
                pnl_ranking by worst PnL first, and
                shared_exposure_warnings for tokens appearing in
                multiple positions.

            Raises
            ------
            ValueError
                If positions is empty, or if positions have mismatched
                token0 symbols.
        """

        if not positions:
            raise ValueError(
                "AggregatePortfolio: positions must be a non-empty list"
            )

        numeraires = {p.lp.token0 for p in positions}
        if len(numeraires) > 1:
            raise ValueError(
                "AggregatePortfolio: positions must share a common "
                "token0 numeraire. Got mixed token0 across positions: "
                "{}. Either group positions by their token0 and call "
                "AggregatePortfolio once per group, or wait for "
                "multi-numeraire support in a later release."
                .format(sorted(numeraires))
            )

        numeraire = next(iter(numeraires))

        # Run AnalyzePosition on each input and collect summaries.
        summaries = []
        for p in positions:
            analysis = AnalyzePosition().apply(
                p.lp, p.lp_init_amt, p.entry_x_amt, p.entry_y_amt,
                lwr_tick = p.lwr_tick,
                upr_tick = p.upr_tick,
                holding_period_days = p.holding_period_days,
            )
            display_name = p.name if p.name is not None \
                           else "{}/{}".format(p.lp.token0, p.lp.token1)
            summaries.append(PositionSummary(
                name = display_name,
                net_pnl = analysis.net_pnl,
                il_percentage = analysis.il_percentage,
                fee_income = analysis.fee_income,
                tokens = [p.lp.token0, p.lp.token1],
                analysis = analysis,
            ))

        # Scalar totals. All in the common numeraire.
        total_value = sum(s.analysis.current_value for s in summaries)
        total_hold_value = sum(s.analysis.hold_value for s in summaries)
        total_fees = sum(s.fee_income for s in summaries)
        total_net_pnl = sum(s.net_pnl for s in summaries)

        # PnL ranking: worst net_pnl first, tiebreak on worst
        # il_percentage first. Both ascending (more-negative first).
        pnl_ranking = [
            s.name for s in sorted(
                summaries,
                key = lambda s: (s.net_pnl, s.il_percentage),
            )
        ]

        shared_exposure_warnings = self._detect_shared_exposure(summaries)

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

    def _detect_shared_exposure(self, summaries):

        """ _detect_shared_exposure

            Flag tokens that appear in more than one position's pair.

            Parameters
            ----------
            summaries : list[PositionSummary]

            Returns
            -------
            list[str]
                One warning per token that appears in multiple
                positions, listing the position names that share it.

            Notes
            -----
            The common-numeraire enforcement guarantees every position
            shares token0, so token0 will always appear here as
            "shared across all positions." That's not spurious — it's
            the defining feature of the portfolio and worth stating
            once. The more actionable warnings are for token1 overlaps
            (e.g., two positions both exposed to DAI on the quote side).
        """

        # Build: token → list of position names containing it.
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
