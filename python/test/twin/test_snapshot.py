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
    V2PoolSnapshot,
    V3PoolSnapshot,
    BalancerPoolSnapshot,
    StableswapPoolSnapshot,
)


# ─── V2 snapshot ────────────────────────────────────────────────────────────


def test_v2_snapshot_construction():
    s = V2PoolSnapshot(
        pool_id = "p",
        token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    assert s.reserve0 == 1000
    assert s.reserve1 == 100000
    assert s.token0_name == "ETH"


def test_v2_snapshot_sets_protocol():
    s = V2PoolSnapshot(
        pool_id = "p", token0_name = "A", token1_name = "B",
        reserve0 = 1, reserve1 = 1,
    )
    assert s.protocol == "uniswap_v2"


# ─── V3 snapshot ────────────────────────────────────────────────────────────


def test_v3_snapshot_full_range_defaults():
    s = V3PoolSnapshot(
        pool_id = "p", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
    )
    # Defaults: fee 3000 (0.3%), tick_spacing 60, full-range ticks computed.
    assert s.fee == 3000
    assert s.tick_spacing == 60
    assert s.lwr_tick is not None
    assert s.upr_tick is not None
    assert s.lwr_tick < s.upr_tick


def test_v3_snapshot_sets_protocol():
    s = V3PoolSnapshot(
        pool_id = "p", token0_name = "A", token1_name = "B",
        reserve0 = 1, reserve1 = 1,
    )
    assert s.protocol == "uniswap_v3"


def test_v3_snapshot_rejects_inverted_tick_range():
    with pytest.raises(ValueError) as excinfo:
        V3PoolSnapshot(
            pool_id = "p", token0_name = "A", token1_name = "B",
            reserve0 = 1, reserve1 = 1,
            lwr_tick = 100, upr_tick = 50,
        )
    assert "lwr_tick" in str(excinfo.value)


def test_v3_snapshot_accepts_custom_ticks():
    s = V3PoolSnapshot(
        pool_id = "p", token0_name = "A", token1_name = "B",
        reserve0 = 1, reserve1 = 1,
        lwr_tick = -600, upr_tick = 600,
    )
    assert s.lwr_tick == -600
    assert s.upr_tick == 600


# ─── Balancer snapshot ──────────────────────────────────────────────────────


def test_balancer_snapshot_construction():
    s = BalancerPoolSnapshot(
        pool_id = "p", token0_name = "ETH", token1_name = "DAI",
        reserve0 = 1000, reserve1 = 100000,
        weight0 = 0.5, weight1 = 0.5,
    )
    assert s.weight0 == 0.5
    assert s.pool_shares_init == 100.0  # default


def test_balancer_snapshot_sets_protocol():
    s = BalancerPoolSnapshot(
        pool_id = "p", token0_name = "A", token1_name = "B",
        reserve0 = 1, reserve1 = 1,
    )
    assert s.protocol == "balancer"


def test_balancer_snapshot_rejects_bad_weights():
    with pytest.raises(ValueError) as excinfo:
        BalancerPoolSnapshot(
            pool_id = "p", token0_name = "A", token1_name = "B",
            reserve0 = 1, reserve1 = 1,
            weight0 = 0.6, weight1 = 0.3,  # sums to 0.9
        )
    assert "weight" in str(excinfo.value).lower()


def test_balancer_snapshot_accepts_80_20():
    s = BalancerPoolSnapshot(
        pool_id = "p", token0_name = "A", token1_name = "B",
        reserve0 = 1, reserve1 = 1,
        weight0 = 0.8, weight1 = 0.2,
    )
    assert s.weight0 == 0.8


# ─── Stableswap snapshot ────────────────────────────────────────────────────


def test_stableswap_snapshot_construction():
    s = StableswapPoolSnapshot(
        pool_id = "p",
        token_names = ["USDC", "DAI"],
        reserves = [100000, 100000],
        A = 10,
    )
    assert s.A == 10
    assert s.token_names == ["USDC", "DAI"]


def test_stableswap_snapshot_sets_protocol():
    s = StableswapPoolSnapshot(
        pool_id = "p",
        token_names = ["A", "B"],
        reserves = [1, 1],
    )
    assert s.protocol == "stableswap"


def test_stableswap_snapshot_rejects_mismatched_lengths():
    with pytest.raises(ValueError) as excinfo:
        StableswapPoolSnapshot(
            pool_id = "p",
            token_names = ["USDC", "DAI", "USDT"],
            reserves = [1, 1],  # 2 != 3
        )
    assert "length" in str(excinfo.value).lower()


def test_stableswap_snapshot_rejects_non_2_asset():
    with pytest.raises(ValueError) as excinfo:
        StableswapPoolSnapshot(
            pool_id = "p",
            token_names = ["USDC", "DAI", "USDT"],
            reserves = [1, 1, 1],
        )
    assert "2" in str(excinfo.value)
