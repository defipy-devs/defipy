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

from uniswappy.cpt.quote import LPQuote
from uniswappy.utils.data import UniswapExchangeData
from ...utils.data import SlippageAnalysis


# V2 swap fee: Uniswap V2 hardcodes 0.3% (expressed as fee_bps = 3, so that
# the swap formula `amount_in * 997 / 1000` has 997 = 1000 - fee_bps in the
# numerator).
_V2_FEE_BPS = 3
_V2_FEE_DENOM = 1000

# Default slippage target for max-size computation: 1% matches the
# SlippageAnalysis.max_size_at_1pct field name.
_DEFAULT_SLIPPAGE_TARGET = 0.01


class CalculateSlippage:

    """ Compute slippage and price-impact decomposition for a trade.

        Answers "how much am I actually losing on the swap itself?" for
        a proposed trade. Decomposes the cost into the gap between spot
        and executed price (slippage), the amount of opposing token
        missed (slippage cost), and how far the trade moves the pool's
        own spot price (price impact). Also inverts the math to find the
        largest trade size that stays within a 1% slippage budget.

        Answers: Q8.1 (actual slippage), Q8.2 (max trade size before
        slippage exceeds X%), Q9.2 (price impact framing).

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        Slippage vs price impact: distinct metrics. For small trades,
        slippage approaches the pool fee rate (~0.3% on V2) while price
        impact approaches zero — the pool hasn't moved, but the trader
        paid the fee. For large trades, price impact grows roughly
        quadratically in trade size while slippage grows sub-linearly,
        so price impact typically exceeds slippage. There is no useful
        inequality that holds in all regimes; both should be surfaced.

        max_size_at_1pct is V2-only. For V2 with 0.3% fee, the slippage
        formula inverts to a closed form:
            A = R * (1000*s - 3) / (997 * (1 - s))
        where R is reserve_in and s is the target slippage. This is
        defined only for s > 0.003 (you cannot achieve slippage below
        the fee rate); at s = 0.003 the formula returns 0, below it the
        formula would return a negative number and we clamp to 0.
        For V3, tick-crossing behavior makes the inversion non-trivial;
        max_size_at_1pct is returned as None. A dedicated primitive
        (AssessLiquidityDepth) will handle V3 depth analysis.

        V3 trades that cross tick boundaries will have a price_impact_pct
        approximation error — the primitive reads virtual reserves at the
        active tick and computes new_spot as if the trade stayed within
        that tick. For large trades in narrow-range V3 pools, this
        underestimates the true price impact. Small trades relative to
        the active tick's depth are unaffected.
    """

    def __init__(self):
        pass

    def apply(self, lp, token_in, amount_in, lwr_tick = None, upr_tick = None):

        """ apply

            Compute slippage metrics for a proposed trade on lp.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current pool state.
            token_in : ERC20
                The token being sold. Must be one of lp.token0 or
                lp.token1.
            amount_in : float
                Amount of token_in to trade, in human units. Must be
                strictly greater than zero.
            lwr_tick : int, optional
                Lower tick of the position (V3 only, passed through to
                LP methods that need it).
            upr_tick : int, optional
                Upper tick of the position (V3 only).

            Returns
            -------
            SlippageAnalysis
                Structured result with spot_price, execution_price,
                slippage_pct, slippage_cost, price_impact_pct, and
                max_size_at_1pct (float for V2, None for V3).

            Raises
            ------
            ValueError
                If amount_in <= 0 or token_in is not a token in lp's pair.
        """

        if amount_in <= 0:
            raise ValueError(
                "CalculateSlippage: amount_in must be > 0; "
                "got {}".format(amount_in)
            )

        if token_in.token_name not in (lp.token0, lp.token1):
            raise ValueError(
                "CalculateSlippage: token_in {!r} is not in lp's pair "
                "({!r}, {!r})".format(
                    token_in.token_name, lp.token0, lp.token1
                )
            )

        tokens = lp.factory.token_from_exchange[lp.name]
        token_out = tokens[lp.token1] if token_in.token_name == lp.token0 \
                    else tokens[lp.token0]

        # Spot price: pre-trade price of token_in in token_out units.
        # lp.get_price returns reserve_out / reserve_in (no fee). Works for
        # both V2 and V3 directly.
        spot_price = lp.get_price(token_in)

        # Execute the trade through LPQuote — dispatches to V2's
        # get_amount_out0/_out1 (fee baked in at 0.3%) or V3's
        # UniV3Helper.quote (fee per the pool's fee tier). Keeps the
        # primitive protocol-agnostic.
        lpq_trade = LPQuote(quote_opposing = True, include_fee = True)
        amount_out = lpq_trade.get_amount(lp, token_in, amount_in, lwr_tick, upr_tick)

        # Execution price: effective rate received on this trade.
        execution_price = amount_out / amount_in

        # Slippage vs spot, as a fraction.
        slippage_pct = (spot_price - execution_price) / spot_price

        # Slippage cost in token_out units: what the trader missed
        # relative to the theoretical spot-priced execution.
        slippage_cost = amount_in * spot_price - amount_out

        # Price impact: how far the pool's own spot price moves.
        # Read reserves via LPQuote so V2 and V3 (virtual reserves) both
        # work. Price-impact formula assumes V3 trades don't cross ticks;
        # this holds for trades small relative to the active tick's depth.
        lpq_reserves = LPQuote()
        reserve_in = lpq_reserves.get_reserve(lp, token_in, lwr_tick, upr_tick)
        reserve_out = lpq_reserves.get_reserve(lp, token_out, lwr_tick, upr_tick)
        new_reserve_in = reserve_in + amount_in
        new_reserve_out = reserve_out - amount_out
        new_spot_price = new_reserve_out / new_reserve_in
        price_impact_pct = (spot_price - new_spot_price) / spot_price

        # Max size at 1% slippage.
        max_size_at_1pct = self._calc_max_size(lp, reserve_in)

        return SlippageAnalysis(
            spot_price = spot_price,
            execution_price = execution_price,
            slippage_pct = slippage_pct,
            slippage_cost = slippage_cost,
            price_impact_pct = price_impact_pct,
            max_size_at_1pct = max_size_at_1pct,
        )

    def _calc_max_size(self, lp, reserve_in):

        """ _calc_max_size

            Largest amount_in that keeps V2 slippage at or below 1%.

            Parameters
            ----------
            lp : Exchange
                LP exchange (used for .version dispatch only).
            reserve_in : float
                Reserve of token_in, in human units.

            Returns
            -------
            Optional[float]
                Maximum amount_in in human units. None for V3 (tick
                crossing math makes the inversion non-trivial).

            Notes
            -----
            Derivation (V2, 0.3% fee, fee_bps = 3, denom = 1000):
                slippage_pct = (fee_bps * R + 997 * A) / (1000 * R + 997 * A)
                solving for A given target slippage s:
                    A = R * (1000 * s - fee_bps) / (997 * (1 - s))
                defined only for s > fee_bps/1000.
        """

        if lp.version != UniswapExchangeData.VERSION_V2:
            return None

        s = _DEFAULT_SLIPPAGE_TARGET
        fee_bps = _V2_FEE_BPS
        denom = _V2_FEE_DENOM
        effective = denom - fee_bps   # 997

        numerator = denom * s - fee_bps
        if numerator <= 0:
            # Target slippage is at or below the fee rate — unreachable.
            return 0.0

        return reserve_in * numerator / (effective * (1.0 - s))
