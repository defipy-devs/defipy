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

"""Mocked-RPC unit tests for LiveProvider Stableswap (v2.2 Phase 3).

Mirrors test_live_provider_balancer.py: a FakeRpcClient returns canned
A()/coins(i)/balances(i) over the Curve read path, injected via
LiveProvider._with_client(). Covers both the n_coins hint (fast path)
and the allow_failure coin-count probe. No network, no real web3.

Live-RPC verification lives in test_live_provider_stableswap_live.py
(gated by the `live_rpc` marker).
"""

import pytest

from defipy.twin import (
    LiveProvider,
    StateTwinBuilder,
    StableswapPoolSnapshot,
    MockProvider,
)

from twin._fake_rpc import (
    CurvePoolSpec, TokenSpec,
    build_fake_client,
    canonical_usdc_dai_curve_spec,
    canonical_usdc_dai_curve_token_specs,
    canonical_3pool_curve_spec,
    canonical_3pool_curve_token_specs,
    CURVE_3POOL, DAI_ADDRESS, USDC_ADDRESS, USDT_ADDRESS,
)


def _ss_pool_id(addr: str = CURVE_3POOL) -> str:
    return "stableswap:{}".format(addr)


def _build_ref_pool(names, reserves, A):
    """Directly-constructed stableswappy pool for parity comparison —
    mirrors stableswap_setup's construction, generalized to N tokens."""
    from stableswappy.erc import ERC20 as SERC20
    from stableswappy.vault import StableswapVault
    from stableswappy.cst.factory import StableswapFactory
    from stableswappy.utils.data import StableswapExchangeData
    from stableswappy.process.join import Join as SJoin
    vault = StableswapVault()
    for nm, amt in zip(names, reserves):
        t = SERC20(nm, "0xref_{}".format(nm), 18)
        t.deposit("twin_user", amt)
        vault.add_token(t)
    factory = StableswapFactory("ref factory", "0xref_factory")
    exch = StableswapExchangeData(vault=vault, symbol="CST", address="0xref_lp")
    lp = factory.deploy(exch)
    SJoin().apply(lp, "twin_user", A)
    return lp


# ─── 2-coin snapshot construction ───────────────────────────────────────────


def test_stableswap_snapshot_returns_stableswap_pool_snapshot():
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert isinstance(snap, StableswapPoolSnapshot)
    assert snap.protocol == "stableswap"


def test_stableswap_2coin_fields():
    """2-coin USDC/DAI pool: names, decimal-adjusted reserves, A, N==2."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(
            usdc_amount=100_000.0, dai_amount=100_000.0, A=10,
        ),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert snap.token_names == ["USDC", "DAI"]
    assert snap.reserves == [100_000.0, 100_000.0]
    assert snap.A == 10
    assert len(snap.token_names) == 2


def test_stableswap_2coin_mixed_decimals():
    """USDC(6)/DAI(18) raw balances decimal-adjust independently to
    human units."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(
            usdc_amount=250_000.0, dai_amount=180_000.0,
        ),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert snap.reserves == [250_000.0, 180_000.0]


def test_stableswap_snapshot_populates_chain_context():
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
        latest_block=20_000_000,
        chain_id=1,
        block_timestamp=1_715_000_000,
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert snap.block_number == 20_000_000
    assert snap.timestamp == 1_715_000_000
    assert snap.chain_id == 1


def test_stableswap_decimals_stays_scalar_18():
    """The snapshot's decimals stays scalar 18 (decimals-invariant for
    plain pools); per-token native decimals are not recorded."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert snap.decimals == 18


# ─── 3-coin snapshot construction ───────────────────────────────────────────


def test_stableswap_3coin_fields():
    """3pool DAI/USDC/USDT: names, reserves, A, N==3."""
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(
            dai_amount=200_000_000.0,
            usdc_amount=190_000_000.0,
            usdt_amount=210_000_000.0,
            A=2000,
        ),
        tokens=canonical_3pool_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id(), n_coins=3)
    assert snap.token_names == ["DAI", "USDC", "USDT"]
    assert snap.reserves == [200_000_000.0, 190_000_000.0, 210_000_000.0]
    assert snap.A == 2000
    assert len(snap.token_names) == 3


# ─── Coin-count: hint vs probe ──────────────────────────────────────────────


def test_stableswap_n_coins_hint_skips_probe():
    """Passing n_coins=3 takes the fast path — a single multicall (the
    main read), no probe round trip."""
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(),
        tokens=canonical_3pool_curve_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_ss_pool_id(), n_coins=3)
    aggregate3_calls = [
        rec for rec in client.call_log if rec.function == "aggregate3"
    ]
    assert len(aggregate3_calls) == 1


def test_stableswap_probe_resolves_coin_count():
    """Without a hint, the probe resolves N=3 — proving coins(3) failed
    (else N would over-count) — and adds one extra multicall (probe +
    main = 2)."""
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(),
        tokens=canonical_3pool_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert len(snap.token_names) == 3
    aggregate3_calls = [
        rec for rec in client.call_log if rec.function == "aggregate3"
    ]
    assert len(aggregate3_calls) == 2


def test_stableswap_probe_resolves_two_coins():
    """The probe stops at 2 for a 2-coin pool."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert len(snap.token_names) == 2


def test_stableswap_probe_too_few_coins_raises():
    """A pool whose coins() reverts before index 2 (a malformed/empty
    probe) raises ValueError pointing at the n_coins escape hatch."""
    # 1-coin spec: coins(0) succeeds, coins(1) reverts → probe n=1 < 2.
    spec = CurvePoolSpec(
        address=CURVE_3POOL,
        coin_addresses=[USDC_ADDRESS],
        balances_raw=[100_000 * 10**6],
        A=10,
    )
    client = build_fake_client(
        pool=spec,
        tokens=[TokenSpec(address=USDC_ADDRESS, symbol="USDC", decimals=6)],
    )
    with pytest.raises(ValueError) as excinfo:
        LiveProvider._with_client(client).snapshot(_ss_pool_id())
    assert "n_coins" in str(excinfo.value)


# ─── Read pattern / R1 ──────────────────────────────────────────────────────


def test_stableswap_reads_expected_functions():
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(),
        tokens=canonical_3pool_curve_token_specs(),
    )
    LiveProvider._with_client(client).snapshot(_ss_pool_id(), n_coins=3)
    fns = {rec.function for rec in client.call_log}
    assert {
        "A", "coins", "balances", "getCurrentBlockTimestamp",
        "symbol", "decimals",
    } <= fns


def test_stableswap_all_subcalls_pin_to_block_with_probe():
    """R1 — every sub-call across BOTH the probe and the main read pins
    to the resolved block."""
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(),
        tokens=canonical_3pool_curve_token_specs(),
        latest_block=20_500_000,
    )
    LiveProvider._with_client(client).snapshot(_ss_pool_id())
    pinned = [
        rec for rec in client.call_log
        if rec.function in {
            "aggregate3", "A", "coins", "balances", "getCurrentBlockTimestamp",
        }
    ]
    block_ids = {rec.block_identifier for rec in pinned}
    assert block_ids == {20_500_000}


# ─── Builder parity ─────────────────────────────────────────────────────────


def test_stableswap_built_lp_matches_fixture(stableswap_setup):
    """2-coin read path → builder matches the stableswap_setup fixture
    (USDC/DAI, A=10, balanced) on reserves and spot price."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(
            usdc_amount=100_000.0, dai_amount=100_000.0, A=10,
        ),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id())
    built = StateTwinBuilder().build(snap)

    assert dict(built.tkn_reserves) == dict(stableswap_setup.lp.tkn_reserves)

    built_tokens = built.factory.token_from_exchange[built.name]
    assert built.get_price(
        built_tokens["USDC"], built_tokens["DAI"],
    ) == pytest.approx(
        stableswap_setup.lp.get_price(
            stableswap_setup.token0, stableswap_setup.token1,
        )
    )


def test_stableswap_3coin_built_lp_matches_direct_construction():
    """3-coin read path → builder matches a directly-constructed
    stableswappy 3-token pool on reserves and spot price."""
    names = ["DAI", "USDC", "USDT"]
    reserves = [200_000_000.0, 190_000_000.0, 210_000_000.0]
    A = 2000
    client = build_fake_client(
        pool=canonical_3pool_curve_spec(
            dai_amount=reserves[0], usdc_amount=reserves[1],
            usdt_amount=reserves[2], A=A,
        ),
        tokens=canonical_3pool_curve_token_specs(),
    )
    snap = LiveProvider._with_client(client).snapshot(_ss_pool_id(), n_coins=3)
    built = StateTwinBuilder().build(snap)

    ref = _build_ref_pool(names, reserves, A)
    assert dict(built.tkn_reserves) == dict(ref.tkn_reserves)

    built_tokens = built.factory.token_from_exchange[built.name]
    ref_tokens = ref.factory.token_from_exchange[ref.name]
    assert built.get_price(
        built_tokens["DAI"], built_tokens["USDC"],
    ) == pytest.approx(
        ref.get_price(ref_tokens["DAI"], ref_tokens["USDC"])
    )


def test_stableswap_live_twin_builds_like_mock_twin():
    """Live Stableswap twin builds through the same path as
    MockProvider's usdc_dai_stableswap_A10 recipe."""
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    live_lp = StateTwinBuilder().build(
        LiveProvider._with_client(client).snapshot(_ss_pool_id())
    )
    mock_lp = StateTwinBuilder().build(
        MockProvider().snapshot("usdc_dai_stableswap_A10")
    )
    assert live_lp is not None
    assert mock_lp is not None


# ─── chain_id caching ───────────────────────────────────────────────────────


def test_stableswap_chain_id_cached_across_snapshots():
    client = build_fake_client(
        pool=canonical_usdc_dai_curve_spec(),
        tokens=canonical_usdc_dai_curve_token_specs(),
    )
    provider = LiveProvider._with_client(client)
    provider.snapshot(_ss_pool_id(), n_coins=2)
    provider.snapshot(_ss_pool_id(), n_coins=2)
    assert client._w3.eth._chain_id_reads == 1
