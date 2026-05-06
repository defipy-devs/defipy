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

"""Mocked-RPC unit tests for LiveProvider V3 (Phase 2).

Tests below correspond to the test enumeration in
STATE_TWIN_PHASE_2_EXPANDED.md, "Concrete test surface for
test_live_provider_v3.py". Section headers match the brief.

Test infrastructure: see python/test/twin/_fake_rpc.py for the
FakeRpcClient + V3 surface (V3PoolSpec, _V3PoolFunctions,
_MulticallFunctions). All tests inject a fake via
`LiveProvider._with_client(fake)`; production flow is exercised
end-to-end through the Multicall3 path. No network, no real web3.

Live-RPC verification of the same surface lives in
test_live_provider_v3_live.py (gated by the `live_rpc` marker).
"""

import pytest

from defipy.twin import (
    LiveProvider,
    StateTwinBuilder,
    V3PoolSnapshot,
    MockProvider,
)
from defipy.primitives.pool_health import CheckPoolHealth
from defipy.primitives.position import AnalyzePosition

from twin._fake_rpc import (
    V3PoolSpec, V2PoolSpec, TokenSpec,
    build_fake_client,
    canonical_usdc_weth_v3_spec,
    canonical_usdc_weth_v3_token_specs,
    USDC_WETH_V3_3000_POOL,
    USDC_ADDRESS, WETH_ADDRESS,
)


def _v3_pool_id(addr: str = USDC_WETH_V3_3000_POOL) -> str:
    return "uniswap_v3:{}".format(addr)


# ─── V3 snapshot construction ───────────────────────────────────────────────


# Test 1
def test_v3_snapshot_returns_v3_pool_snapshot():
    """provider.snapshot('uniswap_v3:0xPOOL') returns a V3PoolSnapshot
    (not V2). Distinguishes the V3 path from V2 by type discriminator."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    assert isinstance(snap, V3PoolSnapshot)
    assert snap.protocol == "uniswap_v3"


# Test 2
def test_v3_snapshot_default_full_range_ticks():
    """Without lwr_tick/upr_tick kwargs, snapshot ticks default to
    full-range per the pool's tick_spacing. Matches MockProvider's
    eth_dai_v3 default. Per D13."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(tick_spacing=60),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    from uniswappy.utils.tools.v3 import UniV3Utils
    assert snap.lwr_tick == UniV3Utils.getMinTick(60)
    assert snap.upr_tick == UniV3Utils.getMaxTick(60)


# Test 3
def test_v3_snapshot_caller_provided_ticks():
    """Explicit lwr_tick / upr_tick kwargs override the full-range
    default. Reserves are derived for the caller's range."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(
        _v3_pool_id(), lwr_tick=-600, upr_tick=600,
    )
    assert snap.lwr_tick == -600
    assert snap.upr_tick == 600


# Test 4
def test_v3_snapshot_reserves_decimal_adjusted():
    """For a known sqrtPriceX96 + L combination, reserves come out as
    decimal-adjusted floats (raw / 10**decimals). D15 contract."""
    # Pick sqrt_price_x96 mid-range + a moderate liquidity. The exact
    # numeric values matter less than the "decimal-adjusted, finite,
    # nonzero" property — V3 math has many input combinations that
    # produce reasonable outputs.
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(
            sqrt_price_x96 = 1_366_488_517_146_854_400_000_000_000_000,
            liquidity = 10_000_000_000_000_000_000_000,
            tick_spacing = 60,
        ),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    # Both reserves > 0 (in-range) and decimal-adjusted (i.e. not raw).
    # Raw values for liquidity=1e22 would be in the 1e22 range; decimal
    # USDC (6dec) and WETH (18dec) are O(millions / thousands).
    assert snap.reserve0 > 0
    assert snap.reserve1 > 0
    assert snap.reserve0 < 1e15   # USDC reserves: nowhere near raw 1e22
    assert snap.reserve1 < 1e10   # WETH reserves: ditto


# Test 5
def test_v3_snapshot_handles_mixed_decimals():
    """USDC (6) / WETH (18) — reserves come out in human-readable units
    regardless of decimal mismatch. Same shape as the V2 mixed-decimals
    test."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    assert snap.token0_name == "USDC"
    assert snap.token1_name == "WETH"
    # If decimal adjustment were skipped, reserves would be in raw
    # uint scale (typically 10^18+ for L=1e22). Decimal-adjusted
    # reserves should be many orders of magnitude smaller — assert
    # the upper bound only (the math itself is exercised in test 4).
    assert snap.reserve0 < 1e15
    assert snap.reserve1 < 1e15


# ─── V3 read pattern ────────────────────────────────────────────────────────


# Test 6
def test_v3_snapshot_reads_slot0_and_liquidity():
    """slot0 and liquidity reads happen during the multicall."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_v3_pool_id())
    fns = {rec.function for rec in client.call_log}
    assert "slot0" in fns
    assert "liquidity" in fns


# Test 7
def test_v3_snapshot_reads_fee_and_tick_spacing():
    """fee + tickSpacing reads happen and land in the snapshot
    directly (not derived)."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(fee=500, tick_spacing=10),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    assert snap.fee == 500
    assert snap.tick_spacing == 10


# Test 8
def test_v3_snapshot_reads_token_addresses_and_metadata():
    """token0/token1 reads happen via multicall; FetchToken pulls
    symbols + decimals separately and lands in the snapshot."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    assert snap.token0_name == "USDC"
    assert snap.token1_name == "WETH"
    fns = {rec.function for rec in client.call_log}
    assert "token0" in fns
    assert "token1" in fns
    # FetchToken makes a direct symbol() / decimals() read against
    # each token contract — separate from the multicall.
    assert "symbol" in fns
    assert "decimals" in fns


# Test 9
def test_v3_active_tick_at_range_boundary_produces_single_sided():
    """When sqrt_current is below sqrt(getSqrtRatioAtTick(lwr_tick)),
    the position is single-sided in token0 (reserve1 == 0). When
    above, single-sided in token1 (reserve0 == 0). R14 contract."""
    from uniswappy.utils.tools.v3 import TickMath

    # Below lower tick: all in token0 (USDC).
    sqrt_below = int(TickMath.getSqrtRatioAtTick(-1000))
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(
            sqrt_price_x96 = sqrt_below - 1,
            tick = -1001,
        ),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(
        _v3_pool_id(), lwr_tick=-1000, upr_tick=1000,
    )
    assert snap.reserve1 == 0.0
    assert snap.reserve0 > 0.0

    # Above upper tick: all in token1 (WETH).
    sqrt_above = int(TickMath.getSqrtRatioAtTick(1000))
    client2 = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(
            sqrt_price_x96 = sqrt_above + 1,
            tick = 1001,
        ),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap2 = LiveProvider._with_client(client2).snapshot(
        _v3_pool_id(), lwr_tick=-1000, upr_tick=1000,
    )
    assert snap2.reserve0 == 0.0
    assert snap2.reserve1 > 0.0


# ─── Multicall batching ─────────────────────────────────────────────────────


# Test 10
def test_v3_snapshot_uses_multicall():
    """Inspecting client.call_log shows ONE aggregate3 call against
    the Multicall3 address — not 6+ separate calls against the pool."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_v3_pool_id())
    aggregate3_calls = [
        rec for rec in client.call_log if rec.function == "aggregate3"
    ]
    assert len(aggregate3_calls) == 1


# Test 11
def test_v3_multicall_pin_to_block():
    """Every sub-call inside the multicall pins to the resolved block.
    Same R1 discipline as Phase 1 V2."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
        latest_block=20_500_000,
    )
    LiveProvider._with_client(client).snapshot(_v3_pool_id())
    # All multicall sub-call records should share the same block.
    multicall_records = [
        rec for rec in client.call_log
        if rec.function in {
            "aggregate3", "token0", "token1", "slot0",
            "liquidity", "fee", "tickSpacing", "getCurrentBlockTimestamp",
        }
    ]
    block_ids = {rec.block_identifier for rec in multicall_records}
    assert block_ids == {20_500_000}


# Test 12
def test_v3_multicall_block_timestamp_via_getCurrentBlockTimestamp():
    """The multicall batch includes a getCurrentBlockTimestamp() call
    against Multicall3; the response populates the snapshot's
    timestamp field. Verifies C8."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
        block_timestamp=1_700_000_000,
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    fns = {rec.function for rec in client.call_log}
    assert "getCurrentBlockTimestamp" in fns
    assert snap.timestamp == 1_700_000_000


# Test 13
def test_v3_multicall_partial_failure_propagates():
    """When the multicall returns success=False for any sub-call (or
    a downstream read on returned data fails), the snapshot fails
    loudly per D7 (allowFailure=False)."""
    # Trigger by registering tokens that don't match the pool's
    # token0/token1 — multicall returns the pool's token0_address,
    # but FetchToken on that unregistered address raises during the
    # post-multicall metadata read step.
    pool = canonical_usdc_weth_v3_spec()
    # Register pool but only ONE matching token spec (token1 is
    # legitimately registered; token0 is not). build_fake_client's
    # sanity check would normally reject this — bypass by mounting
    # the spec manually.
    from twin._fake_rpc import (
        FakeWeb3, FakeRpcClient, V3PoolSpec, TokenSpec,
        WETH_ADDRESS,
    )
    fake = FakeWeb3(latest_block=19_500_000, chain_id=1, block_timestamp=1_700_000_000)
    fake._pool_specs[pool.address] = pool
    # Only register token1 (WETH); token0 (USDC) is intentionally absent.
    fake._token_specs[WETH_ADDRESS] = TokenSpec(
        address=WETH_ADDRESS, symbol="WETH", decimals=18,
    )
    client = FakeRpcClient(fake)
    with pytest.raises(Exception):
        LiveProvider._with_client(client).snapshot(_v3_pool_id())


# ─── MockProvider parity ────────────────────────────────────────────────────


# Test 14
def test_v3_live_twin_matches_mock_twin_at_known_state():
    """Live V3 twin for a controlled (sqrtPriceX96, L) configuration
    builds successfully through the V3 builder path — same downstream
    contract as MockProvider's eth_dai_v3."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    live_snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    live_lp = StateTwinBuilder().build(live_snap)
    mock_snap = MockProvider().snapshot("eth_dai_v3")
    mock_lp = StateTwinBuilder().build(mock_snap)

    # Both twins are usable for downstream primitives — that's the
    # cross-provider contract. Specific numerical equality at the
    # exchange level is not required (different reserves) but both
    # paths produce viable LP objects.
    assert live_lp is not None
    assert mock_lp is not None
    assert live_lp.get_liquidity() > 0
    assert mock_lp.get_liquidity() > 0


# Test 15
def test_v3_live_twin_token_from_exchange_populated():
    """The built V3 twin exposes the same token-name surface used by
    MCP tooling. Critical for cross-provider compatibility."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    lp = StateTwinBuilder().build(snap)
    # V3 exchange exposes token0/token1 as name strings; the actual
    # ERC20 objects are reachable via factory.token_from_exchange.
    tokens = lp.factory.token_from_exchange[lp.name]
    assert tokens["USDC"].token_name == "USDC"
    assert tokens["WETH"].token_name == "WETH"


# ─── Schema enrichment ──────────────────────────────────────────────────────


# Test 16
def test_v3_live_snapshot_populates_chain_context():
    """V3 LiveProvider populates block_number, timestamp, chain_id."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
        latest_block=20_000_000,
        chain_id=1,
        block_timestamp=1_715_000_000,
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    assert snap.block_number == 20_000_000
    assert snap.timestamp == 1_715_000_000
    assert snap.chain_id == 1


# Test 17
def test_chain_id_cached_across_snapshots():
    """Two .snapshot() calls on the same LiveProvider — chain_id is
    read from the chain only once. C9 contract."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    provider = LiveProvider._with_client(client)
    provider.snapshot(_v3_pool_id())
    provider.snapshot(_v3_pool_id())
    # FakeWeb3._FakeEth tallies eth.chain_id property reads.
    # With caching on RpcClient, only the first snapshot triggers
    # the read.
    assert client._w3.eth._chain_id_reads == 1


# ─── Error paths ────────────────────────────────────────────────────────────


# Test 18
def test_v3_unknown_pool_id_protocol():
    """uniswap_v4 is not a known protocol — ValueError before any
    chain reads."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    with pytest.raises(ValueError):
        LiveProvider._with_client(client).snapshot("uniswap_v4:0xabc")


# Test 19
def test_v3_invalid_tick_range_kwargs():
    """lwr_tick >= upr_tick raises ValueError before any chain reads
    have been performed for tick range. Surfaces from LiveProvider."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    with pytest.raises(ValueError):
        LiveProvider._with_client(client).snapshot(
            _v3_pool_id(), lwr_tick=100, upr_tick=50,
        )


# Test 20
def test_v3_unregistered_pool_address():
    """Pool address not registered in the fake → KeyError surfaces
    cleanly. Same shape as Phase 1's RPC failure propagation."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    with pytest.raises(Exception):
        LiveProvider._with_client(client).snapshot(
            "uniswap_v3:0x{}".format("dead" * 10),
        )


# ─── Integration: V3 twin through primitives ───────────────────────────────


# Test 21
def test_v3_live_twin_runs_through_check_pool_health():
    """Live V3 twin flows through CheckPoolHealth, returns populated
    PoolHealthAnalysis with the V3 version discriminator."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    lp = StateTwinBuilder().build(snap)
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V3"


# Test 22
def test_v3_live_twin_runs_through_analyze_position():
    """Live V3 twin flows through AnalyzePosition without crashing.
    Specific numerics depend on tick range; assert the output shape
    rather than exact values."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_v3_pool_id())
    lp = StateTwinBuilder().build(snap)
    if snap.reserve0 == 0 or snap.reserve1 == 0:
        pytest.skip("Single-sided position; AnalyzePosition expects both > 0.")
    result = AnalyzePosition().apply(
        lp, lp_init_amt = 1.0,
        entry_x_amt = snap.reserve0,
        entry_y_amt = snap.reserve1,
        lwr_tick = snap.lwr_tick,
        upr_tick = snap.upr_tick,
    )
    assert result.current_value > 0


# ─── Constructor / API parity with V2 ──────────────────────────────────────


# Test 23
def test_v3_live_provider_init_stores_rpc_url():
    """Same constructor invariant as V2 — rpc_url stored on the
    instance, no chain calls on __init__."""
    p = LiveProvider("http://localhost:8545")
    assert p.rpc_url == "http://localhost:8545"


# Test 24
def test_v3_pool_id_must_include_address():
    """Malformed pool_id (no address part) raises ValueError, same
    contract as Phase 1's malformed_pool_id_raises test."""
    client = build_fake_client(
        pool=canonical_usdc_weth_v3_spec(),
        tokens=canonical_usdc_weth_v3_token_specs(),
    )
    with pytest.raises(ValueError):
        LiveProvider._with_client(client).snapshot("uniswap_v3:")
