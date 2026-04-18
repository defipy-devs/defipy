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

from uniswappy.analytics.risk import UniswapImpLoss
from uniswappy.utils.data import UniswapExchangeData
from ...utils.data import PriceMoveScenario


class SimulatePriceMove:

    """ Project an LP position's value at a hypothetical price change.

        Answers "what happens if price moves by X%?" for a given position
        at the current LP state. The simulation treats the current state
        as the baseline — a price_change_pct of -0.30 means "what if
        price drops 30% FROM HERE" — not from some historical entry
        price. This distinguishes SimulatePriceMove from AnalyzePosition,
        which measures outcomes against a real entry state.

        Answers: Q2.1 (price drop scenario), Q5.1 (market crash), Q5.2
        (scaling position size — pass a different position_size_lp to
        see how absolute exposure scales).

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        The "price" that price_change_pct refers to is the price of
        token0 expressed in token1 (consistent with lp.get_price(token0)
        and with AnalyzePosition's alpha convention). For an ETH/DAI
        pool where ETH is token0, a price_change_pct of -0.30 models
        ETH dropping 30% against DAI.

        Values are returned in token0 numeraire — matching AnalyzePosition.
        For an ETH/DAI pool where ETH is token0, "new_value" is expressed
        in ETH.

        This primitive does not model fee income. The `fee_projection`
        field in the returned dataclass is always None. Fee-involved
        analyses (break-even time, rebalancing cost-benefit) live in
        dedicated primitives that take holding period and fee-rate
        context explicitly.

        Value semantics: paper value, not settlement value. The returned
        new_value is computed against the linear share of current reserves
        entitled to position_size_lp — it does not model the price impact
        of actually redeeming and swapping out. This makes the output
        scale-invariant (doubling position_size_lp doubles new_value) and
        is the correct interpretation for hypothetical-value analysis.
        AnalyzePosition uses the same paper-value convention; the two
        primitives agree on how a position is valued at any given state.
    """

    def __init__(self):
        pass

    def apply(self, lp, price_change_pct, position_size_lp,
              lwr_tick = None, upr_tick = None):

        """ apply

            Simulate a price move from the current LP state and compute
            the resulting position metrics.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current pool state.
            price_change_pct : float
                Fractional price change from current price. Must be
                strictly greater than -1.0 (price cannot go below zero).
                Examples:
                  -0.30 → 30% drop, alpha = 0.7
                   0.00 → no move, alpha = 1.0
                  +0.50 → 50% rise, alpha = 1.5
            position_size_lp : float
                LP tokens held by the position, in human units. Must be
                strictly greater than zero.
            lwr_tick : int, optional
                Lower tick of the position (V3 only).
            upr_tick : int, optional
                Upper tick of the position (V3 only).

            Returns
            -------
            PriceMoveScenario
                Structured result with new_price_ratio, new_value,
                il_at_new_price, fee_projection (always None), and
                value_change_pct.

            Raises
            ------
            ValueError
                If price_change_pct <= -1.0 or position_size_lp <= 0.
        """

        if price_change_pct <= -1.0:
            raise ValueError(
                "SimulatePriceMove: price_change_pct must be > -1.0 "
                "(price cannot go below zero); got {}".format(price_change_pct)
            )
        if position_size_lp <= 0:
            raise ValueError(
                "SimulatePriceMove: position_size_lp must be > 0; "
                "got {}".format(position_size_lp)
            )

        tokens = lp.factory.token_from_exchange[lp.name]
        x_tkn = tokens[lp.token0]
        y_tkn = tokens[lp.token1]

        # One helper does double duty: it gives us the linear-share token
        # amounts (x_tkn_init / y_tkn_init) AND the IL formula. These
        # amounts are the pure reserve share entitled to position_size_lp
        # of liquidity at the current state — no settlement swap, no price
        # impact. This is the "paper value" interpretation of a position,
        # appropriate for hypothetical-price analysis. AnalyzePosition uses
        # the same mechanism for the same reason; the two primitives agree
        # on how a position is valued.
        il_helper = UniswapImpLoss(lp, position_size_lp, lwr_tick, upr_tick)
        current_x_amt = il_helper.x_tkn_init
        current_y_amt = il_helper.y_tkn_init

        # Current price of y in x terms (so total position value can be
        # expressed in x_tkn, the numeraire — matches AnalyzePosition).
        price_y_in_x = lp.get_price(y_tkn)

        # Current position value in numeraire terms.
        current_value = current_x_amt + current_y_amt * price_y_in_x

        # Alpha = ratio of new price of token0 (x) to current price.
        alpha = 1.0 + price_change_pct

        # Hold value at new price: if the user had simply held their
        # current (x_amt, y_amt) composition through the move, value in
        # numeraire (x) would be:
        #   x_amt + y_amt * new_price_y_in_x
        # where new_price_y_in_x = price_y_in_x / alpha (x's price rises
        # by factor alpha ⇒ y's price in x terms falls by factor alpha).
        hold_value_at_new = current_x_amt + current_y_amt * (price_y_in_x / alpha)

        # IL at the simulated price, protocol-aware.
        if lp.version == UniswapExchangeData.VERSION_V2:
            il_at_new_price = il_helper.calc_iloss(alpha)
        else:
            r = il_helper.calc_price_range(lwr_tick, upr_tick)
            il_at_new_price = il_helper.calc_iloss(alpha, r)

        # LP position value at new price = hold_value * (1 + IL).
        new_value = hold_value_at_new * (1.0 + il_at_new_price)

        # Fractional change in position value from current to simulated.
        value_change_pct = (new_value - current_value) / current_value

        return PriceMoveScenario(
            new_price_ratio = alpha,
            new_value = new_value,
            il_at_new_price = il_at_new_price,
            fee_projection = None,
            value_change_pct = value_change_pct,
        )
