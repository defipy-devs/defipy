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

from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import TickMath
from ...utils.data import TickRangeStatus


# Q96 factor used to decode sqrtPriceX96 back to a plain sqrt(price).
_Q96 = 2 ** 96


class CheckTickRangeStatus:

    """ Report where a V3 position's current price sits inside its tick range.

        Answers "is my tick range about to go out of range?" for a
        Uniswap V3 LP. Given a proposed [lower, upper] tick band and the
        pool's current state, computes:
          - the current tick (from lp.slot0)
          - how far the price would need to fall to hit the lower bound
          - how far the price would need to rise to hit the upper bound
          - whether the pool is currently in range
          - the total range width as a fraction of current price

        Answers: Q2.4 from DEFIMIND_TIER1_QUESTIONS.md.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        Price convention. In Uniswap V3 the "price" at a tick is
        1.0001**tick = token1 / token0 (i.e., price of token0 expressed
        in token1 units). For an ETH/DAI pool where ETH is token0, this
        is DAI per ETH — the intuitive "price of ETH" direction.

        Sign convention for pct_to_lower and pct_to_upper. Both are
        computed with the current price as the reference and expressed
        as fractional moves. When the position is in range, both values
        are positive — "positive pct_to_upper" means "price must rise by
        this fraction to reach the upper tick." When the position has
        drifted out of range, the crossed-over value becomes negative,
        which the caller can read as "the bound is on the other side."

        Tick alignment. This primitive accepts any valid tick in
        [MIN_TICK, MAX_TICK]; ticks are not required to be multiples of
        the pool's tick_spacing. Real LP positions do align to spacing,
        but the primitive's job is to report the status of an arbitrary
        band, not to enforce position construction rules.
    """

    def __init__(self):
        pass

    def apply(self, lp, lwr_tick, upr_tick):

        """ apply

            Compute tick-range status for a V3 position.

            Parameters
            ----------
            lp : UniswapV3Exchange
                V3 LP exchange at current pool state. Must be V3;
                raises ValueError otherwise.
            lwr_tick : int
                Lower tick of the position.
            upr_tick : int
                Upper tick of the position. Must be strictly greater
                than lwr_tick.

            Returns
            -------
            TickRangeStatus
                Structured snapshot of the position's status relative
                to current price.

            Raises
            ------
            ValueError
                If lp is not a V3 exchange, or if lwr_tick >= upr_tick.
                Tick-bound violations (|tick| > MAX_TICK) propagate
                from TickMath as its own assertion.
        """

        if lp.version != UniswapExchangeData.VERSION_V2 and \
           lp.version != UniswapExchangeData.VERSION_V3:
            raise ValueError(
                "CheckTickRangeStatus: unsupported lp version {!r}".format(
                    lp.version
                )
            )

        if lp.version == UniswapExchangeData.VERSION_V2:
            raise ValueError(
                "CheckTickRangeStatus: V2 LPs have no tick range; "
                "this primitive is V3-only."
            )

        if lwr_tick >= upr_tick:
            raise ValueError(
                "CheckTickRangeStatus: lwr_tick ({}) must be strictly "
                "less than upr_tick ({})".format(lwr_tick, upr_tick)
            )

        current_tick = lp.slot0.tick

        # Decode sqrt prices from Q64.96 to plain floats, then square to
        # get the token1/token0 price at each tick.
        sqrt_ratio_cur = lp.slot0.sqrtPriceX96 / _Q96
        sqrt_ratio_lower = TickMath.getSqrtRatioAtTick(lwr_tick) / _Q96
        sqrt_ratio_upper = TickMath.getSqrtRatioAtTick(upr_tick) / _Q96

        price_cur = sqrt_ratio_cur ** 2
        price_lower = sqrt_ratio_lower ** 2
        price_upper = sqrt_ratio_upper ** 2

        # Fractional moves from current to each bound.
        # Positive values indicate normal in-range geometry; negative
        # values indicate that bound has been crossed.
        pct_to_lower = (price_cur - price_lower) / price_cur
        pct_to_upper = (price_upper - price_cur) / price_cur

        in_range = lwr_tick <= current_tick <= upr_tick

        # Total range width as a fraction of current price. Always
        # non-negative given the lwr < upr precondition.
        range_width_pct = (price_upper - price_lower) / price_cur

        return TickRangeStatus(
            current_tick = current_tick,
            lower_tick = lwr_tick,
            upper_tick = upr_tick,
            pct_to_lower = pct_to_lower,
            pct_to_upper = pct_to_upper,
            in_range = in_range,
            range_width_pct = range_width_pct,
        )
