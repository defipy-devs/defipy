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
class PortfolioPosition:
    """Input container for a single position passed to AggregatePortfolio.

    Wraps the same arguments AnalyzePosition takes — plus an optional
    display name — so a portfolio call site reads cleanly instead of
    passing tuples-of-tuples.

    Attributes
    ----------
    lp : Any
        LP exchange (V2 or V3) for this position.
    lp_init_amt : float
        LP tokens held by this position, in human units.
    entry_x_amt : float
        Amount of token0 originally deposited at entry, human units.
    entry_y_amt : float
        Amount of token1 originally deposited at entry, human units.
    lwr_tick : Optional[int]
        Lower tick for V3 positions. None for V2.
    upr_tick : Optional[int]
        Upper tick for V3 positions. None for V2.
    name : Optional[str]
        Human-readable label for this position. Defaults to
        "{token0}/{token1}" when None.
    holding_period_days : Optional[float]
        Holding period in days, passed through to AnalyzePosition for
        real_apr calculation. Optional; None means APR is not computed.
    """
    lp: Any
    lp_init_amt: float
    entry_x_amt: float
    entry_y_amt: float
    lwr_tick: Optional[int] = None
    upr_tick: Optional[int] = None
    name: Optional[str] = None
    holding_period_days: Optional[float] = None
