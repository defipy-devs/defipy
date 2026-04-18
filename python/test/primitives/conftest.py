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
from typing import Any

import pytest

from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.utils.tools.v3 import UniV3Utils
from uniswappy.process.join import Join


# ─── Canonical test constants ────────────────────────────────────────────────
USER = "user0"
ETH_AMT = 1000.0
DAI_AMT = 100000.0

# V3 defaults — 0.3% fee tier, tick spacing 60 (matches most mainnet pools)
V3_TICK_SPACING = 60
V3_FEE = 3000


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
