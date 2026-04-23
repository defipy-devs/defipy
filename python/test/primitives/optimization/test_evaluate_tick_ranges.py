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

import sys, os, math, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])

import pytest

from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import TickMath

from python.prod.utils.data import (
    TickRangeCandidate,
    TickRangeEvaluation,
    RangeMetrics,
)
from python.prod.primitives.optimization import EvaluateTickRanges


USER = "user0"
V3_TICK_SPACING = 60


def _candidate(lwr, upr, name = None):
    return TickRangeCandidate(lwr_tick = lwr, upr_tick = upr, name = name)


def _centered_range(current_tick, tick_spacing, half_width_multiples):
    """Build a candidate centered on current_tick, ±N·tick_spacing wide."""
    half = half_width_multiples * tick_spacing
    # Snap to tick_spacing grid.
    lwr_raw = current_tick - half
    upr_raw = current_tick + half
    lwr = (lwr_raw // tick_spacing) * tick_spacing
    upr = ((upr_raw + tick_spacing - 1) // tick_spacing) * tick_spacing
    # Ensure the snap didn't collapse them — expand if equal.
    if lwr >= upr:
        upr = lwr + tick_spacing
    return lwr, upr


# ═══════════════════════════════════════════════════════════════════════════
# Shape & return type
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def _basic_candidates(self):
        ct = self.setup.lp.slot0.tick
        lwr1, upr1 = _centered_range(ct, V3_TICK_SPACING, 20)
        lwr2, upr2 = _centered_range(ct, V3_TICK_SPACING, 5)
        return [
            _candidate(lwr1, upr1, name = "wide"),
            _candidate(lwr2, upr2, name = "narrow"),
        ]

    def test_returns_tick_range_evaluation(self):
        result = EvaluateTickRanges().apply(
            self.setup.lp, self._basic_candidates(),
        )
        self.assertIsInstance(result, TickRangeEvaluation)

    def test_ranges_contain_range_metrics(self):
        result = EvaluateTickRanges().apply(
            self.setup.lp, self._basic_candidates(),
        )
        self.assertEqual(len(result.ranges), 2)
        for m in result.ranges:
            self.assertIsInstance(m, RangeMetrics)

    def test_optimal_range_is_a_range_metrics(self):
        result = EvaluateTickRanges().apply(
            self.setup.lp, self._basic_candidates(),
        )
        self.assertIsInstance(result.optimal_range, RangeMetrics)

    def test_price_shock_echoed(self):
        result = EvaluateTickRanges(price_shock = 0.15).apply(
            self.setup.lp, self._basic_candidates(),
        )
        self.assertAlmostEqual(result.price_shock, 0.15, places = 10)

    def test_default_names_when_candidate_name_is_none(self):
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        result = EvaluateTickRanges().apply(
            self.setup.lp, [_candidate(lwr, upr)],
        )
        self.assertEqual(result.ranges[0].name, "range_0")


# ═══════════════════════════════════════════════════════════════════════════
# Capital efficiency — closed form correctness
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesCapitalEfficiency(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_narrow_greater_than_wide(self):
        ct = self.setup.lp.slot0.tick
        lwr_w, upr_w = _centered_range(ct, V3_TICK_SPACING, 30)
        lwr_n, upr_n = _centered_range(ct, V3_TICK_SPACING, 3)
        result = EvaluateTickRanges().apply(self.setup.lp, [
            _candidate(lwr_w, upr_w, name = "wide"),
            _candidate(lwr_n, upr_n, name = "narrow"),
        ])
        wide = next(m for m in result.ranges if m.name == "wide")
        narrow = next(m for m in result.ranges if m.name == "narrow")
        self.assertGreater(narrow.capital_efficiency,
                           wide.capital_efficiency)

    def test_matches_closed_form(self):
        # efficiency = 1 / (1 - sqrt(Pa/Pb))
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        result = EvaluateTickRanges().apply(
            self.setup.lp, [_candidate(lwr, upr, name = "c")],
        )
        Q96 = 2 ** 96
        pa = (TickMath.getSqrtRatioAtTick(lwr) / Q96) ** 2
        pb = (TickMath.getSqrtRatioAtTick(upr) / Q96) ** 2
        expected = 1.0 / (1.0 - math.sqrt(pa / pb))
        self.assertAlmostEqual(
            result.ranges[0].capital_efficiency, expected, places = 6,
        )

    def test_capital_efficiency_above_one(self):
        # Any bounded range is strictly more capital-efficient than
        # full-range (== 1.0).
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 50)
        result = EvaluateTickRanges().apply(
            self.setup.lp, [_candidate(lwr, upr)],
        )
        self.assertGreater(result.ranges[0].capital_efficiency, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# IL exposure — range-aware formula sanity
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesILExposure(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_wider_range_lower_il_exposure(self):
        # At the same price shock, a narrower range has amplified IL
        # (the scale factor in UniswapImpLoss's range-aware formula
        # multiplies the classic IL by sqrt(r)/(sqrt(r)-1), which
        # grows as the range narrows).
        ct = self.setup.lp.slot0.tick
        lwr_w, upr_w = _centered_range(ct, V3_TICK_SPACING, 30)
        lwr_n, upr_n = _centered_range(ct, V3_TICK_SPACING, 3)
        result = EvaluateTickRanges().apply(self.setup.lp, [
            _candidate(lwr_w, upr_w, name = "wide"),
            _candidate(lwr_n, upr_n, name = "narrow"),
        ])
        wide = next(m for m in result.ranges if m.name == "wide")
        narrow = next(m for m in result.ranges if m.name == "narrow")
        self.assertLess(wide.il_exposure, narrow.il_exposure)

    def test_il_exposure_non_negative(self):
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        result = EvaluateTickRanges().apply(
            self.setup.lp, [_candidate(lwr, upr)],
        )
        self.assertGreaterEqual(result.ranges[0].il_exposure, 0.0)

    def test_smaller_shock_smaller_il(self):
        # IL grows with shock magnitude.
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        cand = [_candidate(lwr, upr, name = "c")]
        small = EvaluateTickRanges(price_shock = 0.02).apply(
            self.setup.lp, cand,
        )
        large = EvaluateTickRanges(price_shock = 0.15).apply(
            self.setup.lp, cand,
        )
        self.assertLess(small.ranges[0].il_exposure,
                        large.ranges[0].il_exposure)


# ═══════════════════════════════════════════════════════════════════════════
# Fee capture — per-candidate bounds and ordering
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesFeeCapture(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_fee_capture_in_unit_interval(self):
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        result = EvaluateTickRanges().apply(
            self.setup.lp, [_candidate(lwr, upr)],
        )
        self.assertGreaterEqual(result.ranges[0].fee_capture_pct, 0.0)
        self.assertLess(result.ranges[0].fee_capture_pct, 1.0)

    def test_narrow_captures_more_than_wide(self):
        # Higher capital_efficiency → higher L_cand at unit capital →
        # higher share of (L_active + L_cand).
        ct = self.setup.lp.slot0.tick
        lwr_w, upr_w = _centered_range(ct, V3_TICK_SPACING, 30)
        lwr_n, upr_n = _centered_range(ct, V3_TICK_SPACING, 3)
        result = EvaluateTickRanges().apply(self.setup.lp, [
            _candidate(lwr_w, upr_w, name = "wide"),
            _candidate(lwr_n, upr_n, name = "narrow"),
        ])
        wide = next(m for m in result.ranges if m.name == "wide")
        narrow = next(m for m in result.ranges if m.name == "narrow")
        self.assertGreater(narrow.fee_capture_pct, wide.fee_capture_pct)


# ═══════════════════════════════════════════════════════════════════════════
# Ranking
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesRanking(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_rank_length_equals_candidate_count(self):
        ct = self.setup.lp.slot0.tick
        cands = [
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 20),
                       name = "wide"),
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 5),
                       name = "narrow"),
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 10),
                       name = "medium"),
        ]
        result = EvaluateTickRanges().apply(self.setup.lp, cands)
        self.assertEqual(len(result.fee_per_il_rank), 3)

    def test_optimal_range_matches_rank_head(self):
        ct = self.setup.lp.slot0.tick
        cands = [
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 20),
                       name = "wide"),
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 5),
                       name = "narrow"),
        ]
        result = EvaluateTickRanges().apply(self.setup.lp, cands)
        self.assertEqual(result.optimal_range.name,
                         result.fee_per_il_rank[0])

    def test_rank_is_stable_on_identical_ratios(self):
        # Two identical candidates → stable on input order.
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        cands = [
            _candidate(lwr, upr, name = "first"),
            _candidate(lwr, upr, name = "second"),
        ]
        result = EvaluateTickRanges().apply(self.setup.lp, cands)
        self.assertEqual(result.fee_per_il_rank, ["first", "second"])


# ═══════════════════════════════════════════════════════════════════════════
# Split comparison
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesSplit(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def _three_candidates(self):
        ct = self.setup.lp.slot0.tick
        return [
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 20),
                       name = "wide"),
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 5),
                       name = "narrow_lo"),
            _candidate(*_centered_range(ct, V3_TICK_SPACING, 5),
                       name = "narrow_hi"),
        ]

    def test_split_is_none_when_not_requested(self):
        result = EvaluateTickRanges().apply(
            self.setup.lp, self._three_candidates(),
        )
        self.assertIsNone(result.split_vs_single)

    def test_split_computed_when_requested(self):
        cands = self._three_candidates()
        result = EvaluateTickRanges().apply(
            self.setup.lp, cands,
            split_comparison = (0, [1, 2]),
        )
        self.assertIsNotNone(result.split_vs_single)

    def test_split_matches_arithmetic(self):
        cands = self._three_candidates()
        result = EvaluateTickRanges().apply(
            self.setup.lp, cands,
            split_comparison = (0, [1, 2]),
        )
        expected = (
            result.ranges[1].fee_capture_pct
            + result.ranges[2].fee_capture_pct
            - result.ranges[0].fee_capture_pct
        )
        self.assertAlmostEqual(result.split_vs_single, expected,
                               places = 10)


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestEvaluateTickRangesValidation(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_empty_candidates_raises(self):
        with self.assertRaises(ValueError) as ctx:
            EvaluateTickRanges().apply(self.setup.lp, [])
        self.assertIn("non-empty", str(ctx.exception))

    def test_v2_pool_raises(self):
        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("v2 factory", "0x99")
        exch = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V2LP",
            address = "0x099",
        )
        lp_v2 = factory.deploy(exch)
        lp_v2.add_liquidity(USER, 1000.0, 100_000.0, 1000.0, 100_000.0)
        with self.assertRaises(ValueError) as ctx:
            EvaluateTickRanges().apply(lp_v2, [_candidate(0, 60)])
        self.assertIn("V3 only", str(ctx.exception))

    def test_bad_tick_order_raises(self):
        with self.assertRaises(ValueError) as ctx:
            EvaluateTickRanges().apply(
                self.setup.lp, [_candidate(100, 50)],
            )
        self.assertIn("lwr_tick", str(ctx.exception))
        self.assertIn("upr_tick", str(ctx.exception))

    def test_out_of_range_candidate_raises(self):
        ct = self.setup.lp.slot0.tick
        # Range entirely above current tick.
        above = _candidate(
            ct + 5 * V3_TICK_SPACING,
            ct + 10 * V3_TICK_SPACING,
        )
        with self.assertRaises(ValueError) as ctx:
            EvaluateTickRanges().apply(self.setup.lp, [above])
        self.assertIn("out-of-range", str(ctx.exception))

    def test_price_shock_zero_raises(self):
        with self.assertRaises(ValueError):
            EvaluateTickRanges(price_shock = 0.0)

    def test_price_shock_too_large_raises(self):
        with self.assertRaises(ValueError):
            EvaluateTickRanges(price_shock = 1.0)

    def test_split_comparison_bad_idx_raises(self):
        ct = self.setup.lp.slot0.tick
        lwr, upr = _centered_range(ct, V3_TICK_SPACING, 10)
        with self.assertRaises(ValueError) as ctx:
            EvaluateTickRanges().apply(
                self.setup.lp, [_candidate(lwr, upr)],
                split_comparison = (5, [0]),
            )
        self.assertIn("out of bounds", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
