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
from uniswappy.process.swap import Swap

from python.prod.utils.data import (
    FeeTierCandidate,
    FeeTierMetrics,
    FeeTierComparison,
)
from python.prod.primitives.comparison import CompareFeeTiers


USER = "user0"
V3_TICK_SPACING = 60


# ─── Helpers for building V3 pools at arbitrary fee tiers inline ─────────────

def _build_v3_pool_at_fee(
    fee_pips,
    address_suffix,
    eth_amt = 1000.0,
    dai_amt = 100000.0,
):
    """Deploy a fresh V3 ETH/DAI pool at the specified fee tier.

    fee_pips is the Uniswap V3 fee in pips (100 = 0.01%, 500 = 0.05%,
    3000 = 0.3%, 10000 = 1%). Returns (lp, eth, dai, lp_init_amt,
    lwr_tick, upr_tick).
    """
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory(
        "ETH pool factory {}".format(address_suffix),
        "0x{}".format(address_suffix),
    )
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "LP{}".format(address_suffix),
        address = "0x0{}".format(address_suffix),
        version = 'V3', tick_spacing = V3_TICK_SPACING, fee = fee_pips,
    )
    lp = factory.deploy(exch_data)

    lwr_tick = UniV3Utils.getMinTick(V3_TICK_SPACING)
    upr_tick = UniV3Utils.getMaxTick(V3_TICK_SPACING)

    Join().apply(lp, USER, eth_amt, dai_amt, lwr_tick, upr_tick)

    lp_init_amt = lp.convert_to_human(lp.liquidity_providers[USER])

    return lp, eth, dai, lp_init_amt, lwr_tick, upr_tick


def _build_mismatched_pair_pool(fee_pips, address_suffix):
    """Deploy a V3 pool with token1 = USDC instead of DAI (for mixed-pair test)."""
    eth = ERC20("ETH", "0x09")
    usdc = ERC20("USDC", "0x222")
    factory = UniswapFactory(
        "ETH-USDC factory {}".format(address_suffix),
        "0x{}".format(address_suffix),
    )
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = usdc, symbol = "LPU",
        address = "0x0{}".format(address_suffix),
        version = 'V3', tick_spacing = V3_TICK_SPACING, fee = fee_pips,
    )
    lp = factory.deploy(exch_data)
    lwr_tick = UniV3Utils.getMinTick(V3_TICK_SPACING)
    upr_tick = UniV3Utils.getMaxTick(V3_TICK_SPACING)
    Join().apply(lp, USER, 500.0, 1_000_000.0, lwr_tick, upr_tick)
    lp_init_amt = lp.convert_to_human(lp.liquidity_providers[USER])
    return lp, eth, usdc, lp_init_amt, lwr_tick, upr_tick


def _candidate(lp, lp_init_amt, lwr, upr, name = None):
    return FeeTierCandidate(
        lp = lp,
        position_size_lp = lp_init_amt,
        lwr_tick = lwr,
        upr_tick = upr,
        name = name,
    )


# ─── Shape & return type ─────────────────────────────────────────────────────

class TestCompareFeeTiersShape(unittest.TestCase):

    def _two_tier_setup(self):
        lp_a, _, _, amt_a, lwr_a, upr_a = _build_v3_pool_at_fee(500, "a1")
        lp_b, _, _, amt_b, lwr_b, upr_b = _build_v3_pool_at_fee(3000, "b1")
        return [
            _candidate(lp_a, amt_a, lwr_a, upr_a),
            _candidate(lp_b, amt_b, lwr_b, upr_b),
        ]

    def test_returns_fee_tier_comparison(self):
        result = CompareFeeTiers().apply(self._two_tier_setup())
        self.assertIsInstance(result, FeeTierComparison)

    def test_tiers_contain_fee_tier_metrics(self):
        result = CompareFeeTiers().apply(self._two_tier_setup())
        self.assertEqual(len(result.tiers), 2)
        for tier in result.tiers:
            self.assertIsInstance(tier, FeeTierMetrics)

    def test_numeraire_is_shared_token0(self):
        result = CompareFeeTiers().apply(self._two_tier_setup())
        self.assertEqual(result.numeraire, "ETH")

    def test_pair_reported_correctly(self):
        result = CompareFeeTiers().apply(self._two_tier_setup())
        self.assertEqual(result.pair, "ETH/DAI")

    def test_default_tier_name_uses_pair_and_bps(self):
        # Default name format: "token0/token1@<bps>bps"
        result = CompareFeeTiers().apply(self._two_tier_setup())
        names = [t.name for t in result.tiers]
        self.assertIn("ETH/DAI@5bps", names)
        self.assertIn("ETH/DAI@30bps", names)

    def test_custom_tier_name_respected(self):
        lp_a, _, _, amt_a, lwr_a, upr_a = _build_v3_pool_at_fee(500, "c1")
        lp_b, _, _, amt_b, lwr_b, upr_b = _build_v3_pool_at_fee(3000, "c2")
        result = CompareFeeTiers().apply([
            _candidate(lp_a, amt_a, lwr_a, upr_a, name = "Lowest"),
            _candidate(lp_b, amt_b, lwr_b, upr_b, name = "Standard"),
        ])
        names = [t.name for t in result.tiers]
        self.assertEqual(names, ["Lowest", "Standard"])


# ─── Fee-tier extraction ─────────────────────────────────────────────────────

class TestCompareFeeTiersFeeExtraction(unittest.TestCase):

    def test_all_four_canonical_tiers_report_correct_bps(self):
        # Uniswap V3 canonical tiers: 100/500/3000/10000 pips →
        # 1/5/30/100 bps respectively.
        lp1, _, _, amt1, l1, u1 = _build_v3_pool_at_fee(100, "f1")
        lp2, _, _, amt2, l2, u2 = _build_v3_pool_at_fee(500, "f2")
        lp3, _, _, amt3, l3, u3 = _build_v3_pool_at_fee(3000, "f3")
        lp4, _, _, amt4, l4, u4 = _build_v3_pool_at_fee(10000, "f4")

        result = CompareFeeTiers().apply([
            _candidate(lp1, amt1, l1, u1),
            _candidate(lp2, amt2, l2, u2),
            _candidate(lp3, amt3, l3, u3),
            _candidate(lp4, amt4, l4, u4),
        ])

        bps = [t.fee_tier_bps for t in result.tiers]
        self.assertEqual(bps, [1, 5, 30, 100])


# ─── TVL ranking ─────────────────────────────────────────────────────────────

class TestCompareFeeTiersTVLRanking(unittest.TestCase):

    def test_tvl_ranking_orders_largest_first(self):
        # Build three pools with distinct reserves.
        lp_small, _, _, amt_s, l_s, u_s = _build_v3_pool_at_fee(
            500, "t1", eth_amt = 100.0, dai_amt = 10_000.0,
        )
        lp_large, _, _, amt_l, l_l, u_l = _build_v3_pool_at_fee(
            3000, "t2", eth_amt = 5000.0, dai_amt = 500_000.0,
        )
        lp_med, _, _, amt_m, l_m, u_m = _build_v3_pool_at_fee(
            10000, "t3", eth_amt = 1000.0, dai_amt = 100_000.0,
        )
        result = CompareFeeTiers().apply([
            _candidate(lp_small, amt_s, l_s, u_s, name = "small"),
            _candidate(lp_large, amt_l, l_l, u_l, name = "large"),
            _candidate(lp_med, amt_m, l_m, u_m, name = "med"),
        ])
        self.assertEqual(
            result.ranking_by_tvl, ["large", "med", "small"]
        )

    def test_tvl_ranking_stable_tiebreak_on_input_order(self):
        # Two identical-TVL pools at different fee tiers should sort
        # in input order.
        lp_a, _, _, amt_a, l_a, u_a = _build_v3_pool_at_fee(500, "s1")
        lp_b, _, _, amt_b, l_b, u_b = _build_v3_pool_at_fee(3000, "s2")
        result = CompareFeeTiers().apply([
            _candidate(lp_a, amt_a, l_a, u_a, name = "first"),
            _candidate(lp_b, amt_b, l_b, u_b, name = "second"),
        ])
        # Same reserves → same TVL → stable on input order.
        self.assertEqual(result.ranking_by_tvl, ["first", "second"])


# ─── Observed fee yield ──────────────────────────────────────────────────────

class TestCompareFeeTiersFeeYield(unittest.TestCase):

    def test_fresh_pools_have_none_yield(self):
        # No swaps have happened → no accumulated fees.
        lp_a, _, _, amt_a, l_a, u_a = _build_v3_pool_at_fee(500, "y1")
        lp_b, _, _, amt_b, l_b, u_b = _build_v3_pool_at_fee(3000, "y2")
        result = CompareFeeTiers().apply([
            _candidate(lp_a, amt_a, l_a, u_a),
            _candidate(lp_b, amt_b, l_b, u_b),
        ])
        for tier in result.tiers:
            self.assertIsNone(tier.observed_fee_yield)

    def test_fresh_pool_ranking_stable_on_input_order(self):
        # All None-yield → stable on input order.
        lp_a, _, _, amt_a, l_a, u_a = _build_v3_pool_at_fee(500, "z1")
        lp_b, _, _, amt_b, l_b, u_b = _build_v3_pool_at_fee(3000, "z2")
        lp_c, _, _, amt_c, l_c, u_c = _build_v3_pool_at_fee(10000, "z3")
        result = CompareFeeTiers().apply([
            _candidate(lp_a, amt_a, l_a, u_a, name = "a"),
            _candidate(lp_b, amt_b, l_b, u_b, name = "b"),
            _candidate(lp_c, amt_c, l_c, u_c, name = "c"),
        ])
        self.assertEqual(
            result.ranking_by_observed_fee_yield, ["a", "b", "c"]
        )

    def test_none_yield_pools_sort_last(self):
        # Build two pools; swap through one to populate its fees.
        lp_quiet, eth_q, _, amt_q, l_q, u_q = _build_v3_pool_at_fee(
            500, "m1",
        )
        lp_active, eth_a, _, amt_a, l_a, u_a = _build_v3_pool_at_fee(
            3000, "m2",
        )
        # Drive some swaps through lp_active only.
        Swap().apply(lp_active, eth_a, USER, 10.0)

        result = CompareFeeTiers().apply([
            _candidate(lp_quiet, amt_q, l_q, u_q, name = "quiet"),
            _candidate(lp_active, amt_a, l_a, u_a, name = "active"),
        ])
        # Active pool has fees → goes first; quiet has None → goes last.
        self.assertEqual(
            result.ranking_by_observed_fee_yield, ["active", "quiet"]
        )

    def test_notes_call_out_none_yield(self):
        lp, _, _, amt, l, u = _build_v3_pool_at_fee(3000, "n1")
        result = CompareFeeTiers().apply([
            _candidate(lp, amt, l, u, name = "fresh"),
        ])
        self.assertTrue(any("observed_fee_yield is None" in n
                            for n in result.notes))


# ─── In-range handling ───────────────────────────────────────────────────────

class TestCompareFeeTiersRange(unittest.TestCase):

    def test_full_range_candidates_report_in_range(self):
        lp, _, _, amt, l, u = _build_v3_pool_at_fee(3000, "r1")
        result = CompareFeeTiers().apply([_candidate(lp, amt, l, u)])
        self.assertTrue(result.tiers[0].in_range)
        # No out-of-range note for an in-range candidate.
        self.assertFalse(any("out of range" in n for n in result.notes))

    def test_out_of_range_candidate_gets_note(self):
        # Build a pool, then propose a tick band entirely above current price.
        lp, _, _, amt, _, _ = _build_v3_pool_at_fee(3000, "r2")
        current_tick = lp.slot0.tick
        # Put the candidate range well above current — both bounds above.
        lwr = current_tick + 6 * V3_TICK_SPACING
        upr = current_tick + 12 * V3_TICK_SPACING
        result = CompareFeeTiers().apply([
            _candidate(lp, amt, lwr, upr, name = "oor"),
        ])
        self.assertFalse(result.tiers[0].in_range)
        self.assertTrue(any("out of range" in n for n in result.notes))


# ─── Single candidate ────────────────────────────────────────────────────────

class TestCompareFeeTiersSingleCandidate(unittest.TestCase):

    def test_single_candidate_produces_length_one_rankings(self):
        lp, _, _, amt, l, u = _build_v3_pool_at_fee(3000, "sc1")
        result = CompareFeeTiers().apply([
            _candidate(lp, amt, l, u, name = "only"),
        ])
        self.assertEqual(result.ranking_by_tvl, ["only"])
        self.assertEqual(result.ranking_by_observed_fee_yield, ["only"])
        self.assertEqual(len(result.tiers), 1)


# ─── Validation ──────────────────────────────────────────────────────────────

class TestCompareFeeTiersValidation(unittest.TestCase):

    def test_empty_list_raises(self):
        with self.assertRaises(ValueError) as ctx:
            CompareFeeTiers().apply([])
        self.assertIn("non-empty", str(ctx.exception))

    def test_v2_candidate_raises(self):
        # Use the shared v2_setup fixture via direct construction.
        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("v2 factory", "0x99")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V2LP", address = "0x099"
        )
        lp_v2 = factory.deploy(exch_data)
        lp_v2.add_liquidity(USER, 1000.0, 100_000.0, 1000.0, 100_000.0)
        lp_init_amt = lp_v2.convert_to_human(lp_v2.liquidity_providers[USER])
        with self.assertRaises(ValueError) as ctx:
            CompareFeeTiers().apply([
                FeeTierCandidate(
                    lp = lp_v2, position_size_lp = lp_init_amt,
                    lwr_tick = 0, upr_tick = 1,
                ),
            ])
        self.assertIn("V3 only", str(ctx.exception))
        self.assertIn("candidate 0", str(ctx.exception))

    def test_mixed_pair_raises(self):
        lp_dai, _, _, amt_d, l_d, u_d = _build_v3_pool_at_fee(3000, "mp1")
        lp_usdc, _, _, amt_u, l_u, u_u = _build_mismatched_pair_pool(
            3000, "mp2",
        )
        with self.assertRaises(ValueError) as ctx:
            CompareFeeTiers().apply([
                _candidate(lp_dai, amt_d, l_d, u_d),
                _candidate(lp_usdc, amt_u, l_u, u_u),
            ])
        msg = str(ctx.exception)
        self.assertIn("candidate 1", msg)
        self.assertIn("ETH/USDC", msg)
        self.assertIn("ETH/DAI", msg)

    def test_bad_tick_ordering_raises(self):
        lp, _, _, amt, _, _ = _build_v3_pool_at_fee(3000, "tk1")
        with self.assertRaises(ValueError) as ctx:
            CompareFeeTiers().apply([
                _candidate(lp, amt, lwr = 100, upr = 50),
            ])
        msg = str(ctx.exception)
        self.assertIn("candidate 0", msg)
        self.assertIn("lwr_tick", msg)

    def test_validation_error_identifies_offending_index(self):
        # V3 pool first (valid), V2 pool second (invalid) — error should
        # say candidate 1, not candidate 0.
        lp_v3, _, _, amt_v3, l_v3, u_v3 = _build_v3_pool_at_fee(3000, "id1")

        eth = ERC20("ETH", "0x09")
        dai = ERC20("DAI", "0x111")
        factory = UniswapFactory("v2 factory id", "0x88")
        exch_data = UniswapExchangeData(
            tkn0 = eth, tkn1 = dai, symbol = "V2LP",
            address = "0x088",
        )
        lp_v2 = factory.deploy(exch_data)
        lp_v2.add_liquidity(USER, 1000.0, 100_000.0, 1000.0, 100_000.0)
        amt_v2 = lp_v2.convert_to_human(lp_v2.liquidity_providers[USER])

        with self.assertRaises(ValueError) as ctx:
            CompareFeeTiers().apply([
                _candidate(lp_v3, amt_v3, l_v3, u_v3),
                FeeTierCandidate(
                    lp = lp_v2, position_size_lp = amt_v2,
                    lwr_tick = 0, upr_tick = 1,
                ),
            ])
        self.assertIn("candidate 1", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
