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

from ...utils.data import StableswapPriceMoveScenario


# Reachability tolerance for the at-peg short-circuit. Matches
# AnalyzeStableswapPosition's _AT_PEG_TOL so the two primitives
# behave identically at the balanced-pool boundary.
_AT_PEG_TOL = 1e-12


class SimulateStableswapPriceMove:

    """ Project a stableswap 2-asset LP position's value at a hypothetical
        depeg.

        Sibling to SimulatePriceMove (V2/V3) and
        SimulateBalancerPriceMove. Answers "what happens if the
        depegged asset's price moves X% from its current value?" for
        a stableswap position, using StableswapImpLoss's closed-form
        invariant expansion.

        Answers: Q2.1 (depeg scenario), Q5.1 (market crash, for
        stablecoins specifically) — for stableswap pools.

        Composition over duplication. Math lives in
        stableswappy.analytics.risk.StableswapImpLoss. This primitive
        treats the current pool state as the baseline, builds the
        implied "current alpha" from dydx, then simulates moves
        against that.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Simulation semantics — from current state, not entry
        ------------------------------------------------------
        A `price_change_pct` of -0.05 models "what if the current
        dydx drifted 5% further." The framing is intentionally
        shock-from-here, consistent with the V2/V3 and Balancer
        siblings. For historical-entry analysis compose with
        AnalyzeStableswapPosition.

        Alpha derivation at current state
        ---------------------------------
        Stableswap's "alpha" is the ratio of one asset's price to peg.
        At a balanced pool this is 1.0 (dydx = 1.0). At a depegged
        pool it's whatever dydx reads. The simulation scales the
        current alpha by (1 + price_change_pct): from a balanced
        pool, a 5% shock means alpha moves from 1.0 to 1.05; from a
        pool at dydx = 0.98, a -2% shock means alpha moves to
        0.98 * 0.98 = 0.9604.

        Simulating "from here" this way lets the caller probe how
        bad things could get given the pool's current state, without
        having to pretend the pool is balanced first.

        Unreachable-alpha handling
        --------------------------
        At high A, some shock sizes produce alphas that exceed the
        reachability bound (|ε| >= 0.95). When this happens, the
        returned dataclass has:
          - il_at_new_price = None
          - new_value = None
          - value_change_pct = None
        The new_price_ratio, A, and token_names remain populated so
        the caller can see WHAT was unreachable. Same convention as
        AnalyzeStableswapPosition and AssessDepegRisk.

        Scope limits
        ------------
        - 2-asset pools only. Inherited from StableswapImpLoss.
        - No fee projection.
        - Leading-order expansion accuracy; good for |ε| < 0.8.

        Numeraire convention
        --------------------
        Values in peg numeraire (tokens 1:1). Matches
        StableswapImpLoss.hold_value() and AnalyzeStableswapPosition.
    """

    def __init__(self):
        pass

    def apply(self, lp, price_change_pct, lp_init_amt):

        """ apply

            Simulate a price move from the current stableswap pool
            state and compute the resulting position metrics.

            Parameters
            ----------
            lp : StableswapExchange
                2-asset stableswap pool. N>2 raises ValueError (via
                StableswapImpLoss). V2/V3/Balancer pools raise
                ValueError directly.
            price_change_pct : float
                Fractional shock to the current alpha. Must be
                strictly greater than -1.0. Simulated alpha is
                `current_alpha * (1 + price_change_pct)`.
            lp_init_amt : float
                LP tokens held by this position, in human units.
                Must be > 0.

            Returns
            -------
            StableswapPriceMoveScenario

            Raises
            ------
            ValueError
                If lp is not a StableswapExchange, if price_change_pct
                <= -1.0, or if lp_init_amt <= 0. Propagated errors
                from StableswapImpLoss for non-2-asset pools.
        """

        if not isinstance(lp, StableswapExchange):
            raise ValueError(
                "SimulateStableswapPriceMove: lp must be a "
                "StableswapExchange; got {}. For V2/V3 use "
                "SimulatePriceMove; for Balancer use "
                "SimulateBalancerPriceMove.".format(type(lp).__name__)
            )

        if price_change_pct <= -1.0:
            raise ValueError(
                "SimulateStableswapPriceMove: price_change_pct must be "
                "> -1.0 (price cannot go below zero); got {}".format(
                    price_change_pct
                )
            )

        # StableswapImpLoss validates lp_init_amt > 0, 2-asset, and
        # math_pool initialized.
        il = StableswapImpLoss(lp, lp_init_amt)
        token_names = list(il.token_names)
        A = int(il.A)

        # "Current value" in peg numeraire is the LP's pro-rata share
        # of current reserves (valued 1:1). This matches
        # StableswapImpLoss.hold_value() at any pool state, and
        # AnalyzeStableswapPosition's current_value at the at-peg
        # short-circuit.
        lp_share = il.lp_share_frac
        current_per_token = [
            float(lp.tkn_reserves[nm] * lp_share) for nm in token_names
        ]
        current_value = sum(current_per_token)

        # Read the current alpha from dydx. At a balanced pool this is
        # ~1.0; for a depegged pool it drifts from 1.0.
        dydx = lp.math_pool.dydx(0, 1, use_fee = False)
        if dydx is None or dydx <= 0:
            current_alpha = 1.0
        else:
            current_alpha = float(dydx)

        # Simulated alpha: scale the current alpha by (1 + shock).
        # For a balanced pool this is just (1 + shock); for a pool
        # already off-peg it compounds the shock onto the existing
        # drift.
        new_alpha = current_alpha * (1.0 + price_change_pct)

        # At-peg short-circuit: if the simulated alpha is essentially
        # 1.0, IL is exactly 0 and new_value == current_value.
        if abs(1.0 - new_alpha) < _AT_PEG_TOL:
            return StableswapPriceMoveScenario(
                token_names = token_names,
                A = A,
                new_price_ratio = new_alpha,
                new_value = current_value,
                il_at_new_price = 0.0,
                fee_projection = None,
                value_change_pct = 0.0,
            )

        # Otherwise invoke the IL solver. Catch unreachability and
        # return a partial result with None on the numeric fields.
        try:
            il_at_new_price = il.calc_iloss(new_alpha)
        except DepegUnreachableError:
            return StableswapPriceMoveScenario(
                token_names = token_names,
                A = A,
                new_price_ratio = new_alpha,
                new_value = None,
                il_at_new_price = None,
                fee_projection = None,
                value_change_pct = None,
            )

        # Reachable path. Stableswap's natural hold counterfactual at
        # peg numeraire is just the sum — unchanged across price moves
        # (stables are valued 1:1 at peg regardless of which one moves).
        # So hold_value_at_new == current_value, and
        # new_value = current_value * (1 + IL).
        #
        # This is a clean consequence of the peg numeraire: unlike
        # V2/V3 or Balancer (where hold_value shifts with the new
        # price), stableswap's hold_value is simulation-invariant.
        new_value = current_value * (1.0 + il_at_new_price)

        if current_value > 0:
            value_change_pct = (new_value - current_value) / current_value
        else:
            value_change_pct = 0.0

        return StableswapPriceMoveScenario(
            token_names = token_names,
            A = A,
            new_price_ratio = new_alpha,
            new_value = new_value,
            il_at_new_price = il_at_new_price,
            fee_projection = None,
            value_change_pct = value_change_pct,
        )
