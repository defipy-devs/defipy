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

from ...utils.data import FeeAnomalyResult


# V2's hard-coded fee. The UniswapExchange swap math uses 997/1000 throughout
# (see get_amount_out0/1: amount_in * 997, denominator * 1000), which
# corresponds to 0.3% = 30 bps. V2 pools do NOT expose a .fee attribute;
# the fee is a protocol constant, not per-pool configuration.
_V2_FEE_BPS = 30
_V2_FEE_FRAC = 0.003

# Default discrepancy threshold for flagging an anomaly, in bps. 10 bps
# (0.1%) is well above the float/integer rounding noise a clean V2 pool
# produces (~1e-8 bps in practice) and well below anything a real skim
# contract would need to extract meaningful value.
_DEFAULT_DISCREPANCY_THRESHOLD_BPS = 10.0

# Default test trade size, expressed as a fraction of the input token's
# reserve. 1% is small enough not to move the pool appreciably but large
# enough that float-precision noise stays well below the anomaly
# threshold.
_DEFAULT_TEST_AMOUNT_FRAC = 0.01


class DetectFeeAnomaly:

    """ V2 pool fee-anomaly detector (invariant-vs-contract consistency).

        Answers Q7.3 from DEFIMIND_TIER1_QUESTIONS.md — "Is the fee
        structure what it claims to be?"

        Validates that the pool's actual swap output (from
        lp.get_amount_out) matches what the constant-product invariant
        predicts at the pool's stated fee. Any divergence flags a
        pool whose real behavior departs from its stated parameters —
        which could mean a proxy/wrapper skimming output, an
        implementation bug in the fee arithmetic, an admin-fee quirk,
        integer-math rounding adversarial to the trader, or other
        protocol-specific overhead. The primitive reports the
        observation cleanly; it does not assign motive.

        Design choice: Shape A only (invariant-vs-contract consistency).
        -----------------------------------------------------------
        Two shapes are possible for a fee-anomaly check:
          Shape A — compare actual output against what the invariant
            predicts at the pool's OWN stated fee. Internal-consistency
            check.
          Shape B — compare actual output against what the invariant
            predicts at a USER-SUPPLIED expected fee. Requires the
            caller to know what fee to expect.

        v1 ships Shape A only. It's the more general case (works
        without caller knowledge), it catches a richer class of
        misbehavior (skim wrappers, fee arithmetic bugs, hidden
        admin fees), and it's what the spec description captures.
        Shape B is deferrable as an optional `expected_fee_bps`
        parameter in a future iteration.

        Scope limits.
        -------------
        - V2 only. V2's fee is a protocol constant (30 bps via 997/1000
          in the swap math); the pool object does not expose a .fee
          attribute. The invariant formula at that fee is known and
          computable in floats.
        - V3 raises ValueError. V3 pools have a configurable .fee but
          the available in-range quote path (UniV3Helper.quote) uses
          a hard-coded 30-bps constant that diverges from .fee for
          non-30-bps pools. This is itself a latent issue (tracked in
          the cleanup backlog), but it means we can't cleanly compare
          invariant-predicted output to pool-actual output on V3
          without either mutating state (lp.swap) or introducing a
          non-mutating quote path that respects .fee. Either is
          viable but beyond v1 scope.
        - Stableswap / Balancer raise ValueError. Different invariants;
          future work.

        What "pool_underdelivers" catches.
        ----------------------------------
        The pool's actual output is LESS than the invariant predicts
        at the stated fee. Possible causes (not distinguished by
        this primitive):
        - Proxy/wrapper contract silently reducing output (true skim)
        - Undocumented admin fee taken before the caller's receipt
        - Bug in the fee arithmetic (wrong numerator/denominator)
        - Integer-math rounding adversarial to the trader
        - Reentrancy guards or slippage checks reducing returned value

        What "pool_overdelivers" catches.
        ---------------------------------
        The pool's actual output is MORE than the invariant predicts.
        Possible causes:
        - Fee rebate or subsidy mechanism (pool charges stated fee but
          rebates some back)
        - Fee routing that doesn't reduce user receipt (fee goes
          elsewhere but invariant math still underestimates output)
        - Bug in the trader's favor
        - Floor-division rounding accumulating the trader's way
        - Wrapper adding reward tokens alongside the swap output

        What it does NOT catch.
        -----------------------
        An honestly-advertised high fee. A pool where
        stated_fee_bps = 100 (1%) and the output exactly matches the
        invariant at 1% will show anomaly_detected = False. Whether
        1% is reasonable for a given asset pair is a product question,
        not a math question. This primitive answers the math question.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.
    """

    def __init__(self,
                 discrepancy_threshold_bps = _DEFAULT_DISCREPANCY_THRESHOLD_BPS):

        """ __init__

            Parameters
            ----------
            discrepancy_threshold_bps : float, optional
                Minimum absolute discrepancy (in basis points of
                theoretical output) to flag as an anomaly. Default
                10 bps. Must be >= 0. A value of 0 would flag every
                float-precision rounding difference; 10 bps gives
                comfortable headroom over normal integer-math noise.
        """

        if discrepancy_threshold_bps < 0:
            raise ValueError(
                "DetectFeeAnomaly: discrepancy_threshold_bps must be "
                ">= 0; got {}".format(discrepancy_threshold_bps)
            )

        self.discrepancy_threshold_bps = discrepancy_threshold_bps

    def apply(self, lp, token_in, test_amount = None):

        """ apply

            Run a synthetic test trade through the invariant (at the
            stated fee) and compare to the pool's actual reported
            output. Does NOT mutate the pool — uses lp.get_amount_out
            which is a pure query.

            Parameters
            ----------
            lp : UniswapExchange
                V2 LP exchange. V3 / Stableswap / Balancer raise
                ValueError.
            token_in : ERC20
                The token being swapped IN. Must be one of the pool's
                two tokens.
            test_amount : float, optional
                Size of the synthetic trade, in token_in units. If
                None (default), uses 1% of the input token's reserve.
                Must be > 0 when specified.

            Returns
            -------
            FeeAnomalyResult

            Raises
            ------
            ValueError
                If lp is not a V2 exchange, token_in is not in the
                pool, test_amount is <= 0, or constructor
                discrepancy_threshold_bps was invalid.
        """

        # Scope: V2 only. V3 and other protocols are out of scope for v1.
        if lp.version != UniswapExchangeData.VERSION_V2:
            raise ValueError(
                "DetectFeeAnomaly v1: only V2 pools supported; got "
                "version {!r}. V3 fee-anomaly detection requires a "
                "non-mutating quote path that honors lp.fee; tracked "
                "for a future release.".format(lp.version)
            )

        # Validate token_in.
        if token_in.token_name not in (lp.token0, lp.token1):
            raise ValueError(
                "DetectFeeAnomaly: token_in {!r} not in pool "
                "(pool holds {}, {})".format(
                    token_in.token_name, lp.token0, lp.token1
                )
            )

        # Determine input reserve (in human units) and opposing reserve.
        # Pool reserves are in machine units; convert for the math.
        if token_in.token_name == lp.token0:
            reserve_in = lp.convert_to_human(lp.reserve0)
            reserve_out = lp.convert_to_human(lp.reserve1)
        else:
            reserve_in = lp.convert_to_human(lp.reserve1)
            reserve_out = lp.convert_to_human(lp.reserve0)

        # Guard against uninitialized pools.
        if reserve_in <= 0 or reserve_out <= 0:
            raise ValueError(
                "DetectFeeAnomaly: pool reserves must be > 0; got "
                "reserve_in={}, reserve_out={}".format(
                    reserve_in, reserve_out
                )
            )

        # Resolve test_amount. Default: 1% of input reserve.
        if test_amount is None:
            effective_amount = reserve_in * _DEFAULT_TEST_AMOUNT_FRAC
        else:
            if test_amount <= 0:
                raise ValueError(
                    "DetectFeeAnomaly: test_amount must be > 0; "
                    "got {}".format(test_amount)
                )
            effective_amount = test_amount

        # Theoretical output from the constant-product-with-fee formula.
        #   dy = (dx · (1 − fee) · y) / (x + dx · (1 − fee))
        # In pure floats. fee = 0.003 (30 bps) for V2.
        dx_net = effective_amount * (1.0 - _V2_FEE_FRAC)
        theoretical_output = (dx_net * reserve_out) / (reserve_in + dx_net)

        # Actual output from the pool's own get_amount_out.
        actual_output = lp.get_amount_out(effective_amount, token_in)

        # Signed discrepancy in bps. Positive = pool underdelivers.
        #   discrepancy_bps = (theoretical − actual) / theoretical · 10000
        if theoretical_output == 0:
            # Degenerate case — effectively no trade happened.
            # Treat as zero discrepancy, default direction.
            discrepancy_bps = 0.0
        else:
            discrepancy_bps = (
                (theoretical_output - actual_output) / theoretical_output
            ) * 10000.0

        # Direction label. Zero (essentially unreachable in float math)
        # defaults to "pool_underdelivers" per the documented tie-breaker.
        if discrepancy_bps >= 0:
            direction = "pool_underdelivers"
        else:
            direction = "pool_overdelivers"

        anomaly_detected = (
            abs(discrepancy_bps) > self.discrepancy_threshold_bps
        )

        return FeeAnomalyResult(
            stated_fee_bps = _V2_FEE_BPS,
            test_amount = effective_amount,
            theoretical_output = theoretical_output,
            actual_output = actual_output,
            discrepancy_bps = discrepancy_bps,
            direction = direction,
            anomaly_detected = anomaly_detected,
        )
