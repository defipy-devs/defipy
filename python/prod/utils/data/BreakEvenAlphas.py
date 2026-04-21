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

from dataclasses import dataclass
from typing import Optional


@dataclass
class BreakEvenAlphas:
    """Break-even price ratios where fee income exactly offsets impermanent loss.

    Produced by FindBreakEvenPrice. The break-even condition — where
    accumulated fee income exactly compensates for IL drag — is satisfied
    at TWO alpha values in general: one below entry (alpha < 1, price
    drop direction) and one above (alpha > 1, price rise direction).
    Both are returned because the asymmetry is information — a position
    currently near alpha = 1 has different downside and upside cushion,
    and hiding one value behind a "closer to current" rule obscures
    decision-relevant information.

    Attributes
    ----------
    break_even_alpha_down : Optional[float]
        Alpha (< 1) below which IL overwhelms accumulated fees. Always
        exists for fee_income > 0. None when fee_income is zero or
        negative (degenerate — entry itself is the only break-even).
    break_even_alpha_up : Optional[float]
        Alpha (> 1) above which IL overwhelms accumulated fees. Exists
        only when fee_to_entry_ratio < 1 in V2 (or < scale factor in
        V3). None when the position is upside-hedged (fees have grown
        large enough that no finite upward price move can wipe them).
    break_even_price_down : Optional[float]
        Absolute price at break_even_alpha_down, in token1/token0 units
        (consistent with lp.get_price). None when alpha_down is None.
    break_even_price_up : Optional[float]
        Absolute price at break_even_alpha_up. None when alpha_up is None.
    fee_to_entry_ratio : float
        f = fee_income / x_tkn_init. The dimensionless accumulation
        parameter that drives both alphas. For V3, internally divided
        by the tick-range scale factor before the alpha calculation,
        but reported here as the raw ratio.
    upside_hedged : bool
        True when the position has accumulated enough fees that no
        finite upward price move can make IL exceed them. Equivalent
        to break_even_alpha_up is None.

    Notes
    -----
    Derivation. Using numeraire = token0, entry value V₀ = x₀(1 + 1/1)
    = 2x₀ at alpha = 1. At a later alpha, hold_value(alpha) = x₀(1 +
    1/alpha). The V2 break-even equation fee_income = hold_value · |IL|
    simplifies algebraically to:

        f · alpha = (1 − sqrt(alpha))²        where f = fee_income / x₀

    Substituting s = sqrt(alpha) gives s·sqrt(f) = ±(1 − s), which
    solves cleanly:

        alpha_down = 1 / (1 + sqrt(f))²        always exists for f > 0
        alpha_up   = 1 / (1 − sqrt(f))²        exists only for f < 1

    For V3, the IL formula gains a scale factor k = sqrt(r)/(sqrt(r)−1)
    where r = calc_price_range(lwr_tick, upr_tick). The equation
    becomes f·alpha = k·(1 − sqrt(alpha))², so f is replaced by f/k
    throughout. The V3 upside-hedge threshold shifts accordingly.
    """

    break_even_alpha_down: Optional[float]
    break_even_alpha_up: Optional[float]
    break_even_price_down: Optional[float]
    break_even_price_up: Optional[float]
    fee_to_entry_ratio: float
    upside_hedged: bool
