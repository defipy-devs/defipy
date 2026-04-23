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
from typing import Any, List, Optional


@dataclass
class PortfolioPosition:
    """Input container for a single position passed to AggregatePortfolio.

    Wraps the same arguments the per-protocol Analyze*Position
    primitives take — plus an optional display name and protocol-
    specific overrides — so a portfolio call site reads cleanly
    instead of passing tuples-of-tuples.

    Cross-protocol entry shape
    --------------------------
    V2, V3, and Balancer positions use `entry_x_amt` and
    `entry_y_amt`. For Balancer, these map to the base and opp
    tokens respectively (matching the pool's tkn_reserves
    insertion order).

    Stableswap positions use `entry_amounts` — a list of per-token
    entry values in pool's insertion order. For 2-asset pools the
    list has 2 entries; if/when StableswapImpLoss supports N-asset,
    the list grows with it.

    AggregatePortfolio dispatches on the pool's isinstance type and
    reads the appropriate fields. Stableswap positions that set
    `entry_x_amt/entry_y_amt` instead of `entry_amounts` get a
    clear error at aggregation time rather than silently running
    the V2/V3 path.

    Attributes
    ----------
    lp : Any
        LP exchange for this position. V2/V3 (UniswapExchange),
        Balancer, or Stableswap pools are supported.
    lp_init_amt : float
        LP tokens / pool shares held by this position, human units.
    entry_x_amt : Optional[float]
        V2/V3/Balancer: amount of the first token deposited at entry.
        Leave None for stableswap positions (use entry_amounts).
    entry_y_amt : Optional[float]
        V2/V3/Balancer: amount of the second token deposited at entry.
        Leave None for stableswap positions.
    entry_amounts : Optional[List[float]]
        Stableswap: per-token entry amounts in pool order. Leave None
        for V2/V3/Balancer positions (use entry_x_amt/entry_y_amt).
    lwr_tick : Optional[int]
        Lower tick for V3 positions. None for everyone else.
    upr_tick : Optional[int]
        Upper tick for V3 positions. None for everyone else.
    name : Optional[str]
        Human-readable label. Defaults to "{token0}/{token1}" or the
        protocol-appropriate equivalent when None.
    holding_period_days : Optional[float]
        Holding period in days, passed through to the per-protocol
        analyzer for real_apr calculation.
    """
    lp: Any
    lp_init_amt: float
    entry_x_amt: Optional[float] = None
    entry_y_amt: Optional[float] = None
    entry_amounts: Optional[List[float]] = None
    lwr_tick: Optional[int] = None
    upr_tick: Optional[int] = None
    name: Optional[str] = None
    holding_period_days: Optional[float] = None
