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
from typing import Any, Optional


@dataclass
class FeeTierCandidate:
    """ Input container for CompareFeeTiers.

        Describes one V3 pool (at one fee tier) the caller wants compared
        against peers for the same token pair. Callers are expected to
        already hold references to deployed pools — this primitive does
        not construct pools, it only compares the ones provided.

        Attributes
        ----------
        lp : UniswapV3Exchange
            V3 LP exchange at current state. Must be V3; CompareFeeTiers
            raises ValueError otherwise.
        position_size_lp : float
            LP tokens the caller would hold (or does hold) in this pool,
            in human units. Retained for future extensions where the
            primitive reports per-position metrics alongside pool-level
            ones; v1 ranks at the pool level and treats position_size_lp
            as an echo field so callers don't lose the value across calls.
        lwr_tick : int
            Lower tick of the candidate position in this pool.
        upr_tick : int
            Upper tick of the candidate position in this pool. Must be
            strictly greater than lwr_tick.
        name : Optional[str]
            Display name for this candidate. Defaults inside
            CompareFeeTiers to "token0/token1@<bps>bps" when None.
    """
    lp: Any
    position_size_lp: float
    lwr_tick: int
    upr_tick: int
    name: Optional[str] = None
