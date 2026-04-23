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
class BalancerPriceMoveScenario:
    """Projected LP position state at a hypothetical price, for a 2-asset
    Balancer weighted pool.

    Produced by SimulateBalancerPriceMove. All values measured against
    the current LP state, like the V2/V3 sibling dataclass. Values are
    denominated in opp-token units (matches BalancerImpLoss and
    AnalyzeBalancerPosition).

    The `base_weight` field distinguishes this from the V2/V3
    PriceMoveScenario: Balancer IL depends on the base token's weight,
    not just the price ratio. Surfacing the weight on the result makes
    the primitive self-describing — an LLM reading this dataclass can
    interpret the IL number without consulting the pool object.

    Attributes
    ----------
    base_tkn_name : str
        Symbol of the base token (first in the pool's tkn_reserves
        insertion order). The alpha is the price ratio of this token
        measured in opp-token units.
    opp_tkn_name : str
        Symbol of the opp token (second). Numeraire for all values.
    base_weight : float
        Normalized weight of the base token at the time of simulation,
        in (0, 1). Relevant for interpreting the IL magnitude:
        50/50 pools have the classic CP IL shape; 80/20 pools show
        substantially less IL at the same alpha.
    new_price_ratio : float
        Alpha = new_price / current_price, where price is opp-per-base.
    new_value : float
        Position value at the simulated price, in opp-token units.
    il_at_new_price : float
        Impermanent loss at the simulated price, as a fraction. For
        0 < w < 1 and alpha > 0, alpha != 1, this is always < 0.
    fee_projection : Optional[float]
        Projected fee income over the simulated move. Always None in v1
        — matches the V2/V3 SimulatePriceMove convention and consistent
        with AnalyzeBalancerPosition's no-fee-attribution scope.
    value_change_pct : float
        Fractional change in position value from current to simulated.
    """
    base_tkn_name: str
    opp_tkn_name: str
    base_weight: float
    new_price_ratio: float
    new_value: float
    il_at_new_price: float
    fee_projection: Optional[float]
    value_change_pct: float
