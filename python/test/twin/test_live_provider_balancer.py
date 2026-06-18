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

"""Mocked-RPC unit tests for LiveProvider Balancer (v2.2 Phase 2).

Mirrors test_live_provider_v3.py: a FakeRpcClient (see _fake_rpc.py)
returns canned getPoolId/getVault/getNormalizedWeights/getPoolTokens
over the two-round-trip Balancer read path, injected via
LiveProvider._with_client(). No network, no real web3.

Live-RPC verification of the same surface lives in
test_live_provider_balancer_live.py (gated by the `live_rpc` marker).
"""

import pytest

from defipy.twin import (
    LiveProvider,
    StateTwinBuilder,
    BalancerPoolSnapshot,
    MockProvider,
)

from twin._fake_rpc import (
    BalancerPoolSpec, TokenSpec,
    build_fake_client,
    canonical_bal_weth_balancer_spec,
    canonical_bal_weth_token_specs,
    BAL_WETH_BALANCER_POOL, BALANCER_VAULT,
    BAL_ADDRESS, WETH_ADDRESS,
)


def _bal_pool_id(addr: str = BAL_WETH_BALANCER_POOL) -> str:
    return "balancer:{}".format(addr)


# ─── Snapshot construction ──────────────────────────────────────────────────


def test_balancer_snapshot_returns_balancer_pool_snapshot():
    """provider.snapshot('balancer:0xPOOL') returns a BalancerPoolSnapshot
    (discriminated by type + protocol)."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert isinstance(snap, BalancerPoolSnapshot)
    assert snap.protocol == "balancer"


def test_balancer_snapshot_weights_match_and_sum_to_one():
    """Normalized weights come back as floats matching the on-chain
    1e18-scaled values and sum to 1.0 (80/20 sums exactly)."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(weight_bal=0.8, weight_weth=0.2),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.weight0 == 0.8
    assert snap.weight1 == 0.2
    assert snap.weight0 + snap.weight1 == pytest.approx(1.0)


def test_balancer_snapshot_weight_sum_within_tolerance():
    """A 30/70 pool's float weights sum to 0.9999999999999999 — inside
    BalancerPoolSnapshot's 1e-9 tolerance. Read both honestly; don't
    derive weight1 = 1 - weight0."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(weight_bal=0.3, weight_weth=0.7),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.weight0 == 0.3
    assert snap.weight1 == 0.7
    # Construction did not raise despite the float sum != 1.0 exactly.
    assert abs(snap.weight0 + snap.weight1 - 1.0) < 1e-9


def test_balancer_snapshot_reserves_decimal_adjusted():
    """Reserves come out as decimal-adjusted floats (raw / 10**dec),
    not raw uints. 500k BAL / 1.5k WETH at 18 decimals each."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(
            bal_amount=500_000.0, weth_amount=1_500.0,
        ),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.reserve0 == 500_000.0
    assert snap.reserve1 == 1_500.0


def test_balancer_snapshot_handles_mixed_decimals():
    """A mixed-decimals pool (token0 6dec, token1 18dec) decimal-adjusts
    each balance independently to human units."""
    # USDC(6)/WETH(18)-style 50/50 pool. Build a spec directly so the
    # decimals differ across the two tokens.
    USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    spec = BalancerPoolSpec.from_human(
        address=BAL_WETH_BALANCER_POOL,
        pool_id=b"\x22" * 32,
        vault_address=BALANCER_VAULT,
        token0_address=USDC,
        token1_address=WETH_ADDRESS,
        balance0=2_000_000.0,   # 2M USDC
        balance1=600.0,         # 600 WETH
        weight0=0.5,
        weight1=0.5,
        decimals0=6,
        decimals1=18,
    )
    client = build_fake_client(
        pool=spec,
        tokens=[
            TokenSpec(address=USDC, symbol="USDC", decimals=6),
            TokenSpec(address=WETH_ADDRESS, symbol="WETH", decimals=18),
        ],
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.token0_name == "USDC"
    assert snap.token1_name == "WETH"
    assert snap.reserve0 == 2_000_000.0
    assert snap.reserve1 == 600.0


def test_balancer_snapshot_token_names_from_specs():
    """Token symbols come from FetchToken metadata reads."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.token0_name == "BAL"
    assert snap.token1_name == "WETH"


def test_balancer_snapshot_populates_chain_context():
    """block_number, timestamp, chain_id all populated."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
        latest_block=20_000_000,
        chain_id=1,
        block_timestamp=1_715_000_000,
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert snap.block_number == 20_000_000
    assert snap.timestamp == 1_715_000_000
    assert snap.chain_id == 1


# ─── Read pattern ───────────────────────────────────────────────────────────


def test_balancer_snapshot_two_round_trips():
    """The read is two Multicall3 batches: RT1 (pool no-arg reads +
    timestamp) and RT2 (vault getPoolTokens). poolId isn't known until
    RT1 returns, so it can't fold into one batch."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_bal_pool_id())
    aggregate3_calls = [
        rec for rec in client.call_log if rec.function == "aggregate3"
    ]
    assert len(aggregate3_calls) == 2


def test_balancer_snapshot_reads_expected_functions():
    """RT1 reads getPoolId/getVault/getNormalizedWeights +
    getCurrentBlockTimestamp; RT2 reads getPoolTokens; FetchToken pulls
    symbol/decimals per token."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_bal_pool_id())
    fns = {rec.function for rec in client.call_log}
    assert {
        "getPoolId", "getVault", "getNormalizedWeights",
        "getCurrentBlockTimestamp", "getPoolTokens", "symbol", "decimals",
    } <= fns


def test_balancer_getpooltokens_targets_vault():
    """getPoolTokens dispatches against the Vault address, not the
    pool address — the 2-hop structure."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_bal_pool_id())
    pool_tokens_recs = [
        rec for rec in client.call_log if rec.function == "getPoolTokens"
    ]
    assert len(pool_tokens_recs) == 1
    # Address recorded for the getPoolTokens read is the vault (checksum
    # of BALANCER_VAULT), not the pool.
    assert pool_tokens_recs[0].address.lower() == BALANCER_VAULT.lower()


def test_balancer_multicall_pins_all_subcalls_to_block():
    """R1 — every sub-call across BOTH round trips pins to the resolved
    block."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
        latest_block=20_500_000,
    )
    LiveProvider._with_client(client).snapshot(_bal_pool_id())
    pinned = [
        rec for rec in client.call_log
        if rec.function in {
            "aggregate3", "getPoolId", "getVault", "getNormalizedWeights",
            "getCurrentBlockTimestamp", "getPoolTokens",
        }
    ]
    block_ids = {rec.block_identifier for rec in pinned}
    assert block_ids == {20_500_000}


# ─── Scope guard ────────────────────────────────────────────────────────────


def test_balancer_three_asset_pool_raises_not_implemented():
    """v2.2 supports 2-asset weighted pools only; a 3-asset pool raises
    NotImplementedError."""
    THIRD = "0x6B175474E89094C44Da98b954EedeAC495271d0F"   # DAI as 3rd token
    spec = canonical_bal_weth_balancer_spec()
    spec.extra_token_addresses = [THIRD]
    spec.extra_balances_raw = [1_000 * 10**18]
    client = build_fake_client(
        pool=spec,
        tokens=canonical_bal_weth_token_specs() + [
            TokenSpec(address=THIRD, symbol="DAI", decimals=18),
        ],
    )
    with pytest.raises(NotImplementedError) as excinfo:
        LiveProvider._with_client(client).snapshot(_bal_pool_id())
    assert "2-asset" in str(excinfo.value)


# ─── Builder parity ─────────────────────────────────────────────────────────


def test_balancer_built_lp_matches_fixture(balancer_setup):
    """Read path → builder produces a balancerpy lp whose reserves,
    weights, and spot price match a directly-constructed balancer_setup
    pool for matched inputs (50/50 ETH/DAI, 1000/100000)."""
    # ETH/DAI 50/50 spec matching balancer_setup's entry composition.
    # token0 = ETH (WETH addr, symbol "ETH"), token1 = DAI — insertion
    # order matches balancer_setup (base=ETH first, opp=DAI second).
    DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
    spec = BalancerPoolSpec.from_human(
        address=BAL_WETH_BALANCER_POOL,
        pool_id=b"\x33" * 32,
        vault_address=BALANCER_VAULT,
        token0_address=WETH_ADDRESS,
        token1_address=DAI,
        balance0=1_000.0,
        balance1=100_000.0,
        weight0=0.5,
        weight1=0.5,
        decimals0=18,
        decimals1=18,
    )
    client = build_fake_client(
        pool=spec,
        tokens=[
            TokenSpec(address=WETH_ADDRESS, symbol="ETH", decimals=18),
            TokenSpec(address=DAI, symbol="DAI", decimals=18),
        ],
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    built = StateTwinBuilder().build(snap)

    assert dict(built.tkn_reserves) == dict(balancer_setup.lp.tkn_reserves)
    assert float(built.tkn_weights["ETH"]) == pytest.approx(
        float(balancer_setup.lp.tkn_weights["ETH"])
    )

    # Spot price (DAI per ETH) matches the fixture.
    built_tokens = built.factory.token_from_exchange[built.name]
    built_eth = built_tokens["ETH"]
    built_dai = built_tokens["DAI"]
    assert built.get_price(built_eth, built_dai) == pytest.approx(
        balancer_setup.lp.get_price(
            balancer_setup.base_tkn, balancer_setup.opp_tkn,
        )
    )


def test_balancer_built_lp_token_surface_populated():
    """The built twin exposes the token-name surface MCP tooling uses."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    lp = StateTwinBuilder().build(snap)
    tokens = lp.factory.token_from_exchange[lp.name]
    assert tokens["BAL"].token_name == "BAL"
    assert tokens["WETH"].token_name == "WETH"


def test_balancer_live_twin_builds_like_mock_twin():
    """Live Balancer twin builds through the same downstream path as
    MockProvider's eth_dai_balancer_50_50 recipe."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    live_snap = LiveProvider._with_client(client).snapshot(_bal_pool_id())
    live_lp = StateTwinBuilder().build(live_snap)
    mock_snap = MockProvider().snapshot("eth_dai_balancer_50_50")
    mock_lp = StateTwinBuilder().build(mock_snap)
    assert live_lp is not None
    assert mock_lp is not None


# ─── chain_id caching ───────────────────────────────────────────────────────


def test_balancer_chain_id_cached_across_snapshots():
    """chain_id read once across two snapshots on the same provider (C9)."""
    client = build_fake_client(
        pool=canonical_bal_weth_balancer_spec(),
        tokens=canonical_bal_weth_token_specs(),
    )
    provider = LiveProvider._with_client(client)
    provider.snapshot(_bal_pool_id())
    provider.snapshot(_bal_pool_id())
    assert client._w3.eth._chain_id_reads == 1
