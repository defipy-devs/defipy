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

from python.prod.utils.data import BalancerPriceMoveScenario
from python.prod.primitives.position import SimulateBalancerPriceMove


USER = "user0"


# ══════════════════════════════════════════════════════════════════════
# Shape & return type
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _simulate(self, price_change_pct):
        return SimulateBalancerPriceMove().apply(
            self.setup.lp, price_change_pct, self.setup.lp_init_amt,
        )

    def test_returns_balancer_price_move_scenario(self):
        result = self._simulate(-0.30)
        self.assertIsInstance(result, BalancerPriceMoveScenario)

    def test_all_fields_populated(self):
        result = self._simulate(-0.30)
        self.assertIsInstance(result.base_tkn_name, str)
        self.assertIsInstance(result.opp_tkn_name, str)
        self.assertIsInstance(result.base_weight, float)
        self.assertIsInstance(result.new_price_ratio, float)
        self.assertIsInstance(result.new_value, float)
        self.assertIsInstance(result.il_at_new_price, float)
        self.assertIsInstance(result.value_change_pct, float)

    def test_token_names_match_pool_order(self):
        result = self._simulate(-0.30)
        self.assertEqual(result.base_tkn_name, "ETH")
        self.assertEqual(result.opp_tkn_name, "DAI")

    def test_base_weight_from_pool(self):
        result = self._simulate(0.0)
        self.assertAlmostEqual(result.base_weight, 0.5, places = 6)

    def test_fee_projection_is_none(self):
        result = self._simulate(-0.30)
        self.assertIsNone(result.fee_projection)


# ══════════════════════════════════════════════════════════════════════
# Identity: zero shock
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveAtIdentity(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _simulate(self, pct):
        return SimulateBalancerPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_zero_shock_gives_unit_alpha(self):
        result = self._simulate(0.0)
        self.assertAlmostEqual(result.new_price_ratio, 1.0, places = 10)

    def test_zero_shock_gives_zero_il(self):
        result = self._simulate(0.0)
        self.assertAlmostEqual(result.il_at_new_price, 0.0, places = 6)

    def test_zero_shock_gives_zero_value_change(self):
        result = self._simulate(0.0)
        self.assertAlmostEqual(result.value_change_pct, 0.0, places = 6)


# ══════════════════════════════════════════════════════════════════════
# Alpha mapping
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveAlpha(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _simulate(self, pct):
        return SimulateBalancerPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_alpha_maps_from_price_change_pct(self):
        # alpha = 1 + pct
        self.assertAlmostEqual(
            self._simulate(-0.30).new_price_ratio, 0.70, places = 10,
        )
        self.assertAlmostEqual(
            self._simulate(+0.50).new_price_ratio, 1.50, places = 10,
        )
        self.assertAlmostEqual(
            self._simulate(+1.00).new_price_ratio, 2.00, places = 10,
        )


# ══════════════════════════════════════════════════════════════════════
# IL direction and magnitude (50/50 baseline)
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveILDirection(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _simulate(self, pct):
        return SimulateBalancerPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_price_drop_gives_nonpositive_il(self):
        result = self._simulate(-0.30)
        self.assertLessEqual(result.il_at_new_price, 0.0)

    def test_price_rise_gives_nonpositive_il(self):
        result = self._simulate(+0.50)
        self.assertLessEqual(result.il_at_new_price, 0.0)

    def test_larger_drop_gives_larger_il_magnitude(self):
        il_30 = self._simulate(-0.30).il_at_new_price
        il_50 = self._simulate(-0.50).il_at_new_price
        self.assertGreater(abs(il_50), abs(il_30))

    def test_50_50_matches_v2_il_symmetry(self):
        # At w=0.5, Balancer IL reduces to the V2 classical form, which
        # is symmetric under alpha inversion: IL(alpha) == IL(1/alpha).
        il_up = self._simulate(+1.0).il_at_new_price     # alpha = 2
        il_dn = self._simulate(-0.5).il_at_new_price     # alpha = 0.5
        self.assertAlmostEqual(il_up, il_dn, places = 6)


# ══════════════════════════════════════════════════════════════════════
# Weight-dependence: 80/20 vs 50/50 at same shock
# ══════════════════════════════════════════════════════════════════════

def test_80_20_has_less_il_than_50_50_at_same_shock(weighted_balancer_setup):
    # The distinguishing Balancer property: at w_base = 0.8 (heavier on
    # the moving asset), IL at the same alpha is smaller in magnitude
    # than at w_base = 0.5. Same comparison as the AnalyzeBalancerPosition
    # test — but here we're simulating a hypothetical shock rather than
    # running a real swap, so the comparison is at pure alpha-equivalent.
    setup_50 = weighted_balancer_setup(0.5, suffix = 'sim50')
    setup_80 = weighted_balancer_setup(0.8, suffix = 'sim80')

    prim = SimulateBalancerPriceMove()
    r50 = prim.apply(setup_50.lp, -0.30, setup_50.lp_init_amt)
    r80 = prim.apply(setup_80.lp, -0.30, setup_80.lp_init_amt)

    # Both IL values should be negative (standard weighted-pool IL).
    assert r50.il_at_new_price < 0
    assert r80.il_at_new_price < 0

    # 80/20 has smaller IL magnitude at the same alpha — the weighted
    # IL formula's core property.
    assert abs(r80.il_at_new_price) < abs(r50.il_at_new_price)


def test_base_weight_surfaces_on_result(weighted_balancer_setup):
    # The base_weight on the result reflects the pool's actual weight,
    # which is useful for LLMs interpreting the result without looking
    # at the pool itself.
    setup = weighted_balancer_setup(0.7, suffix = 'sim70')
    result = SimulateBalancerPriceMove().apply(
        setup.lp, -0.20, setup.lp_init_amt,
    )
    assert abs(result.base_weight - 0.7) < 1e-6


# ══════════════════════════════════════════════════════════════════════
# Position size scaling
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveScaling(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, balancer_setup):
        self.setup = balancer_setup

    def _simulate(self, pct, lp_amt):
        return SimulateBalancerPriceMove().apply(
            self.setup.lp, pct, lp_amt,
        )

    def test_doubling_position_size_doubles_new_value(self):
        half = self._simulate(-0.30, self.setup.lp_init_amt / 2)
        full = self._simulate(-0.30, self.setup.lp_init_amt)
        self.assertAlmostEqual(
            full.new_value, 2.0 * half.new_value, places = 4,
        )

    def test_il_invariant_under_position_scaling(self):
        half = self._simulate(-0.30, self.setup.lp_init_amt / 2)
        full = self._simulate(-0.30, self.setup.lp_init_amt)
        self.assertAlmostEqual(
            full.il_at_new_price, half.il_at_new_price, places = 6,
        )

    def test_value_change_pct_invariant_under_scaling(self):
        half = self._simulate(-0.30, self.setup.lp_init_amt / 2)
        full = self._simulate(-0.30, self.setup.lp_init_amt)
        self.assertAlmostEqual(
            full.value_change_pct, half.value_change_pct, places = 6,
        )


# ══════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════

class TestSimulateBalancerPriceMoveValidation(unittest.TestCase):

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
            SimulateBalancerPriceMove().apply(lp_v2, -0.30, 1.0)
        self.assertIn("BalancerExchange", str(ctx.exception))


def test_price_change_at_minus_one_raises(balancer_setup):
    with pytest.raises(ValueError):
        SimulateBalancerPriceMove().apply(
            balancer_setup.lp, -1.0, balancer_setup.lp_init_amt,
        )


def test_price_change_below_minus_one_raises(balancer_setup):
    with pytest.raises(ValueError):
        SimulateBalancerPriceMove().apply(
            balancer_setup.lp, -1.5, balancer_setup.lp_init_amt,
        )


def test_zero_lp_init_amt_raises(balancer_setup):
    # Propagates from BalancerImpLoss's validation.
    with pytest.raises(ValueError):
        SimulateBalancerPriceMove().apply(
            balancer_setup.lp, -0.30, 0.0,
        )


def test_negative_lp_init_amt_raises(balancer_setup):
    with pytest.raises(ValueError):
        SimulateBalancerPriceMove().apply(
            balancer_setup.lp, -0.30, -10.0,
        )


if __name__ == '__main__':
    unittest.main()
