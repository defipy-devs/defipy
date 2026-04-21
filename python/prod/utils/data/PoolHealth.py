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

from dataclasses import dataclass
from typing import Optional


@dataclass
class PoolHealth:
    """Snapshot of pool-level health metrics.

    Produced by CheckPoolHealth. Pool-level (not position-level) view
    useful for answering "is this a pool I'd deposit into?" — liquidity
    depth, fee accrual activity, LP concentration, spot price.

    Attributes
    ----------
    version : str
        "V2" or "V3".
    token0_name : str
        Symbol of token0 in the pair.
    token1_name : str
        Symbol of token1 in the pair.
    spot_price : float
        Price of token0 in token1 units (lp.get_price(token0)).
    reserve0 : float
        Reserve of token0 in human units. For V3, the raw on-chain
        reserve (cumulative deposits minus withdrawals), not a virtual
        reserve — V3-specific metrics belong in AssessLiquidityDepth.
    reserve1 : float
        Reserve of token1 in human units.
    total_liquidity : float
        Total LP tokens in circulation (lp.get_liquidity()).
    tvl_in_token0 : float
        Total value locked expressed in token0 numeraire:
        reserve0 + reserve1 / spot_price.
    total_fee0 : float
        Accumulated fees in token0 since pool inception
        (lp.collected_fee0 in human units).
    total_fee1 : float
        Accumulated fees in token1.
    num_swaps : int
        Number of swaps observed by the pool. V2-only (derived from
        len(fee0_arr)). None for V3, which accumulates feeGrowth
        rather than per-swap history.
    fee_accrual_rate_recent : Optional[float]
        Average token0 fees per swap over the last recent_window
        swaps. V2-only. None when num_swaps is None or zero.
    num_lps : int
        Distinct liquidity providers currently in the pool. The V2
        "0" sentinel for MINIMUM_LIQUIDITY burn is excluded.
    top_lp_share_pct : float
        Fraction (0.0–1.0) of total_supply held by the single largest
        LP. A value near 1.0 means the pool is essentially a single-LP
        pool (concentration risk). None when the pool has no LPs.
    has_activity : bool
        True if num_swaps is known and > 0. False for an untouched
        pool or a V3 pool where swap count isn't tracked.
    """
    version: str
    token0_name: str
    token1_name: str
    spot_price: float
    reserve0: float
    reserve1: float
    total_liquidity: float
    tvl_in_token0: float
    total_fee0: float
    total_fee1: float
    num_swaps: Optional[int]
    fee_accrual_rate_recent: Optional[float]
    num_lps: int
    top_lp_share_pct: Optional[float]
    has_activity: bool
