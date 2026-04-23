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
class TickRangeCandidate:
    """ Input container for EvaluateTickRanges.

        Describes one candidate (lwr_tick, upr_tick) range the caller
        wants evaluated against peers on the same V3 pool. Callers
        construct these for the ranges they're considering and pass a
        list to EvaluateTickRanges().apply().

        Attributes
        ----------
        lwr_tick : int
            Lower tick of the candidate range. Must be strictly less
            than upr_tick. Must sit at or below the pool's current tick
            (ranges must bracket current price; out-of-range candidates
            are rejected with ValueError).
        upr_tick : int
            Upper tick. Must be strictly greater than lwr_tick. Must
            sit at or above the pool's current tick.
        name : Optional[str]
            Human-readable label. Defaults inside EvaluateTickRanges
            to "range_<idx>" when None.
    """
    lwr_tick: int
    upr_tick: int
    name: Optional[str] = None
