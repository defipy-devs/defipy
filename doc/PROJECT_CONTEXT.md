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

### Multi-Protocol Support
- **uniswappy**: Uniswap V2 / V3 implementations
- **balancerpy**: Balancer weighted pools
- **stableswappy**: Curve-style stableswap math
- **web3scout** (optional, via `[book]` extra): onchain event monitoring for agents

### Primitives Layer (current focus)

Each primitive follows the DeFiPy contract: stateless construction, computation at `.apply()`, structured dataclass return.

**Eight primitives shipped as of the 1.2.0 working branch:**

| Primitive | Category | Answers | Tests |
|---|---|---|---|
| `AnalyzePosition` | position/ | Q1.1–Q1.4 (PnL decomposition) | 17 |
| `SimulatePriceMove` | position/ | Q2.1, Q5.1, Q5.2 (price-move scenarios) | 21 |
| `CalculateSlippage` | execution/ | Q8.1, Q8.2, Q9.2 (trade slippage + max-size) | 20 |
| `CheckTickRangeStatus` | risk/ | Q2.4 (V3 range proximity) | 16 |
| `FindBreakEvenPrice` | position/ | Q3.1–Q3.3 (break-even pricing, both alphas) | 23 |
| `CheckPoolHealth` | pool_health/ | Q4.1–Q4.3, Q7.1 (pool-level health snapshot) | 24 |
| `DetectRugSignals` | pool_health/ | Q7.4 (threshold-based rug signals) | 23 |
| `AggregatePortfolio` | portfolio/ | Q6.1–Q6.3 (N-position aggregation + shared-exposure) | 21 |

Full suite: **181 tests passing** (primitives + fixture smoke tests). The full 19-primitive inventory and LP-question mapping lives in `doc/execution/DEFIMIND_TIER1_QUESTIONS.md`. Authoring conventions (file layout, style, test coverage, `__init__.py` wiring) are in `doc/execution/PRIMITIVE_AUTHORING_CHECKLIST.md`.

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

- **Numeraire convention: token0.** All position values, fees, and TVL figures are expressed in token0 units unless explicitly stated. Callers can re-denominate as needed. Enforced across AnalyzePosition, SimulatePriceMove, FindBreakEvenPrice, CheckPoolHealth, DetectRugSignals, AggregatePortfolio.

- **Uniform-numeraire as a v1 design stance for multi-position primitives.** AggregatePortfolio requires all input positions to share a common token0 and raises `ValueError` on mismatch rather than silently summing across incompatible units. The error message explicitly directs the user to group by token0 and call multiple times. This is the v1 scope; a multi-numeraire version can come later if the cross-numeraire case turns out to be common. The same stance will likely apply to future comparison primitives (CompareProtocols, CompareFeeTiers) — define scope by rejecting shape mismatches rather than papering over them.

- **V2 has per-swap fee history (`fee0_arr`, `fee1_arr`); V3 does not.** V3 accumulates `feeGrowthGlobal0X128` / `feeGrowthGlobal1X128` and derives `collected_fee*` lazily via `_update_fees()`. Primitives that rely on swap history (e.g., `CheckPoolHealth.fee_accrual_rate_recent`, `DetectRugSignals.inactive_with_liquidity`) return `None` / `False` for V3 and document why.

- **V2 `liquidity_providers` has a `"0"` sentinel** for the `MINIMUM_LIQUIDITY` burn at first mint. Exclude it from LP counting and concentration metrics.

- **V3 sign convention in `CheckTickRangeStatus`**: `pct_to_lower` and `pct_to_upper` are positive when in-range, negative when the corresponding bound has been crossed.

- **Closed forms over solvers, when available.** FindBreakEvenPrice and SimulatePriceMove both collapse to exact closed-form solutions after correct formulation (see the SolveDeltasRobust entry in the backlog for the same pattern applied to pool rebalancing). Default to finding the closed form before reaching for `scipy.optimize.fsolve`.

- **Threshold comparators deserve edge-case thought.** `DetectRugSignals` uses strict `>` on concentration (so passing `1.0` means "never fire") and `<=` on the TVL floor (so the floor reads as "minimum acceptable"). Two signals, two comparators, picked per signal's intuitive meaning rather than forced into a single rule. The `>= with threshold=1.0` bug caught during shipping reinforced: step through the ceiling-case of every threshold before writing the comparator.

- **Composition primitives should read only their dependency's output.** `DetectRugSignals` calls `CheckPoolHealth` and operates purely on the returned `PoolHealth` — no direct `lp.*` access. If a signal can't be expressed from the dependency's output, it belongs on a different primitive (or the dependency needs extending). Keeps the "primitives chain into primitives" claim honest.

- **Two chaining shapes: depth and breadth.** DetectRugSignals demonstrates *depth* chaining — one primitive composed over another. AggregatePortfolio demonstrates *breadth* chaining — the same primitive applied N times, results aggregated. Both are legitimate composition patterns; future primitives should pick the shape that fits the question, not default to one. Depth-chains work for threshold-over-metric patterns (DetectRugSignals, DetectFeeAnomaly). Breadth-chains work for "summarize across a set" patterns (AggregatePortfolio, eventually CompareProtocols, CompareFeeTiers). The full `EvaluateRebalance` when shipped will combine both — depth-chain several per-position primitives, then use breadth-chain logic to rank candidates.

- **Signal surfacer, not verdict generator.** Established by DetectRugSignals, continued by AggregatePortfolio's `pnl_ranking` (not "exit_priority" as the spec had it) and its `shared_exposure_warnings` (not "correlation"). Primitives expose the numbers and the orderings; the verdict — "you should exit this" or "these positions are correlated risks" — belongs to the caller. Fields named for verdicts overpromise what the math actually delivers.

- **One dataclass per file is a guideline, not a rule.** `PositionSummary` lives in `PortfolioAnalysis.py` because it's a structural component of `PortfolioAnalysis` rather than a standalone result. Nested component types can colocate with their parent; top-level primitive results get their own file.

## Testing

Shared fixtures in `python/test/primitives/conftest.py`:
- `v2_setup` — 1000 ETH / 100000 DAI V2 LP, USER owns 100%
- `v3_setup` — same reserves, full-range V3, tick_spacing=60, fee=3000

Both return a dataclass with `.lp`, `.eth`, `.dai`, `.lp_init_amt`, `.entry_x_amt`, `.entry_y_amt` (V3 adds `.lwr_tick`, `.upr_tick`).

Note: the fixture's 100% ownership is deliberately stressful — it exposed the `RebaseIndexToken` V3 divide-by-zero bug during SimulatePriceMove development. New primitives that use V3 codepaths should run against this fixture specifically to catch similar issues.

**Multi-pool fixtures deferred by design.** AggregatePortfolio's tests construct additional pools inline (`_build_eth_usdc_lp`, `_build_btc_dai_lp`) rather than via a shared fixture. The reasoning: the natural shape of a multi-pool fixture (uniform-ETH portfolio vs. uniform-stable portfolio vs. mixed protocols vs. mixed fee tiers) depends on what the next multi-pool primitive needs, which we don't know until we reach CompareProtocols or CompareFeeTiers. Better to design the shared fixture against two concrete consumers than one.

```bash
# Full primitive suite
pytest python/test/primitives/ -v

# Release gate across all sibling packages (clean venv)
./resources/run_clean_test_suite.sh --with-defipy
```

**Working-branch state: 181 tests passing.**

## Usage Patterns

```python
from defipy import (
    AnalyzePosition,
    SimulatePriceMove,
    CalculateSlippage,
    CheckTickRangeStatus,
    FindBreakEvenPrice,
    CheckPoolHealth,
    DetectRugSignals,
    AggregatePortfolio,
    PortfolioPosition,
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

# Portfolio aggregation (breadth-chain over AnalyzePosition)
portfolio = AggregatePortfolio().apply([
    PortfolioPosition(lp = lp_a, lp_init_amt = amt_a,
                      entry_x_amt = 1000, entry_y_amt = 100000),
    PortfolioPosition(lp = lp_b, lp_init_amt = amt_b,
                      entry_x_amt = 500, entry_y_amt = 1_000_000),
])
# → PortfolioAnalysis(numeraire, total_value, total_hold_value,
#                    total_fees, total_net_pnl, positions (in input order),
#                    pnl_ranking (worst-first), shared_exposure_warnings)
```

## Next Phase

### Recommended opener for next session

1. Verify 1.2.0 working-branch state: `pytest python/test/primitives/ -v` should show 181 passing.
2. Pick primitive #9 from the candidate list below.

### Primitive #9 candidates, with reasoning

**Strongest lean: `DetectFeeAnomaly`** (P4, pool_health/).
- Depth-chain pattern, natural pair with DetectRugSignals in the same category
- Answers Q7.3: compares theoretical fee output against actual observed fee accrual. For V2 the fee rate is hard-coded at 0.3%; theoretical vs. observed will catch pools with off-spec fee behavior or skimming contracts
- Small, self-contained, low-risk after two depth-chain primitives have shown the pattern works
- Design decisions mainly live in: how do we get "actual" observed fees from the pool state, and what's the tolerance band for flagging divergence
- Estimated ~45 min

**Second choice: `OptimalDepositSplit` V2-only** (P2, optimization/).
- V2 has a clean closed form (the Uniswap V2 zap-in quadratic); ships a new category (optimization/) and new primitive shape (returns optimal parameters rather than metrics)
- V3 is the open question — either raise cleanly with a helpful message, or tick-walk the harder math. V2-only with V3-rejection is a defensible v1 scope following the CalculateSlippage precedent
- Shortens the road to the full `EvaluateRebalance` when it eventually ships
- Estimated ~45 min V2-only

**Third choice: `AssessDepegRisk`** (P5, risk/).
- Stableswap-specific primitive that's been deferred entirely. Would be the first primitive to exercise the stableswappy package
- The "needs new reading pass on stableswappy source" is the honest estimate — it's not a small add
- Useful for real users but narrower audience
- Estimated ~90 min including stableswappy reading time

**Deferred (same reasoning as part 1): `EvaluateRebalance` full**, `AssessLiquidityDepth`, `CompareProtocols`, `CompareFeeTiers`.
- `EvaluateRebalance` full needs `WithdrawSwap` / `SwapDeposit` / `OptimalDepositSplit` as dependencies — not there yet
- `AssessLiquidityDepth` needs V3 tick-walking that doesn't exist in the codebase yet; deserves a dedicated session
- `CompareProtocols` and `CompareFeeTiers` both want multi-pool fixtures beyond what's in conftest; the fixture design will be cleaner after we've seen two concrete consumers (currently only AggregatePortfolio)

**Full remaining inventory by priority:**
- **P1 remaining**: `AssessLiquidityDepth`
- **P2 — Optimization**: `OptimalDepositSplit`, `EvaluateRebalance`, `EvaluateTickRanges`
- **P3 — Comparison**: `CompareProtocols`, `CompareFeeTiers`
- **P4 — Safety (remaining)**: `DetectFeeAnomaly`
- **P5 — Advanced**: `FindBreakEvenTime`, `AssessDepegRisk`, `DetectMEV`, `DiscoverPools`

Full LP-question mapping and signatures for all 19 primitives live in `doc/execution/DEFIMIND_TIER1_QUESTIONS.md`. Read that doc for any primitive not covered above before designing — the spec has exact signatures that should not be guessed.

### Decision heuristics for picking the next primitive (general, beyond #9)

1. **Mode B is mandatory.** Read the relevant uniswappy/balancerpy/stableswappy source before proposing a design. Session 2026-04-18 proved Mode A (design-then-discover-API-through-failing-tests) costs more tokens than it saves. Every primitive that skipped this step had at least one revision cycle.
2. **Composition primitives before new-math primitives, when both are available.** They're lower-risk (no new derivations to verify), they demonstrate the architecture's key claim (composability), and they're educational about what the shipped primitives actually expose. Two patterns available: depth-chain (one-into-one) and breadth-chain (one-over-many). Pick whichever fits the question.
3. **V2+V3 parity is the target, but scope honestly.** `CalculateSlippage`'s `max_size_at_1pct` is V2-only with V3 documented as `None`. That's a defensible shape. `FindBreakEvenPrice` is V2+V3 full. `CheckPoolHealth`'s `num_swaps` is V2-only; `DetectRugSignals.inactive_with_liquidity` inherits that V2-only-ness. These are examples of graceful degradation — do the same when a V3 implementation would be either infeasible (tick crossing) or disproportionately expensive.
4. **Fixture stress is a feature.** The `v2_setup` / `v3_setup` at 100% pool ownership is intentionally pathological. It exposed one real bug (`RebaseIndexToken` V3 divide-by-zero) during session 2026-04-18 and forced the DetectRugSignals "top LP at ~100%" test case during session 2026-04-21. Keep new primitives running against this fixture; don't relax it to "make V3 work."
5. **Step through threshold edge cases before writing the comparator.** Session 2026-04-21's DetectRugSignals bug was `>=` vs. `>` at `threshold=1.0`. For any primitive that takes a threshold with a meaningful ceiling or floor, verify the ceiling/floor case explicitly before shipping.
6. **Name fields for information, not verdicts.** `pnl_ranking` not `exit_priority`; `shared_exposure_warnings` not `correlation_warnings`; `signals_detected` not `is_rug`. The primitive exposes numbers and orderings; the judgment belongs to the caller. Spec-level verdict naming is a recurring pattern worth pushing back on during design.
7. **Design decisions up front, written down.** Session 2026-04-21 shipped DetectRugSignals with one mid-session redesign (dropped the reserve-skew signal) and one test-caught bug (the `>=` comparator). Session 2026-04-22 shipped AggregatePortfolio with zero mid-session corrections. The difference: AggregatePortfolio had explicit design-decisions conversation, with the proposed signal set and name choices reviewed before writing code. Reproduce this pattern.

### Later: LLM Reasoning Layer (DeFiMind)

Once the primitive library is substantially complete, add a reasoning layer on top for intent-based LP diagnostics, multi-protocol orchestration, and chained primitive calls as LLM tools. The primitives themselves stay LLM-agnostic.

The composability architecture is the point: LLMs don't get special tool definitions — the primitives **are** the tools, same interface a quant uses in a notebook. This was clarified during session discussion on 2026-04-18 and is the distinguishing feature vs. other agentic DeFi frameworks that wrap LLMs around raw onchain data.

## File Structure Reference

```
python/prod/
├── primitives/              # Analytics primitives (new in 1.2.0)
│   ├── position/            # AnalyzePosition, SimulatePriceMove, FindBreakEvenPrice
│   ├── execution/           # CalculateSlippage
│   ├── risk/                # CheckTickRangeStatus
│   ├── pool_health/         # CheckPoolHealth, DetectRugSignals
│   └── portfolio/           # AggregatePortfolio
├── agents/                  # Legacy — frozen for book chapter 9
├── cpt/quote/               # Core pricing/liquidity (re-exports from uniswappy)
├── cpt/index/               # Mathematical inverse relationships
├── process/                 # AMM operation implementations (V2/V3/Balancer/Stableswap dispatch)
└── utils/data/              # Result dataclasses:
                               PositionAnalysis, PriceMoveScenario, SlippageAnalysis,
                               TickRangeStatus, BreakEvenAlphas, PoolHealth,
                               RugSignalReport, PortfolioPosition,
                               PortfolioAnalysis (+ nested PositionSummary)

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

### Session 2026-04-22: primitive #8 (AggregatePortfolio)

Single-primitive session. Continued from session 2026-04-21.

- **Shipped**: AggregatePortfolio (portfolio/, 21 tests). First primitive in a new `portfolio/` category. Breadth-chains AnalyzePosition across N input positions; returns uniform-numeraire totals, per-position summaries in input order, a worst-first PnL ranking, and shared-token exposure warnings. New result dataclasses: `PortfolioPosition` (input container), `PortfolioAnalysis` (result), `PositionSummary` (nested).
- **Three spec-level name choices deliberated and refactored before writing**: `correlation_warnings` → `shared_exposure_warnings` (the field is token overlap, not ρ); `exit_priority` → `pnl_ranking` (the primitive ranks, doesn't verdict); dataclass input type introduced (`PortfolioPosition`) rather than raw tuples. All three changes codify the "signal surfacer not verdict generator" stance first established by DetectRugSignals.
- **New-category wiring**: `primitives/portfolio/__init__.py` created; parent `primitives/__init__.py` extended with `from .portfolio import *`; data `__init__.py` gained three new exports. Category directory plus test-side mirror created via `filesystem:create_directory`.
- **Multi-pool fixture deliberately deferred**: tests build additional V2 pools inline (`_build_eth_usdc_lp`, `_build_btc_dai_lp`). The reasoning — documented in the Testing section above — is that the right shape of a shared multi-pool fixture depends on what the next multi-pool primitive needs, which we won't know until CompareProtocols or CompareFeeTiers. Extracting the builder prematurely would be designing against a single consumer.
- **Session rhythm, notably clean**: zero mid-session redesigns, zero test-suite-caught bugs. The difference from session 2026-04-21 was the explicit up-front design conversation — naming the three decisions (correlation/exit_priority/uniform-numeraire), reasoning through each separately, getting user sign-off before writing. This pattern worth reproducing for future primitives; documented as decision heuristic #7.
- **Conceptual insight surfaced**: AggregatePortfolio opens a possible "portfolio-level companion" pattern for other primitives. E.g., CompareProtocols-across-portfolio is a legitimate question the current spec doesn't name. Not a 2026 conversation — flagged for later.
- **State at close**: 181 tests passing. Docs updated, ready to commit.

Next session should pick primitive #9 from the candidates above. DetectFeeAnomaly is the strongest lean — same category as DetectRugSignals, depth-chain pattern already proven, small and self-contained.

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
