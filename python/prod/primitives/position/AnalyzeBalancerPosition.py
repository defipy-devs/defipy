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

from balancerpy.cwpt.exchg import BalancerExchange
from balancerpy.analytics.risk import BalancerImpLoss

from ...utils.data import BalancerPositionAnalysis


class AnalyzeBalancerPosition:

    """ Decompose a 2-asset Balancer LP position into IL, fees, net PnL.

        Sibling to AnalyzePosition (V2/V3). Same answer shape — IL
        decomposition from price divergence — but adapted to
        Balancer's weighted AMM where the IL formula depends on the
        base token's weight, not just the price ratio.

        Answers the core diagnostic questions for any Balancer LP
        position:
          - Why is this position losing (or making) money?
          - How does the weighting affect my IL?
          - What's the real APR including IL?

        Composition over duplication. The IL math lives in
        balancerpy.analytics.risk.BalancerImpLoss (lifted there
        during the 1.2.0 work, symmetric with UniswapImpLoss and
        StableswapImpLoss). This primitive composes it — no new
        math here, just the same primitive contract wrapping around
        the sibling-repo helper.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Scope limits
        ------------
        - 2-asset pools only. Inherited from BalancerImpLoss's own
          2-asset scope. N-asset extension requires first extending
          BalancerImpLoss; noted in its own docstring.
        - No fee income attribution. Balancer's collected_fees is
          vault-level with no per-LP attribution inside the pool
          object — surfacing a derived fee number would fabricate
          precision the state doesn't carry. fee_income is always
          0.0 in v1.
        - diagnosis enum has only two values in v1
          ("net_positive" / "il_dominant"). When fee attribution
          lands, "fee_compensated" will be added to match
          AnalyzePosition's V2/V3 shape.

        Numeraire convention
        --------------------
        All values are denominated in opp-token units (the second
        token in the pool's insertion order), matching
        BalancerImpLoss's convention. This differs from
        AnalyzePosition's token0 numeraire; callers aggregating
        across protocols in a common token need to rebase
        manually. AggregatePortfolio handles this by requiring a
        shared first-token symbol across positions.

        alpha convention
        ----------------
        alpha = current_price / entry_price, where price is
        opp-per-base (units of opp token per unit of base token).
        Computed fee-free — we go direct to reserves rather than
        through lp.get_price() which bakes in a fee scale factor
        (matches BalancerImpLoss's internal approach, documented
        there).

        Input shape — entry amounts, not alpha
        --------------------------------------
        The public surface takes `entry_base_amt, entry_opp_amt`
        for the user's natural framing ("what did I deposit?"),
        and derives alpha internally. Callers who want to explore
        hypothetical alphas should compose with CompareProtocols
        (symmetric ±shock against this pool) or call
        BalancerImpLoss.calc_iloss directly.
    """

    def __init__(self):
        pass

    def apply(self, lp, lp_init_amt, entry_base_amt, entry_opp_amt,
              holding_period_days = None):

        """ apply

            Compute full position decomposition.

            Parameters
            ----------
            lp : BalancerExchange
                2-asset weighted pool. N>2 raises ValueError (via
                BalancerImpLoss). V2/V3/Stableswap pools raise
                ValueError directly.
            lp_init_amt : float
                Pool shares held by this position, in human units.
                Must be > 0.
            entry_base_amt : float
                Amount of base (first) token originally deposited.
                Must be > 0. Base is defined as the first token in
                the pool's tkn_reserves insertion order, matching
                BalancerImpLoss.
            entry_opp_amt : float
                Amount of opp (second) token originally deposited.
                Must be > 0.
            holding_period_days : float, optional
                Days the position has been held. When provided,
                real_apr is annualized from net_pnl. Otherwise
                real_apr is None.

            Returns
            -------
            BalancerPositionAnalysis

            Raises
            ------
            ValueError
                If lp is not a BalancerExchange, lp_init_amt <= 0,
                entry amounts <= 0, or pool is not 2-asset
                (propagated from BalancerImpLoss).
        """

        if not isinstance(lp, BalancerExchange):
            raise ValueError(
                "AnalyzeBalancerPosition: lp must be a BalancerExchange; "
                "got {}. For V2/V3 pools use AnalyzePosition; for "
                "stableswap use AnalyzeStableswapPosition.".format(
                    type(lp).__name__
                )
            )

        if entry_base_amt <= 0:
            raise ValueError(
                "AnalyzeBalancerPosition: entry_base_amt must be > 0; "
                "got {}".format(entry_base_amt)
            )
        if entry_opp_amt <= 0:
            raise ValueError(
                "AnalyzeBalancerPosition: entry_opp_amt must be > 0; "
                "got {}".format(entry_opp_amt)
            )

        # Construct the IL helper. BalancerImpLoss's constructor
        # validates lp_init_amt > 0 and 2-asset-only; let those
        # errors propagate unchanged so callers see the same
        # ValueError shape from both primitives.
        il = BalancerImpLoss(lp, lp_init_amt)

        base_tkn_name = il.base_tkn_name
        opp_tkn_name = il.opp_tkn_name
        w_base = il.base_weight

        # Fee-free spot price, opp-per-base, from raw reserves/weights.
        # Same computation BalancerImpLoss.apply() uses internally;
        # we inline it here because we need the value for both alpha
        # and hold_value, and calling .apply() would re-read reserves
        # a second time.
        b_base = lp.tkn_reserves[base_tkn_name]
        b_opp = lp.tkn_reserves[opp_tkn_name]
        w_opp = lp.tkn_weights[opp_tkn_name]
        current_spot = (b_opp / w_opp) / (b_base / w_base)

        # Implied entry price from caller's deposit composition.
        # Balancer deposits preserve the pool's weight-adjusted ratio
        # (otherwise the zap swaps to rebalance first), so at entry
        # spot_entry ≈ (opp_amt / w_opp) / (base_amt / w_base).
        # Using the fee-free form to match current_spot and the IL
        # helper's convention.
        entry_spot = (entry_opp_amt / w_opp) / (entry_base_amt / w_base)

        alpha = current_spot / entry_spot

        # IL from the closed form. Passes the base weight explicitly
        # so the override path is exercised (matches construction's
        # default but makes the semantic explicit).
        il_raw = il.calc_iloss(alpha, weight = w_base)

        # Hold value: entry composition priced at current fee-free
        # spot, denominated in opp units.
        hold_value = entry_base_amt * current_spot + entry_opp_amt

        # Current position value: pool share's current composition,
        # also in opp units. BalancerImpLoss captures the per-token
        # share at construction time — that's what the position
        # actually owns right now. Pricing current-base at
        # current-spot gives current value in opp units.
        current_value = (
            il.base_tkn_init * current_spot + il.opp_tkn_init
        )

        net_pnl = current_value - hold_value

        # In v1 fee_income is always 0 and il_with_fees == il_raw.
        # When fee attribution lands, il_with_fees becomes
        # net_pnl / hold_value (matching AnalyzePosition).
        fee_income = 0.0
        il_with_fees = il_raw

        if holding_period_days is not None and holding_period_days > 0:
            real_apr = (net_pnl / hold_value) * (365.0 / holding_period_days)
        else:
            real_apr = None

        diagnosis = self._diagnose(net_pnl)

        return BalancerPositionAnalysis(
            base_tkn_name = base_tkn_name,
            opp_tkn_name = opp_tkn_name,
            base_weight = w_base,
            current_value = current_value,
            hold_value = hold_value,
            il_percentage = il_raw,
            il_with_fees = il_with_fees,
            fee_income = fee_income,
            net_pnl = net_pnl,
            real_apr = real_apr,
            diagnosis = diagnosis,
            alpha = alpha,
        )

    def _diagnose(self, net_pnl):

        """ _diagnose

            Two-bucket diagnosis — matches v1 scope of no fee income
            attribution. Expands to match AnalyzePosition's three
            buckets when fees become attributable.
        """

        if net_pnl > 0:
            return "net_positive"
        return "il_dominant"
