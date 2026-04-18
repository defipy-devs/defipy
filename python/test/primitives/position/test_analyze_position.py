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
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.process.swap import Swap

from python.prod.utils.data import PositionAnalysis
from python.prod.primitives.position import AnalyzePosition


USER = 'user0'
ETH_AMT = 1000
DAI_AMT = 100000


def setup_v2_lp(eth_amt = ETH_AMT, dai_amt = DAI_AMT):
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory("ETH pool factory", "0x2")
    exch_data = UniswapExchangeData(tkn0 = eth, tkn1 = dai, symbol = "LP", address = "0x011")
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, eth_amt, dai_amt, eth_amt, dai_amt)
    return lp, eth, dai


class TestAnalyzePosition(unittest.TestCase):

    def setUp(self):
        self.lp, self.eth, self.dai = setup_v2_lp()
        self.lp_init_amt = self.lp.convert_to_human(self.lp.liquidity_providers[USER])
        # Entry token amounts — captured at deposit time, before any swaps.
        self.entry_eth = ETH_AMT
        self.entry_dai = DAI_AMT

    def analyze(self, holding_period_days = None):
        """Helper: call AnalyzePosition with the standard entry state."""
        return AnalyzePosition().apply(
            self.lp, self.lp_init_amt, self.entry_eth, self.entry_dai,
            holding_period_days = holding_period_days,
        )

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_position_analysis(self):
        result = self.analyze()
        self.assertIsInstance(result, PositionAnalysis)

    def test_all_fields_populated(self):
        result = self.analyze()
        self.assertIsInstance(result.current_value, float)
        self.assertIsInstance(result.hold_value, float)
        self.assertIsInstance(result.il_percentage, float)
        self.assertIsInstance(result.il_with_fees, float)
        self.assertIsInstance(result.fee_income, float)
        self.assertIsInstance(result.net_pnl, float)
        self.assertIsInstance(result.diagnosis, str)

    # ─── At-entry boundary conditions ───────────────────────────────────────

    def test_at_entry_il_near_zero(self):
        result = self.analyze()
        self.assertAlmostEqual(result.il_percentage, 0.0, places = 4)

    def test_at_entry_net_pnl_near_zero(self):
        result = self.analyze()
        self.assertAlmostEqual(result.net_pnl, 0.0, places = 4)

    def test_at_entry_current_value_equals_hold_value(self):
        result = self.analyze()
        self.assertAlmostEqual(result.current_value, result.hold_value, places = 4)

    def test_at_entry_values_positive(self):
        result = self.analyze()
        self.assertGreater(result.current_value, 0)
        self.assertGreater(result.hold_value, 0)

    # ─── After price move ───────────────────────────────────────────────────

    def test_after_price_move_il_negative(self):
        Swap().apply(self.lp, self.dai, USER, 10000)
        result = self.analyze()
        self.assertLess(result.il_percentage, 0)

    def test_after_price_move_net_pnl_negative(self):
        Swap().apply(self.lp, self.dai, USER, 10000)
        result = self.analyze()
        self.assertLess(result.net_pnl, 0)

    def test_il_with_fees_not_worse_than_il_raw(self):
        # il_with_fees accounts for fee income; it should never be strictly
        # worse than pure-price IL. Allow a small numerical tolerance.
        Swap().apply(self.lp, self.dai, USER, 10000)
        result = self.analyze()
        self.assertGreaterEqual(result.il_with_fees, result.il_percentage - 1e-9)

    # ─── Real APR annualization ─────────────────────────────────────────────

    def test_real_apr_none_without_holding_period(self):
        result = self.analyze()
        self.assertIsNone(result.real_apr)

    def test_real_apr_computed_with_holding_period(self):
        Swap().apply(self.lp, self.dai, USER, 10000)
        result = self.analyze(holding_period_days = 30)
        self.assertIsNotNone(result.real_apr)
        self.assertIsInstance(result.real_apr, float)

    def test_real_apr_annualization_direction(self):
        # Same loss, shorter holding period → more extreme annualized APR
        # (further from zero). net_pnl is negative after the swap, so the
        # 30-day APR should be more negative than the 365-day APR.
        Swap().apply(self.lp, self.dai, USER, 10000)
        result_30d = self.analyze(holding_period_days = 30)
        result_365d = self.analyze(holding_period_days = 365)
        self.assertLess(result_30d.real_apr, result_365d.real_apr)

    # ─── Diagnosis string ───────────────────────────────────────────────────

    def test_diagnosis_is_valid_category(self):
        result = self.analyze()
        self.assertIn(
            result.diagnosis,
            ["net_positive", "fee_compensated", "il_dominant"],
        )

    def test_diagnosis_after_price_move_is_il_dominant(self):
        # After a one-sided swap with no further trading activity, fees
        # earned are trivial relative to IL drag, so diagnosis should flag IL.
        Swap().apply(self.lp, self.dai, USER, 10000)
        result = self.analyze()
        self.assertEqual(result.diagnosis, "il_dominant")


# ─── V3 smoke suite ──────────────────────────────────────────────
#
# Added retroactively to cover the gap I shipped with primitive #1 —
# the original test file only exercised V2, so the V3 codepath through
# LPQuote(False).get_amount_from_lp was never run. These smoke tests
# hold the V3 path accountable to the same entry-condition invariants
# as V2: at entry, IL and net_pnl should be essentially zero.

class TestAnalyzePositionV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def analyze(self, holding_period_days = None):
        return AnalyzePosition().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
            holding_period_days = holding_period_days,
        )

    def test_v3_returns_position_analysis(self):
        result = self.analyze()
        self.assertIsInstance(result, PositionAnalysis)

    def test_v3_at_entry_il_near_zero(self):
        result = self.analyze()
        self.assertAlmostEqual(result.il_percentage, 0.0, places = 4)

    def test_v3_at_entry_net_pnl_near_zero(self):
        result = self.analyze()
        self.assertAlmostEqual(result.net_pnl, 0.0, places = 4)


if __name__ == '__main__':
    unittest.main()
