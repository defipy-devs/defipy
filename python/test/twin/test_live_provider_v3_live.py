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

"""Opt-in live-RPC verification for LiveProvider V3 (Phase 2).

These tests hit a real Ethereum mainnet RPC. They are marked
`live_rpc` and skipped by default. To run them:

    DEFIPY_LIVE_RPC=https://your-rpc-url pytest -m live_rpc

The RPC URL must be set via the `DEFIPY_LIVE_RPC` environment
variable. Public RPCs (Alchemy / Infura free tiers) work; the test
reads at most one Multicall3.aggregate3 round trip per snapshot.

Tests are written defensively — assert sane bounds rather than exact
values, since reserves change every block.

Canonical pool: USDC/WETH V3 0.3% fee tier
(0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640) per the Phase 2 EXPANDED
brief. Long-running pool with deep liquidity, mixed decimals.
"""

import os

import pytest

from defipy.twin import LiveProvider, V3PoolSnapshot, StateTwinBuilder
from defipy.primitives.pool_health import CheckPoolHealth


USDC_WETH_V3_3000 = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
USDC_WETH_V3_3000_POOL_ID = "uniswap_v3:" + USDC_WETH_V3_3000


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
def test_live_v3_usdc_weth_snapshot_constructs():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(USDC_WETH_V3_3000_POOL_ID)
    assert isinstance(snap, V3PoolSnapshot)
    assert snap.protocol == "uniswap_v3"
    assert snap.fee == 3000
    assert snap.tick_spacing == 60


@pytest.mark.live_rpc
def test_live_v3_usdc_weth_token_symbols():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(USDC_WETH_V3_3000_POOL_ID)
    assert snap.token0_name == "USDC"
    assert snap.token1_name == "WETH"


@pytest.mark.live_rpc
def test_live_v3_reserves_positive_and_scaled():
    """Full-range default reserves are positive and decimal-scaled.

    Loose bounds — V3 active liquidity at full range produces large
    notional amounts. The point is to catch a missing decimal scale
    (which would surface as 10^12+ values), not to pin a specific
    reserve quote.
    """
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(USDC_WETH_V3_3000_POOL_ID)
    assert snap.reserve0 > 0
    assert snap.reserve1 > 0
    # Without decimal scaling, raw reserves would be > 1e15 for any
    # realistic L. Decimal-scaled: USDC and WETH stay in human range.
    assert snap.reserve0 < 1e15
    assert snap.reserve1 < 1e15


@pytest.mark.live_rpc
def test_live_v3_snapshot_runs_through_check_pool_health():
    """End-to-end: real chain read → builder → primitive."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(USDC_WETH_V3_3000_POOL_ID)
    lp = StateTwinBuilder().build(snap)
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V3"


@pytest.mark.live_rpc
def test_live_v3_snapshot_at_specific_block():
    """Pinning to a historical block produces deterministic snapshots.

    Block 19_500_000 (mid-2024) is stable historical state. Reading
    the same block twice must produce identical reserves and ticks —
    proves block-pinning is honored across the multicall.
    """
    rpc = _get_rpc_or_skip()
    block = 19_500_000
    s1 = LiveProvider(rpc).snapshot(
        USDC_WETH_V3_3000_POOL_ID, block_number=block,
    )
    s2 = LiveProvider(rpc).snapshot(
        USDC_WETH_V3_3000_POOL_ID, block_number=block,
    )
    assert s1.reserve0 == s2.reserve0
    assert s1.reserve1 == s2.reserve1
    assert s1.fee == s2.fee
    assert s1.tick_spacing == s2.tick_spacing
    assert s1.block_number == s2.block_number == block
    # Enrichment populated.
    assert s1.timestamp is not None
    assert s1.chain_id == 1
