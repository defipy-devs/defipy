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
from typing import List, Optional


@dataclass
class StableswapPriceMoveScenario:
    """Projected LP position state at a hypothetical price, for a 2-asset
    stableswap pool.

    Produced by SimulateStableswapPriceMove. All values measured against
    the current LP state. Values are denominated at peg (sum across
    tokens valued 1:1), matching AnalyzeStableswapPosition and
    StableswapImpLoss.

    The `A` field distinguishes this from the V2/V3 and Balancer
    scenarios: stableswap IL depends heavily on the amplification
    coefficient. At high A, small alpha shocks can produce surprisingly
    large IL (the "strong negative convexity" property surfaced by
    AssessDepegRisk).

    Unreachable-alpha regime
    ------------------------
    At high A, small |1 - alpha| shocks may require pool compositions
    past the reachability bound (|ε| >= 0.95). When the simulated alpha
    is unreachable:
      - il_at_new_price = None
      - new_value = None
      - value_change_pct = None
    But new_price_ratio, A, token_names stay populated so the caller
    can see *what* was unreachable.

    Same convention as AnalyzeStableswapPosition's unreachable-alpha
    regime and AssessDepegRisk.

    Attributes
    ----------
    token_names : List[str]
        Pool tokens in insertion order (2 entries in v1).
    A : int
        Amplification coefficient at the time of simulation.
    new_price_ratio : float
        Alpha. 1.0 means at peg; <1 or >1 means depegged. Stableswap IL
        is symmetric around peg (0.95 and 1.05 produce the same
        magnitude).
    new_value : Optional[float]
        Position value at the simulated price, in peg-numeraire units.
        None when the simulated alpha is unreachable.
    il_at_new_price : Optional[float]
        Impermanent loss at the simulated price, as a fraction. None
        when unreachable. 0.0 exactly at alpha=1 (at-peg short-circuit).
    fee_projection : Optional[float]
        Always None in v1 — matches the other SimulatePriceMove
        siblings and AnalyzeStableswapPosition's no-fee-attribution
        scope.
    value_change_pct : Optional[float]
        Fractional change in position value from current to simulated.
        None when unreachable.
    """
    token_names: List[str]
    A: int
    new_price_ratio: float
    new_value: Optional[float]
    il_at_new_price: Optional[float]
    fee_projection: Optional[float]
    value_change_pct: Optional[float]
