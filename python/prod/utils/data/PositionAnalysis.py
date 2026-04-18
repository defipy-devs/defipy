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
class PositionAnalysis:
    """ Structured result of AnalyzePosition primitive.

        Decomposes an LP position into impermanent loss, fee income, and net
        PnL, with a categorical diagnosis string suitable for LLM consumption.

        Attributes
        ----------
        current_value : float
            Current position value in terms of the reference token (token0).
        hold_value : float
            Value the initial tokens would have if held rather than LP'd,
            priced at current spot.
        il_percentage : float
            Raw impermanent loss as a fraction (fees=False). Purely price-
            divergence driven. Typically <= 0.
        il_with_fees : float
            Net IL accounting for fee income (fees=True). Equals
            (current_value - hold_value) / hold_value. Greater than
            il_percentage when fees have been earned.
        fee_income : float
            Isolated fee component in absolute terms.
            (il_with_fees - il_percentage) * hold_value.
        net_pnl : float
            current_value - hold_value. Absolute profit or loss vs. holding.
        real_apr : Optional[float]
            Annualized net return accounting for IL. None when holding period
            is not provided.
        diagnosis : str
            One of: "net_positive", "fee_compensated", "il_dominant".
    """
    current_value: float
    hold_value: float
    il_percentage: float
    il_with_fees: float
    fee_income: float
    net_pnl: float
    real_apr: Optional[float]
    diagnosis: str
