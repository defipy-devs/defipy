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

"""Opt-in live-RPC verification for LiveProvider V2.

These tests hit a real Ethereum mainnet RPC. They are marked
`live_rpc` and skipped by default. To run them:

    DEFIPY_LIVE_RPC=https://your-rpc-url pytest -m live_rpc

The RPC URL must be set via the `DEFIPY_LIVE_RPC` environment
variable. Public RPCs (Alchemy / Infura free tiers) work; the test
reads at most a handful of slots per pool.

Tests are written defensively — they assert sane bounds (reserves
positive, decimals scaling correct, ratio in a wide range) rather
than exact values, since reserves change over time.

Canonical pool: WETH/USDC V2 (0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc)
per D6 in STATE_TWIN_PHASE_1_EXPANDED.md. WETH/USDC V2 has been the
most active V2 pool throughout the protocol's life — most likely to
still have meaningful liquidity in 2026.

Maintenance: if WETH/USDC V2 ever loses meaningful liquidity (unlikely
but possible), update WETH_USDC_V2 below to a still-active V2 pool
and adjust the assertion ranges accordingly.
"""

import os

import pytest

from defipy.twin import LiveProvider, V2PoolSnapshot, StateTwinBuilder
from defipy.primitives.pool_health import CheckPoolHealth


# Canonical Phase 1 smoke-test pool: WETH/USDC on Uniswap V2 mainnet.
# Token0 = USDC (6 decimals), token1 = WETH (18 decimals). Asymmetric
# decimals — the most informative test of correct scaling.
WETH_USDC_V2 = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
WETH_USDC_V2_POOL_ID = "uniswap_v2:" + WETH_USDC_V2


_RPC_ENV_VAR = "DEFIPY_LIVE_RPC"


def _get_rpc_or_skip():
    """Return RPC URL from env or skip the test."""
    url = os.environ.get(_RPC_ENV_VAR)
    if not url:
        pytest.skip(
            "Set {} to run live-RPC tests (e.g. "
            "DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key>)"
            .format(_RPC_ENV_VAR)
        )
    return url


@pytest.mark.live_rpc
def test_live_v2_weth_usdc_snapshot_constructs():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID)
    assert isinstance(snap, V2PoolSnapshot)
    assert snap.protocol == "uniswap_v2"


@pytest.mark.live_rpc
def test_live_v2_weth_usdc_token_symbols():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID)
    # USDC is token0 (lower address); WETH is token1.
    assert snap.token0_name == "USDC"
    assert snap.token1_name == "WETH"


@pytest.mark.live_rpc
def test_live_v2_weth_usdc_reserves_positive_and_scaled():
    """Reserves are positive and within realistic bounds.

    Tight enough to catch a wrong-decimals scaling (which would
    produce ratios like 1e12 or 1e-12) but loose enough not to flake
    on natural liquidity drift over years. WETH/USDC V2 has had
    tens of millions in TVL throughout its life; even a heavily
    drained pool will be in the tens of thousands at minimum.
    """
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID)
    assert snap.reserve0 > 0
    assert snap.reserve1 > 0

    # USDC is reserve0 (6 decimals), WETH is reserve1 (18 decimals).
    # If decimal scaling were wrong, USDC would be ~1e12 too large or
    # too small; WETH would be wildly off.
    # Sanity ranges that hold against any realistic liquidity state:
    assert 1e3 < snap.reserve0 < 1e10, (
        "USDC reserve {} is outside realistic bounds — likely a "
        "decimals-scaling bug.".format(snap.reserve0)
    )
    assert 1e-1 < snap.reserve1 < 1e7, (
        "WETH reserve {} is outside realistic bounds — likely a "
        "decimals-scaling bug.".format(snap.reserve1)
    )


@pytest.mark.live_rpc
def test_live_v2_snapshot_runs_through_check_pool_health():
    """End-to-end: real chain read → builder → primitive."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID)
    lp = StateTwinBuilder().build(snap)
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V2"
    assert health.reserve0 > 0
    assert health.reserve1 > 0


@pytest.mark.live_rpc
def test_live_v2_snapshot_at_specific_block():
    """Pinning to a historical block returns deterministic state.

    Block 19_500_000 (mid-2024) is a stable historical block. Reading
    the same block twice must produce identical snapshots — this
    proves block-pinning is honored.
    """
    rpc = _get_rpc_or_skip()
    block = 19_500_000

    s1 = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID, block_number=block)
    s2 = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID, block_number=block)
    assert s1.reserve0 == s2.reserve0
    assert s1.reserve1 == s2.reserve1
    assert s1.token0_name == s2.token0_name
    assert s1.token1_name == s2.token1_name


@pytest.mark.live_rpc
def test_live_v2_snapshot_populates_chain_context():
    """V2 LiveProvider's Phase 2 retrofit populates block_number,
    timestamp, and chain_id on the snapshot."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(WETH_USDC_V2_POOL_ID)
    assert snap.block_number is not None
    assert snap.block_number > 19_000_000   # post-2024
    assert snap.timestamp is not None
    assert snap.timestamp > 1_700_000_000   # post-Nov 2023
    assert snap.chain_id == 1                # Ethereum mainnet
