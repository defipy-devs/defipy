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
from typing import List

from .PositionAnalysis import PositionAnalysis


@dataclass
class PositionSummary:
    """Per-position summary for inclusion in PortfolioAnalysis.positions.

    Compact view of one AnalyzePosition result plus the position's
    token pair, for ranking and filtering at the portfolio level.
    The full AnalyzePosition is carried on .analysis so callers who
    got a portfolio-level verdict don't need to re-run per-position.

    Attributes
    ----------
    name : str
        Human-readable label for this position (from PortfolioPosition.name
        or "{token0}/{token1}" default).
    net_pnl : float
        From PositionAnalysis.net_pnl. In the portfolio's common
        token0 numeraire.
    il_percentage : float
        From PositionAnalysis.il_percentage. Fractional IL drag.
    fee_income : float
        From PositionAnalysis.fee_income. In numeraire units.
    tokens : List[str]
        Two-element list [token0_name, token1_name] for this position's
        pair. Used by shared-exposure detection at the portfolio level.
    analysis : PositionAnalysis
        Full AnalyzePosition output for this position.
    """
    name: str
    net_pnl: float
    il_percentage: float
    fee_income: float
    tokens: List[str]
    analysis: PositionAnalysis


@dataclass
class PortfolioAnalysis:
    """Aggregate view of multiple LP positions sharing a common token0 numeraire.

    Produced by AggregatePortfolio. Chains AnalyzePosition across N
    positions, sums the scalar metrics in a shared numeraire, ranks
    by net_pnl, and flags token sets that appear in more than one
    position (shared-exposure warnings).

    All scalar totals are expressed in the common token0 numeraire
    enforced by the primitive. Mixed-numeraire portfolios raise at
    .apply() time rather than silently summing incompatible units.

    Attributes
    ----------
    numeraire : str
        Common token0 symbol shared by all positions. Every total
        below is in these units.
    total_value : float
        Sum of per-position current_value, in numeraire.
    total_hold_value : float
        Sum of per-position hold_value, in numeraire. The counterfactual
        portfolio value if every position had been held rather than LP'd.
    total_fees : float
        Sum of per-position fee_income, in numeraire.
    total_net_pnl : float
        Sum of per-position net_pnl, in numeraire. Equivalently,
        total_value - total_hold_value.
    positions : List[PositionSummary]
        One summary per input position, in the caller's original input
        order. Ranking information is exposed separately via pnl_ranking
        to avoid reordering the caller's data.
    pnl_ranking : List[str]
        Position names ordered by net_pnl ascending (worst PnL first),
        tiebroken on il_percentage ascending (worst IL first on ties).
        Information, not verdict — the caller decides what to do with
        the ordering.
    shared_exposure_warnings : List[str]
        Human-readable notes for tokens that appear in more than one
        position (e.g., "ETH appears in 2 positions: ETH/USDC, ETH/DAI").
        Not statistical correlation — just token overlap, which is the
        risk concept LPs actually reason about. Empty list when no
        token is shared across multiple positions.

    Notes
    -----
    Why no exit_priority. Ranking positions by PnL is useful; calling
    that ranking "exit priority" overclaims — the primitive can't know
    whether a bad PnL position should be exited (it might be at its
    worst and due to mean-revert) or held (exit cost might exceed hold
    cost). Matches DetectRugSignals' "signal surfacer, not verdict
    generator" stance.

    Why numeraire is required uniform. Summing a BTC-pair position's
    value (in BTC) and an ETH-pair position's value (in ETH) is
    nonsensical without a cross-rate DeFiPy doesn't carry. v1 rejects
    mixed-numeraire portfolios with a helpful error rather than silently
    producing a meaningless total. A future release can add
    multi-numeraire support; the current return shape leaves room.

    Why positions stay in input order. Reordering the caller's data by
    PnL is surprising — the caller knows which position is which by
    index. Exposing the ranking via pnl_ranking (names, not indices)
    gives both views without either rewriting the other.
    """
    numeraire: str
    total_value: float
    total_hold_value: float
    total_fees: float
    total_net_pnl: float
    positions: List[PositionSummary]
    pnl_ranking: List[str]
    shared_exposure_warnings: List[str]
