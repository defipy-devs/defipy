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

from uniswappy.process.swap import Swap
from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData

from python.prod.utils.data import PoolHealth
from python.prod.primitives.pool_health import CheckPoolHealth


USER = "user0"
USER2 = "user1"


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestCheckPoolHealthV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """v2_setup: 1000 ETH / 100000 DAI V2 LP, USER owns 100%.
        Spot price = 100 DAI/ETH. One LP, no swaps yet."""
        self.setup = v2_setup

    def health(self, recent_window = 20):
        return CheckPoolHealth().apply(self.setup.lp, recent_window = recent_window)

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_pool_health(self):
        result = self.health()
        self.assertIsInstance(result, PoolHealth)

    def test_version_reported(self):
        result = self.health()
        self.assertEqual(result.version, "V2")

    def test_token_names_reported(self):
        result = self.health()
        self.assertEqual(result.token0_name, "ETH")
        self.assertEqual(result.token1_name, "DAI")

    # ─── Reserves & TVL ──────────────────────────────────────────────────────

    def test_reserves_match_fixture(self):
        result = self.health()
        self.assertAlmostEqual(result.reserve0, 1000.0, places = 4)
        self.assertAlmostEqual(result.reserve1, 100000.0, places = 4)

    def test_spot_price_is_100(self):
        # 100000 DAI / 1000 ETH = 100 DAI per ETH.
        result = self.health()
        self.assertAlmostEqual(result.spot_price, 100.0, places = 4)

    def test_tvl_in_token0_is_2000_eth(self):
        # 1000 ETH + 100000 DAI / 100 = 2000 ETH numeraire.
        result = self.health()
        self.assertAlmostEqual(result.tvl_in_token0, 2000.0, places = 4)

    def test_total_liquidity_positive(self):
        result = self.health()
        self.assertGreater(result.total_liquidity, 0.0)

    # ─── Activity: fresh pool has no swaps ───────────────────────────────────

    def test_fresh_pool_has_zero_swaps(self):
        result = self.health()
        self.assertEqual(result.num_swaps, 0)

    def test_fresh_pool_no_activity(self):
        result = self.health()
        self.assertFalse(result.has_activity)

    def test_fresh_pool_no_recent_rate(self):
        # num_swaps == 0 → rate is None (no swaps to average).
        result = self.health()
        self.assertIsNone(result.fee_accrual_rate_recent)

    def test_fresh_pool_zero_fees(self):
        result = self.health()
        self.assertAlmostEqual(result.total_fee0, 0.0, places = 4)
        self.assertAlmostEqual(result.total_fee1, 0.0, places = 4)

    # ─── Activity: post-swap values update ───────────────────────────────────

    def test_after_swap_has_activity(self):
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self.health()
        self.assertTrue(result.has_activity)
        self.assertEqual(result.num_swaps, 1)

    def test_after_swap_fees_accumulate(self):
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self.health()
        # 10 ETH in on token0 side → collected_fee0 should be positive.
        self.assertGreater(result.total_fee0, 0.0)

    def test_after_swap_recent_rate_positive(self):
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self.health()
        self.assertIsNotNone(result.fee_accrual_rate_recent)
        self.assertGreater(result.fee_accrual_rate_recent, 0.0)

    # ─── LP concentration ───────────────────────────────────────────────────

    def test_single_lp_counted_correctly(self):
        # Fixture has USER as sole LP. The "0" MINIMUM_LIQUIDITY sentinel
        # should be excluded, so num_lps == 1, not 2.
        result = self.health()
        self.assertEqual(result.num_lps, 1)

    def test_single_lp_concentration_near_one(self):
        # USER owns essentially 100% (minus MINIMUM_LIQUIDITY sentinel dust).
        result = self.health()
        self.assertGreater(result.top_lp_share_pct, 0.999)
        self.assertLessEqual(result.top_lp_share_pct, 1.0)

    def test_two_lps_counted_correctly(self):
        # Add a second LP at the same ratio.
        self.setup.lp.add_liquidity(USER2, 500.0, 50000.0, 500.0, 50000.0)
        result = self.health()
        self.assertEqual(result.num_lps, 2)

    def test_top_lp_share_after_second_lp(self):
        # USER originally owns ~100%; after USER2 adds ~half again,
        # USER's share should drop to roughly 2/3.
        self.setup.lp.add_liquidity(USER2, 500.0, 50000.0, 500.0, 50000.0)
        result = self.health()
        self.assertLess(result.top_lp_share_pct, 1.0)
        self.assertGreater(result.top_lp_share_pct, 0.5)

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_zero_recent_window(self):
        with self.assertRaises(ValueError):
            self.health(recent_window = 0)

    def test_raises_on_negative_recent_window(self):
        with self.assertRaises(ValueError):
            self.health(recent_window = -5)


# ─── V3 suite ────────────────────────────────────────────────────────────────

class TestCheckPoolHealthV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_v3_returns_pool_health(self):
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertIsInstance(result, PoolHealth)

    def test_v3_version_reported(self):
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertEqual(result.version, "V3")

    def test_v3_swap_history_is_none(self):
        # Documented: V3 doesn't track per-swap fee history.
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertIsNone(result.num_swaps)
        self.assertIsNone(result.fee_accrual_rate_recent)

    def test_v3_no_activity_reported(self):
        # has_activity requires num_swaps > 0; V3's None means False.
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertFalse(result.has_activity)

    def test_v3_spot_price_positive(self):
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertGreater(result.spot_price, 0.0)

    def test_v3_tvl_positive(self):
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertGreater(result.tvl_in_token0, 0.0)

    def test_v3_lp_count_positive(self):
        result = CheckPoolHealth().apply(self.setup.lp)
        self.assertGreaterEqual(result.num_lps, 1)


if __name__ == '__main__':
    unittest.main()
