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

"""Opt-in live-RPC verification for LiveProvider Stableswap (v2.2 Phase 3).

These tests hit a real Ethereum mainnet RPC. They are marked
`live_rpc` and skipped by default. To run them:

    DEFIPY_LIVE_RPC=https://your-rpc-url pytest -m live_rpc

Assertions are defensive — sane bounds rather than exact values.

Canonical pool: Curve DAI/USDC/USDT 3pool
(0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7) — the archetypal plain
Stableswap pool.

Note on primitives: AnalyzeStableswapPosition / AssessDepegRisk are
2-asset only in v2.2 (StableswapImpLoss scope); extending them to
N-coin pools is v2.3 work (see the spec). So the 3pool twin's "sane
output" is verified here through its native StableswapExchange methods
(get_price / get_reserve), not through the 2-asset position primitives.
"""

import os

import pytest

from defipy.twin import LiveProvider, StableswapPoolSnapshot, StateTwinBuilder


CURVE_3POOL = "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
CURVE_3POOL_ID = "stableswap:" + CURVE_3POOL

# 3pool coins, in coin-index order (DAI 18dec, USDC 6dec, USDT 6dec).
EXPECTED_COINS = ["DAI", "USDC", "USDT"]


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
def test_live_stableswap_3pool_snapshot_constructs():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    assert isinstance(snap, StableswapPoolSnapshot)
    assert snap.protocol == "stableswap"


@pytest.mark.live_rpc
def test_live_stableswap_3pool_resolves_three_coins():
    """The coin-count probe (no n_coins hint) resolves exactly 3 coins,
    in DAI/USDC/USDT order."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    assert len(snap.token_names) == 3
    assert snap.token_names == EXPECTED_COINS


@pytest.mark.live_rpc
def test_live_stableswap_n_coins_hint_matches_probe():
    """Passing n_coins=3 (fast path) yields the same coins as the probe."""
    rpc = _get_rpc_or_skip()
    probed = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    hinted = LiveProvider(rpc).snapshot(CURVE_3POOL_ID, n_coins=3)
    assert hinted.token_names == probed.token_names


@pytest.mark.live_rpc
def test_live_stableswap_A_in_expected_range():
    """3pool amplification coefficient (human A) sits in a plausible
    range. A() not A_precise()."""
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    assert isinstance(snap.A, int)
    assert 10 <= snap.A <= 50_000


@pytest.mark.live_rpc
def test_live_stableswap_reserves_positive_and_scaled():
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    assert len(snap.reserves) == 3
    for r in snap.reserves:
        assert r > 0
        # Decimal-scaled to human units; raw (6/18-dec) would be >> 1e9.
        assert r < 1e12


@pytest.mark.live_rpc
def test_live_stableswap_snapshot_at_specific_block():
    """Pinning to a historical block is deterministic across both the
    probe and the main read."""
    rpc = _get_rpc_or_skip()
    block = 19_500_000
    s1 = LiveProvider(rpc).snapshot(CURVE_3POOL_ID, block_number=block)
    s2 = LiveProvider(rpc).snapshot(CURVE_3POOL_ID, block_number=block)
    assert s1.token_names == s2.token_names
    assert s1.reserves == s2.reserves
    assert s1.A == s2.A
    assert s1.block_number == s2.block_number == block
    assert s1.timestamp is not None
    assert s1.chain_id == 1


@pytest.mark.live_rpc
def test_live_stableswap_twin_builds_and_prices_near_peg():
    """End-to-end: real read → builder → a working stableswappy twin.

    The 3pool is near-peg, so the twin's pairwise spot prices sit close
    to 1.0 and every reserve is positive. Exercised via the twin's
    native StableswapExchange methods (the 2-asset position primitives
    don't apply to a 3-coin pool — v2.3).
    """
    rpc = _get_rpc_or_skip()
    snap = LiveProvider(rpc).snapshot(CURVE_3POOL_ID)
    lp = StateTwinBuilder().build(snap)
    tokens = lp.factory.token_from_exchange[lp.name]
    for name in EXPECTED_COINS:
        assert lp.get_reserve(tokens[name]) > 0
    # DAI/USDC and DAI/USDT spot prices near parity.
    assert lp.get_price(tokens["DAI"], tokens["USDC"]) == pytest.approx(
        1.0, abs=0.05,
    )
    assert lp.get_price(tokens["DAI"], tokens["USDT"]) == pytest.approx(
        1.0, abs=0.05,
    )
