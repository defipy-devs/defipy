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

"""
Shared fixtures for primitive tests.

Provides canonical V2 and V3 LP setups that any primitive test in this
subtree can request via pytest fixture injection. Keeps setup consistent
across the 19-primitive build-out and prevents the setUp-boilerplate drift
that would otherwise accumulate as each primitive re-invents its own
'build a test LP' helper.

Usage in a test file:

    class TestMyPrimitive(unittest.TestCase):

        @pytest.fixture(autouse=True)
        def _bind_setup(self, v2_setup):
            self.setup = v2_setup

        def test_something(self):
            result = MyPrimitive().apply(
                self.setup.lp,
                self.setup.lp_init_amt,
                self.setup.entry_x_amt,
                self.setup.entry_y_amt,
            )

Or with plain-function pytest style:

    def test_something(v2_setup):
        result = MyPrimitive().apply(
            v2_setup.lp, v2_setup.lp_init_amt,
            v2_setup.entry_x_amt, v2_setup.entry_y_amt,
        )

Both styles work. Pick whichever matches the existing test file's pattern.
"""

from dataclasses import dataclass
from typing import Any, List

import pytest

from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import UniV3Utils
from uniswappy.process.join import Join

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


# ─── Canonical test constants ────────────────────────────────────────────────
USER = "user0"
ETH_AMT = 1000.0
DAI_AMT = 100000.0

# V3 defaults — 0.3% fee tier, tick spacing 60 (matches most mainnet pools)
V3_TICK_SPACING = 60
V3_FEE = 3000

# Balancer: 50/50 by default, ETH/DAI at the same nominal amounts as V2/V3.
# Weighted pools with non-default weights are configurable via the
# `base_weight` parameter on the _build_balancer helper fixtures.
BAL_DEFAULT_WEIGHT = 0.5
BAL_POOL_SHARES_INIT = 100.0

# Stableswap: use USDC/DAI by default (stable-stable by design). Amplification
# coefficient 10 is moderate — low enough that ±10% shocks remain reachable,
# high enough that the stableswap vs V2 IL ordering is clearly distinguishable.
SS_DEFAULT_AMPL = 10
SS_BALANCE_EACH = 100000.0


# ─── Result containers ───────────────────────────────────────────────────────

@dataclass
class V2Setup:
    """Canonical V2 LP fixture state.

    USER owns 100% of the pool at entry with ETH_AMT / DAI_AMT reserves.
    """
    lp: Any
    eth: ERC20
    dai: ERC20
    lp_init_amt: float
    entry_x_amt: float   # ETH deposited at entry (== ETH_AMT)
    entry_y_amt: float   # DAI deposited at entry (== DAI_AMT)


@dataclass
class V3Setup:
    """Canonical V3 LP fixture state.

    USER owns 100% of the pool at entry with full-range ticks at
    tick_spacing=60, fee=3000 (0.3%).
    """
    lp: Any
    eth: ERC20
    dai: ERC20
    lp_init_amt: float
    entry_x_amt: float
    entry_y_amt: float
    lwr_tick: int
    upr_tick: int


@dataclass
class BalancerSetup:
    """Canonical Balancer weighted-pool fixture state.

    2-asset pool (matches the scope of BalancerImpLoss). USER holds
    BAL_POOL_SHARES_INIT pool shares after the Join. Default weight
    is 50/50; use the `weighted_balancer_setup` factory for other
    splits.
    """
    lp: Any
    base_tkn: Any   # ERC20 — the first token (matches lp.tkn_reserves order)
    opp_tkn: Any    # ERC20 — the second token
    lp_init_amt: float
    entry_base_amt: float
    entry_opp_amt: float
    base_weight: float


@dataclass
class StableswapSetup:
    """Canonical stableswap fixture state.

    2-asset pool (matches the scope of StableswapImpLoss). USER owns
    the full initial LP token supply minted by Join(USER, ampl).
    Balanced at entry — both reserves equal SS_BALANCE_EACH, so
    the implied alpha at construction is exactly 1.0.
    """
    lp: Any
    token0: Any   # ERC20 — first token in tkn_reserves insertion order
    token1: Any
    lp_init_amt: float
    entry_amounts: List[float]   # [SS_BALANCE_EACH, SS_BALANCE_EACH]
    A: int


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def v2_setup():
    """Fresh V2 LP at entry state. Function-scoped — each test gets a new pool."""
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory("ETH pool factory", "0x2")
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "LP", address = "0x011"
    )
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, ETH_AMT, DAI_AMT, ETH_AMT, DAI_AMT)

    lp_init_amt = lp.convert_to_human(lp.liquidity_providers[USER])

    return V2Setup(
        lp = lp,
        eth = eth,
        dai = dai,
        lp_init_amt = lp_init_amt,
        entry_x_amt = ETH_AMT,
        entry_y_amt = DAI_AMT,
    )


@pytest.fixture
def v3_setup():
    """Fresh V3 LP at entry state, full-range ticks. Function-scoped."""
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")

    factory = UniswapFactory("ETH pool factory", "0x2")
    exch_data = UniswapExchangeData(
        tkn0 = eth, tkn1 = dai, symbol = "LP", address = "0x011",
        version = 'V3', tick_spacing = V3_TICK_SPACING, fee = V3_FEE,
    )
    lp = factory.deploy(exch_data)

    lwr_tick = UniV3Utils.getMinTick(V3_TICK_SPACING)
    upr_tick = UniV3Utils.getMaxTick(V3_TICK_SPACING)

    Join().apply(lp, USER, ETH_AMT, DAI_AMT, lwr_tick, upr_tick)

    lp_init_amt = lp.convert_to_human(lp.liquidity_providers[USER])

    return V3Setup(
        lp = lp,
        eth = eth,
        dai = dai,
        lp_init_amt = lp_init_amt,
        entry_x_amt = ETH_AMT,
        entry_y_amt = DAI_AMT,
        lwr_tick = lwr_tick,
        upr_tick = upr_tick,
    )


@pytest.fixture
def balancer_setup():
    """Fresh Balancer LP at entry state, 50/50 ETH/DAI. Function-scoped.

    USER deposits ETH_AMT ETH and DAI_AMT DAI into the vault, then
    joins for BAL_POOL_SHARES_INIT pool shares. At this balanced entry
    state the pool's fee-free spot price (DAI per ETH) equals
    DAI_AMT / ETH_AMT — same as the V2/V3 fixtures, so cross-protocol
    tests can use matched entry compositions.
    """
    base = BERC20("ETH", "0xbal_eth")
    base.deposit(USER, ETH_AMT)
    opp = BERC20("DAI", "0xbal_dai")
    opp.deposit(USER, DAI_AMT)

    vault = BalancerVault()
    vault.add_token(base, BAL_DEFAULT_WEIGHT)
    vault.add_token(opp, 1.0 - BAL_DEFAULT_WEIGHT)

    factory = BalancerFactory("Balancer factory", "0xbal_factory")
    exch_data = BalancerExchangeData(
        vault = vault, symbol = "BPT", address = "0xbal_lp",
    )
    lp = factory.deploy(exch_data)
    BJoin().apply(lp, USER, BAL_POOL_SHARES_INIT)

    return BalancerSetup(
        lp = lp,
        base_tkn = base,
        opp_tkn = opp,
        lp_init_amt = BAL_POOL_SHARES_INIT,
        entry_base_amt = ETH_AMT,
        entry_opp_amt = DAI_AMT,
        base_weight = BAL_DEFAULT_WEIGHT,
    )


@pytest.fixture
def weighted_balancer_setup():
    """Factory fixture for non-50/50 Balancer pools.

    Returns a builder function that takes a base_weight and optional
    suffix (for address disambiguation when a test needs multiple
    pools in the same run). Callable from tests that want to
    parameterize over weighting.
    """
    def _build(base_weight, suffix = 'w'):
        base = BERC20("ETH", "0xbal_eth_{}".format(suffix))
        base.deposit(USER, ETH_AMT)
        opp = BERC20("DAI", "0xbal_dai_{}".format(suffix))
        opp.deposit(USER, DAI_AMT)

        vault = BalancerVault()
        vault.add_token(base, base_weight)
        vault.add_token(opp, 1.0 - base_weight)

        factory = BalancerFactory(
            "Balancer factory {}".format(suffix),
            "0xbal_factory_{}".format(suffix),
        )
        exch_data = BalancerExchangeData(
            vault = vault, symbol = "BPT_{}".format(suffix),
            address = "0xbal_lp_{}".format(suffix),
        )
        lp = factory.deploy(exch_data)
        BJoin().apply(lp, USER, BAL_POOL_SHARES_INIT)

        return BalancerSetup(
            lp = lp,
            base_tkn = base,
            opp_tkn = opp,
            lp_init_amt = BAL_POOL_SHARES_INIT,
            entry_base_amt = ETH_AMT,
            entry_opp_amt = DAI_AMT,
            base_weight = base_weight,
        )
    return _build


@pytest.fixture
def stableswap_setup():
    """Fresh stableswap LP at entry state, USDC/DAI balanced.
    Function-scoped.

    Amplification coefficient SS_DEFAULT_AMPL (=10). USER owns 100%
    of the LP token supply minted by Join.
    """
    t0 = SERC20("USDC", "0xss_usdc", 18)
    t0.deposit(USER, SS_BALANCE_EACH)
    t1 = SERC20("DAI", "0xss_dai", 18)
    t1.deposit(USER, SS_BALANCE_EACH)

    vault = StableswapVault()
    vault.add_token(t0)
    vault.add_token(t1)

    factory = StableswapFactory("Stableswap factory", "0xss_factory")
    exch_data = StableswapExchangeData(
        vault = vault, symbol = "CST", address = "0xss_lp",
    )
    lp = factory.deploy(exch_data)
    SJoin().apply(lp, USER, SS_DEFAULT_AMPL)

    # LP shares: read from the math_pool's tokens counter, converted
    # to human units (18 decimals).
    lp_init_amt = lp.dec2amt(lp.math_pool.tokens, 18)

    return StableswapSetup(
        lp = lp,
        token0 = t0,
        token1 = t1,
        lp_init_amt = lp_init_amt,
        entry_amounts = [SS_BALANCE_EACH, SS_BALANCE_EACH],
        A = SS_DEFAULT_AMPL,
    )


@pytest.fixture
def amplified_stableswap_setup():
    """Factory fixture for stableswap pools at arbitrary A.

    Returns a builder function accepting an amplification coefficient
    and optional suffix. Useful for tests that compare low-A vs
    high-A behavior (reachability, strong-negative-convexity demos).
    """
    def _build(ampl, suffix = 'a'):
        t0 = SERC20("USDC", "0xss_usdc_{}".format(suffix), 18)
        t0.deposit(USER, SS_BALANCE_EACH)
        t1 = SERC20("DAI", "0xss_dai_{}".format(suffix), 18)
        t1.deposit(USER, SS_BALANCE_EACH)

        vault = StableswapVault()
        vault.add_token(t0)
        vault.add_token(t1)

        factory = StableswapFactory(
            "Stableswap factory {}".format(suffix),
            "0xss_factory_{}".format(suffix),
        )
        exch_data = StableswapExchangeData(
            vault = vault, symbol = "CST_{}".format(suffix),
            address = "0xss_lp_{}".format(suffix),
        )
        lp = factory.deploy(exch_data)
        SJoin().apply(lp, USER, ampl)

        lp_init_amt = lp.dec2amt(lp.math_pool.tokens, 18)

        return StableswapSetup(
            lp = lp,
            token0 = t0,
            token1 = t1,
            lp_init_amt = lp_init_amt,
            entry_amounts = [SS_BALANCE_EACH, SS_BALANCE_EACH],
            A = ampl,
        )
    return _build
