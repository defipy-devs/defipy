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

from abc import ABC
from dataclasses import dataclass, field
from typing import Optional


# Tolerance for Balancer weight-sum validation. Weights are provided
# as floats; allowing a small epsilon lets callers pass e.g. 0.8/0.2
# derived from integer arithmetic without spurious rejection.
_WEIGHT_SUM_TOL = 1e-9


@dataclass(kw_only=True)
class PoolSnapshot(ABC):
    """Protocol-agnostic pool state.

    Concrete subclasses carry protocol-specific fields. Each subclass
    sets `protocol` in __post_init__ so the discriminator can't be
    forged by the caller.

    Note on `pool_id` semantics — this field is provider-dependent:

      - For MockProvider snapshots, `pool_id` is the recipe name
        (e.g. "eth_dai_v2"). Builder uses it as a synthetic-address
        component, e.g. "0xtwin_eth_dai_v2_ETH".

      - For LiveProvider snapshots, `pool_id` is the on-chain pool
        address as supplied by the caller (with or without "0x"
        prefix, with or without checksum casing). Builder uses it
        the same way; the synthesized internal token addresses
        ("0xtwin_<addr>_<symbol>") are non-functional identifiers,
        not real chain addresses.

    Downstream consumers should not parse `pool_id` expecting a
    specific format.

    Chain-context fields (block_number, timestamp, chain_id) are
    Optional[int] = None per C5 of STATE_TWIN_PHASE_2_EXPANDED.md.
    LiveProvider populates them from on-chain reads; MockProvider
    leaves them None to honestly signal "synthetic, not chain state."
    Consumers that need chain context check for None and branch.
    """
    pool_id: str
    protocol: str = ""
    block_number: Optional[int] = None
    timestamp: Optional[int] = None
    chain_id: Optional[int] = None


@dataclass(kw_only=True)
class V2PoolSnapshot(PoolSnapshot):
    """Uniswap V2 pool state.

    `reserve0` and `reserve1` are decimal-adjusted floats in
    whole-token units, NOT raw uint112 wei values. LiveProvider does
    the conversion (raw_reserve / 10**decimals) before constructing
    the snapshot; MockProvider produces decimal floats directly.
    `StateTwinBuilder._build_v2` passes these straight to
    `lp.add_liquidity()`, which expects decimal-adjusted amounts.

    `total_supply` is the pool's real LP-token totalSupply in whole-token
    (18-decimal-adjusted) units, populated by LiveProvider. None for
    MockProvider and for older wire forms — in which case StateTwinBuilder
    falls back to the synthetic √(reserve0·reserve1) single-mint supply.
    """
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    total_supply: Optional[float] = None   # real LP supply; None → synthetic fallback

    def __post_init__(self):
        self.protocol = "uniswap_v2"


@dataclass(kw_only=True)
class V3PoolSnapshot(PoolSnapshot):
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    fee: int = 3000
    tick_spacing: int = 60
    # Full-range defaults computed lazily in __post_init__ from
    # tick_spacing via UniV3Utils. Callers can override either.
    lwr_tick: Optional[int] = None
    upr_tick: Optional[int] = None

    def __post_init__(self):
        self.protocol = "uniswap_v3"
        if self.lwr_tick is None or self.upr_tick is None:
            # Local import: avoid pulling uniswappy at module load time,
            # keep snapshot.py cheap for pure-data inspection.
            from uniswappy.utils.tools.v3 import UniV3Utils
            if self.lwr_tick is None:
                self.lwr_tick = UniV3Utils.getMinTick(self.tick_spacing)
            if self.upr_tick is None:
                self.upr_tick = UniV3Utils.getMaxTick(self.tick_spacing)
        if self.lwr_tick >= self.upr_tick:
            raise ValueError(
                "V3PoolSnapshot: lwr_tick ({}) must be < upr_tick ({})"
                .format(self.lwr_tick, self.upr_tick)
            )


@dataclass(kw_only=True)
class BalancerPoolSnapshot(PoolSnapshot):
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    weight0: float = 0.5
    weight1: float = 0.5
    # Pool shares minted at the initial Join. Matches the conftest
    # BAL_POOL_SHARES_INIT default so built pools behave identically
    # to balancer_setup fixtures.
    pool_shares_init: float = 100.0

    def __post_init__(self):
        self.protocol = "balancer"
        if abs(self.weight0 + self.weight1 - 1.0) > _WEIGHT_SUM_TOL:
            raise ValueError(
                "BalancerPoolSnapshot: weights must sum to 1.0; "
                "got weight0={}, weight1={} (sum={})"
                .format(self.weight0, self.weight1, self.weight0 + self.weight1)
            )


@dataclass(kw_only=True)
class StableswapPoolSnapshot(PoolSnapshot):
    token_names: list[str]
    reserves: list[float]
    A: int = 10
    # Stableswap decimals: tokens in the curated pools (USDC/DAI) are
    # treated at 18 decimals internally by stableswappy's rate-table
    # convention. Matching conftest's SERC20(..., 18) construction.
    decimals: int = 18

    def __post_init__(self):
        self.protocol = "stableswap"
        if len(self.token_names) != len(self.reserves):
            raise ValueError(
                "StableswapPoolSnapshot: token_names and reserves must "
                "have same length; got {} names, {} reserves"
                .format(len(self.token_names), len(self.reserves))
            )
        if len(self.token_names) < 2:
            raise ValueError(
                "StableswapPoolSnapshot: at least 2 tokens required; got {}"
                .format(len(self.token_names))
            )
