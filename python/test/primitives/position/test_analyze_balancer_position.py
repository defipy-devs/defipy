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

from uniswappy.erc import ERC20 as UERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData

from python.prod.utils.data import BalancerPositionAnalysis
from python.prod.primitives.position import AnalyzeBalancerPosition


USER = "user0"


# Test-style note:
#
# This file mixes unittest.TestCase classes (for the bulk of tests,
# matching defipy's house pattern) with a small section of plain
# pytest functions for tests that need the `weighted_balancer_setup`
# factory fixture. unittest.TestCase methods can't receive pytest
# fixture parameters directly — the autouse-bind trick works for
# simple fixtures but not for factory fixtures that need per-test
# parameters. Rather than force a workaround, plain functions get
# the factory fixture injected cleanly.


def _do_swap_in(lp, tkn_in_name, tkn_out_name, amt):
    """Execute a Balancer swap_exact_amount_in by token name."""
    tkn_in = lp.vault.get_token(tkn_in_name)
    tkn_out = lp.vault.get_token(tkn_out_name)
    lp.swap_exact_amount_in(amt, tkn_in, tkn_out, USER)


# ══════════════════════════════════════════════════════════════════════
# Shape & return type
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeBalancerPositionShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _analyze(self, **kwargs):
        return AnalyzeBalancerPosition().apply(
            self.setup.lp,
            self.setup.lp_init_amt,
            self.setup.entry_base_amt,
            self.setup.entry_opp_amt,
            **kwargs,
        )

    def test_returns_balancer_position_analysis(self):
        result = self._analyze()
        self.assertIsInstance(result, BalancerPositionAnalysis)

    def test_all_fields_populated(self):
        result = self._analyze()
        self.assertIsInstance(result.current_value, float)
        self.assertIsInstance(result.hold_value, float)
        self.assertIsInstance(result.il_percentage, float)
        self.assertIsInstance(result.il_with_fees, float)
        self.assertIsInstance(result.fee_income, float)
        self.assertIsInstance(result.net_pnl, float)
        self.assertIsInstance(result.diagnosis, str)
        self.assertIsInstance(result.alpha, float)
        self.assertIsInstance(result.base_weight, float)
        self.assertEqual(result.base_tkn_name, "ETH")
        self.assertEqual(result.opp_tkn_name, "DAI")


# ══════════════════════════════════════════════════════════════════════
# At-entry boundary conditions
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeBalancerPositionAtEntry(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _analyze(self):
        return AnalyzeBalancerPosition().apply(
            self.setup.lp,
            self.setup.lp_init_amt,
            self.setup.entry_base_amt,
            self.setup.entry_opp_amt,
        )

    def test_at_entry_alpha_is_one(self):
        result = self._analyze()
        self.assertAlmostEqual(result.alpha, 1.0, places = 6)

    def test_at_entry_il_is_zero(self):
        result = self._analyze()
        self.assertAlmostEqual(result.il_percentage, 0.0, places = 6)

    def test_at_entry_net_pnl_is_zero(self):
        result = self._analyze()
        self.assertAlmostEqual(result.net_pnl, 0.0, places = 4)

    def test_at_entry_current_equals_hold(self):
        result = self._analyze()
        self.assertAlmostEqual(
            result.current_value, result.hold_value, places = 4,
        )

    def test_at_entry_values_positive(self):
        result = self._analyze()
        self.assertGreater(result.current_value, 0)
        self.assertGreater(result.hold_value, 0)

    def test_at_entry_diagnosis_is_il_dominant(self):
        # net_pnl == 0 exactly at entry falls through the
        # "net_positive" branch (strict >) into "il_dominant". Not
        # the most informative label at entry, but the diagnosis
        # string is most useful post-move. Documented here so the
        # expectation matches.
        result = self._analyze()
        self.assertEqual(result.diagnosis, "il_dominant")


# ══════════════════════════════════════════════════════════════════════
# Post-swap behavior
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeBalancerPositionPostSwap(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _analyze(self):
        return AnalyzeBalancerPosition().apply(
            self.setup.lp,
            self.setup.lp_init_amt,
            self.setup.entry_base_amt,
            self.setup.entry_opp_amt,
        )

    def test_after_dai_for_eth_il_negative(self):
        # Swap DAI in for ETH out. Pool DAI ↑, ETH ↓, so spot
        # (DAI per ETH) rises → alpha > 1 → IL negative.
        _do_swap_in(self.setup.lp, "DAI", "ETH", 10000)
        result = self._analyze()
        self.assertLess(result.il_percentage, 0)

    def test_after_swap_net_pnl_negative(self):
        _do_swap_in(self.setup.lp, "DAI", "ETH", 10000)
        result = self._analyze()
        self.assertLess(result.net_pnl, 0)

    def test_after_dai_in_alpha_above_one(self):
        _do_swap_in(self.setup.lp, "DAI", "ETH", 10000)
        result = self._analyze()
        self.assertGreater(result.alpha, 1.0)

    def test_after_eth_in_alpha_below_one(self):
        _do_swap_in(self.setup.lp, "ETH", "DAI", 1)
        result = self._analyze()
        self.assertLess(result.alpha, 1.0)

    def test_il_reasonable_magnitude_on_modest_swap(self):
        # 50/50 pool, 5% of reserves swapped: IL should be modest
        # (well above -20%) to confirm the formula isn't blowing up.
        _do_swap_in(self.setup.lp, "DAI", "ETH", 5000)
        result = self._analyze()
        self.assertLess(result.il_percentage, 0)
        self.assertGreater(result.il_percentage, -0.20)


# ══════════════════════════════════════════════════════════════════════
# Weight-dependent IL behavior (plain pytest style — factory fixture)
# ══════════════════════════════════════════════════════════════════════

def test_80_20_has_less_il_than_50_50(weighted_balancer_setup):
    # An 80/20 base/opp pool has LESS |IL| than 50/50 at the same
    # directional shock when the base token is the one that moved.
    # This is the core Balancer-weighting payoff — heavier weighting
    # on the moving asset bounds IL exposure.
    setup_50 = weighted_balancer_setup(0.5, suffix = 'w50')
    setup_80 = weighted_balancer_setup(0.8, suffix = 'w80')

    _do_swap_in(setup_50.lp, "DAI", "ETH", 5000)
    _do_swap_in(setup_80.lp, "DAI", "ETH", 5000)

    analyze = AnalyzeBalancerPosition()
    result_50 = analyze.apply(
        setup_50.lp, setup_50.lp_init_amt,
        setup_50.entry_base_amt, setup_50.entry_opp_amt,
    )
    result_80 = analyze.apply(
        setup_80.lp, setup_80.lp_init_amt,
        setup_80.entry_base_amt, setup_80.entry_opp_amt,
    )

    assert abs(result_80.il_percentage) < abs(result_50.il_percentage)


def test_base_weight_recorded_in_result(weighted_balancer_setup):
    setup = weighted_balancer_setup(0.7, suffix = 'w70')
    result = AnalyzeBalancerPosition().apply(
        setup.lp, setup.lp_init_amt,
        setup.entry_base_amt, setup.entry_opp_amt,
    )
    assert abs(result.base_weight - 0.7) < 1e-6


# ══════════════════════════════════════════════════════════════════════
# Real APR annualization
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeBalancerPositionRealAPR(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _analyze(self, holding_period_days = None):
        return AnalyzeBalancerPosition().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_base_amt, self.setup.entry_opp_amt,
            holding_period_days = holding_period_days,
        )

    def test_real_apr_none_without_holding_period(self):
        result = self._analyze()
        self.assertIsNone(result.real_apr)

    def test_real_apr_computed_with_holding_period(self):
        _do_swap_in(self.setup.lp, "DAI", "ETH", 10000)
        result = self._analyze(holding_period_days = 30)
        self.assertIsNotNone(result.real_apr)
        self.assertIsInstance(result.real_apr, float)

    def test_real_apr_annualization_direction(self):
        _do_swap_in(self.setup.lp, "DAI", "ETH", 10000)
        result_30d = self._analyze(holding_period_days = 30)
        result_365d = self._analyze(holding_period_days = 365)
        # net_pnl negative after swap → 30d APR more negative than 365d.
        self.assertLess(result_30d.real_apr, result_365d.real_apr)


# ══════════════════════════════════════════════════════════════════════
# Validation — unittest class for pool-type rejection, pytest for
# fixture-dependent cases.
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeBalancerPositionValidation(unittest.TestCase):

    def test_v2_lp_raises(self):
        eth = UERC20("ETH", "0x99")
        dai = UERC20("DAI", "0x98")
        factory = UniswapFactory("test factory", "0x01")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V2", address = "0x001",
        )
        lp_v2 = factory.deploy(exch_data)
        lp_v2.add_liquidity(USER, 10.0, 10000.0, 10.0, 10000.0)
        with self.assertRaises(ValueError) as ctx:
            AnalyzeBalancerPosition().apply(lp_v2, 1.0, 10.0, 10000.0)
        self.assertIn("BalancerExchange", str(ctx.exception))


def test_zero_entry_base_raises(balancer_setup):
    with pytest.raises(ValueError):
        AnalyzeBalancerPosition().apply(
            balancer_setup.lp, balancer_setup.lp_init_amt,
            0.0, balancer_setup.entry_opp_amt,
        )


def test_zero_entry_opp_raises(balancer_setup):
    with pytest.raises(ValueError):
        AnalyzeBalancerPosition().apply(
            balancer_setup.lp, balancer_setup.lp_init_amt,
            balancer_setup.entry_base_amt, 0.0,
        )


def test_zero_lp_init_amt_raises(balancer_setup):
    # Propagates from BalancerImpLoss's own validation.
    with pytest.raises(ValueError):
        AnalyzeBalancerPosition().apply(
            balancer_setup.lp, 0.0,
            balancer_setup.entry_base_amt,
            balancer_setup.entry_opp_amt,
        )


if __name__ == '__main__':
    unittest.main()
