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


@dataclass
class TickRangeStatus:
    """Status of a Uniswap V3 position's tick range relative to current price.

    Produced by CheckTickRangeStatus. Answers "how far is my position from
    going out of range?" for a V3 LP. Sign conventions are chosen so that
    in-range positions have positive pct_to_lower and positive pct_to_upper,
    while out-of-range cases produce a negative value on the side that the
    price has already crossed.

    Attributes
    ----------
    current_tick : int
        The pool's current tick (from lp.slot0.tick).
    lower_tick : int
        The position's lower tick bound (echo of input).
    upper_tick : int
        The position's upper tick bound (echo of input).
    pct_to_lower : float
        Fractional price move from current to the lower bound, in the
        "price of token0 in token1" convention. Positive when current
        price is above the lower bound (normal in-range case); negative
        when current has already fallen through the lower bound.
    pct_to_upper : float
        Fractional price move from current to the upper bound. Positive
        when current price is below the upper bound (normal in-range
        case); negative when current has already risen through it.
    in_range : bool
        True when lower_tick <= current_tick <= upper_tick.
    range_width_pct : float
        Total range width (upper_price - lower_price) as a fraction of
        current price. Always non-negative.
    """
    current_tick: int
    lower_tick: int
    upper_tick: int
    pct_to_lower: float
    pct_to_upper: float
    in_range: bool
    range_width_pct: float
