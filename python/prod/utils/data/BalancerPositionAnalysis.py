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
class BalancerPositionAnalysis:
    """ Structured result of AnalyzeBalancerPosition primitive.

        Decomposes a 2-asset Balancer weighted LP position into
        impermanent loss, fee income, and net PnL. Parallel in shape
        to PositionAnalysis (the V2/V3 analog) with one additional
        weight field surfaced because weighting is the defining
        parameter that distinguishes Balancer from constant-product.

        Distinct from PositionAnalysis rather than a superset. V2/V3
        positions don't have a "base_weight" concept — forcing that
        field onto PositionAnalysis as Optional[float] would muddy
        the contract of both primitives. Same split philosophy as
        StableswapPositionAnalysis vs PositionAnalysis.

        Attributes
        ----------
        base_tkn_name : str
            Symbol of the token treated as the base (first token in
            the pool's insertion order). Matches BalancerImpLoss's
            convention.
        opp_tkn_name : str
            Symbol of the token treated as opp.
        base_weight : float
            Normalized weight of base_tkn, in (0, 1). opp's weight
            is 1 - base_weight.
        current_value : float
            Current position value in opp-token units (numeraire).
        hold_value : float
            Value the initial tokens would have if held rather than
            LP'd, priced at current fee-free spot. Opp-token units.
        il_percentage : float
            Raw impermanent loss as a fraction. Purely price-
            divergence driven via the weighted closed form
            alpha^w / (w*alpha + 1-w) - 1. Typically <= 0.
        il_with_fees : float
            Net IL accounting for fee income.
            (current_value - hold_value) / hold_value. Equals
            il_percentage in v1 because fee income is always 0
            (see `fee_income`).
        fee_income : float
            Always 0.0 in v1. Balancer's collected_fees is
            vault-level with no per-LP attribution available inside
            the pool object; surfacing a derived fee number would
            fabricate precision the underlying state doesn't carry.
            Callers tracking fees externally can compose their own
            accounting.
        net_pnl : float
            current_value - hold_value. Absolute profit or loss vs.
            the hold counterfactual.
        real_apr : Optional[float]
            Annualized net return. None when holding_period_days is
            not provided.
        diagnosis : str
            One of:
              "net_positive"    — net_pnl > 0
              "il_dominant"     — net_pnl <= 0, IL drag is the story
            Note: the "fee_compensated" bucket that PositionAnalysis
            carries doesn't appear here because fee_income is always
            0 in v1; with no fees there's no way for fees to
            compensate for IL. When fee attribution lands, this
            enum will expand to match PositionAnalysis.
        alpha : float
            Price ratio observed: current fee-free spot price of
            base (in opp units) divided by the implied entry price
            (entry_opp_amt / entry_base_amt). Exposed for debuggability
            and for callers who want to feed it into SimulatePriceMove
            or CompareProtocols without rederiving.
    """
    base_tkn_name: str
    opp_tkn_name: str
    base_weight: float
    current_value: float
    hold_value: float
    il_percentage: float
    il_with_fees: float
    fee_income: float
    net_pnl: float
    real_apr: Optional[float]
    diagnosis: str
    alpha: float
