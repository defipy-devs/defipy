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
from uniswappy.utils.tools.v3 import UniV3Utils
from uniswappy.process.join import Join as UJoin

from balancerpy.erc import ERC20 as BERC20
from balancerpy.vault import BalancerVault
from balancerpy.cwpt.factory import BalancerFactory
from balancerpy.utils.data import BalancerExchangeData
from balancerpy.process.join import Join as BJoin

from stableswappy.erc import ERC20 as SERC20
from stableswappy.vault import StableswapVault
from stableswappy.cst.factory import StableswapFactory
from stableswappy.utils.data import StableswapExchangeData
from stableswappy.process.join import Join as SJoin

from python.prod.utils.data import (
    ProtocolComparison, ProtocolMetrics,
)
from python.prod.primitives.comparison import CompareProtocols


USER = "user0"


# ═══════════════════════════════════════════════════════════════════════════
# Pool builders — one per protocol, ETH/DAI pair with matching amounts
# ═══════════════════════════════════════════════════════════════════════════

def _build_v2(suffix = 'v2a'):
    eth = UERC20("ETH", "0x{}_eth".format(suffix))
    dai = UERC20("DAI", "0x{}_dai".format(suffix))
    factory = UniswapFactory("V2 factory {}".format(suffix),
                             "0x{}".format(suffix))
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "V2LP_{}".format(suffix),
        address = "0x0{}".format(suffix),
    )
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, 10.0, 10000.0, 10.0, 10000.0)
    return lp, eth, dai


def _build_v3(suffix = 'v3a'):
    eth = UERC20("ETH", "0x{}_eth".format(suffix))
    dai = UERC20("DAI", "0x{}_dai".format(suffix))
    factory = UniswapFactory("V3 factory {}".format(suffix),
                             "0x{}".format(suffix))
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "V3LP_{}".format(suffix),
        address = "0x0{}".format(suffix),
        version = 'V3', tick_spacing = 60, fee = 3000,
    )
    lp = factory.deploy(exch_data)
    lwr = UniV3Utils.getMinTick(60)
    upr = UniV3Utils.getMaxTick(60)
    UJoin().apply(lp, USER, 10.0, 10000.0, lwr, upr)
    return lp, eth, dai


def _build_balancer(base_weight = 0.5, suffix = 'bala'):
    eth = BERC20("ETH", "0x{}_eth".format(suffix))
    eth.deposit(USER, 10.0)
    dai = BERC20("DAI", "0x{}_dai".format(suffix))
    dai.deposit(USER, 10000.0)
    vault = BalancerVault()
    vault.add_token(eth, base_weight)
    vault.add_token(dai, 1.0 - base_weight)
    factory = BalancerFactory("Balancer factory {}".format(suffix),
                              "0x{}".format(suffix))
    exch_data = BalancerExchangeData(
        vault = vault, symbol = "BPT_{}".format(suffix),
        address = "0x0{}".format(suffix),
    )
    lp = factory.deploy(exch_data)
    BJoin().apply(lp, USER, 100)
    return lp, eth, dai


def _build_stableswap(ampl = 10, suffix = 'stba'):
    # Stableswap pools are stable-stable by design. Use USDC/DAI.
    # Still expose as "matches token_in ETH" style? No — stableswap
    # pool must contain the caller's token_in. For CompareProtocols
    # tests that mix V2/V3/Balancer (ETH/DAI) with stableswap, use
    # a stableswap ETH/DAI pool. Stableswap is agnostic to what
    # tokens are "supposed" to be pegged — it only cares about the
    # balanced reserves at construction.
    usdc = SERC20("ETH", "0x{}_eth".format(suffix), 18)
    usdc.deposit(USER, 10000.0)
    dai = SERC20("DAI", "0x{}_dai".format(suffix), 18)
    dai.deposit(USER, 10000.0)
    vault = StableswapVault()
    vault.add_token(usdc)
    vault.add_token(dai)
    factory = StableswapFactory("Stableswap factory {}".format(suffix),
                                "0x{}".format(suffix))
    exch_data = StableswapExchangeData(
        vault = vault, symbol = "CST_{}".format(suffix),
        address = "0x0{}".format(suffix),
    )
    lp = factory.deploy(exch_data)
    SJoin().apply(lp, USER, ampl)
    return lp, usdc, dai


# ═══════════════════════════════════════════════════════════════════════════
# Shape
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsShape(unittest.TestCase):

    def test_returns_protocol_comparison(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'sh1a')
        lp_b, _, _ = _build_v2(suffix = 'sh1b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIsInstance(result, ProtocolComparison)

    def test_pool_metrics_typed(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'sh2a')
        lp_b, _, _ = _build_v2(suffix = 'sh2b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIsInstance(result.pool_a, ProtocolMetrics)
        self.assertIsInstance(result.pool_b, ProtocolMetrics)

    def test_echoes_shock_amount_token(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'sh3a')
        lp_b, _, _ = _build_v2(suffix = 'sh3b')
        result = CompareProtocols(price_shock = 0.15).apply(
            lp_a, lp_b, 2.5, eth_a,
        )
        self.assertAlmostEqual(result.price_shock, 0.15, places = 10)
        self.assertAlmostEqual(result.amount, 2.5, places = 10)
        self.assertEqual(result.token_in_name, "ETH")

    def test_default_token_in_is_lp_a_token0(self):
        # When token_in is None, defaults to lp_a's token0 (ETH).
        lp_a, _, _ = _build_v2(suffix = 'sh4a')
        lp_b, _, _ = _build_v2(suffix = 'sh4b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0)
        self.assertEqual(result.token_in_name, "ETH")


# ═══════════════════════════════════════════════════════════════════════════
# V2 vs V2 baseline — same pool twice → tied on everything
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsBaseline(unittest.TestCase):

    def test_identical_v2_pools_il_tied(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'b1a')
        lp_b, _, _ = _build_v2(suffix = 'b1b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertEqual(result.il_advantage, "tied")

    def test_identical_v2_pools_slippage_tied(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'b2a')
        lp_b, _, _ = _build_v2(suffix = 'b2b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertEqual(result.slippage_advantage, "tied")


# ═══════════════════════════════════════════════════════════════════════════
# Protocol detection & labeling
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsDetection(unittest.TestCase):

    def test_v2_labeled_uniswap_v2(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'd1a')
        lp_b, _, _ = _build_v2(suffix = 'd1b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertEqual(result.pool_a.protocol, "uniswap_v2")
        self.assertEqual(result.pool_b.protocol, "uniswap_v2")

    def test_v3_labeled_uniswap_v3(self):
        lp_a, eth_a, _ = _build_v3(suffix = 'd2a')
        lp_b, _, _ = _build_v3(suffix = 'd2b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertEqual(result.pool_a.protocol, "uniswap_v3")
        self.assertEqual(result.pool_b.protocol, "uniswap_v3")

    def test_balancer_labeled_balancer(self):
        lp_a, eth_a, _ = _build_balancer(suffix = 'd3a')
        lp_b, _, _ = _build_balancer(suffix = 'd3b')
        result = CompareProtocols().apply(lp_a, lp_b, 0.5, eth_a)
        self.assertEqual(result.pool_a.protocol, "balancer")
        self.assertEqual(result.pool_b.protocol, "balancer")

    def test_stableswap_labeled_stableswap(self):
        lp_a, eth_a, _ = _build_stableswap(suffix = 'd4a')
        lp_b, _, _ = _build_stableswap(suffix = 'd4b')
        result = CompareProtocols().apply(lp_a, lp_b, 100.0, eth_a)
        self.assertEqual(result.pool_a.protocol, "stableswap")
        self.assertEqual(result.pool_b.protocol, "stableswap")


# ═══════════════════════════════════════════════════════════════════════════
# Cross-protocol comparisons — the whole point of the primitive
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsCrossProtocol(unittest.TestCase):

    def test_balancer_80_20_less_il_than_v2_50_50(self):
        # 80/20 Balancer has bounded IL vs 50/50 V2 at same alpha shock.
        lp_v2, eth_v2, _ = _build_v2(suffix = 'cp1v')
        lp_bal, eth_bal, _ = _build_balancer(
            base_weight = 0.8, suffix = 'cp1b',
        )
        result = CompareProtocols().apply(lp_v2, lp_bal, 1.0, eth_v2)
        # Both IL values should be populated.
        self.assertIsNotNone(result.pool_a.il_at_shock)
        self.assertIsNotNone(result.pool_b.il_at_shock)
        # Balancer (pool_b) should have lower IL.
        self.assertLess(
            result.pool_b.il_at_shock, result.pool_a.il_at_shock,
        )
        self.assertEqual(result.il_advantage, "pool_b")

    def test_stableswap_has_more_il_than_v2_at_moderate_A(self):
        # Counterintuitive but mathematically correct (Cintra &
        # Holloway 2023): stableswap has LARGER |IL| than V2 at the
        # same alpha, not smaller. The flat curve forces arbitrageurs
        # to drain substantial balance to move dydx even a little;
        # once they do, the LP holds a skewed composition. The
        # marketing line "stableswap protects LPs from IL" is true
        # per unit of trading volume but misleading per unit of
        # price deviation — and CompareProtocols reports the
        # per-price-deviation IL.
        #
        # A=5 is chosen so ±10% is REACHABLE (higher A would make
        # the shock unreachable and produce il_at_shock = None).
        lp_v2, eth_v2, _ = _build_v2(suffix = 'cp2v')
        lp_ss, eth_ss, _ = _build_stableswap(ampl = 5, suffix = 'cp2s')
        result = CompareProtocols().apply(lp_v2, lp_ss, 1.0, eth_v2)
        self.assertIsNotNone(result.pool_a.il_at_shock)
        self.assertIsNotNone(result.pool_b.il_at_shock)
        # Stableswap (pool_b) has MORE IL than V2 (pool_a).
        self.assertGreater(
            result.pool_b.il_at_shock, result.pool_a.il_at_shock,
        )
        self.assertEqual(result.il_advantage, "pool_a")

    def test_v3_concentrated_vs_v2(self):
        # V3 at default ±10% auto-range has higher IL per unit capital
        # vs V2 full-range (concentrated liquidity amplifies IL).
        lp_v2, eth_v2, _ = _build_v2(suffix = 'cp3v')
        lp_v3, _, _ = _build_v3(suffix = 'cp3w')
        result = CompareProtocols().apply(lp_v2, lp_v3, 1.0, eth_v2)
        self.assertIsNotNone(result.pool_a.il_at_shock)
        self.assertIsNotNone(result.pool_b.il_at_shock)
        # V3 at auto-range should have MORE IL than V2 at same alpha.
        self.assertGreater(
            result.pool_b.il_at_shock, result.pool_a.il_at_shock,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Stableswap unreachable regime
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsStableswapUnreachable(unittest.TestCase):

    def test_high_A_unreachable_il_is_none(self):
        # A=200 at ±10% shock is unreachable → il_at_shock = None.
        lp_v2, eth_v2, _ = _build_v2(suffix = 'u1v')
        lp_ss, _, _ = _build_stableswap(ampl = 200, suffix = 'u1s')
        result = CompareProtocols().apply(lp_v2, lp_ss, 1.0, eth_v2)
        self.assertIsNone(result.pool_b.il_at_shock)

    def test_unreachable_il_advantage_is_none(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 'u2v')
        lp_ss, _, _ = _build_stableswap(ampl = 200, suffix = 'u2s')
        result = CompareProtocols().apply(lp_v2, lp_ss, 1.0, eth_v2)
        self.assertIsNone(result.il_advantage)

    def test_unreachable_flagged_in_notes(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 'u3v')
        lp_ss, _, _ = _build_stableswap(ampl = 200, suffix = 'u3s')
        result = CompareProtocols().apply(lp_v2, lp_ss, 1.0, eth_v2)
        found = any("unreachable" in n.lower() for n in result.notes)
        self.assertTrue(found)


# ═══════════════════════════════════════════════════════════════════════════
# Slippage scope — Balancer / Stableswap slippage is None in v1
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsSlippageScope(unittest.TestCase):

    def test_balancer_slippage_is_none(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 's1v')
        lp_bal, _, _ = _build_balancer(suffix = 's1b')
        result = CompareProtocols().apply(lp_v2, lp_bal, 1.0, eth_v2)
        self.assertIsNotNone(result.pool_a.slippage_at_amount)
        self.assertIsNone(result.pool_b.slippage_at_amount)

    def test_balancer_slippage_flagged_in_notes(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 's2v')
        lp_bal, _, _ = _build_balancer(suffix = 's2b')
        result = CompareProtocols().apply(lp_v2, lp_bal, 1.0, eth_v2)
        found = any("slippage" in n.lower() and "balancer" in n.lower()
                    for n in result.notes)
        self.assertTrue(found)

    def test_stableswap_slippage_is_none(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 's3v')
        lp_ss, _, _ = _build_stableswap(ampl = 10, suffix = 's3s')
        result = CompareProtocols().apply(lp_v2, lp_ss, 1.0, eth_v2)
        self.assertIsNotNone(result.pool_a.slippage_at_amount)
        self.assertIsNone(result.pool_b.slippage_at_amount)

    def test_slippage_advantage_none_when_one_side_none(self):
        lp_v2, eth_v2, _ = _build_v2(suffix = 's4v')
        lp_bal, _, _ = _build_balancer(suffix = 's4b')
        result = CompareProtocols().apply(lp_v2, lp_bal, 1.0, eth_v2)
        self.assertIsNone(result.slippage_advantage)


# ═══════════════════════════════════════════════════════════════════════════
# TVL reporting
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsTVL(unittest.TestCase):

    def test_v2_tvl_in_token_in_positive(self):
        lp_a, eth_a, _ = _build_v2(suffix = 't1a')
        lp_b, _, _ = _build_v2(suffix = 't1b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertGreater(result.pool_a.tvl_in_token_in, 0)
        self.assertGreater(result.pool_b.tvl_in_token_in, 0)

    def test_identical_pools_same_tvl(self):
        lp_a, eth_a, _ = _build_v2(suffix = 't2a')
        lp_b, _, _ = _build_v2(suffix = 't2b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertAlmostEqual(
            result.pool_a.tvl_in_token_in,
            result.pool_b.tvl_in_token_in,
            places = 6,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Advantage labels
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsAdvantage(unittest.TestCase):

    def test_il_advantage_one_of_allowed(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'ad1a')
        lp_b, _, _ = _build_v2(suffix = 'ad1b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIn(result.il_advantage,
                      {"pool_a", "pool_b", "tied", None})

    def test_slippage_advantage_one_of_allowed(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'ad2a')
        lp_b, _, _ = _build_v2(suffix = 'ad2b')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIn(result.slippage_advantage,
                      {"pool_a", "pool_b", "tied", None})


# ═══════════════════════════════════════════════════════════════════════════
# V3 auto-range behavior
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsV3AutoRange(unittest.TestCase):

    def test_v3_pools_note_auto_range(self):
        lp_a, eth_a, _ = _build_v3(suffix = 'v3a1')
        lp_b, _, _ = _build_v3(suffix = 'v3a2')
        result = CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        found = any("auto-range" in n.lower() for n in result.notes)
        self.assertTrue(found)

    def test_narrower_v3_range_yields_different_il(self):
        # Verifies v3_range_pct affects il_at_shock (the parameter is
        # actually plumbed into the range calculation). Doesn't
        # assert direction: the range-aware IL scale factor
        # sqrt(r)/(sqrt(r)-1) is numerically delicate when ranges
        # are near-symmetric around current price, and the tick
        # snapping in _auto_v3_range can flip the direction between
        # any two specific widths. EvaluateTickRanges has dedicated
        # tests for the "narrower range → more IL" property using
        # tick-multiple-based widths where the property holds
        # reliably; callers who need direction guarantees should
        # use that primitive directly.
        lp_a, eth_a, _ = _build_v3(suffix = 'v3b1')
        lp_b, _, _ = _build_v3(suffix = 'v3b2')
        wide = CompareProtocols(
            price_shock = 0.03, v3_range_pct = 0.20,
        ).apply(lp_a, lp_b, 1.0, eth_a)
        narrow = CompareProtocols(
            price_shock = 0.03, v3_range_pct = 0.05,
        ).apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIsNotNone(wide.pool_a.il_at_shock)
        self.assertIsNotNone(narrow.pool_a.il_at_shock)
        # The two values should differ (both are using different
        # ranges) but we don't pin the sign.
        self.assertNotAlmostEqual(
            narrow.pool_a.il_at_shock, wide.pool_a.il_at_shock,
            places = 3,
        )

    def test_shock_exceeding_v3_range_yields_none_il(self):
        # When price_shock > v3_range_pct, the shock pushes alpha
        # outside the V3 position's range. The range-aware IL formula
        # is undefined there, so the primitive returns None + note.
        lp_a, eth_a, _ = _build_v3(suffix = 'v3c1')
        lp_b, _, _ = _build_v3(suffix = 'v3c2')
        result = CompareProtocols(
            price_shock = 0.15, v3_range_pct = 0.05,
        ).apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIsNone(result.pool_a.il_at_shock)
        self.assertIsNone(result.il_advantage)
        found = any("out-of-range" in n.lower() or "undefined" in n.lower()
                    for n in result.notes)
        self.assertTrue(found)


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestCompareProtocolsValidation(unittest.TestCase):

    def test_zero_amount_raises(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'va1a')
        lp_b, _, _ = _build_v2(suffix = 'va1b')
        with self.assertRaises(ValueError):
            CompareProtocols().apply(lp_a, lp_b, 0.0, eth_a)

    def test_negative_amount_raises(self):
        lp_a, eth_a, _ = _build_v2(suffix = 'va2a')
        lp_b, _, _ = _build_v2(suffix = 'va2b')
        with self.assertRaises(ValueError):
            CompareProtocols().apply(lp_a, lp_b, -1.0, eth_a)

    def test_common_token_violation_raises(self):
        # pool_a holds ETH/DAI, pool_b holds BTC/USDC — no common token.
        lp_a, eth_a, _ = _build_v2(suffix = 'va3a')

        btc = UERC20("BTC", "0xbtc")
        usdc = UERC20("USDC", "0xusdc")
        factory = UniswapFactory("Other factory", "0x_other")
        exch_data = UniswapExchangeData(
            tkn0 = btc, tkn1 = usdc, symbol = "OtherLP",
            address = "0x_other_lp",
        )
        lp_b = factory.deploy(exch_data)
        lp_b.add_liquidity(USER, 1.0, 30000.0, 1.0, 30000.0)

        with self.assertRaises(ValueError) as ctx:
            CompareProtocols().apply(lp_a, lp_b, 1.0, eth_a)
        self.assertIn("pool_b", str(ctx.exception))

    def test_bad_price_shock_raises_at_construction(self):
        with self.assertRaises(ValueError):
            CompareProtocols(price_shock = 0.0)
        with self.assertRaises(ValueError):
            CompareProtocols(price_shock = 1.0)

    def test_bad_v3_range_pct_raises_at_construction(self):
        with self.assertRaises(ValueError):
            CompareProtocols(v3_range_pct = 0.0)
        with self.assertRaises(ValueError):
            CompareProtocols(v3_range_pct = 1.0)


if __name__ == '__main__':
    unittest.main()
