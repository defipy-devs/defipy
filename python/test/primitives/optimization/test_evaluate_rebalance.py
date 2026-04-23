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

from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import UniV3Utils
from uniswappy.process.join import Join
from uniswappy.process.liquidity import RemoveLiquidity
from uniswappy.process.swap import Swap
from uniswappy.process.deposit import SwapDeposit

from python.prod.utils.data import RebalanceCostReport
from python.prod.primitives.optimization import EvaluateRebalance


USER = "user0"
USER2 = "user1"


# ─── Helper: build a two-LP V2 pool so USER can cycle while USER2 stays ─────

def _build_two_lp_v2_pool(
    address_suffix,
    user_eth = 500.0, user_dai = 50_000.0,
    user2_eth = 500.0, user2_dai = 50_000.0,
):
    """Deploy a fresh V2 ETH/DAI pool with two LPs present.

    Default: 1000 ETH / 100000 DAI total, USER owns 50%, USER2 owns 50%.
    Leaves residual liquidity to swap against even when USER withdraws
    their full position.
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
    lp.add_liquidity(USER, user_eth, user_dai, user_eth, user_dai)
    lp.add_liquidity(USER2, user2_eth, user2_dai, user2_eth, user2_dai)

    user_lp_amt = lp.convert_to_human(lp.liquidity_providers[USER])
    return lp, eth, dai, user_lp_amt


# ─── Shape & return type ─────────────────────────────────────────────────────

class TestEvaluateRebalanceShape(unittest.TestCase):

    def _result(self):
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("s1")
        return EvaluateRebalance().apply(lp, dai, user_lp_amt)

    def test_returns_rebalance_cost_report(self):
        result = self._result()
        self.assertIsInstance(result, RebalanceCostReport)

    def test_token_out_name_echoed(self):
        result = self._result()
        self.assertEqual(result.token_out_name, "DAI")

    def test_all_numeric_fields_finite(self):
        # Defensive: catch NaN/inf leakage from any of the division
        # or sqrt operations.
        result = self._result()
        for field in (
            "position_size_lp", "current_value",
            "withdrawal_direct_out", "withdrawal_swap_amount_in",
            "withdrawal_swap_amount_out", "withdrawal_total_out",
            "withdrawal_slippage_cost", "withdrawal_slippage_pct",
            "redeposit_swap_amount_in", "redeposit_swap_amount_out",
            "redeposit_slippage_cost", "redeposit_slippage_pct",
            "expected_lp_tokens_after",
            "total_slippage_cost", "total_slippage_pct", "lp_delta",
        ):
            val = getattr(result, field)
            self.assertTrue(math.isfinite(val),
                            "{} is not finite: {}".format(field, val))

    def test_current_value_positive(self):
        result = self._result()
        self.assertGreater(result.current_value, 0.0)

    def test_position_size_echoed(self):
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("s2")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertAlmostEqual(result.position_size_lp, user_lp_amt,
                               places = 6)


# ─── Pro-rata withdrawal correctness ─────────────────────────────────────────

class TestEvaluateRebalanceWithdrawal(unittest.TestCase):

    def test_direct_out_matches_pro_rata_share(self):
        # USER owns 500/1000 ETH = 50% share. withdrawal_direct_out
        # on the DAI side should be 50% of the DAI reserve = 50000.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("w1")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertAlmostEqual(result.withdrawal_direct_out, 50_000.0,
                               places = 2)

    def test_swap_amount_in_matches_pro_rata_share(self):
        # 50% of the ETH reserve = 500.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("w2")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertAlmostEqual(result.withdrawal_swap_amount_in, 500.0,
                               places = 2)

    def test_withdrawal_total_out_sums_legs(self):
        # withdrawal_total_out should exactly equal direct_out + swap_amount_out.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("w3")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertAlmostEqual(
            result.withdrawal_total_out,
            result.withdrawal_direct_out + result.withdrawal_swap_amount_out,
            places = 6,
        )


# ─── Slippage makes sense ────────────────────────────────────────────────────

class TestEvaluateRebalanceSlippage(unittest.TestCase):

    def test_withdrawal_slippage_nonnegative(self):
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("sl1")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertGreaterEqual(result.withdrawal_slippage_cost, 0.0)
        self.assertGreaterEqual(result.withdrawal_slippage_pct, 0.0)

    def test_redeposit_slippage_nonnegative(self):
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("sl2")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertGreaterEqual(result.redeposit_slippage_cost, 0.0)
        self.assertGreaterEqual(result.redeposit_slippage_pct, 0.0)

    def test_total_slippage_sums_legs_in_token_out_units(self):
        # total_slippage_cost = withdrawal_slippage_cost (in token_out)
        #                     + redeposit_slippage_cost * spot_post_withdraw
        # The last part converts the redeposit slippage from token_in
        # units (ETH, the swap output side) to token_out units (DAI).
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("sl3")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        # At the post-withdrawal 50% state, pool is 500/50000 → spot
        # price DAI per ETH = 100. Redeposit slippage is in ETH units;
        # multiply by 100 to get DAI.
        expected_total = (
            result.withdrawal_slippage_cost
            + result.redeposit_slippage_cost * 100.0
        )
        self.assertAlmostEqual(result.total_slippage_cost, expected_total,
                               places = 2)

    def test_slippage_pct_small_for_small_position(self):
        # ~1% ownership. After USER withdraws their pro-rata share,
        # the withdrawal-swap leg sends ~10 ETH into a ~1000-ETH pool
        # — about a 1%-of-reserve swap, with ~1% price impact. Two
        # such legs plus two 30-bps fees put total_slippage_pct well
        # under 2%. This is the regime where "small position = cheap
        # to cycle" carries real meaning; neighboring tests cover the
        # growth of slippage at larger shares.
        lp, _, dai, _ = _build_two_lp_v2_pool(
            "sl4", user_eth = 10.0, user_dai = 1_000.0,
            user2_eth = 1000.0, user2_dai = 100_000.0,
        )
        user_lp_amt = lp.convert_to_human(lp.liquidity_providers[USER])
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertLess(result.total_slippage_pct, 0.02)

    def test_slippage_pct_grows_with_position_size(self):
        # Same USER2 baseline, vary USER's share. Larger USER share
        # means larger swap-as-fraction-of-remaining-pool in both
        # legs, so slippage_pct should grow monotonically.
        sizes = [
            (50.0, 5000.0),      # 5%
            (200.0, 20_000.0),   # 17%
            (500.0, 50_000.0),   # 33%
        ]
        pcts = []
        for idx, (user_eth, user_dai) in enumerate(sizes):
            lp, _, dai, user_lp_amt = _build_two_lp_v2_pool(
                "sg{}".format(idx),
                user_eth = user_eth, user_dai = user_dai,
                user2_eth = 1000.0, user2_dai = 100_000.0,
            )
            result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
            pcts.append(result.total_slippage_pct)
        for i in range(1, len(pcts)):
            self.assertGreater(pcts[i], pcts[i - 1])


# ─── LP delta and expected tokens ────────────────────────────────────────────

class TestEvaluateRebalanceLPDelta(unittest.TestCase):

    def test_lp_delta_negative(self):
        # Any cycle destroys LP tokens because both swap legs charge
        # a 30-bps fee that doesn't come back.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("lpd1")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertLess(result.lp_delta, 0.0)

    def test_expected_lp_tokens_positive(self):
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("lpd2")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertGreater(result.expected_lp_tokens_after, 0.0)

    def test_expected_lp_tokens_smaller_than_original(self):
        # lp_delta < 0 means expected_lp_tokens_after < position_size_lp.
        # Direct check.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("lpd3")
        result = EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertLess(result.expected_lp_tokens_after,
                        result.position_size_lp)


# ─── Consistency cross-check against full execution ─────────────────────────

class TestEvaluateRebalanceConsistency(unittest.TestCase):

    """Run the full cycle on a twin pool and verify the projected
    expected_lp_tokens_after matches the actual LP balance."""

    def test_projected_matches_executed(self):
        # Build two identical two-LP pools.
        lp_p, _, dai_p, user_lp_amt_p = _build_two_lp_v2_pool("cx1")
        lp_e, eth_e, dai_e, user_lp_amt_e = _build_two_lp_v2_pool("cx2")

        # Non-mutating projection.
        projected = EvaluateRebalance().apply(
            lp_p, dai_p, user_lp_amt_p,
        )

        # Executed cycle on the twin pool:
        # Step 1: remove all of USER's liquidity, pro-rata.
        # RemoveLiquidity takes the token amount to pull on the
        # token_in side (DAI for us); it converts to LP amount
        # internally. We want to pull USER's full share, which is
        # the DAI side of their proportional share.
        total_supply = lp_e.get_liquidity()
        share = user_lp_amt_e / total_supply
        dai_to_pull = share * lp_e.get_reserve(dai_e)
        _ = RemoveLiquidity().apply(lp_e, dai_e, USER, dai_to_pull)
        # USER now holds dai_to_pull of DAI and some amount of ETH.

        # Step 2: swap the withdrawn ETH to DAI via the pool.
        # Figure out how much ETH USER got. After step 1 lp_e's ETH
        # reserve should have dropped by USER's share; let's compute
        # what USER received from the token balance tracker.
        # Actually, simpler: the pro-rata ETH share is share * pre-withdraw
        # reserve0. Use that directly for the swap-in amount.
        # Because lp_e's reserves have shifted, pull from the ERC20
        # balance tracker: share * (pre-withdraw reserve0) =
        # share * 1000 = 500 at default fixture.
        user_eth_to_swap = share * 1000.0
        _ = Swap().apply(lp_e, eth_e, USER, user_eth_to_swap)

        # Step 3: re-zap the full DAI balance. The zap runs against
        # the now-shifted pool state and mutates it further; our
        # projection has already accounted for this.
        # We want the total DAI USER has post-withdrawal-and-swap.
        # That's withdrawal_total_out from the projection.
        zap_amt = projected.withdrawal_total_out
        SwapDeposit().apply(lp_e, dai_e, USER, zap_amt)

        # Compare USER's final LP balance against projected.
        user_lp_after_machine = lp_e.liquidity_providers.get(USER, 0)
        user_lp_after = lp_e.convert_to_human(user_lp_after_machine)

        # Integer-math rounding tolerance: 0.5% (looser than
        # OptimalDepositSplit's 0.1% because this cycle has four
        # integer-math passes: remove, swap, swap, mint).
        self.assertAlmostEqual(
            projected.expected_lp_tokens_after, user_lp_after,
            delta = abs(user_lp_after) * 0.005,
        )

    def test_non_mutating(self):
        # Running EvaluateRebalance should NOT touch pool state.
        lp, _, dai, user_lp_amt = _build_two_lp_v2_pool("cx3")
        reserve0_before = lp.reserve0
        reserve1_before = lp.reserve1
        total_supply_before = lp.total_supply
        user_lp_before = lp.liquidity_providers[USER]

        _ = EvaluateRebalance().apply(lp, dai, user_lp_amt)

        self.assertEqual(lp.reserve0, reserve0_before)
        self.assertEqual(lp.reserve1, reserve1_before)
        self.assertEqual(lp.total_supply, total_supply_before)
        self.assertEqual(lp.liquidity_providers[USER], user_lp_before)


# ─── Symmetry: token0-out vs token1-out ─────────────────────────────────────

class TestEvaluateRebalanceSymmetry(unittest.TestCase):

    def test_both_token_directions_valid(self):
        # Exit to ETH (token0) or exit to DAI (token1): both should
        # produce well-formed results with similar total_slippage_pct
        # at the 50/50 split (the math is symmetric under token-swap).
        lp, eth, dai, user_lp_amt = _build_two_lp_v2_pool("sym1")

        # Build a twin for the DAI-out direction since the primitive
        # is non-mutating but we want independent results.
        lp2, eth2, dai2, user_lp_amt2 = _build_two_lp_v2_pool("sym2")

        eth_result = EvaluateRebalance().apply(lp, eth, user_lp_amt)
        dai_result = EvaluateRebalance().apply(lp2, dai2, user_lp_amt2)

        # Total slippage percentages should match within tight tol.
        # (The two cycles are mirror images of each other.)
        self.assertAlmostEqual(
            eth_result.total_slippage_pct,
            dai_result.total_slippage_pct,
            places = 4,
        )

    def test_token_out_name_reflects_input(self):
        lp1, eth1, _, amt1 = _build_two_lp_v2_pool("sym3")
        lp2, _, dai2, amt2 = _build_two_lp_v2_pool("sym4")
        r1 = EvaluateRebalance().apply(lp1, eth1, amt1)
        r2 = EvaluateRebalance().apply(lp2, dai2, amt2)
        self.assertEqual(r1.token_out_name, "ETH")
        self.assertEqual(r2.token_out_name, "DAI")


# ─── Validation ──────────────────────────────────────────────────────────────

class TestEvaluateRebalanceValidation(unittest.TestCase):

    def test_v3_raises(self):
        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("v3 factory", "0xv3")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V3LP",
            address = "0x0v3", version = 'V3',
            tick_spacing = 60, fee = 3000,
        )
        lp_v3 = factory.deploy(exch_data)
        lwr = UniV3Utils.getMinTick(60)
        upr = UniV3Utils.getMaxTick(60)
        Join().apply(lp_v3, USER, 1000.0, 100000.0, lwr, upr)
        user_lp_amt = lp_v3.convert_to_human(
            lp_v3.liquidity_providers[USER]
        )

        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp_v3, dai, user_lp_amt)
        self.assertIn("V3", str(ctx.exception))

    def test_unknown_token_raises(self):
        lp, _, _, user_lp_amt = _build_two_lp_v2_pool("val1")
        btc = ERC20("BTC", "0x77")
        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp, btc, user_lp_amt)
        self.assertIn("BTC", str(ctx.exception))

    def test_zero_position_raises(self):
        lp, _, dai, _ = _build_two_lp_v2_pool("val2")
        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp, dai, 0.0)
        self.assertIn("position_size_lp", str(ctx.exception))

    def test_negative_position_raises(self):
        lp, _, dai, _ = _build_two_lp_v2_pool("val3")
        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp, dai, -5.0)
        self.assertIn("position_size_lp", str(ctx.exception))

    def test_oversized_position_raises(self):
        lp, _, dai, _ = _build_two_lp_v2_pool("val4")
        oversized = lp.get_liquidity() * 2.0
        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp, dai, oversized)
        self.assertIn("exceeds", str(ctx.exception))

    def test_full_pool_ownership_raises(self):
        # Using the v2_setup fixture where USER is sole LP — cycling
        # is undefined because withdrawing 100% leaves nothing to swap.
        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("sole LP factory", "0xsole")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "LPsole",
            address = "0x0sole",
        )
        lp = factory.deploy(exch_data)
        lp.add_liquidity(USER, 1000.0, 100_000.0, 1000.0, 100_000.0)
        user_lp_amt = lp.convert_to_human(lp.liquidity_providers[USER])

        with self.assertRaises(ValueError) as ctx:
            EvaluateRebalance().apply(lp, dai, user_lp_amt)
        self.assertIn("ownership", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
