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

from uniswappy.erc import ERC20

from python.prod.utils.data import SlippageAnalysis
from python.prod.primitives.execution import CalculateSlippage


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestCalculateSlippageV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """Inject v2_setup fixture: 1000 ETH / 100000 DAI pool, USER owns 100%."""
        self.setup = v2_setup

    def slip(self, amount_in, token_in = None):
        """Helper: call CalculateSlippage, defaulting to ETH (token0) as token_in."""
        token_in = token_in if token_in is not None else self.setup.eth
        return CalculateSlippage().apply(self.setup.lp, token_in, amount_in)

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_slippage_analysis(self):
        result = self.slip(10.0)
        self.assertIsInstance(result, SlippageAnalysis)

    def test_numeric_fields_are_floats(self):
        result = self.slip(10.0)
        self.assertIsInstance(result.spot_price, float)
        self.assertIsInstance(result.execution_price, float)
        self.assertIsInstance(result.slippage_pct, float)
        self.assertIsInstance(result.slippage_cost, float)
        self.assertIsInstance(result.price_impact_pct, float)

    def test_v2_max_size_is_float(self):
        result = self.slip(10.0)
        self.assertIsInstance(result.max_size_at_1pct, float)
        self.assertGreater(result.max_size_at_1pct, 0.0)

    # ─── Spot price & execution price ────────────────────────────────────────

    def test_spot_price_matches_reserve_ratio(self):
        # Pool: 1000 ETH / 100000 DAI ⇒ spot = 100 DAI per ETH.
        result = self.slip(10.0)
        self.assertAlmostEqual(result.spot_price, 100.0, places = 4)

    def test_execution_price_strictly_less_than_spot(self):
        result = self.slip(10.0)
        self.assertLess(result.execution_price, result.spot_price)

    # ─── Slippage ────────────────────────────────────────────────────────────

    def test_slippage_pct_nonnegative(self):
        result = self.slip(10.0)
        self.assertGreaterEqual(result.slippage_pct, 0.0)

    def test_tiny_trade_slippage_near_fee_rate(self):
        # For V2 with 0.3% fee, infinitesimal trades have slippage → 0.003.
        # A 0.0001 ETH trade in a 1000 ETH pool should be essentially all fee.
        result = self.slip(0.0001)
        self.assertAlmostEqual(result.slippage_pct, 0.003, places = 4)

    def test_larger_trade_gives_larger_slippage(self):
        small = self.slip(1.0).slippage_pct
        large = self.slip(100.0).slippage_pct
        self.assertGreater(large, small)

    def test_slippage_cost_positive(self):
        result = self.slip(10.0)
        self.assertGreater(result.slippage_cost, 0.0)

    # ─── Price impact ────────────────────────────────────────────────────────

    def test_price_impact_pct_nonnegative(self):
        result = self.slip(10.0)
        self.assertGreaterEqual(result.price_impact_pct, 0.0)

    def test_price_impact_increases_with_trade_size(self):
        small = self.slip(1.0).price_impact_pct
        large = self.slip(100.0).price_impact_pct
        self.assertGreater(large, small)

    def test_small_trade_price_impact_below_slippage(self):
        # For small trades, slippage is dominated by the fee (~0.3%) while
        # price impact → 0. So price_impact < slippage in the small-trade regime.
        result = self.slip(0.01)
        self.assertLess(result.price_impact_pct, result.slippage_pct)

    # ─── Symmetry: token0 vs token1 as token_in ──────────────────────────────

    def test_works_with_token1_as_input(self):
        # Trading DAI for ETH should also produce valid metrics.
        result = self.slip(1000.0, token_in = self.setup.dai)
        self.assertIsInstance(result, SlippageAnalysis)
        # Spot price of DAI in ETH ≈ 0.01
        self.assertAlmostEqual(result.spot_price, 0.01, places = 6)
        self.assertLess(result.execution_price, result.spot_price)

    # ─── max_size round-trip ─────────────────────────────────────────────────

    def test_max_size_produces_target_slippage(self):
        # The max_size_at_1pct value, when used as amount_in, should produce
        # a slippage_pct very close to 1%. This validates both the inversion
        # formula AND the forward slippage calculation against each other.
        max_size = self.slip(10.0).max_size_at_1pct
        result_at_max = self.slip(max_size)
        self.assertAlmostEqual(result_at_max.slippage_pct, 0.01, places = 4)

    def test_max_size_is_reasonable_fraction_of_reserve(self):
        # For V2 with 0.3% fee at 1% slippage target:
        #   A = R * (1000*0.01 - 3) / (997 * 0.99) ≈ R * 0.00709
        # Reserve of ETH = 1000, so max_size ≈ 7.09 ETH.
        result = self.slip(10.0)
        self.assertAlmostEqual(result.max_size_at_1pct, 1000.0 * 7 / (997 * 0.99), places = 2)

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_zero_amount_in(self):
        with self.assertRaises(ValueError):
            self.slip(0.0)

    def test_raises_on_negative_amount_in(self):
        with self.assertRaises(ValueError):
            self.slip(-1.0)

    def test_raises_on_token_not_in_pool(self):
        foreign = ERC20("USDC", "0xFF")
        with self.assertRaises(ValueError):
            CalculateSlippage().apply(self.setup.lp, foreign, 10.0)


# ─── V3 smoke suite ──────────────────────────────────────────────────────────

class TestCalculateSlippageV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def slip(self, amount_in):
        return CalculateSlippage().apply(
            self.setup.lp, self.setup.eth, amount_in,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )

    def test_v3_returns_slippage_analysis(self):
        result = self.slip(10.0)
        self.assertIsInstance(result, SlippageAnalysis)

    def test_v3_max_size_is_none(self):
        # Documented limitation: V3 tick-crossing math requires a different
        # approach; max_size inversion is punted to AssessLiquidityDepth.
        result = self.slip(10.0)
        self.assertIsNone(result.max_size_at_1pct)

    def test_v3_slippage_pct_nonnegative(self):
        result = self.slip(10.0)
        self.assertGreaterEqual(result.slippage_pct, 0.0)


if __name__ == '__main__':
    unittest.main()
