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

import math

from uniswappy.analytics.risk import UniswapImpLoss
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import TickMath

from balancerpy.cwpt.exchg import BalancerExchange
from balancerpy.analytics.risk import BalancerImpLoss

from stableswappy.cst.exchg import StableswapExchange
from stableswappy.analytics.risk import (
    StableswapImpLoss, DepegUnreachableError,
)

from ..execution import CalculateSlippage
from ...utils.data import ProtocolComparison, ProtocolMetrics


# Floor for tied-comparison equality test. Under this, two IL numbers
# are treated as equal for advantage-label purposes.
_TIED_EPSILON = 1e-9

# Default symmetric shock for IL (±10%) and default V3 range width
# (±10% centered on current price). Both constructor-overridable.
_DEFAULT_PRICE_SHOCK = 0.10
_DEFAULT_V3_RANGE_PCT = 0.10


class CompareProtocols:

    """ Compare impermanent-loss and slippage behavior for the same
        capital across two pools on potentially different AMM protocols.

        Answers Q4.1 from DEFIMIND_TIER1_QUESTIONS.md — "Is Curve
        better than Uniswap for this pair?" — and its generalization
        across the full V2/V3/Balancer/Stableswap matrix. The question
        only DeFiPy can answer cleanly, since it's the one library that
        carries exact-math implementations of all four AMMs in the same
        process space.

        Follows the DeFiPy primitive contract: stateless construction
        (modulo price_shock and v3_range_pct params), computation at
        .apply(), structured dataclass return. Non-mutating —
        composes shipped IL helpers (UniswapImpLoss, BalancerImpLoss,
        StableswapImpLoss) and CalculateSlippage without touching pool
        state.

        Composition pattern: depth-chain. Each per-pool metric fans out
        to the appropriate IL helper by protocol dispatch; results
        aggregate into a pairwise comparison.

        Pure composition, no new math. The IL math for each protocol
        lives in its natural home (uniswappy/balancerpy/stableswappy),
        promoted to that location during the 1.2.0 work. This primitive
        is the capstone of that effort — the one place where "same
        capital, N AMMs, pick winner" becomes mechanically demonstrable.

        Scope & signaling-not-verdict
        ------------------------------
        No single winner label. Different protocols win on different
        axes (IL vs slippage vs TVL depth vs reachability). Collapsing
        to one number hides the trade-off, which is the whole point.
        Independent `il_advantage` and `slippage_advantage` fields
        preserve each axis; callers building a best-of-both-worlds
        summary consume both independently. Matches the
        signal-surfacer convention of CompareFeeTiers,
        DetectRugSignals, and AggregatePortfolio.

        V2/V3/Balancer/Stableswap dispatch
        ----------------------------------
        isinstance against the three sibling-repo exchange classes
        (BalancerExchange, StableswapExchange) plus .version for
        Uniswap V2/V3. Every pool must be one of the four supported
        types; an unrecognized lp raises ValueError immediately.

        V3 range auto-detection
        -----------------------
        V3 pools need a tick range to evaluate IL. v1 auto-picks a
        symmetric range of ±v3_range_pct around the pool's current
        tick (default ±10%), snapped to the pool's tick_spacing. This
        matches EvaluateTickRanges' default shock semantics and
        represents a "moderate concentration" stance that shows V3's
        capital-efficiency story without going degenerately narrow.
        Callers who want a specific range should evaluate via
        EvaluateTickRanges directly.

        V3 IL requires price_shock <= v3_range_pct. The range-aware IL
        formula only holds when alpha stays inside [P_a, P_b]; beyond
        the range, the position is single-sided and the formula's
        scale factor sqrt(r)/(sqrt(r)-1) no longer applies. When the
        caller configures price_shock > v3_range_pct, V3 pools return
        il_at_shock = None with a clarifying note rather than
        extrapolating into the invalid regime. The default config
        (both 0.10) sits exactly at the boundary and computes fine.
        Callers tightening the range should also tighten the shock.

        V3 IL numerics at near-symmetric ranges. The UniswapImpLoss
        range-aware formula uses r = (P_a + P_b) / (2·P_cur). For
        ranges centered on current price, r ≈ 1 and the scale factor
        sqrt(r) / (sqrt(r)-1) becomes highly sensitive to small
        asymmetries introduced by tick snapping. Two v3_range_pct
        values that should in principle produce a monotonic IL
        ordering may flip direction depending on how the auto-range
        ticks land. Use CompareProtocols for side-by-side protocol
        comparison at a single configured range; use EvaluateTickRanges
        (which takes explicit tick ranges) when you need monotonic
        orderings between different V3 range widths.

        Stableswap reachability
        -----------------------
        At high A, a ±10% shock is often unreachable (the pool
        physically cannot reach that peg deviation without draining).
        When StableswapImpLoss raises DepegUnreachableError, the
        primitive sets `il_at_shock = None` for that pool and appends
        a clarifying note. The IL advantage comparison is then
        `None` — genuinely undefined. This is honest to the physics;
        the alternative (silently substituting max-reachable IL) would
        change the alpha being compared and produce misleading
        rankings.

        Slippage scope (v1)
        -------------------
        Slippage is V2/V3 only in v1, because CalculateSlippage only
        covers Uniswap. Balancer and Stableswap pools get
        `slippage_at_amount = None` with a documented note. A future
        extension will add protocol-specific slippage computation to
        CalculateSlippage or a sibling helper; for now, callers
        wanting Balancer/Stableswap slippage compose with
        protocol-native tooling outside this primitive.

        Common token requirement
        ------------------------
        Both pools must contain a token with the symbol matching
        `token_in`. Cross-pair comparisons (ETH/DAI vs BTC/USDC) are
        explicitly rejected rather than allowed with
        apples-to-oranges numeraires.
    """

    def __init__(self,
                 price_shock = _DEFAULT_PRICE_SHOCK,
                 v3_range_pct = _DEFAULT_V3_RANGE_PCT):

        """ __init__

            Parameters
            ----------
            price_shock : float, optional
                Symmetric shock magnitude used for IL comparison.
                Default 0.10 (±10%). Must lie in (0, 1).
            v3_range_pct : float, optional
                For V3 pools, half-width of the default tick range
                as a fraction of current price. Default 0.10 (±10%).
                Must lie in (0, 1).

            Raises
            ------
            ValueError
                If either parameter is outside (0, 1).
        """

        if not (0 < price_shock < 1):
            raise ValueError(
                "CompareProtocols: price_shock must be in (0, 1); "
                "got {}".format(price_shock)
            )
        if not (0 < v3_range_pct < 1):
            raise ValueError(
                "CompareProtocols: v3_range_pct must be in (0, 1); "
                "got {}".format(v3_range_pct)
            )
        self.price_shock = price_shock
        self.v3_range_pct = v3_range_pct

    def apply(self, lp_a, lp_b, amount, token_in = None):

        """ apply

            Run the pairwise comparison.

            Parameters
            ----------
            lp_a, lp_b : Exchange
                Pool objects from any supported protocol (V2, V3,
                Balancer, Stableswap). Bare lp inputs — no
                candidate-wrapper dataclass needed because V3 ticks
                are auto-detected and Balancer/Stableswap have no
                range to configure.
            amount : float
                Reference trade size in `token_in` units, used for
                slippage computation on V2/V3 pools. Must be > 0.
            token_in : ERC20, optional
                The token both pools will evaluate against. When None,
                defaults to the ERC20 for lp_a's token0 (resolved from
                the factory's token registry). Both pools must contain
                a token by this name; otherwise ValueError.

            Returns
            -------
            ProtocolComparison

            Raises
            ------
            ValueError
                On any of: amount <= 0; unrecognized lp protocol;
                common-token violation; V3 auto-range computation
                fails due to uninitialized pool state.
        """

        if amount <= 0:
            raise ValueError(
                "CompareProtocols: amount must be > 0; got {}"
                .format(amount)
            )

        # Resolve token_in default lazily from lp_a's factory token
        # registry. Matches how CalculateSlippage looks up token_out.
        if token_in is None:
            token_in = self._default_token(lp_a)

        # Validate: both pools hold a token by that symbol.
        self._check_common_token(lp_a, lp_b, token_in)

        notes = []
        metrics_a = self._analyze_pool(lp_a, token_in, amount,
                                       "pool_a", notes)
        metrics_b = self._analyze_pool(lp_b, token_in, amount,
                                       "pool_b", notes)

        il_advantage = self._advantage(
            metrics_a.il_at_shock, metrics_b.il_at_shock,
            smaller_wins = True,
        )
        slippage_advantage = self._advantage(
            metrics_a.slippage_at_amount, metrics_b.slippage_at_amount,
            smaller_wins = True,
        )

        return ProtocolComparison(
            price_shock = self.price_shock,
            amount = amount,
            token_in_name = token_in.token_name,
            pool_a = metrics_a,
            pool_b = metrics_b,
            il_advantage = il_advantage,
            slippage_advantage = slippage_advantage,
            notes = notes,
        )

    # ─── Per-pool analysis (protocol dispatch) ─────────────────────────

    def _analyze_pool(self, lp, token_in, amount, pool_label, notes):

        """ _analyze_pool

            Build ProtocolMetrics for one pool by dispatching on
            protocol. Notes (scope flags, unreachability) are appended
            to the shared `notes` list in place.
        """

        protocol = self._detect_protocol(lp)

        if protocol == "uniswap_v2":
            return self._analyze_v2(lp, token_in, amount,
                                    pool_label, notes)
        if protocol == "uniswap_v3":
            return self._analyze_v3(lp, token_in, amount,
                                    pool_label, notes)
        if protocol == "balancer":
            return self._analyze_balancer(lp, token_in, amount,
                                          pool_label, notes)
        if protocol == "stableswap":
            return self._analyze_stableswap(lp, token_in, amount,
                                            pool_label, notes)

        # Shouldn't happen after _detect_protocol — but fail loudly if
        # new protocols are added without updating the dispatch.
        raise ValueError(
            "CompareProtocols: unhandled protocol {!r}".format(protocol)
        )

    def _analyze_v2(self, lp, token_in, amount, pool_label, notes):

        # lp_init_amt of 1.0 gives a scale-free IL fraction; the exact
        # value doesn't matter for calc_iloss, which returns a ratio.
        il = UniswapImpLoss(lp, 1.0)
        alpha_up = 1.0 + self.price_shock
        alpha_dn = 1.0 - self.price_shock
        il_at_shock = 0.5 * (
            abs(il.calc_iloss(alpha_up))
            + abs(il.calc_iloss(alpha_dn))
        )

        slippage = CalculateSlippage().apply(
            lp, token_in, amount,
        ).slippage_pct

        tvl = self._v2_tvl_in_token_in(lp, token_in)

        return ProtocolMetrics(
            pool_label = pool_label,
            protocol = "uniswap_v2",
            il_at_shock = il_at_shock,
            slippage_at_amount = slippage,
            tvl_in_token_in = tvl,
        )

    def _analyze_v3(self, lp, token_in, amount, pool_label, notes):

        lwr_tick, upr_tick = self._auto_v3_range(lp)

        # V3 IL formula is only valid when alpha stays INSIDE the
        # position's price range. When price_shock > v3_range_pct, the
        # shock pushes alpha outside [P_a, P_b] — the position
        # becomes single-sided and the range-aware IL scale factor
        # sqrt(r)/(sqrt(r)-1) blows up into nonsense. Return None
        # rather than extrapolate a formula past its valid domain.
        if self.price_shock > self.v3_range_pct:
            notes.append(
                "{}: V3 IL undefined — price_shock {:.0%} exceeds "
                "v3_range_pct {:.0%}. Position would be out-of-range "
                "at shocked alpha; IL formula only valid in-range. "
                "Lower price_shock or widen v3_range_pct to compute."
                .format(pool_label, self.price_shock, self.v3_range_pct)
            )
            slippage = CalculateSlippage().apply(
                lp, token_in, amount,
                lwr_tick = lwr_tick, upr_tick = upr_tick,
            ).slippage_pct
            tvl = self._v3_tvl_in_token_in(lp, token_in)
            return ProtocolMetrics(
                pool_label = pool_label,
                protocol = "uniswap_v3",
                il_at_shock = None,
                slippage_at_amount = slippage,
                tvl_in_token_in = tvl,
            )

        il = UniswapImpLoss(lp, 1.0, lwr_tick, upr_tick)
        r = il.calc_price_range(lwr_tick, upr_tick)
        alpha_up = 1.0 + self.price_shock
        alpha_dn = 1.0 - self.price_shock
        il_at_shock = 0.5 * (
            abs(il.calc_iloss(alpha_up, r))
            + abs(il.calc_iloss(alpha_dn, r))
        )

        slippage = CalculateSlippage().apply(
            lp, token_in, amount,
            lwr_tick = lwr_tick, upr_tick = upr_tick,
        ).slippage_pct

        tvl = self._v3_tvl_in_token_in(lp, token_in)

        notes.append(
            "{}: V3 evaluated at auto-range ±{:.0%} ({}, {})"
            .format(pool_label, self.v3_range_pct, lwr_tick, upr_tick)
        )

        return ProtocolMetrics(
            pool_label = pool_label,
            protocol = "uniswap_v3",
            il_at_shock = il_at_shock,
            slippage_at_amount = slippage,
            tvl_in_token_in = tvl,
        )

    def _analyze_balancer(self, lp, token_in, amount, pool_label, notes):

        il = BalancerImpLoss(lp, lp.pool_shares)

        # Balancer IL is computed with the supplied token as base
        # unless its construction-time base doesn't match — in which
        # case we use the inverse-alpha symmetry and a flipped weight.
        # calc_iloss accepts a weight override for that case.
        w_base = lp.tkn_weights[token_in.token_name]
        alpha_up = 1.0 + self.price_shock
        alpha_dn = 1.0 - self.price_shock
        il_at_shock = 0.5 * (
            abs(il.calc_iloss(alpha_up, weight = w_base))
            + abs(il.calc_iloss(alpha_dn, weight = w_base))
        )

        tvl = self._balancer_tvl_in_token_in(lp, token_in)

        notes.append(
            "{}: Balancer slippage not computed in v1 "
            "(CalculateSlippage is Uniswap-only)".format(pool_label)
        )

        return ProtocolMetrics(
            pool_label = pool_label,
            protocol = "balancer",
            il_at_shock = il_at_shock,
            slippage_at_amount = None,
            tvl_in_token_in = tvl,
        )

    def _analyze_stableswap(self, lp, token_in, amount, pool_label, notes):

        # Use total supply as reference lp_init_amt — IL returned by
        # calc_iloss is scale-free. (100% ownership would exhibit the
        # same IL ratio as any other ownership fraction.)
        lp_init_amt = lp.dec2amt(lp.math_pool.tokens, 18)
        il = StableswapImpLoss(lp, lp_init_amt)

        alpha_up = 1.0 + self.price_shock
        alpha_dn = 1.0 - self.price_shock
        try:
            il_up = abs(il.calc_iloss(alpha_up))
            il_dn = abs(il.calc_iloss(alpha_dn))
            il_at_shock = 0.5 * (il_up + il_dn)
        except DepegUnreachableError as e:
            il_at_shock = None
            notes.append(
                "{}: stableswap unreachable at ±{:.0%} shock (A={}); "
                "max reachable |1-alpha| ≈ {:.4f}".format(
                    pool_label, self.price_shock, e.A,
                    e.max_reachable_delta or float('nan'),
                )
            )

        tvl = self._stableswap_tvl_in_token_in(lp, token_in)

        notes.append(
            "{}: stableswap slippage not computed in v1 "
            "(CalculateSlippage is Uniswap-only)".format(pool_label)
        )

        return ProtocolMetrics(
            pool_label = pool_label,
            protocol = "stableswap",
            il_at_shock = il_at_shock,
            slippage_at_amount = None,
            tvl_in_token_in = tvl,
        )

    # ─── Protocol detection ────────────────────────────────────────────

    def _detect_protocol(self, lp):

        """ _detect_protocol

            Dispatch on class identity for Balancer/Stableswap, and
            on .version for Uniswap. V3 takes precedence over V2 in
            the Uniswap branch (the default .version is 'V2' on the
            factory; V3 is set explicitly).

            Raises
            ------
            ValueError
                If the lp is not an instance of any of the four
                supported exchange types.
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
            "CompareProtocols: unrecognized lp type {}. Supported: "
            "UniswapExchange (V2/V3), BalancerExchange, StableswapExchange."
            .format(type(lp).__name__)
        )

    # ─── Common-token validation ───────────────────────────────────────

    def _default_token(self, lp):

        """ _default_token

            Resolve lp's token0 to an ERC20 object via the factory's
            token registry. Protocol-specific — Balancer and
            Stableswap pools store tokens in the vault rather than
            the factory.
        """

        if isinstance(lp, (BalancerExchange, StableswapExchange)):
            # vault.get_names() returns names in insertion order;
            # first entry is the natural token0 analog.
            first_name = list(lp.tkn_reserves.keys())[0]
            return lp.vault.get_token(first_name)

        # Uniswap path: factory registry.
        return lp.factory.token_from_exchange[lp.name][lp.token0]

    def _check_common_token(self, lp_a, lp_b, token_in):

        """ _check_common_token

            Both pools must hold a token whose name matches
            token_in.token_name. Cross-pair comparisons are rejected
            — IL on ETH/DAI vs IL on BTC/USDT are independent
            questions and conflating them would produce a meaningless
            advantage label.
        """

        name = token_in.token_name
        for label, lp in (("pool_a", lp_a), ("pool_b", lp_b)):
            tokens_in_pool = self._tokens_in_pool(lp)
            if name not in tokens_in_pool:
                raise ValueError(
                    "CompareProtocols: {} does not contain token_in "
                    "{!r}; pool holds {}. Both pools must share the "
                    "input token."
                    .format(label, name, tokens_in_pool)
                )

    def _tokens_in_pool(self, lp):

        if isinstance(lp, (BalancerExchange, StableswapExchange)):
            return list(lp.tkn_reserves.keys())
        return [lp.token0, lp.token1]

    # ─── V3 auto-range ─────────────────────────────────────────────────

    def _auto_v3_range(self, lp):

        """ _auto_v3_range

            Compute a symmetric ±self.v3_range_pct tick range around
            the pool's current price, snapped to the pool's
            tick_spacing.

            Returns
            -------
            (int, int)
                (lwr_tick, upr_tick).

            Raises
            ------
            ValueError
                If the pool is uninitialized (sqrtPriceX96 == 0).
            """

        if lp.slot0.sqrtPriceX96 == 0:
            raise ValueError(
                "CompareProtocols: V3 pool is uninitialized "
                "(sqrtPriceX96 == 0). Cannot auto-detect tick range."
            )

        Q96 = 2 ** 96
        sqrtp_cur = lp.slot0.sqrtPriceX96 / Q96
        p_cur = sqrtp_cur ** 2

        p_lo = p_cur * (1 - self.v3_range_pct)
        p_hi = p_cur * (1 + self.v3_range_pct)

        tick_lo_raw = math.floor(math.log(p_lo) / math.log(1.0001))
        tick_hi_raw = math.ceil(math.log(p_hi) / math.log(1.0001))

        ts = lp.tickSpacing
        # Floor-snap the lower bound and ceil-snap the upper to
        # guarantee the range brackets current_tick.
        lwr_tick = (tick_lo_raw // ts) * ts
        upr_tick = ((tick_hi_raw + ts - 1) // ts) * ts
        if lwr_tick >= upr_tick:
            upr_tick = lwr_tick + ts
        return lwr_tick, upr_tick

    # ─── TVL computation per protocol ──────────────────────────────────

    def _v2_tvl_in_token_in(self, lp, token_in):

        tokens = lp.factory.token_from_exchange[lp.name]
        token_in_erc = tokens[token_in.token_name]
        # Other token in the pair.
        other_name = (lp.token1 if token_in.token_name == lp.token0
                      else lp.token0)
        reserve_in = lp.get_reserve(token_in_erc)
        reserve_other = lp.get_reserve(tokens[other_name])
        spot_in_per_other = lp.get_price(tokens[other_name])
        return reserve_in + reserve_other * spot_in_per_other

    def _v3_tvl_in_token_in(self, lp, token_in):
        # V3 exchange has the same get_reserve/get_price API as V2.
        return self._v2_tvl_in_token_in(lp, token_in)

    def _balancer_tvl_in_token_in(self, lp, token_in):
        # Sum each token's reserve, converted to token_in via spot.
        # For 2-asset Balancer pools this is straightforward.
        total = 0.0
        for tkn_name, reserve in lp.tkn_reserves.items():
            if tkn_name == token_in.token_name:
                total += reserve
            else:
                # Compute fee-free weight-adjusted spot: token_in per
                # this token. Uses the same inline-computation pattern
                # BalancerImpLoss uses internally (see its .apply()
                # inline docs — lp.get_price bakes in a fee scale we
                # don't want for TVL).
                b_in = lp.tkn_reserves[token_in.token_name]
                b_ot = reserve
                w_in = lp.tkn_weights[token_in.token_name]
                w_ot = lp.tkn_weights[tkn_name]
                if b_ot <= 0 or w_in <= 0 or w_ot <= 0:
                    continue
                # Price of `tkn_name` in units of token_in:
                #   (b_in / w_in) / (b_ot / w_ot)
                price = (b_in / w_in) / (b_ot / w_ot)
                total += reserve * price
        return total

    def _stableswap_tvl_in_token_in(self, lp, token_in):
        # Stableswap assets are pegged 1:1 at the ideal balance point,
        # so a sum of human reserves is a correct TVL under the peg
        # assumption. At any actual pool state the peg may be broken
        # but the human-reserves sum is the conventional TVL proxy.
        return sum(lp.tkn_reserves.values())

    # ─── Advantage label ──────────────────────────────────────────────

    def _advantage(self, value_a, value_b, smaller_wins):

        """ _advantage

            Compare two values and return "pool_a" | "pool_b" | "tied"
            | None. Both must be non-None to produce a verdict; if
            either is None, the comparison is undefined (None).

            Parameters
            ----------
            value_a, value_b : Optional[float]
                The two metric values. None means undefined.
            smaller_wins : bool
                True for IL and slippage — lower is better. False
                would be for metrics where higher wins (not used in
                v1).
        """

        if value_a is None or value_b is None:
            return None
        if abs(value_a - value_b) < _TIED_EPSILON:
            return "tied"
        if smaller_wins:
            return "pool_a" if value_a < value_b else "pool_b"
        return "pool_a" if value_a > value_b else "pool_b"
