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

from .CheckPoolHealth import CheckPoolHealth
from ...utils.data import RugSignalReport


# ─── Default thresholds ──────────────────────────────────────────────────────
# All keyword-overridable at .apply() time. Defaults are deliberately
# conservative — they should almost never fire on a healthy, established
# pool, and should almost always fire on a drained or abandoned one. The
# in-between is where real tuning happens, and tuning is the caller's job.

_DEFAULT_LP_CONCENTRATION = 0.90
_DEFAULT_TVL_FLOOR = 10.0

# ─── Risk-bucket boundaries ──────────────────────────────────────────────────
# Count-based bucketing. Simple, defensible, easy to reason about. A
# future version could weight signals (e.g. drained-pool weighs heavier
# than low TVL) but weights are another tuning dimension and cheap
# judgment calls compound — count-first is the honest MVP.

_RISK_LEVELS = ["low", "medium", "high", "critical"]


class DetectRugSignals:

    """ Threshold-based rug-pull signal detector.

        Composes over CheckPoolHealth. Applies three heuristic checks —
        TVL floor, LP concentration, and dormant-pool detection — and
        returns a structured report with per-signal booleans, a
        count-based risk level, and the underlying PoolHealth snapshot
        for context.

        Answers Q7.4 from DEFIMIND_TIER1_QUESTIONS.md. Intentionally
        a signal surfacer, not a verdict generator — the primitive
        flags patterns; the caller (or an LLM reasoning layer) decides
        what to do with them.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        Why composition over raw lp access. This primitive reads only
        PoolHealth fields — no direct lp.* calls. That keeps it honest
        about what it's doing (applying thresholds to a computed
        snapshot) and means future CheckPoolHealth additions become
        available automatically. If a signal can't be expressed from
        PoolHealth, it belongs on a different primitive.

        Why no reserve-skew signal. A raw-reserve skew check was
        considered and cut during design. Under the constant-product
        invariant, each side's contribution to TVL (in a shared
        numeraire) is equal by construction at any valid pool state —
        reserve0 == reserve1 / spot_price, always. A contribution-skew
        signal can therefore never fire on a mathematically valid V2
        pool. A raw-ratio signal (e.g. reserve0 / reserve1 > 99) would
        fire, but it would fire on any exotic-value pair (stablecoin
        vs. low-value meme), which isn't "rug" — it's "unusual pair."
        Neither framing earned its place in v1.

        Threshold defaults are nominal. The TVL floor in particular
        (_DEFAULT_TVL_FLOOR = 10.0 token0 units) is context-free — it
        will fire on any legitimate pool denominated in a low-value
        token0 and miss obvious drains denominated in a high-value one.
        Callers should override with a pair-appropriate floor. We keep
        the signal on by default anyway because silent non-detection
        is a worse failure mode than noisy detection for a safety
        primitive.

        Threshold comparators. Concentration uses strict > so that
        passing 1.0 means "never fire" — a natural escape hatch for
        callers who want to disable the signal. TVL uses <= so that
        passing a floor equal to current TVL does fire (treating the
        floor as "minimum acceptable" rather than "below which is
        bad"). Two signals, two comparators — trades perfect symmetry
        for intuitive per-signal semantics.

        V2 vs V3 coverage. The inactive_with_liquidity signal depends
        on PoolHealth.num_swaps, which is V2-only (V3 accumulates
        feeGrowth globally rather than per-swap history). On V3 this
        signal is always False and a note explaining why is appended
        to details — it should not be read as "V3 pool is active" but
        as "this check was skipped."
    """

    def __init__(self):
        pass

    def apply(self, lp,
              lp_concentration_threshold = _DEFAULT_LP_CONCENTRATION,
              tvl_floor = _DEFAULT_TVL_FLOOR):

        """ apply

            Compute the rug-signal report for a pool.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current state. V2 or V3.
            lp_concentration_threshold : float, optional
                Fraction of total_supply that the top LP must strictly
                exceed to trigger single_sided_concentration. Default
                0.90. Passing 1.0 disables the signal (nothing can
                strictly exceed 1.0).
            tvl_floor : float, optional
                Minimum acceptable TVL in token0 numeraire. Values at
                or below fire tvl_suspiciously_low. Default 10.0 — this
                is nominal; override with a pair-appropriate value.

            Returns
            -------
            RugSignalReport

            Raises
            ------
            ValueError
                If any threshold is outside its valid range:
                lp_concentration_threshold must be in (0, 1];
                tvl_floor must be >= 0.
        """

        if not (0 < lp_concentration_threshold <= 1):
            raise ValueError(
                "DetectRugSignals: lp_concentration_threshold must be "
                "in (0, 1]; got {}".format(lp_concentration_threshold)
            )
        if tvl_floor < 0:
            raise ValueError(
                "DetectRugSignals: tvl_floor must be >= 0; "
                "got {}".format(tvl_floor)
            )

        health = CheckPoolHealth().apply(lp)
        details = []

        # ─── Signal 1: TVL floor ────────────────────────────────────────────
        tvl_suspiciously_low = health.tvl_in_token0 <= tvl_floor
        if tvl_suspiciously_low:
            details.append(
                "tvl_suspiciously_low: TVL {:.4f} <= floor {:.4f} "
                "(in {} numeraire)".format(
                    health.tvl_in_token0, tvl_floor, health.token0_name
                )
            )

        # ─── Signal 2: LP concentration ─────────────────────────────────────
        # Strict inequality (>) so a caller who passes 1.0 gets
        # "never fire" semantics — useful for disabling this signal
        # without touching the constructor surface.
        single_sided_concentration = (
            health.top_lp_share_pct is not None
            and health.top_lp_share_pct > lp_concentration_threshold
        )
        if single_sided_concentration:
            details.append(
                "single_sided_concentration: top LP holds {:.1%} of "
                "supply (threshold {:.1%})".format(
                    health.top_lp_share_pct, lp_concentration_threshold
                )
            )

        # ─── Signal 3: inactive with liquidity ──────────────────────────────
        # Requires knowable swap history. V2 tracks it; V3 does not.
        if health.num_swaps is None:
            inactive_with_liquidity = False
            details.append(
                "inactive_with_liquidity: unavailable for V3 "
                "(no per-swap history)"
            )
        else:
            inactive_with_liquidity = (
                health.num_swaps == 0 and health.tvl_in_token0 > 0
            )
            if inactive_with_liquidity:
                details.append(
                    "inactive_with_liquidity: pool has {:.4f} TVL but "
                    "zero swaps".format(health.tvl_in_token0)
                )

        signals_detected = sum([
            tvl_suspiciously_low,
            single_sided_concentration,
            inactive_with_liquidity,
        ])

        risk_level = self._bucket(signals_detected)

        return RugSignalReport(
            tvl_suspiciously_low = tvl_suspiciously_low,
            single_sided_concentration = single_sided_concentration,
            inactive_with_liquidity = inactive_with_liquidity,
            signals_detected = signals_detected,
            risk_level = risk_level,
            details = details,
            pool_health = health,
        )

    def _bucket(self, signals_detected):

        """ _bucket

            Map signal count to a risk-level bucket.

            0 → "low"
            1 → "medium"
            2 → "high"
            3 → "critical"
        """

        idx = min(signals_detected, len(_RISK_LEVELS) - 1)
        return _RISK_LEVELS[idx]
