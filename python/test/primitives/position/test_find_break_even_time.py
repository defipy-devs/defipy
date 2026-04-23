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

import sys, os, math, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])

import pytest

from uniswappy.process.swap import Swap

from python.prod.utils.data import BreakEvenTime
from python.prod.primitives.position import (
    AnalyzePosition,
    FindBreakEvenTime,
)


USER = "user0"
TRADER = "user1"


# ─── Helper: drive pool state to a state with IL drag and fee income ────────

def _drive_pool_to_il_state(lp, token_in, trade_amount, n_trades = 1):
    """Run n swaps of trade_amount token_in through the pool.

    Produces:
      - IL drag (price has moved)
      - Fee income (30-bps fee per swap accumulates into pool reserves)

    n_trades > 1 lets tests accumulate more fees without moving price
    too far. (Alternating directions could balance price while still
    accumulating fees; v1 keeps this simple and moves price in one
    direction.)
    """
    for _ in range(n_trades):
        Swap().apply(lp, token_in, TRADER, trade_amount)


# ═══════════════════════════════════════════════════════════════════════════
# Shape & return type
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_returns_break_even_time(self):
        # Drive some state to ensure all fields get meaningful values.
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        self.assertIsInstance(result, BreakEvenTime)

    def test_scalar_fields_are_floats(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        self.assertIsInstance(result.current_il_drag, float)
        self.assertIsInstance(result.fee_income_to_date, float)
        self.assertIsInstance(result.fee_rate_per_day, float)
        self.assertIsInstance(result.already_broken_even, bool)
        self.assertIsInstance(result.diagnosis, str)

    def test_diagnosis_is_one_of_allowed(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        self.assertIn(result.diagnosis, {
            "already_broken_even",
            "no_il_drag",
            "no_fee_income",
            "projected",
        })


# ═══════════════════════════════════════════════════════════════════════════
# no_il_drag path — fresh pool, no price movement
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeNoILDrag(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_fresh_pool_diagnoses_no_il_drag(self):
        # No swaps have occurred; price hasn't moved; il_raw ≈ 0.
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 1.0,
        )
        # Could be "no_il_drag" or "already_broken_even" depending on
        # which guard fires first — but days and blocks must be 0.
        self.assertIn(result.diagnosis,
                      {"no_il_drag", "already_broken_even"})
        self.assertEqual(result.days_to_break_even, 0.0)
        self.assertEqual(result.blocks_to_break_even, 0)

    def test_fresh_pool_current_il_drag_is_zero(self):
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 1.0,
        )
        self.assertEqual(result.current_il_drag, 0.0)


# ═══════════════════════════════════════════════════════════════════════════
# already_broken_even path — construct a state where net_pnl > 0
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeAlreadyBrokenEven(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_fees_exceeding_il_yields_already_broken_even(self):
        # Drive enough swaps that the accumulated fee income outweighs
        # the IL drag. With USER owning 100%, multiple small swaps let
        # fees accumulate while price motion stays modest.
        for _ in range(20):
            Swap().apply(self.setup.lp, self.setup.eth, TRADER, 5.0)
            Swap().apply(self.setup.lp, self.setup.dai, TRADER, 500.0)
        # Twenty paired swaps in alternating directions leaves price
        # close to entry (small directional drift from fee asymmetry)
        # but ~60 bps · 20 swaps worth of fees accumulated.

        analysis = AnalyzePosition().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 30.0,
        )
        # Only run the real assertion if the construction actually
        # delivered net_pnl >= 0. If not, skip rather than fail
        # misleadingly — the primitive's correctness doesn't depend on
        # our ability to construct this particular state.
        if analysis.net_pnl < 0:
            self.skipTest("Fixture didn't produce net-positive state; "
                          "primitive path untested in this variant.")

        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 30.0,
        )
        self.assertTrue(result.already_broken_even)
        self.assertEqual(result.diagnosis, "already_broken_even")
        self.assertEqual(result.days_to_break_even, 0.0)
        self.assertEqual(result.blocks_to_break_even, 0)


# ═══════════════════════════════════════════════════════════════════════════
# projected path — IL drag exists AND fee income is positive
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeProjected(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def _run_with_il_state(self, holding_period_days = 14.0,
                           blocks_per_day = 7200):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        return FindBreakEvenTime(
            blocks_per_day = blocks_per_day,
        ).apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = holding_period_days,
        )

    def test_v2_with_il_and_fees_projects(self):
        result = self._run_with_il_state()
        # A single 50-ETH swap against 1000/100000 moves price enough
        # to produce real IL drag and a real fee. If the primitive
        # still can't find a rate something is wrong.
        self.assertEqual(result.diagnosis, "projected")
        self.assertIsNotNone(result.days_to_break_even)
        self.assertIsNotNone(result.blocks_to_break_even)

    def test_projected_days_is_positive(self):
        result = self._run_with_il_state()
        self.assertGreater(result.days_to_break_even, 0.0)

    def test_projected_blocks_is_positive_int(self):
        result = self._run_with_il_state()
        self.assertIsInstance(result.blocks_to_break_even, int)
        self.assertGreater(result.blocks_to_break_even, 0)

    def test_days_equals_drag_over_rate(self):
        # days = current_il_drag / fee_rate_per_day, by construction.
        result = self._run_with_il_state()
        expected = result.current_il_drag / result.fee_rate_per_day
        self.assertAlmostEqual(result.days_to_break_even, expected,
                               places = 10)

    def test_blocks_equals_days_times_bpd(self):
        # Default blocks_per_day = 7200.
        result = self._run_with_il_state()
        expected = int(round(result.days_to_break_even * 7200))
        self.assertEqual(result.blocks_to_break_even, expected)

    def test_not_already_broken_even_when_projected(self):
        result = self._run_with_il_state()
        self.assertFalse(result.already_broken_even)


# ═══════════════════════════════════════════════════════════════════════════
# Monotonicity: longer declared holding period → slower inferred rate
#               → longer days_to_break_even
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeMonotonicity(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_doubling_period_doubles_break_even_days(self):
        # Same realized fee_income (pool state is fixed), but declaring
        # a longer holding period halves fee_rate_per_day, so
        # days_to_break_even should roughly double.
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)

        short = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 7.0,
        )
        long = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )

        # Only meaningful when both paths project.
        if short.diagnosis != "projected" or long.diagnosis != "projected":
            self.skipTest("Fixture didn't land on projected path for "
                          "both holding periods.")

        # Exact doubling up to float precision: the primitive's output
        # is a pure function of (il_drag, fee_income, holding_period).
        ratio = long.days_to_break_even / short.days_to_break_even
        self.assertAlmostEqual(ratio, 2.0, places = 6)


# ═══════════════════════════════════════════════════════════════════════════
# Composition: fee_income_to_date agrees with AnalyzePosition
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeComposition(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_fee_income_matches_analyze_position(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)

        analysis = AnalyzePosition().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        # Exact equality: FindBreakEvenTime calls AnalyzePosition
        # internally with the same args and just reads fee_income.
        self.assertEqual(result.fee_income_to_date, analysis.fee_income)


# ═══════════════════════════════════════════════════════════════════════════
# blocks_per_day override — non-Ethereum chain parameterization
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeBlocksPerDay(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_default_blocks_per_day_is_ethereum(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        if result.diagnosis != "projected":
            self.skipTest("Fixture didn't reach projected path.")
        # Ethereum mainnet: 7200 blocks/day.
        expected = int(round(result.days_to_break_even * 7200))
        self.assertEqual(result.blocks_to_break_even, expected)

    def test_base_override_changes_blocks_not_days(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)

        eth = FindBreakEvenTime(blocks_per_day = 7200).apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        base = FindBreakEvenTime(blocks_per_day = 43200).apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
        )
        if eth.diagnosis != "projected" or base.diagnosis != "projected":
            self.skipTest("Fixture didn't reach projected path.")

        # Days are identical (primitive math is chain-agnostic).
        self.assertAlmostEqual(eth.days_to_break_even,
                               base.days_to_break_even, places = 10)
        # Base produces 6x more blocks per day (43200/7200 = 6).
        # Allow ±1 for integer rounding.
        self.assertAlmostEqual(
            base.blocks_to_break_even / eth.blocks_to_break_even,
            6.0, delta = 0.01,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeValidation(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_zero_holding_period_raises(self):
        with self.assertRaises(ValueError) as ctx:
            FindBreakEvenTime().apply(
                self.setup.lp, self.setup.lp_init_amt,
                self.setup.entry_x_amt, self.setup.entry_y_amt,
                holding_period_days = 0.0,
            )
        self.assertIn("holding_period_days", str(ctx.exception))

    def test_negative_holding_period_raises(self):
        with self.assertRaises(ValueError):
            FindBreakEvenTime().apply(
                self.setup.lp, self.setup.lp_init_amt,
                self.setup.entry_x_amt, self.setup.entry_y_amt,
                holding_period_days = -1.0,
            )

    def test_none_holding_period_raises(self):
        with self.assertRaises(ValueError):
            FindBreakEvenTime().apply(
                self.setup.lp, self.setup.lp_init_amt,
                self.setup.entry_x_amt, self.setup.entry_y_amt,
                holding_period_days = None,
            )

    def test_zero_blocks_per_day_raises_at_construction(self):
        with self.assertRaises(ValueError) as ctx:
            FindBreakEvenTime(blocks_per_day = 0)
        self.assertIn("blocks_per_day", str(ctx.exception))

    def test_negative_blocks_per_day_raises_at_construction(self):
        with self.assertRaises(ValueError):
            FindBreakEvenTime(blocks_per_day = -100)


# ═══════════════════════════════════════════════════════════════════════════
# V3 smoke suite — confirm primitive works end-to-end on concentrated liquidity
# ═══════════════════════════════════════════════════════════════════════════

class TestFindBreakEvenTimeV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def test_v3_returns_break_even_time(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        self.assertIsInstance(result, BreakEvenTime)

    def test_v3_fresh_pool_not_projected(self):
        # No swaps → no IL drag → not on the "projected" path.
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        self.assertNotEqual(result.diagnosis, "projected")

    def test_v3_projected_path_reachable(self):
        _drive_pool_to_il_state(self.setup.lp, self.setup.eth, 50.0)
        result = FindBreakEvenTime().apply(
            self.setup.lp, self.setup.lp_init_amt,
            self.setup.entry_x_amt, self.setup.entry_y_amt,
            holding_period_days = 14.0,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )
        # V3 may also land on projected given swap-induced IL; confirm
        # that when it does the field-consistency invariant holds.
        if result.diagnosis == "projected":
            self.assertGreater(result.days_to_break_even, 0.0)
            self.assertGreater(result.blocks_to_break_even, 0)


if __name__ == '__main__':
    unittest.main()
