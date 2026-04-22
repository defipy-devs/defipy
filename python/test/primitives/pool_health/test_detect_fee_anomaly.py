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

from python.prod.utils.data import FeeAnomalyResult
from python.prod.primitives.pool_health import DetectFeeAnomaly


USER = "user0"


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestDetectFeeAnomalyV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """v2_setup: 1000 ETH / 100000 DAI V2 LP, USER owns 100%.
        V2 fee hard-coded at 30 bps (997/1000 in swap math)."""
        self.setup = v2_setup

    def _detect(self, token_in = None, test_amount = None, **ctor_kwargs):
        tkn = token_in if token_in is not None else self.setup.eth
        return DetectFeeAnomaly(**ctor_kwargs).apply(
            self.setup.lp, tkn, test_amount = test_amount,
        )

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_fee_anomaly_result(self):
        result = self._detect()
        self.assertIsInstance(result, FeeAnomalyResult)

    def test_field_types(self):
        result = self._detect()
        self.assertIsInstance(result.stated_fee_bps, int)
        self.assertIsInstance(result.test_amount, float)
        self.assertIsInstance(result.theoretical_output, float)
        self.assertIsInstance(result.actual_output, float)
        self.assertIsInstance(result.discrepancy_bps, float)
        self.assertIsInstance(result.direction, str)
        self.assertIsInstance(result.anomaly_detected, bool)

    # ─── Stated fee ─────────────────────────────────────────────────────────

    def test_stated_fee_bps_is_30(self):
        # V2's protocol-constant fee is 30 bps (0.3%).
        result = self._detect()
        self.assertEqual(result.stated_fee_bps, 30)

    # ─── Default test_amount ────────────────────────────────────────────────

    def test_default_test_amount_is_1pct_of_reserve(self):
        # setup has 1000 ETH as reserve0; 1% = 10 ETH.
        result = self._detect(token_in = self.setup.eth)
        self.assertAlmostEqual(result.test_amount, 10.0, places = 6)

    def test_default_test_amount_dai_side(self):
        # setup has 100000 DAI as reserve1; 1% = 1000 DAI.
        result = self._detect(token_in = self.setup.dai)
        self.assertAlmostEqual(result.test_amount, 1000.0, places = 6)

    def test_explicit_test_amount_honored(self):
        result = self._detect(test_amount = 5.0)
        self.assertAlmostEqual(result.test_amount, 5.0, places = 6)

    # ─── Well-behaved V2 pool: no anomaly ───────────────────────────────────

    def test_clean_pool_no_anomaly(self):
        # A clean V2 pool's get_amount_out uses the same 997/1000
        # constants the primitive encodes as "theoretical." Discrepancy
        # should be negligible — well below the default 10 bps threshold.
        result = self._detect()
        self.assertFalse(result.anomaly_detected)
        self.assertLess(abs(result.discrepancy_bps), 10.0)

    def test_clean_pool_discrepancy_near_zero(self):
        # Precision claim: the primitive's float math and the pool's
        # integer-with-mul_div_round math should agree to well under
        # 1 bps on a healthy-sized test trade.
        result = self._detect()
        self.assertLess(abs(result.discrepancy_bps), 1.0)

    # ─── Direction classification ───────────────────────────────────────────

    def test_direction_in_valid_set(self):
        result = self._detect()
        self.assertIn(
            result.direction,
            {"pool_underdelivers", "pool_overdelivers"},
        )

    def test_direction_matches_discrepancy_sign(self):
        # direction tracks the sign of discrepancy_bps — always.
        result = self._detect()
        if result.discrepancy_bps >= 0:
            self.assertEqual(result.direction, "pool_underdelivers")
        else:
            self.assertEqual(result.direction, "pool_overdelivers")

    # ─── Theoretical output correctness ─────────────────────────────────────

    def test_theoretical_output_matches_hand_formula(self):
        # Closed form: dy = (dx · 0.997 · y) / (x + dx · 0.997).
        # At dx = 10 ETH (default 1% of 1000), x = 1000, y = 100000:
        #   dx_net = 9.97
        #   dy = 9.97 · 100000 / (1000 + 9.97) = 997000 / 1009.97 = 987.1595...
        result = self._detect()
        dx = 10.0
        dx_net = dx * 0.997
        expected = (dx_net * 100000.0) / (1000.0 + dx_net)
        self.assertAlmostEqual(
            result.theoretical_output, expected, places = 6,
        )

    def test_actual_output_matches_lp_get_amount_out(self):
        # The primitive reports lp.get_amount_out as actual_output
        # verbatim. Sanity check the plumbing.
        result = self._detect()
        expected_actual = self.setup.lp.get_amount_out(
            result.test_amount, self.setup.eth,
        )
        self.assertAlmostEqual(
            result.actual_output, expected_actual, places = 10,
        )

    # ─── Threshold semantics ────────────────────────────────────────────────

    def test_threshold_disables_anomaly_when_very_high(self):
        # Any clean-pool discrepancy is < 0.1 bps; threshold = 10000
        # (i.e. 100%) certainly won't flag.
        result = self._detect(discrepancy_threshold_bps = 10000.0)
        self.assertFalse(result.anomaly_detected)

    def test_threshold_zero_flags_even_tiny_discrepancy(self):
        # With threshold 0, any discrepancy > 0 flags. On a clean pool
        # the tiny rounding between float and integer math produces a
        # sub-bps discrepancy that is nonetheless strictly nonzero.
        # anomaly_detected should be True (since |discrepancy| > 0).
        # Note: if the specific pool happens to produce EXACTLY zero
        # discrepancy, this would assertFalse — hence we check the
        # conjunction with the actual discrepancy.
        result = self._detect(discrepancy_threshold_bps = 0.0)
        if abs(result.discrepancy_bps) > 0:
            self.assertTrue(result.anomaly_detected)
        else:
            self.assertFalse(result.anomaly_detected)

    # ─── Validation ─────────────────────────────────────────────────────────

    def test_negative_threshold_raises(self):
        with self.assertRaises(ValueError):
            DetectFeeAnomaly(discrepancy_threshold_bps = -1.0)

    def test_zero_test_amount_raises(self):
        with self.assertRaises(ValueError):
            self._detect(test_amount = 0.0)

    def test_negative_test_amount_raises(self):
        with self.assertRaises(ValueError):
            self._detect(test_amount = -1.0)

    def test_unknown_token_raises(self):
        from uniswappy.erc import ERC20
        stray = ERC20("STRAY", "0xff")
        with self.assertRaises(ValueError):
            self._detect(token_in = stray)

    # ─── Pool state not mutated ─────────────────────────────────────────────

    def test_pool_reserves_unchanged_after_apply(self):
        res0_before = self.setup.lp.reserve0
        res1_before = self.setup.lp.reserve1
        self._detect()
        self.assertEqual(self.setup.lp.reserve0, res0_before)
        self.assertEqual(self.setup.lp.reserve1, res1_before)


# ─── V3 rejection ───────────────────────────────────────────────────────────

class TestDetectFeeAnomalyV3Rejection(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_v3_raises_value_error(self):
        # V3 is out of scope for v1 — the available in-range quote path
        # hard-codes 30 bps and diverges from lp.fee for non-30-bps
        # pools. Primitive should refuse cleanly rather than produce
        # a misleading result.
        with self.assertRaises(ValueError):
            DetectFeeAnomaly().apply(
                self.setup.lp, self.setup.eth,
            )


if __name__ == '__main__':
    unittest.main()
