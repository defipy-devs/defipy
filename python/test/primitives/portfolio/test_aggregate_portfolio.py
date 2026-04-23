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
from uniswappy.process.swap import Swap

from python.prod.utils.data import (
    PortfolioPosition,
    PortfolioAnalysis,
    PositionSummary,
    PositionAnalysis,
)
from python.prod.primitives.portfolio import AggregatePortfolio


USER = "user0"
USER2 = "user1"


# ─── Helpers for building additional V2 positions inline ─────────────────────

def _build_eth_usdc_lp(address = "0x022"):
    """Second V2 pool with the same token0 (ETH) but different token1 (USDC)."""
    eth = ERC20("ETH", "0x09")
    usdc = ERC20("USDC", "0x222")
    factory = UniswapFactory("ETH-USDC pool factory", "0x3")
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = usdc, symbol = "LP2", address = address
    )
    lp = factory.deploy(exch_data)
    # 500 ETH / 1_000_000 USDC → spot 2000 USDC/ETH.
    lp.add_liquidity(USER, 500.0, 1_000_000.0, 500.0, 1_000_000.0)
    return lp, eth, usdc


def _build_btc_dai_lp():
    """A V2 pool with DIFFERENT token0 (BTC), for mixed-numeraire testing."""
    btc = ERC20("BTC", "0x77")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory("BTC-DAI pool factory", "0x4")
    exch_data = UniswapExchangeData(
        tkn0 = btc, tkn1 = dai, symbol = "LP3", address = "0x033"
    )
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, 10.0, 500_000.0, 10.0, 500_000.0)
    return lp, btc, dai


# ─── V2 test suite ───────────────────────────────────────────────────────────

class TestAggregatePortfolioV2(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v2_setup):
        """Primary portfolio position: ETH/DAI from the shared fixture.
        Additional positions built inline per test when needed."""
        self.setup = v2_setup

    def _primary_position(self, name = None):
        """Wrap the fixture's ETH/DAI LP as a PortfolioPosition."""
        return PortfolioPosition(
            lp = self.setup.lp,
            lp_init_amt = self.setup.lp_init_amt,
            entry_x_amt = self.setup.entry_x_amt,
            entry_y_amt = self.setup.entry_y_amt,
            name = name,
        )

    # ─── Shape & return type ────────────────────────────────────────────────

    def test_returns_portfolio_analysis(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertIsInstance(result, PortfolioAnalysis)

    def test_single_position_numeraire_is_token0(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertEqual(result.numeraire, "ETH")

    def test_positions_carry_full_analysis(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertEqual(len(result.positions), 1)
        self.assertIsInstance(result.positions[0], PositionSummary)
        self.assertIsInstance(result.positions[0].analysis, PositionAnalysis)

    def test_default_position_name_is_pair_slash(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertEqual(result.positions[0].name, "ETH/DAI")

    def test_custom_position_name_respected(self):
        result = AggregatePortfolio().apply(
            [self._primary_position(name = "MyMainLP")]
        )
        self.assertEqual(result.positions[0].name, "MyMainLP")

    # ─── Single-position totals equal per-position values ───────────────────

    def test_totals_match_single_position_analysis(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        only = result.positions[0].analysis
        self.assertAlmostEqual(result.total_value, only.current_value, places = 6)
        self.assertAlmostEqual(result.total_hold_value, only.hold_value, places = 6)
        self.assertAlmostEqual(result.total_net_pnl, only.net_pnl, places = 6)

    def test_single_position_pnl_ranking_is_that_one_position(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertEqual(result.pnl_ranking, ["ETH/DAI"])

    # ─── Multi-position aggregation ─────────────────────────────────────────

    def _two_position_portfolio(self):
        """Build a portfolio of two ETH-numeraire positions."""
        lp_usdc, eth, usdc = _build_eth_usdc_lp()
        lp_init_usdc = lp_usdc.convert_to_human(lp_usdc.liquidity_providers[USER])
        return [
            self._primary_position(name = "ETH/DAI"),
            PortfolioPosition(
                lp = lp_usdc,
                lp_init_amt = lp_init_usdc,
                entry_x_amt = 500.0,
                entry_y_amt = 1_000_000.0,
                name = "ETH/USDC",
            ),
        ]

    def test_two_position_totals_are_sums(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        self.assertEqual(len(result.positions), 2)
        # Both positions at entry → total_net_pnl ~= 0 modulo floating-point.
        self.assertAlmostEqual(result.total_net_pnl, 0.0, places = 4)
        # total_value at entry = sum of hold_values (no price move yet).
        self.assertAlmostEqual(
            result.total_value, result.total_hold_value, places = 4
        )

    def test_positions_returned_in_input_order(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        self.assertEqual(
            [s.name for s in result.positions],
            ["ETH/DAI", "ETH/USDC"],
        )

    def test_numeraire_agrees_across_positions(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        self.assertEqual(result.numeraire, "ETH")

    # ─── PnL ranking after asymmetric swaps ─────────────────────────────────

    def test_pnl_ranking_worst_first_after_divergent_swaps(self):
        # Build two-position portfolio, then hit ONE pool with a big swap to
        # create IL asymmetry. The swapped pool should rank worst.
        positions = self._two_position_portfolio()
        # Swap on the fixture's ETH/DAI pool — push price substantially.
        Swap().apply(self.setup.lp, self.setup.eth, USER2, 200.0)
        result = AggregatePortfolio().apply(positions)
        # The ETH/DAI pool had the price disturbance → IL hit → worst PnL.
        self.assertEqual(result.pnl_ranking[0], "ETH/DAI")
        self.assertEqual(result.pnl_ranking[1], "ETH/USDC")

    def test_pnl_ranking_length_matches_positions(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        self.assertEqual(len(result.pnl_ranking), len(positions))

    # ─── Shared-exposure warnings ───────────────────────────────────────────

    def test_shared_numeraire_produces_warning(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        # ETH is in both positions → expect a warning mentioning ETH and
        # both position names.
        eth_warning = [w for w in result.shared_exposure_warnings if "ETH" in w]
        self.assertEqual(len(eth_warning), 1)
        self.assertIn("ETH/DAI", eth_warning[0])
        self.assertIn("ETH/USDC", eth_warning[0])

    def test_unique_token1_not_warned(self):
        positions = self._two_position_portfolio()
        result = AggregatePortfolio().apply(positions)
        # DAI appears in only one position → no warning for DAI.
        dai_warning = [w for w in result.shared_exposure_warnings if w.startswith("DAI")]
        self.assertEqual(len(dai_warning), 0)
        # USDC also in only one position.
        usdc_warning = [w for w in result.shared_exposure_warnings if w.startswith("USDC")]
        self.assertEqual(len(usdc_warning), 0)

    def test_single_position_no_shared_exposure(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertEqual(result.shared_exposure_warnings, [])

    # ─── Mixed-numeraire rejection ──────────────────────────────────────────

    def test_raises_on_mixed_numeraire(self):
        lp_btc, btc, dai = _build_btc_dai_lp()
        lp_init_btc = lp_btc.convert_to_human(lp_btc.liquidity_providers[USER])
        positions = [
            self._primary_position(),
            PortfolioPosition(
                lp = lp_btc,
                lp_init_amt = lp_init_btc,
                entry_x_amt = 10.0,
                entry_y_amt = 500_000.0,
            ),
        ]
        with self.assertRaises(ValueError) as ctx:
            AggregatePortfolio().apply(positions)
        # Error message should list both offending numeraires.
        msg = str(ctx.exception)
        self.assertIn("ETH", msg)
        self.assertIn("BTC", msg)

    # ─── Empty input ────────────────────────────────────────────────────────

    def test_raises_on_empty_positions(self):
        with self.assertRaises(ValueError):
            AggregatePortfolio().apply([])

    # ─── Holding period passthrough to AnalyzePosition ──────────────────────

    def test_holding_period_produces_real_apr(self):
        position = PortfolioPosition(
            lp = self.setup.lp,
            lp_init_amt = self.setup.lp_init_amt,
            entry_x_amt = self.setup.entry_x_amt,
            entry_y_amt = self.setup.entry_y_amt,
            holding_period_days = 30.0,
        )
        result = AggregatePortfolio().apply([position])
        # real_apr computed → not None on the carried analysis.
        self.assertIsNotNone(result.positions[0].analysis.real_apr)

    def test_no_holding_period_yields_none_apr(self):
        result = AggregatePortfolio().apply([self._primary_position()])
        self.assertIsNone(result.positions[0].analysis.real_apr)


# ─── V3 suite ────────────────────────────────────────────────────────────────

class TestAggregatePortfolioV3(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, v3_setup):
        self.setup = v3_setup

    def _v3_position(self):
        return PortfolioPosition(
            lp = self.setup.lp,
            lp_init_amt = self.setup.lp_init_amt,
            entry_x_amt = self.setup.entry_x_amt,
            entry_y_amt = self.setup.entry_y_amt,
            lwr_tick = self.setup.lwr_tick,
            upr_tick = self.setup.upr_tick,
        )

    def test_v3_single_position_returns_portfolio(self):
        result = AggregatePortfolio().apply([self._v3_position()])
        self.assertIsInstance(result, PortfolioAnalysis)

    def test_v3_numeraire_is_token0(self):
        result = AggregatePortfolio().apply([self._v3_position()])
        self.assertEqual(result.numeraire, "ETH")

    def test_v3_position_analysis_carries_through(self):
        result = AggregatePortfolio().apply([self._v3_position()])
        self.assertIsInstance(result.positions[0].analysis, PositionAnalysis)


# ─── Cross-protocol aggregation suite ────────────────────────────────────────────
#
# Portfolios that mix V2/V3/Balancer/Stableswap positions. Exercises the
# isinstance-dispatch layer added when Balancer and Stableswap analyzers
# landed. The baseline expectation: a cross-protocol portfolio where
# each position is at its own entry state should aggregate to
# total_net_pnl ≈ 0, just like the V2-only baseline above.
#
# Numeraire: all fixture pools use ETH (V2/V3/Balancer) or USDC
# (Stableswap) as first token. Cross-protocol tests that include
# Stableswap stick to USDC-first fixtures for AggregatePortfolio
# compatibility.


class TestAggregatePortfolioCrossProtocol(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setups(self, v2_setup, v3_setup, balancer_setup):
        self.v2 = v2_setup
        self.v3 = v3_setup
        self.bal = balancer_setup

    def _v2_position(self):
        return PortfolioPosition(
            lp = self.v2.lp, lp_init_amt = self.v2.lp_init_amt,
            entry_x_amt = self.v2.entry_x_amt,
            entry_y_amt = self.v2.entry_y_amt,
            name = "v2_ethdai",
        )

    def _v3_position(self):
        return PortfolioPosition(
            lp = self.v3.lp, lp_init_amt = self.v3.lp_init_amt,
            entry_x_amt = self.v3.entry_x_amt,
            entry_y_amt = self.v3.entry_y_amt,
            lwr_tick = self.v3.lwr_tick, upr_tick = self.v3.upr_tick,
            name = "v3_ethdai",
        )

    def _balancer_position(self):
        return PortfolioPosition(
            lp = self.bal.lp, lp_init_amt = self.bal.lp_init_amt,
            entry_x_amt = self.bal.entry_base_amt,
            entry_y_amt = self.bal.entry_opp_amt,
            name = "bal_ethdai",
        )

    # ─── V2 + Balancer mix ───────────────────────────────────────

    def test_v2_plus_balancer_aggregates(self):
        positions = [self._v2_position(), self._balancer_position()]
        result = AggregatePortfolio().apply(positions)
        self.assertIsInstance(result, PortfolioAnalysis)
        self.assertEqual(result.numeraire, "ETH")
        self.assertEqual(len(result.positions), 2)

    def test_v2_plus_balancer_position_protocols_labeled(self):
        positions = [self._v2_position(), self._balancer_position()]
        result = AggregatePortfolio().apply(positions)
        protos = {s.name: s.protocol for s in result.positions}
        self.assertEqual(protos["v2_ethdai"], "uniswap_v2")
        self.assertEqual(protos["bal_ethdai"], "balancer")

    def test_v2_plus_balancer_at_entry_net_pnl_near_zero(self):
        positions = [self._v2_position(), self._balancer_position()]
        result = AggregatePortfolio().apply(positions)
        # Both at entry → combined PnL should be within float noise of 0.
        # Looser tolerance than V2-only because Balancer's fee-free
        # spot derivation can leave a tiny residual.
        self.assertAlmostEqual(result.total_net_pnl, 0.0, places = 2)

    # ─── V2 + V3 + Balancer mix ─────────────────────────────────

    def test_three_protocol_aggregation(self):
        positions = [
            self._v2_position(),
            self._v3_position(),
            self._balancer_position(),
        ]
        result = AggregatePortfolio().apply(positions)
        self.assertEqual(len(result.positions), 3)
        self.assertEqual(result.numeraire, "ETH")
        protos = sorted(s.protocol for s in result.positions)
        self.assertEqual(
            protos, ["balancer", "uniswap_v2", "uniswap_v3"],
        )

    def test_three_protocol_shared_eth_exposure_flagged(self):
        positions = [
            self._v2_position(),
            self._v3_position(),
            self._balancer_position(),
        ]
        result = AggregatePortfolio().apply(positions)
        eth_warnings = [
            w for w in result.shared_exposure_warnings
            if w.startswith("ETH")
        ]
        self.assertEqual(len(eth_warnings), 1)
        # All three position names should appear in the ETH warning.
        self.assertIn("v2_ethdai", eth_warnings[0])
        self.assertIn("v3_ethdai", eth_warnings[0])
        self.assertIn("bal_ethdai", eth_warnings[0])

    # ─── Validation ──────────────────────────────────────────────

    def test_mixed_first_token_across_protocols_raises(self):
        # V2 ETH/DAI + a Balancer pool whose first token is NOT ETH
        # should raise. Build a small inline DAI/ETH-ordered
        # Balancer pool to prove the point.
        from balancerpy.erc import ERC20 as BERC20
        from balancerpy.vault import BalancerVault
        from balancerpy.cwpt.factory import BalancerFactory
        from balancerpy.utils.data import BalancerExchangeData
        from balancerpy.process.join import Join as BJoin

        dai = BERC20("DAI", "0xdai_first")
        dai.deposit(USER, 10000.0)
        eth = BERC20("ETH", "0xeth_second")
        eth.deposit(USER, 10.0)
        vault = BalancerVault()
        vault.add_token(dai, 0.5)
        vault.add_token(eth, 0.5)
        factory = BalancerFactory("DAI-first bal", "0xd1")
        exch = BalancerExchangeData(
            vault = vault, symbol = "BPT", address = "0xd2",
        )
        lp_bal = factory.deploy(exch)
        BJoin().apply(lp_bal, USER, 100.0)

        bad_position = PortfolioPosition(
            lp = lp_bal, lp_init_amt = 100.0,
            entry_x_amt = 10000.0, entry_y_amt = 10.0,
            name = "dai_first_bal",
        )

        with self.assertRaises(ValueError) as ctx:
            AggregatePortfolio().apply([
                self._v2_position(), bad_position,
            ])
        msg = str(ctx.exception)
        self.assertIn("ETH", msg)
        self.assertIn("DAI", msg)


# ─── Stableswap aggregation (USDC-numeraire, separate class) ─────────────
#
# Stableswap's first token is USDC in our fixture. V2/V3 ETH/DAI pools
# won't aggregate with it (different first-token symbol). Use a separate
# V2 USDC/DAI pool for mixed aggregation.


def _build_usdc_dai_v2():
    """V2 USDC/DAI pool — for mixing with the stableswap fixture."""
    usdc = ERC20("USDC", "0xusdc_v2")
    dai = ERC20("DAI", "0xdai_v2")
    factory = UniswapFactory("USDC-DAI V2", "0xud1")
    exch = UniswapExchangeData(
        tkn0 = usdc, tkn1 = dai, symbol = "UDLP", address = "0xud2",
    )
    lp = factory.deploy(exch)
    lp.add_liquidity(USER, 50000.0, 50000.0, 50000.0, 50000.0)
    return lp, usdc, dai


class TestAggregatePortfolioStableswapMix(unittest.TestCase):

    @pytest.fixture(autouse = True)
    def _bind_setup(self, stableswap_setup):
        self.ss = stableswap_setup

    def _stableswap_position(self, name = "ss_usdc_dai"):
        return PortfolioPosition(
            lp = self.ss.lp, lp_init_amt = self.ss.lp_init_amt,
            entry_amounts = self.ss.entry_amounts,
            name = name,
        )

    def test_stableswap_alone_aggregates(self):
        result = AggregatePortfolio().apply([self._stableswap_position()])
        self.assertIsInstance(result, PortfolioAnalysis)
        self.assertEqual(result.numeraire, "USDC")
        self.assertEqual(result.positions[0].protocol, "stableswap")

    def test_stableswap_at_peg_contributes_zero_pnl(self):
        result = AggregatePortfolio().apply([self._stableswap_position()])
        self.assertAlmostEqual(result.total_net_pnl, 0.0, places = 4)

    def test_stableswap_plus_v2_usdc_aggregate(self):
        lp_v2, usdc, dai = _build_usdc_dai_v2()
        lp_init = lp_v2.convert_to_human(lp_v2.liquidity_providers[USER])
        v2_pos = PortfolioPosition(
            lp = lp_v2, lp_init_amt = lp_init,
            entry_x_amt = 50000.0, entry_y_amt = 50000.0,
            name = "v2_usdc_dai",
        )
        result = AggregatePortfolio().apply([
            v2_pos, self._stableswap_position(),
        ])
        self.assertEqual(result.numeraire, "USDC")
        self.assertEqual(len(result.positions), 2)
        protos = {s.name: s.protocol for s in result.positions}
        self.assertEqual(protos["v2_usdc_dai"], "uniswap_v2")
        self.assertEqual(protos["ss_usdc_dai"], "stableswap")

    def test_stableswap_missing_entry_amounts_raises(self):
        # A stableswap position with entry_x_amt/entry_y_amt set but
        # entry_amounts None gets rejected at aggregation time.
        bad_position = PortfolioPosition(
            lp = self.ss.lp, lp_init_amt = self.ss.lp_init_amt,
            entry_x_amt = 100000.0, entry_y_amt = 100000.0,
        )
        with self.assertRaises(ValueError) as ctx:
            AggregatePortfolio().apply([bad_position])
        self.assertIn("entry_amounts", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
