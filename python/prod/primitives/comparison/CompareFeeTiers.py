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

from uniswappy.utils.data import UniswapExchangeData

from ..pool_health import CheckPoolHealth
from ..risk import CheckTickRangeStatus
from ...utils.data import FeeTierMetrics, FeeTierComparison


class CompareFeeTiers:

    """ Compare V3 fee tiers for the same token pair across N candidate pools.

        Answers Q4.3 from DEFIMIND_TIER1_QUESTIONS.md — "Should I move to
        a different fee tier?" — for Uniswap V3. Takes a list of
        candidate pools (same pair, different fee tiers), runs
        CheckPoolHealth and CheckTickRangeStatus against each, and
        returns per-tier metrics plus independent orderings by observed
        fee yield and by TVL.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Composition pattern: breadth-chain (same primitives applied N
        times, results aggregated). Sibling to AggregatePortfolio
        structurally; cousin to DetectRugSignals in that it reads only
        its dependencies' outputs and does not touch lp internals.

        Notes
        -----
        V3-only. V2 pools have a single hard-coded fee (30 bps via
        997/1000 in UniswapExchange.get_amount_out0/1) — there are no
        tiers to compare. Mixed V2/V3 input or any V2 input raises
        ValueError.

        Common-pair rejection. All candidates must share token0 AND
        token1 symbols. Comparing fee tiers of different pairs would
        collapse independent questions into a spurious ranking; this
        primitive errors early rather than silently mixing them.
        Callers with mixed pairs should group by pair and call
        CompareFeeTiers once per group. Same stance as
        AggregatePortfolio's common-numeraire rejection.

        No forward volume model. The catalog spec mentions
        "fee_income_estimate" and "net_return"; v1 does not project
        forward because the pool object carries no volume model the
        primitive could honestly ground that projection in. Instead,
        v1 reports observed_fee_yield — cumulative fees earned to
        date, in token0 numeraire, divided by current TVL. It's a
        rate not a forecast. Callers who know the pool's age
        annualize by dividing by (age_in_years); callers who want a
        forward projection compose with their own volume assumptions.

        No single "optimal tier" verdict. Different axes (observed
        yield, TVL, range status) favor different tiers. The primitive
        exposes two orderings and the per-tier metrics; the caller
        picks. Matches the signal-surfacer-not-verdict-generator
        convention from DetectRugSignals / AggregatePortfolio /
        AssessDepegRisk / DetectFeeAnomaly.

        position_size_lp is an echo. v1 ranks at the pool level, not
        the position level. position_size_lp is preserved on the input
        dataclass for forward compatibility (future extensions may add
        per-position metrics alongside pool-level ones) but is not
        read during comparison. Including it avoids breaking the
        signature when that extension lands.

        CheckPoolHealth composition boundary. This primitive reads
        only what CheckPoolHealth returns per pool — no direct lp.*
        access beyond what's needed to extract the fee tier itself
        (lp.fee) and validate the common-pair invariant (lp.token0,
        lp.token1). If a per-tier metric can't be expressed from
        CheckPoolHealth's output plus CheckTickRangeStatus's output,
        it belongs on a different primitive or the dependency needs
        extending.
    """

    def __init__(self):
        pass

    def apply(self, candidates):

        """ apply

            Compare fee tiers across N candidate V3 pools.

            Parameters
            ----------
            candidates : list[FeeTierCandidate]
                One FeeTierCandidate per pool to compare. Must contain
                at least one entry. All candidates must be V3, must
                share token0 and token1 symbols, and each must have
                lwr_tick < upr_tick.

            Returns
            -------
            FeeTierComparison
                Structured comparison with per-tier metrics in input
                order, an ordering best-first by observed_fee_yield
                (None-yield candidates sorted last), an ordering
                largest-first by pool_tvl_in_token0, and informational
                notes.

            Raises
            ------
            ValueError
                If candidates is empty, any candidate is not a V3 pool,
                candidates have mismatched token0 or token1 symbols,
                or any candidate has lwr_tick >= upr_tick.
        """

        if not candidates:
            raise ValueError(
                "CompareFeeTiers: candidates must be a non-empty list"
            )

        self._validate_candidates(candidates)

        # Common pair — guaranteed consistent by validation.
        numeraire = candidates[0].lp.token0
        pair = "{}/{}".format(
            candidates[0].lp.token0, candidates[0].lp.token1
        )

        tiers = []
        notes = []
        for c in candidates:
            metrics = self._analyze_candidate(c)
            tiers.append(metrics)
            notes.extend(self._notes_for(metrics))

        # Ordering best-first by observed_fee_yield. None sorts last,
        # stable on input order — indexing by position in the original
        # list breaks ties deterministically.
        enumerated_tiers = list(enumerate(tiers))
        ranking_by_yield = [
            t.name for _, t in sorted(
                enumerated_tiers,
                key = lambda it: (
                    # None → infinity so it sinks to the bottom
                    float('inf') if it[1].observed_fee_yield is None
                    else -it[1].observed_fee_yield,
                    it[0],   # stable tiebreak on input order
                ),
            )
        ]

        # Ordering largest-first by TVL. TVL is always a float, no
        # None handling needed.
        ranking_by_tvl = [
            t.name for _, t in sorted(
                enumerated_tiers,
                key = lambda it: (-it[1].pool_tvl_in_token0, it[0]),
            )
        ]

        return FeeTierComparison(
            numeraire = numeraire,
            pair = pair,
            tiers = tiers,
            ranking_by_observed_fee_yield = ranking_by_yield,
            ranking_by_tvl = ranking_by_tvl,
            notes = notes,
        )

    def _validate_candidates(self, candidates):

        """ _validate_candidates

            Enforce V3-only, common-pair, and tick-ordering invariants.

            Raises
            ------
            ValueError
                On any violation. Message identifies the offending
                candidate's position in the input list for debuggability.
        """

        first_token0 = candidates[0].lp.token0
        first_token1 = candidates[0].lp.token1

        for i, c in enumerate(candidates):
            if c.lp.version != UniswapExchangeData.VERSION_V3:
                raise ValueError(
                    "CompareFeeTiers: candidate {} has version {!r}; "
                    "V3 only. V2 pools have a single hard-coded fee "
                    "and no tiers to compare.".format(i, c.lp.version)
                )

            if c.lp.token0 != first_token0 or c.lp.token1 != first_token1:
                raise ValueError(
                    "CompareFeeTiers: candidate {} has pair {}/{}, "
                    "expected {}/{}. All candidates must share token0 "
                    "and token1. Group by pair and call once per group."
                    .format(
                        i, c.lp.token0, c.lp.token1,
                        first_token0, first_token1
                    )
                )

            if c.lwr_tick >= c.upr_tick:
                raise ValueError(
                    "CompareFeeTiers: candidate {} has "
                    "lwr_tick ({}) >= upr_tick ({}); lwr must be "
                    "strictly less than upr.".format(
                        i, c.lwr_tick, c.upr_tick
                    )
                )

    def _analyze_candidate(self, candidate):

        """ _analyze_candidate

            Run CheckPoolHealth + CheckTickRangeStatus on one candidate,
            compute observed_fee_yield in token0, and assemble the
            FeeTierMetrics for it.

            Returns
            -------
            FeeTierMetrics
        """

        health = CheckPoolHealth().apply(candidate.lp)
        status = CheckTickRangeStatus().apply(
            candidate.lp, candidate.lwr_tick, candidate.upr_tick
        )

        fee_tier_bps = candidate.lp.fee // 100

        display_name = candidate.name if candidate.name is not None \
            else "{}/{}@{}bps".format(
                candidate.lp.token0, candidate.lp.token1, fee_tier_bps
            )

        observed_fee_yield = self._compute_fee_yield(health)

        return FeeTierMetrics(
            name = display_name,
            fee_tier_bps = fee_tier_bps,
            pool_tvl_in_token0 = health.tvl_in_token0,
            observed_fee_yield = observed_fee_yield,
            in_range = status.in_range,
            range_width_pct = status.range_width_pct,
        )

    def _compute_fee_yield(self, health):

        """ _compute_fee_yield

            Convert accumulated fees to token0 and divide by TVL to
            get cumulative fee yield. Returns None when the ratio is
            ill-defined (no fees, no price, or no TVL).

            Notes
            -----
            CheckPoolHealth already normalizes V2 and V3 fees through
            convert_to_human and reports them as total_fee0 /
            total_fee1 in human units. spot_price is token1-per-token0,
            so total_fee1 / spot_price converts token1 fees back to
            token0 numeraire.
        """

        total_fee0 = health.total_fee0
        total_fee1 = health.total_fee1

        if total_fee0 <= 0 and total_fee1 <= 0:
            return None

        if health.spot_price is None or health.spot_price <= 0:
            return None

        if health.tvl_in_token0 <= 0:
            return None

        total_fees_token0 = total_fee0 + total_fee1 / health.spot_price
        return total_fees_token0 / health.tvl_in_token0

    def _notes_for(self, metrics):

        """ _notes_for

            Generate informational notes for one candidate's metrics.
            Notes highlight conditions a caller might otherwise
            overlook; they do not duplicate what's directly visible
            on the metrics dataclass.

            Returns
            -------
            list[str]
        """

        notes = []
        if metrics.observed_fee_yield is None:
            notes.append(
                "{}: no accumulated fees, observed_fee_yield is None"
                .format(metrics.name)
            )
        if not metrics.in_range:
            notes.append(
                "{}: candidate range is out of range at current price"
                .format(metrics.name)
            )
        return notes
