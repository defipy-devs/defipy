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

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StableswapPositionAnalysis:
    """ Structured result of AnalyzeStableswapPosition primitive.

        Decomposes a 2-asset Curve-style stableswap LP position into
        impermanent loss, fee income, and net PnL. Parallel in shape
        to PositionAnalysis (V2/V3 analog) and
        BalancerPositionAnalysis, with stableswap-specific additions:
          - A (amplification coefficient) surfaced for debuggability
          - alpha may be None when the pool's current state implies an
            alpha outside the reachability bound at this A

        Distinct from PositionAnalysis rather than a superset. V2/V3
        positions don't have an amplification coefficient, and
        reachability is a stableswap-specific concern. Same split
        philosophy as BalancerPositionAnalysis.

        Attributes
        ----------
        token_names : list[str]
            Tokens in pool insertion order. 2-asset only in v1; the
            list will have exactly two entries.
        A : int
            Amplification coefficient of the pool. Higher A = flatter
            curve = lower slippage near peg = LARGER per-alpha IL
            (the "strong negative convexity" property). Surfaced so
            callers can reason about reachability without extra calls.
        current_value : float
            Current position value denominated at peg (sum across
            tokens, 1:1 valued — stableswap's natural numeraire).
            When the pool is perfectly balanced this equals hold_value.
        hold_value : float
            Counterfactual hold value, equal to sum of the LP's
            entry amounts (at peg).
        il_percentage : Optional[float]
            Raw impermanent loss as a fraction, or None when the
            implied alpha is unreachable at this A (|ε| ≥ 0.95).
            Matches the None-sentinel pattern used by AssessDepegRisk
            and CompareProtocols for unreachable-alpha scenarios.
        il_with_fees : Optional[float]
            Net IL accounting for fee income. None when
            il_percentage is None. In v1 equals il_percentage (fee
            income is always 0 — see `fee_income`).
        fee_income : float
            Always 0.0 in v1. Stableswap's self.tkn_fees is
            pool-global with no per-LP attribution available inside
            the pool object. Same scope boundary as
            BalancerPositionAnalysis.fee_income.
        net_pnl : Optional[float]
            current_value - hold_value, or None when il_percentage
            is None (without IL we can't back out lp_value, so pnl
            is undefined).
        real_apr : Optional[float]
            Annualized net return. None when holding_period_days is
            not supplied, or when net_pnl is None.
        diagnosis : str
            One of:
              "at_peg"               — implied alpha == 1; no divergence
              "net_positive"         — net_pnl > 0
              "il_dominant"          — net_pnl <= 0, IL drag is the story
              "unreachable_alpha"    — pool state implies unreachable α
        alpha : Optional[float]
            Price ratio observed from the pool's live dydx. Derived
            as abs(1 - dydx) converted back to an alpha. None only
            when dydx read fails; otherwise set even if the alpha
            proves unreachable downstream.
        per_token_init : list[float]
            Per-token entry amounts owned by this LP share. Sums to
            hold_value.
        per_token_current : list[float]
            Per-token amounts the LP's share currently claims from
            the pool. Sums to the lp_value in the peg-numeraire
            framing; populated as empty list [] when lp_value is
            None (unreachable path).
    """
    token_names: List[str]
    A: int
    current_value: float
    hold_value: float
    il_percentage: Optional[float]
    il_with_fees: Optional[float]
    fee_income: float
    net_pnl: Optional[float]
    real_apr: Optional[float]
    diagnosis: str
    alpha: Optional[float]
    per_token_init: List[float] = field(default_factory = list)
    per_token_current: List[float] = field(default_factory = list)
