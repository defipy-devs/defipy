# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2026 Ian Moore
# Email: defipy.devs@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# See the License for the specific language governing permissions and
# limitations under the License

"""v2.2.2 — V2 State Twin carries the pool's real LP `totalSupply`.

Proves the patch: LiveProvider stores `totalSupply()/1e18` on the snapshot,
StateTwinBuilder stamps it onto the twin (with a synthetic √(r0·r1) fallback
when None), so AnalyzePosition's absolute outputs scale by the real supply
while every scale-invariant output is untouched. All offline (FakeRpcClient
for the read path; direct snapshots for the builder path).
"""

import math
from dataclasses import asdict

import pytest

from defipy.twin import (
    LiveProvider,
    StateTwinBuilder,
    V2PoolSnapshot,
    MockProvider,
)
from defipy.primitives.position import AnalyzePosition, SimulatePriceMove
from defipy.primitives.execution import CalculateSlippage

from twin._fake_rpc import V2PoolSpec, TokenSpec, build_fake_client

# Reserves chosen so √(r0·r1) = 10000 — clearly distinct from the real
# supplies the tests stamp (250 / 200 / 400), which is the whole point.
_R0, _R1 = 1000.0, 100_000.0
_SQRT = math.sqrt(_R0 * _R1)   # 10000.0


def _v2_snap(total_supply):
    return V2PoolSnapshot(
        pool_id="0xPOOL", token0_name="USDC", token1_name="WETH",
        reserve0=_R0, reserve1=_R1, total_supply=total_supply,
        block_number=1, chain_id=1,
    )


# ─── 1. Snapshot carries the field ──────────────────────────────────────────

def test_live_snapshot_carries_real_total_supply():
    pool = V2PoolSpec(
        address="0xPOOL", token0_address="0xT0", token1_address="0xT1",
        reserve0_raw=1000 * 10**18, reserve1_raw=100_000 * 10**18,
        total_supply_raw=7_777 * 10**18,   # known, 18-dec, ≠ √(r0·r1)
    )
    tokens = [
        TokenSpec(address="0xT0", symbol="ETH", decimals=18),
        TokenSpec(address="0xT1", symbol="DAI", decimals=18),
    ]
    client = build_fake_client(pool=pool, tokens=tokens)
    snap = LiveProvider._with_client(client).snapshot("uniswap_v2:0xPOOL")
    assert snap.total_supply == pytest.approx(7_777.0)   # raw / 1e18


def test_live_snapshot_total_supply_uses_18_decimals_not_pool_token():
    # USDC is 6-dec; if the supply were (wrongly) adjusted by a pool token's
    # decimals it would be off by 1e12. LP tokens are always 18-dec.
    pool = V2PoolSpec(
        address="0xPOOL", token0_address="0xT0", token1_address="0xT1",
        reserve0_raw=int(50_000_000 * 10**6), reserve1_raw=15_000 * 10**18,
        total_supply_raw=1_234 * 10**18,
    )
    tokens = [
        TokenSpec(address="0xT0", symbol="USDC", decimals=6),
        TokenSpec(address="0xT1", symbol="WETH", decimals=18),
    ]
    snap = LiveProvider._with_client(
        build_fake_client(pool=pool, tokens=tokens)).snapshot("uniswap_v2:0xPOOL")
    assert snap.total_supply == pytest.approx(1_234.0)


def test_mock_snapshot_total_supply_is_none():
    assert MockProvider().snapshot("eth_dai_v2").total_supply is None


# ─── 2. Builder stamps it (the core assertion) ──────────────────────────────

def test_builder_stamps_real_supply():
    lp = StateTwinBuilder().build(_v2_snap(total_supply=250.0))
    # total_supply AND the single synthetic provider's balance == real supply.
    assert lp.get_liquidity() == pytest.approx(250.0)
    assert lp.get_liquidity_from_provider("twin_user") == pytest.approx(250.0)
    # And it really differs from the synthetic √(r0·r1) it would've used.
    assert lp.get_liquidity() != pytest.approx(_SQRT)


# ─── 3. Fallback preserved (None → synthetic √(r0·r1)) ──────────────────────

def test_builder_synthetic_fallback_when_none():
    lp = StateTwinBuilder().build(_v2_snap(total_supply=None))
    assert lp.get_liquidity() == pytest.approx(_SQRT)   # today's exact behavior


# ─── 4. AnalyzePosition absolute outputs now scale correctly ────────────────

def test_analyze_position_absolute_outputs_scale_with_supply():
    def cv(S):
        lp = StateTwinBuilder().build(_v2_snap(total_supply=S))
        return AnalyzePosition().apply(
            lp, lp_init_amt=10.0, entry_x_amt=_R0, entry_y_amt=_R1).current_value

    # current_value scales as lp_init_amt / total_supply, so halving the
    # supply doubles the absolute value (previously every live twin used
    # √(r0·r1) regardless — the bug).
    assert cv(200.0) / cv(400.0) == pytest.approx(2.0)


# ─── 5. Scale-invariant outputs unchanged ───────────────────────────────────

def test_scale_invariant_outputs_unchanged_by_supply():
    lp_real = StateTwinBuilder().build(_v2_snap(total_supply=250.0))
    lp_synth = StateTwinBuilder().build(_v2_snap(total_supply=None))

    a = SimulatePriceMove().apply(lp_real, price_change_pct=-0.2, position_size_lp=10.0)
    b = SimulatePriceMove().apply(lp_synth, price_change_pct=-0.2, position_size_lp=10.0)
    assert a.il_at_new_price == pytest.approx(b.il_at_new_price)
    assert a.value_change_pct == pytest.approx(b.value_change_pct)

    tok = "USDC"
    sa = CalculateSlippage().apply(lp_real, token_in=_token(lp_real, tok), amount_in=1000.0)
    sb = CalculateSlippage().apply(lp_synth, token_in=_token(lp_synth, tok), amount_in=1000.0)
    assert sa.slippage_pct == pytest.approx(sb.slippage_pct)
    assert sa.price_impact_pct == pytest.approx(sb.price_impact_pct)


def _token(lp, name):
    return lp.factory.token_from_exchange[lp.name][name]


# ─── 6. Wire-form round-trip ────────────────────────────────────────────────

def test_wire_form_roundtrip_total_supply():
    snap = _v2_snap(total_supply=250.0)
    body = asdict(snap)
    assert body["total_supply"] == 250.0

    rt = V2PoolSnapshot(**body)
    assert rt.total_supply == 250.0
    assert rt == snap

    # Old wire form (no total_supply key) reconstructs with None.
    old_body = {k: v for k, v in body.items() if k != "total_supply"}
    assert V2PoolSnapshot(**old_body).total_supply is None
