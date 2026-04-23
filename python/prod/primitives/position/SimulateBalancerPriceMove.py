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

from balancerpy.cwpt.exchg import BalancerExchange
from balancerpy.analytics.risk import BalancerImpLoss

from ...utils.data import BalancerPriceMoveScenario


class SimulateBalancerPriceMove:

    """ Project a Balancer 2-asset LP position's value at a hypothetical
        price change.

        Sibling to SimulatePriceMove (V2/V3) and
        SimulateStableswapPriceMove. Answers "what happens if price
        moves by X% from here?" for a Balancer position, using
        BalancerImpLoss's weighted-pool IL formula.

        Answers: Q2.1 (price drop scenario), Q5.1 (market crash),
        Q5.2 (scaling position size) — for Balancer pools.

        Composition over duplication. Math lives in
        balancerpy.analytics.risk.BalancerImpLoss; this primitive
        treats the current pool state as the baseline and simulates
        price shocks against it. The IL formula depends on BOTH alpha
        and the base-token weight, so the weight is surfaced on the
        result dataclass for caller interpretability.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Simulation semantics — from current state, not entry
        ------------------------------------------------------
        A `price_change_pct` of -0.30 models "what if the base token's
        price (in opp units) drops 30% from its CURRENT value." This
        matches the V2/V3 sibling's convention. For historical-entry
        analysis (comparing a known entry composition to a hypothetical
        future price), compose with AnalyzeBalancerPosition — that
        primitive takes entry amounts explicitly and measures against
        them.

        Scope limits
        ------------
        - 2-asset pools only. Inherited from BalancerImpLoss.
        - No fee projection. `fee_projection` is always None on the
          result, matching the V2/V3 sibling and consistent with
          AnalyzeBalancerPosition's no-fee-attribution scope.
        - Paper value, not settlement value. The IL formula gives
          V_LP / V_hold at the simulated price; `new_value` is
          `hold_value_at_new_price * (1 + IL)`. No modeling of
          price impact from actually redeeming and swapping out.

        Numeraire convention
        --------------------
        All values denominated in opp-token units, matching
        BalancerImpLoss and AnalyzeBalancerPosition. For an ETH/DAI
        Balancer pool with ETH as base, `new_value` is in DAI.

        alpha convention
        ----------------
        alpha = 1 + price_change_pct. The price referred to is
        opp-per-base (price of base in opp units). For a 50/50
        ETH/DAI pool, `price_change_pct = -0.30` means ETH drops
        30% in DAI terms, i.e. new DAI-per-ETH spot is 70% of
        current.
    """

    def __init__(self):
        pass

    def apply(self, lp, price_change_pct, lp_init_amt):

        """ apply

            Simulate a price move from the current Balancer pool state
            and compute the resulting position metrics.

            Parameters
            ----------
            lp : BalancerExchange
                2-asset weighted pool. N>2 raises ValueError (via
                BalancerImpLoss). V2/V3/Stableswap pools raise
                ValueError directly.
            price_change_pct : float
                Fractional price change from current price. Must be
                strictly greater than -1.0. Examples:
                  -0.30 → 30% drop, alpha = 0.7
                   0.00 → no move, alpha = 1.0
                  +0.50 → 50% rise, alpha = 1.5
            lp_init_amt : float
                Pool shares held by this position, in human units.
                Must be > 0.

            Returns
            -------
            BalancerPriceMoveScenario

            Raises
            ------
            ValueError
                If lp is not a BalancerExchange, if price_change_pct
                <= -1.0, or if lp_init_amt <= 0. Propagated errors
                from BalancerImpLoss for non-2-asset pools.
        """

        if not isinstance(lp, BalancerExchange):
            raise ValueError(
                "SimulateBalancerPriceMove: lp must be a BalancerExchange; "
                "got {}. For V2/V3 pools use SimulatePriceMove; for "
                "stableswap use SimulateStableswapPriceMove.".format(
                    type(lp).__name__
                )
            )

        if price_change_pct <= -1.0:
            raise ValueError(
                "SimulateBalancerPriceMove: price_change_pct must be "
                "> -1.0 (price cannot go below zero); got {}".format(
                    price_change_pct
                )
            )

        # BalancerImpLoss validates lp_init_amt > 0 and 2-asset; propagate.
        il = BalancerImpLoss(lp, lp_init_amt)

        base_tkn_name = il.base_tkn_name
        opp_tkn_name = il.opp_tkn_name
        w_base = il.base_weight
        w_opp = float(lp.tkn_weights[opp_tkn_name])

        # Fee-free current spot price, opp-per-base. Matches the
        # approach in AnalyzeBalancerPosition — bypass lp.get_price()
        # which bakes in the 0.25% swap-fee scaling.
        b_base = lp.tkn_reserves[base_tkn_name]
        b_opp = lp.tkn_reserves[opp_tkn_name]
        current_spot = (b_opp / w_opp) / (b_base / w_base)

        # "Current value" of the position at the current state, in opp
        # units. This is the LP's pro-rata share of reserves priced at
        # the current spot (paper value).
        current_value = (
            il.base_tkn_init * current_spot + il.opp_tkn_init
        )

        # Alpha for the IL formula. Since we're treating "now" as the
        # reference point, alpha = 1 + shock — the price of base in
        # opp units at the simulated state, relative to its current
        # value.
        alpha = 1.0 + price_change_pct

        # IL at the simulated alpha. Weight stays at w_base (no pool
        # restructuring being modeled).
        il_at_new_price = il.calc_iloss(alpha, weight = w_base)

        # Hold-value counterfactual at the simulated price. If the LP
        # had held their current (base_amt, opp_amt) composition
        # through the move, value in opp units becomes:
        #     base_amt * new_spot + opp_amt
        # where new_spot = current_spot * alpha.
        new_spot = current_spot * alpha
        hold_value_at_new = (
            il.base_tkn_init * new_spot + il.opp_tkn_init
        )

        # LP position value at the simulated price, in opp units.
        # Relationship V_LP = V_hold · (1 + IL) is the same
        # identity SimulatePriceMove uses for V2/V3.
        new_value = hold_value_at_new * (1.0 + il_at_new_price)

        # Fractional change from current to simulated state.
        if current_value > 0:
            value_change_pct = (new_value - current_value) / current_value
        else:
            value_change_pct = 0.0

        return BalancerPriceMoveScenario(
            base_tkn_name = base_tkn_name,
            opp_tkn_name = opp_tkn_name,
            base_weight = w_base,
            new_price_ratio = alpha,
            new_value = new_value,
            il_at_new_price = il_at_new_price,
            fee_projection = None,
            value_change_pct = value_change_pct,
        )
