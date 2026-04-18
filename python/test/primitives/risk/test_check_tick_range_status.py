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

import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])

import pytest

from python.prod.utils.data import TickRangeStatus
from python.prod.primitives.risk import CheckTickRangeStatus


# ─── V3 test suite ───────────────────────────────────────────────────────────

class TestCheckTickRangeStatusV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        """v3_setup gives a full-range V3 LP. We ignore its full-range
        ticks and pass synthetic narrow ticks around lp.slot0.tick at
        apply() time, since CheckTickRangeStatus takes ticks as arguments
        rather than reading them from the LP."""
        self.setup = v3_setup
        self.current_tick = v3_setup.lp.slot0.tick

    def check(self, lwr_tick, upr_tick):
        """Helper: call CheckTickRangeStatus with explicit ticks."""
        return CheckTickRangeStatus().apply(self.setup.lp, lwr_tick, upr_tick)

    # ─── Shape & echoes ─────────────────────────────────────────────────────

    def test_returns_tick_range_status(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertIsInstance(result, TickRangeStatus)

    def test_field_types(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertIsInstance(result.current_tick, int)
        self.assertIsInstance(result.lower_tick, int)
        self.assertIsInstance(result.upper_tick, int)
        self.assertIsInstance(result.pct_to_lower, float)
        self.assertIsInstance(result.pct_to_upper, float)
        self.assertIsInstance(result.in_range, bool)
        self.assertIsInstance(result.range_width_pct, float)

    def test_current_tick_matches_lp_slot0(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertEqual(result.current_tick, self.current_tick)

    def test_input_ticks_echoed(self):
        lwr, upr = self.current_tick - 600, self.current_tick + 600
        result = self.check(lwr, upr)
        self.assertEqual(result.lower_tick, lwr)
        self.assertEqual(result.upper_tick, upr)

    # ─── In-range scenario: narrow band straddling current tick ─────────────

    def test_in_range_true_when_current_between_bounds(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertTrue(result.in_range)

    def test_in_range_pct_to_lower_positive(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertGreater(result.pct_to_lower, 0.0)

    def test_in_range_pct_to_upper_positive(self):
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertGreater(result.pct_to_upper, 0.0)

    def test_range_width_positive_and_sensible(self):
        # ±600 ticks ≈ ±6% → range_width ≈ 12%.
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertGreater(result.range_width_pct, 0.10)
        self.assertLess(result.range_width_pct, 0.15)

    def test_pct_to_lower_approx_6pct_at_600_ticks_below(self):
        # 1.0001^600 ≈ 1.0618, so price_lower ≈ current / 1.0618,
        # hence pct_to_lower ≈ 1 - 1/1.0618 ≈ 0.0583.
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertAlmostEqual(result.pct_to_lower, 0.0583, places = 2)

    def test_pct_to_upper_approx_6pct_at_600_ticks_above(self):
        # 1.0001^600 ≈ 1.0618, so price_upper ≈ current * 1.0618,
        # hence pct_to_upper ≈ 0.0618.
        result = self.check(self.current_tick - 600, self.current_tick + 600)
        self.assertAlmostEqual(result.pct_to_upper, 0.0618, places = 2)

    # ─── Out-of-range scenarios ─────────────────────────────────────────────

    def test_in_range_false_when_current_above_upper(self):
        # Band entirely below current → current is above upper bound.
        result = self.check(self.current_tick - 1200, self.current_tick - 600)
        self.assertFalse(result.in_range)

    def test_in_range_false_when_current_below_lower(self):
        # Band entirely above current → current is below lower bound.
        result = self.check(self.current_tick + 600, self.current_tick + 1200)
        self.assertFalse(result.in_range)

    def test_pct_to_upper_negative_when_above_band(self):
        # Current is above upper → upper is below current → pct_to_upper < 0.
        result = self.check(self.current_tick - 1200, self.current_tick - 600)
        self.assertLess(result.pct_to_upper, 0.0)

    def test_pct_to_lower_negative_when_below_band(self):
        # Current is below lower → lower is above current → pct_to_lower < 0.
        result = self.check(self.current_tick + 600, self.current_tick + 1200)
        self.assertLess(result.pct_to_lower, 0.0)

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_inverted_ticks(self):
        with self.assertRaises(ValueError):
            self.check(self.current_tick + 600, self.current_tick - 600)

    def test_raises_on_equal_ticks(self):
        with self.assertRaises(ValueError):
            self.check(self.current_tick, self.current_tick)


# ─── V2 rejection suite ──────────────────────────────────────────────────────

class TestCheckTickRangeStatusV2Rejection(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_raises_on_v2_lp(self):
        with self.assertRaises(ValueError):
            CheckTickRangeStatus().apply(self.setup.lp, -600, 600)


if __name__ == '__main__':
    unittest.main()
