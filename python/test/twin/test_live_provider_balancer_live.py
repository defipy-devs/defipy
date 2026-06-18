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

"""Opt-in live-RPC verification for LiveProvider Balancer (v2.2 Phase 2).

These tests hit a real Ethereum mainnet RPC. They are marked
`live_rpc` and skipped by default. To run them:

    DEFIPY_LIVE_RPC=https://your-rpc-url pytest -m live_rpc

Assertions are defensive — sane bounds rather than exact values, since
reserves change every block.

Canonical pool: BAL/WETH 80/20 weighted pool
(0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56) — the archetypal Balancer
V2 weighted (non-50/50) pool, deep and long-running.
"""

import os

import pytest

from defipy.twin import LiveProvider, BalancerPoolSnapshot, StateTwinBuilder
from defipy.primitives.position import AnalyzeBalancerPosition
from defipy.utils.data import BalancerPositionAnalysis


BAL_WETH_80_20 = "0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56"
BAL_WETH_POOL_ID = "balancer:" + BAL_WETH_80_20


_RPC_ENV_VAR = "DEFIPY_LIVE_RPC"


def _get_rpc_or_skip():
    url = os.environ.get(_RPC_ENV_VAR)
    if not url:
        pytest.skip(
            "Set {} to run live-RPC tests (e.g. "
            "DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key>)"
            .format(_RPC_ENV_VAR)
        )
    return url


@pytest.mark.live_rpc
def test_live_balancer_snapshot_constructs():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID)
    assert isinstance(snap, BalancerPoolSnapshot)
    assert snap.protocol == "balancer"


@pytest.mark.live_rpc
def test_live_balancer_token_symbols():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID)
    # token0 = BAL (lower address), token1 = WETH.
    assert snap.token0_name == "BAL"
    assert snap.token1_name == "WETH"


@pytest.mark.live_rpc
def test_live_balancer_weights_sum_to_one():
    """80/20 pool — weights are positive, sum to 1, and reflect the
    non-50/50 split."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID)
    assert snap.weight0 > 0
    assert snap.weight1 > 0
    assert snap.weight0 + snap.weight1 == pytest.approx(1.0, abs=1e-9)
    # The 80/20 pool's BAL weight is the larger of the two.
    assert snap.weight0 == pytest.approx(0.8, abs=1e-6)
    assert snap.weight1 == pytest.approx(0.2, abs=1e-6)


@pytest.mark.live_rpc
def test_live_balancer_reserves_positive_and_scaled():
    """Reserves are positive and decimal-scaled to human units."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID)
    assert snap.reserve0 > 0
    assert snap.reserve1 > 0
    # Both tokens are 18-decimal; raw balances would be > 1e18. Decimal
    # scaling keeps them in human range.
    assert snap.reserve0 < 1e12
    assert snap.reserve1 < 1e12


@pytest.mark.live_rpc
def test_live_balancer_snapshot_at_specific_block():
    """Pinning to a historical block produces deterministic snapshots.

    Reading the same block twice must yield identical reserves and
    weights — proves block-pinning holds across both round trips.
    """
    rpc = _get_rpc_or_skip()
    block = 19_500_000
    s1 = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID, block_number=block)
    s2 = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID, block_number=block)
    assert s1.reserve0 == s2.reserve0
    assert s1.reserve1 == s2.reserve1
    assert s1.weight0 == s2.weight0
    assert s1.weight1 == s2.weight1
    assert s1.block_number == s2.block_number == block
    assert s1.timestamp is not None
    assert s1.chain_id == 1


@pytest.mark.live_rpc
def test_live_balancer_runs_through_analyze_position():
    """End-to-end: real chain read → builder → AnalyzeBalancerPosition.

    Analyzed at the built twin's entry composition (reserves as entry
    amounts, the default pool_shares_init), so impermanent loss is ~0
    and alpha ~1. The point is that the primitive produces a sane,
    typed result against a live-read twin.
    """
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(BAL_WETH_POOL_ID)
    lp = StateTwinBuilder().build(snap)
    result = AnalyzeBalancerPosition().apply(
        lp,
        snap.pool_shares_init,
        snap.reserve0,
        snap.reserve1,
    )
    assert isinstance(result, BalancerPositionAnalysis)
    assert isinstance(result.current_value, float)
    assert result.current_value > 0
    assert result.base_tkn_name == "BAL"
    assert result.opp_tkn_name == "WETH"
    # At entry composition, IL is ~0.
    assert result.il_percentage == pytest.approx(0.0, abs=1e-6)
