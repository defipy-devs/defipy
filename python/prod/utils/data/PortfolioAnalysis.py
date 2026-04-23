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
from typing import Any, List

from .PositionAnalysis import PositionAnalysis


@dataclass
class PositionSummary:
    """Per-position summary for inclusion in PortfolioAnalysis.positions.

    Compact view of one Analyze*Position result plus the position's
    token pair, for ranking and filtering at the portfolio level.
    The full analyzer output is carried on .analysis so callers who
    got a portfolio-level verdict don't need to re-run per-position.

    Cross-protocol: .analysis may be a PositionAnalysis (V2/V3),
    BalancerPositionAnalysis, or StableswapPositionAnalysis. The
    caller can dispatch on isinstance to access protocol-specific
    fields; the scalars on PositionSummary (net_pnl, il_percentage,
    fee_income) are extracted uniformly so portfolio-level ranking
    doesn't need to care.

    Attributes
    ----------
    name : str
        Human-readable label for this position (from PortfolioPosition.name
        or a protocol-appropriate default).
    protocol : str
        One of "uniswap_v2" | "uniswap_v3" | "balancer" | "stableswap".
        Surfaced so callers can dispatch without re-inspecting .lp.
    net_pnl : float
        In the portfolio's common first-token numeraire. For
        stableswap positions in the unreachable-alpha regime this
        is 0.0 and the position is flagged in
        PortfolioAnalysis.shared_exposure_warnings (or a dedicated
        notes list in a future release).
    il_percentage : float
        Fractional IL drag. Stableswap unreachable positions report 0.0.
    fee_income : float
        In numeraire units. Always 0.0 for Balancer/Stableswap in v1.
    tokens : List[str]
        Token symbols for this position in pool order. Used by
        shared-exposure detection.
    analysis : Any
        Full analyzer output — one of PositionAnalysis,
        BalancerPositionAnalysis, or StableswapPositionAnalysis.
        Typed as Any because the union would bloat imports;
        isinstance-dispatch at the call site.
    """
    name: str
    protocol: str
    net_pnl: float
    il_percentage: float
    fee_income: float
    tokens: List[str]
    analysis: Any


@dataclass
class PortfolioAnalysis:
    """Aggregate view of multiple LP positions sharing a common first-token numeraire.

    Produced by AggregatePortfolio. Chains the appropriate
    Analyze*Position primitive across N positions (protocol-dispatched
    on lp isinstance), sums the scalar metrics in a shared numeraire,
    ranks by net_pnl, and flags token sets that appear in more than
    one position (shared-exposure warnings).

    All scalar totals are expressed in the common first-token numeraire
    enforced by the primitive. Mixed-numeraire portfolios raise at
    .apply() time rather than silently summing incompatible units.

    Cross-protocol aggregation: portfolios may contain a mix of V2,
    V3, Balancer, and Stableswap positions. Per-protocol numeraire
    conventions are pre-rationalized at the primitive level so sums
    are in comparable units (see AggregatePortfolio docstring for the
    details). Stableswap positions in the unreachable-alpha regime
    are skipped from totals and flagged in notes.

    Attributes
    ----------
    numeraire : str
        Common first-token symbol shared by all positions. For V2/V3
        this is lp.token0; for Balancer/Stableswap it's the first
        token in the pool's insertion order. All positions must share
        this symbol.
    total_value : float
        Sum of per-position current_value, in numeraire.
    total_hold_value : float
        Sum of per-position hold_value, in numeraire.
    total_fees : float
        Sum of per-position fee_income, in numeraire. For v1 this is
        contributed to only by V2/V3 positions; Balancer and Stableswap
        fee income is 0 pending per-LP attribution support.
    total_net_pnl : float
        Sum of per-position net_pnl, in numeraire.
    positions : List[PositionSummary]
        One summary per input position, in the caller's original input
        order.
    pnl_ranking : List[str]
        Position names ordered by net_pnl ascending (worst PnL first),
        tiebroken on il_percentage ascending.
    shared_exposure_warnings : List[str]
        Human-readable notes for tokens appearing in 2+ positions. Also
        carries unreachable-alpha notices for stableswap positions that
        couldn't be fully aggregated.
    """
    numeraire: str
    total_value: float
    total_hold_value: float
    total_fees: float
    total_net_pnl: float
    positions: List[PositionSummary]
    pnl_ranking: List[str]
    shared_exposure_warnings: List[str]
