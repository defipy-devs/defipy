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

import pytest

from defipy.twin import (
    MockProvider,
    StateTwinBuilder,
    V2PoolSnapshot, V3PoolSnapshot,
    BalancerPoolSnapshot, StableswapPoolSnapshot,
)

from defipy.primitives.pool_health import CheckPoolHealth


EXPECTED_RECIPES = {
    "eth_dai_v2",
    "eth_dai_v3",
    "eth_dai_balancer_50_50",
    "usdc_dai_stableswap_A10",
}


# ─── list_recipes ──────────────────────────────────────────────────────────


def test_list_recipes_returns_sorted_four_names():
    names = MockProvider().list_recipes()
    assert set(names) == EXPECTED_RECIPES
    assert names == sorted(names)
    assert len(names) == 4


# ─── Per-recipe snapshot ────────────────────────────────────────────────────


def test_eth_dai_v2_recipe():
    snap = MockProvider().snapshot("eth_dai_v2")
    assert isinstance(snap, V2PoolSnapshot)
    assert snap.reserve0 == 1000.0
    assert snap.reserve1 == 100000.0
    assert snap.token0_name == "ETH"
    assert snap.token1_name == "DAI"
    assert snap.protocol == "uniswap_v2"


def test_eth_dai_v3_recipe():
    snap = MockProvider().snapshot("eth_dai_v3")
    assert isinstance(snap, V3PoolSnapshot)
    assert snap.reserve0 == 1000.0
    assert snap.reserve1 == 100000.0
    assert snap.fee == 3000
    assert snap.tick_spacing == 60
    assert snap.lwr_tick < snap.upr_tick


def test_eth_dai_balancer_50_50_recipe():
    snap = MockProvider().snapshot("eth_dai_balancer_50_50")
    assert isinstance(snap, BalancerPoolSnapshot)
    assert snap.weight0 == 0.5
    assert snap.weight1 == 0.5
    assert snap.reserve0 == 1000.0
    assert snap.reserve1 == 100000.0


def test_usdc_dai_stableswap_A10_recipe():
    snap = MockProvider().snapshot("usdc_dai_stableswap_A10")
    assert isinstance(snap, StableswapPoolSnapshot)
    assert snap.A == 10
    assert snap.token_names == ["USDC", "DAI"]
    assert snap.reserves == [100000.0, 100000.0]


# ─── Error path + freshness ─────────────────────────────────────────────────


def test_unknown_recipe_raises_with_available_list():
    with pytest.raises(ValueError) as excinfo:
        MockProvider().snapshot("bogus_pool")
    msg = str(excinfo.value)
    assert "bogus_pool" in msg
    # Message should surface the available recipes so callers can
    # correct their input without digging through docs.
    for name in EXPECTED_RECIPES:
        assert name in msg


def test_recipes_produce_fresh_snapshots():
    # Mutating one snapshot must not affect the next call.
    p = MockProvider()
    s1 = p.snapshot("eth_dai_v2")
    s1.reserve0 = 99999.0
    s2 = p.snapshot("eth_dai_v2")
    assert s2.reserve0 == 1000.0
    assert s1 is not s2


# ─── End-to-end provider → builder → primitive ──────────────────────────────


@pytest.mark.parametrize("recipe", sorted(EXPECTED_RECIPES))
def test_recipe_builds_lp_that_is_usable(recipe):
    snap = MockProvider().snapshot(recipe)
    lp = StateTwinBuilder().build(snap)
    assert lp is not None


def test_v2_recipe_check_pool_health():
    lp = StateTwinBuilder().build(MockProvider().snapshot("eth_dai_v2"))
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V2"
    assert health.reserve0 == 1000.0
    assert health.reserve1 == 100000.0


def test_v3_recipe_check_pool_health():
    lp = StateTwinBuilder().build(MockProvider().snapshot("eth_dai_v3"))
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V3"
    assert health.reserve0 == 1000.0
    assert health.reserve1 == 100000.0
