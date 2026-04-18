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

from python.prod.utils.data import PriceMoveScenario
from python.prod.primitives.position import SimulatePriceMove


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestSimulatePriceMoveV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """Inject v2_setup fixture from conftest.py into self.setup."""
        self.setup = v2_setup

    def simulate(self, price_change_pct, position_size_lp = None):
        """Helper: call SimulatePriceMove with the standard V2 fixture."""
        size = position_size_lp if position_size_lp is not None \
               else self.setup.lp_init_amt
        return SimulatePriceMove().apply(
            self.setup.lp, price_change_pct, size,
        )

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_price_move_scenario(self):
        result = self.simulate(-0.30)
        self.assertIsInstance(result, PriceMoveScenario)

    def test_fee_projection_is_none(self):
        # Documented behavior: this primitive does not model fees.
        result = self.simulate(-0.30)
        self.assertIsNone(result.fee_projection)

    def test_numeric_fields_are_floats(self):
        result = self.simulate(-0.30)
        self.assertIsInstance(result.new_price_ratio, float)
        self.assertIsInstance(result.new_value, float)
        self.assertIsInstance(result.il_at_new_price, float)
        self.assertIsInstance(result.value_change_pct, float)

    # ─── Identity: zero price change ─────────────────────────────────────────

    def test_zero_change_gives_unit_alpha(self):
        result = self.simulate(0.0)
        self.assertAlmostEqual(result.new_price_ratio, 1.0, places = 10)

    def test_zero_change_gives_zero_il(self):
        result = self.simulate(0.0)
        self.assertAlmostEqual(result.il_at_new_price, 0.0, places = 6)

    def test_zero_change_gives_zero_value_change(self):
        result = self.simulate(0.0)
        self.assertAlmostEqual(result.value_change_pct, 0.0, places = 6)

    # ─── Alpha mapping ───────────────────────────────────────────────────────

    def test_alpha_maps_from_price_change_pct(self):
        # alpha = 1 + pct, for any valid pct.
        self.assertAlmostEqual(self.simulate(-0.30).new_price_ratio, 0.70, places = 10)
        self.assertAlmostEqual(self.simulate(+0.50).new_price_ratio, 1.50, places = 10)
        self.assertAlmostEqual(self.simulate(+1.00).new_price_ratio, 2.00, places = 10)

    # ─── IL direction: always non-positive for alpha != 1 ────────────────────

    def test_price_drop_gives_nonpositive_il(self):
        result = self.simulate(-0.30)
        self.assertLessEqual(result.il_at_new_price, 0.0)

    def test_price_rise_gives_nonpositive_il(self):
        result = self.simulate(+0.50)
        self.assertLessEqual(result.il_at_new_price, 0.0)

    # ─── IL magnitude: monotone in distance from alpha=1 ─────────────────────

    def test_larger_drop_gives_larger_il_magnitude(self):
        il_30 = self.simulate(-0.30).il_at_new_price
        il_50 = self.simulate(-0.50).il_at_new_price
        self.assertGreater(abs(il_50), abs(il_30))

    def test_il_symmetric_under_alpha_inversion(self):
        # IL(alpha) == IL(1/alpha). alpha=2 from pct=+1.0, alpha=0.5 from pct=-0.5.
        il_up = self.simulate(+1.0).il_at_new_price     # alpha = 2
        il_dn = self.simulate(-0.5).il_at_new_price     # alpha = 0.5
        self.assertAlmostEqual(il_up, il_dn, places = 6)

    # ─── Value change direction (token0 numeraire) ───────────────────────────

    def test_price_drop_increases_value_in_x_numeraire(self):
        # When token0's price drops, holding half of token1 makes the
        # position worth MORE in token0 terms. Counterintuitive but correct.
        result = self.simulate(-0.30)
        self.assertGreater(result.value_change_pct, 0.0)

    def test_price_rise_decreases_value_in_x_numeraire(self):
        # When token0's price rises, the position ends up with LESS token0
        # (LPs rebalance toward the dropping asset), so value in token0
        # numeraire decreases.
        result = self.simulate(+0.50)
        self.assertLess(result.value_change_pct, 0.0)

    # ─── Position size scaling ───────────────────────────────────────────────

    def test_doubling_position_size_doubles_new_value(self):
        half = self.simulate(-0.30, position_size_lp = self.setup.lp_init_amt / 2)
        full = self.simulate(-0.30, position_size_lp = self.setup.lp_init_amt)
        self.assertAlmostEqual(full.new_value, 2.0 * half.new_value, places = 4)

    def test_il_invariant_under_position_scaling(self):
        # IL percentage is scale-free: same price move ⇒ same IL %
        # regardless of position size.
        half = self.simulate(-0.30, position_size_lp = self.setup.lp_init_amt / 2)
        full = self.simulate(-0.30, position_size_lp = self.setup.lp_init_amt)
        self.assertAlmostEqual(full.il_at_new_price, half.il_at_new_price, places = 6)

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_price_change_at_minus_one(self):
        # alpha=0 means new_price=0; not a legal simulation input.
        with self.assertRaises(ValueError):
            self.simulate(-1.0)

    def test_raises_on_price_change_below_minus_one(self):
        with self.assertRaises(ValueError):
            self.simulate(-1.5)

    def test_raises_on_zero_position_size(self):
        with self.assertRaises(ValueError):
            self.simulate(-0.30, position_size_lp = 0.0)

    def test_raises_on_negative_position_size(self):
        with self.assertRaises(ValueError):
            self.simulate(-0.30, position_size_lp = -10.0)


# ─── V3 smoke suite ──────────────────────────────────────────────────────────

class TestSimulatePriceMoveV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def simulate(self, price_change_pct):
        return SimulatePriceMove().apply(
            self.setup.lp, price_change_pct, self.setup.lp_init_amt,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )

    def test_v3_returns_price_move_scenario(self):
        result = self.simulate(-0.30)
        self.assertIsInstance(result, PriceMoveScenario)

    def test_v3_zero_change_gives_zero_il(self):
        result = self.simulate(0.0)
        self.assertAlmostEqual(result.il_at_new_price, 0.0, places = 4)

    def test_v3_price_drop_gives_nonpositive_il(self):
        result = self.simulate(-0.30)
        self.assertLessEqual(result.il_at_new_price, 1e-9)


if __name__ == '__main__':
    unittest.main()
