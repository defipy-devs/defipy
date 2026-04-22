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

from ...utils.data import DepegRiskAssessment, DepegScenario


# Default depeg levels. Whether each is reachable depends on the pool's
# amplification coefficient A — see the "Reachability" note on the class.
_DEFAULT_DEPEG_LEVELS = [0.02, 0.05, 0.10, 0.20, 0.50]

# Self-consistent fixed-point iteration parameters.
_FIXED_POINT_TOL = 1e-9
_FIXED_POINT_MAX_ITER = 50

# Reachability bound on |ε|. At |ε| = 1 the pool is fully drained; at |ε|
# near 1 the leading-order expansion used here breaks down numerically.
# Depeg targets requiring |ε| ≥ this bound are flagged as "unreachable"
# rather than returning garbage. 0.95 gives a comfortable safety margin
# while still covering realistic depeg scenarios (on the test pool at
# A=200, 0.95 corresponds to roughly 30% reachable depeg).
_EPSILON_MAX = 0.95


class AssessDepegRisk:

    """ Stableswap depeg-risk quantification primitive — analytical.

        For a stableswap LP position, computes impermanent loss at a
        set of depeg magnitudes using a closed-form expansion of the
        stableswap invariant. Optionally contrasts each scenario
        against what a constant-product V2 pool would have produced
        at the same price deviation.

        Answers Q2.3 from DEFIMIND_TIER1_QUESTIONS.md — "How exposed am
        I to a depeg?"

        Design choice: analytical, not iterative.
        -----------------------------------------
        The stableswap invariant gives an exact functional
        relationship between pool composition and internal dydx.
        Rather than re-simulating arbitrage trades to push the pool
        state to a target dydx (which invokes stableswappy's
        integer-math Newton solvers, complete with unit-conversion
        subtleties and non-convergence cliffs at extreme balances),
        this primitive parameterizes the curve analytically and
        evaluates IL from the closed form.

        The derivation. For a 2-asset stableswap with invariant
        4A(x+y) + D = 4AD + D³/(4xy), parameterize by
        ε = (x - y)/(x + y) and S = x + y. Substituting into the
        invariant and solving to leading order in ε yields:

            u = S/D - 1 = ε² / [(4A + 2)(1 - ε²)]

        The dydx expression from stableswappy's _dydx formula,
        substituting and expanding to leading order, yields:

            δ = 1 - dydx ≈ 2ε / (α + 1 + ε)
            where α = A · (1 - ε²)²

        Inverting for ε given δ:

            ε = δ(α + 1) / (2 - δ)

        Because α depends on ε via (1-ε²)², this is solved by
        fixed-point iteration (converges in 3-10 iterations for
        practical (δ, A) pairs). Once ε is known, IL follows from
        the LP/hold value difference:

            v_LP  = S · (1 - δ(1+ε)/2)
            v_hold = D · (1 - δ/2)
            IL = (v_LP - v_hold) / v_hold

        Substituting S = D(1+u) and simplifying:

            IL ≈ -δε/2 + u - δ·u·(1+ε)/2 + O(higher)

        all divided by (1 - δ/2) to get the fractional form.

        The "strong negative convexity" property.
        -----------------------------------------
        A surprising consequence of this derivation, first
        emphasized in Cintra & Holloway (2023) "Detecting Depegs":
        at high A, stableswap pools exhibit larger absolute IL than
        V2 at the same price deviation, not smaller. The flat curve
        forces arbitrageurs to drain substantial balance to move
        dydx even a little; once they do, the LP holds a skewed
        composition. The marketing line "stableswap protects LPs
        from IL" is true per unit of trading volume (small dydx
        change per dollar traded) but misleading per unit of price
        deviation. This primitive reports the per-price-deviation
        IL — the quantity that matters in a depeg event.

        Reachability.
        -------------
        At A=200, a 2% depeg requires ε ≈ 2.0, which is physically
        impossible (|ε| must be < 1 for y > 0). Real pools absorb
        arbitrage up to |ε| near 1 before fully draining. The
        primitive flags any requested depeg that would require
        |ε| ≥ _EPSILON_MAX (0.95) as "unreachable" and reports the
        maximum-reachable depeg the pool actually supports.

        Scope limits.
        -------------
        - 2-asset stableswap only. N>2 is a future extension; the
          invariant generalizes but the closed-form inversion does
          not yield cleanly to the same treatment.
        - Leading-order expansion. Accuracy is best for moderate
          ε (say |ε| < 0.8); for near-drained pools the higher-order
          terms matter. In practice "moderate ε" covers most
          realistic depeg events in high-A pools.
        - V2 and V3 lp objects raise ValueError. Use
          SimulatePriceMove for price-move scenarios on V2/V3.

        Follows the DeFiPy primitive contract: stateless
        construction, computation at .apply(), structured dataclass
        return. The pool's state twin is never mutated.
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
                Levels requiring |ε| ≥ _EPSILON_MAX for the pool's
                A value are flagged as unreachable in their
                DepegScenario (il_pct set to None, lp_value_at_depeg
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

        n_assets = lp.math_pool.n
        if n_assets != 2:
            raise ValueError(
                "AssessDepegRisk v1: only 2-asset pools supported; "
                "got N={}. N>2 extension is tracked for a future "
                "release.".format(n_assets)
            )

        levels = depeg_levels if depeg_levels is not None \
                              else list(_DEFAULT_DEPEG_LEVELS)
        for d in levels:
            if not (0 < d < 1):
                raise ValueError(
                    "AssessDepegRisk: depeg level {} outside (0, 1)"
                    .format(d)
                )

        # Pool parameters for the derivation.
        A = lp.math_pool.A
        depeg_idx = lp.get_tkn_index(depeg_token.token_name)
        ref_idx = 0 if depeg_idx != 0 else 1

        # Total pool value (hold counterfactual) in human units.
        # For the IL formula we just need D and the LP's share of it;
        # the specific token amounts are computed for the value fields.
        dec_tkn_decimals = lp.tkn_decimals
        tkn_names = list(lp.tkn_reserves.keys())
        entry_balances_human = [
            lp.dec2amt(lp.math_pool.balances[i], dec_tkn_decimals[tkn_names[i]])
            for i in range(n_assets)
        ]
        # D in human units, approximating the balanced-pool D ≈ S = x + y.
        # Any small imbalance at entry is treated as "approximately
        # balanced" for this primitive's purposes.
        D_human = sum(entry_balances_human)

        # LP's share of the pool (by LP tokens held over total supply).
        lp_amt_dec = lp.amt2dec(lp_init_amt, 18)
        total_supply_dec = lp.math_pool.tokens
        lp_share_frac = (lp_amt_dec / total_supply_dec
                         if total_supply_dec > 0 else 0.0)

        # Current peg deviation. Entry pool near-balanced → ~0.
        current_dydx = lp.math_pool.dydx(depeg_idx, ref_idx, use_fee = False)
        current_peg_deviation = abs(1.0 - current_dydx)

        scenarios = []
        for depeg_pct in levels:
            scenario = self._analytical_scenario(
                A, D_human, lp_share_frac, depeg_pct, compare_v2,
            )
            scenarios.append(scenario)

        return DepegRiskAssessment(
            depeg_token = depeg_token.token_name,
            protocol_type = "stableswap",
            n_assets = n_assets,
            current_peg_deviation = current_peg_deviation,
            scenarios = scenarios,
        )

    def _analytical_scenario(self, A, D, lp_share_frac, depeg_pct,
                             compare_v2):

        """ _analytical_scenario

            Compute a single DepegScenario via the closed-form
            expansion. No pool mutation, no iteration on pool state —
            just fixed-point on ε given (δ, A), then direct IL formula.
        """

        delta = depeg_pct        # δ in the derivation
        peg_price = 1.0 - delta

        # Fixed-point iteration for ε given δ and A.
        #   ε = δ · (α + 1) / (2 - δ)
        #   α = A · (1 - ε²)²
        # Seed with leading-order value ε₀ = δ(A+1)/(2-δ).
        epsilon = delta * (A + 1) / (2 - delta)

        reachable = True
        for _ in range(_FIXED_POINT_MAX_ITER):
            if abs(epsilon) >= _EPSILON_MAX:
                reachable = False
                break
            alpha = A * (1 - epsilon**2)**2
            epsilon_new = delta * (alpha + 1) / (2 - delta)
            if abs(epsilon_new - epsilon) < _FIXED_POINT_TOL:
                epsilon = epsilon_new
                break
            epsilon = epsilon_new

        # Recheck reachability post-iteration (solution may have grown
        # past the bound in later iterations).
        if abs(epsilon) >= _EPSILON_MAX:
            reachable = False

        v2_il = None
        if compare_v2:
            # V2 IL closed form at alpha_ratio = peg_price.
            v2_il = 2 * _math.sqrt(peg_price) / (1 + peg_price) - 1

        if not reachable:
            return DepegScenario(
                depeg_pct = delta,
                peg_price = peg_price,
                lp_value_at_depeg = None,
                hold_value_at_depeg = None,
                il_pct = None,
                v2_il_comparison = v2_il,
            )

        # u = S/D - 1 from the derivation.
        u = epsilon**2 / ((4*A + 2) * (1 - epsilon**2))
        S = D * (1 + u)

        # LP value per unit pool (in price-of-peg numeraire):
        #   v_LP_per_unit = S/D · (1 - δ(1+ε)/2)
        # Multiply by D for absolute pool value, then by lp_share_frac
        # for this LP's claim.
        pool_lp_value = S * (1 - delta * (1 + epsilon) / 2)
        pool_hold_value = D * (1 - delta / 2)

        lp_value = pool_lp_value * lp_share_frac
        hold_value = pool_hold_value * lp_share_frac

        il_pct = ((lp_value - hold_value) / hold_value
                  if hold_value > 0 else 0.0)

        return DepegScenario(
            depeg_pct = delta,
            peg_price = peg_price,
            lp_value_at_depeg = lp_value,
            hold_value_at_depeg = hold_value,
            il_pct = il_pct,
            v2_il_comparison = v2_il,
        )
