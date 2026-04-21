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
from ...utils.data import BreakEvenAlphas


class FindBreakEvenPrice:

    """ Find both alpha values at which accumulated fees exactly offset IL.

        For a given fee_income on a position of known size, there are
        TWO prices at which the LP's return (IL drag + fee income)
        equals the hold-only return: one below entry and one above.
        Both are returned — the asymmetry between downside and upside
        cushion is information that callers (quants or LLM operators)
        want to see directly.

        Answers: Q3.1 (break-even price), Q3.2 (upside cushion),
        Q3.3 (downside cushion) from DEFIMIND_TIER1_QUESTIONS.md.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        Closed-form solution (V2). The break-even equation
        fee_income = hold_value(alpha) · |IL(alpha)| simplifies to
        f · alpha = (1 − sqrt(alpha))² where f = fee_income / x_tkn_init
        (fees normalized by entry token0 amount). Solving:

            alpha_down = 1 / (1 + sqrt(f))²      always exists for f > 0
            alpha_up   = 1 / (1 − sqrt(f))²      exists only for f < 1

        For V3, IL picks up a range-scale factor k = sqrt(r)/(sqrt(r)−1),
        and f is replaced by f/k throughout. Same closed form, scaled.

        Upside-hedged case. When accumulated fees reach f ≥ 1 (V2) or
        f/k ≥ 1 (V3), the upside break-even equation has no finite
        solution — fees have grown large enough that no finite upward
        price move can make IL exceed them. In this case the dataclass
        reports break_even_alpha_up = None and upside_hedged = True.
        The downside break-even always exists for any f > 0 because IL
        diverges as alpha → 0.

        Numeraire convention. All prices are token1 per token0 (matches
        lp.get_price(token0)), and fee_income is in token0 units —
        consistent with AnalyzePosition and SimulatePriceMove.
    """

    def __init__(self):
        pass

    def apply(self, lp, lp_init_amt, fee_income, lwr_tick = None, upr_tick = None):

        """ apply

            Compute break-even alphas for a position of lp_init_amt LP
            tokens that has accumulated fee_income so far.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current pool state. V2 or V3.
            lp_init_amt : float
                LP tokens held by the position, in human units. Must
                be strictly positive.
            fee_income : float
                Accumulated fee income in token0 (numeraire) units.
                Must be non-negative. Zero is a valid input and returns
                the degenerate result (both alphas collapse to 1.0,
                i.e., break-even only at entry).
            lwr_tick : int, optional
                Lower tick of the position (V3 only).
            upr_tick : int, optional
                Upper tick of the position (V3 only).

            Returns
            -------
            BreakEvenAlphas
                Structured result with both alphas, both absolute
                prices, the fee-to-entry ratio, and the upside-hedged
                flag.

            Raises
            ------
            ValueError
                If lp_init_amt <= 0 or fee_income < 0.
        """

        if lp_init_amt <= 0:
            raise ValueError(
                "FindBreakEvenPrice: lp_init_amt must be > 0; "
                "got {}".format(lp_init_amt)
            )
        if fee_income < 0:
            raise ValueError(
                "FindBreakEvenPrice: fee_income must be >= 0; "
                "got {}".format(fee_income)
            )

        # UniswapImpLoss gives us x_tkn_init (paper-share of x at entry)
        # — the denominator for normalizing fees — and calc_price_range
        # for the V3 scale factor.
        il = UniswapImpLoss(lp, lp_init_amt, lwr_tick, upr_tick)
        x_tkn_init = il.x_tkn_init

        # f = fee_income / x_tkn_init (dimensionless accumulation ratio).
        # This is the reported fee_to_entry_ratio.
        f_raw = fee_income / x_tkn_init

        # For V3, divide by the range-scale factor k = sqrt(r)/(sqrt(r)−1).
        # The rest of the math is identical to V2.
        if lp.version == UniswapExchangeData.VERSION_V2:
            f_scaled = f_raw
        else:
            r = il.calc_price_range(lwr_tick, upr_tick)
            k = math.sqrt(r) / (math.sqrt(r) - 1.0)
            f_scaled = f_raw / k

        # Degenerate case: zero fees → both alphas = 1 (entry).
        if f_scaled == 0.0:
            current_price = lp.get_price(
                lp.factory.token_from_exchange[lp.name][lp.token0]
            )
            return BreakEvenAlphas(
                break_even_alpha_down = 1.0,
                break_even_alpha_up = 1.0,
                break_even_price_down = current_price,
                break_even_price_up = current_price,
                fee_to_entry_ratio = f_raw,
                upside_hedged = False,
            )

        sqrt_f = math.sqrt(f_scaled)

        # Downside break-even: always exists for f > 0.
        alpha_down = 1.0 / ((1.0 + sqrt_f) ** 2)

        # Upside break-even: exists only when sqrt_f < 1, i.e., f < 1.
        upside_hedged = sqrt_f >= 1.0
        if upside_hedged:
            alpha_up = None
        else:
            alpha_up = 1.0 / ((1.0 - sqrt_f) ** 2)

        # Convert alphas to absolute prices. Alpha is defined against
        # current price (matching AnalyzePosition's convention when
        # called at entry), so price_at_alpha = current_price · alpha.
        # Callers who track their own entry price can rescale.
        x_tkn = lp.factory.token_from_exchange[lp.name][lp.token0]
        current_price = lp.get_price(x_tkn)

        price_down = current_price * alpha_down
        price_up = None if alpha_up is None else current_price * alpha_up

        return BreakEvenAlphas(
            break_even_alpha_down = alpha_down,
            break_even_alpha_up = alpha_up,
            break_even_price_down = price_down,
            break_even_price_up = price_up,
            fee_to_entry_ratio = f_raw,
            upside_hedged = upside_hedged,
        )
