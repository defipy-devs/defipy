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

from python.prod.utils.data import RugSignalReport, PoolHealth
from python.prod.primitives.pool_health import DetectRugSignals


USER = "user0"


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestDetectRugSignalsV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """v2_setup: 1000 ETH / 100000 DAI V2 LP, USER owns 100%.
        TVL-in-token0 = 2000 ETH. Single LP at fixture start.
        Zero swaps."""
        self.setup = v2_setup

    def _detect(self, **overrides):
        return DetectRugSignals().apply(self.setup.lp, **overrides)

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_rug_signal_report(self):
        result = self._detect()
        self.assertIsInstance(result, RugSignalReport)

    def test_report_carries_pool_health(self):
        result = self._detect()
        self.assertIsInstance(result.pool_health, PoolHealth)
        self.assertEqual(result.pool_health.version, "V2")

    def test_signal_types_are_bool(self):
        result = self._detect()
        self.assertIsInstance(result.tvl_suspiciously_low, bool)
        self.assertIsInstance(result.single_sided_concentration, bool)
        self.assertIsInstance(result.inactive_with_liquidity, bool)

    def test_signals_detected_matches_true_count(self):
        result = self._detect()
        expected = sum([
            result.tvl_suspiciously_low,
            result.single_sided_concentration,
            result.inactive_with_liquidity,
        ])
        self.assertEqual(result.signals_detected, expected)

    def test_risk_level_in_valid_set(self):
        result = self._detect()
        self.assertIn(result.risk_level, {"low", "medium", "high", "critical"})

    # ─── Fixture default: single LP, no swaps, healthy TVL ──────────────────
    # TVL-in-token0 = 2000 ETH, well above the 10 ETH default floor.
    # USER owns ~100%, trips single_sided_concentration at the 0.9 default.
    # No swaps yet, trips inactive_with_liquidity. Exactly 2 signals → "high".

    def test_fixture_default_fires_two_signals(self):
        result = self._detect()
        self.assertFalse(result.tvl_suspiciously_low)
        self.assertTrue(result.single_sided_concentration)
        self.assertTrue(result.inactive_with_liquidity)
        self.assertEqual(result.signals_detected, 2)
        self.assertEqual(result.risk_level, "high")

    def test_details_populated_for_fired_signals(self):
        result = self._detect()
        # Two signals fire → at least two detail lines.
        self.assertGreaterEqual(len(result.details), 2)

    # ─── Diluted LPs clear the concentration signal ─────────────────────────

    def test_adding_lps_clears_concentration(self):
        # USER starts at ~100%. Add enough additional LPs at the same
        # ratio to drag top share below 0.90.
        for user_i in ["user_a", "user_b", "user_c"]:
            self.setup.lp.add_liquidity(user_i, 1000.0, 100000.0, 1000.0, 100000.0)
        result = self._detect()
        self.assertFalse(result.single_sided_concentration)

    # ─── Swapping activates, so inactive signal clears ──────────────────────

    def test_swap_clears_inactive_signal(self):
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self._detect()
        self.assertFalse(result.inactive_with_liquidity)

    # ─── TVL floor override fires when raised above TVL ─────────────────────

    def test_tvl_floor_override_fires_signal(self):
        # Fixture TVL is 2000 ETH. Floor of 10000 should trip the signal.
        result = self._detect(tvl_floor = 10000.0)
        self.assertTrue(result.tvl_suspiciously_low)

    def test_tvl_floor_default_does_not_fire_on_healthy_pool(self):
        # 2000 ETH TVL > 10 ETH default floor → does not fire.
        result = self._detect()
        self.assertFalse(result.tvl_suspiciously_low)

    # ─── Concentration threshold override ───────────────────────────────────

    def test_concentration_threshold_override_can_clear_signal(self):
        # Raising the bar to 1.0 means even 99.999% doesn't trip.
        result = self._detect(lp_concentration_threshold = 1.0)
        self.assertFalse(result.single_sided_concentration)

    # ─── Risk-bucket arithmetic ─────────────────────────────────────────────

    def test_all_signals_clear_returns_low(self):
        # Add dilution to kill concentration, swap to kill inactivity.
        # Default TVL floor (10) is well below the new 8000-ETH TVL.
        for user_i in ["user_a", "user_b", "user_c"]:
            self.setup.lp.add_liquidity(user_i, 1000.0, 100000.0, 1000.0, 100000.0)
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self._detect()
        self.assertEqual(result.signals_detected, 0)
        self.assertEqual(result.risk_level, "low")

    def test_one_signal_returns_medium(self):
        # Swap (clears inactive) + dilute (clears concentration),
        # but force the TVL signal via an override above the new TVL
        # (~8000 ETH after dilution).
        for user_i in ["user_a", "user_b", "user_c"]:
            self.setup.lp.add_liquidity(user_i, 1000.0, 100000.0, 1000.0, 100000.0)
        Swap().apply(self.setup.lp, self.setup.eth, USER, 10.0)
        result = self._detect(tvl_floor = 20000.0)
        self.assertEqual(result.signals_detected, 1)
        self.assertEqual(result.risk_level, "medium")

    def test_three_signals_returns_critical(self):
        # Fixture already fires concentration + inactive. Add a tvl_floor
        # override above 2000 to fire the third signal.
        result = self._detect(tvl_floor = 5000.0)
        self.assertEqual(result.signals_detected, 3)
        self.assertEqual(result.risk_level, "critical")

    # ─── Validation ──────────────────────────────────────────────────────────

    def test_raises_on_zero_lp_concentration_threshold(self):
        with self.assertRaises(ValueError):
            self._detect(lp_concentration_threshold = 0.0)

    def test_raises_on_above_one_lp_concentration_threshold(self):
        with self.assertRaises(ValueError):
            self._detect(lp_concentration_threshold = 1.5)

    def test_raises_on_negative_tvl_floor(self):
        with self.assertRaises(ValueError):
            self._detect(tvl_floor = -1.0)

    def test_accepts_zero_tvl_floor(self):
        # tvl_floor=0 is legitimate (effectively disables the check;
        # TVL > 0 never trips it).
        result = self._detect(tvl_floor = 0.0)
        self.assertFalse(result.tvl_suspiciously_low)


# ─── V3 suite ────────────────────────────────────────────────────────────────

class TestDetectRugSignalsV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def _detect(self, **overrides):
        return DetectRugSignals().apply(self.setup.lp, **overrides)

    def test_v3_returns_rug_signal_report(self):
        result = self._detect()
        self.assertIsInstance(result, RugSignalReport)

    def test_v3_inactive_signal_always_false(self):
        # V3 has no per-swap history → signal can't evaluate → False.
        result = self._detect()
        self.assertFalse(result.inactive_with_liquidity)

    def test_v3_inactive_detail_explains_skip(self):
        # A note should be appended to details explaining why the
        # V2-only signal was skipped.
        result = self._detect()
        self.assertTrue(any(
            "unavailable for V3" in line
            for line in result.details
        ))

    def test_v3_concentration_still_fires(self):
        # V3 fixture also has a single LP at 100% — concentration
        # signal is protocol-agnostic and should fire here too.
        result = self._detect()
        self.assertTrue(result.single_sided_concentration)


if __name__ == '__main__':
    unittest.main()
