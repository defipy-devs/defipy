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
class BreakEvenTime:
    """ Structured result of FindBreakEvenTime primitive.

        Projects an LP position's observed fee-accrual rate forward
        linearly and reports when cumulative fees would offset the
        current IL drag. Produced by FindBreakEvenTime; answers Q5.3.

        All absolute monetary fields are expressed in token0 units,
        matching AnalyzePosition's numeraire convention.

        Attributes
        ----------
        current_il_drag : float
            Absolute IL drag in token0 units: -il_raw * hold_value
            when il_raw < 0, else 0. Magnitude the fees have to climb.
        fee_income_to_date : float
            AnalyzePosition.fee_income evaluated at the current pool
            state. In token0 units. Can be negative in edge cases
            (e.g., adversarial rounding on very new pools); the
            primitive treats non-positive values as "no recoverable
            rate" and sets days_to_break_even to None.
        fee_rate_per_day : float
            fee_income_to_date / holding_period_days. Units:
            token0/day. Zero or negative when fee income is
            non-positive.
        days_to_break_even : Optional[float]
            current_il_drag / fee_rate_per_day when both are positive;
            0.0 when the position is already broken even or has no
            IL drag; None when fee_rate_per_day <= 0 (can't project
            a recovery without a rate).
        blocks_to_break_even : Optional[int]
            round(days_to_break_even * blocks_per_day). Mirrors the
            None semantics of days_to_break_even. Uses the
            blocks_per_day passed to the FindBreakEvenTime
            constructor (Ethereum mainnet default 7200).
        already_broken_even : bool
            True when net_pnl >= 0 at current state. Under this
            condition days_to_break_even and blocks_to_break_even
            are both 0 (no more time required).
        diagnosis : str
            One of:
              "already_broken_even" — net_pnl >= 0; position is
                already net positive, time fields are 0.
              "no_il_drag" — il_raw >= 0 (price hasn't diverged);
                there is nothing to break even on, time fields are 0.
              "no_fee_income" — fee_rate_per_day <= 0; we can't
                project a recovery, time fields are None.
              "projected" — finite days_to_break_even was computed.

        Notes
        -----
        Linear projection. The primitive assumes the observed
        fee-accrual rate continues unchanged into the future. Real
        fee rates depend on future volume, which this primitive does
        not model. The number is an honest baseline — "at the rate
        this position has been earning, break-even is N days" — not
        a forecast.

        Why fee_income_to_date can be negative. AnalyzePosition
        derives fee_income as (il_with_fees - il_raw) * hold_value.
        On a brand-new position where il_with_fees and il_raw are
        both ~0 but float precision disagrees at the ULP level, this
        can show a tiny negative number. The primitive treats that as
        "no projectable rate" rather than forcing an unphysical answer.

        Numeraire. All absolute amounts (current_il_drag,
        fee_income_to_date, fee_rate_per_day) are in token0, matching
        AnalyzePosition. If the caller wants a different numeraire
        they re-denominate at call-site.
    """
    current_il_drag: float
    fee_income_to_date: float
    fee_rate_per_day: float
    days_to_break_even: Optional[float]
    blocks_to_break_even: Optional[int]
    already_broken_even: bool
    diagnosis: str
