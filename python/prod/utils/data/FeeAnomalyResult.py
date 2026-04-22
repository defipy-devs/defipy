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
class FeeAnomalyResult:
    """Fee-anomaly diagnostic for a single pool.

    Produced by DetectFeeAnomaly. Reports whether the pool's actual
    swap output (from lp.get_amount_out) matches what the invariant
    predicts at the pool's stated fee. A mismatch flags a pool whose
    real behavior diverges from its stated parameters — which could
    mean a proxy/wrapper siphoning output, an implementation bug, a
    subsidy mechanism, or integer-math rounding accumulating in an
    unusual direction. The primitive reports the observation; it
    does not assign motive.

    Attributes
    ----------
    stated_fee_bps : int
        The pool's own reported fee in basis points. Read from
        lp.fee directly. For V2 this is typically 30 (0.3%); for
        V3 it's one of 100 / 500 / 3000 / 10000.
    test_amount : float
        The trade size used for the comparison, in token_in units.
    theoretical_output : float
        What the invariant predicts the output should be, given the
        pool's stated fee and reserves. Computed in pure floats from
        the constant-product-with-fee formula (V2) or its
        in-tick-range V3 equivalent using virtual reserves.
    actual_output : float
        What lp.get_amount_out actually returns for the test trade.
    discrepancy_bps : float
        (theoretical_output − actual_output) / theoretical_output * 10000.
        Signed: positive means the pool underdelivers vs. math,
        negative means it overdelivers. In basis points of the
        theoretical output.
    direction : str
        One of "pool_underdelivers" or "pool_overdelivers", based on
        the sign of discrepancy_bps. Always populated. A zero
        discrepancy (essentially unreachable in float math) is
        labeled "pool_underdelivers" by convention.
    anomaly_detected : bool
        True if abs(discrepancy_bps) exceeds the primitive's
        discrepancy_threshold_bps. The discrepancy magnitude is
        what matters for the flag; the sign is reported in
        direction but doesn't affect the boolean.

    Notes
    -----
    Scope. This primitive validates that pool output matches what
    its stated fee predicts. It does NOT judge whether the stated
    fee itself is reasonable or competitive — that's a product
    decision, not a math check. A pool charging 1% honestly
    (lp.fee = 10000, pool outputs exactly what 1% predicts) will
    show anomaly_detected = False here; whether 1% is reasonable
    for its asset class is for the caller to decide.

    What "pool_underdelivers" catches. The pool hands back less
    output than the invariant predicts at its stated fee. Possible
    causes (not distinguished by this primitive):
    - A proxy/wrapper contract silently reducing output (true skim)
    - An unreported admin fee diverted before the caller's receipt
    - Implementation bugs in the fee arithmetic
    - Integer-math rounding adversarial to the trader
    - Reentrancy or slippage guards returning a reduced value

    What "pool_overdelivers" catches. The pool hands back more
    output than the invariant predicts. Possible causes (again,
    not distinguished):
    - Fee-subsidy or rebate mechanisms
    - Fee routing that doesn't reduce the user's receipt
    - Bugs in the trader's favor
    - Floor-division rounding that accumulates in the trader's
      direction
    - A wrapper that adds reward tokens alongside the swap output

    The primitive is a signal surfacer. The diagnosis — skim vs.
    subsidy vs. bug vs. admin-fee vs. rounding — is a human or
    LLM call based on context (audit status, protocol docs,
    competing pools in the same family). This primitive provides
    the observation cleanly; interpretation belongs elsewhere.

    Signed convention. discrepancy_bps is positive when the pool
    underdelivers. Callers checking "is the pool ripping me off"
    should look for anomaly_detected and direction == "pool_
    underdelivers" — the combination. direction alone is always
    populated; anomaly_detected alone tells you the magnitude
    matters; the pair together captures "meaningful underdelivery
    worth investigating."
    """
    stated_fee_bps: int
    test_amount: float
    theoretical_output: float
    actual_output: float
    discrepancy_bps: float
    direction: str
    anomaly_detected: bool
