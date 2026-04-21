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
from typing import List

from .PoolHealth import PoolHealth


@dataclass
class RugSignalReport:
    """Rug-pull signal assessment for a pool.

    Produced by DetectRugSignals. Composes over a PoolHealth snapshot
    and applies threshold-based checks to surface structural patterns
    associated with rug-pull risk (single-LP concentration,
    dormant-pool-with-liquidity, implausibly low TVL).

    Signals are booleans, not probabilities. The risk_level field is a
    count-based bucket (0 → "low", 1 → "medium", 2 → "high",
    3 → "critical") — intentionally crude, honest about what counting
    three heuristics can and can't tell you.

    Attributes
    ----------
    tvl_suspiciously_low : bool
        TVL in token0 numeraire is below the floor passed to the
        primitive. Weakest signal without pair-specific context;
        default floor is nominal and callers are expected to override.
    single_sided_concentration : bool
        A single liquidity provider owns a dominant share of total_supply,
        meaning one actor can unilaterally drain the pool.
    inactive_with_liquidity : bool
        Pool holds liquidity but has no recorded swap activity — classic
        "deploy, seed, wait, drain" pattern. V2-only signal; always
        False for V3 (no per-swap history) and the reason is recorded
        in details.
    signals_detected : int
        Count of the three boolean signals that are True.
    risk_level : str
        One of "low", "medium", "high", "critical", derived from
        signals_detected.
    details : List[str]
        Human-readable lines explaining which signals fired, with the
        numeric values that triggered them, plus any signals that
        couldn't be evaluated (e.g., inactive_with_liquidity on V3).
    pool_health : PoolHealth
        The underlying snapshot the signals were derived from. Kept on
        the report so callers who got a rug warning don't need to
        re-fetch to see the numbers behind it.
    """
    tvl_suspiciously_low: bool
    single_sided_concentration: bool
    inactive_with_liquidity: bool
    signals_detected: int
    risk_level: str
    details: List[str]
    pool_health: PoolHealth
