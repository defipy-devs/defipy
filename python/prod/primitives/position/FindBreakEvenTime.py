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

from .AnalyzePosition import AnalyzePosition

from ...utils.data import BreakEvenTime


# Ethereum mainnet default: 86400 seconds/day ÷ 12 seconds/block = 7200.
# L2 callers override via the constructor (e.g., Base at 2s/block → 43200).
_DEFAULT_BLOCKS_PER_DAY = 7200


class FindBreakEvenTime:

    """ Estimate how long until accumulated fees compensate current IL drag.

        Answers Q5.3 from DEFIMIND_TIER1_QUESTIONS.md.

        Runs AnalyzePosition internally to obtain the position's observed
        IL and fee income, derives the per-day fee-accrual rate from the
        caller's stated holding_period_days, and projects that rate
        forward linearly to report when cumulative fees would equal the
        raw IL drag.

        Follows the DeFiPy primitive contract: stateless construction
        (modulo the blocks_per_day chain parameter), computation at
        .apply(), structured dataclass return.

        Non-mutating. Reads pool state via AnalyzePosition; no writes.

        Notes
        -----
        Linear projection of observed rate. The primitive projects the
        fee-accrual rate this position has actually been earning —
        AnalyzePosition.fee_income divided by holding_period_days —
        forward without modeling future volume. This is deliberately
        an honest baseline, not a forecast. Callers stress-testing
        under different assumptions can either (a) re-run the primitive
        at different holding_period_days to see how sensitive the
        answer is, or (b) compose this primitive with their own
        volume model externally.

        Why the position's own rate, not a pool-level average. The
        question the user is asking is "when does MY position pay
        off?", not "when would the average LP pay off?" The
        position's realized fee_income already accounts for pool
        share, tick range (V3), and time-in-range. Pool-level
        CheckPoolHealth.total_fee* values would require further
        attribution to this position, which loses the precision that
        AnalyzePosition already provides.

        Diagnosis-driven return semantics. The primitive produces one
        of four diagnoses, each with consistent field values:

          already_broken_even — net_pnl >= 0 at current state.
              days/blocks set to 0. No further time is required; the
              question is moot.

          no_il_drag — il_raw >= 0 (price hasn't diverged enough to
              produce IL, or has moved favorably). days/blocks set
              to 0. Trivially broken even on the IL-recovery question.

          no_fee_income — fee_rate_per_day <= 0. Without a positive
              accrual rate there is no finite break-even time.
              days/blocks set to None to force callers to handle the
              "unprojectable" case explicitly rather than default to
              a sentinel.

          projected — finite days_to_break_even computed. Blocks
              derived as round(days * blocks_per_day) using the
              constructor's chain parameter.

        Blocks as integers. Break-even is a whole-block event, so
        blocks_to_break_even is rounded to int. Callers who want
        sub-block precision can divide days_to_break_even by their
        own per-block seconds.

        Default chain assumption. The constructor defaults to
        7200 blocks/day (Ethereum mainnet, 12s/block). L2 and
        non-Ethereum chains require passing the appropriate value —
        this is intentionally not auto-detected because lp objects
        in this codebase don't carry chain identity.
    """

    def __init__(self, blocks_per_day = _DEFAULT_BLOCKS_PER_DAY):

        """ __init__

            Parameters
            ----------
            blocks_per_day : int or float, optional
                Average blocks produced per day on the target chain.
                Default 7200 (Ethereum mainnet at 12s/block). Override
                for L2s: Base at 2s/block → 43200; Arbitrum at ~0.25s
                → ~345600. Must be > 0.

            Raises
            ------
            ValueError
                If blocks_per_day <= 0.
        """

        if blocks_per_day <= 0:
            raise ValueError(
                "FindBreakEvenTime: blocks_per_day must be > 0; "
                "got {}".format(blocks_per_day)
            )

        self.blocks_per_day = blocks_per_day

    def apply(self, lp, lp_init_amt, entry_x_amt, entry_y_amt,
              holding_period_days,
              lwr_tick = None, upr_tick = None):

        """ apply

            Compute the break-even time for an LP position.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current pool state.
            lp_init_amt : float
                LP tokens held by the position, in human units.
            entry_x_amt : float
                Amount of token0 originally deposited at entry, human
                units.
            entry_y_amt : float
                Amount of token1 originally deposited at entry, human
                units.
            holding_period_days : float
                Days the position has been held. Required (not
                defaulted) because without it the fee-accrual rate
                cannot be derived from realized fee income. Must be
                > 0. If the caller doesn't know the holding period,
                the break-even time is not computable.
            lwr_tick : int, optional
                Lower tick of the position (V3 positions only).
            upr_tick : int, optional
                Upper tick of the position (V3 positions only).

            Returns
            -------
            BreakEvenTime

            Raises
            ------
            ValueError
                If holding_period_days is None or <= 0.
        """

        if holding_period_days is None or holding_period_days <= 0:
            raise ValueError(
                "FindBreakEvenTime: holding_period_days must be > 0; "
                "got {!r}. Without a holding period the fee-accrual "
                "rate cannot be derived from realized fees.".format(
                    holding_period_days
                )
            )

        # Single call to AnalyzePosition gets us everything we need:
        # net_pnl, il_percentage (= il_raw), hold_value, fee_income.
        analysis = AnalyzePosition().apply(
            lp, lp_init_amt, entry_x_amt, entry_y_amt,
            lwr_tick = lwr_tick,
            upr_tick = upr_tick,
            holding_period_days = holding_period_days,
        )

        # IL drag in numeraire units. il_percentage <= 0 under price
        # divergence; treat >= 0 as "no drag to recover from".
        if analysis.il_percentage < 0:
            current_il_drag = -analysis.il_percentage * analysis.hold_value
        else:
            current_il_drag = 0.0

        fee_income_to_date = analysis.fee_income
        fee_rate_per_day = fee_income_to_date / holding_period_days

        already_broken_even = analysis.net_pnl >= 0

        # ─── Branch on diagnosis ────────────────────────────────────────
        if already_broken_even:
            # Position is net positive; no time required.
            return BreakEvenTime(
                current_il_drag = current_il_drag,
                fee_income_to_date = fee_income_to_date,
                fee_rate_per_day = fee_rate_per_day,
                days_to_break_even = 0.0,
                blocks_to_break_even = 0,
                already_broken_even = True,
                diagnosis = "already_broken_even",
            )

        if current_il_drag <= 0:
            # No IL to recover from. Trivially "broken even" on the
            # IL-recovery axis, even if net_pnl isn't strictly positive.
            return BreakEvenTime(
                current_il_drag = current_il_drag,
                fee_income_to_date = fee_income_to_date,
                fee_rate_per_day = fee_rate_per_day,
                days_to_break_even = 0.0,
                blocks_to_break_even = 0,
                already_broken_even = False,
                diagnosis = "no_il_drag",
            )

        if fee_rate_per_day <= 0:
            # Can't project recovery without a positive rate.
            return BreakEvenTime(
                current_il_drag = current_il_drag,
                fee_income_to_date = fee_income_to_date,
                fee_rate_per_day = fee_rate_per_day,
                days_to_break_even = None,
                blocks_to_break_even = None,
                already_broken_even = False,
                diagnosis = "no_fee_income",
            )

        # ─── Projected path ────────────────────────────────────────────
        days_to_break_even = current_il_drag / fee_rate_per_day
        blocks_to_break_even = int(round(
            days_to_break_even * self.blocks_per_day
        ))

        return BreakEvenTime(
            current_il_drag = current_il_drag,
            fee_income_to_date = fee_income_to_date,
            fee_rate_per_day = fee_rate_per_day,
            days_to_break_even = days_to_break_even,
            blocks_to_break_even = blocks_to_break_even,
            already_broken_even = False,
            diagnosis = "projected",
        )
