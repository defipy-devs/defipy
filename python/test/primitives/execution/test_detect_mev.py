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

from uniswappy.cpt.quote import LPQuote

from python.prod.utils.data import MEVDetectionResult
from python.prod.primitives.execution import DetectMEV


def _theoretical(lp, token_in, amount_in, lwr_tick = None, upr_tick = None):
    """Helper: compute what DetectMEV will compute for theoretical_output,
    so tests can construct matching/mismatching actual_output values
    without reinventing the wheel."""
    return LPQuote(
        quote_opposing = True, include_fee = True,
    ).get_amount(lp, token_in, amount_in, lwr_tick, upr_tick)


# ═══════════════════════════════════════════════════════════════════════════
# Shape & return type
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_returns_mev_detection_result(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
        )
        self.assertIsInstance(result, MEVDetectionResult)

    def test_echoes_amount_and_token(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
        )
        self.assertEqual(result.amount_in, 10.0)
        self.assertEqual(result.token_in_name, "ETH")

    def test_direction_is_one_of_allowed(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.99,
        )
        self.assertIn(result.direction,
                      {"underdelivered", "overdelivered", "matches"})


# ═══════════════════════════════════════════════════════════════════════════
# "matches" path — actual exactly equals theoretical
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVMatches(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_exact_match_direction(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
        )
        self.assertEqual(result.direction, "matches")

    def test_exact_match_extraction_zero(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
        )
        self.assertEqual(result.extraction_amount, 0.0)
        self.assertEqual(result.extraction_bps, 0.0)

    def test_exact_match_not_frontrun(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
        )
        self.assertFalse(result.likely_frontrun)


# ═══════════════════════════════════════════════════════════════════════════
# "underdelivered" path — caller received less than expected
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVUnderdelivered(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_5pct_shortfall_direction(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.95,
        )
        self.assertEqual(result.direction, "underdelivered")

    def test_5pct_shortfall_extraction_bps_matches(self):
        # actual = 0.95 * theoretical → extraction_pct = 0.05 → 500 bps.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.95,
        )
        self.assertAlmostEqual(result.extraction_bps, 500.0, places = 6)

    def test_5pct_shortfall_flags_frontrun(self):
        # 500 bps is well above the default 50 bps threshold.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.95,
        )
        self.assertTrue(result.likely_frontrun)

    def test_tiny_shortfall_below_threshold_does_not_flag(self):
        # Shortfall of 0.1% = 10 bps, well below 50 bps threshold.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.999,
        )
        self.assertEqual(result.direction, "underdelivered")
        self.assertFalse(result.likely_frontrun)

    def test_extraction_amount_matches_arithmetic(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        actual = theo * 0.95
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, actual,
        )
        self.assertAlmostEqual(
            result.extraction_amount, theo - actual, places = 10,
        )


# ═══════════════════════════════════════════════════════════════════════════
# "overdelivered" path — caller received more than expected
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVOverdelivered(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_overdelivery_direction(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 1.05,
        )
        self.assertEqual(result.direction, "overdelivered")

    def test_overdelivery_never_flags_frontrun(self):
        # Even 500 bps OVER delivery should not flag — overdelivery
        # is not a frontrun signal.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 1.05,
        )
        self.assertFalse(result.likely_frontrun)

    def test_overdelivery_extraction_is_negative(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 1.05,
        )
        self.assertLess(result.extraction_amount, 0.0)
        self.assertLess(result.extraction_bps, 0.0)


# ═══════════════════════════════════════════════════════════════════════════
# Composition consistency with LPQuote
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVComposition(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_theoretical_output_matches_lpquote(self):
        # The primitive's theoretical_output should equal LPQuote's
        # direct computation on identical inputs.
        expected = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, expected,
        )
        self.assertAlmostEqual(
            result.theoretical_output, expected, places = 10,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Threshold override — non-default frontrun_threshold_bps
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVThreshold(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_100bps_extraction_flags_at_default_threshold(self):
        # actual = 0.99 * theoretical → 100 bps; default threshold = 50.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.99,
        )
        self.assertTrue(result.likely_frontrun)

    def test_100bps_extraction_does_not_flag_at_200bps_threshold(self):
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV(frontrun_threshold_bps = 200.0).apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.99,
        )
        self.assertEqual(result.direction, "underdelivered")
        self.assertFalse(result.likely_frontrun)

    def test_zero_threshold_flags_any_underdelivery(self):
        # Any positive extraction at threshold = 0 should flag.
        theo = _theoretical(self.setup.lp, self.setup.eth, 10.0)
        result = DetectMEV(frontrun_threshold_bps = 0.0).apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.9999,
        )
        self.assertTrue(result.likely_frontrun)


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVValidation(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_zero_amount_in_raises(self):
        with self.assertRaises(ValueError) as ctx:
            DetectMEV().apply(
                self.setup.lp, self.setup.eth, 0.0, 100.0,
            )
        self.assertIn("amount_in", str(ctx.exception))

    def test_negative_amount_in_raises(self):
        with self.assertRaises(ValueError):
            DetectMEV().apply(
                self.setup.lp, self.setup.eth, -5.0, 100.0,
            )

    def test_negative_actual_output_raises(self):
        with self.assertRaises(ValueError) as ctx:
            DetectMEV().apply(
                self.setup.lp, self.setup.eth, 10.0, -1.0,
            )
        self.assertIn("actual_output", str(ctx.exception))

    def test_zero_actual_output_permitted(self):
        # Zero actual output is unusual but not invalid — describes
        # a fully-extracted or failed-settlement case.
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, 0.0,
        )
        self.assertEqual(result.actual_output, 0.0)
        self.assertEqual(result.direction, "underdelivered")
        self.assertTrue(result.likely_frontrun)
        # extraction_pct should be 1.0 (100% extraction)
        self.assertAlmostEqual(result.extraction_pct, 1.0, places = 6)

    def test_unknown_token_raises(self):
        from uniswappy.erc import ERC20
        btc = ERC20("BTC", "0x77")
        with self.assertRaises(ValueError) as ctx:
            DetectMEV().apply(
                self.setup.lp, btc, 10.0, 100.0,
            )
        self.assertIn("BTC", str(ctx.exception))

    def test_negative_threshold_raises_at_construction(self):
        with self.assertRaises(ValueError) as ctx:
            DetectMEV(frontrun_threshold_bps = -10.0)
        self.assertIn("frontrun_threshold_bps", str(ctx.exception))


# ═══════════════════════════════════════════════════════════════════════════
# V3 smoke suite
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectMEVV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_v3_matches_path(self):
        theo = _theoretical(
            self.setup.lp, self.setup.eth, 10.0,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        self.assertEqual(result.direction, "matches")
        self.assertFalse(result.likely_frontrun)

    def test_v3_underdelivered_flags(self):
        theo = _theoretical(
            self.setup.lp, self.setup.eth, 10.0,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        result = DetectMEV().apply(
            self.setup.lp, self.setup.eth, 10.0, theo * 0.90,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        self.assertEqual(result.direction, "underdelivered")
        self.assertTrue(result.likely_frontrun)


if __name__ == '__main__':
    unittest.main()
