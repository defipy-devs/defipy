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
class DepegScenario:
    """Per-level result for a single depeg magnitude within a DepegRiskAssessment.

    Produced by AssessDepegRisk, one per entry in its depeg_levels input.
    Each scenario reports the LP position's IL at a given internal-price
    depeg, derived from a closed-form expansion of the stableswap
    invariant.

    Attributes
    ----------
    depeg_pct : float
        The depeg magnitude requested (e.g., 0.05 = 5% depeg).
    peg_price : float
        The effective in-pool price of the depegging asset at this
        scenario, in units of the other assets (= 1 - depeg_pct).
    lp_value_at_depeg : Optional[float]
        LP position's value at the depegged state, expressed in peg
        numeraire. None if the requested depeg is unreachable for
        the pool's amplification coefficient.
    hold_value_at_depeg : Optional[float]
        Counterfactual value had the LP held their entry tokens and
        the depegging asset's market price moved to 1 - depeg_pct.
        None if unreachable.
    il_pct : Optional[float]
        (lp_value_at_depeg - hold_value_at_depeg) / hold_value_at_depeg.
        Negative under depeg (LPs lose vs. holding). None if unreachable.
    v2_il_comparison : Optional[float]
        The equivalent constant-product IL at the same price
        deviation — 2·sqrt(peg_price)/(1+peg_price) - 1. Reported
        even in unreachable scenarios (V2 has no reachability
        constraint). None when compare_v2=False.

    Notes
    -----
    Depeg definition. "Depeg" here means the pool's internal dydx
    ratio, not an external oracle price. The primitive models the
    pool-state depeg because that's what directly determines LP
    value via the invariant.

    Reachability. For high amplification coefficients, small depegs
    require large composition shifts — at A=200, reaching 20% depeg
    requires ε ≈ 0.9 (very drained pool), and reaching 2% depeg is
    actually unreachable in the closed-form expansion (it asks for
    |ε| > 1). When that happens, the scenario fields that depend on
    the pool state are set to None and only v2_il_comparison is
    populated. This lets callers see the V2 benchmark even when the
    stableswap case is out of envelope.

    Strong negative convexity. A surprising consequence of the math:
    at high A, stableswap has LARGER absolute IL than V2 at the same
    price deviation, not smaller. The flat curve forces arbitrageurs
    to drain substantial balance to move dydx even a little. The
    marketing line "stableswap protects LPs from IL" is true per
    unit of trading volume but misleading per unit of price
    deviation — this primitive reports the per-price-deviation IL.
    """
    depeg_pct: float
    peg_price: float
    lp_value_at_depeg: Optional[float]
    hold_value_at_depeg: Optional[float]
    il_pct: Optional[float]
    v2_il_comparison: Optional[float]


@dataclass
class DepegRiskAssessment:
    """Stableswap depeg-risk assessment for an LP position.

    Produced by AssessDepegRisk. Quantifies what happens to the LP
    position as one asset in the basket depegs to a given set of
    magnitudes, via a closed-form expansion of the stableswap
    invariant. The primitive is stableswap-specific and currently
    limited to N=2 pools.

    Answers Q2.3 from DEFIMIND_TIER1_QUESTIONS.md.

    Attributes
    ----------
    depeg_token : str
        Symbol of the asset assumed to depeg in each scenario.
    protocol_type : str
        "stableswap" for v1. Reserved for future protocol expansions
        (e.g., Curve v2 dynamic-peg pools, Balancer stable pools).
    n_assets : int
        Number of assets in the pool's basket. v1 requires N=2.
    current_peg_deviation : float
        How far the pool's dydx between depeg_token and the other
        asset is from 1.0 right now, as a fraction. Informational —
        tells callers what depeg level the pool is already at before
        their scenarios even start.
    scenarios : List[DepegScenario]
        One scenario per entry in the primitive's depeg_levels input.
        In the order supplied.

    Notes
    -----
    No aggregate "risk_level" field. Depeg risk is inherently
    multi-dimensional — a 2% stablecoin wobble and a 90% collapse
    are categorically different events, though both produce nonzero
    IL here. Collapsing them into a single label would be the
    primitive overstepping what the math actually delivers. Callers
    (or an LLM layer) decide how to interpret the scenario grid.
    Matches DetectRugSignals' and AggregatePortfolio's signal-
    surfacer stance.

    V2 comparison. Closed-form 2·sqrt(peg_price)/(1+peg_price) - 1.
    Useful for understanding the relative shape at each depeg level;
    be aware that stableswap can exceed V2's absolute IL at small
    depegs in high-A pools (strong negative convexity).
    """
    depeg_token: str
    protocol_type: str
    n_assets: int
    current_peg_deviation: float
    scenarios: List[DepegScenario]
