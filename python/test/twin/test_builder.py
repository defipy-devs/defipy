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

from uniswappy.cpt.exchg import UniswapExchange, UniswapV3Exchange
from balancerpy.cwpt.exchg import BalancerExchange
from stableswappy.cst.exchg import StableswapExchange

from defipy.twin import (
    StateTwinBuilder,
    V2PoolSnapshot, V3PoolSnapshot,
    BalancerPoolSnapshot, StableswapPoolSnapshot,
)


# ─── Type dispatch ──────────────────────────────────────────────────────────


def test_builder_returns_uniswap_exchange_for_v2():
    snap = V2PoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    lp = StateTwinBuilder().build(snap)
    assert isinstance(lp, UniswapExchange)


def test_builder_returns_uniswapv3_exchange_for_v3():
    snap = V3PoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    lp = StateTwinBuilder().build(snap)
    assert isinstance(lp, UniswapV3Exchange)


def test_builder_returns_balancer_exchange_for_balancer():
    snap = BalancerPoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    lp = StateTwinBuilder().build(snap)
    assert isinstance(lp, BalancerExchange)


def test_builder_returns_stableswap_exchange_for_stableswap():
    snap = StableswapPoolSnapshot(
        pool_id = "t", token_names = ["USDC", "DAI"],
        reserves = [100000, 100000], A = 10,
    )
    lp = StateTwinBuilder().build(snap)
    assert isinstance(lp, StableswapExchange)


def test_builder_rejects_unknown_snapshot_type():
    class BogusSnapshot:
        pass
    with pytest.raises(TypeError) as excinfo:
        StateTwinBuilder().build(BogusSnapshot())
    assert "unknown snapshot type" in str(excinfo.value).lower()


# ─── Reserves consistency ───────────────────────────────────────────────────
# Built lp must have the same reserves that the fixture fixture produces
# for the same inputs. Critical guardrail against silent divergence.


def test_v2_built_lp_reserves_match_fixture(v2_setup):
    snap = V2PoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    built = StateTwinBuilder().build(snap)

    fixture_eth = v2_setup.eth
    fixture_dai = v2_setup.dai

    built_tokens = built.factory.token_from_exchange[built.name]
    built_eth = built_tokens[built.token0]
    built_dai = built_tokens[built.token1]

    assert built.get_reserve(built_eth) == v2_setup.lp.get_reserve(fixture_eth)
    assert built.get_reserve(built_dai) == v2_setup.lp.get_reserve(fixture_dai)
    assert built.total_supply == v2_setup.lp.total_supply


def test_v3_built_lp_reserves_match_fixture(v3_setup):
    snap = V3PoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    built = StateTwinBuilder().build(snap)

    fixture_eth = v3_setup.eth
    fixture_dai = v3_setup.dai

    built_tokens = built.factory.token_from_exchange[built.name]
    built_eth = built_tokens[built.token0]
    built_dai = built_tokens[built.token1]

    assert built.get_reserve(built_eth) == v3_setup.lp.get_reserve(fixture_eth)
    assert built.get_reserve(built_dai) == v3_setup.lp.get_reserve(fixture_dai)
    assert built.get_liquidity() == v3_setup.lp.get_liquidity()
    assert built.total_supply == v3_setup.lp.total_supply


def test_balancer_built_lp_reserves_match_fixture(balancer_setup):
    snap = BalancerPoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
        weight0 = 0.5, weight1 = 0.5,
        pool_shares_init = 100.0,
    )
    built = StateTwinBuilder().build(snap)

    assert dict(built.tkn_reserves) == dict(balancer_setup.lp.tkn_reserves)
    assert float(built.tkn_weights["ETH"]) == pytest.approx(
        float(balancer_setup.lp.tkn_weights["ETH"])
    )


def test_stableswap_built_lp_reserves_match_fixture(stableswap_setup):
    snap = StableswapPoolSnapshot(
        pool_id = "t",
        token_names = ["USDC", "DAI"],
        reserves = [100000, 100000],
        A = 10,
    )
    built = StateTwinBuilder().build(snap)

    assert dict(built.tkn_reserves) == dict(stableswap_setup.lp.tkn_reserves)
    assert int(built.math_pool.A) == int(stableswap_setup.lp.math_pool.A)
    # At-peg pool: dydx ≈ 1.0 on both sides.
    assert built.math_pool.dydx(0, 1, use_fee = False) == pytest.approx(
        stableswap_setup.lp.math_pool.dydx(0, 1, use_fee = False)
    )


# ─── Spot price consistency ─────────────────────────────────────────────────


def test_v2_built_lp_spot_price_matches_reserve_ratio():
    snap = V2PoolSnapshot(
        pool_id = "t", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    built = StateTwinBuilder().build(snap)

    tokens = built.factory.token_from_exchange[built.name]
    eth = tokens[built.token0]

    # lp.get_price(token0) returns reserve1/reserve0 (price of token0 in
    # token1 units). Must match the reserve ratio directly.
    assert built.get_price(eth) == pytest.approx(100000 / 1000)
