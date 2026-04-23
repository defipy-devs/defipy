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
class DepositSplitResult:
    """ Structured result of OptimalDepositSplit primitive.

        Non-mutating projection of what a SwapDeposit / zap-in would do
        against the current pool state. Describes the optimal swap
        fraction, the resulting balances to deposit, the projected LP
        tokens minted, and the execution friction incurred by the swap
        leg of the zap.

        Attributes
        ----------
        token_in_name : str
            Symbol of the input token (echoed from input for traceability).
        amount_in : float
            Total input amount, in human units.
        optimal_fraction : float
            α — the fraction of amount_in to swap before depositing.
            Always in (0, 1). Starts at 1/(1+f) ≈ 0.50075 in the limit
            of zero deposit (where f = 0.997 is the V2 fee multiplier)
            and decreases monotonically as the deposit grows relative
            to reserves. The 30-bps fee is what puts the limiting
            value slightly above 0.5; the decrease with size comes
            from the swap's own price impact — a larger swap buys
            less per unit swapped, so you need to swap less.
        swap_amount_in : float
            α · amount_in of token_in to swap. In human units.
        swap_amount_out : float
            Token_out received from the swap (at the 30-bps V2 fee).
            In human units.
        deposit_amount_in : float
            (1-α) · amount_in of token_in to deposit alongside the swap
            output. In human units.
        deposit_amount_out : float
            Equals swap_amount_out — echoed here for clarity at the
            deposit step.
        expected_lp_tokens : float
            LP tokens minted, computed as:
              min(b_in · L / res_in, b_out · L / res_out)
            after the swap, using post-swap reserves. V2's
            add_liquidity uses the min to prevent dilution attacks;
            at the optimal split the two ratios match to within
            integer-math rounding, so either branch of the min wins.
            In human units.
        slippage_cost : float
            Value lost to the swap's curve-walking, expressed in
            token_out units. Equals (α · amount_in · p_spot) -
            swap_amount_out, where p_spot is the pre-swap spot price
            of token_in in token_out. Always >= 0 by construction.
        slippage_pct : float
            slippage_cost / (α · amount_in · p_spot). Fraction of the
            swap leg's spot-priced value that was lost to slippage.
            In [0, 1].
    """
    token_in_name: str
    amount_in: float
    optimal_fraction: float
    swap_amount_in: float
    swap_amount_out: float
    deposit_amount_in: float
    deposit_amount_out: float
    expected_lp_tokens: float
    slippage_cost: float
    slippage_pct: float
