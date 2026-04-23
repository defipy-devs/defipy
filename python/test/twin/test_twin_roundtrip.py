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

"""End-to-end roundtrip tests.

One test per (recipe, primitive) pairing the twin-built lp with the
curated-10 primitive that applies to that protocol. These are the
demonstration that Day 2 closes the loop with Day 1 — the minimal
agentic flow `MockProvider → builder → lp → primitive → dataclass
result` is real code, not aspiration.
"""

import pytest

from defipy.twin import MockProvider, StateTwinBuilder

from defipy.primitives.position import (
    AnalyzePosition,
    AnalyzeBalancerPosition,
    AnalyzeStableswapPosition,
)
from defipy.primitives.pool_health import CheckPoolHealth


ALLOWED_DIAGNOSES = {
    "il_dominant", "fee_compensated", "net_positive", "at_peg",
    "unreachable_alpha",
}


def _build(recipe):
    snap = MockProvider().snapshot(recipe)
    return StateTwinBuilder().build(snap)


def test_v2_recipe_runs_analyze_position():
    lp = _build("eth_dai_v2")
    result = AnalyzePosition().apply(
        lp, lp_init_amt = 1.0, entry_x_amt = 1000, entry_y_amt = 100000,
    )
    assert result.current_value > 0
    assert result.diagnosis in ALLOWED_DIAGNOSES


def test_v3_recipe_runs_analyze_position():
    lp = _build("eth_dai_v3")
    snap = MockProvider().snapshot("eth_dai_v3")
    result = AnalyzePosition().apply(
        lp, lp_init_amt = 1.0, entry_x_amt = 1000, entry_y_amt = 100000,
        lwr_tick = snap.lwr_tick, upr_tick = snap.upr_tick,
    )
    assert result.current_value > 0
    assert result.diagnosis in ALLOWED_DIAGNOSES


def test_balancer_recipe_runs_analyze_balancer_position():
    lp = _build("eth_dai_balancer_50_50")
    result = AnalyzeBalancerPosition().apply(
        lp, lp_init_amt = 100.0,
        entry_base_amt = 1000, entry_opp_amt = 100000,
    )
    assert result.current_value > 0
    assert result.diagnosis in ALLOWED_DIAGNOSES


def test_stableswap_recipe_runs_analyze_stableswap_position():
    lp = _build("usdc_dai_stableswap_A10")
    result = AnalyzeStableswapPosition().apply(
        lp, lp_init_amt = 100.0,
        entry_amounts = [100000, 100000],
    )
    # Balanced pool: at_peg short-circuit, current==hold, IL=0.
    assert result.diagnosis in ALLOWED_DIAGNOSES
    assert result.A == 10


def test_v2_recipe_runs_check_pool_health():
    lp = _build("eth_dai_v2")
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V2"
    assert health.tvl_in_token0 > 0


def test_v3_recipe_runs_check_pool_health():
    lp = _build("eth_dai_v3")
    health = CheckPoolHealth().apply(lp)
    assert health.version == "V3"
    assert health.tvl_in_token0 > 0
