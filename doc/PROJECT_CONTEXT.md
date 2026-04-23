# DeFiPy: Professional-Grade DeFi Analytics & Primitives

## Overview

DeFiPy is a Python SDK for DeFi analytics, simulation, and autonomous agents. Built from mathematical first principles with hand-derived AMM formulas. Current version: **1.2.0** (on PyPI; working branch continues).

As of 1.2.0, the go-forward architecture centers on composable **primitives** — stateless objects that answer specific LP questions and return structured dataclass results. Primitives are designed to be callable directly by quants in notebooks or by an LLM reasoning layer (DeFiMind) as tools.

## Architecture Highlights

### Mathematical Foundation
- **Hand-derived inverse relationships**: `RebaseIndexToken` ↔ `SettlementLPToken`
- **Exact V2/V3 calculations**: No approximations, includes fee integration
- **Concentrated liquidity math**: Full V3 tick / sqrt-price implementations (TickMath ported from the on-chain contract)
- **Financial-grade precision**: SaferMath, FullMath for accurate calculations
- **Closed-form stableswap IL expansion**: `AssessDepegRisk` derives IL analytically from the stableswap invariant (parameterize by ε, fixed-point solve for given δ, direct IL formula), skipping stableswappy's integer-math state solvers entirely.
- **Invariant-vs-contract consistency checks**: `DetectFeeAnomaly` validates that a V2 pool's actual swap output matches what the constant-product invariant predicts at the stated fee — a second invariant-math primitive that treats the protocol library as a metadata adapter, not a math engine.

### Multi-Protocol Support
- **uniswappy**: Uniswap V2 / V3 implementations
- **balancerpy**: Balancer weighted pools
- **stableswappy**: Curve-style stableswap math
- **web3scout** (optional, via `[book]` extra): onchain event monitoring for agents

### Primitives Layer (current focus)

Each primitive follows the DeFiPy contract: stateless construction, computation at `.apply()`, structured dataclass return.

**Twenty primitives shipped as of the 1.2.0 working branch** — 17 from the original Tier 1 spec, plus 3 cross-protocol position analyzers (sibling primitives to AnalyzePosition for Balancer and Stableswap). AggregatePortfolio has been upgraded to cross-protocol dispatch.

| Primitive | Category | Answers | Tests |
|---|---|---|---|
| `AnalyzePosition` | position/ | Q1.1–Q1.4 (V2/V3 PnL decomposition) | 17 |
| `AnalyzeBalancerPosition` | position/ | Q1.1–Q1.4 on Balancer weighted pools, 2-asset | 22 |
| `AnalyzeStableswapPosition` | position/ | Q1.1–Q1.4 on Stableswap, 2-asset, with unreachable-alpha handling | 21 |
| `SimulatePriceMove` | position/ | Q2.1, Q5.1, Q5.2 (V2/V3 price-move scenarios) | 21 |
| `CalculateSlippage` | execution/ | Q8.1, Q8.2, Q9.2 (V2/V3 trade slippage + max-size) | 20 |
| `DetectMEV` | execution/ | Q8.5 (theoretical-vs-actual output comparison) | 20 |
| `CheckTickRangeStatus` | risk/ | Q2.4 (V3 range proximity) | 16 |
| `EvaluateTickRanges` | optimization/ | Q3.1, Q3.2 (V3 tick-range evaluation + split) | 21 |
| `EvaluateRebalance` | optimization/ | Q3.4, Q8.4 (rebalance cost-vs-benefit, V2) | 20 |
| `FindBreakEvenPrice` | position/ | Q2.2 (V2/V3 break-even pricing, both alphas) | 23 |
| `FindBreakEvenTime` | position/ | Q5.3 (V2/V3 blocks/days to fee-IL breakeven) | 20 |
| `CheckPoolHealth` | pool_health/ | Q7.1, Q7.2, Q7.5 (pool-level health snapshot) | 24 |
| `DetectRugSignals` | pool_health/ | Q7.4 (threshold-based rug signals) | 23 |
| `AssessDepegRisk` | risk/ | Q2.3 (stableswap depeg scenarios, N=2) | 22 |
| `DetectFeeAnomaly` | pool_health/ | Q7.3 (invariant-vs-contract fee consistency, V2) | 20 |
| `CompareFeeTiers` | comparison/ | Q4.3 (V3 fee-tier comparison, N candidates) | 21 |
| `CompareProtocols` | comparison/ | Q4.1, Q8.3 (same capital across V2/V3/Balancer/Stableswap) | 23 |
| `OptimalDepositSplit` | optimization/ | Q3.3 (V2 zap-in optimal swap fraction, non-mutating) | 19 |
| `AggregatePortfolio` | portfolio/ | Q6.1–Q6.3 (cross-protocol N-position aggregation) | ~34 |

**Not primitives but worth naming** — sibling-repo IL helpers that these primitives compose:
- `uniswappy.analytics.risk.UniswapImpLoss` — V2/V3 IL math, dual-role pattern (captures linear-share amounts at construction, exposes `calc_iloss`)
- `balancerpy.analytics.risk.BalancerImpLoss` — weighted-pool IL math, 2-asset, lifted during 1.2.0
- `stableswappy.analytics.risk.StableswapImpLoss` — stableswap IL math, 2-asset, with unreachable-alpha semantics

Full suite: **459 tests passing** (primitives + fixture smoke tests). The full 19-primitive inventory, LP-question mapping, and per-primitive v1 implementation notes live in `doc/execution/DEFIMIND_TIER1_QUESTIONS.md`. Authoring conventions (file layout, style, test coverage, `__init__.py` wiring, cross-protocol extension pattern) are in `doc/execution/PRIMITIVE_AUTHORING_CHECKLIST.md`.

Tier 1 scorecard: 17/19 from the original spec shipped. Remaining: `AssessLiquidityDepth` (V3 tick-walking, biggest unshipped piece) and `DiscoverPools` (web3scout-dependent, stretch goal).  Plus the three cross-protocol position analyzers beyond the 19-primitive spec.

### Legacy Agents (frozen for book chapter 9)

`python/prod/agents/` contains the original event-driven agents (`ImpermanentLossAgent`, `VolumeSpikeNotifierAgent`, `TVLBasedLiquidityExitAgent`, `PriceThresholdSwapAgent`). Preserved for readers of *Hands-On AMMs with Python* chapter 9. **Not the go-forward architecture** — new agentic behavior should be composed from primitives.

Agent imports in `python/prod/__init__.py` are wrapped in a broad `try/except ImportError` guard. If `web3scout` (or any of its transitive web3.py surface requirements) is missing or mismatched, agents are silently skipped with an `ImportWarning` directing the user to `pip install defipy[book]`. Core defipy (primitives, math, analytics) remains fully usable without `[book]` installed.

## Install Surface (1.2.0)

- `pip install defipy` — core math + analytics + primitives. **Zero chain-integration dependencies.**
- `pip install defipy[book]` — adds web3scout + web3 for chapter 9 agents and onchain examples.
- `pip install defipy[anvil]` — adds just web3 for local Foundry workflows using `ExecuteScript` / `UniswapScriptHelper`.

`[book]` is a superset of `[anvil]`.

## Key Internal Conventions (learned the hard way — propagate forward)

These are not obvious from reading any single file. They surfaced during primitive development and should be held in mind by anyone writing new primitives.

- **Multi-protocol state reads: use `LPQuote`, not direct `lp.*` calls.** `lp.get_amount_out` and `lp.get_reserve` are V2-specific — V3 fails with `AttributeError`. `LPQuote.get_amount(lp, token, amount_in, lwr, upr)` and `LPQuote.get_reserve(lp, token, lwr, upr)` dispatch correctly across V2/V3. Some direct `lp.*` methods are polymorphic (`lp.get_price`, `lp.get_liquidity`) but you can't tell which from the name — when in doubt, route through LPQuote.

- **`LPQuote` is the nucleus of the package.** Every meaningful cross-protocol operation — price reads, reserve access, LP↔token conversion, trade simulation — ultimately routes through LPQuote. When you understand LPQuote's surface, the rest of the architecture becomes obvious. Start reading there.

- **Paper value vs settlement value.** Position-level primitives use `UniswapImpLoss.x_tkn_init / y_tkn_init` for linear-share token amounts (paper value). `LPQuote(False).get_amount_from_lp` returns *settlement* value via an internal `RebaseIndexToken` swap — useful for exit-value questions but scale-dependent and crashes with `ZeroDivisionError` on V3 at 100% pool ownership. All shipped position/ primitives use paper value.

- **`UniswapImpLoss` does double duty.** Constructing it captures `x_tkn_init / y_tkn_init` (linear reserve share); the same instance provides `calc_iloss(alpha[, r])` for the IL formula. One construction, two uses. The AnalyzePosition and SimulatePriceMove primitives both rely on this pattern.

- **`lp.get_price(token)` is polymorphic** across V2 and V3, returns raw reserve ratio (no fee). Safe to use directly.

- **`lp.token0` and `lp.token1` are bare string symbols**, not ERC20 objects. `PoolHealth.token0_name = lp.token0` directly. No `.token_name` accessor needed. Contrast with ERC20 instances obtained via `lp.factory.token_from_exchange[lp.name][lp.token0]`, which are full ERC20 objects and do have a `.token_name`. Bare string is the right form for display and shared-exposure detection.

- **V2 and V3 expose fee differently.** V2 `UniswapExchange` has **no `.fee` attribute** — the fee is a protocol constant, hard-coded as 997/1000 (30 bps) inside `get_amount_out0/1`. V3 `UniswapV3Exchange` has `self.fee = exchg_struct.fee`, stored as pips (3000 = 0.3%, 500 = 0.05%). Primitives that need the stated fee must dispatch: hard-code 30 bps for V2, read `lp.fee / 100` for V3 in bps. DetectFeeAnomaly documents this asymmetry in its v1 V2-only scope.

- **Numeraire convention: first-token-in-insertion-order.** All position values, fees, and TVL figures are expressed in the pool's first-token units unless explicitly stated. For V2/V3 this is `lp.token0`; for Balancer and Stableswap it's `list(lp.tkn_reserves.keys())[0]`. AggregatePortfolio enforces this uniformly — the legacy "token0" framing was generalized to "first token" when Balancer and Stableswap joined the protocol mix. Mixed-numeraire portfolios raise `ValueError`; callers group by first-token symbol and call once per group. For stableswap primitives, values are in peg-numeraire (tokens 1:1 at peg), which falls out of the derivation naturally. Balancer analyzers use opp-token numeraire internally per `BalancerImpLoss`'s convention and re-label as base/opp on their dataclass.

- **Uniform-numeraire / common-pair as a v1 design stance for multi-input primitives.** AggregatePortfolio requires all input positions to share a common token0; CompareFeeTiers requires all candidates to share both token0 and token1 (same pair). Both raise `ValueError` with an index-identifying message on mismatch rather than silently summing or ranking across incompatible units. The error messages direct the caller to group by the mismatched axis and call multiple times. A multi-numeraire version can come later if the cross-numeraire case turns out to be common. The same stance will likely apply to CompareProtocols — define scope by rejecting shape mismatches rather than papering over them.

- **V2 has per-swap fee history (`fee0_arr`, `fee1_arr`); V3 does not.** V3 accumulates `feeGrowthGlobal0X128` / `feeGrowthGlobal1X128` and derives `collected_fee*` via `_update_fees()`. Primitives that rely on swap *history* (e.g., `CheckPoolHealth.fee_accrual_rate_recent`, `DetectRugSignals.inactive_with_liquidity`) return `None` / `False` for V3 and document why.

- **V3 `collected_fee0` / `collected_fee1` update synchronously during `Swap().apply()`.** Correcting an earlier misreading: V3's fee-growth accumulators get converted to `collected_fee0/1` as part of the swap path, not lazily on a later trigger. `CheckPoolHealth.total_fee0 / total_fee1` show the updated values immediately. This was verified during CompareFeeTiers test authoring — a single swap on a V3 pool populates `collected_fee0` visible through `CheckPoolHealth`. What V3 does *not* have is per-swap history (no `fee0_arr`), only the running accumulator — so rate/window metrics remain V2-only, but point-in-time totals are available on both protocols.

- **V2 zap-in α does NOT grow with deposit size. It shrinks.** The closed-form V2 zap-in quadratic yields α → 1/(1+f) ≈ 0.50075 in the limit of zero deposit (f = 0.997 is the fee multiplier) and dα/d(dx) < 0 identically for dx > 0. Intuition: a larger swap moves the price more, so each unit swapped buys LESS of the opposing token, so you need to swap LESS. The 30-bps fee is the only thing that puts the limiting value slightly above 0.5; the direction of movement with size is *downward*. Verified empirically (α = 0.4779 at 200/1000 = 20% of reserves) and via implicit differentiation. OptimalDepositSplit's docstring and tests now enforce the correct direction; an earlier iteration of the tests asserted `α > 0.5` at size and failed, which prompted the full derivation. Keep in mind for any primitive that reasons about V2 zap-in mechanics.

- **Non-mutating primitives that compose over process-layer math.** OptimalDepositSplit calls `SwapDeposit()._calc_univ2_deposit_portion(...)` — a leading-underscore method on the mutating `SwapDeposit` process object — purely as a read. The helper itself doesn't mutate the pool (it only reads reserves and solves the quadratic); the mutation happens in `SwapDeposit.apply`, which is a separate entry point. This pattern is clean when the math helper is factored out, less clean when it isn't. If a future uniswappy refactor reshapes the private method, OptimalDepositSplit breaks — worth asking uniswappy to promote `_calc_univ2_deposit_portion` to a public `calc_univ2_deposit_portion` at some point, but not blocking for v1. Same pattern would apply for any future primitive wanting to project what a process-layer apply() would do without executing it.

- **V2 `liquidity_providers` has a `"0"` sentinel** for the `MINIMUM_LIQUIDITY` burn at first mint. Exclude it from LP counting and concentration metrics.

- **V3 sign convention in `CheckTickRangeStatus`**: `pct_to_lower` and `pct_to_upper` are positive when in-range, negative when the corresponding bound has been crossed.

- **Stableswap math_pool balance units.** `math_pool.balances[i]` is in each token's native decimal units (USDC at 10**6 scale, DAI at 10**18 scale). Converting to human-readable amounts uses `dec2amt(balance, token_decimals)` directly — no rate-table manipulation needed at that boundary. The `rates` table is used internally for building xp (all tokens at common 10**18 scale for invariant math); xp → balance conversion goes through rates, but balance → human conversion does not. Getting this wrong (multiplying through rates twice) produced a ~10⁴× error during session 2026-04-22 initial AssessDepegRisk attempts.

- **Closed forms over solvers, when available.** FindBreakEvenPrice and SimulatePriceMove both collapse to exact closed-form solutions after correct formulation (see the SolveDeltasRobust entry in the backlog for the same pattern applied to pool rebalancing). AssessDepegRisk does the same for stableswap IL by deriving a fixed-point relation between ε and δ. DetectFeeAnomaly ships with a pure-float constant-product formula as the invariant reference, compared directly against integer-math `get_amount_out`. Default to finding the closed form before reaching for `scipy.optimize.fsolve` or for driving a protocol library's state solvers into a counterfactual region.

- **Invariant-math primitives vs. state-threading primitives.** Most primitives drive the protocol library — they ask the `lp` object "what happens if this trade or composition change is applied." Some primitives answer a different kind of question: "what's the relationship between pool composition and price, given the invariant the pool obeys?" or "is the pool's own math internally consistent with its stated parameters?" For those, evaluating the invariant directly in floats is usually cleaner than driving the protocol library's state-transition solvers to a counterfactual target. AssessDepegRisk and DetectFeeAnomaly are the two primitives of this shape — they read a handful of scalars from the `lp` object and perform the core math in pure floats. Protocol library as *metadata adapter*, invariant as *math source*. See PRIMITIVE_AUTHORING_CHECKLIST.md §10 for detailed guidance on choosing the approach.

- **Threshold comparators deserve edge-case thought.** `DetectRugSignals` uses strict `>` on concentration (so passing `1.0` means "never fire") and `<=` on the TVL floor (so the floor reads as "minimum acceptable"). Two signals, two comparators, picked per signal's intuitive meaning rather than forced into a single rule. The `>= with threshold=1.0` bug caught during shipping reinforced: step through the ceiling-case of every threshold before writing the comparator.

- **Composition primitives should read only their dependency's output.** `DetectRugSignals` calls `CheckPoolHealth` and operates purely on the returned `PoolHealth` — no direct `lp.*` access. If a signal can't be expressed from the dependency's output, it belongs on a different primitive (or the dependency needs extending). Keeps the "primitives chain into primitives" claim honest.

- **Two chaining shapes: depth and breadth.** DetectRugSignals demonstrates *depth* chaining — one primitive composed over another. AggregatePortfolio demonstrates *breadth* chaining — the same primitive applied N times, results aggregated. Both are legitimate composition patterns; future primitives should pick the shape that fits the question, not default to one. Depth-chains work for threshold-over-metric patterns (DetectRugSignals). Breadth-chains work for "summarize across a set" patterns (AggregatePortfolio, eventually CompareProtocols, CompareFeeTiers). DetectFeeAnomaly is neither — it's a math primitive, not a composition. The full `EvaluateRebalance` when shipped will combine depth and breadth — depth-chain several per-position primitives, then use breadth-chain logic to rank candidates.

- **Signal surfacer, not verdict generator.** Established by DetectRugSignals, continued by AggregatePortfolio's `pnl_ranking` (not "exit_priority" as the spec had it) and its `shared_exposure_warnings` (not "correlation"). AssessDepegRisk extends it to "no aggregate risk_level field" — the scenarios are reported as a grid, callers decide how to interpret 2% vs. 50% vs. unreachable. DetectFeeAnomaly extends it further with `direction: "pool_underdelivers" | "pool_overdelivers"` — descriptive signed-discrepancy labels rather than accusatory terms like `"pool_skimming"`, because underdelivery has many possible causes (skim, bug, admin fee, rounding) and the primitive shouldn't prejudge. Primitives expose the numbers and the orderings; the verdict belongs to the caller. Fields named for verdicts overpromise what the math actually delivers.

- **Reachability as a first-class output.** Invariant-math primitives can be asked questions with no physical solution (e.g., "IL at δ=0.02 in a pool with A=200" requires |ε| > 1, violating the invariant). Flag unreachable scenarios explicitly — in AssessDepegRisk, `lp_value_at_depeg`, `hold_value_at_depeg`, and `il_pct` are `Optional[float]` and set to `None` when the target is unreachable; the V2 comparison stays populated. Callers check `il_pct is None` to distinguish reachable from unreachable without guessing at a sentinel. Better than silently returning the closest reachable approximation.

- **One dataclass per file is a guideline, not a rule.** `PositionSummary` lives in `PortfolioAnalysis.py` because it's a structural component of `PortfolioAnalysis` rather than a standalone result. `DepegScenario` lives in `DepegRiskAssessment.py` for the same reason. Nested component types can colocate with their parent; top-level primitive results get their own file.

- **Cross-protocol extensions: sibling primitives, not isinstance-branchy single primitives.** When a primitive is V2/V3-specific but the question it answers is protocol-independent (IL decomposition, PnL), the right shape is three parallel primitives (one per AMM family) that share the `apply()` contract but return protocol-specific dataclasses. This is the pattern `UniswapImpLoss` / `BalancerImpLoss` / `StableswapImpLoss` uses at the sibling-repo level, and the pattern `AnalyzePosition` / `AnalyzeBalancerPosition` / `AnalyzeStableswapPosition` uses at the defipy level. Forcing isinstance dispatch into a single primitive creates branchy unreadable code and conflates result shapes (per-token lists only make sense for stableswap; weight fields only make sense for Balancer). Composition primitives (AggregatePortfolio) do the dispatch at the *aggregator* layer, which is the correct home for it — each analyzer stays focused.

- **Balancer fee-free spot price: read reserves and weights directly, not `lp.get_price`.** `BalancerExchange.get_price` bakes in the SWAP_FEE (0.25%) scale factor and returns a Decimal. For IL analysis, we want the fee-free spot — `spot = (b_opp / w_opp) / (b_base / w_base)`. `BalancerImpLoss.apply` computes this internally; `AnalyzeBalancerPosition` inlines the same formula (to avoid reading reserves twice). Any future Balancer primitive wanting spot-for-IL should read the reserves and weights directly, not route through `get_price`. Noted here because it's a trap: the method name suggests "correct price," but the IL math wants the raw invariant ratio.

- **Stableswap `dydx` returns 1.0 exactly at balance, confirmed via source read.** `StableswapPoolMath._dydx(i, j, xp, use_fee)` returns `(xj * (xi * A_pow * x_prod + D_pow)) / (xi * (xj * A_pow * x_prod + D_pow))`, which is algebraically 1.0 when `xi == xj`. Safe to use as the at-peg short-circuit condition — `AnalyzeStableswapPosition` uses `abs(dydx - 1.0) < 1e-12` to detect balanced pools and shortcut to zero IL. No floating-point noise to worry about at balance. Important for any future stableswap primitive that wants to branch on peg/off-peg; this is a cheap and correct test.

- **Balancer SWAP_FEE is 0.25%, not 0.3%.** `balancerpy.cwpt.exchg.BalancerExchange` sets `SWAP_FEE = 0.0025` at module level (compare Uniswap V2's 30 bps = 0.003). Matters for any primitive computing Balancer swap outputs or expected fee yields. Documented on the exchange class. Doesn't affect IL math (fee-free spot is used there), but affects slippage, fee-yield estimation, and any future Balancer extension of CalculateSlippage.

## Testing

Shared fixtures in `python/test/primitives/conftest.py`:
- `v2_setup` — 1000 ETH / 100000 DAI V2 LP, USER owns 100%
- `v3_setup` — same reserves, full-range V3, tick_spacing=60, fee=3000
- `balancer_setup` — 50/50 ETH/DAI weighted Balancer pool, USER holds 100 pool shares
- `weighted_balancer_setup` — factory fixture, takes `(base_weight, suffix)`, returns a Balancer pool at the requested weighting
- `stableswap_setup` — 2-asset USDC/DAI stableswap at A=10, 100K of each token
- `amplified_stableswap_setup` — factory fixture, takes `(A, suffix)`, returns a stableswap at the requested amplification

Each returns a setup dataclass (`V2Setup`, `V3Setup`, `BalancerSetup`, `StableswapSetup`) with the appropriate fields. V2/V3 have `.lp`, `.eth`, `.dai`, `.lp_init_amt`, `.entry_x_amt`, `.entry_y_amt` (V3 adds `.lwr_tick`, `.upr_tick`). Balancer has `.lp`, `.lp_init_amt`, `.entry_base_amt`, `.entry_opp_amt`. Stableswap has `.lp`, `.lp_init_amt`, `.entry_amounts` (a list), and `.A`.

Note: the V2/V3 fixture's 100% ownership is deliberately stressful — it exposed the `RebaseIndexToken` V3 divide-by-zero bug during SimulatePriceMove development. New primitives that use V3 codepaths should run against this fixture specifically to catch similar issues. The Balancer and Stableswap fixtures also put USER at 100% ownership for consistency; the IL classes (BalancerImpLoss, StableswapImpLoss) are designed around this and the math is valid at full ownership.

**Factory-pattern fixtures for regime coverage.** `weighted_balancer_setup` and `amplified_stableswap_setup` take parameters and return fresh pools per call — this lets tests like `test_80_20_has_less_il_than_50_50` build two pools with different weights in the same test without cross-contamination. This is the same pattern as AssessDepegRisk's inline `_build_pool(ampl)` builder, but promoted to conftest.py because it's used by multiple test files now. Future regime-dependent primitives should use this pattern rather than re-inventing per-test pool builders.

**Inline pool builders for ad-hoc needs.** AggregatePortfolio's cross-protocol tests construct a V2 USDC/DAI pool inline (`_build_usdc_dai_v2`) and a DAI-first Balancer pool inline (for the mixed-first-token-rejection test). CompareProtocols and CompareFeeTiers similarly use inline helpers. Inline over fixture is the right call when a test needs an *atypical* pool shape (non-matching first token, exotic weight, etc.) that promoting to conftest would fold into the common path unnecessarily.

**Independent-oracle cross-checks for invariant-math primitives.** AssessDepegRisk's test file includes `_reference_il(A, delta)` — a separate implementation of the same derivation, used as a correctness witness. If either the primitive or the reference has a bug the derivation didn't catch, the cross-check fails and surfaces it. The two code paths are independent (same math, different expression); a single test validates both simultaneously. Future invariant-math primitives should do the same. DetectFeeAnomaly's equivalent is `test_theoretical_output_matches_hand_formula` — the test re-implements the constant-product-with-fee formula inline and asserts the primitive matches.

**V3-rejection test classes.** For primitives scoped V2-only (DetectFeeAnomaly) or stableswap-only (AssessDepegRisk), a dedicated small test class wires up the *other* protocol's fixture and asserts the expected ValueError. Keeps the scope boundary visible in the test suite, not only in the docstring.

```bash
# Full primitive suite
pytest python/test/primitives/ -v

# Release gate across all sibling packages (clean venv)
./resources/run_clean_test_suite.sh --with-defipy
```

**Working-branch state: 459 tests passing.**

## Usage Patterns

```python
from defipy import (
    # V2/V3 position analysis
    AnalyzePosition,
    SimulatePriceMove,
    FindBreakEvenPrice,
    FindBreakEvenTime,
    # Cross-protocol position analysis
    AnalyzeBalancerPosition,
    AnalyzeStableswapPosition,
    # Execution
    CalculateSlippage,
    DetectMEV,
    # Risk / pool health
    CheckTickRangeStatus,
    CheckPoolHealth,
    DetectRugSignals,
    DetectFeeAnomaly,
    AssessDepegRisk,
    # Optimization
    EvaluateTickRanges,
    EvaluateRebalance,
    OptimalDepositSplit,
    # Comparison
    CompareFeeTiers, FeeTierCandidate,
    CompareProtocols, ProtocolCandidate,
    # Portfolio
    AggregatePortfolio, PortfolioPosition,
)

# Position analysis
result = AnalyzePosition().apply(lp, lp_init_amt, entry_eth, entry_dai)
# → PositionAnalysis(current_value, hold_value, il_percentage, il_with_fees,
#                   fee_income, net_pnl, real_apr, diagnosis)

# Price-move simulation
scenario = SimulatePriceMove().apply(lp, -0.30, position_size_lp)
# → PriceMoveScenario(new_price_ratio, new_value, il_at_new_price,
#                    fee_projection, value_change_pct)

# Trade slippage
slip = CalculateSlippage().apply(lp, token_in, amount_in)
# → SlippageAnalysis(spot_price, execution_price, slippage_pct,
#                   slippage_cost, price_impact_pct, max_size_at_1pct)

# V3 range status
status = CheckTickRangeStatus().apply(lp, lwr_tick, upr_tick)
# → TickRangeStatus(current_tick, lower_tick, upper_tick, pct_to_lower,
#                  pct_to_upper, in_range, range_width_pct)

# Break-even alphas (returns both directions)
be = FindBreakEvenPrice().apply(lp, lp_init_amt, fee_income)
# → BreakEvenAlphas(break_even_alpha_down, break_even_alpha_up,
#                  break_even_price_down, break_even_price_up,
#                  fee_to_entry_ratio, upside_hedged)

# Pool-level snapshot
health = CheckPoolHealth().apply(lp)
# → PoolHealth(version, token0_name, token1_name, spot_price, reserve0,
#             reserve1, total_liquidity, tvl_in_token0, total_fee0, total_fee1,
#             num_swaps, fee_accrual_rate_recent, num_lps, top_lp_share_pct,
#             has_activity)

# Rug-signal detection (depth-chain over CheckPoolHealth)
signals = DetectRugSignals().apply(lp, tvl_floor = 100.0)
# → RugSignalReport(tvl_suspiciously_low, single_sided_concentration,
#                  inactive_with_liquidity, signals_detected,
#                  risk_level ∈ {"low","medium","high","critical"},
#                  details, pool_health)

# Balancer 2-asset position analysis
bal_result = AnalyzeBalancerPosition().apply(
    bal_lp, lp_init_amt,
    entry_base_amt = 10.0,   # ETH deposited
    entry_opp_amt  = 10000.0,  # DAI deposited
)
# → BalancerPositionAnalysis(base_tkn_name, opp_tkn_name, base_weight,
#                           current_value, hold_value, il_percentage,
#                           il_with_fees, fee_income, net_pnl, real_apr,
#                           diagnosis, alpha)

# Stableswap 2-asset position analysis
ss_result = AnalyzeStableswapPosition().apply(
    ss_lp, lp_init_amt,
    entry_amounts = [100000.0, 100000.0],  # USDC, DAI
)
# → StableswapPositionAnalysis(token_names, A, per_token_init,
#                             per_token_current, current_value, hold_value,
#                             il_percentage (Optional), il_with_fees (Optional),
#                             fee_income, net_pnl (Optional), real_apr (Optional),
#                             diagnosis, alpha (Optional))
# Unreachable-alpha regime (high A + large dydx): Optional fields are None.

# Portfolio aggregation — cross-protocol (breadth-chain over Analyze*Position)
portfolio = AggregatePortfolio().apply([
    # V2 position
    PortfolioPosition(lp = v2_lp, lp_init_amt = v2_amt,
                      entry_x_amt = 500, entry_y_amt = 1_000_000),
    # V3 position
    PortfolioPosition(lp = v3_lp, lp_init_amt = v3_amt,
                      entry_x_amt = 500, entry_y_amt = 1_000_000,
                      lwr_tick = lwr, upr_tick = upr),
    # Balancer position
    PortfolioPosition(lp = bal_lp, lp_init_amt = bal_shares,
                      entry_x_amt = 10.0, entry_y_amt = 10000.0),
    # Stableswap position — NB uses entry_amounts, not entry_x/y_amt
    PortfolioPosition(lp = ss_lp, lp_init_amt = ss_shares,
                      entry_amounts = [100000.0, 100000.0]),
])
# → PortfolioAnalysis(numeraire, total_value, total_hold_value,
#                    total_fees, total_net_pnl, positions (in input order),
#                    pnl_ranking (worst-first), shared_exposure_warnings)
# Each PositionSummary includes `protocol`: "uniswap_v2" | "uniswap_v3" |
#   "balancer" | "stableswap". All positions must share a common first-token
#   symbol (the portfolio numeraire); mixed-numeraire raises ValueError.
# Stableswap positions in unreachable-alpha regime contribute 0 to totals
#   and are flagged in shared_exposure_warnings.

# Stableswap depeg risk (invariant-math, N=2)
risk = AssessDepegRisk().apply(ss_lp, ss_lp_init_amt, usdc_token,
                               depeg_levels = [0.02, 0.05, 0.10, 0.20, 0.50])
# → DepegRiskAssessment(depeg_token, protocol_type, n_assets,
#                      current_peg_deviation,
#                      scenarios = List[DepegScenario])
# Each DepegScenario has:
#   depeg_pct, peg_price,
#   lp_value_at_depeg (Optional — None if unreachable),
#   hold_value_at_depeg (Optional),
#   il_pct (Optional),
#   v2_il_comparison (always populated — V2 IL benchmark)

# V2 fee-anomaly detection (invariant-vs-contract consistency)
anomaly = DetectFeeAnomaly().apply(v2_lp, eth_token)
# → FeeAnomalyResult(stated_fee_bps=30, test_amount, theoretical_output,
#                   actual_output, discrepancy_bps (signed),
#                   direction ∈ {"pool_underdelivers", "pool_overdelivers"},
#                   anomaly_detected)
# Default threshold 10 bps; adjustable via constructor.

# V3 fee-tier comparison (breadth-chain over CheckPoolHealth + CheckTickRangeStatus)
comparison = CompareFeeTiers().apply([
    FeeTierCandidate(lp = lp_5bps,   position_size_lp = amt_5,
                     lwr_tick = l5, upr_tick = u5),
    FeeTierCandidate(lp = lp_30bps,  position_size_lp = amt_30,
                     lwr_tick = l30, upr_tick = u30),
    FeeTierCandidate(lp = lp_100bps, position_size_lp = amt_100,
                     lwr_tick = l100, upr_tick = u100),
])
# → FeeTierComparison(numeraire, pair, tiers, ranking_by_observed_fee_yield,
#                    ranking_by_tvl, notes)
# Each FeeTierMetrics has:
#   name, fee_tier_bps, pool_tvl_in_token0,
#   observed_fee_yield (Optional — cumulative, not annualized),
#   in_range, range_width_pct
# Reports observed yield (cumulative fees / TVL), not a forecast —
# callers who know pool age annualize themselves.

# V2 zap-in optimal split (non-mutating projection of SwapDeposit)
split = OptimalDepositSplit().apply(v2_lp, eth_token, amount_in = 50.0)
# → DepositSplitResult(token_in_name, amount_in, optimal_fraction,
#                      swap_amount_in, swap_amount_out,
#                      deposit_amount_in, deposit_amount_out,
#                      expected_lp_tokens, slippage_cost, slippage_pct)
# α = optimal_fraction is the exact swap fraction that leaves zero
# dust post-deposit. Pure read — does NOT mutate the pool. Pair with
# SwapDeposit().apply() to execute; projected expected_lp_tokens
# matches what SwapDeposit actually mints within ~0.1%.
```

## Next Phase

Tier 1 is substantially complete — 17 of the original 19 primitives have shipped, plus 3 cross-protocol position analyzers that weren't in the original spec. The remaining work falls into four buckets in descending value/effort order:

### Recommended opener for next session

1. Verify working-branch state: `pytest python/test/primitives/ -v` should show 459 passing.
2. Pick a bucket below — the strongest lean depends on immediate goals (infrastructure completeness vs. demonstrable capability).

### Bucket A — Cross-protocol depth: round out Balancer/Stableswap (~half-day to day)

The three shipped cross-protocol analyzers (`AnalyzePosition` + Balancer/Stableswap siblings) establish the pattern. Two near-term extensions follow the same shape without new math:

- **`SimulateBalancerPriceMove` / `SimulateStableswapPriceMove`** — mirror `SimulatePriceMove`, compose over the Impermanent Loss classes with alpha override. Pure copy-of-pattern, ~30 min each. Unblocks full V2/V3/Balancer/Stableswap parity for the "what if price moved X%" question.
- **Balancer/Stableswap slippage extension to `CalculateSlippage`** — currently V2/V3-only. Add sibling primitives or extend CalculateSlippage itself to dispatch by protocol. Unlocks full slippage plumbing in `CompareProtocols`.

These are low-risk and move the library toward "every question the 17 primitives answer, answers that question on any of the 4 protocols" which is a real and useful completeness bar.

### Bucket B — Real math: break-even on non-Uniswap protocols (half-day each)

- **`FindBreakEvenBalancerPrice`** — needs new derivation. Balancer's weighted-pool IL is `α^w_base + (1-w_base)·α^(w_base - 1) - 1` (approximately); solving `fees + IL(α) = 0` for α requires inverting that expression, which doesn't have a general closed form. Newton's method converges cleanly; the question is whether to derive a two-root formula for the upside/downside alphas symmetric to `FindBreakEvenPrice`.
- **`FindBreakEvenStableswapPrice`** — needs new derivation over the invariant. Similar to `AssessDepegRisk`'s ε↔δ fixed point but inverted to solve for the δ where fees compensate IL.

Both are genuine math work and deserve the same "derive-on-paper-first" discipline that `AssessDepegRisk` got.

### Bucket C — The big unshipped primitive: V3 liquidity depth (full day)

- **`AssessLiquidityDepth`** — the largest remaining piece from the original Tier 1 spec. Needs V3 tick-walking infrastructure that doesn't exist in the codebase yet. Answers Q9.1, Q9.3, Q9.4, Q9.6 and also unblocks V3 extension of DetectFeeAnomaly via the UniV3Helper.quote fix (tracked in cleanup backlog). Deserves a dedicated session with up-front design on tick-walking abstractions — likely a new `utils/tools/v3/TickWalker` helper that other V3 primitives can reuse.

### Bucket D — Stretch and lower-value items

- **`DiscoverPools`** — web3scout-dependent, requires chain scanning. Not primitive-library work in the pure sense; belongs later.
- **N-asset extensions of BalancerImpLoss, StableswapImpLoss, AnalyzeBalancerPosition, AnalyzeStableswapPosition** — non-trivial math (different parameterization for N>2), limited practical payoff for the common 2-asset stablecoin and ETH/stable pairs that dominate.
- **Fee-attribution for Balancer and Stableswap** — would require pool-object API extensions in the sibling repos. Currently `fee_income = 0.0` for both in `AnalyzeBalancer/StableswapPosition`. Not blocking; fee yield can be tracked externally by callers who care.

Full LP-question mapping, per-primitive signatures, and v1 implementation notes for all shipped primitives live in `doc/execution/DEFIMIND_TIER1_QUESTIONS.md`. Read that doc before designing any extension — the per-primitive notes there capture scope decisions that shouldn't be re-litigated.

### Decision heuristics for picking the next primitive (general, beyond #11)

1. **Mode B is mandatory.** Read the relevant uniswappy/balancerpy/stableswappy source before proposing a design. Session 2026-04-18 proved Mode A (design-then-discover-API-through-failing-tests) costs more tokens than it saves. Every primitive that skipped this step had at least one revision cycle. DetectFeeAnomaly reinforced this — reading `UniswapExchange.get_amount_out0` and `UniV3Helper.quote` mid-implementation revealed the V2-vs-V3 fee asymmetry and the hard-coded-997 bug, which shaped the V2-only scope.
2. **Composition primitives before new-math primitives, when both are available.** They're lower-risk (no new derivations to verify), they demonstrate the architecture's key claim (composability), and they're educational about what the shipped primitives actually expose. Two patterns available: depth-chain (one-into-one) and breadth-chain (one-over-many). Pick whichever fits the question.
3. **V2+V3 parity is the target, but scope honestly.** `CalculateSlippage`'s `max_size_at_1pct` is V2-only with V3 documented as `None`. That's a defensible shape. `FindBreakEvenPrice` is V2+V3 full. `CheckPoolHealth`'s `num_swaps` is V2-only; `DetectRugSignals.inactive_with_liquidity` inherits that V2-only-ness. `AssessDepegRisk` is stableswap-only + N=2. `DetectFeeAnomaly` is V2-only (blocked on UniV3Helper fee-passthrough fix — see backlog). These are examples of graceful degradation — do the same when a broader implementation would be infeasible or disproportionately expensive.
4. **Fixture stress is a feature.** The `v2_setup` / `v3_setup` at 100% pool ownership is intentionally pathological. It exposed one real bug (`RebaseIndexToken` V3 divide-by-zero) during session 2026-04-18 and forced the DetectRugSignals "top LP at ~100%" test case during session 2026-04-21. Keep new primitives running against this fixture; don't relax it to "make V3 work."
5. **Step through threshold edge cases before writing the comparator.** Session 2026-04-21's DetectRugSignals bug was `>=` vs. `>` at `threshold=1.0`. For any primitive that takes a threshold with a meaningful ceiling or floor, verify the ceiling/floor case explicitly before shipping.
6. **Name fields for information, not verdicts.** `pnl_ranking` not `exit_priority`; `shared_exposure_warnings` not `correlation_warnings`; `signals_detected` not `is_rug`; `pool_underdelivers` not `pool_skimming`. The primitive exposes numbers and orderings; the judgment belongs to the caller. Spec-level verdict naming is a recurring pattern worth pushing back on during design.
7. **Design decisions up front, written down.** Session 2026-04-21 shipped DetectRugSignals with one mid-session redesign and one test-caught bug. Session 2026-04-22 shipped AggregatePortfolio with zero mid-session corrections — the difference was the explicit up-front design conversation with written-out reasoning before code. AssessDepegRisk initially skipped this step and cost four rounds of local fixes; when Option B (analytical invariant evaluation, worked out on paper first) was proposed with full derivation, it shipped first try. DetectFeeAnomaly took the same up-front-design approach: Shape A vs B, direction classification, V2-only scope all settled before code; shipped clean. Reproduce this pattern.
8. **Three rounds, then rethink.** If a primitive's implementation has required three or more rounds of local fixes against failing tests, stop adding fixes and reconsider the *approach*, not the patch. Session 2026-04-22's AssessDepegRisk initial iterative-solver approach accumulated a modeling error, a unit-conversion error, a reachability assumption violation, and was about to accumulate a fourth before the pivot to the analytical approach resolved everything cleanly. When at round 3, ask: "is this approach compatible with what my dependency was designed for?" If no, propose an alternative explicitly and get user sign-off before reimplementing. Codified as §9 of PRIMITIVE_AUTHORING_CHECKLIST.md.
9. **Invariant-math vs state-threading: pick deliberately.** For counterfactual questions at the edges of a protocol library's operating envelope (extreme depegs, far out-of-range price moves, drained pools), evaluating the invariant directly in floats is usually cleaner than driving the library's state solvers to the counterfactual target. For forward trajectories (swap + deposit + withdrawal sequences, fee accumulation over time), state threading through the protocol library is correct. AssessDepegRisk and DetectFeeAnomaly are the two invariant-math primitives shipped so far; the pattern is codified as §10 of PRIMITIVE_AUTHORING_CHECKLIST.md.
10. **When dependency tooling reveals a limitation, scope narrower; don't invent workarounds.** Session 2026-04-22's DetectFeeAnomaly discovered that `UniV3Helper.quote` hard-codes 30 bps rather than reading `lp.fee`. Rather than invent a synthetic V3 path, v1 shipped V2-only and the UniV3Helper issue went to the backlog. Future primitives hitting similar dependency-layer issues should follow suit: document the issue, track in backlog, scope the primitive honestly, ship.
11. **Direction-of-change assertions deserve a derivation, not a prior.** Session 2026-04-23's OptimalDepositSplit shipped with tests asserting `α > 0.5` for large V2 zap deposits — based on an intuition ("swap moves price so you swap more to match what's left") that sounded right but was wrong. The actual math has dα/d(dx) < 0 identically: α starts at 1/(1+f) ≈ 0.50075 in the zero-deposit limit and DECREASES with deposit size. The failed tests forced the derivation. The generalizable rule: when a test assertion encodes a direction of change or a monotonicity claim, work out the sign from the closed form BEFORE writing the assertion. Better yet, write the monotonicity claim as a sequential test across increasing inputs — that's a stronger assertion than any single-threshold check, and it tells you immediately when your sign intuition is backwards. Applies especially to primitives reasoning about AMM mechanics where "this moves the price" is often less directly related to caller-observable behavior than it feels.

12. **Cross-protocol extensions: sibling primitives, not branchy dispatch within a single primitive.** When a primitive is V2/V3-specific but the question is protocol-independent, add sibling primitives (`AnalyzePosition` + `AnalyzeBalancerPosition` + `AnalyzeStableswapPosition`) with distinct result dataclasses. Keep each focused on its protocol's natural math and API shape; do the dispatch at the *composition* layer (AggregatePortfolio) where it belongs. Don't inflate the original primitive with isinstance branches, Optional fields that are only-populated-for-one-protocol, or per-token-list shapes that only stableswap uses. Split dataclasses (BalancerPositionAnalysis, StableswapPositionAnalysis) keep V2/V3 callers from reasoning about fields they never need; AggregatePortfolio's isinstance-based router extracts the common scalars uniformly for the breadth-chain sum. Pattern codified as PRIMITIVE_AUTHORING_CHECKLIST.md §11.

13. **Composition-layer dispatch scales; primitive-layer dispatch does not.** AggregatePortfolio extended to cross-protocol in ~200 lines by pushing isinstance checks into a private `_detect_protocol` helper and routing to the appropriate analyzer. If the same dispatch had been pushed into each individual analyzer (`AnalyzePosition` growing Balancer and Stableswap branches), every position primitive would need that dispatch duplicated, every test file would fork by protocol, and any new primitive would need to re-solve the same problem. The rule: stateless primitives are simpler when they know their protocol at authoring time; multi-input primitives (breadth-chain aggregators, cross-protocol comparators) are the correct home for dispatch. Applies equally to any future CompareProtocols-shaped primitive.

### Later: LLM Reasoning Layer (DeFiMind)

Once the primitive library is substantially complete, add a reasoning layer on top for intent-based LP diagnostics, multi-protocol orchestration, and chained primitive calls as LLM tools. The primitives themselves stay LLM-agnostic.

The composability architecture is the point: LLMs don't get special tool definitions — the primitives **are** the tools, same interface a quant uses in a notebook. This was clarified during session discussion on 2026-04-18 and is the distinguishing feature vs. other agentic DeFi frameworks that wrap LLMs around raw onchain data.

## File Structure Reference

```
python/prod/
├── primitives/              # Analytics primitives (new in 1.2.0)
│   ├── position/            # AnalyzePosition, SimulatePriceMove, FindBreakEvenPrice,
│   │                        # FindBreakEvenTime, AnalyzeBalancerPosition,
│   │                        # AnalyzeStableswapPosition
│   ├── execution/           # CalculateSlippage, DetectMEV
│   ├── risk/                # CheckTickRangeStatus, AssessDepegRisk
│   ├── pool_health/         # CheckPoolHealth, DetectRugSignals, DetectFeeAnomaly
│   ├── portfolio/           # AggregatePortfolio (cross-protocol dispatch)
│   ├── comparison/          # CompareFeeTiers, CompareProtocols
│   └── optimization/        # OptimalDepositSplit, EvaluateRebalance, EvaluateTickRanges
├── agents/                  # Legacy — frozen for book chapter 9
├── cpt/quote/               # Core pricing/liquidity (re-exports from uniswappy)
├── cpt/index/               # Mathematical inverse relationships
├── process/                 # AMM operation implementations (V2/V3/Balancer/Stableswap dispatch)
└── utils/data/              # Result dataclasses:
                               PositionAnalysis, BalancerPositionAnalysis,
                               StableswapPositionAnalysis, PriceMoveScenario,
                               SlippageAnalysis, TickRangeStatus, BreakEvenAlphas,
                               BreakEvenTimeResult, PoolHealth, RugSignalReport,
                               MEVDetectionResult, TickRangeEvaluation (+ RangeMetrics),
                               RebalanceEvaluation, PortfolioPosition,
                               PortfolioAnalysis (+ nested PositionSummary),
                               DepegRiskAssessment (+ nested DepegScenario),
                               FeeAnomalyResult, FeeTierCandidate,
                               FeeTierComparison (+ nested FeeTierMetrics),
                               ProtocolCandidate, ProtocolComparison
                                 (+ nested ProtocolMetrics),
                               DepositSplitResult

doc/
├── PROJECT_CONTEXT.md                              # This file
└── execution/
    ├── DEFIMIND_TIER1_QUESTIONS.md                 # 19-primitive spec
    └── PRIMITIVE_AUTHORING_CHECKLIST.md            # Mechanical authoring guide
```

## Cleanup Backlog (tracked across sibling packages)

Items that surfaced during 1.2.0 but belong in future releases of the sibling packages:

- **uniswappy**: SPDX watermark in `prod/__init__.py`; unused `import pytest` in `UniV3Utils.py` line 29; potential ghost deps in `install_requires` (audit `requests`)
- **balancerpy**: migrate `from attr import dataclass` → stdlib `dataclasses`
- **uniswappy**: `UniswapImpLoss.apply(fees=True)` has a one-sided vs total-numeraire comparison math issue (noted April 16 audit; AnalyzePosition sidesteps it by not using `apply(fees=True)`)
- **uniswappy**: `RebaseIndexToken.calc_univ3_tkn_settlement` divides by `L_diff = L - dL`, fails at 100% ownership. Latent since defipy no longer uses this codepath, but still a real bug for anyone else calling `LPQuote(False).get_amount_from_lp` on a fully-owned V3 pool.
- **web3scout**: migration off `web3._utils.contracts.get_function_info` (private API) would let defipy drop the `web3 < 7.0` pin. Flagged as "possibly transitional piece" — as the ecosystem matures, web3scout may be rewritten or deprecated.

- **uniswappy `UniV3Helper.quote` hard-codes fee = 997.** The V3 non-mutating quote helper at `uniswappy/python/prod/utils/tools/v3/UniV3Helper.py:quote` applies a hard-coded `fee = 997` rather than reading from `lp.fee`. For a 30-bps V3 pool this matches; for any other fee tier (100/500/10000 = 0.01%/0.05%/1%) the helper returns values that diverge from what the pool's actual swap would produce. This is itself a latent fee anomaly in the tooling — exactly what DetectFeeAnomaly was built to surface — but it means DetectFeeAnomaly can't cleanly use the helper as a V3 ground-truth "actual output" path. Surfaced during session 2026-04-22 while scoping DetectFeeAnomaly V3 extension; resulted in V2-only v1 scope. Fix: read `lp.fee` inside `quote()` and apply the pip-to-fraction conversion (`lp.fee / 1_000_000`), replacing the hard-coded `997`. Blocker for V3 extension of DetectFeeAnomaly and a latent issue for anyone using `LPQuote.get_amount(include_fee=True)` on non-30-bps V3 pools.

- **stableswappy `get_y` / `get_D` need iteration caps.** Both Newton loops in `StableswapPoolMath.py` use `while abs(x - x_prev) > 1` with no iteration cap. At extreme balance ratios (dydx far from 1) these can fail to converge, hanging any caller. This surfaced during session 2026-04-22's first attempts at AssessDepegRisk, where bisecting on balance multipliers to reach extreme depegs caused hangs. The fix is parallel to uniswappy's `SolveDeltasRobust` pattern: add an iteration cap, raise `RuntimeError` cleanly on non-convergence rather than silently looping. Blocker for any future primitive wanting to use stableswappy's state solvers for counterfactual state reconstruction at extreme ratios. Not blocking for AssessDepegRisk itself in its current shape — the primitive avoids `get_y`/`get_D` entirely by evaluating the invariant directly in floats — but a clean fix in stableswappy would widen the scope of future invariant-adjacent primitives.

- **balancerpy could ship a fee-free spot accessor.** Currently `BalancerExchange.get_price(base, opp)` applies the SWAP_FEE (0.25%) scale factor, which is correct for trade sizing but wrong for IL analysis. Both `BalancerImpLoss.apply()` and `AnalyzeBalancerPosition.apply()` inline the fee-free formula (`(b_opp / w_opp) / (b_base / w_base)`) to avoid the fee scaling. A fee-free accessor on the exchange class (`get_spot_price(base, opp)` returning the raw invariant ratio, or an `include_fee: bool` flag on `get_price`) would eliminate the inline-computation workaround and make the naming explicit about which price the caller means. Non-blocking — the current inline approach is correct and small — but cleaner API if balancerpy does a future pass.

- **AssessDepegRisk N>2 extension.** v1 is 2-asset only. The closed-form `ε = (x-y)/(x+y)` parameterization used in the derivation is specific to N=2; extending to 3-asset and higher baskets needs a different derivation (likely multi-dimensional ε plus fixed-point on a system of equations, or a different parameterization entirely). Tracked separately because the math is non-trivial and the v1 already answers the stablecoin-pair question that's most common in practice.

- **DetectFeeAnomaly V3 extension.** Blocked on the UniV3Helper fix above. Once the helper honors `lp.fee`, DetectFeeAnomaly's invariant-vs-contract check can be extended to V3 in-range trades (compute theoretical from virtual reserves + stated fee, compare to helper output). Trades that would cross a tick boundary remain out of scope until V3 tick-walking is implemented — that's a larger piece of work tracked with AssessLiquidityDepth.

- **DetectFeeAnomaly Shape B (user-supplied expected fee).** v1 ships Shape A only (invariant-vs-contract consistency; compares against the pool's *stated* fee). Shape B would add an optional `expected_fee_bps` parameter letting the caller supply a ground-truth fee expectation — useful for auditing a pool against a specification rather than against its own reported parameters. Non-blocking since Shape A catches the broader class of anomalies; worth adding if a real user asks for it.

- **Balancer/Stableswap extensions to CalculateSlippage + CompareProtocols.** `CalculateSlippage` is V2/V3-only; `CompareProtocols` accepts Balancer and Stableswap candidates but degrades slippage fields to `None` for those protocols in v1. Sibling slippage primitives (`CalculateBalancerSlippage`, `CalculateStableswapSlippage`) or a protocol-dispatching CalculateSlippage would close this gap. Low-risk, moderate-effort — the math is available in each sibling repo's get_amount_out paths. Unblocks full cross-protocol slippage plumbing in CompareProtocols.

- **SimulatePriceMove sibling primitives for Balancer and Stableswap.** Same pattern as AnalyzeBalancerPosition / AnalyzeStableswapPosition — compose BalancerImpLoss / StableswapImpLoss with an explicit alpha override. No new math required; ~30 min each. Fills out "every Q2.1/Q5.1/Q5.2 question answerable on every protocol" which is a real completeness bar.

- **FindBreakEven sibling primitives for Balancer and Stableswap.** Genuine new math: Balancer's break-even α inverts `α^w + (1-w)·α^(w-1) - 1 = -fee_ratio`; stableswap's inverts via the ε↔δ fixed point. Half-day each, not copy-paste. Tracked as Bucket B in the Next Phase section above.

- **N-asset extension of BalancerImpLoss, StableswapImpLoss, and their AnalyzePosition siblings.** All four are 2-asset in v1 (inherited from the underlying IL classes). N>2 requires different parameterization and reopens derivation work. Non-blocking for common pairs but worth flagging for Balancer weighted baskets and 3Pool-style stableswaps.

- **uniswappy `SolveDeltas` hardening**: the current `fsolve`-based implementation in `uniswappy/python/prod/analytics/simulate/SolveDeltas.py` can silently fail under high-volatility price spikes — returning a bad `(Δx, Δy)` without raising, corrupting downstream simulation state. The system is formulated as two coupled equations in linear space; in log space the multiplicative constraint `|Δy|/|Δx| = p` linearizes to `ln|Δy| − ln|Δx| = ln p`, which collapses the effective dimensionality to 1 and yields a closed-form V2 solution: `u = |p·x − y| / (2p)`, `v = p·u`, with sign determined by `sign(Δp)`.

  **Partial implementation in place**: `uniswappy/python/prod/analytics/simulate/SolveDeltasRobust.py` was written this session. Same constructor/calc signature as `SolveDeltas` (drop-in), uses closed-form V2 seed in log space, analytical Jacobian passed to `fsolve` via `fprime`, raises `RuntimeError` on non-convergence (no more silent failures). Exported from the package. **Awaits empirical validation**:
  1. Side-by-side numerical comparison with `SolveDeltas` on calm inputs (expect agreement to ~1e-6)
  2. Spike test — confirm robust version handles the specific high-vol inputs where the original silently fails
  3. V3 sim notebook substitution — trajectories should match in normal regimes
  4. Feasibility edge — confirm `ValueError` fires cleanly when target price requires draining the pool

  Once validated, decide: promote to default, or keep both and deprecate the old one. V3 tick-crossing remains an open question — the robust version operates on virtual reserves same as the original, which Ian has validated empirically for the simulation regimes he runs; whether it correctly handles true tick-crossing is not verified.

## Session Notes

### Session 2026-04-18: 1.2.0 foundation + 6 primitives

Long multi-primitive session. Key architectural shifts captured:

- Dep hygiene pass: dropped ghost `web3` and `requests` from install_requires; introduced `[book]` and `[anvil]` extras; agent imports guarded with broad ImportError catch.
- Primitives scaffold: conftest fixtures, authoring checklist, 1 pre-existing primitive (AnalyzePosition, had latent V3 bug fixed this session) + 5 new primitives.
- SolveDeltas log-reformulation derivation + partial implementation (SolveDeltasRobust). Genuine mathematical contribution to uniswappy, not just refactor.
- Architectural framings clarified in session:
  - LPQuote as the nucleus (user's framing via Grok)
  - DeFiMind as an operator of DeFiPy's exact-math tooling, not a calculator itself
  - AnchorRegistry anchors belong at the session/insight level, not per-primitive (unit economics)
  - "Scipy of DeFi for human analysts" → "exact-math infrastructure for AI operators" — user's stated vision shift during the session

### Session 2026-04-21: primitive #7 (DetectRugSignals)

Single-primitive session, "DeFiPy Upgrade part 2." Continued from the part-1 sign-off which left 6 primitives and 136 tests on disk plus an uncommitted working branch.

- **Shipped**: DetectRugSignals (pool_health/, 23 tests). Composes over CheckPoolHealth. Three signals: TVL floor, LP concentration, inactive-with-liquidity. Count-based risk bucketing (0→low, 1→medium, 2→high, 3→critical). `pool_health` carried on the report so callers who got a warning don't need to re-fetch.
- **Design reversed mid-session**: an originally-proposed fourth signal (`reserve_ratio_extreme`) was dropped when walking through the math showed that contribution-skew is always equal by construction under constant product, so the signal could never fire on a valid V2 pool. Dropped cleanly; dataclass reshaped to 3 signals. The alternative framing (raw token-scale ratio) would flag exotic-value pairs rather than rugs — not earning its place in v1.
- **Bug caught by test suite**: `>=` comparator on concentration threshold meant `threshold=1.0` still fired at 100% ownership. Fixed to strict `>`, which gives callers "pass 1.0 to disable" as a clean escape hatch. Reinforced the "step through ceiling-case before writing comparator" heuristic now in the decision heuristics list above.
- **Meta-observation on session rhythm**: two times in this session (reserve-skew signal, `>=` comparator), I wrote code before doing the step-by-step derivation needed to catch an edge case. The first was caught at design-review time by explicit reasoning; the second slipped through to the test suite. The pattern is the same one session 2026-04-18 named as "Mode A costs more tokens than it saves" — even for pure-composition primitives, edge cases deserve worked-out examples before writing the comparison operator.
- **State at close**: 159 tests passing. Docs updated and committed.

### Session 2026-04-22: primitives #8, #9, and #10 (AggregatePortfolio, AssessDepegRisk, DetectFeeAnomaly)

Three-primitive session. The longest single session to date, and the most architecturally informative. Continued from session 2026-04-21.

**Primitive #8 — AggregatePortfolio** (portfolio/, 21 tests). First primitive in a new `portfolio/` category. Breadth-chains AnalyzePosition across N input positions; returns uniform-numeraire totals, per-position summaries in input order, a worst-first PnL ranking, and shared-token exposure warnings. New result dataclasses: `PortfolioPosition` (input container), `PortfolioAnalysis` (result), `PositionSummary` (nested).

- Three spec-level name choices deliberated and refactored before writing: `correlation_warnings` → `shared_exposure_warnings` (the field is token overlap, not ρ); `exit_priority` → `pnl_ranking` (the primitive ranks, doesn't verdict); dataclass input type introduced (`PortfolioPosition`) rather than raw tuples. All three changes codify the "signal surfacer not verdict generator" stance first established by DetectRugSignals.
- New-category wiring: `primitives/portfolio/__init__.py` created; parent `primitives/__init__.py` extended with `from .portfolio import *`; data `__init__.py` gained three new exports.
- Multi-pool fixture deliberately deferred; tests build additional V2 pools inline (`_build_eth_usdc_lp`, `_build_btc_dai_lp`).
- Zero mid-session redesigns, zero test-suite-caught bugs. Attributed to explicit up-front design conversation — naming the three decisions, reasoning through each separately, getting user sign-off before writing.

**Primitive #9 — AssessDepegRisk** (risk/, 22 tests). Stableswap depeg-risk quantification, N=2 only, answers Q2.3. The session's most architecturally informative primitive.

- **Initial approach failed through four rounds of local fixes.** First attempt: drive stableswappy's integer-math Newton solver (`get_y`) to a target dydx state by bisecting on balance multipliers, then read the depegged balances out. Round 1 surfaced a modeling error (used `calc_withdraw_one_coin` as LP value — a single-asset-exit computation, not a pro-rata claim). Round 2 surfaced a unit-conversion error in the balance → human conversion (multiplying through `rates` twice, collapsing USDC balances to zero via integer floor division and producing a ~10⁴× IL error). Round 3 surfaced a reachability assumption — at A=200 the target was physically unreachable, and the test's "stableswap IL < V2 IL at small depeg" assertion was itself wrong-premise (stableswap at high A has *larger* |IL| than V2 at the same δ; strong negative convexity, per Cintra & Holloway 2023). Round 4 would have been another local patch, but the user pushed on the approach itself.
- **The pivot: Option B (analytical invariant evaluation)**. Instead of driving stableswappy's solver to a counterfactual state, derive ε(δ, A) directly from the stableswap invariant and compute IL in pure floats. The derivation: parameterize by ε = (x−y)/(x+y), expand the invariant to get u = S/D − 1 = ε²/[(4A+2)(1−ε²)], expand dydx to get δ ≈ 2ε/(α+1+ε) with α = A(1−ε²)², invert for ε given δ via fixed-point iteration (converges in ~5 iterations), compute IL = (v_LP − v_hold)/v_hold from closed-form v_LP = S·(1−δ(1+ε)/2) and v_hold = D·(1−δ/2). Written out on paper first; implementation was ~200 lines and shipped green on the first attempt.
- **Reachability as a first-class output**. At high A, many depeg targets are physically unreachable (require |ε|>1). The primitive flags these explicitly — scenarios with `il_pct = None`, `lp_value_at_depeg = None`, etc. The V2 benchmark stays populated even in unreachable scenarios.
- **Architectural insight: invariant-math primitives vs. state-threading primitives**. The pivot from Option A to Option B is not just "different implementation" — it's a different answer to "what's this primitive's relationship to the protocol library?" State-threading primitives drive the library to a hypothetical state; invariant-math primitives use the library only as a metadata adapter (A, N, balances, LP supply) and perform the core math directly. For counterfactual questions at the edges of a library's operating envelope, invariant-math is usually cleaner. Codified as PRIMITIVE_AUTHORING_CHECKLIST.md §10 and as decision heuristic #9 above.
- **Three-rounds-then-rethink rule**. The lesson generalizes: if a primitive has required three rounds of local fixes, the fourth is almost never the right move. Stop, reconsider approach, propose alternative explicitly, get sign-off before reimplementing. Codified as PRIMITIVE_AUTHORING_CHECKLIST.md §9 and as decision heuristic #8 above.
- **Independent-oracle test pattern**. `_reference_il(A, delta)` in the test file implements the same derivation in separate code from the primitive's implementation. A single cross-check test validates both simultaneously — if either has a derivation bug, it surfaces. Applicable to any invariant-math primitive.
- **Innovation framing, per user conversation**. The math itself is inherited from academic work on stableswap (Cintra & Holloway 2023, the arxiv "General Framework for IL in AMMs" paper, and the Curve whitepaper). What's new is the *packaging*: composable primitive with stateless construction, typed dataclass output, explicit reachability semantics, and the adapter-vs-math separation that makes it equally usable by a quant in a notebook or an LLM as a tool call. The architectural distinction between state-threading and invariant-math primitives — surfaced by this primitive's shape — is itself worth naming, because it guides future primitive design.

**Primitive #10 — DetectFeeAnomaly** (pool_health/, 20 tests). V2 fee-anomaly detector. Warm-down primitive after the long AssessDepegRisk arc; shipped clean on a single pass thanks to explicit up-front design conversation.

- **Shape A only, not Shape B**. Explicit design decision: v1 compares pool actual output against invariant-predicted output at the pool's *own* stated fee (internal consistency check). Shape B (user-supplied expected fee) is deferrable. Shape A catches a richer class of anomalies (skim wrappers, admin-fee quirks, implementation bugs, rounding) without requiring caller knowledge of the "correct" fee.
- **V2-only scope, hard-earned during implementation**. Reading `UniV3Helper.quote` mid-implementation revealed that the V3 non-mutating quote helper hard-codes `fee = 997` regardless of `lp.fee`. That means it diverges from actual V3 swap output at any non-30-bps fee tier — itself a fee anomaly in the tooling. Rather than invent a workaround in DetectFeeAnomaly, the primitive ships V2-only with a clear ValueError on V3 and the UniV3Helper issue goes to the cleanup backlog. Pattern codified as decision heuristic #10: when dependency tooling reveals a limitation mid-implementation, scope the primitive narrower and document the gap, don't paper over.
- **Direction classification: descriptive, not accusatory**. The `direction` field takes `"pool_underdelivers"` / `"pool_overdelivers"` — pure signed-discrepancy labels. Earlier design iteration considered `"pool_skimming"` which overreaches into attributing motive; underdelivery can come from skim, bug, admin fee, or rounding, and the primitive shouldn't prejudge. Consistent with the "signal surfacer" convention running through DetectRugSignals / AggregatePortfolio / AssessDepegRisk.
- **Both directions surfaced equally**. Unlike typical fee-anomaly tooling that flags only underdelivery, v1 reports overdelivery with equal clarity. Overdelivery is diagnostically important — subsidies, fee-routing, bugs in trader's favor, reward wrappers. An LLM doing forensic pool analysis should see both.
- **Default test_amount: 1% of input reserve**. Small enough not to move the pool appreciably, large enough that float-vs-integer rounding noise stays well below the 10-bps default threshold. Typical clean-pool discrepancy in testing is ~1e-8 bps — ample headroom.

- **State at close**: 225 tests passing. All three doc files (PROJECT_CONTEXT, PRIMITIVE_AUTHORING_CHECKLIST, DEFIMIND_TIER1_QUESTIONS) updated to reflect #8, #9, and #10 ships plus the invariant-math architectural pattern, the three-rounds-then-rethink rule, the V2-vs-V3 fee asymmetry, and the new UniV3Helper backlog item.

### Session 2026-04-23: primitive #11 (CompareFeeTiers)

Single-primitive session. Opened new `comparison/` category, shipped the first V3-only breadth-chain primitive, and corrected an earlier misread about V3 fee accounting.

**Primitive #11 — CompareFeeTiers** (comparison/, 21 tests). Compares N V3 pools at different fee tiers for the same token pair. Breadth-chains `CheckPoolHealth` + `CheckTickRangeStatus` across inputs; reports per-tier metrics (fee_tier_bps, pool_tvl_in_token0, observed_fee_yield, in_range, range_width_pct) plus independent orderings by observed yield and by TVL. New result dataclasses: `FeeTierCandidate` (input container), `FeeTierMetrics` (per-tier, nested), `FeeTierComparison` (result).

- **Mode B execution was clean and fast.** Read `UniswapV3Exchange.__init__` (to confirm `self.fee` storage in pips), `UniV3Helper.quote` (to confirm the backlogged hard-coded-997 issue is orthogonal — we don't need the helper for this primitive), `CheckPoolHealth.apply()` (to confirm V3's fee accounting path), and the AggregatePortfolio test file (to lift the inline pool-building pattern). Zero mid-implementation surprises. Validates the rule: a full dependency-read pass before designing saves more time than it costs.
- **Spec-level deviations accepted up-front.** The DEFIMIND_TIER1_QUESTIONS spec proposed `fee_income_estimate`, `net_return`, and `optimal_tier: int`. All three were dropped: the first two require a forward volume model the primitive can't honestly ground (the pool object has no volume projection); the third is a verdict field, inconsistent with the signal-surfacer convention. Replaced with `observed_fee_yield` (cumulative fees / TVL in token0 — a rate, not a forecast) and two independent rankings. User signed off on all three deviations before code.
- **`observed_fee_apr` → `observed_fee_yield` mid-implementation.** Caught during the dataclass write: the pool object carries no real-world duration, so an "APR" figure requires a caller-supplied age and would either be dishonest (guessing at age) or always-None (when age is unsupplied). Cumulative yield is honest and composes cleanly — callers who know pool age annualize themselves. This is the kind of naming tightening heuristic #6 is about; I made the call and continued without pinging for approval because it was a strict honesty improvement, not a shape change.
- **Correction to an earlier convention note.** PROJECT_CONTEXT previously described V3 `collected_fee*` as lazily derived via `_update_fees()`. The CompareFeeTiers test `test_none_yield_pools_sort_last` drives a single swap through `Swap().apply()` and asserts the active pool ranks ahead of the quiet one by observed yield — this passed on the first run, which means `collected_fee0` DOES update synchronously during the swap path. The Key Internal Conventions section was updated to reflect this: V3 has the running accumulator available at all times, it just doesn't have per-swap history (`fee0_arr`). Point-in-time fee totals are V2+V3; rate/window metrics are V2-only. This distinction matters for future primitive design — any primitive needing cumulative-fees-since-deployment works on both protocols.
- **Notes-as-informational, not-warnings.** The `notes: list[str]` field on FeeTierComparison explicitly calls out conditions a caller might overlook (no accumulated fees → yield is None; candidate out of range) but does NOT duplicate information directly visible on the per-tier metrics dataclass. This is the right boundary for a breadth-chain composition: notes surface conditions that affect interpretation of the rankings without editorializing the rankings themselves.
- **Inline-helper pattern continues to scale.** `_build_v3_pool_at_fee(fee_pips, address_suffix)` builds an arbitrary-tier V3 pool with fresh ERC20 tokens, factory, and Join(). Supports up to 4 pools in a single test (canonical tier extraction test exercises 100/500/3000/10000 pips simultaneously). Shared multi-pool fixture remains deferred — AggregatePortfolio and CompareFeeTiers are the only two multi-pool consumers to date, both use inline helpers successfully, and the shape a shared fixture would need depends heavily on what CompareProtocols eventually looks like.
- **Zero mid-session redesigns, zero test-caught bugs, 21 tests passing on first run.** Attributed to the (by-now-ritualized) up-front design conversation — Shape A vs B vs C settled with user sign-off, three spec-level deviations reviewed before code, dataclass field names argued through in prose before the first keystroke. This is what sessions are supposed to look like when heuristic #7 is followed.

- **State at close**: 246 tests passing. All three doc files updated. CompareFeeTiers moves from P3 remaining to shipped; P3 now holds only CompareProtocols.

Next session should pick primitive #12 from the candidates above. `OptimalDepositSplit` (V2-only) remains the strongest lean — opens optimization/, uses a known closed form, unblocks EvaluateRebalance downstream.

### Session 2026-04-23 (part 2): primitive #12 (OptimalDepositSplit)

Second primitive of the day. Shipped the V2 zap-in optimizer as a non-mutating projection of SwapDeposit, and closed a small intuition bug by forcing a derivation.

**Primitive #12 — OptimalDepositSplit** (optimization/, 19 tests). Non-mutating V2 primitive. Given `amount_in` tokens of a single side, returns the optimal swap fraction α such that post-swap reserves match the (1-α)·amount_in remainder, leaving zero deposit dust. Pure read — projects what `SwapDeposit().apply()` would do without executing it. New dataclass: `DepositSplitResult` (10 fields covering split, balances, expected LP tokens, and swap-leg slippage). Opens the `optimization/` category.

- **Mode B read before design.** Reading `SwapDeposit._calc_univ2_deposit_portion` confirmed the quadratic is factored out and read-only; it just solves for α given pool state. That made OptimalDepositSplit a pure composition primitive — the V2 zap-in math is inherited intact via a single helper call, and the rest is surrounding bookkeeping (spot price, post-swap reserves, LP-token mint formula, slippage denomination).
- **Private-method import, tracked risk.** OptimalDepositSplit calls `SwapDeposit()._calc_univ2_deposit_portion(...)` — leading-underscore convention but not actually name-mangled. Works today; a future uniswappy refactor could break it. Not blocking. The sibling Key Internal Conventions entry now documents the pattern and suggests a future uniswappy API promotion (`_calc_univ2_deposit_portion` → `calc_univ2_deposit_portion`).
- **The direction-of-α bug I shipped in my own head.** Initial test assertions expected α > 0.5 for large deposits ("swap moves price, so you need to swap more to match what's left"). Two tests failed on first run — α = 0.4779 at 200/1000 reserves, not above 0.5. I stopped and worked out the V2 zap-in quadratic from scratch: f·α²·dx + r·α·(1+f) − r = 0 with f = 0.997. Taking the dx→0 limit via L'Hôpital gives α → 1/(1+f) ≈ 0.50075 (slight upward bias from fee asymmetry). Implicit differentiation gives dα/d(dx) = −α²f / [2αf·dx + r(1+f)] < 0 identically. So α starts just above 0.5, decreases monotonically with size. Correct intuition: a larger swap moves the price more, so each unit swapped buys LESS, so you need to swap LESS. This was a textbook case of heuristic #5 ("step through threshold edge cases before writing the comparator") extended to direction-of-change assertions. The failure did its job: forced the derivation, which is now captured both in the docstring and as a new Key Internal Conventions entry so the mistake is caught if any future primitive (especially EvaluateRebalance, which depends on OptimalDepositSplit) repeats the bad intuition.
- **Test plan added a direct monotonicity check in response.** The fix was more than flipping an inequality: I added `test_alpha_monotone_decreasing_in_amount_in` that checks α is strictly decreasing across [0.1, 10, 50, 200]. That's a much stronger assertion than picking a single threshold and asserting which side of it α sits — it directly tests the dα/d(dx) < 0 property. Future primitives reasoning about V2 mechanics should prefer this shape of test over single-threshold assertions.
- **Consistency cross-check worked.** The critical test builds two identical pools, calls OptimalDepositSplit on one and SwapDeposit on the other, and verifies the projected `expected_lp_tokens` matches the actual LP minting within 0.1%. Passed on the first run at the set tolerance. The projection primitive really does describe what the execution primitive will do, which is the whole point of a non-mutating-projection shape.
- **Estimated 45 min, actual ~60 min** including the derivation pause. The derivation-on-failure loop is a net win — the original time estimate assumed intuition was right; when it wasn't, 15 minutes of paper-math recovery is cheaper than shipping a primitive whose docstring lies about its own behavior.
- **19 tests across 7 classes** (Shape, Small-deposit, Large-deposit, Monotonicity, LP tokens, Consistency, Symmetry, Validation). One of the Consistency tests asserts non-mutation explicitly — checks that lp.reserve0, lp.reserve1, lp.total_supply, and lp.liquidity_providers[USER] are all unchanged after `.apply()`. Pattern worth continuing for any future projection primitive.

- **State at close**: 269 tests passing. All three doc files updated with #12 ship, new conventions entries (V2 zap-in α direction; non-mutating primitives over process-layer helpers), and updated next-session candidates.

Next session should pick primitive #13. `EvaluateRebalance` is now unlocked — OptimalDepositSplit was its last hard dependency — and is the biggest-value remaining primitive. Design conversation needed up front: single candidate vs. N candidates, verdict field vs. metrics-only.

### Session 2026-04-23 (part 3): cross-protocol position analyzers + portfolio dispatch

Audit-and-extend session following the BalancerImpLoss / StableswapImpLoss / AssessDepegRisk-refactor / CompareProtocols arc (Phases 1–3 of earlier work in this day). Continued from 2026-04-23 part 2 which closed at 17 Tier 1 primitives + CompareProtocols shipped.

**Audit phase.** Reviewed all 17 existing primitives for cross-protocol extension opportunities now that BalancerImpLoss and StableswapImpLoss live in their natural sibling-repo homes. Five candidates identified: AnalyzePosition (highest value), SimulatePriceMove, FindBreakEvenPrice, FindBreakEvenTime (transitively via AnalyzePosition), AggregatePortfolio. Non-candidates: EvaluateRebalance / OptimalDepositSplit / EvaluateTickRanges / CheckTickRangeStatus (V2- or V3-specific by design), pool_health and comparison primitives (no IL math to extend).

**Path A selected** — ship sibling primitives with their own dataclasses, extend AggregatePortfolio for cross-protocol dispatch, skip SimulatePriceMove and FindBreakEvenPrice extensions for now (tracked as Bucket A / Bucket B in Next Phase). Key decision rejected: "add isinstance dispatch to AnalyzePosition" — would have made that primitive branchy and conflated result shapes.

**Three primitives shipped:**

- **AnalyzeBalancerPosition** (position/, 22 tests). 2-asset weighted-pool PnL decomposition. Composes BalancerImpLoss. Returns BalancerPositionAnalysis with base_weight surfaced as the Balancer-distinguishing field. Fee-free spot computed inline (not via `lp.get_price` which bakes in SWAP_FEE scale). fee_income = 0 in v1 (no per-LP attribution in Balancer pool objects). diagnosis narrows to two buckets (net_positive / il_dominant) rather than AnalyzePosition's three, pending fee attribution.

- **AnalyzeStableswapPosition** (position/, 21 tests). 2-asset stableswap analyzer. Three diagnostic paths: at_peg (balanced pool short-circuit via `abs(dydx - 1.0) < 1e-12`), reachable off-peg, and unreachable-alpha (Optional fields set to None, matching AssessDepegRisk / CompareProtocols convention). Uses `lp.math_pool.dydx(0, 1, use_fee=False)` for live alpha. per_token_init and per_token_current surfaced for N-asset readability (even at N=2). Numeraire is peg (1:1 across tokens).

- **AggregatePortfolio cross-protocol extension.** isinstance-based protocol detection → routes to appropriate analyzer → extracts common scalars (net_pnl, il_percentage, fee_income) for breadth-chain aggregation. Numeraire rule generalized from `lp.token0` to "first token in pool's insertion order" — V2/V3 still use `lp.token0`; Balancer/Stableswap use `list(lp.tkn_reserves.keys())[0]`. Mixed portfolios must share first-token symbol. Stableswap unreachable positions contribute 0 and get flagged in shared_exposure_warnings. New field on PositionSummary: `protocol: str` ∈ {uniswap_v2, uniswap_v3, balancer, stableswap}.

**Dataclass additions:** BalancerPositionAnalysis (12 fields), StableswapPositionAnalysis (13 fields with 4 Optional for unreachable regime). PortfolioPosition grew `entry_amounts: Optional[List[float]]` for the stableswap path; `entry_x_amt`/`entry_y_amt` became Optional. PositionSummary gained required `protocol` field; `analysis` retyped to Any (was PositionAnalysis) to avoid union imports.

**Conftest additions:** `balancer_setup` (50/50 ETH/DAI, 100 pool shares), `weighted_balancer_setup` factory, `stableswap_setup` (USDC/DAI at A=10, balanced), `amplified_stableswap_setup` factory. Two new setup dataclasses (BalancerSetup, StableswapSetup).

**Test coverage:** 22 Balancer (Shape, AtEntry, PostSwap, Weighting, RealAPR, Validation), 21 Stableswap (Shape, AtPeg, OffPeg, A-dependence, RealAPR, Validation), 13 new cross-protocol AggregatePortfolio tests (V2+Balancer, V2+V3+Balancer, mixed-first-token rejection, Stableswap-alone, Stableswap+V2 USDC).

**Key architectural insights captured:**
- Sibling primitives over branchy dispatch (codified as decision heuristic #12 above, PRIMITIVE_AUTHORING_CHECKLIST.md §11).
- Composition-layer dispatch scales; primitive-layer dispatch doesn't (decision heuristic #13).
- Balancer fee-free spot bypass trap (Key Internal Conventions).
- Stableswap dydx returns exactly 1.0 at balance, confirmed via source read — safe at-peg short-circuit condition.
- Balancer SWAP_FEE is 0.25% not 0.3% — documented to avoid confusion.

**459 tests passing on first run.** The Balancer 80/20-vs-50/50 weight-dependence test (flagged as highest-risk assertion in pre-run review) passed without adjustment. Zero mid-session redesigns, zero test-caught bugs. Attributed to the Mode-B source reads up front (BalancerExchange, StableswapPoolMath, sibling conftest patterns) and to explicit up-front design conversation on Path A vs. branchy dispatch.

**State at close:** 459 tests passing. 20 primitives shipped (17 Tier 1 + 3 cross-protocol siblings). Docs updated.

## MCP Setup (for Claude.ai sessions)

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "defipy-filesystem": {
      "command": "/opt/homebrew/bin/node",
      "args": [
        "/opt/homebrew/lib/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js",
        "/Users/ian_moore/repos/defipy",
        "/Users/ian_moore/repos/uniswappy",
        "/Users/ian_moore/repos/balancerpy",
        "/Users/ian_moore/repos/stableswappy",
        "/Users/ian_moore/repos/web3scout",
        "/Users/ian_moore/repos/defipy-book"
      ]
    }
  }
}
```

Restart Claude.ai after editing.

---

*This document orients a fresh Claude session on DeFiPy's architecture as of the 1.2.0 working branch. For mechanical primitive-authoring steps, see `doc/execution/PRIMITIVE_AUTHORING_CHECKLIST.md`. For the full primitive catalog and LP-question mapping, see `doc/execution/DEFIMIND_TIER1_QUESTIONS.md`.*
