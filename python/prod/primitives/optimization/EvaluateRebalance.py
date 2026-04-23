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

import math

from uniswappy.utils.data import UniswapExchangeData

from ...utils.data import RebalanceCostReport


# V2 fee multiplier (997/1000 per the UniswapExchange swap math).
_V2_F = 0.997


class EvaluateRebalance:

    """ Report the cost of cycling a V2 LP position (withdraw then re-deposit).

        Answers Q3.4 and Q8.4 from DEFIMIND_TIER1_QUESTIONS.md: "Should
        I rebalance now or wait?" and "What's the slippage cost of
        rebalancing my position?" For V2 specifically, rebalancing
        reduces to "withdraw the position completely, swap the off-side
        half to the target token, then re-zap the combined proceeds
        back into the same pool." This primitive computes that cycle's
        cost without executing it.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Non-mutating. This primitive projects what would happen if the
        caller withdrew and re-zapped, but the pool is not touched.
        Pair with RemoveLiquidity + Swap + SwapDeposit to execute.

        Notes
        -----
        Design scope: cost of cycling, not verdict on rebalancing.
        v1 reports the cost of the full exit-and-re-enter cycle \u2014
        slippage on both the withdrawal swap and the redeposit swap,
        plus the net LP-token loss. It does NOT:
          - Make a "rebalance" / "hold" / "marginal" recommendation.
            Whether the cost is worth paying depends on forward-looking
            assumptions (expected volume, expected price, holding
            period) that the pool object cannot supply. Consistent
            with the signal-surfacer convention.
          - Project fee income improvement from a new position. Same
            reason \u2014 requires a volume model outside the primitive's
            scope.
          - Compare multiple candidate redeployments. v1 assumes full
            redeploy into the same pool, which is the natural V2
            cycle shape. Multi-candidate comparison could come later
            as an extension.
          - Include gas estimates. Network-dependent; not in scope.

        V2-only in v1. V3 rebalancing is the more interesting case
        (move to a new tick range) but the withdraw path depends on
        virtual reserves and the UniV3Helper fee-passthrough issue
        tracked in the backlog. OptimalDepositSplit has the same
        scope; EvaluateRebalance inherits it. V3 raises ValueError
        cleanly with a message pointing to the tracked blocker.

        Math: three composed steps.
        ---------------------------
        1. Pro-rata withdrawal at current reserves:
             dx = (position_size_lp / total_supply) * reserve_in
             dy = (position_size_lp / total_supply) * reserve_out
           Updated reserves: (r_in - dx, r_out - dy). Supply shrinks
           by position_size_lp.

        2. Swap dx (token_in) for token_out against the shrunken
           reserves, using the V2 constant-product-with-fee formula:
             swap_out = (f * dx * (r_out - dy))
                        / ((r_in - dx) + f * dx)
           where f = 0.997. Updated reserves: (r_in, r_out - dy - swap_out).
           (The full dx goes back into reserve_in \u2014 fee stays in pool.)

           At this point the caller has (dy + swap_out) of token_out
           and no token_in. That's the full exit proceeds.

        3. Re-zap the full proceeds. Using the V2 zap quadratic against
           the post-swap reserves:
             f*\u03b1\u00b2*dx_z + r_in_post*\u03b1*(1+f) - r_in_post = 0
           where dx_z = dy + swap_out and r_in_post is the token_out
           reserve after step 2 (dy + swap_out will be going IN as
           token_out, so from the zap's perspective token_out is the
           "input" and token_in is the "output"). Solve for \u03b1,
           compute the swap output, and apply the V2 mint formula at
           the post-redeposit-swap reserves to get expected_lp_tokens.

        Slippage denomination. Both withdrawal and redeposit slippage
        are computed in their own swap-output units first — withdrawal
        slippage in token_out, redeposit slippage in token_in. For the
        total, redeposit slippage is rebased to token_out by multiplying
        by spot_price_post_withdraw (= token_out / token_in). This gives
        total_slippage_cost a consistent token_out denomination matching
        current_value. total_slippage_pct = total_slippage_cost /
        current_value — the fraction of position value lost to the
        full cycle.
    """

    def __init__(self):
        pass

    def apply(self, lp, token_out, position_size_lp):

        """ apply

            Compute the cost of cycling a V2 position.

            Parameters
            ----------
            lp : UniswapExchange
                V2 LP exchange at current state. V3 raises ValueError.
            token_out : ERC20
                The desired exit token (the single token the caller
                wants to end up holding before the re-zap). Must be
                one of the pool's two tokens.
            position_size_lp : float
                LP tokens in the current position, in human units.
                Must be > 0. Must be <= total_supply (you can't cycle
                more than exists).

            Returns
            -------
            RebalanceCostReport

            Raises
            ------
            ValueError
                If lp is not V2, token_out is not in the pool,
                position_size_lp <= 0, position_size_lp > total_supply,
                or the pool has zero reserves on either side.
        """

        if lp.version != UniswapExchangeData.VERSION_V2:
            raise ValueError(
                "EvaluateRebalance v1: only V2 pools supported; "
                "got version {!r}. V3 rebalancing depends on virtual "
                "reserves and the UniV3Helper fee-passthrough fix "
                "tracked in the cleanup backlog.".format(lp.version)
            )

        if token_out.token_name not in (lp.token0, lp.token1):
            raise ValueError(
                "EvaluateRebalance: token_out {!r} not in pool "
                "(pool holds {}, {})".format(
                    token_out.token_name, lp.token0, lp.token1
                )
            )

        if position_size_lp <= 0:
            raise ValueError(
                "EvaluateRebalance: position_size_lp must be > 0; "
                "got {}".format(position_size_lp)
            )

        total_supply = lp.get_liquidity()

        if position_size_lp > total_supply:
            raise ValueError(
                "EvaluateRebalance: position_size_lp ({}) exceeds "
                "total_supply ({}); can't cycle more than exists"
                .format(position_size_lp, total_supply)
            )

        # Reject full-pool ownership: withdrawing 100% leaves nothing
        # to swap against, so the cycle is undefined. V2's actual
        # `remove_liquidity` allows this (the pool just ends empty),
        # but there's no meaningful "rebalance" when you ARE the pool
        # — after exit there's no counterparty for the swap leg.
        # Use a small tolerance to catch near-100% ownership that
        # would also produce degenerate math.
        ownership_share = position_size_lp / total_supply
        if ownership_share > 0.999:
            raise ValueError(
                "EvaluateRebalance: position_size_lp is {:.4f} of "
                "total_supply ({:.1%} ownership). A rebalance cycle "
                "requires residual liquidity to swap against; at "
                "~100% ownership the cycle is undefined. Leave some "
                "share in the pool or use the v2_setup's two-LP "
                "pattern for tests.".format(
                    ownership_share, ownership_share,
                )
            )

        tokens = lp.factory.token_from_exchange[lp.name]
        x_tkn = tokens[lp.token0]
        y_tkn = tokens[lp.token1]

        reserve0 = lp.get_reserve(x_tkn)
        reserve1 = lp.get_reserve(y_tkn)

        if reserve0 <= 0 or reserve1 <= 0:
            raise ValueError(
                "EvaluateRebalance: pool reserves must be > 0; got "
                "reserve0={}, reserve1={}".format(reserve0, reserve1)
            )

        # Which side is "out" (target) vs "in" (to be swapped)?
        if token_out.token_name == lp.token0:
            reserve_out = reserve0
            reserve_in = reserve1
        else:
            reserve_out = reserve1
            reserve_in = reserve0

        # Current position value in token_out units (pre-swap spot).
        # Pro-rata share of both reserves, off-side valued at spot.
        share = position_size_lp / total_supply
        direct_out = share * reserve_out             # dy in the math notes
        direct_in = share * reserve_in               # dx in the math notes
        spot_price_pre = reserve_out / reserve_in    # out per in
        current_value = direct_out + direct_in * spot_price_pre

        # ─── Step 1: pro-rata withdrawal (pure math, no mutation) ──────
        # After withdrawal, reserves shrink proportionally and the
        # off-side tokens (direct_in) are now in the caller's hand
        # ready to be swapped.
        res_in_after_withdraw = reserve_in - direct_in
        res_out_after_withdraw = reserve_out - direct_out

        # ─── Step 2: swap direct_in → token_out against shrunken pool ──
        # V2 constant-product-with-fee formula.
        withdrawal_swap_amount_in = direct_in
        withdrawal_swap_amount_out = (
            _V2_F * withdrawal_swap_amount_in * res_out_after_withdraw
        ) / (
            res_in_after_withdraw + _V2_F * withdrawal_swap_amount_in
        )

        # Post-swap reserves for Step 3.
        res_in_after_swap = (
            res_in_after_withdraw + withdrawal_swap_amount_in
        )
        res_out_after_swap = (
            res_out_after_withdraw - withdrawal_swap_amount_out
        )

        # Slippage on the withdrawal swap. Spot-priced value of the
        # swap input (using post-withdrawal reserves to define spot)
        # minus actual output.
        spot_price_post_withdraw = (
            res_out_after_withdraw / res_in_after_withdraw
        )
        withdrawal_spot_value = (
            withdrawal_swap_amount_in * spot_price_post_withdraw
        )
        withdrawal_slippage_cost = (
            withdrawal_spot_value - withdrawal_swap_amount_out
        )
        withdrawal_slippage_pct = (
            withdrawal_slippage_cost / withdrawal_spot_value
            if withdrawal_spot_value > 0 else 0.0
        )

        # Total exit proceeds in token_out.
        withdrawal_total_out = direct_out + withdrawal_swap_amount_out

        # ─── Step 3: re-zap the proceeds back in ───────────────────────
        # Now token_out is the input to the zap; token_in is the output.
        # Use the V2 zap quadratic against post-swap reserves.
        # f*\u03b1\u00b2*dx_z + r_in_post*\u03b1*(1+f) - r_in_post = 0
        #   with r_in_post = res_out_after_swap (the input side of the
        #                    zap is the token_out reserve)
        #        dx_z      = withdrawal_total_out
        dx_z = withdrawal_total_out
        r_zap_in = res_out_after_swap

        # Quadratic: a*\u03b1\u00b2 + b*\u03b1 + c = 0
        a = _V2_F * dx_z
        b = r_zap_in * (1.0 + _V2_F)
        c = -r_zap_in
        discriminant = b * b - 4.0 * a * c
        # discriminant > 0 always for a, b > 0 and c < 0.
        alpha = (-b + math.sqrt(discriminant)) / (2.0 * a)

        # Redeposit swap leg: α * dx_z of token_out → token_in.
        redeposit_swap_amount_in = alpha * dx_z   # in token_out units
        redeposit_swap_amount_out = (
            _V2_F * redeposit_swap_amount_in * res_in_after_swap
        ) / (
            res_out_after_swap + _V2_F * redeposit_swap_amount_in
        )

        # Slippage on the redeposit swap. Spot before this swap is
        # the post-withdrawal-swap reserves (we haven't done the zap
        # yet at this measurement point).
        spot_price_pre_redeposit = (
            res_in_after_swap / res_out_after_swap
        )
        redeposit_spot_value = (
            redeposit_swap_amount_in * spot_price_pre_redeposit
        )
        redeposit_slippage_cost = (
            redeposit_spot_value - redeposit_swap_amount_out
        )
        redeposit_slippage_pct = (
            redeposit_slippage_cost / redeposit_spot_value
            if redeposit_spot_value > 0 else 0.0
        )

        # Post-redeposit-swap reserves (for the LP-mint calculation).
        res_zap_in_post = (
            res_out_after_swap + redeposit_swap_amount_in
        )
        res_zap_out_post = (
            res_in_after_swap - redeposit_swap_amount_out
        )

        # Deposit balances: (1-α)*dx_z of token_out and
        # redeposit_swap_amount_out of token_in.
        deposit_token_out = (1.0 - alpha) * dx_z
        deposit_token_in = redeposit_swap_amount_out

        # V2 mint formula: L_new = min(b_in·L'/r_in_post,
        #                              b_out·L'/r_out_post)
        # where L' is the total_supply after the withdrawal (shrunk
        # by position_size_lp; not further changed by swaps).
        total_supply_post_withdraw = total_supply - position_size_lp

        if token_out.token_name == lp.token0:
            # token_out is token0 (zap-in side), token_in is token1
            b0 = deposit_token_out
            b1 = deposit_token_in
            r0_post = res_zap_in_post
            r1_post = res_zap_out_post
        else:
            # token_out is token1, token_in is token0
            b0 = deposit_token_in
            b1 = deposit_token_out
            r0_post = res_zap_out_post
            r1_post = res_zap_in_post

        if r0_post <= 0 or r1_post <= 0 or total_supply_post_withdraw <= 0:
            raise ValueError(
                "EvaluateRebalance: redeposit would drain pool "
                "reserves. Likely position_size_lp is too close to "
                "total_supply for this cycle to be representable."
            )

        lp_from_side_0 = b0 * total_supply_post_withdraw / r0_post
        lp_from_side_1 = b1 * total_supply_post_withdraw / r1_post
        expected_lp_tokens_after = min(lp_from_side_0, lp_from_side_1)

        # ─── Totals in token_out units ──────────────────────────────────
        # Redeposit slippage is in token_in units; convert to token_out
        # via the post-withdrawal spot price.
        #
        # Units: redeposit_slippage_cost is denominated in token_in
        # (the output side of the redeposit swap). spot_price_post_withdraw
        # is (token_out / token_in). To rebase token_in → token_out we
        # MULTIPLY: token_in · (token_out / token_in) = token_out.
        # Dividing would give token_in² / token_out, which in exit-to-
        # token0 pools with spot << 1 produces explosively wrong totals.
        redeposit_slippage_in_out = (
            redeposit_slippage_cost * spot_price_post_withdraw
            if spot_price_post_withdraw > 0 else 0.0
        )
        total_slippage_cost = (
            withdrawal_slippage_cost + redeposit_slippage_in_out
        )
        total_slippage_pct = (
            total_slippage_cost / current_value
            if current_value > 0 else 0.0
        )

        lp_delta = expected_lp_tokens_after - position_size_lp

        return RebalanceCostReport(
            token_out_name = token_out.token_name,
            position_size_lp = position_size_lp,
            current_value = current_value,
            withdrawal_direct_out = direct_out,
            withdrawal_swap_amount_in = withdrawal_swap_amount_in,
            withdrawal_swap_amount_out = withdrawal_swap_amount_out,
            withdrawal_total_out = withdrawal_total_out,
            withdrawal_slippage_cost = withdrawal_slippage_cost,
            withdrawal_slippage_pct = withdrawal_slippage_pct,
            redeposit_swap_amount_in = redeposit_swap_amount_in,
            redeposit_swap_amount_out = redeposit_swap_amount_out,
            redeposit_slippage_cost = redeposit_slippage_cost,
            redeposit_slippage_pct = redeposit_slippage_pct,
            expected_lp_tokens_after = expected_lp_tokens_after,
            total_slippage_cost = total_slippage_cost,
            total_slippage_pct = total_slippage_pct,
            lp_delta = lp_delta,
        )
