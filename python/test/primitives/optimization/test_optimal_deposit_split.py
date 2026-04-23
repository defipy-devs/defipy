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
from uniswappy.utils.tools.v3 import UniV3Utils
from uniswappy.process.join import Join
from uniswappy.process.deposit import SwapDeposit

from python.prod.utils.data import DepositSplitResult
from python.prod.primitives.optimization import OptimalDepositSplit


USER = "user0"


# ─── Helper: build an identical V2 pool for consistency cross-checks ─────────

def _build_v2_pool(address_suffix = "cx", eth_amt = 1000.0, dai_amt = 100_000.0):
    """Deploy a fresh V2 ETH/DAI pool at the given reserves.

    Used when a test needs a second pool to run SwapDeposit against
    (mutating) alongside OptimalDepositSplit (non-mutating) on an
    identical starting state. Also used for the sanity-check tests
    that want an ETH-token reference to pass as `token_in`.
    """
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory(
        "factory {}".format(address_suffix), "0x{}".format(address_suffix),
    )
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "LP{}".format(address_suffix),
        address = "0x0{}".format(address_suffix),
    )
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, eth_amt, dai_amt, eth_amt, dai_amt)
    return lp, eth, dai


# ─── Shape & return type ─────────────────────────────────────────────────────

class TestOptimalDepositSplitShape(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def _result(self, amount_in = 10.0, token = None):
        token = token if token is not None else self.setup.eth
        return OptimalDepositSplit().apply(self.setup.lp, token, amount_in)

    def test_returns_deposit_split_result(self):
        result = self._result()
        self.assertIsInstance(result, DepositSplitResult)

    def test_token_in_name_echoed(self):
        result = self._result()
        self.assertEqual(result.token_in_name, "ETH")

    def test_amount_in_echoed(self):
        result = self._result(amount_in = 42.5)
        self.assertEqual(result.amount_in, 42.5)

    def test_optimal_fraction_in_unit_interval(self):
        # α must lie in (0, 1) for any valid input.
        result = self._result()
        self.assertGreater(result.optimal_fraction, 0.0)
        self.assertLess(result.optimal_fraction, 1.0)

    def test_all_numeric_fields_are_finite(self):
        # Defensive: catch any NaN / inf leakage from the math.
        import math
        result = self._result()
        for field in (
            "optimal_fraction", "swap_amount_in", "swap_amount_out",
            "deposit_amount_in", "deposit_amount_out",
            "expected_lp_tokens", "slippage_cost", "slippage_pct",
        ):
            val = getattr(result, field)
            self.assertTrue(math.isfinite(val),
                            "{} is not finite: {}".format(field, val))


# ─── Small-deposit regime: α → 1/(1+f) ≈ 0.50075, slippage → fee ────────────

class TestOptimalDepositSplitSmallDeposit(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        # Fixture has 1000 ETH / 100000 DAI reserves.
        self.setup = v2_setup

    def test_tiny_deposit_alpha_near_fee_limit(self):
        # Solving the V2 zap quadratic in the limit dx → 0 gives
        # α → 1/(1+f) where f = 0.997 is the fee multiplier. That's
        # 0.50075 — NOT 0.5. The 30-bps fee introduces a small upward
        # bias: you swap slightly more than half because a sliver of
        # what you swap goes to LPs as fees. For a 0.01%-of-reserves
        # deposit we expect α within ~1e-5 of this limit.
        fee_frac = 0.997
        alpha_limit = 1.0 / (1.0 + fee_frac)
        result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 0.1,
        )
        self.assertAlmostEqual(result.optimal_fraction, alpha_limit,
                               places = 4)

    def test_tiny_deposit_slippage_near_zero(self):
        # Same small-deposit regime: the swap leg is so small that
        # slippage_pct is dominated by the 30-bps protocol fee itself.
        # The fee produces slippage_pct ≈ 0.003 (the 30 bps). Stay
        # comfortably under 1%.
        result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 0.1,
        )
        self.assertLess(result.slippage_pct, 0.01)


# ─── Large-deposit regime: α shifts BELOW the small-deposit limit ───────────

class TestOptimalDepositSplitLargeDeposit(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_large_deposit_alpha_below_fee_limit(self):
        # As dx grows, α decreases from its dx→0 limit of 1/(1+f).
        # Intuition: a larger swap moves the price more, so each unit
        # swapped buys less of the opposing token — you need to swap
        # LESS of your input (not more) to match what's left against
        # the purchased amount. Implicit differentiation of the V2
        # zap quadratic confirms dα/d(dx) < 0 identically.
        #
        # For 200 ETH into a 1000 ETH pool (20% of reserves), α drops
        # materially below the 0.50075 limit. Use 0.5 as a simple
        # upper bound that's well above the expected value (≈ 0.478).
        result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 200.0,
        )
        self.assertLess(result.optimal_fraction, 0.5)

    def test_alpha_monotone_decreasing_in_amount_in(self):
        # Direct check of the dα/d(dx) < 0 property: a series of
        # increasing deposits should produce a strictly decreasing
        # series of α values.
        amounts = [0.1, 10.0, 50.0, 200.0]
        alphas = []
        for amt in amounts:
            result = OptimalDepositSplit().apply(
                self.setup.lp, self.setup.eth, amt,
            )
            alphas.append(result.optimal_fraction)
        for i in range(1, len(alphas)):
            self.assertLess(alphas[i], alphas[i - 1])

    def test_large_deposit_conserves_amount_in(self):
        # swap_amount_in + deposit_amount_in should equal amount_in
        # exactly — the α split is a partition of amount_in.
        amount_in = 200.0
        result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, amount_in,
        )
        total = result.swap_amount_in + result.deposit_amount_in
        self.assertAlmostEqual(total, amount_in, places = 8)

    def test_large_deposit_slippage_materially_larger(self):
        # The large-deposit case should have meaningfully more slippage
        # than the small-deposit case.
        small = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 0.1,
        )
        large = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 200.0,
        )
        self.assertGreater(large.slippage_pct, small.slippage_pct)


# ─── Monotonicity: bigger deposits cost more slippage ───────────────────────

class TestOptimalDepositSplitMonotonicity(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_slippage_cost_monotone_in_amount_in(self):
        # Across a series of growing deposits, slippage_cost should
        # grow strictly.
        amounts = [1.0, 10.0, 50.0, 200.0]
        costs = []
        for amt in amounts:
            result = OptimalDepositSplit().apply(
                self.setup.lp, self.setup.eth, amt,
            )
            costs.append(result.slippage_cost)
        for i in range(1, len(costs)):
            self.assertGreater(costs[i], costs[i - 1])

    def test_slippage_pct_monotone_in_amount_in(self):
        # Same for slippage_pct — bigger relative size means bigger
        # relative friction.
        amounts = [1.0, 10.0, 50.0, 200.0]
        pcts = []
        for amt in amounts:
            result = OptimalDepositSplit().apply(
                self.setup.lp, self.setup.eth, amt,
            )
            pcts.append(result.slippage_pct)
        for i in range(1, len(pcts)):
            self.assertGreater(pcts[i], pcts[i - 1])


# ─── LP tokens and positivity ───────────────────────────────────────────────

class TestOptimalDepositSplitLPTokens(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_expected_lp_tokens_positive(self):
        result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 10.0,
        )
        self.assertGreater(result.expected_lp_tokens, 0.0)

    def test_larger_deposit_yields_more_lp_tokens(self):
        # LP tokens minted should scale with deposit size (at fixed
        # pool state).
        small = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 1.0,
        )
        large = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 100.0,
        )
        self.assertGreater(large.expected_lp_tokens,
                           small.expected_lp_tokens)


# ─── Consistency with SwapDeposit execution ─────────────────────────────────

class TestOptimalDepositSplitConsistency(unittest.TestCase):

    """The critical cross-check: OptimalDepositSplit's projection must
    match what SwapDeposit would actually mint if executed."""

    def test_projected_lp_matches_executed_lp(self):
        # Build two identical pools.
        lp_project, eth_p, dai_p = _build_v2_pool(address_suffix = "p1")
        lp_execute, eth_e, dai_e = _build_v2_pool(address_suffix = "p2")

        amount_in = 25.0

        # Snapshot LP balance before execution.
        lp_balance_before = lp_execute.liquidity_providers[USER]

        # Non-mutating projection.
        projected = OptimalDepositSplit().apply(
            lp_project, eth_p, amount_in,
        )

        # Mutating execution on the twin pool.
        SwapDeposit().apply(lp_execute, eth_e, USER, amount_in)

        # Actual LP balance change.
        lp_balance_after = lp_execute.liquidity_providers[USER]
        actual_minted_machine = lp_balance_after - lp_balance_before
        actual_minted = lp_execute.convert_to_human(actual_minted_machine)

        # Compare projected vs. actual. Tolerance ~0.1% for V2's
        # integer-math rounding.
        self.assertAlmostEqual(
            projected.expected_lp_tokens, actual_minted,
            delta = abs(actual_minted) * 0.001,
        )

    def test_non_mutating_on_projection_side(self):
        # Running OptimalDepositSplit should NOT change pool state.
        lp, eth, _ = _build_v2_pool(address_suffix = "nm")

        reserve0_before = lp.reserve0
        reserve1_before = lp.reserve1
        total_supply_before = lp.total_supply
        user_lp_before = lp.liquidity_providers.get(USER, 0)

        _ = OptimalDepositSplit().apply(lp, eth, 50.0)

        self.assertEqual(lp.reserve0, reserve0_before)
        self.assertEqual(lp.reserve1, reserve1_before)
        self.assertEqual(lp.total_supply, total_supply_before)
        self.assertEqual(
            lp.liquidity_providers.get(USER, 0), user_lp_before,
        )


# ─── Symmetry: token0-in vs token1-in produce consistent results ────────────

class TestOptimalDepositSplitSymmetry(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_token0_in_and_token1_in_both_valid(self):
        # Depositing 10 ETH vs. depositing 1000 DAI (same spot-equivalent)
        # should each produce a well-formed result with α near 0.5
        # (small deposit relative to 1000-ETH/100000-DAI reserves).
        result_eth = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 10.0,
        )
        result_dai = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.dai, 1000.0,
        )
        # Both α values should be in (0, 1), close to 0.5 (small relative
        # deposit).
        for r in (result_eth, result_dai):
            self.assertGreater(r.optimal_fraction, 0.4)
            self.assertLess(r.optimal_fraction, 0.6)

    def test_token_in_name_reflects_input_side(self):
        eth_result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.eth, 10.0,
        )
        dai_result = OptimalDepositSplit().apply(
            self.setup.lp, self.setup.dai, 1000.0,
        )
        self.assertEqual(eth_result.token_in_name, "ETH")
        self.assertEqual(dai_result.token_in_name, "DAI")


# ─── Validation ──────────────────────────────────────────────────────────────

class TestOptimalDepositSplitValidation(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def test_v3_raises(self):
        # Build a V3 pool inline (v3_setup fixture would also work
        # but we inline here to avoid mixed-fixture binding).
        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("v3 factory", "0x99")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V3LP",
            address = "0x099", version = 'V3',
            tick_spacing = 60, fee = 3000,
        )
        lp_v3 = factory.deploy(exch_data)
        lwr = UniV3Utils.getMinTick(60)
        upr = UniV3Utils.getMaxTick(60)
        Join().apply(lp_v3, USER, 1000.0, 100000.0, lwr, upr)

        with self.assertRaises(ValueError) as ctx:
            OptimalDepositSplit().apply(lp_v3, eth, 10.0)
        msg = str(ctx.exception)
        self.assertIn("V3", msg)

    def test_unknown_token_raises(self):
        # An ERC20 that isn't in the pool should raise with a clear
        # message listing the pool's tokens.
        btc = ERC20("BTC", "0x77")
        with self.assertRaises(ValueError) as ctx:
            OptimalDepositSplit().apply(self.setup.lp, btc, 10.0)
        self.assertIn("BTC", str(ctx.exception))

    def test_zero_amount_in_raises(self):
        with self.assertRaises(ValueError) as ctx:
            OptimalDepositSplit().apply(
                self.setup.lp, self.setup.eth, 0.0,
            )
        self.assertIn("amount_in", str(ctx.exception))

    def test_negative_amount_in_raises(self):
        with self.assertRaises(ValueError) as ctx:
            OptimalDepositSplit().apply(
                self.setup.lp, self.setup.eth, -5.0,
            )
        self.assertIn("amount_in", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
