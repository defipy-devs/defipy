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
class RebalanceCostReport:
    """ Structured result of EvaluateRebalance primitive.

        Non-mutating projection of the cost of cycling a V2 position:
        withdraw the full position proportionally, swap the off-side
        tokens to the target token, then re-deposit all proceeds via
        an optimal zap. All values in token_out units.

        This primitive reports COST, not a verdict. Whether the cost
        is worth paying depends on the caller's forward-looking
        assumptions about improved fee capture, price movement, or
        other benefits that the pool object cannot supply.
        Consistent with the signal-surfacer convention.

        Attributes
        ----------
        token_out_name : str
            Symbol of the desired exit token (echoed from input).
        position_size_lp : float
            LP tokens in the current position being cycled (echoed).
        current_value : float
            Current position value in token_out units. Sum of the
            pro-rata withdrawn amounts, with the off-side valued
            at pre-swap spot price.
        withdrawal_direct_out : float
            token_out proceeds from the pro-rata withdrawal on the
            target-token side. No swap involved; this is just your
            share of reserve_out.
        withdrawal_swap_amount_in : float
            token_in proceeds from the pro-rata withdrawal (the
            off-side share) that need to be swapped.
        withdrawal_swap_amount_out : float
            token_out proceeds from swapping withdrawal_swap_amount_in
            through the pool (after the pro-rata withdrawal has
            shrunk reserves).
        withdrawal_total_out : float
            Sum: withdrawal_direct_out + withdrawal_swap_amount_out.
            This is what you have in hand after the withdraw leg.
        withdrawal_slippage_cost : float
            Value lost in the withdrawal swap vs. spot. In token_out
            units. Equals (withdrawal_swap_amount_in · spot_price)
            minus withdrawal_swap_amount_out, where spot_price is
            measured AFTER the pro-rata withdrawal.
        withdrawal_slippage_pct : float
            withdrawal_slippage_cost / (withdrawal_swap_amount_in
            · spot_price_after_withdraw). Fraction lost in the
            withdrawal swap leg.
        redeposit_swap_amount_in : float
            token_out amount swapped in the re-zap (α · total_out).
        redeposit_swap_amount_out : float
            token_in received from the re-zap swap leg.
        redeposit_slippage_cost : float
            Value lost in the re-deposit swap, expressed in token_in
            units (the swap output direction). Matches
            OptimalDepositSplit's slippage denomination convention.
        redeposit_slippage_pct : float
            Fraction lost in the re-deposit swap.
        expected_lp_tokens_after : float
            LP tokens the caller holds after the full cycle, computed
            from the re-zap's expected mint against post-redeposit
            reserves.
        total_slippage_cost : float
            Sum of both slippage costs, normalized to token_out units
            for comparison with current_value. The redeposit slippage
            (originally in token_in units) is converted via the
            post-withdraw spot price.
        total_slippage_pct : float
            total_slippage_cost / current_value. Fraction of position
            value lost to the cycle. Useful gross signal: if this is
            0.5%, cycling the position costs 50 bps in slippage alone.
        lp_delta : float
            expected_lp_tokens_after - position_size_lp. Always
            negative in practice (two fees plus two slippage legs).
            Tells the caller "how many LP tokens does this cycle
            destroy."
    """
    token_out_name: str
    position_size_lp: float
    current_value: float
    withdrawal_direct_out: float
    withdrawal_swap_amount_in: float
    withdrawal_swap_amount_out: float
    withdrawal_total_out: float
    withdrawal_slippage_cost: float
    withdrawal_slippage_pct: float
    redeposit_swap_amount_in: float
    redeposit_swap_amount_out: float
    redeposit_slippage_cost: float
    redeposit_slippage_pct: float
    expected_lp_tokens_after: float
    total_slippage_cost: float
    total_slippage_pct: float
    lp_delta: float
