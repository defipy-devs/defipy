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
from uniswappy.process.deposit import SwapDeposit

from ...utils.data import DepositSplitResult


# V2 protocol fee as a fraction (30 bps via 997/1000 in the swap math).
_V2_FEE_FRAC = 0.003


class OptimalDepositSplit:

    """ Compute the optimal swap fraction for a single-sided V2 deposit.

        Answers Q3.3 (and informs Q9.5) from DEFIMIND_TIER1_QUESTIONS.md.
        "I have X tokens of one side — what fraction should I swap to
        the other side before depositing so I end up with zero leftover
        dust?" The naive answer is 50/50, but the V2 fee plus the
        swap's own price impact shift the optimum. Specifically: in
        the limit of a zero-size deposit, α → 1/(1+f) ≈ 0.50075
        (f = 0.997 is the fee multiplier, so there's a slight upward
        bias from fee asymmetry). As the deposit grows, α decreases
        monotonically — larger swaps move the price more, so each
        unit swapped buys less, so you need to swap less. The
        direction is counterintuitive if you think of the fee as
        "you'll lose some to the LPs so swap more" — but the fee is
        already baked into the swap output, and what dominates at
        size is the AMM curve's own nonlinearity.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Non-mutating. This primitive is a projection — it tells you
        what `SwapDeposit().apply(...)` WOULD do against the current
        pool state without executing it. The pool is not modified. If
        the caller wants to execute, they use SwapDeposit. If they want
        to preview, they use this primitive.

        Notes
        -----
        V2-only in v1. V2 has a clean closed-form solution (the zap-in
        quadratic) already derived and tested in
        `uniswappy.process.deposit.SwapDeposit._calc_univ2_deposit_portion`.
        V3 uses scipy.optimize.minimize internally and depends on
        `UniV3Helper.quote` which is tracked in the cleanup backlog
        for its hard-coded-997-fee issue. Rather than propagate that
        latent bug into a projection primitive, v1 rejects V3 cleanly;
        extension comes after the UniV3Helper fix lands. V2 raises
        `ValueError` with a backlog-referencing message so the caller
        understands the scope choice rather than assuming the
        primitive is broken.

        Scope for "deposit larger than reserves." The closed-form
        quadratic does not have an upper bound on amount_in vs.
        reserves. A deposit that's a very large fraction of reserves
        still produces a valid α in (0, 1), but the swap leg will
        incur heavy slippage. The primitive does NOT reject such
        inputs — the slippage_cost and slippage_pct fields surface
        the friction, and the caller decides whether to proceed.
        Consistent with AggregatePortfolio's stance: the primitive
        surfaces the shape, the caller reads the signal.

        Expected LP tokens formula. V2's add_liquidity mints:
          L_new = min(b_0 · L / res_0,  b_1 · L / res_1)
        after the swap, using post-swap reserves and post-swap
        total_supply. At the optimal split the two ratios match to
        within integer-math rounding; the min just picks whichever
        side rounds down. This primitive computes the same thing
        from the math side, so the returned expected_lp_tokens is
        what the caller will actually receive if they execute.

        Slippage semantics. slippage_cost is measured in token_out
        units: (α · amount_in · p_spot) - swap_amount_out, where
        p_spot is the pre-swap spot price of token_in in token_out.
        Always >= 0 by the no-arbitrage property of constant-product
        swaps. slippage_pct normalizes by (α · amount_in · p_spot)
        to give a fraction in [0, 1). Matches CalculateSlippage's
        denomination convention so the two primitives compose cleanly.

        Integer-math boundary. V2's internal quadratic runs in machine
        units (SaferMath.mul_div_round on integer reserves). The
        SwapDeposit helper handles the machine↔human conversion; this
        primitive invokes that helper once and does the rest of the
        math in pure floats on human units. The fraction α is
        unit-free, so it travels clean across the boundary.
    """

    def __init__(self):
        pass

    def apply(self, lp, token_in, amount_in):

        """ apply

            Compute the optimal deposit split for a single-sided V2
            deposit of amount_in tokens of token_in.

            Parameters
            ----------
            lp : UniswapExchange
                V2 LP exchange at current state. V3 raises ValueError.
            token_in : ERC20
                The token being provided (the "single side"). Must be
                one of the pool's two tokens.
            amount_in : float
                Total human-units amount of token_in available to
                deposit via the zap. Must be > 0.

            Returns
            -------
            DepositSplitResult

            Raises
            ------
            ValueError
                If lp is not V2, token_in is not in the pool,
                amount_in <= 0, or the pool has zero reserves on
                either side.
        """

        if lp.version != UniswapExchangeData.VERSION_V2:
            raise ValueError(
                "OptimalDepositSplit v1: only V2 pools supported; "
                "got version {!r}. V3 extension is tracked behind "
                "the UniV3Helper.quote fee-passthrough fix in the "
                "cleanup backlog.".format(lp.version)
            )

        if token_in.token_name not in (lp.token0, lp.token1):
            raise ValueError(
                "OptimalDepositSplit: token_in {!r} not in pool "
                "(pool holds {}, {})".format(
                    token_in.token_name, lp.token0, lp.token1
                )
            )

        if amount_in <= 0:
            raise ValueError(
                "OptimalDepositSplit: amount_in must be > 0; "
                "got {}".format(amount_in)
            )

        tokens = lp.factory.token_from_exchange[lp.name]
        x_tkn = tokens[lp.token0]
        y_tkn = tokens[lp.token1]

        reserve0 = lp.get_reserve(x_tkn)
        reserve1 = lp.get_reserve(y_tkn)

        if reserve0 <= 0 or reserve1 <= 0:
            raise ValueError(
                "OptimalDepositSplit: pool reserves must be > 0; "
                "got reserve0={}, reserve1={}".format(
                    reserve0, reserve1
                )
            )

        # Determine which side is input vs. opposing, in human units.
        if token_in.token_name == lp.token0:
            reserve_in = reserve0
            reserve_out = reserve1
        else:
            reserve_in = reserve1
            reserve_out = reserve0

        # Spot price of token_in in token_out, pre-swap.
        # Pure reserve ratio, no fee. Safe under the lp.get_reserve
        # helper regardless of V2/V3 precision setting.
        spot_price = reserve_out / reserve_in

        # Optimal fraction from the V2 zap-in quadratic. Delegates to
        # the in-house SwapDeposit helper which handles the
        # human↔machine unit conversion internally. Pure read — the
        # helper does not mutate the pool.
        alpha = SwapDeposit()._calc_univ2_deposit_portion(
            lp, token_in, amount_in
        )

        # Swap leg in human units.
        swap_amount_in = alpha * amount_in
        swap_amount_out = lp.get_amount_out(swap_amount_in, token_in)

        # Deposit leg. The remaining (1 - α) of amount_in stays as
        # token_in; it's paired with the full swap output on the
        # token_out side.
        deposit_amount_in = (1.0 - alpha) * amount_in
        deposit_amount_out = swap_amount_out

        # Post-swap reserves for the LP-tokens calculation. After a
        # swap of swap_amount_in (net of fee), reserves shift:
        #   reserve_in  += swap_amount_in       (full input goes in)
        #   reserve_out -= swap_amount_out      (buyer takes the output)
        # Fee stays in the pool (the 0.3% of swap_amount_in), which is
        # already reflected in swap_amount_out being derived from the
        # fee-adjusted get_amount_out formula. The reserves after swap
        # increase by the full swap_amount_in on the input side.
        if token_in.token_name == lp.token0:
            post_res0 = reserve0 + swap_amount_in
            post_res1 = reserve1 - swap_amount_out
        else:
            post_res0 = reserve0 - swap_amount_out
            post_res1 = reserve1 + swap_amount_in

        # Total supply post-swap is unchanged — a swap doesn't mint or
        # burn LP tokens, it just moves reserves. Use current supply.
        total_supply = lp.get_liquidity()

        # V2 add_liquidity mint formula: L_new = min(b0·L/res0, b1·L/res1)
        # using POST-swap reserves and the to-be-deposited balances.
        if token_in.token_name == lp.token0:
            b0 = deposit_amount_in
            b1 = deposit_amount_out
        else:
            b0 = deposit_amount_out
            b1 = deposit_amount_in

        if post_res0 <= 0 or post_res1 <= 0:
            # Swap would drain a side. Shouldn't happen for valid alpha
            # in (0, 1) with positive reserves, but guard defensively.
            raise ValueError(
                "OptimalDepositSplit: swap at optimal fraction would "
                "drain pool reserves. Likely amount_in is too large "
                "relative to reserves; reduce amount_in."
            )

        lp_from_side_0 = b0 * total_supply / post_res0
        lp_from_side_1 = b1 * total_supply / post_res1
        expected_lp_tokens = min(lp_from_side_0, lp_from_side_1)

        # Slippage on the swap leg, denominated in token_out.
        # Spot-priced value of the swap input minus actual output.
        spot_priced_swap_value = swap_amount_in * spot_price
        slippage_cost = spot_priced_swap_value - swap_amount_out

        # Guard against degenerate slippage_pct when the swap leg has
        # essentially no size (alpha → 0 edge; shouldn't happen for
        # valid inputs but keeps the denominator honest).
        if spot_priced_swap_value > 0:
            slippage_pct = slippage_cost / spot_priced_swap_value
        else:
            slippage_pct = 0.0

        return DepositSplitResult(
            token_in_name = token_in.token_name,
            amount_in = amount_in,
            optimal_fraction = alpha,
            swap_amount_in = swap_amount_in,
            swap_amount_out = swap_amount_out,
            deposit_amount_in = deposit_amount_in,
            deposit_amount_out = deposit_amount_out,
            expected_lp_tokens = expected_lp_tokens,
            slippage_cost = slippage_cost,
            slippage_pct = slippage_pct,
        )
