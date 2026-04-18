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
class SlippageAnalysis:
    """Slippage and price-impact decomposition for a single trade.

    Produced by CalculateSlippage. Measures what a trade of `amount_in`
    would cost in slippage given the current LP state, decomposes the
    cost into execution-price gap and pool price impact, and finds the
    largest trade that stays within a 1% slippage budget.

    Attributes
    ----------
    spot_price : float
        Pre-trade price of token_in in token_out units. Derived purely
        from reserve ratio; no fee applied.
    execution_price : float
        Effective price paid on the actual trade: amount_out / amount_in.
        Strictly less than spot_price due to fee and invariant curvature.
    slippage_pct : float
        Fractional gap from spot: (spot_price - execution_price)/spot_price.
        Always non-negative. For V2 with 0.3% fee, bounded below by ~0.003
        (the fee alone, for infinitesimal trades).
    slippage_cost : float
        Missed amount_out in token_out units:
            amount_in * spot_price - amount_out
        How much of the opposing token the trader would have received at
        spot price minus what they actually received.
    price_impact_pct : float
        How much the POOL's spot price moved after the trade, as a
        fraction: (spot_price - new_spot_price)/spot_price. Distinct
        from slippage — for small trades, price_impact approaches zero
        while slippage approaches the fee rate.
    max_size_at_1pct : Optional[float]
        Largest amount_in that keeps slippage_pct at or below 1%.
        Closed-form for V2. For V3, None — tick-crossing math makes the
        inversion non-trivial; a dedicated primitive will handle it.
    """
    spot_price: float
    execution_price: float
    slippage_pct: float
    slippage_cost: float
    price_impact_pct: float
    max_size_at_1pct: Optional[float]
