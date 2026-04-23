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
from typing import List, Optional


@dataclass
class FeeTierMetrics:
    """ Per-tier metrics produced by CompareFeeTiers.

        One FeeTierMetrics instance per input FeeTierCandidate, in input
        order. Carries the pool-level and range-level scalars needed to
        rank candidates against each other on their own merits, without
        forecasting forward fee income.

        Attributes
        ----------
        name : str
            Display name, either caller-supplied or the
            "token0/token1@<bps>bps" default.
        fee_tier_bps : int
            Fee tier in basis points. Derived as lp.fee // 100 from the
            V3 pool's fee-in-pips. For the canonical Uniswap V3 tiers
            (100/500/3000/10000 pips) this is 1/5/30/100 bps exactly.
        pool_tvl_in_token0 : float
            Pool TVL in token0 units, straight from CheckPoolHealth.
            The common-numeraire rejection in CompareFeeTiers guarantees
            every candidate shares this numeraire.
        observed_fee_yield : Optional[float]
            Cumulative fees earned by the pool, denominated in token0,
            divided by current TVL in token0. A CUMULATIVE rate, not
            annualized — the pool object does not track real-world
            duration, so an APR figure would require a caller-supplied
            holding period. None when total_fee0 + total_fee1 == 0, or
            when spot_price or tvl_in_token0 is zero. Callers who know
            the pool's age annualize by dividing by (age_in_years).
        in_range : bool
            True when the candidate's [lwr_tick, upr_tick] brackets the
            pool's current tick. From CheckTickRangeStatus.
        range_width_pct : float
            Total range width as a fraction of current price. From
            CheckTickRangeStatus.
    """
    name: str
    fee_tier_bps: int
    pool_tvl_in_token0: float
    observed_fee_yield: Optional[float]
    in_range: bool
    range_width_pct: float


@dataclass
class FeeTierComparison:
    """ Result of CompareFeeTiers.

        Compares V3 fee tiers for the same token pair by surfacing
        per-tier observed metrics and orderings. Does not name a single
        "optimal tier" — TVL, fee yield, and range status are
        independent axes; the caller decides what matters for their use
        case.

        Follows the signal-surfacer-not-verdict-generator convention
        established by DetectRugSignals and continued by
        AggregatePortfolio / AssessDepegRisk / DetectFeeAnomaly.

        Attributes
        ----------
        numeraire : str
            Common token0 symbol shared by every candidate, enforced by
            CompareFeeTiers. All TVL and fee-yield values in tiers use
            this as their numeraire.
        pair : str
            Common "token0/token1" symbol pair. All candidates must
            share both tokens; comparing fee tiers of different pairs
            is a different primitive.
        tiers : List[FeeTierMetrics]
            Per-candidate metrics in input order. Same length as the
            input list.
        ranking_by_observed_fee_yield : List[str]
            Candidate names ordered best-first by observed_fee_yield.
            Candidates with observed_fee_yield == None sort last,
            stable on input order (no historical fees == not comparable
            on this axis, so they go to the bottom).
        ranking_by_tvl : List[str]
            Candidate names ordered largest-first by pool_tvl_in_token0.
        notes : List[str]
            Informational strings — e.g., "candidate X has no
            accumulated fees, observed_fee_yield is None" or
            "candidate Y is out of range". Does not duplicate
            information already visible in the per-tier metrics; the
            notes are for conditions a caller might otherwise overlook.
    """
    numeraire: str
    pair: str
    tiers: List[FeeTierMetrics]
    ranking_by_observed_fee_yield: List[str]
    ranking_by_tvl: List[str]
    notes: List[str]
