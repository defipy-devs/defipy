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
class PriceMoveScenario:
    """Projected LP position state at a hypothetical price.

    Produced by SimulatePriceMove. All values measured against the current
    LP state (not a historical entry) — a price_change_pct of -0.30 means
    "if price drops 30% from where it is right now."

    Attributes
    ----------
    new_price_ratio : float
        Alpha = new_price / current_price. 1.0 means no change.
    new_value : float
        Position value at the new price, expressed in token0 numeraire.
    il_at_new_price : float
        Impermanent loss at the simulated price, as a fraction. Negative
        for any alpha != 1 (IL is always a loss relative to holding).
    fee_projection : Optional[float]
        Projected fee income over the simulated move. Always None for
        this primitive; fee-involved analysis belongs in chaining
        primitives (FindBreakEvenTime, EvaluateRebalance).
    value_change_pct : float
        Fractional change in position value from current to simulated.
        Positive means the position is worth more at the new price.
    """
    new_price_ratio: float
    new_value: float
    il_at_new_price: float
    fee_projection: Optional[float]
    value_change_pct: float
