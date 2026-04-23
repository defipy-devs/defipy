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

import math

from uniswappy.analytics.risk import UniswapImpLoss
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import TickMath

from ...utils.data import (
    RangeMetrics,
    TickRangeEvaluation,
)


_Q96 = 2 ** 96

# Reference capital used when computing IL exposure. IL is scale-free
# as a fraction, so the exact value is immaterial; 1.0 keeps the
# downstream `UniswapImpLoss._calc_univ3_dx/dy` arithmetic in pure
# float space without integer-math precision games.
_REFERENCE_CAPITAL = 1.0

# Default symmetric price shock used for il_exposure. 10% is a
# common mid-sized stress scenario — small enough that V3 positions
# at ±30% width stay in-range (IL is defined), large enough that
# the numbers are meaningful above float noise.
_DEFAULT_PRICE_SHOCK = 0.10

# Floor for the fee/IL rank denominator. Prevents blow-up for
# near-zero IL (full-range or shocks that barely move alpha).
# 1e-9 is below realistic IL even at ±0.01% shock on tight ranges.
_IL_RANK_FLOOR = 1e-9


class EvaluateTickRanges:

    """ Quantify the capital-efficiency vs IL-exposure vs fee-capture
        trade-off across N candidate ranges on a V3 pool.

        Answers Q3.1 ("is my tick range too wide or too narrow?") and
        Q3.2 ("should I split into multiple positions?") from
        DEFIMIND_TIER1_QUESTIONS.md.

        Per-range metrics:
          - capital_efficiency: closed-form 1 / (1 - sqrt(Pa/Pb)),
            unitless, full-range = 1.0, narrow ranges grow to large
            multiples. Independent of current price within the range.
          - il_exposure: mean absolute IL at ±price_shock, computed
            via UniswapImpLoss's range-aware V3 formula. Fractional.
          - fee_capture_pct: L_candidate / (L_active + L_candidate) at
            unit reference capital. Active-tick liquidity approximated
            as the pool's total liquidity (matches this codebase's
            full-range aggregation model).

        Follows the DeFiPy primitive contract: stateless construction
        (modulo the price_shock parameter), computation at .apply(),
        structured dataclass return. Non-mutating.

        V3 only. V2 has no tick mechanics; tick-range questions are
        meaningless. V2 pools raise ValueError.

        Notes
        -----
        Out-of-range rejection. Candidates whose [lwr_tick, upr_tick]
        does not bracket the pool's current tick are rejected with a
        clear error. A position starting out-of-range holds only one
        token and earns no fees until price enters the band —
        evaluating it against in-range candidates on the same metrics
        would mix two fundamentally different position shapes. Callers
        who want to reason about out-of-range positioning compose with
        CheckTickRangeStatus first.

        "optimal" is fee-per-IL. The spec has one `optimal_range` field;
        multiple weightings are defensible ("optimal" depends on the
        caller's risk appetite), so the primitive picks one — highest
        fee_capture_pct per unit il_exposure — and surfaces the
        `fee_per_il_rank` ordering for full transparency. Callers with
        different priorities (pure fee capture, pure IL minimization)
        read `ranges` directly. Matches CompareFeeTiers' stance.

        Active-tick liquidity approximation. Real Uniswap V3 distributes
        fees to liquidity currently contributing to the active tick,
        which is an aggregate across positions crossing that tick. In
        this codebase's V3 model (where the fixture uses a single
        full-range position), total pool liquidity and active-tick
        liquidity coincide. For pools with concentrated non-candidate
        positions already in place, the fee_capture_pct value
        conservatively overstates because the denominator is larger.
        Noted here rather than silently applied; callers with
        non-full-range baselines should interpret fee_capture_pct as
        an upper bound.

        Split comparison. split_comparison is optional. When supplied
        as (wide_idx, [narrow_idx_1, narrow_idx_2, ...]), the
        primitive computes the sum of fee_capture_pct for the narrow
        candidates minus the wide candidate's. Positive means
        splitting captures more fee share at unit reference capital.
        This is the simplest honest form of the Q3.2 comparison —
        more elaborate volume-weighted forms require assumptions
        beyond the pool state.
    """

    def __init__(self, price_shock = _DEFAULT_PRICE_SHOCK):

        """ __init__

            Parameters
            ----------
            price_shock : float, optional
                Symmetric price shock used for il_exposure. Default
                0.10 (±10%). Must be in (0, 1). 0 would produce
                zero IL for all ranges; >=1 would drive alpha to
                non-positive which the IL formula can't handle.

            Raises
            ------
            ValueError
                If price_shock is outside (0, 1).
        """

        if not (0 < price_shock < 1):
            raise ValueError(
                "EvaluateTickRanges: price_shock must be in (0, 1); "
                "got {}".format(price_shock)
            )

        self.price_shock = price_shock

    def apply(self, lp, candidates, split_comparison = None):

        """ apply

            Compute the tick-range evaluation across N candidates.

            Parameters
            ----------
            lp : UniswapV3Exchange
                V3 LP exchange at current pool state. V2 raises
                ValueError.
            candidates : list[TickRangeCandidate]
                One per range to evaluate. Must be non-empty. Each
                must satisfy lwr_tick < upr_tick and bracket the
                pool's current tick.
            split_comparison : Optional[tuple[int, list[int]]]
                Optional (wide_idx, [narrow_idxs]) for Q3.2. Indices
                refer to positions in the candidates list. When
                supplied, split_vs_single is populated on the result.
                When None, split_vs_single is None.

            Returns
            -------
            TickRangeEvaluation

            Raises
            ------
            ValueError
                If lp is not V3, candidates is empty, any candidate
                has lwr_tick >= upr_tick, any candidate is out-of-range
                at current price, or split_comparison indices are out
                of bounds.
        """

        if lp.version != UniswapExchangeData.VERSION_V3:
            raise ValueError(
                "EvaluateTickRanges: V3 only; got version {!r}. V2 "
                "pools have no tick mechanics; tick-range questions "
                "don't apply.".format(lp.version)
            )

        if not candidates:
            raise ValueError(
                "EvaluateTickRanges: candidates must be a non-empty list"
            )

        current_tick = lp.slot0.tick

        # ─── Validate every candidate up-front ──────────────────────────
        for i, c in enumerate(candidates):
            if c.lwr_tick >= c.upr_tick:
                raise ValueError(
                    "EvaluateTickRanges: candidate {} has "
                    "lwr_tick ({}) >= upr_tick ({})".format(
                        i, c.lwr_tick, c.upr_tick
                    )
                )
            if not (c.lwr_tick <= current_tick <= c.upr_tick):
                raise ValueError(
                    "EvaluateTickRanges: candidate {} is out-of-range "
                    "(lwr={}, upr={}, current={}). Out-of-range "
                    "candidates hold only one token and earn no fees "
                    "until price re-enters the band; mix with "
                    "in-range candidates gives meaningless "
                    "comparisons.".format(
                        i, c.lwr_tick, c.upr_tick, current_tick
                    )
                )

        # ─── Per-range metric computation ───────────────────────────────
        range_metrics = [
            self._compute_range_metrics(lp, c, i)
            for i, c in enumerate(candidates)
        ]

        # ─── Ranking ────────────────────────────────────────────────────
        # fee_capture_pct / max(il_exposure, floor), best-first.
        # Stable on input order for deterministic tiebreaks.
        enumerated = list(enumerate(range_metrics))
        fee_per_il_rank = [
            m.name for _, m in sorted(
                enumerated,
                key = lambda it: (
                    -(it[1].fee_capture_pct
                      / max(it[1].il_exposure, _IL_RANK_FLOOR)),
                    it[0],
                ),
            )
        ]

        # optimal_range = the metrics object whose name is rank[0].
        name_to_metrics = {m.name: m for m in range_metrics}
        optimal_range = name_to_metrics[fee_per_il_rank[0]]

        # ─── Split comparison (optional) ────────────────────────────────
        split_vs_single = self._compute_split(
            range_metrics, split_comparison,
        )

        return TickRangeEvaluation(
            price_shock = self.price_shock,
            ranges = range_metrics,
            fee_per_il_rank = fee_per_il_rank,
            optimal_range = optimal_range,
            split_vs_single = split_vs_single,
        )

    # ─── Per-range computation ──────────────────────────────────────────

    def _compute_range_metrics(self, lp, candidate, idx):

        """ _compute_range_metrics

            Build a RangeMetrics for one candidate range.
        """

        name = (candidate.name if candidate.name is not None
                else "range_{}".format(idx))

        # Price boundaries from ticks (human units, token1-per-token0).
        sqrtp_pa_raw = TickMath.getSqrtRatioAtTick(candidate.lwr_tick) / _Q96
        sqrtp_pb_raw = TickMath.getSqrtRatioAtTick(candidate.upr_tick) / _Q96
        pa = sqrtp_pa_raw ** 2
        pb = sqrtp_pb_raw ** 2

        # Current price from the pool, in the same units.
        sqrtp_cur = lp.slot0.sqrtPriceX96 / _Q96
        p_cur = sqrtp_cur ** 2

        # ─── capital_efficiency: closed form ────────────────────────────
        # efficiency = 1 / (1 - sqrt(Pa/Pb))
        # Full-range limit: Pa → 0, sqrt(Pa/Pb) → 0, efficiency → 1.
        ratio = math.sqrt(pa / pb)
        capital_efficiency = 1.0 / (1.0 - ratio) if ratio < 1.0 else float('inf')

        # ─── il_exposure: mean |IL| at ±price_shock ─────────────────────
        il = UniswapImpLoss(
            lp, _REFERENCE_CAPITAL,
            candidate.lwr_tick, candidate.upr_tick,
        )
        r = il.calc_price_range(candidate.lwr_tick, candidate.upr_tick)
        alpha_up = 1.0 + self.price_shock
        alpha_dn = 1.0 - self.price_shock
        il_up = abs(il.calc_iloss(alpha_up, r))
        il_dn = abs(il.calc_iloss(alpha_dn, r))
        il_exposure = 0.5 * (il_up + il_dn)

        # ─── fee_capture_pct: L_cand / (L_active + L_cand) ──────────────
        # At unit reference capital in this range, the liquidity
        # provided scales with capital_efficiency vs full-range.
        # L_cand_unit = efficiency × L_fullrange_unit
        # We substitute pool's current L for L_active (see class docstring
        # scope note) and fix L_fullrange_unit = 1.0 as the reference.
        L_active = lp.get_liquidity()
        L_cand_unit = capital_efficiency  # unit capital × efficiency
        if L_active + L_cand_unit > 0:
            fee_capture_pct = L_cand_unit / (L_active + L_cand_unit)
        else:
            fee_capture_pct = 0.0

        # ─── range_width_pct: (Pb - Pa) / P_current ─────────────────────
        range_width_pct = (pb - pa) / p_cur if p_cur > 0 else 0.0

        return RangeMetrics(
            name = name,
            lwr_tick = candidate.lwr_tick,
            upr_tick = candidate.upr_tick,
            capital_efficiency = capital_efficiency,
            il_exposure = il_exposure,
            fee_capture_pct = fee_capture_pct,
            range_width_pct = range_width_pct,
        )

    # ─── Split comparison ───────────────────────────────────────────────

    def _compute_split(self, range_metrics, split_comparison):

        """ _compute_split

            Compute split_vs_single if the caller requested it.
            Returns None otherwise.
        """

        if split_comparison is None:
            return None

        try:
            wide_idx, narrow_idxs = split_comparison
        except (TypeError, ValueError):
            raise ValueError(
                "EvaluateTickRanges: split_comparison must be a "
                "tuple (wide_idx, [narrow_idxs]); got {!r}".format(
                    split_comparison
                )
            )

        n = len(range_metrics)
        if not (0 <= wide_idx < n):
            raise ValueError(
                "EvaluateTickRanges: split_comparison wide_idx {} "
                "out of bounds for {} candidates".format(wide_idx, n)
            )
        for j in narrow_idxs:
            if not (0 <= j < n):
                raise ValueError(
                    "EvaluateTickRanges: split_comparison narrow_idx "
                    "{} out of bounds for {} candidates".format(j, n)
                )

        narrow_sum = sum(range_metrics[j].fee_capture_pct
                         for j in narrow_idxs)
        wide_fee = range_metrics[wide_idx].fee_capture_pct
        return narrow_sum - wide_fee
