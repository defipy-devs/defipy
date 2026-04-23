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

from stableswappy.cst.exchg import StableswapExchange
from stableswappy.analytics.risk import (
    StableswapImpLoss, DepegUnreachableError,
)

from ...utils.data import StableswapPositionAnalysis


# Reachability tolerance for the "at peg" short-circuit. When the
# pool's implied |1 - dydx| is below this threshold we treat it as
# perfectly balanced and skip the fixed-point IL computation —
# both for performance and to avoid the epsilon=0 degenerate case
# bouncing through the solver.
_AT_PEG_TOL = 1e-12


class AnalyzeStableswapPosition:

    """ Decompose a 2-asset stableswap LP position into IL, fees, net PnL.

        Sibling to AnalyzePosition (V2/V3) and AnalyzeBalancerPosition.
        Answers the same question — "how is this position doing?" —
        adapted to stableswap's flat-curve IL regime where small
        price deviations can produce surprisingly large IL at high A.

        Answers the core diagnostic questions for any stableswap LP
        position:
          - Is this position losing money to depeg dynamics?
          - At this A, is my position exposed to the
            strong-negative-convexity regime?
          - What's the real APR including IL?

        Composition over duplication. The IL math lives in
        stableswappy.analytics.risk.StableswapImpLoss (lifted there
        during the 1.2.0 work). This primitive composes it. Same
        pattern used by AssessDepegRisk after its Phase 2b refactor.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Scope limits
        ------------
        - 2-asset pools only. Inherited from StableswapImpLoss.
        - No fee income attribution. Stableswap's self.tkn_fees is
          pool-global with no per-LP attribution; same scope stance
          as AnalyzeBalancerPosition. fee_income is always 0.0.
        - No historical price-change tracking. The IL formula treats
          the pool's current dydx as the "observed alpha." Callers
          comparing entry-alpha to current-alpha should feed entry
          price context externally (via SimulatePriceMove with an
          explicit shock, when that primitive ships for stableswap).

        Reachability
        ------------
        At high A, small |1 - alpha| shocks may be unreachable
        (|ε| >= 0.95). When the current pool state implies such an
        alpha, the primitive catches DepegUnreachableError and emits:
          - il_percentage = None
          - net_pnl = None
          - diagnosis = "unreachable_alpha"
          - current_value = hold_value (conservatively — without IL
            we can't back out a per-token composition)
        This matches the None-sentinel convention used by
        AssessDepegRisk and CompareProtocols. In practice it's rare
        for a pool's OWN state to drift past reachability (self-
        consistency of the invariant keeps it inside), but honest
        handling avoids silent surprises.

        Numeraire convention
        --------------------
        All values are denominated at peg — sum across tokens valued
        1:1. This is stableswap's natural numeraire (no divergence ==
        tokens equivalent in value) and matches StableswapImpLoss's
        `hold_value()`. Callers wanting a non-peg numeraire can
        rebase manually.

        entry_amounts shape
        -------------------
        Takes a list `entry_amounts: [x0, x1]` of the caller's
        actual deposit composition. For stableswap, balanced
        deposits [x, x] are the common case but not the only one —
        single-sided deposits produce skewed entry compositions,
        and the IL calculation has to account for this. Public
        signature takes the list for generality.
    """

    def __init__(self):
        pass

    def apply(self, lp, lp_init_amt, entry_amounts,
              holding_period_days = None):

        """ apply

            Compute full position decomposition.

            Parameters
            ----------
            lp : StableswapExchange
                2-asset stableswap pool. N>2 raises ValueError (via
                StableswapImpLoss). V2/V3/Balancer pools raise
                ValueError directly.
            lp_init_amt : float
                LP tokens held by this position, in human units.
                Must be > 0.
            entry_amounts : list[float]
                Per-token entry amounts in pool's insertion order.
                Must have exactly 2 entries (matching the pool's N).
                Each entry > 0.
            holding_period_days : float, optional
                Days the position has been held. When provided,
                real_apr is annualized. Otherwise None.

            Returns
            -------
            StableswapPositionAnalysis

            Raises
            ------
            ValueError
                If lp is not a StableswapExchange; if lp_init_amt <= 0;
                if entry_amounts length != 2 or any entry <= 0;
                propagated errors from StableswapImpLoss for non-2-asset
                pools or uninitialized math_pool.
        """

        if not isinstance(lp, StableswapExchange):
            raise ValueError(
                "AnalyzeStableswapPosition: lp must be a "
                "StableswapExchange; got {}. For V2/V3 pools use "
                "AnalyzePosition; for Balancer use "
                "AnalyzeBalancerPosition.".format(type(lp).__name__)
            )

        if not isinstance(entry_amounts, (list, tuple)):
            raise ValueError(
                "AnalyzeStableswapPosition: entry_amounts must be a "
                "list or tuple; got {}".format(type(entry_amounts).__name__)
            )

        if len(entry_amounts) != 2:
            raise ValueError(
                "AnalyzeStableswapPosition: entry_amounts must have "
                "exactly 2 entries (2-asset pools only in v1); "
                "got {} entries".format(len(entry_amounts))
            )

        for i, amt in enumerate(entry_amounts):
            if amt <= 0:
                raise ValueError(
                    "AnalyzeStableswapPosition: entry_amounts[{}] "
                    "must be > 0; got {}".format(i, amt)
                )

        # Construct IL helper. Validates lp_init_amt > 0, pool joined,
        # 2-asset.
        il = StableswapImpLoss(lp, lp_init_amt)
        token_names = list(il.token_names)
        A = int(il.A)

        # Read current implied alpha from pool state via dydx. When the
        # pool is balanced dydx ~ 1.0; when depegged it drifts.
        dydx = lp.math_pool.dydx(0, 1, use_fee = False)
        if dydx is None or dydx <= 0:
            alpha = None
        else:
            alpha = float(dydx)

        hold_value = float(sum(entry_amounts))

        # ─── At-peg short-circuit ───────────────────────────────────────
        # Skip the IL solver when dydx is essentially 1.0 — the math
        # is exact (IL = 0) and the short-circuit avoids epsilon=0
        # edge cases in the fixed-point loop.
        if alpha is None or abs(1.0 - alpha) < _AT_PEG_TOL:
            return self._at_peg_result(
                il, token_names, A, hold_value, entry_amounts,
                alpha, holding_period_days,
            )

        # ─── Solve IL; catch unreachable ────────────────────────────────
        try:
            il_raw = il.calc_iloss(alpha)
        except DepegUnreachableError:
            return self._unreachable_result(
                token_names, A, hold_value, entry_amounts,
                alpha, holding_period_days,
            )

        # ─── Reachable path ─────────────────────────────────────────────
        # Current LP value at peg-numeraire: hold_value · (1 + IL).
        # IL <= 0 so current_value <= hold_value; equals hold at α=1.
        current_value = hold_value * (1.0 + il_raw)
        net_pnl = current_value - hold_value

        # Per-token current amounts — derive from the pool's current
        # reserve composition at the LP's share. For stableswap this
        # is the honest readout: at depeg the LP doesn't hold 50/50
        # anymore, they hold whatever composition the arbitrageurs
        # have pushed the pool into.
        lp_share = il.lp_share_frac
        per_token_current = [
            float(lp.tkn_reserves[nm] * lp_share)
            for nm in token_names
        ]

        fee_income = 0.0
        il_with_fees = il_raw

        if holding_period_days is not None and holding_period_days > 0:
            real_apr = (net_pnl / hold_value) * (365.0 / holding_period_days)
        else:
            real_apr = None

        diagnosis = "net_positive" if net_pnl > 0 else "il_dominant"

        return StableswapPositionAnalysis(
            token_names = token_names,
            A = A,
            current_value = current_value,
            hold_value = hold_value,
            il_percentage = il_raw,
            il_with_fees = il_with_fees,
            fee_income = fee_income,
            net_pnl = net_pnl,
            real_apr = real_apr,
            diagnosis = diagnosis,
            alpha = alpha,
            per_token_init = list(entry_amounts),
            per_token_current = per_token_current,
        )

    # ─── Short-circuit helpers ──────────────────────────────────────────

    def _at_peg_result(self, il, token_names, A, hold_value,
                       entry_amounts, alpha, holding_period_days):

        """ Build result for balanced pool (alpha ≈ 1, IL = 0 exactly). """

        # At peg, per-token current == per-token init (within float
        # tolerance) and current_value == hold_value.
        lp_share = il.lp_share_frac
        per_token_current = [
            float(il.lp.tkn_reserves[nm] * lp_share)
            for nm in token_names
        ]

        if holding_period_days is not None and holding_period_days > 0:
            real_apr = 0.0
        else:
            real_apr = None

        return StableswapPositionAnalysis(
            token_names = token_names,
            A = A,
            current_value = hold_value,
            hold_value = hold_value,
            il_percentage = 0.0,
            il_with_fees = 0.0,
            fee_income = 0.0,
            net_pnl = 0.0,
            real_apr = real_apr,
            diagnosis = "at_peg",
            alpha = alpha if alpha is not None else 1.0,
            per_token_init = list(entry_amounts),
            per_token_current = per_token_current,
        )

    def _unreachable_result(self, token_names, A, hold_value,
                            entry_amounts, alpha, holding_period_days):

        """ Build result for unreachable-alpha regime.

            IL is undefined, so net_pnl is too. Conservatively set
            current_value = hold_value (the best we can say without
            a valid IL number) and flag the condition via diagnosis.
        """

        return StableswapPositionAnalysis(
            token_names = token_names,
            A = A,
            current_value = hold_value,
            hold_value = hold_value,
            il_percentage = None,
            il_with_fees = None,
            fee_income = 0.0,
            net_pnl = None,
            real_apr = None,
            diagnosis = "unreachable_alpha",
            alpha = alpha,
            per_token_init = list(entry_amounts),
            per_token_current = [],
        )
