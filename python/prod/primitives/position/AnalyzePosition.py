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
from ...utils.data import PositionAnalysis


class AnalyzePosition:

    """ Decompose an LP position into impermanent loss, fee income, and net PnL.

        Answers the core diagnostic questions for any LP position:
          - Why is this position losing (or making) money?
          - Is fee income compensating for IL?
          - What's the real APR including IL?
          - How much has this position earned in fees?

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        v1 requires the caller to provide entry token amounts explicitly.
        This is the information a user naturally has ("I deposited X ETH and
        Y DAI"). The primitive combines entry amounts with the current lp
        state to compute what the position is worth now, what it would be
        worth if held, and the full IL/fee decomposition.

        UniswapImpLoss serves a dual role here. Its constructor captures
        the linear share of current reserves (x_tkn_init, y_tkn_init)
        entitled to lp_init_amt; its calc_iloss method provides the
        closed-form IL formula. Both faces of that helper are used below.
        When the Twin layer ships, an alternate overload can accept two
        twin snapshots (entry_twin, current_twin) for callers who'd rather
        pass pool states than scalar amounts.
    """

    def __init__(self):
        pass

    def apply(self, lp, lp_init_amt, entry_x_amt, entry_y_amt,
              lwr_tick = None, upr_tick = None, holding_period_days = None):

        """ apply

            Compute the full position decomposition for an LP position.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current pool state.
            lp_init_amt : float
                LP tokens held by the position, in human units.
            entry_x_amt : float
                Amount of token0 originally deposited at entry, human units.
            entry_y_amt : float
                Amount of token1 originally deposited at entry, human units.
            lwr_tick : int, optional
                Lower tick of the position (V3 positions only).
            upr_tick : int, optional
                Upper tick of the position (V3 positions only).
            holding_period_days : float, optional
                Holding period in days. When provided, real_apr is
                annualized from net_pnl. Otherwise real_apr is None.

            Returns
            -------
            PositionAnalysis
                Structured decomposition containing current_value,
                hold_value, il_percentage, il_with_fees, fee_income,
                net_pnl, real_apr, and diagnosis.
        """

        tokens = lp.factory.token_from_exchange[lp.name]
        x_tkn = tokens[lp.token0]
        y_tkn = tokens[lp.token1]

        # One helper does double duty: UniswapImpLoss's constructor gives
        # us the linear-share token amounts (x_tkn_init / y_tkn_init), and
        # the same instance provides calc_iloss for the IL formula below.
        # The token amounts are the pure reserve share entitled to
        # lp_init_amt at current state — no settlement swap.
        il = UniswapImpLoss(lp, lp_init_amt, lwr_tick, upr_tick)
        current_x_amt = il.x_tkn_init
        current_y_amt = il.y_tkn_init

        # Price of y_token expressed in x_token units (e.g., ETH per DAI).
        price_y_in_x = lp.get_price(y_tkn)

        # Total position value in x_token (numeraire) terms.
        current_value = current_x_amt + current_y_amt * price_y_in_x

        # Hold value: the entry tokens revalued at current spot.
        hold_value = entry_x_amt + entry_y_amt * price_y_in_x

        net_pnl = current_value - hold_value
        il_with_fees = net_pnl / hold_value if hold_value > 0 else 0.0

        # Pure-price IL using the classic 2*sqrt(alpha)/(1+alpha) - 1 formula.
        # alpha is the ratio of current price to entry price, both expressed
        # as "price of x in y terms". UniswapImpLoss.calc_iloss() is a pure
        # function that takes alpha and returns iloss.
        initial_price_x_in_y = (
            entry_y_amt / entry_x_amt if entry_x_amt > 0 else 0.0
        )
        current_price_x_in_y = lp.get_price(x_tkn)

        if initial_price_x_in_y > 0:
            alpha = current_price_x_in_y / initial_price_x_in_y
            if lp.version == UniswapExchangeData.VERSION_V2:
                il_raw = il.calc_iloss(alpha)
            else:
                r = il.calc_price_range(lwr_tick, upr_tick)
                il_raw = il.calc_iloss(alpha, r)
        else:
            il_raw = 0.0

        # Fee income isolated: the gap between realized IL and pure-price IL,
        # converted from fractional to absolute in numeraire terms.
        fee_income = (il_with_fees - il_raw) * hold_value

        if holding_period_days is not None and holding_period_days > 0:
            real_apr = (net_pnl / hold_value) * (365.0 / holding_period_days)
        else:
            real_apr = None

        diagnosis = self._diagnose(net_pnl, il_raw, il_with_fees)

        return PositionAnalysis(
            current_value = current_value,
            hold_value = hold_value,
            il_percentage = il_raw,
            il_with_fees = il_with_fees,
            fee_income = fee_income,
            net_pnl = net_pnl,
            real_apr = real_apr,
            diagnosis = diagnosis,
        )

    def _diagnose(self, net_pnl, il_raw, il_with_fees):

        """ _diagnose

            Categorize the position state into one of three buckets.

            Parameters
            ----------
            net_pnl : float
                current_value - hold_value.
            il_raw : float
                Pure-price IL. Typically <= 0 after any price divergence.
            il_with_fees : float
                Realized IL accounting for fee income. Greater than il_raw
                when fees have been earned.

            Returns
            -------
            str
                "net_positive" : position is making money overall.
                "fee_compensated" : fees recovered >50% of the IL drag.
                "il_dominant" : IL drag dominates; fees are not keeping up.
        """

        if net_pnl > 0:
            return "net_positive"

        # Fee recovery ratio: how much of the raw IL drag has been recouped
        # by fee income. Guard against il_raw == 0 (no price divergence).
        if il_raw != 0 and (1 - il_with_fees / il_raw) > 0.5:
            return "fee_compensated"

        return "il_dominant"
