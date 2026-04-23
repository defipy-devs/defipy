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

from uniswappy.cpt.quote import LPQuote

from ...utils.data import MEVDetectionResult


# Normal sandwich extraction is typically 50-500 bps depending on trade
# size and pool depth. Below 50 bps is plausibly integer rounding or
# legitimate price drift between quote and execution; above 50 bps
# starts looking like deliberate MEV extraction.
_DEFAULT_FRONTRUN_THRESHOLD_BPS = 50.0


class DetectMEV:

    """ Detect likely MEV extraction by comparing a trade's actual on-chain
        output to the invariant-predicted output for the same pool state.

        Answers Q8.5 from DEFIMIND_TIER1_QUESTIONS.md — "Am I being
        frontrun?"

        The caller supplies three things: the LP object at the pool state
        that matches their tx execution context, the trade's input amount,
        and the actual output they received on-chain (from their tx
        receipt). The primitive computes what the invariant math says
        they SHOULD have received and reports the gap.

        Follows the DeFiPy primitive contract: stateless construction
        (modulo the frontrun threshold), computation at .apply(),
        structured dataclass return. Non-mutating — uses LPQuote which
        is a pure query.

        Notes
        -----
        What "extraction" means in this primitive. The reported
        extraction_amount is the difference between the invariant-
        predicted output at the SUPPLIED pool state and the caller's
        actual received amount. This captures frontrunning correctly
        ONLY if the caller supplies an lp whose reserves/ticks match
        what the chain held at their tx's block. If the caller supplies
        today's lp state for a trade that executed yesterday against
        different reserves, the extraction number conflates frontrun
        loss with market drift, and the "likely_frontrun" flag becomes
        noisy. Historical state reconstruction is outside this
        primitive's scope — it's an on-chain indexing concern (web3scout
        territory), not an AMM-math concern.

        V2 and V3 both supported. LPQuote dispatches to the correct
        invariant: V2's constant-product-with-fee, or V3's in-range
        virtual-reserves quote. Fees are included in theoretical_output
        on both sides, matching what get_amount_out / UniV3Helper.quote
        actually return on-chain — so the comparison is apples-to-apples.
        For large V3 trades that cross tick boundaries, theoretical_output
        inherits LPQuote's in-tick approximation; very large trades may
        show an apparent "underdelivery" that's really just the quote's
        single-tick assumption breaking down. Flagged in the scope notes.

        Threshold convention. frontrun_threshold_bps defaults to 50 bps.
        Only underdelivery with magnitude above threshold fires
        likely_frontrun; overdelivery (caller got MORE than expected)
        never fires the flag regardless of magnitude, because it's
        not a frontrun signal — it's a rebate, subsidy, or rounding
        quirk, and this primitive's job is specifically to detect
        extraction.

        Why not a "severity" field. We considered adding a severity
        bucket (low/medium/high) mirroring DetectRugSignals. Extraction
        magnitude is naturally continuous (bps float), so a single
        threshold + a human-readable value beats a bucketed proxy.
        Callers who want to classify can apply their own bucketing to
        extraction_bps. Matches the signal-surfacer-not-verdict-generator
        convention established by the pool_health primitives.
    """

    def __init__(self,
                 frontrun_threshold_bps = _DEFAULT_FRONTRUN_THRESHOLD_BPS):

        """ __init__

            Parameters
            ----------
            frontrun_threshold_bps : float, optional
                Minimum absolute extraction (in basis points of the
                theoretical output) to fire likely_frontrun when the
                caller got less than expected. Default 50 bps. Must
                be >= 0. Setting to 0 would flag any nonzero
                underdelivery including float rounding noise.

            Raises
            ------
            ValueError
                If frontrun_threshold_bps < 0.
        """

        if frontrun_threshold_bps < 0:
            raise ValueError(
                "DetectMEV: frontrun_threshold_bps must be >= 0; "
                "got {}".format(frontrun_threshold_bps)
            )

        self.frontrun_threshold_bps = frontrun_threshold_bps

    def apply(self, lp, token_in, amount_in, actual_output,
              lwr_tick = None, upr_tick = None):

        """ apply

            Compute the MEV-extraction gap for a trade.

            Parameters
            ----------
            lp : Exchange
                LP exchange at the pool state that matches the trade's
                execution context. V2 or V3.
            token_in : ERC20
                The token the caller swapped IN. Must be one of the
                pool's two tokens.
            amount_in : float
                Input amount, in human units. Must be > 0.
            actual_output : float
                The caller's actual on-chain output from tx receipt,
                in human units of token_out. Must be >= 0. (Zero is
                unusual but permissible — it describes a fully
                extracted or failed-settlement case.)
            lwr_tick : int, optional
                Lower tick (V3 positions only); passed through to
                LPQuote.
            upr_tick : int, optional
                Upper tick (V3 positions only).

            Returns
            -------
            MEVDetectionResult

            Raises
            ------
            ValueError
                If amount_in <= 0, actual_output < 0, or token_in is
                not in the pool.
        """

        if amount_in <= 0:
            raise ValueError(
                "DetectMEV: amount_in must be > 0; got {}".format(
                    amount_in
                )
            )

        if actual_output < 0:
            raise ValueError(
                "DetectMEV: actual_output must be >= 0; got {}".format(
                    actual_output
                )
            )

        if token_in.token_name not in (lp.token0, lp.token1):
            raise ValueError(
                "DetectMEV: token_in {!r} not in pool (pool holds "
                "{}, {})".format(
                    token_in.token_name, lp.token0, lp.token1
                )
            )

        # Theoretical output: what the invariant math says this trade
        # should have returned at the supplied pool state. LPQuote
        # handles V2 vs V3 dispatch and fee integration.
        theoretical_output = LPQuote(
            quote_opposing = True, include_fee = True,
        ).get_amount(lp, token_in, amount_in, lwr_tick, upr_tick)

        extraction_amount = theoretical_output - actual_output

        if theoretical_output > 0:
            extraction_pct = extraction_amount / theoretical_output
        else:
            # Degenerate case: invariant predicts zero output. Can
            # happen for trades so small they round to zero through
            # integer math, or for pools with zero liquidity.
            extraction_pct = 0.0

        extraction_bps = extraction_pct * 10000.0

        # Direction label. Float-precision matches → "matches"; strict
        # inequality on either side → named direction.
        if extraction_amount > 0:
            direction = "underdelivered"
        elif extraction_amount < 0:
            direction = "overdelivered"
        else:
            direction = "matches"

        # likely_frontrun fires ONLY for underdelivery above threshold.
        # Overdelivery never fires — it's not a frontrun pattern.
        likely_frontrun = (
            direction == "underdelivered"
            and extraction_bps > self.frontrun_threshold_bps
        )

        return MEVDetectionResult(
            amount_in = amount_in,
            token_in_name = token_in.token_name,
            theoretical_output = theoretical_output,
            actual_output = actual_output,
            extraction_amount = extraction_amount,
            extraction_pct = extraction_pct,
            extraction_bps = extraction_bps,
            direction = direction,
            likely_frontrun = likely_frontrun,
        )
