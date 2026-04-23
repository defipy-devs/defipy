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

from python.prod.utils.data import StableswapPriceMoveScenario
from python.prod.primitives.position import SimulateStableswapPriceMove


USER = "user0"


# ══════════════════════════════════════════════════════════════════════
# Shape & return type
# ══════════════════════════════════════════════════════════════════════

class TestSimulateStableswapPriceMoveShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, stableswap_setup):
        self.setup = stableswap_setup

    def _simulate(self, pct):
        return SimulateStableswapPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_returns_stableswap_price_move_scenario(self):
        result = self._simulate(-0.05)
        self.assertIsInstance(result, StableswapPriceMoveScenario)

    def test_core_fields_populated_on_reachable(self):
        result = self._simulate(-0.05)
        self.assertIsNotNone(result.il_at_new_price)
        self.assertIsNotNone(result.new_value)
        self.assertIsNotNone(result.value_change_pct)
        self.assertIsInstance(result.new_price_ratio, float)

    def test_token_names_populated(self):
        result = self._simulate(-0.05)
        self.assertEqual(len(result.token_names), 2)
        self.assertEqual(result.token_names[0], "USDC")
        self.assertEqual(result.token_names[1], "DAI")

    def test_A_recorded(self):
        result = self._simulate(-0.05)
        self.assertEqual(result.A, self.setup.A)

    def test_fee_projection_is_none(self):
        result = self._simulate(-0.05)
        self.assertIsNone(result.fee_projection)


# ══════════════════════════════════════════════════════════════════════
# Identity: zero shock
# ══════════════════════════════════════════════════════════════════════

class TestSimulateStableswapPriceMoveAtIdentity(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, stableswap_setup):
        self.setup = stableswap_setup

    def _simulate(self, pct):
        return SimulateStableswapPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_zero_shock_gives_unit_alpha(self):
        result = self._simulate(0.0)
        self.assertAlmostEqual(result.new_price_ratio, 1.0, places = 10)

    def test_zero_shock_gives_zero_il(self):
        # At-peg short-circuit: IL is exactly 0.
        result = self._simulate(0.0)
        self.assertEqual(result.il_at_new_price, 0.0)

    def test_zero_shock_gives_zero_value_change(self):
        result = self._simulate(0.0)
        self.assertEqual(result.value_change_pct, 0.0)

    def test_zero_shock_new_value_equals_current(self):
        # At zero shock, new_value should equal the LP's pro-rata share.
        # For the fixture (100K USDC + 100K DAI at 100% ownership), new_value
        # should be ~200,000 in peg numeraire.
        result = self._simulate(0.0)
        total_at_peg = sum(self.setup.entry_amounts)
        self.assertAlmostEqual(result.new_value, total_at_peg, places = 2)


# ══════════════════════════════════════════════════════════════════════
# Off-peg reachable behavior (A=10 fixture)
# ══════════════════════════════════════════════════════════════════════

class TestSimulateStableswapPriceMoveReachable(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, stableswap_setup):
        self.setup = stableswap_setup

    def _simulate(self, pct):
        return SimulateStableswapPriceMove().apply(
            self.setup.lp, pct, self.setup.lp_init_amt,
        )

    def test_negative_shock_gives_negative_il(self):
        # At A=10, a 5% shock is well within reachable range.
        result = self._simulate(-0.05)
        self.assertIsNotNone(result.il_at_new_price)
        self.assertLess(result.il_at_new_price, 0.0)

    def test_positive_shock_gives_negative_il(self):
        # Stableswap IL is symmetric around peg, so positive shocks
        # also produce negative IL.
        result = self._simulate(+0.05)
        self.assertIsNotNone(result.il_at_new_price)
        self.assertLess(result.il_at_new_price, 0.0)

    def test_il_symmetric_around_peg(self):
        # IL(alpha) should equal IL(2 - alpha) to leading order:
        # shocks of +5% and -5% (from balanced fixture) should give
        # the same magnitude.
        up = self._simulate(+0.05).il_at_new_price
        dn = self._simulate(-0.05).il_at_new_price
        self.assertAlmostEqual(up, dn, places = 4)

    def test_larger_shock_gives_larger_il_magnitude(self):
        il_2 = self._simulate(-0.02).il_at_new_price
        il_10 = self._simulate(-0.10).il_at_new_price
        # Both reachable at A=10, and |IL| monotone increasing in |shock|.
        self.assertGreater(abs(il_10), abs(il_2))

    def test_reachable_new_value_less_than_current(self):
        # Off-peg → IL < 0 → new_value < current_value.
        result = self._simulate(-0.05)
        total_at_peg = sum(self.setup.entry_amounts)
        self.assertLess(result.new_value, total_at_peg)


# ══════════════════════════════════════════════════════════════════════
# Unreachable-alpha regime (A=200 fixture)
# ══════════════════════════════════════════════════════════════════════

def test_small_shock_at_high_A_is_unreachable(amplified_stableswap_setup):
    # At A=200, even a 2% shock requires |ε| > 0.95 → unreachable.
    # The primitive should return a result with None on the numeric
    # fields but populated with token_names and A.
    setup = amplified_stableswap_setup(200, suffix = 'unreach200')
    result = SimulateStableswapPriceMove().apply(
        setup.lp, -0.02, setup.lp_init_amt,
    )

    assert result.il_at_new_price is None
    assert result.new_value is None
    assert result.value_change_pct is None
    # But the scenario metadata stays populated so caller can see
    # WHAT was unreachable.
    assert result.A == 200
    assert len(result.token_names) == 2
    assert abs(result.new_price_ratio - 0.98) < 1e-9


def test_at_peg_short_circuit_even_at_high_A(amplified_stableswap_setup):
    # Zero shock always hits the at-peg short-circuit regardless of A.
    setup = amplified_stableswap_setup(200, suffix = 'peg200')
    result = SimulateStableswapPriceMove().apply(
        setup.lp, 0.0, setup.lp_init_amt,
    )
    assert result.il_at_new_price == 0.0
    assert result.new_value is not None
    assert result.value_change_pct == 0.0


# ══════════════════════════════════════════════════════════════════════
# Position size scaling
# ══════════════════════════════════════════════════════════════════════

class TestSimulateStableswapPriceMoveScaling(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, stableswap_setup):
        self.setup = stableswap_setup

    def _simulate(self, pct, lp_amt):
        return SimulateStableswapPriceMove().apply(
            self.setup.lp, pct, lp_amt,
        )

    def test_doubling_position_size_doubles_new_value(self):
        half = self._simulate(-0.05, self.setup.lp_init_amt / 2)
        full = self._simulate(-0.05, self.setup.lp_init_amt)
        self.assertAlmostEqual(
            full.new_value, 2.0 * half.new_value, places = 2,
        )

    def test_il_invariant_under_position_scaling(self):
        half = self._simulate(-0.05, self.setup.lp_init_amt / 2)
        full = self._simulate(-0.05, self.setup.lp_init_amt)
        self.assertAlmostEqual(
            full.il_at_new_price, half.il_at_new_price, places = 6,
        )


# ══════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════

class TestSimulateStableswapPriceMoveValidation(unittest.TestCase):

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
            SimulateStableswapPriceMove().apply(lp_v2, -0.05, 1.0)
        self.assertIn("StableswapExchange", str(ctx.exception))


def test_price_change_at_minus_one_raises(stableswap_setup):
    with pytest.raises(ValueError):
        SimulateStableswapPriceMove().apply(
            stableswap_setup.lp, -1.0, stableswap_setup.lp_init_amt,
        )


def test_price_change_below_minus_one_raises(stableswap_setup):
    with pytest.raises(ValueError):
        SimulateStableswapPriceMove().apply(
            stableswap_setup.lp, -1.5, stableswap_setup.lp_init_amt,
        )


def test_zero_lp_init_amt_raises(stableswap_setup):
    # Propagates from StableswapImpLoss's validation.
    with pytest.raises(ValueError):
        SimulateStableswapPriceMove().apply(
            stableswap_setup.lp, -0.05, 0.0,
        )


if __name__ == '__main__':
    unittest.main()
