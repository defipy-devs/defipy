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

import math as _math

from stableswappy.cst.exchg import StableswapExchange
from stableswappy.analytics.risk import (
    StableswapImpLoss, DepegUnreachableError,
)

from ...utils.data import DepegRiskAssessment, DepegScenario


# Default depeg levels. Whether each is reachable depends on the pool's
# amplification coefficient A — see the "Reachability" note on the class.
_DEFAULT_DEPEG_LEVELS = [0.02, 0.05, 0.10, 0.20, 0.50]


class AssessDepegRisk:

    """ Stableswap depeg-risk quantification primitive — analytical.

        For a stableswap LP position, computes impermanent loss at a
        set of depeg magnitudes using the closed-form expansion of the
        stableswap invariant (now lifted into
        stableswappy.analytics.risk.StableswapImpLoss). Optionally
        contrasts each scenario against what a constant-product V2 pool
        would have produced at the same price deviation.

        Answers Q2.3 from DEFIMIND_TIER1_QUESTIONS.md — "How exposed am
        I to a depeg?"

        Composition over duplication.
        -----------------------------
        In earlier versions of this primitive the IL math was inlined
        here. As of the 1.2.0 work the closed-form machinery lives in
        its natural home at stableswappy.analytics.risk.StableswapImpLoss,
        symmetric with BalancerImpLoss and UniswapImpLoss. This
        primitive now composes that helper rather than duplicating the
        derivation, following the same pattern AnalyzePosition uses
        with UniswapImpLoss.

        Scope, reachability, and the strong-negative-convexity property
        are all documented on StableswapImpLoss itself; refer there
        for the mathematical details. This class focuses on:
          - the multi-level scenario surface (default 5 depeg levels,
            overridable)
          - V2 comparison as a side-by-side benchmark
          - absolute LP/hold values (scaled to the caller's share of
            the pool) alongside the IL fraction
          - unreachable-scenario handling: None-sentinels on the
            scenario's value/IL fields when StableswapImpLoss raises
            DepegUnreachableError

        Scope limits.
        -------------
        - 2-asset stableswap only (inherited from StableswapImpLoss).
        - V2 and V3 lp objects raise ValueError. Use SimulatePriceMove
          for price-move scenarios on V2/V3.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return. The
        pool's state twin is never mutated.
    """

    def __init__(self):
        pass

    def apply(self, lp, lp_init_amt, depeg_token,
              depeg_levels = None, compare_v2 = True):

        """ apply

            Compute depeg-risk scenarios for a stableswap LP position.

            Parameters
            ----------
            lp : StableswapExchange
                Stableswap LP. Must be 2-asset (N=2). Raises
                ValueError if not a StableswapExchange or if N>2.
            lp_init_amt : float
                LP tokens held, in human units. Must be > 0.
            depeg_token : ERC20
                The asset assumed to depeg. Must be in the pool's
                vault.
            depeg_levels : list[float], optional
                Depeg magnitudes as fractions. Defaults to
                [0.02, 0.05, 0.10, 0.20, 0.50]. Each entry in (0, 1).
                Levels requiring |ε| ≥ the StableswapImpLoss bound
                for the pool's A value are flagged as unreachable in
                their DepegScenario (il_pct = None, lp_value_at_depeg
                and hold_value_at_depeg also None).
            compare_v2 : bool, optional
                If True (default), each scenario reports the
                equivalent V2 constant-product IL at the same price
                deviation.

            Returns
            -------
            DepegRiskAssessment
        """

        if not isinstance(lp, StableswapExchange):
            raise ValueError(
                "AssessDepegRisk: lp must be a StableswapExchange; "
                "got {}. For V2/V3 price-move scenarios, use "
                "SimulatePriceMove.".format(type(lp).__name__)
            )

        if lp_init_amt <= 0:
            raise ValueError(
                "AssessDepegRisk: lp_init_amt must be > 0; got {}"
                .format(lp_init_amt)
            )

        vault_tokens = lp.vault.get_names()
        if depeg_token.token_name not in vault_tokens:
            raise ValueError(
                "AssessDepegRisk: depeg_token {!r} not in pool "
                "(vault holds {})"
                .format(depeg_token.token_name, vault_tokens)
            )

        levels = depeg_levels if depeg_levels is not None \
                              else list(_DEFAULT_DEPEG_LEVELS)
        for d in levels:
            if not (0 < d < 1):
                raise ValueError(
                    "AssessDepegRisk: depeg level {} outside (0, 1)"
                    .format(d)
                )

        # Construct the IL helper once. Constructor validates N=2 and
        # raises on bad lp state; we let that error propagate unchanged
        # so callers see the same ValueError shape they used to.
        il = StableswapImpLoss(lp, lp_init_amt)

        # Current peg deviation from live dydx. Near-balanced pool → ~0.
        depeg_idx = lp.get_tkn_index(depeg_token.token_name)
        ref_idx = 0 if depeg_idx != 0 else 1
        current_dydx = lp.math_pool.dydx(depeg_idx, ref_idx, use_fee = False)
        current_peg_deviation = abs(1.0 - current_dydx)

        scenarios = [
            self._build_scenario(il, depeg_pct, compare_v2)
            for depeg_pct in levels
        ]

        return DepegRiskAssessment(
            depeg_token = depeg_token.token_name,
            protocol_type = "stableswap",
            n_assets = il.n_assets,
            current_peg_deviation = current_peg_deviation,
            scenarios = scenarios,
        )

    def _build_scenario(self, il, depeg_pct, compare_v2):

        """ _build_scenario

            Turn one (il_helper, depeg_pct) pair into a DepegScenario.

            Delegates the IL math to StableswapImpLoss; catches
            DepegUnreachableError to surface as None-sentinel fields
            on the scenario (preserving the pre-refactor API where
            unreachable levels produce a scenario with il_pct=None
            rather than raising).

            Parameters
            ----------
            il : StableswapImpLoss
                Pre-constructed helper bound to the pool and LP share.
            depeg_pct : float
                Depeg magnitude δ in (0, 1).
            compare_v2 : bool
                Whether to populate v2_il_comparison.

            Returns
            -------
            DepegScenario
        """

        delta = depeg_pct
        peg_price = 1.0 - delta

        # V2 comparison: closed form at alpha = peg_price. Always
        # computable regardless of stableswap reachability — that's
        # the point of surfacing it alongside.
        v2_il = None
        if compare_v2:
            v2_il = 2 * _math.sqrt(peg_price) / (1 + peg_price) - 1

        # Stableswap IL via the helper. alpha = 1 - delta.
        try:
            il_pct = il.calc_iloss(peg_price)
        except DepegUnreachableError:
            return DepegScenario(
                depeg_pct = delta,
                peg_price = peg_price,
                lp_value_at_depeg = None,
                hold_value_at_depeg = None,
                il_pct = None,
                v2_il_comparison = v2_il,
            )

        # Absolute LP / hold values for this caller's share.
        #
        # StableswapImpLoss.calc_iloss returns IL as a ratio:
        #   il_pct = (v_LP - v_hold) / v_hold
        # We need the dollar values. At the pool level, v_hold per unit
        # of D is (1 - δ/2). The caller's share of D is captured in
        # il.D · il.lp_share_frac. Then v_LP follows from the ratio:
        #   v_LP = v_hold · (1 + il_pct)
        hold_value = il.D * il.lp_share_frac * (1 - delta / 2)
        lp_value = hold_value * (1 + il_pct)

        return DepegScenario(
            depeg_pct = delta,
            peg_price = peg_price,
            lp_value_at_depeg = lp_value,
            hold_value_at_depeg = hold_value,
            il_pct = il_pct,
            v2_il_comparison = v2_il,
        )
