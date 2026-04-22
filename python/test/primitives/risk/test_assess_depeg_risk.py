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

import math
import pytest

from stableswappy.erc import ERC20 as SSERC20
from stableswappy.vault import StableswapVault
from stableswappy.cst.factory import StableswapFactory
from stableswappy.utils.data import StableswapExchangeData
from stableswappy.process.join import Join as SSJoin
from stableswappy.process.swap import Swap as SSSwap

from python.prod.utils.data import DepegRiskAssessment, DepegScenario
from python.prod.primitives.risk import AssessDepegRisk


USER = "user0"


# ─── Stableswap pool builders ────────────────────────────────────────────────

def _build_pool(ampl, n_assets = 2):
    """Build a balanced stableswap pool with the given amplification.

    n_assets: 2 (USDC/DAI) or 3 (USDC/DAI/USDT). All balances 10000
    human units.
    """
    usdc = SSERC20("USDC", "0x01", 6)
    usdc.deposit(USER, 10000)
    dai = SSERC20("DAI", "0x02", 18)
    dai.deposit(USER, 10000)

    vault = StableswapVault()
    vault.add_token(usdc)
    vault.add_token(dai)

    tokens = [usdc, dai]
    if n_assets == 3:
        usdt = SSERC20("USDT", "0x03", 6)
        usdt.deposit(USER, 10000)
        vault.add_token(usdt)
        tokens.append(usdt)

    factory = StableswapFactory("Factory", f"0x{ampl:02x}_{n_assets}")
    exch_data = StableswapExchangeData(
        vault = vault, symbol = "CST", address = f"0x{ampl:02x}{n_assets}",
    )
    lp = factory.deploy(exch_data)
    SSJoin().apply(lp, USER, ampl)

    lp_init_amt = lp.liquidity_providers[USER]
    return (lp, tokens, lp_init_amt)


# ─── Closed-form reference implementation for test oracles ──────────────────

def _reference_il(A, delta, max_iter = 50, tol = 1e-9,
                  epsilon_max = 0.95):
    """Closed-form IL for a 2-asset stableswap at given A, δ.

    Mirrors the derivation in AssessDepegRisk. Returns il_pct if
    reachable, None otherwise. Used as an independent oracle — same
    math, separate implementation in the test file, so a bug in the
    primitive's implementation shows up as a test mismatch.
    """
    epsilon = delta * (A + 1) / (2 - delta)
    for _ in range(max_iter):
        if abs(epsilon) >= epsilon_max:
            return None
        alpha = A * (1 - epsilon**2)**2
        new_eps = delta * (alpha + 1) / (2 - delta)
        if abs(new_eps - epsilon) < tol:
            epsilon = new_eps
            break
        epsilon = new_eps
    if abs(epsilon) >= epsilon_max:
        return None

    u = epsilon**2 / ((4*A + 2) * (1 - epsilon**2))
    S_over_D = 1 + u
    v_lp = S_over_D * (1 - delta * (1 + epsilon) / 2)
    v_hold = 1 - delta / 2
    return (v_lp - v_hold) / v_hold


# ─── N=2 USDC/DAI at A=200 (high amplification) ─────────────────────────────

class TestAssessDepegRiskHighA(unittest.TestCase):
    """High-A (A=200) — small depegs are unreachable, large depegs reachable."""

    def setUp(self):
        self.lp, (self.usdc, self.dai), self.lp_init_amt = _build_pool(200)

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_depeg_risk_assessment(self):
        result = AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdc)
        self.assertIsInstance(result, DepegRiskAssessment)

    def test_report_shape(self):
        result = AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdc)
        self.assertEqual(result.depeg_token, "USDC")
        self.assertEqual(result.protocol_type, "stableswap")
        self.assertEqual(result.n_assets, 2)

    def test_scenarios_per_depeg_level(self):
        result = AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdc)
        self.assertEqual(len(result.scenarios), 5)  # default levels
        for s in result.scenarios:
            self.assertIsInstance(s, DepegScenario)

    def test_scenario_levels_match_input(self):
        levels = [0.03, 0.07, 0.15]
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = levels,
        )
        for i, s in enumerate(result.scenarios):
            self.assertAlmostEqual(s.depeg_pct, levels[i], places = 6)
            self.assertAlmostEqual(s.peg_price, 1.0 - levels[i], places = 6)

    # ─── Reachability at high A ─────────────────────────────────────────────

    def test_small_depegs_unreachable_at_high_A(self):
        # At A=200, δ=0.02 requires ε ≈ 2 (impossible). The primitive
        # should flag these as unreachable (il_pct = None).
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.02],
        )
        self.assertIsNone(result.scenarios[0].il_pct)
        self.assertIsNone(result.scenarios[0].lp_value_at_depeg)
        self.assertIsNone(result.scenarios[0].hold_value_at_depeg)

    def test_v2_comparison_populated_even_when_unreachable(self):
        # V2 has no reachability limit; its IL should still be reported
        # so callers see the benchmark even in the unreachable regime.
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.02],
        )
        self.assertIsNotNone(result.scenarios[0].v2_il_comparison)

    # ─── Current peg deviation ──────────────────────────────────────────────

    def test_fresh_pool_near_peg(self):
        result = AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdc)
        self.assertLess(result.current_peg_deviation, 0.01)

    def test_post_swap_deviation_increases(self):
        SSSwap().apply(self.lp, self.usdc, self.dai, USER, 2000)
        held = self.lp.liquidity_providers[USER]
        result = AssessDepegRisk().apply(self.lp, held, self.usdc)
        self.assertGreater(result.current_peg_deviation, 0.0)

    # ─── V2 comparison plumbing ─────────────────────────────────────────────

    def test_v2_comparison_absent_when_disabled(self):
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, compare_v2 = False,
        )
        for s in result.scenarios:
            self.assertIsNone(s.v2_il_comparison)

    def test_v2_comparison_matches_closed_form(self):
        # V2 IL = 2·sqrt(α)/(1+α) - 1 at α = 1-depeg_pct.
        levels = [0.02, 0.05, 0.10]
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = levels,
        )
        for s, d in zip(result.scenarios, levels):
            expected = 2 * math.sqrt(1 - d) / (1 + (1 - d)) - 1
            self.assertAlmostEqual(s.v2_il_comparison, expected, places = 10)

    # ─── Validation ─────────────────────────────────────────────────────────

    def test_raises_on_v2_lp(self):
        from uniswappy.erc import ERC20
        from uniswappy.cpt.factory import UniswapFactory
        from uniswappy.utils.data import UniswapExchangeData

        eth = ERC20("ETH", "0x09")
        dai2 = ERC20("DAI", "0x111")
        factory = UniswapFactory("V2 factory", "0x9")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai2, symbol = "LP", address = "0x099",
        )
        v2_lp = factory.deploy(exch_data)
        v2_lp.add_liquidity(USER, 1000.0, 100000.0, 1000.0, 100000.0)

        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(v2_lp, 100.0, self.usdc)

    def test_raises_on_unknown_token(self):
        stray = SSERC20("STRAY", "0xff", 18)
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(self.lp, self.lp_init_amt, stray)

    def test_raises_on_zero_lp_init_amt(self):
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(self.lp, 0.0, self.usdc)

    def test_raises_on_negative_lp_init_amt(self):
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(self.lp, -1.0, self.usdc)

    def test_raises_on_zero_depeg_level(self):
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(
                self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.0],
            )

    def test_raises_on_out_of_range_depeg_level(self):
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(
                self.lp, self.lp_init_amt, self.usdc, depeg_levels = [1.5],
            )

    # ─── Twin safety ────────────────────────────────────────────────────────

    def test_original_pool_unchanged_after_apply(self):
        before = list(self.lp.math_pool.balances)
        AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdc)
        after = list(self.lp.math_pool.balances)
        self.assertEqual(before, after)


# ─── N=2 USDC/DAI at A=10 (low amplification) ───────────────────────────────

class TestAssessDepegRiskLowA(unittest.TestCase):
    """Low-A (A=10) — small-to-moderate depegs are reachable with
    closed-form computable IL values."""

    def setUp(self):
        self.lp, (self.usdc, self.dai), self.lp_init_amt = _build_pool(10)

    # ─── IL matches independent closed-form reference ──────────────────────

    def test_il_matches_reference_at_small_depeg(self):
        # At A=10, δ=0.05, the hand-computed IL is ~-0.48%. The
        # primitive and the test-file reference impl should agree
        # tightly — they encode the same derivation in different code.
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.05],
        )
        s = result.scenarios[0]
        ref = _reference_il(A = 10, delta = 0.05)
        self.assertIsNotNone(s.il_pct)
        self.assertIsNotNone(ref)
        self.assertAlmostEqual(s.il_pct, ref, places = 8)

    def test_il_matches_reference_across_range(self):
        # Spot-check the reachable band across the default depeg levels.
        levels = [0.02, 0.05, 0.10]
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = levels,
        )
        for s, d in zip(result.scenarios, levels):
            ref = _reference_il(A = 10, delta = d)
            if ref is None:
                self.assertIsNone(s.il_pct)
            else:
                self.assertIsNotNone(s.il_pct)
                self.assertAlmostEqual(s.il_pct, ref, places = 8)

    # ─── Physical properties ────────────────────────────────────────────────

    def test_il_is_non_positive_on_reachable(self):
        levels = [0.01, 0.02, 0.03, 0.05]
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = levels,
        )
        for s in result.scenarios:
            if s.il_pct is not None:
                self.assertLessEqual(s.il_pct, 1e-12)  # non-positive

    def test_il_grows_with_depeg_magnitude(self):
        # On the reachable band, |IL| should be monotonically
        # increasing in δ.
        levels = [0.01, 0.02, 0.03, 0.05]
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = levels,
        )
        reachable = [s for s in result.scenarios if s.il_pct is not None]
        for i in range(1, len(reachable)):
            self.assertGreaterEqual(
                abs(reachable[i].il_pct), abs(reachable[i-1].il_pct),
            )

    def test_il_quadratic_scaling_near_peg(self):
        # For small δ, IL scales ≈ δ². IL(2δ)/IL(δ) ≈ 4.
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.01, 0.02],
        )
        s1, s2 = result.scenarios
        ratio = s2.il_pct / s1.il_pct
        # Tight tolerance — the leading-order expansion gives exactly
        # δ² scaling, modulo small higher-order corrections.
        self.assertAlmostEqual(ratio, 4.0, delta = 0.15)

    # ─── Strong negative convexity (the real stableswap story) ──────────────

    def test_stableswap_exceeds_v2_at_small_depeg(self):
        # Counterintuitive but mathematically correct: at any finite
        # A > 0, stableswap has LARGER |IL| than V2 at the same δ.
        # The flat curve forces arbitrageurs to drain the pool more
        # to achieve a given price deviation, so LPs eat more of the
        # compositional shift.
        result = AssessDepegRisk().apply(
            self.lp, self.lp_init_amt, self.usdc, depeg_levels = [0.05],
        )
        s = result.scenarios[0]
        self.assertGreater(abs(s.il_pct), abs(s.v2_il_comparison))


# ─── N=3 rejection ──────────────────────────────────────────────────────────

class TestAssessDepegRiskN3(unittest.TestCase):

    def setUp(self):
        self.lp, (self.usdc, self.dai, self.usdt), self.lp_init_amt = \
            _build_pool(200, n_assets = 3)

    def test_n3_raises(self):
        # v1 supports N=2 only. N>2 is a future extension.
        with self.assertRaises(ValueError):
            AssessDepegRisk().apply(self.lp, self.lp_init_amt, self.usdt)


if __name__ == '__main__':
    unittest.main()
