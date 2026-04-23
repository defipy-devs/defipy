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
class RangeMetrics:
    """ Per-range scalar metrics produced by EvaluateTickRanges.

        One RangeMetrics per input TickRangeCandidate, in input order.
        Every field is a pure number carrying explicit units — no
        forward-looking volume assumption, no dollar projection. The
        primitive's job is to quantify the trade-off surface; the
        ranking decision belongs to the caller (or an LLM reasoning
        layer).

        Attributes
        ----------
        name : str
            Display name, caller-supplied or "range_<idx>" default.
        lwr_tick : int
            Lower tick of the range (echo).
        upr_tick : int
            Upper tick of the range (echo).
        capital_efficiency : float
            Closed-form V3 capital efficiency vs full-range:
            1 / (1 - sqrt(Pa/Pb)). Unitless. Full-range = 1.0;
            narrow ranges grow to large multiples (a ±1% range at
            reasonable precision gives ~200x). Independent of where
            the pool currently sits within the range — a property
            of range width alone.
        il_exposure : float
            Mean absolute IL at the primitive's configured
            symmetric price shock (default ±10%). Computed via the
            range-aware IL formula from UniswapImpLoss. Fractional
            (0.01 == 1% IL drag). Wider ranges → lower IL exposure
            at the same shock.
        fee_capture_pct : float
            Fraction of swap fees flowing through the active tick
            that this range would capture if added with unit capital
            to the current pool. Computed as L_candidate /
            (L_active + L_candidate) where L_active is the pool's
            current total liquidity (in this codebase, active-tick
            liquidity equals total pool liquidity under the full-range
            aggregation model). Narrow ranges → higher fee_capture_pct
            per unit capital.
        range_width_pct : float
            (Pb - Pa) / P_current. A ±10% range reports ~0.2 here.
            Informational — gives the caller an intuition for "how
            narrow is narrow" without needing to convert ticks
            manually. Always in [0, ∞); capped practically by the
            tick math's MIN_TICK / MAX_TICK range.
    """
    name: str
    lwr_tick: int
    upr_tick: int
    capital_efficiency: float
    il_exposure: float
    fee_capture_pct: float
    range_width_pct: float


@dataclass
class TickRangeEvaluation:
    """ Result of EvaluateTickRanges.

        Quantifies the capital-efficiency / IL-exposure / fee-capture
        trade-off across N candidate ranges for the same V3 pool. Does
        not project forward fee income — no volume model; that's a
        caller decision. Does surface a fee_per_il_rank ordering plus
        the top-ranked candidate as optimal_range, honoring the spec's
        single-optimum field while keeping the full table available.

        Follows the signal-surfacer-not-verdict-generator convention
        established by DetectRugSignals / AggregatePortfolio /
        CompareFeeTiers. The "optimal" label reflects one specific
        weighting (fee-per-unit-IL); callers with different priorities
        read ranges directly.

        Attributes
        ----------
        price_shock : float
            The shock magnitude used to compute il_exposure (echoed
            from the constructor). Fraction, e.g. 0.10 for ±10%.
        ranges : List[RangeMetrics]
            One per input candidate, preserving input order.
        fee_per_il_rank : List[str]
            Candidate names ordered best-first by
            fee_capture_pct / max(il_exposure, ε). Handles zero-IL
            cases (full-range) by treating them as arbitrarily good
            via the ε floor — the ranking is meaningful for
            non-trivial IL exposures; full-range candidates will
            tend to land last because their fee capture per unit
            capital is very low.
        optimal_range : RangeMetrics
            The RangeMetrics entry corresponding to fee_per_il_rank[0].
            Present for spec conformance. Prefer reading ranges +
            rank directly if your priorities differ from fee/IL.
        split_vs_single : Optional[float]
            Only computed when split_comparison was supplied to
            .apply(). Value: (sum of split candidates' fee_capture_pct)
            minus (wide candidate's fee_capture_pct). Positive means
            splitting captures more fees per unit of IL-adjusted cost;
            negative means the wide range is preferable. None when
            no split comparison was requested.
    """
    price_shock: float
    ranges: List[RangeMetrics]
    fee_per_il_rank: List[str]
    optimal_range: RangeMetrics
    split_vs_single: Optional[float]
