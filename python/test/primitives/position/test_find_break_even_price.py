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

from python.prod.utils.data import BreakEvenAlphas
from python.prod.primitives.position import FindBreakEvenPrice


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestFindBreakEvenPriceV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """v2_setup gives ETH/DAI LP with 1000 ETH / 100000 DAI, USER owns 100%.
        Entry x_tkn_init = 1000 ETH; this is the denominator for f = fees/x_init."""
        self.setup = v2_setup

    def break_even(self, fee_income, lp_init_amt = None):
        size = lp_init_amt if lp_init_amt is not None else self.setup.lp_init_amt
        return FindBreakEvenPrice().apply(self.setup.lp, size, fee_income)

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_break_even_alphas(self):
        result = self.break_even(10.0)  # 10 ETH of fees
        self.assertIsInstance(result, BreakEvenAlphas)

    def test_numeric_fields_have_expected_types(self):
        result = self.break_even(10.0)
        self.assertIsInstance(result.break_even_alpha_down, float)
        self.assertIsInstance(result.break_even_alpha_up, float)
        self.assertIsInstance(result.fee_to_entry_ratio, float)
        self.assertIsInstance(result.upside_hedged, bool)

    # ─── Degenerate case: zero fees ──────────────────────────────────────────

    def test_zero_fees_gives_unit_alphas(self):
        result = self.break_even(0.0)
        self.assertEqual(result.break_even_alpha_down, 1.0)
        self.assertEqual(result.break_even_alpha_up, 1.0)

    def test_zero_fees_gives_zero_ratio(self):
        result = self.break_even(0.0)
        self.assertEqual(result.fee_to_entry_ratio, 0.0)

    def test_zero_fees_not_hedged(self):
        result = self.break_even(0.0)
        self.assertFalse(result.upside_hedged)

    # ─── Closed-form correctness: small fees ─────────────────────────────────

    def test_one_pct_fees_alpha_down_matches_formula(self):
        # f = 10/1000 = 0.01; alpha_down = 1/(1+0.1)² = 1/1.21 ≈ 0.826
        result = self.break_even(10.0)
        expected = 1.0 / ((1.0 + math.sqrt(0.01)) ** 2)
        self.assertAlmostEqual(result.break_even_alpha_down, expected, places = 8)

    def test_one_pct_fees_alpha_up_matches_formula(self):
        # f = 0.01; alpha_up = 1/(1-0.1)² = 1/0.81 ≈ 1.2346
        result = self.break_even(10.0)
        expected = 1.0 / ((1.0 - math.sqrt(0.01)) ** 2)
        self.assertAlmostEqual(result.break_even_alpha_up, expected, places = 8)

    def test_one_pct_fees_ratio_matches(self):
        result = self.break_even(10.0)
        self.assertAlmostEqual(result.fee_to_entry_ratio, 0.01, places = 8)

    # ─── Round-trip: break-even alpha should give |IL| = f_normalized ────────

    def test_alpha_down_satisfies_break_even_equation(self):
        # At alpha_down, f · alpha = (1 − sqrt(alpha))² must hold.
        result = self.break_even(10.0)
        f = result.fee_to_entry_ratio
        a = result.break_even_alpha_down
        lhs = f * a
        rhs = (1.0 - math.sqrt(a)) ** 2
        self.assertAlmostEqual(lhs, rhs, places = 10)

    def test_alpha_up_satisfies_break_even_equation(self):
        result = self.break_even(10.0)
        f = result.fee_to_entry_ratio
        a = result.break_even_alpha_up
        lhs = f * a
        rhs = (1.0 - math.sqrt(a)) ** 2
        self.assertAlmostEqual(lhs, rhs, places = 10)

    # ─── Alpha ordering and asymmetry ────────────────────────────────────────

    def test_alpha_down_below_one(self):
        result = self.break_even(10.0)
        self.assertLess(result.break_even_alpha_down, 1.0)

    def test_alpha_up_above_one(self):
        result = self.break_even(10.0)
        self.assertGreater(result.break_even_alpha_up, 1.0)

    def test_alphas_asymmetric_around_one(self):
        # Downside cushion (1 - alpha_down) is strictly smaller than
        # upside cushion (alpha_up - 1). This is the sqrt asymmetry in IL.
        result = self.break_even(10.0)
        downside_cushion = 1.0 - result.break_even_alpha_down
        upside_cushion = result.break_even_alpha_up - 1.0
        self.assertGreater(upside_cushion, downside_cushion)

    # ─── Monotonicity: more fees → wider break-even band ─────────────────────

    def test_more_fees_widens_band(self):
        small = self.break_even(5.0)
        large = self.break_even(50.0)
        self.assertLess(large.break_even_alpha_down, small.break_even_alpha_down)
        self.assertGreater(large.break_even_alpha_up, small.break_even_alpha_up)

    # ─── Upside hedged case ─────────────────────────────────────────────────

    def test_fees_equal_entry_x_hedges_upside(self):
        # f = 1.0 exactly: alpha_up formula would divide by zero.
        # We report this as upside_hedged = True with alpha_up = None.
        result = self.break_even(1000.0)  # = x_tkn_init
        self.assertTrue(result.upside_hedged)
        self.assertIsNone(result.break_even_alpha_up)
        self.assertIsNone(result.break_even_price_up)

    def test_fees_exceed_entry_x_hedges_upside(self):
        # f > 1: no real solution for alpha_up. Hedged.
        result = self.break_even(5000.0)
        self.assertTrue(result.upside_hedged)
        self.assertIsNone(result.break_even_alpha_up)

    def test_hedged_downside_still_valid(self):
        # Even when upside is hedged, downside break-even always exists.
        result = self.break_even(5000.0)
        self.assertIsNotNone(result.break_even_alpha_down)
        self.assertLess(result.break_even_alpha_down, 1.0)

    # ─── Absolute prices ─────────────────────────────────────────────────────

    def test_prices_consistent_with_alphas(self):
        # price = current_price × alpha
        result = self.break_even(10.0)
        current_price = self.setup.lp.get_price(self.setup.eth)
        self.assertAlmostEqual(
            result.break_even_price_down,
            current_price * result.break_even_alpha_down,
            places = 8,
        )
        self.assertAlmostEqual(
            result.break_even_price_up,
            current_price * result.break_even_alpha_up,
            places = 8,
        )

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_zero_lp_amt(self):
        with self.assertRaises(ValueError):
            self.break_even(10.0, lp_init_amt = 0.0)

    def test_raises_on_negative_lp_amt(self):
        with self.assertRaises(ValueError):
            self.break_even(10.0, lp_init_amt = -5.0)

    def test_raises_on_negative_fees(self):
        with self.assertRaises(ValueError):
            self.break_even(-1.0)


# ─── V3 smoke suite ──────────────────────────────────────────────────────────

class TestFindBreakEvenPriceV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def break_even(self, fee_income):
        return FindBreakEvenPrice().apply(
            self.setup.lp, self.setup.lp_init_amt, fee_income,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )

    def test_v3_returns_break_even_alphas(self):
        result = self.break_even(10.0)
        self.assertIsInstance(result, BreakEvenAlphas)

    def test_v3_alpha_down_below_one(self):
        result = self.break_even(10.0)
        self.assertLess(result.break_even_alpha_down, 1.0)

    def test_v3_alpha_up_above_one(self):
        result = self.break_even(10.0)
        self.assertGreater(result.break_even_alpha_up, 1.0)


if __name__ == '__main__':
    unittest.main()
