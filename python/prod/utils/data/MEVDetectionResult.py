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


@dataclass
class MEVDetectionResult:
    """ Structured result of DetectMEV primitive.

        Compares what the invariant math says a trade SHOULD have
        returned at a given pool state to what the caller actually
        received on-chain. Produced by DetectMEV; answers Q8.5.

        A positive extraction (underdelivery) is the expected signal
        when a trade was sandwiched — the attacker moved the price
        against the victim before their tx was mined, so the victim
        got less than the invariant predicted against the pre-sandwich
        state. Overdelivery is the rare opposite — usually a sign of
        rebates, subsidies, or rounding in the caller's favor. Near-
        zero extraction means the trade executed as expected.

        Attributes
        ----------
        amount_in : float
            Echo of the trade's input amount, in human units.
        token_in_name : str
            Symbol of the token sold.
        theoretical_output : float
            What the invariant predicts the output should have been,
            given the supplied lp state. Computed via LPQuote (fees
            included). In token_out units.
        actual_output : float
            What the caller actually received on-chain. Supplied by
            the caller from tx receipt data. In token_out units.
        extraction_amount : float
            theoretical_output - actual_output. Positive when the
            caller got less than expected; negative when more. In
            token_out units.
        extraction_pct : float
            extraction_amount / theoretical_output, as a fraction.
            Zero when theoretical_output == 0 (degenerate case).
        extraction_bps : float
            extraction_pct * 10000. Basis-points view used for the
            frontrun threshold comparison.
        direction : str
            One of:
              "underdelivered" — actual < theoretical; caller got less.
              "overdelivered"  — actual > theoretical; caller got more.
              "matches"        — actual == theoretical (to float precision).
        likely_frontrun : bool
            True only when direction == "underdelivered" AND
            abs(extraction_bps) exceeds the primitive's
            frontrun_threshold_bps. Overdelivery never flags regardless
            of magnitude — it's not a frontrun signal.

        Notes
        -----
        Scope. This primitive compares math to an externally-supplied
        actual output. It does NOT reconstruct historical pool state.
        The caller is responsible for supplying an lp object whose
        state matches the state their tx executed against; otherwise
        the "extraction" reported may reflect market drift between
        their tx and now, not frontrunning. Documented more fully
        in the DetectMEV class docstring.

        Threshold defaults. frontrun_threshold_bps defaults to 50 bps.
        Normal sandwich extraction ranges from 50 to 500 bps depending
        on trade size relative to pool depth. Anything below 50 bps is
        plausibly integer rounding or mild price drift; above 50 bps
        starts looking intentional. Callers tuning to a specific DEX
        or chain can override via the constructor.

        Numeraire. extraction_amount is in the same units as
        actual_output — the swap output token. If the caller wants
        a numeraire-consistent value, they convert at call-site.
    """
    amount_in: float
    token_in_name: str
    theoretical_output: float
    actual_output: float
    extraction_amount: float
    extraction_pct: float
    extraction_bps: float
    direction: str
    likely_frontrun: bool
