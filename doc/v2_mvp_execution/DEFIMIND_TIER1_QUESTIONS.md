# DeFiMind — Tier 1 Question Catalog & Primitive Architecture

**Date:** April 16, 2026  
**Purpose:** Complete inventory of LP-facing questions DeFiMind can answer, and the DeFiPy primitives that answer them  
**Status:** Working document — expanding through iterative review

---

## How DeFiMind Works: The State Twin Architecture

DeFiMind's diagnostic capability rests on a single architectural concept: the **State Twin** — a mathematically exact, off-chain replica of on-chain pool state.

Diagnosing a DeFi position requires running calculations that are impossible to perform on-chain: scenario simulation, cross-protocol comparison, historical decomposition, and optimization. You cannot ask a smart contract "what would my IL be if price moved 30%?" You cannot run a Curve stableswap invariant against a Uniswap pool's reserves to compare IL profiles. You cannot rewind a pool to your entry block and replay the math forward. These operations require a local twin of the pool that can be interrogated, mutated, and stress-tested without touching the blockchain.

The State Twin is only useful if the math is exact. An approximate twin gives approximate answers — useless for financial diagnostics where the difference between 3.1% IL and 3.8% IL determines whether a position is net profitable. DeFiPy's hand-derived AMM formulas — constant product with fee integration, concentrated liquidity with sqrt price and tick mechanics, Balancer weighted invariants, and Curve stableswap polynomials — provide the mathematical precision required for the twin to be trustworthy.

### The Diagnostic Loop

```
Web3Scout        →  Captures real on-chain state (reserves, prices, ticks, supply)
     ↓
State Twin       →  Replicates state locally as a DeFiPy exchange object
     ↓
DeFiPy Math      →  Runs diagnostics on the twin (IL, fees, slippage, scenarios)
     ↓
LLM Reasoning    →  Chains primitives, synthesizes answers, explains in plain language
     ↓
AnchorRegistry   →  Proves the analysis happened, immutably and verifiably
```

### Why This Requires Exact Math

Every diagnostic question in this catalog operates on the State Twin, not the chain. The twin is built from DeFiPy's protocol-specific exchange implementations:

- **Uniswap V2:** `UniswapExchange` with constant product invariant `x × y = k`, fee-integrated swap math, and `SaferMath` / `FullMath` precision
- **Uniswap V3:** `UniswapV3Exchange` with concentrated liquidity, `sqrtPriceX96` encoding, tick-range positioning, and virtual reserve computation
- **Balancer:** `BalancerExchange` with weighted invariant `∏(Bᵢ^wᵢ) = k` and weight-adjusted swap math
- **Curve:** `StableswapExchange` with the stableswap polynomial `A·n^n·∑xᵢ + D = A·D·n^n + D^(n+1)/(n^n·∏xᵢ)`

The multi-protocol dispatch layer (`Swap`, `Join`, `AddLiquidity`, `RemoveLiquidity`) routes operations to the correct twin based on exchange type, enabling cross-protocol analysis within a single diagnostic session.

### State Twin vs. Invariant Math

Some primitives don't need a full state twin to answer their question — they need only the invariant that governs valid twin states. Session 2026-04-22 established this distinction concretely with `AssessDepegRisk`: instead of driving stableswappy's state-transition solvers to a counterfactual depegged state, the primitive extracts a handful of scalars (A, N, balances, LP supply) from the twin and evaluates the stableswap invariant directly in pure floats. The twin is still the source of *metadata*; the invariant is the source of *math*.

`DetectFeeAnomaly` is a second, smaller example of the same pattern: V2 pool state provides reserves and token identities (metadata), the constant-product-with-fee formula provides the theoretical output (invariant math), and the pool's own `get_amount_out` provides the actual output — the primitive is a consistency check between the two maths. Neither drives the other.

Future primitives should ask: is this question about a *state* (use the protocol library's state-threading machinery) or about an *invariant* (evaluate the mathematical law directly)? Counterfactual questions at the edges of realistic pool operation — depeg scenarios, extreme-price simulations, out-of-envelope stress tests, fee-math consistency checks — often fall into the latter category. See `PRIMITIVE_AUTHORING_CHECKLIST.md` §10 for the full guidance.

### What the State Twin Enables

- **Position diagnostics** — decompose PnL into IL, fee income, and price impact by replaying the twin from entry state to current state
- **Scenario simulation** — mutate the twin's reserves to model hypothetical price moves, then recalculate all metrics
- **Cross-protocol comparison** — build twins of the same capital across Uniswap, Balancer, and Curve simultaneously, run identical analysis, compare results
- **Optimization** — evaluate multiple tick ranges, deposit splits, or rebalancing strategies against the twin without executing anything on-chain
- **Slippage and depth analysis** — run trades of any size through the twin's invariant curve to compute exact execution price, price impact, and liquidity cliffs

---

## Tier Definition

**Tier 1 — Economic & Mathematical Analysis**  
Questions answerable through DeFiPy's exact AMM formulas, web3scout chain data, and LLM reasoning. This is DeFiMind's core territory. Every answer is grounded in deterministic, verifiable math — computed against the State Twin, not approximated.

**Tier 2 — Smart Contract Security & Compliance**  
Questions requiring bytecode analysis, audit tooling, or governance assessment. Covered by the DeFiMind business plan (UC1/UC2, sidecar architecture). Not in scope for this document.

---

# Section 1 — Questions

*What LPs and traders need to know. These are the human-level questions that drive the product. Each maps to one or more primitives defined in Section 2.*

---

## Category 1: Position Diagnostics

*"What's happening to my money?"*

### Q1.1 — Why is my position losing money?
The core decomposition. Break a position's PnL into impermanent loss, accumulated fee income, and net result. Identify the mathematical cause — price deviation magnitude, tick range mismatch, fee tier inadequacy.

### Q1.2 — Am I actually earning anything after IL?
The fees=True vs fees=False comparison. Most LPs don't know whether fee income is compensating for IL. Provides the exact net number.

### Q1.3 — What's my real APR including IL?
Not the advertised APR, but actual return accounting for impermanent loss. Annualize (position_value - hold_value) / hold_value over the holding period. Completely different number from what any dashboard shows.

### Q1.4 — How much have I actually earned in fees?
Isolate the fee component from total position value change. Separate fee income from IL and price movement effects.

---

## Category 2: Risk Assessment

*"Should I be worried?"*

### Q2.1 — What happens if price drops X%?
Simulate price move, recalculate IL at the new level, project fee income at new price. IL formula is a closed-form function of price ratio — evaluable at any hypothetical price instantly.

### Q2.2 — At what price do I start losing money overall?
Solve for the break-even price ratio where cumulative fee income equals IL drag. Invert the IL formula to find the alpha where fees_accumulated + IL(alpha) = 0.

### Q2.3 — How exposed am I to a depeg?
For stableswap pools specifically. Curve invariant math shows what happens when one asset depegs 2%, 5%, 10%. Stableswap IL behaves completely differently from constant product IL.

### Q2.4 — Is my tick range about to go out of range?
For V3 positions. Current price vs tick boundaries. Calculate percentage price move needed to exit range. Assess likelihood based on recent price action.

---

## Category 3: Optimization

*"What should I do differently?"*

### Q3.1 — Is my tick range too wide or too narrow?
Capital efficiency tradeoff. Wider = less IL risk but lower fee capture per dollar. Quantify fee capture percentage vs IL exposure at multiple candidate ranges.

### Q3.2 — Should I split into multiple positions?
Compare one wide range vs two narrow ranges straddling current price. Evaluate each sub-position independently and sum results.

### Q3.3 — What's the optimal amount to deposit right now?
The quadratic deposit split from SwapDeposit. Most LPs eyeball the 50/50 split and lose value on the swap. The formula gives the exact optimum.

### Q3.4 — Should I rebalance now or wait?
Compare cost of rebalancing (swap fees, gas, IL crystallization) against projected benefit of better positioning. Chains multiple primitives across current state analysis, new position modeling, and stress testing.

---

## Category 4: Cross-Protocol Comparison

*"Am I in the right pool?"*

### Q4.1 — Is Curve better than Uniswap for this pair?
The question only DeFiMind can answer. Same capital, same token pair, different AMM invariant curves. Compare IL profiles directly. For stablecoin pairs, Curve invariant gives dramatically less IL near peg.

### Q4.2 — What's the best pool for this token pair across all protocols?
Scan available pools, run health checks on each, compare risk-adjusted returns across Uniswap V2, V3, Balancer, and Curve.

### Q4.3 — Should I move to a different fee tier?
V3 has 0.01%, 0.05%, 0.3%, 1% tiers. Higher fees = more income per swap but less volume. Model the tradeoff given current volume patterns.

---

## Category 5: Scenario Planning

*"What if?"*

### Q5.1 — What happens to my position in a market crash?
Run simulate_price_move at -30%, -50%, -70%. Show IL at each level, remaining position value, and whether fee income over holding period would have compensated.

### Q5.2 — If I add more liquidity, how does that change my risk?
Recalculate position metrics with larger size. IL percentage doesn't change but absolute exposure does. Fee income scales with position size relative to total pool.

### Q5.3 — How long do I need to stay in to break even?
Given current fee rate and current IL, solve for time period where cumulative fees equal IL drag. Directly derivable from existing math.

---

## Category 6: Portfolio Level

*"Big picture across all my positions"*

### Q6.1 — What's my total IL across all my positions?
Aggregate analyze_position across multiple pools. Sum components. Show which positions are carrying the portfolio and which are dragging.

### Q6.2 — Which of my positions should I exit first?
Rank by net PnL, risk-adjusted return, or IL-to-fee ratio. Each metric derived from existing primitives.

### Q6.3 — How correlated are my positions?
If you're in ETH-USDC and ETH-DAI, both have the same directional risk. Quantify the overlap and concentration.

---

## Category 7: Pool Health & Viability

*"Is this pool worth entering?"*

### Q7.1 — Is this pool behaving mathematically correctly?
Fetch reserves, compute what the price should be from the invariant curve, compare to what the contract reports. Divergence = red flag. DeFiPy's exact formulas serve as reference implementation.

### Q7.2 — Are the reserves consistent with the claimed TVL?
LPQuote derives what reserves should be given total supply and price. If a pool claims $10M TVL but reserves don't support it, flag it.

### Q7.3 — Is the fee structure what it claims to be?
Run a swap through the math with stated fee, compare to actual contract output. Mismatch = hidden fee or skimming.

### Q7.4 — Is this pool a likely rug pull candidate?
Detect mathematical patterns: extreme reserve ratios, suspiciously low liquidity relative to volume, single-sided concentration.

### Q7.5 — Is this pool economically viable?
TVL too low to generate meaningful fees? Volume insufficient to compensate for IL at current volatility? DeFiMind tells you "this pool will lose money even if nothing malicious happens."

---

## Category 8: Slippage & Execution

*"How much am I losing on the swap itself?"*

### Q8.1 — What's my actual slippage on a trade of this size?
Run the trade through the exact AMM formula. Compare output to spot price. Show the dollar cost of slippage. Most LPs estimate this from a UI slider — DeFiMind gives the exact number from the invariant curve.

### Q8.2 — What's the maximum trade size before slippage exceeds X%?
Invert the problem. Solve for the input amount where `(spot_price - execution_price) / spot_price = X%`. For V2 this is algebraically solvable from constant product. For V3 it requires finding where the trade crosses tick boundaries.

### Q8.3 — How does slippage compare across protocols for this pair?
Same trade size, run through Uniswap V2 constant product, V3 concentrated liquidity, Balancer weighted invariant, and Curve stableswap. For stablecoin pairs especially, the difference is dramatic — Curve was literally designed to minimize slippage near peg.

### Q8.4 — What's the slippage cost of rebalancing my position?
Withdrawal and re-entry involve multiple swaps, each with slippage. `WithdrawSwap` and `SwapDeposit` already compute the swap amounts internally — expose the slippage cost as part of the rebalancing analysis. Connects directly to Q3.4 — sometimes rebalancing slippage cost exceeds the benefit.

### Q8.5 — Am I being frontrun?
Compute expected output from the formula and compare to what the user actually received on-chain. The gap reveals MEV extraction. DeFiPy gives the theoretical output. The chain gives the actual output. The difference is what was taken.

---

## Category 9: Liquidity Depth

*"Can this pool handle my trade?"*

### Q9.1 — How deep is this pool at current price?
Total reserves relative to trade size. For V2, reserves are uniform across all prices. For V3, effective depth is the liquidity concentrated in the active tick range. `get_virtual_reserve` already computes V3's effective depth.

### Q9.2 — What's the price impact of my trade?
Related to slippage but framed as a pool metric. A $100K trade moving price 0.1% is fine. The same trade moving price 5% is a warning sign. The invariant curves compute the new price after any trade size directly.

### Q9.3 — Is there enough liquidity for me to exit my position?
The flip side of entry. If you have $500K in LP tokens and the pool has $1M TVL, withdrawing and swapping to a single token will have massive price impact. `WithdrawSwap` math computes exactly what you'd get out, including the slippage cost of the exit swap.

### Q9.4 — Where are the liquidity cliffs in this V3 pool?
Concentrated liquidity means some tick ranges are deep and others are empty. If price moves into a thin range, slippage spikes. `TickMath` functions can map the liquidity distribution across tick ranges and identify danger zones.

### Q9.5 — How much can I deposit without significantly moving the price?
For large depositors. A $1M single-sided deposit into a $5M pool fundamentally changes the reserve ratio. The `SwapDeposit` quadratic formula already accounts for this — the optimal split changes based on deposit size relative to pool size.

### Q9.6 — Is this pool's liquidity concentrated or distributed?
A V3 pool with all liquidity in ±1% range looks deep at current price but has zero depth elsewhere. A pool with liquidity spread across ±50% is shallow everywhere but resilient. Tick math can quantify this distribution and assess fragility.

---

# Section 2 — Primitives

*The DeFiPy objects that answer Section 1's questions. Each primitive follows the established DeFiPy design pattern: configuration at construction, execution at `.apply()`, structured result returned. These are the building blocks — an LLM chains them for DeFiMind, a quant calls them directly in a notebook.*

---

## Design Pattern

Every primitive in DeFiPy follows a consistent contract:

```python
# Configuration at construction
primitive = AnalyzePosition(include_fees=True)

# Execution at .apply() — takes a State Twin, returns structured result
result = primitive.apply(lp, entry_lp, position_size)

# Structured result — typed dataclass, readable by humans or LLMs
print(result.il_percentage)
print(result.diagnosis)
```

This mirrors the existing DeFiPy process layer — `Swap().apply()`, `Join().apply()`, `SwapDeposit().apply()`, `LPQuote().get_amount_from_lp()`. Configuration is separated from execution. Objects are stateless after construction. Results are deterministic.

The `.apply()` verb is deliberate. It echoes Solidity's separation of transaction construction from execution. It provides a uniform entry point across every object in the library. A user learns the pattern once: construct, then apply. The same pattern works for swaps, joins, quotes, IL calculations, and now diagnostics.

### Multi-Protocol Dispatch

Primitives are protocol-aware. `AnalyzePosition().apply(lp, ...)` checks the exchange type internally and routes to the correct math — constant product for V2, concentrated liquidity for V3, weighted invariant for Balancer, stableswap polynomial for Curve. Same dispatch pattern as the existing `Swap` wrapper.

### Two Consumers, One Interface

```python
# Notebook — quant calls primitives directly
from defipy import AnalyzePosition, SimulatePriceMove, CompareProtocols

result = AnalyzePosition().apply(lp, entry_lp, position_size)
scenario = SimulatePriceMove().apply(lp, -0.30, position_size)
comparison = CompareProtocols().apply(lp_uniswap, lp_curve, amount)

# DeFiMind — LLM calls the same primitives as tools
# (DeFiMind wraps these as tool definitions — not in DeFiPy, no LLM dependency)
tools = [
    {"name": "AnalyzePosition", "description": "Decompose position into IL, fees, net PnL", ...},
    {"name": "SimulatePriceMove", "description": "Project position value at hypothetical price", ...},
    {"name": "CompareProtocols", "description": "Compare risk/return across AMM designs", ...},
]
```

DeFiPy stays pure — no LLM imports, no API keys, no network dependencies beyond the optional `LiveProvider`. The primitives are LLM-ready without being LLM-dependent.

---

## The 19 Primitives

### Primitive 1: `AnalyzePosition`

**Answers:** Q1.1, Q1.2, Q1.3, Q1.4

**Constructor:** `AnalyzePosition(include_fees=True)`

**Signature:** `.apply(lp, entry_lp, position_size_lp) → PositionAnalysis`

**Returns:**
```python
@dataclass
class PositionAnalysis:
    current_value: float        # Current position value in reference token
    hold_value: float           # Value if tokens were held instead of LP'd
    il_percentage: float        # Raw IL from price divergence (fees=False)
    il_with_fees: float         # Net IL accounting for fee income (fees=True)
    fee_income: float           # Isolated fee component
    net_pnl: float              # current_value - hold_value
    real_apr: float             # Annualized net return including IL
    diagnosis: str              # "il_dominant" | "fee_compensated" | "net_positive"
```

**Internal calls:** `UniswapImpLoss.apply(fees=True)`, `UniswapImpLoss.apply(fees=False)`, `UniswapImpLoss.current_position_value()`, `UniswapImpLoss.hold_value()`

---

### Primitive 2: `SimulatePriceMove`

**Answers:** Q2.1, Q5.1, Q5.2

**Constructor:** `SimulatePriceMove()`

**Signature:** `.apply(lp, price_change_pct, position_size_lp) → PriceMoveScenario`

**Returns:**
```python
@dataclass
class PriceMoveScenario:
    new_price_ratio: float      # Alpha = new_price / entry_price
    new_value: float            # Position value at new price
    il_at_new_price: float      # IL percentage at simulated price
    fee_projection: float       # Projected fee income (if estimable)
    value_change_pct: float     # Percentage change from current value
```

**Internal calls:** `UniswapImpLoss.calc_iloss(alpha)`, `LPQuote.get_amount_from_lp()`

---

### Primitive 3: `FindBreakEvenPrice`

**Answers:** Q2.2

**Constructor:** `FindBreakEvenPrice()`

**Signature:** `.apply(lp, entry_lp, position_size_lp, accumulated_fees) → BreakEvenResult`

**Returns:**
```python
@dataclass
class BreakEvenResult:
    break_even_alpha: float     # Price ratio where fees = IL
    break_even_price: float     # Actual price at break-even
    current_alpha: float        # Current price ratio for reference
    margin_pct: float           # How far from break-even (positive = safe)
```

**Internal calls:** Algebraic inversion of `UniswapImpLoss.calc_iloss(alpha)` — **new derivation**

---

### Primitive 4: `FindBreakEvenTime`

**Answers:** Q5.3

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V2/V3). 20 tests passing.

**Constructor:** `FindBreakEvenTime()`

**Signature:** `.apply(lp, entry_lp, position_size_lp, fee_rate_per_block) → BreakEvenTimeResult`

**Returns:**
```python
@dataclass
class BreakEvenTimeResult:
    blocks_to_break_even: int   # Estimated blocks until fees compensate IL
    days_to_break_even: float   # Converted to days (~12s per block)
    current_il_drag: float      # Current IL in reference token
    fee_rate: float             # Fee accumulation rate
```

**Internal calls:** `UniswapImpLoss.apply()`, fee rate estimation — **new derivation**

---

### Primitive 5: `AssessDepegRisk`

**Answers:** Q2.3

**Status:** ✅ Shipped 2026-04-22 (v1.2.0). See v1 Implementation Notes below.

**Constructor (spec):** `AssessDepegRisk()`

**Signature (spec):** `.apply(lp, lp_init_amt, depeg_token, depeg_levels=None, compare_v2=True) → DepegRiskAssessment`

**Returns:**
```python
@dataclass
class DepegScenario:
    depeg_pct: float
    peg_price: float
    lp_value_at_depeg: Optional[float]       # None if unreachable
    hold_value_at_depeg: Optional[float]     # None if unreachable
    il_pct: Optional[float]                   # None if unreachable
    v2_il_comparison: Optional[float]         # V2 IL benchmark, always populated

@dataclass
class DepegRiskAssessment:
    depeg_token: str
    protocol_type: str                        # "stableswap" for v1
    n_assets: int
    current_peg_deviation: float
    scenarios: List[DepegScenario]
```

#### v1 Implementation Notes (2026-04-22)

The shipped v1 is narrower than the spec initially envisioned but more honest about what the math delivers. Key differences from the Primitive 5 design sketch above:

**v1 is N=2 only.** The closed-form expansion of the stableswap invariant used in v1 is specific to 2-asset pools. The derivation generalizes in principle to N>2 but not cleanly — N>2 is explicitly deferred to a future release. Passing an N>2 lp raises ValueError.

**v1 uses analytical invariant evaluation, not state twin mutation.** Initial implementation attempts tried to drive stableswappy's integer-math Newton solvers to a target dydx state by bisecting on balance multipliers. That approach ran into three rounds of unit-conversion and non-convergence issues before being replaced with the current analytical approach: parameterize the invariant by `ε = (x-y)/(x+y)`, derive `δ = 1 - dydx` as a function of (ε, A), invert via fixed-point iteration, and compute IL from the closed-form LP vs. hold value expressions. The primitive reads a handful of metadata scalars from the `lp` object (A, N, balances, LP supply, decimals) and does the core math in pure floats — no `get_y`, no `get_D`, no Newton iteration on state, no deep-copying of `math_pool`.

**Reachability is a first-class output, not a silent assumption.** The shipped primitive recognizes that for high-A pools, small depeg targets require physically impossible pool compositions (|ε| > 1). These are flagged with `il_pct = None` rather than returning a fabricated number. At A=200, depegs of 2% are unreachable; at A=10 they're cleanly reachable. Callers check `il_pct is None` to distinguish the two regimes. The V2 benchmark remains populated even in unreachable scenarios so callers see a reference point regardless.

**V2 comparison reveals a counterintuitive truth.** The popular narrative "stableswap has lower IL than V2 for the same price deviation" is true per unit of trading volume but false per unit of price deviation. At high A, stableswap actually has *larger* absolute IL than V2 at the same δ, because the flat curve forces large composition shifts to move price even slightly. This is Cintra & Holloway's "strong negative convexity." The primitive reports both numbers side-by-side so the shape is visible.

**Realistic envelope.** The leading-order expansion is highly accurate for small-to-moderate ε (say |ε| < 0.8). For near-drained pools the higher-order terms matter more. In practice this covers all realistic depeg events at common A values; exotic cases may need the N>2 or higher-order-accuracy extensions tracked for future work.

See `python/prod/primitives/risk/AssessDepegRisk.py` for the derivation (in the class docstring) and full implementation.

---

### Primitive 6: `CheckTickRangeStatus`

**Answers:** Q2.4

**Constructor:** `CheckTickRangeStatus()`

**Signature:** `.apply(lp, lwr_tick, upr_tick) → TickRangeStatus`

**Returns:**
```python
@dataclass
class TickRangeStatus:
    current_tick: int
    lower_tick: int
    upper_tick: int
    pct_to_lower: float         # Price move % to hit lower bound
    pct_to_upper: float         # Price move % to hit upper bound
    in_range: bool
    range_width_pct: float      # Total range as % of current price
```

**Internal calls:** `TickMath.getSqrtRatioAtTick()`, `lp.slot0.sqrtPriceX96`

---

### Primitive 7: `EvaluateTickRanges`

**Answers:** Q3.1, Q3.2

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V3-only). 21 tests passing.

**Constructor:** `EvaluateTickRanges()`

**Signature:** `.apply(lp, position_size, candidate_ranges) → TickRangeEvaluation`

**Returns:**
```python
@dataclass
class RangeMetrics:
    lower_tick: int
    upper_tick: int
    capital_efficiency: float   # Liquidity per dollar vs full range
    il_exposure: float          # IL at current price deviation
    fee_capture_pct: float      # Estimated share of fees captured

@dataclass
class TickRangeEvaluation:
    ranges: list[RangeMetrics]
    optimal_range: RangeMetrics
    split_vs_single: float      # Benefit of splitting (if applicable)
```

**Internal calls:** `UniV3Helper`, `TickMath`, `UniswapImpLoss.calc_iloss()` per range

---

### Primitive 8: `OptimalDepositSplit`

**Answers:** Q3.3, Q9.5

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V2-only). See v1 Implementation Notes below.

**Constructor (spec):** `OptimalDepositSplit()`

**Signature (spec):** `.apply(lp, token_in, amount_in, lwr_tick=None, upr_tick=None) → DepositSplitResult`

**Returns (spec):**
```python
@dataclass
class DepositSplitResult:
    optimal_fraction: float     # Fraction to swap before deposit
    swap_amount: float          # Exact amount to swap
    deposit_amount_0: float     # Token 0 to deposit
    deposit_amount_1: float     # Token 1 to deposit
    expected_lp_tokens: float   # LP tokens received
    slippage_cost: float        # Cost of the swap in the split
```

**Internal calls:** `SwapDeposit._calc_univ2_deposit_portion()` / `_calc_univ3_deposit_portion()`

#### v1 Implementation Notes (2026-04-23)

v1 diverges from the spec on field names (token_in/token_out rather than token_0/token_1) and on scope (V2-only), but preserves the primitive's core contract: non-mutating projection of what the mutating `SwapDeposit().apply()` would do.

**V2-only, with V3 rejection.** V2's zap-in quadratic has a clean closed form already factored into `SwapDeposit._calc_univ2_deposit_portion` and pure-read. V3's portion calculation uses `scipy.optimize.minimize` internally and depends on `UniV3Helper.quote` which the cleanup backlog flags for its hard-coded-997 fee bug. Rather than propagate that latent issue into a projection primitive, v1 raises `ValueError` on V3 with a backlog-referencing message. Extension to V3 becomes clean once the UniV3Helper fix lands.

**Field-naming divergence from spec.** The spec uses `deposit_amount_0` / `deposit_amount_1` (token0/token1 axis). v1 uses `deposit_amount_in` / `deposit_amount_out` (the input-vs-output axis from the caller's perspective). The motivation: a caller who passes `token_in = token1` doesn't want to reason about which of deposit_amount_0 and deposit_amount_1 matches their input. Pair-with-swap fields is the natural shape — `swap_amount_in` / `swap_amount_out` / `deposit_amount_in` / `deposit_amount_out` all share the same subject. The `lwr_tick` / `upr_tick` parameters from the spec are also omitted, since those are V3-only and v1 is V2-only.

**Non-mutating, by design and by assertion.** The shipped primitive projects what `SwapDeposit().apply(...)` would do *without* touching the pool. `SwapDeposit` mutates (swaps, mints LP tokens, changes reserves); OptimalDepositSplit reads only. The test suite asserts this explicitly — a dedicated test verifies that after `OptimalDepositSplit().apply(...)` returns, lp.reserve0, lp.reserve1, lp.total_supply, and lp.liquidity_providers[USER] are unchanged. Pattern applicable to any future projection primitive.

**Consistency cross-check against SwapDeposit.** The most important test builds two identical pools, runs OptimalDepositSplit on one and SwapDeposit on the other, and verifies the projected `expected_lp_tokens` matches the actual LP balance change within 0.1%. This closes the loop on the primitive's core promise — "I'll tell you what SwapDeposit would do" — by directly comparing the prediction to the execution.

**Added fields not in the spec.** `token_in_name` (echoed for traceability), `amount_in` (echoed), `swap_amount_out`, `deposit_amount_out`, and `slippage_pct`. The additions support the signal-surfacer convention (expose numbers, not verdicts) and make the dataclass self-describing enough that an LLM operator can summarize it without needing the primitive's docstring on hand.

**Slippage denomination.** `slippage_cost` is expressed in token_out units — (α · amount_in · spot_price) minus swap_amount_out, where spot_price is pre-swap. This matches `CalculateSlippage.slippage_cost`'s convention, so the two primitives compose cleanly. `slippage_pct` is `slippage_cost / (α · amount_in · spot_price)`, always in [0, 1). For tiny deposits slippage_pct ≈ 0.003 (the 30-bps fee itself); for a 20%-of-reserves deposit it grows to several percent.

**Correct α behavior, documented after the test suite caught an intuition error.** Working the V2 zap quadratic through carefully: α → 1/(1+f) ≈ 0.50075 as dx → 0 (f = 0.997 is the fee multiplier), and dα/d(dx) < 0 identically for dx > 0. So α starts just above 0.5 and *decreases* with deposit size — not increases. Initial tests asserted the wrong direction and failed on first run; the derivation was done on paper in response and is now captured in the primitive's docstring, in PROJECT_CONTEXT's Key Internal Conventions, and in decision heuristic #11 ("direction-of-change assertions deserve a derivation, not a prior"). This is a trap any future primitive reasoning about V2 mechanics could walk into — EvaluateRebalance especially, since it depends on OptimalDepositSplit.

**Private-method dependency as a tracked risk.** OptimalDepositSplit calls `SwapDeposit()._calc_univ2_deposit_portion(...)` — a leading-underscore method on the mutating process object. The call is read-only and works, but a future uniswappy refactor could reshape the private method and break OptimalDepositSplit silently. Not blocking; tracked as a future API-promotion request on uniswappy.

See `python/prod/primitives/optimization/OptimalDepositSplit.py` for the implementation and `python/prod/utils/data/DepositSplitResult.py` for the shipped dataclass shape.

---

### Primitive 9: `EvaluateRebalance`

**Answers:** Q3.4, Q8.4

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V2-only). 20 tests passing. See v1 Implementation Notes below.

**Constructor (spec):** `EvaluateRebalance()`

**Signature (spec):** `.apply(lp, entry_lp, token_in, position_size_lp, new_lwr_tick=None, new_upr_tick=None) → RebalanceEvaluation`

**Returns:**
```python
@dataclass
class RebalanceEvaluation:
    current_analysis: PositionAnalysis   # From AnalyzePosition
    withdrawal_slippage: float           # Cost to exit current position
    deposit_slippage: float              # Cost to enter new position
    total_rebalance_cost: float          # Combined slippage + gas estimate
    projected_improvement: float         # Expected benefit of new position
    net_benefit: float                   # improvement - cost
    recommendation: str                  # "rebalance" | "hold" | "marginal"
```

**Internal calls:** `AnalyzePosition`, `WithdrawSwap`, `SwapDeposit`, `OptimalDepositSplit`

#### v1 Implementation Notes (2026-04-23)

Deepest-composition primitive shipped to date — chains four per-position primitives to answer "should I rebalance now or wait?"

**V2-only scope, matching OptimalDepositSplit's dependency.** V3 rebalance requires the V3 path on OptimalDepositSplit which is blocked by the UniV3Helper fee-passthrough backlog item. V3 inputs raise `ValueError`.

**Metrics-only, no recommendation string.** The spec's `recommendation: str` field was dropped per the signal-surfacer convention. Rebalance decisions are driven by caller-specific context the primitive can't see (gas price expectations, time horizon, risk tolerance, tax implications of IL crystallization). v1 exposes the net-benefit number and the decomposition; the caller names the verdict.

**Single candidate, not N.** v1 takes one hypothetical new position (target allocation via `token_in` + implicit current-price reallocation). N-candidate ranking shape may come later; for now, callers wanting to compare multiple new positions call the primitive N times and rank themselves. Simpler to ship, composable with existing ranking patterns.

**Explicit cost decomposition.** `withdrawal_slippage`, `deposit_slippage`, and `total_rebalance_cost` are surfaced separately from `projected_improvement` and `net_benefit`. Lets the caller see whether a borderline net-benefit number is driven by tiny-swap arithmetic noise or genuine cost-vs-benefit tension.

See `python/prod/primitives/optimization/EvaluateRebalance.py` for the implementation.

---

### Primitive 10: `CompareProtocols`

**Answers:** Q4.1, Q8.3

**Status:** ✅ Shipped 2026-04-23 (v1.2.0). 23 tests passing. See v1 Implementation Notes below.

**Constructor (spec):** `CompareProtocols()`

**Signature (spec):** `.apply(lp_a, lp_b, amount, token=None) → ProtocolComparison`

**Returns:**
```python
@dataclass
class ProtocolMetrics:
    protocol: str               # "uniswap_v2" | "uniswap_v3" | "balancer" | "stableswap"
    il_at_current: float
    fee_apr: float
    slippage_at_amount: float
    capital_efficiency: float

@dataclass
class ProtocolComparison:
    pool_a: ProtocolMetrics
    pool_b: ProtocolMetrics
    il_advantage: str           # Which pool has less IL
    fee_advantage: str          # Which pool earns more fees
    recommendation: str
    reasoning: str
```

**Internal calls:** `AnalyzePosition` on each twin, `CalculateSlippage` on each twin, `LPQuote` on each

#### v1 Implementation Notes (2026-04-23)

Flagship cross-protocol primitive. Same capital, same token pair (or depeg scenario), different AMM invariant curves — directly answers Q4.1 ("is Curve better than Uniswap for this pair?") with exact math rather than narrative.

**N-candidate list input, not binary A-vs-B.** v1 takes a list of `ProtocolCandidate` inputs (one per pool) rather than the spec's `lp_a, lp_b` pair. Matches AggregatePortfolio's and CompareFeeTiers's list-of-inputs pattern. A caller with two protocols passes a 2-element list; a caller comparing V2 + V3 + Balancer + Stableswap on the same stablecoin pair passes a 4-element list.

**Metrics-only, no `recommendation` field.** The spec's `recommendation` and `reasoning` strings were dropped per the signal-surfacer convention. Protocol choice depends on caller-specific considerations (which token dominates volatility, target holding period, stablecoin vs. volatile pair, risk tolerance) the primitive can't see. v1 exposes IL, fee yield (where observable), slippage, and capital-efficiency metrics side-by-side in consistent shape; caller chooses.

**Stableswap IL via AssessDepegRisk composition.** Stableswap candidates compose AssessDepegRisk internally for the IL-at-current-price metric — same invariant-math path, same reachability semantics (IL can be None for unreachable scenarios). First primitive to demonstrate cross-protocol IL comparison at full fidelity: V2/V3 via UniswapImpLoss, Balancer via BalancerImpLoss, Stableswap via AssessDepegRisk's derivation.

**Slippage and fee yield degrade gracefully.** `slippage_at_amount` is populated for V2/V3 via CalculateSlippage; Balancer and Stableswap report `None` in v1 (CalculateSlippage is V2/V3-only, tracked as a cleanup-backlog item). `fee_apr` is similarly `None` for protocols without per-LP fee attribution. The metric shape stays consistent so the cross-protocol ranking remains meaningful on the axes that are populated.

**Common-pair enforcement.** Candidates must share the same pair of token symbols. Cross-pair comparison (ETH/USDC V2 vs. BTC/USDC Balancer) collapses independent questions; v1 raises `ValueError` early and directs the caller to group by pair. Same stance as CompareFeeTiers.

**Composition pattern.** Depth-chains AnalyzePosition + CalculateSlippage + CheckPoolHealth + AssessDepegRisk (for stableswap) across each candidate, then breadth-combines the results. The deepest-composition primitive of the day.

See `python/prod/primitives/comparison/CompareProtocols.py` for the implementation and `ProtocolCandidate`, `ProtocolMetrics`, `ProtocolComparison` in `utils/data/` for the shipped dataclass shapes.

---

### Primitive 11: `CompareFeeTiers`

**Answers:** Q4.3

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V3-only). See v1 Implementation Notes below.

**Constructor (spec):** `CompareFeeTiers()`

**Signature (spec):** `.apply(lp, position_size, fee_tiers=[100, 500, 3000, 10000]) → FeeTierComparison`

**Returns (spec):**
```python
@dataclass
class FeeTierMetrics:
    fee_tier_bps: int
    fee_income_estimate: float
    il_at_current: float
    net_return: float

@dataclass
class FeeTierComparison:
    tiers: list[FeeTierMetrics]
    optimal_tier: int
```

**Internal calls:** V3 math at different fee parameters, volume estimation from reserves

#### v1 Implementation Notes (2026-04-23)

The shipped v1 diverges from the spec above in shape *and* in what it promises. The differences were deliberate, settled up-front with user sign-off, and driven by what the math and the protocol library can honestly deliver.

**Multi-pool input, not single-pool reparameterization.** The spec's `.apply(lp, position_size, fee_tiers=[...])` implies mutating one pool's fee to see hypothetical outcomes. A V3 pool's fee is baked into its swap math and `feeGrowthGlobal` accumulators at construction — you can't reparameterize a deployed pool. The shipped primitive takes a list of `FeeTierCandidate` input dataclasses, each holding a real V3 pool at its actual fee tier, and compares them. This matches how fee-tier decisions actually look on-chain ("which of these three ETH/USDC pools should I enter?") and mirrors AggregatePortfolio's list-of-inputs pattern.

**No forward fee-income projection.** The spec's `fee_income_estimate` and `net_return` were dropped. Both require a forward volume model the pool object can't provide — no per-block-volume, no historical trajectory, no external price oracle. Rather than guess, v1 reports `observed_fee_yield`: cumulative fees earned to date, in token0 numeraire, divided by current TVL. A rate, not a forecast. Callers who know the pool's age annualize themselves; callers who want forward projection compose with their own volume assumptions.

**No single `optimal_tier` verdict.** Different axes (observed yield, TVL, range status) favor different tiers, and which axis matters depends entirely on the caller's use case — a yield-chaser, a depth-seeker, and an LP worried about out-of-range exposure would each pick differently from the same three pools. v1 returns two independent orderings (`ranking_by_observed_fee_yield`, `ranking_by_tvl`) and per-tier metrics; the caller picks. Consistent with the signal-surfacer-not-verdict-generator convention from DetectRugSignals, AggregatePortfolio, AssessDepegRisk, and DetectFeeAnomaly.

**V3-only with V2 rejection.** V2 has a single hard-coded fee (30 bps via 997/1000) — there are no tiers to compare. V2 inputs raise ValueError with an index-identifying message pointing to the offending candidate. Same graceful-degradation stance as DetectFeeAnomaly (V2-only by necessity; V3 raises) and AssessDepegRisk (stableswap-only; V2/V3 raise).

**Common-pair rejection.** All candidates must share both `token0` and `token1` symbols. Comparing fee tiers of different pairs collapses independent questions into a spurious ranking; v1 errors early with `ValueError` and directs the caller to group by pair. Same stance as AggregatePortfolio's common-token0 rejection.

**Pure composition over CheckPoolHealth and CheckTickRangeStatus.** No new math — the primitive reads per-pool TVL and fees from CheckPoolHealth, range status from CheckTickRangeStatus, and fee tier from `lp.fee // 100`. Yield computation is a single expression: `(total_fee0 + total_fee1 / spot_price) / tvl_in_token0`, with `None` when any input is ill-defined (no fees, no spot price, or no TVL). Demonstrates the breadth-chain composition pattern established by AggregatePortfolio.

**Notes as informational, not warnings.** The `notes: list[str]` field surfaces conditions that affect interpretation of the rankings ("candidate X has no accumulated fees— observed_fee_yield is None", "candidate Y is out of range at current price") but doesn't duplicate information directly visible on the per-tier metrics. Right boundary for a breadth-chain composition: notes alert, metrics inform, rankings order.

**Correction to an earlier convention.** During test development, the test that drives a swap through one V3 pool and asserts its yield ranks ahead of a quiet pool passed on the first run. That disproved an earlier PROJECT_CONTEXT claim that V3 `collected_fee*` updates lazily — they update synchronously in the swap path. The Key Internal Conventions were amended accordingly. Future primitives needing point-in-time fee totals work on both V2 and V3; only per-swap history and rolling rates remain V2-only.

See `python/prod/primitives/comparison/CompareFeeTiers.py` for the implementation and its fuller docstring. See `FeeTierCandidate`, `FeeTierMetrics`, `FeeTierComparison` in `utils/data/` for the shipped dataclass shapes.

---

### Primitive 12: `AggregatePortfolio`

**Answers:** Q6.1, Q6.2, Q6.3

**Status:** ✅ Shipped 2026-04-22 (v1.2.0, V2/V3). Cross-protocol extension shipped 2026-04-23. 21 tests at v1 + 13 cross-protocol tests = 34 total. See v1 Implementation Notes below.

**Constructor:** `AggregatePortfolio()`

**Signature:** `.apply(positions: list[PortfolioPosition]) → PortfolioAnalysis`

**Returns:**
```python
@dataclass
class PositionSummary:
    pool_name: str
    net_pnl: float
    il_percentage: float
    fee_income: float
    tokens: list[str]

@dataclass
class PortfolioAnalysis:
    total_value: float
    total_il: float
    total_fees: float
    total_net_pnl: float
    positions: list[PositionSummary]   # Ranked by net_pnl
    exit_priority: list[str]            # Worst performers first
    correlation_warnings: list[str]     # Token overlap alerts
```

**Internal calls:** `AnalyzePosition` per position, token overlap detection

#### v1 Implementation Notes (2026-04-22) and cross-protocol extension (2026-04-23)

Originally shipped V2/V3-only; extended to full cross-protocol dispatch in the 2026-04-23 part 3 session after the sibling cross-protocol position analyzers (`AnalyzeBalancerPosition`, `AnalyzeStableswapPosition`) landed.

**Spec-level field name changes.** The spec's `correlation_warnings` became `shared_exposure_warnings` (token overlap is not statistical correlation), `exit_priority` became `pnl_ranking` (the primitive ranks, the caller decides exit order). Signal-surfacer-not-verdict-generator convention. The spec's `total_il` was dropped — the portfolio-level IL isn't a clean sum across heterogeneous pools (different numeraires, different IL semantics across protocols); per-position `il_percentage` stays on each PositionSummary for callers who want to roll it up themselves.

**Structured input via PortfolioPosition.** The spec's `list[tuple[lp, entry_lp, size]]` was replaced with a typed `PortfolioPosition` dataclass. Lets the input carry optional fields (display name, holding period, V3 ticks, protocol-specific entry shapes) without positional-tuple growth. Matches CompareFeeTiers's and CompareProtocols's list-of-dataclass input pattern.

**Cross-protocol dispatch (2026-04-23 extension).** isinstance-based protocol detection routes each position to the appropriate analyzer: V2/V3 → AnalyzePosition, Balancer → AnalyzeBalancerPosition, Stableswap → AnalyzeStableswapPosition. `PositionSummary` gained a `protocol: str` field ({uniswap_v2, uniswap_v3, balancer, stableswap}) for consumer-side dispatch without re-inspecting the lp object. `analysis` field retyped to `Any` (was `PositionAnalysis`) to accept any of the three analyzer output variants; callers who need protocol-specific fields do isinstance-dispatch on `.analysis`.

**Numeraire generalization.** The legacy "common token0" rule generalized to "common first-token-in-pool-insertion-order." V2/V3 still use `lp.token0`; Balancer and Stableswap use `list(lp.tkn_reserves.keys())[0]`. Mixed-first-token portfolios raise `ValueError` — callers group by first-token symbol and call once per group. Same rejection shape as v1 but generalized across protocols.

**PortfolioPosition grew an `entry_amounts: Optional[List[float]]` field** for the stableswap path. V2/V3/Balancer positions still use `entry_x_amt` + `entry_y_amt`. Stableswap positions must provide `entry_amounts` instead; aggregation raises `ValueError` if a stableswap position lacks it.

**Stableswap unreachable-alpha handling.** Positions whose analyzer returns `il_percentage = None` (unreachable regime) contribute 0 to the scalar totals and get flagged in `shared_exposure_warnings` with an identifying note. Keeps aggregation meaningful for the reachable positions; the skip is explicit rather than silent.

**Fee income scope.** `total_fees` in v1 is contributed to only by V2/V3 positions. Balancer and Stableswap fee_income = 0 pending per-LP fee attribution in the sibling repos. Documented; callers tracking Balancer/Stableswap fee yield must track externally.

**Input-order preservation with independent ranking.** Positions stay in caller's input order in `positions[]`; worst-first ordering exposed via `pnl_ranking` (names, not indices). Reordering the caller's data would be surprising — both views available without either rewriting the other.

See `python/prod/primitives/portfolio/AggregatePortfolio.py` for the implementation.

---

### Primitive 13: `CheckPoolHealth`

**Answers:** Q7.1, Q7.2, Q7.5

**Constructor:** `CheckPoolHealth()`

**Signature:** `.apply(lp) → PoolHealthReport`

**Returns:**
```python
@dataclass
class PoolHealthReport:
    tvl: float
    reserve_ratio: float            # Actual vs expected from invariant
    price_consistency: bool         # Math price matches reported price
    fee_apr_estimate: float
    volume_estimate: float
    economically_viable: bool
    warnings: list[str]
```

**Internal calls:** `LPQuote.get_price()`, `LPQuote.get_reserve()`, reserve consistency checks

---

### Primitive 14: `DetectFeeAnomaly`

**Answers:** Q7.3

**Status:** ✅ Shipped 2026-04-22 (v1.2.0, V2-only). See v1 Implementation Notes below.

**Constructor (spec):** `DetectFeeAnomaly(discrepancy_threshold_bps=10.0)`

**Signature (spec):** `.apply(lp, token_in, test_amount=None) → FeeAnomalyResult`

**Returns:**
```python
@dataclass
class FeeAnomalyResult:
    stated_fee_bps: int
    test_amount: float
    theoretical_output: float       # What math says you should get at stated fee
    actual_output: float            # What lp.get_amount_out returns
    discrepancy_bps: float          # Signed; positive = pool underdelivers
    direction: str                  # "pool_underdelivers" | "pool_overdelivers"
    anomaly_detected: bool          # |discrepancy_bps| > threshold
```

**Internal calls:** Constant-product-with-fee formula in pure floats, vs. `lp.get_amount_out()`.

#### v1 Implementation Notes (2026-04-22)

The shipped v1 is narrower than the initial spec sketch, scoped to answer the consistency question (Shape A) cleanly rather than the broader stated-vs-actual comparison question (Shape B).

**Shape A only (invariant-vs-contract consistency).** v1 compares the pool's actual output against what the constant-product invariant predicts *at the pool's own stated fee*. It validates that pool behavior is internally consistent — that the contract's math does what the contract's fee parameter claims. What this catches: proxy wrappers silently reducing output (skim), implementation bugs in fee arithmetic, undocumented admin fees, integer-math rounding adversarial to the trader, reentrancy guards reducing return values, subsidy mechanisms that over-deliver. What it does NOT catch: an honestly-advertised high fee (a 1% pool whose math is internally consistent at 1% will show no anomaly). The broader Shape B (user-supplied expected fee) is deferrable to a future iteration as an optional `expected_fee_bps` parameter.

**v1 is V2-only.** V2's fee is a protocol constant (30 bps via 997/1000 in the swap math); the pool object does not expose `.fee` and the constant is known. V3 extension is blocked by a latent issue in `UniV3Helper.quote`: it hard-codes `fee = 997` rather than reading `lp.fee`, so a 0.05% V3 pool's quote helper diverges from actual swap output at any non-30-bps fee tier. That's itself a fee-anomaly-in-the-tooling that DetectFeeAnomaly would rightly want to surface, but it means we can't use the helper as a ground-truth "actual output" path on V3 without first fixing the helper or introducing a non-mutating V3 quote path that honors `.fee`. Tracked in the cleanup backlog. V3 pools raise ValueError with a clear explanation; stableswap and Balancer also raise (different invariants, future work).

**Direction classification is descriptive, not accusatory.** `direction` takes one of `"pool_underdelivers"` / `"pool_overdelivers"` — pure signed-discrepancy labels. Earlier framing considered `"pool_skimming"` which overreaches into attributing motive (not all underdelivery is malicious). The primitive observes; the caller — or an LLM layer, or a human — interprets whether observed underdelivery means a skim, a bug, an admin fee, or rounding. Consistent with DetectRugSignals' and AggregatePortfolio's "signal surfacer, not verdict generator" stance.

**Both directions surfaced equally.** Unlike most fee-anomaly tools that only flag underdelivery, v1 reports overdelivery with the same clarity. Overdelivery is diagnostically important: it signals subsidies, fee-routing that bypasses the trader's receipt, implementation bugs in the trader's favor, or reward wrappers. An LLM doing forensic analysis of pool behavior should see both; the primitive provides the observation, the caller decides whether 30 bps of over-delivery is subsidy or bug.

**Default test_amount: 1% of input reserve.** Small enough not to move the pool appreciably (so repeated calls are stable), large enough that float-vs-integer rounding noise stays well below the 10-bps default threshold. Callers can override with an explicit `test_amount` if they want to probe at a specific size. Typical clean-pool discrepancy in testing is ~1e-8 bps — ample headroom.

See `python/prod/primitives/pool_health/DetectFeeAnomaly.py` for the implementation and its fuller docstring.

---

### Primitive 15: `DetectRugSignals`

**Answers:** Q7.4

**Constructor:** `DetectRugSignals()`

**Signature:** `.apply(lp) → RugSignalReport`

**Returns:**
```python
@dataclass
class RugSignalReport:
    reserve_ratio_extreme: bool     # One side >95% of pool
    tvl_suspiciously_low: bool
    single_sided_concentration: bool
    signals_detected: int
    risk_level: str                 # "low" | "medium" | "high" | "critical"
    details: list[str]
```

**Internal calls:** Reserve ratio analysis, TVL checks, concentration metrics

---

### Primitive 16: `CalculateSlippage`

**Answers:** Q8.1, Q8.2, Q9.2

**Constructor:** `CalculateSlippage()`

**Signature:** `.apply(lp, token_in, amount_in) → SlippageAnalysis`

**Returns:**
```python
@dataclass
class SlippageAnalysis:
    spot_price: float               # Price before trade
    execution_price: float          # Price after trade
    slippage_pct: float             # Percentage slippage
    slippage_cost: float            # Dollar cost of slippage
    price_impact_pct: float         # Pool price moved by this %
    max_size_at_1pct: float         # Max trade for 1% slippage (if computed)
```

**Internal calls:** `LPQuote.get_price()`, `lp.get_amount_out()`, algebraic inversion for max size

---

### Primitive 17: `DetectMEV`

**Answers:** Q8.5

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, V2/V3). 20 tests passing.

**Constructor:** `DetectMEV()`

**Signature:** `.apply(lp, token_in, amount_in, actual_output) → MEVDetectionResult`

**Returns:**
```python
@dataclass
class MEVDetectionResult:
    theoretical_output: float       # What math says you should get
    actual_output: float            # What you actually got
    extraction_amount: float        # theoretical - actual
    extraction_pct: float
    likely_frontrun: bool           # True if gap exceeds fee + normal slippage
```

**Internal calls:** `lp.get_amount_out()` for theoretical, comparison to user-provided actual

---

### Primitive 18: `AssessLiquidityDepth`

**Answers:** Q9.1, Q9.3, Q9.4, Q9.6

**Constructor:** `AssessLiquidityDepth(tick_granularity=10)`

**Signature:** `.apply(lp, token_in, trade_size=None) → LiquidityDepthReport`

**Returns:**
```python
@dataclass
class TickLiquidity:
    tick_lower: int
    tick_upper: int
    liquidity: float

@dataclass
class LiquidityDepthReport:
    total_tvl: float
    depth_at_current_price: float       # Effective liquidity at current tick
    max_trade_1pct_impact: float        # Largest trade with <1% price impact
    exit_slippage_at_full_size: float   # Slippage if exiting full position (if trade_size given)
    concentration_index: float          # 0=uniform, 1=single tick
    tick_distribution: list[TickLiquidity]  # V3 only — liquidity per range
    liquidity_cliffs: list[int]         # Ticks where liquidity drops sharply
```

**Internal calls:** V2 reserves directly, V3 `get_virtual_reserve()`, `TickMath` traversal — **needs tick traversal wrapper**

---

### Primitive 19: `DiscoverPools`

**Answers:** Q4.2

**Constructor:** `DiscoverPools()`

**Signature:** `.apply(token_a, token_b, protocols=["uniswap_v2", "uniswap_v3", "balancer", "stableswap"]) → PoolDiscoveryResult`

**Returns:**
```python
@dataclass
class DiscoveredPool:
    address: str
    protocol: str
    fee_tier: int
    tvl: float
    health: PoolHealthReport

@dataclass
class PoolDiscoveryResult:
    pools: list[DiscoveredPool]
    recommended: DiscoveredPool
```

**Internal calls:** Factory event scanning via web3scout, `CheckPoolHealth` per pool — **stretch goal, not day-one**

---

## Cross-Protocol Extensions (beyond the original 19-primitive spec)

After the 17 Tier 1 primitives + CompareProtocols shipped, an audit identified opportunities to extend position-level analysis across the non-Uniswap AMM families. The result: three sibling primitives to `AnalyzePosition` answering the same Q1.1–Q1.4 questions on Balancer and Stableswap pools. The cross-protocol extension pattern is codified in `PRIMITIVE_AUTHORING_CHECKLIST.md` §11.

---

### Primitive 20: `AnalyzeBalancerPosition`

**Answers:** Q1.1, Q1.2, Q1.3, Q1.4 (on Balancer weighted pools, 2-asset)

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, 2-asset Balancer). 22 tests passing.

**Constructor:** `AnalyzeBalancerPosition()`

**Signature:** `.apply(lp, lp_init_amt, entry_base_amt, entry_opp_amt, holding_period_days=None) → BalancerPositionAnalysis`

**Returns:**
```python
@dataclass
class BalancerPositionAnalysis:
    base_tkn_name: str
    opp_tkn_name: str
    base_weight: float                  # Balancer-distinguishing field
    current_value: float                # Denominated in opp-token units
    hold_value: float
    il_percentage: float
    il_with_fees: float
    fee_income: float                   # Always 0.0 in v1 (see Notes)
    net_pnl: float
    real_apr: Optional[float]
    diagnosis: str                      # "net_positive" | "il_dominant"
    alpha: float                        # current_price / entry_price
```

**Internal calls:** `balancerpy.analytics.risk.BalancerImpLoss`

#### v1 Implementation Notes (2026-04-23)

Sibling to `AnalyzePosition` for Balancer 2-asset weighted pools. Same answer shape (IL decomposition from price divergence) adapted to the weighted AMM's base-weight-dependent IL formula.

**2-asset scope only.** Inherited from BalancerImpLoss. N-asset extension requires extending BalancerImpLoss first and is tracked for future work. N>2 lps raise `ValueError` via BalancerImpLoss's own validation.

**No fee income attribution in v1.** Balancer's `collected_fees` on the vault is pool-level with no per-LP attribution in the pool object. Surfacing a derived fee number would fabricate precision the state doesn't carry. `fee_income = 0.0` always; `il_with_fees == il_percentage`. When fee attribution lands (future balancerpy work), the diagnosis enum expands to three buckets matching AnalyzePosition.

**Numeraire: opp-token units.** All values are in the opp (second) token. Matches BalancerImpLoss's convention; differs from AnalyzePosition's token0 numeraire. Portfolio aggregation normalizes per-pool numeraire to the common first-token symbol via AggregatePortfolio's numeraire rule.

**Fee-free spot from reserves and weights directly.** `spot = (b_opp / w_opp) / (b_base / w_base)` rather than `lp.get_price()` which bakes in the 0.25% SWAP_FEE scale factor. Documented as a Key Internal Convention in PROJECT_CONTEXT.md; any future Balancer primitive wanting spot-for-IL should use the same approach.

**Input: entry amounts, not alpha.** The public surface takes `entry_base_amt` and `entry_opp_amt` for the caller's natural framing ("what did I deposit?") and derives alpha internally. Callers wanting to explore hypothetical alphas should compose with CompareProtocols (symmetric shock) or call BalancerImpLoss.calc_iloss directly.

See `python/prod/primitives/position/AnalyzeBalancerPosition.py` for the implementation.

---

### Primitive 21: `AnalyzeStableswapPosition`

**Answers:** Q1.1, Q1.2, Q1.3, Q1.4 (on Curve-style stableswap pools, 2-asset)

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, 2-asset Stableswap). 21 tests passing.

**Constructor:** `AnalyzeStableswapPosition()`

**Signature:** `.apply(lp, lp_init_amt, entry_amounts, holding_period_days=None) → StableswapPositionAnalysis`

**Returns:**
```python
@dataclass
class StableswapPositionAnalysis:
    token_names: List[str]              # Pool tokens in insertion order
    A: int                              # Amplification coefficient
    per_token_init: List[float]         # Entry composition
    per_token_current: List[float]      # Current composition (pool share)
    current_value: float                # In peg numeraire (tokens 1:1)
    hold_value: float
    il_percentage: Optional[float]      # None in unreachable-alpha regime
    il_with_fees: Optional[float]       # None in unreachable-alpha regime
    fee_income: float                   # Always 0.0 in v1
    net_pnl: Optional[float]            # None in unreachable-alpha regime
    real_apr: Optional[float]
    diagnosis: str                      # "at_peg" | "net_positive" | "il_dominant" | "unreachable_alpha"
    alpha: Optional[float]              # None in unreachable-alpha regime
```

**Internal calls:** `stableswappy.analytics.risk.StableswapImpLoss`, `lp.math_pool.dydx(0, 1, use_fee=False)`

#### v1 Implementation Notes (2026-04-23)

Sibling to `AnalyzePosition` for Stableswap 2-asset pools. Three diagnostic paths route per regime:

**At-peg short-circuit.** Balanced pools (|dydx - 1.0| < 1e-12) skip the IL math and return zero-IL result directly. `StableswapPoolMath._dydx` returns exactly 1.0 at balance (confirmed via source read), so the tolerance is safe. Documented as a Key Internal Convention.

**Off-peg reachable.** Alpha and IL computed via `StableswapImpLoss.calc_iloss(alpha)`. Standard code path.

**Unreachable-alpha regime.** At high A, small depeg targets can correspond to pool compositions that violate the invariant (|ε| > 1). When `StableswapImpLoss` raises `DepegUnreachableError`, v1 catches it and returns a result with the analytical fields (`il_percentage`, `il_with_fees`, `net_pnl`, `alpha`) set to `None`. The V2-style fields (`current_value`, `hold_value`, `per_token_current`) stay populated for reference. `diagnosis` is `"unreachable_alpha"`. Same Optional-fields convention as AssessDepegRisk.

**2-asset scope only.** Inherited from StableswapImpLoss. N>2 raises `ValueError`.

**No fee income attribution in v1.** Same reason as AnalyzeBalancerPosition — no per-LP attribution in stableswappy's pool object. `fee_income = 0.0` always.

**Numeraire: peg.** At peg, all tokens are 1:1, so `current_value = sum(per_token_current)` in peg units. Matches the stableswap family's natural framing for stablecoin pairs.

**Explicit entry as list, not named scalars.** `entry_amounts: List[float]` in pool's insertion order. Supports future N-asset extension cleanly; at v1's N=2, the list has two entries. Differs from AnalyzePosition/AnalyzeBalancerPosition's `entry_x_amt`/`entry_y_amt` pair — the per-primitive input shape follows the protocol's natural math shape.

See `python/prod/primitives/position/AnalyzeStableswapPosition.py` for the implementation.

---

### Primitive 22: `SimulateBalancerPriceMove`

**Answers:** Q2.1, Q5.1, Q5.2 (on Balancer weighted pools, 2-asset)

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, 2-asset Balancer). 22 tests passing.

**Constructor:** `SimulateBalancerPriceMove()`

**Signature:** `.apply(lp, price_change_pct, lp_init_amt) → BalancerPriceMoveScenario`

**Returns:**
```python
@dataclass
class BalancerPriceMoveScenario:
    base_tkn_name: str
    opp_tkn_name: str
    base_weight: float                  # Surfaced for caller interpretability
    new_price_ratio: float              # alpha = 1 + price_change_pct
    new_value: float                    # Position value in opp-token units
    il_at_new_price: float
    fee_projection: Optional[float]     # Always None in v1
    value_change_pct: float
```

**Internal calls:** `balancerpy.analytics.risk.BalancerImpLoss.calc_iloss(alpha, weight=...)`

#### v1 Implementation Notes (2026-04-23)

Sibling to `SimulatePriceMove` for Balancer 2-asset weighted pools. Same "what if price moves X% from here?" framing adapted to the weighted AMM.

**2-asset scope inherited from BalancerImpLoss.** N-asset extension requires extending BalancerImpLoss first.

**Opp-token numeraire matching AnalyzeBalancerPosition.** Differs from AnalyzePosition's token0 numeraire. Base-token price is expressed in opp units; a `price_change_pct = -0.30` means "base token drops 30% in opp units."

**base_weight surfaced on result.** Balancer IL depends on both alpha and weight; surfacing the weight makes the result self-describing for an LLM caller that's reading the dataclass without consulting the pool object.

**Simulate-from-current-state semantics.** Treats the current pool state as the baseline — not a historical entry. For historical-entry framing use AnalyzeBalancerPosition with entry amounts explicit. This matches the V2/V3 sibling's convention.

**fee_projection = None.** Matches the V2/V3 sibling and consistent with AnalyzeBalancerPosition's no-fee-attribution scope.

**Fee-free spot computed directly from reserves and weights** (not `lp.get_price()` which bakes in SWAP_FEE). Matches BalancerImpLoss's internal approach. Documented as a Key Internal Convention.

**Weight-dependence test passed first run.** At 80/20 vs 50/50 under the same shock (-30%), 80/20 has smaller |IL| — the weighted-pool property the primitive is built to expose. This was the highest-risk pre-run assertion; it held without adjustment.

See `python/prod/primitives/position/SimulateBalancerPriceMove.py` for the implementation.

---

### Primitive 23: `SimulateStableswapPriceMove`

**Answers:** Q2.1, Q5.1, Q5.2 (on Curve-style stableswap pools, 2-asset)

**Status:** ✅ Shipped 2026-04-23 (v1.2.0, 2-asset Stableswap). 19 tests passing.

**Constructor:** `SimulateStableswapPriceMove()`

**Signature:** `.apply(lp, price_change_pct, lp_init_amt) → StableswapPriceMoveScenario`

**Returns:**
```python
@dataclass
class StableswapPriceMoveScenario:
    token_names: List[str]              # 2 entries in v1
    A: int                              # Amplification coefficient
    new_price_ratio: float              # current_alpha * (1 + price_change_pct)
    new_value: Optional[float]          # None in unreachable-alpha regime
    il_at_new_price: Optional[float]    # None in unreachable-alpha regime
    fee_projection: Optional[float]     # Always None in v1
    value_change_pct: Optional[float]   # None in unreachable-alpha regime
```

**Internal calls:** `stableswappy.analytics.risk.StableswapImpLoss.calc_iloss`, `lp.math_pool.dydx(0, 1, use_fee=False)`

#### v1 Implementation Notes (2026-04-23)

Sibling to `SimulatePriceMove` for Stableswap 2-asset pools. Clean hold-value identity because of the peg numeraire.

**2-asset scope inherited from StableswapImpLoss.**

**Peg numeraire yields a clean identity.** Because stableswap values tokens 1:1 regardless of which one moved, `hold_value_at_new == current_value` — the hold counterfactual is simulation-invariant. This simplifies the new_value computation to `current_value * (1 + IL)` directly, without needing to re-price the composition at a new spot. Notable contrast with V2/V3 and Balancer where hold_value shifts with price.

**Current-alpha derivation via dydx.** `lp.math_pool.dydx(0, 1, use_fee=False)` gives the current alpha; shocks compound onto existing drift: `new_alpha = current_alpha * (1 + pct)`. Lets the caller probe "how bad could this get" from the pool's current state without first assuming it's balanced.

**At-peg short-circuit via `_AT_PEG_TOL = 1e-12`** matching AnalyzeStableswapPosition. When the simulated alpha is essentially 1.0, return zero IL directly — avoids running the fixed-point solver on an identity case and avoids the degenerate epsilon=0 condition.

**DepegUnreachableError caught → Optional None fields** on numeric outputs (new_value, il_at_new_price, value_change_pct), with populated metadata (token_names, A, new_price_ratio). Same convention as AssessDepegRisk, AnalyzeStableswapPosition, CompareProtocols. At A=200, even a 2% shock triggers the unreachable path.

**fee_projection = None** matching the other SimulatePriceMove siblings.

**Symmetric IL around peg.** Positive and negative shocks of the same magnitude produce the same IL magnitude, matching StableswapImpLoss's derivation. Tested explicitly.

See `python/prod/primitives/position/SimulateStableswapPriceMove.py` for the implementation.

---

## Question → Primitive Mapping

| Question | Primitives Used |
|----------|----------------|
| Q1.1 | `AnalyzePosition` (V2/V3), `AnalyzeBalancerPosition`, `AnalyzeStableswapPosition` |
| Q1.2 | `AnalyzePosition` (V2/V3), `AnalyzeBalancerPosition`, `AnalyzeStableswapPosition` |
| Q1.3 | `AnalyzePosition` (V2/V3), `AnalyzeBalancerPosition`, `AnalyzeStableswapPosition` |
| Q1.4 | `AnalyzePosition` (V2/V3), `AnalyzeBalancerPosition`, `AnalyzeStableswapPosition` |
| Q2.1 | `SimulatePriceMove` (V2/V3), `SimulateBalancerPriceMove`, `SimulateStableswapPriceMove` |
| Q2.2 | `FindBreakEvenPrice` (V2/V3); Balancer/Stableswap extensions pending |
| Q2.3 | `AssessDepegRisk` |
| Q2.4 | `CheckTickRangeStatus` |
| Q3.1 | `EvaluateTickRanges` |
| Q3.2 | `EvaluateTickRanges` |
| Q3.3 | `OptimalDepositSplit` |
| Q3.4 | `EvaluateRebalance` → chains `AnalyzePosition` + `OptimalDepositSplit` + `CalculateSlippage` |
| Q4.1 | `CompareProtocols` |
| Q4.2 | `DiscoverPools` → `CheckPoolHealth` per pool |
| Q4.3 | `CompareFeeTiers` |
| Q5.1 | `SimulatePriceMove` (V2/V3), `SimulateBalancerPriceMove`, `SimulateStableswapPriceMove` — at multiple levels |
| Q5.2 | `SimulatePriceMove` (V2/V3), `SimulateBalancerPriceMove`, `SimulateStableswapPriceMove` — with scaled position |
| Q5.3 | `FindBreakEvenTime` |
| Q6.1 | `AggregatePortfolio` → cross-protocol: `AnalyzePosition` | `AnalyzeBalancerPosition` | `AnalyzeStableswapPosition` |
| Q6.2 | `AggregatePortfolio` |
| Q6.3 | `AggregatePortfolio` |
| Q7.1 | `CheckPoolHealth` |
| Q7.2 | `CheckPoolHealth` |
| Q7.3 | `DetectFeeAnomaly` |
| Q7.4 | `DetectRugSignals` |
| Q7.5 | `CheckPoolHealth` |
| Q8.1 | `CalculateSlippage` |
| Q8.2 | `CalculateSlippage` (inversion mode) |
| Q8.3 | `CompareProtocols` with slippage focus |
| Q8.4 | `EvaluateRebalance` |
| Q8.5 | `DetectMEV` |
| Q9.1 | `AssessLiquidityDepth` |
| Q9.2 | `CalculateSlippage` (price impact framing) |
| Q9.3 | `AssessLiquidityDepth` with position size |
| Q9.4 | `AssessLiquidityDepth` (V3 tick distribution) |
| Q9.5 | `OptimalDepositSplit` with depth awareness |
| Q9.6 | `AssessLiquidityDepth` (concentration index) |

---

## File Structure

```
python/prod/
    process/                    # EXISTING — operations that CHANGE pool state
        swap/
            Swap.py
            WithdrawSwap.py
        join/
            Join.py
        deposit/
            SwapDeposit.py
        liquidity/
            AddLiquidity.py
            RemoveLiquidity.py

    primitives/                 # NEW — operations that ANALYZE pool state
        position/
            AnalyzePosition.py
            SimulatePriceMove.py
            FindBreakEvenPrice.py
            FindBreakEvenTime.py
            __init__.py
        risk/
            AssessDepegRisk.py
            CheckTickRangeStatus.py
            __init__.py
        optimization/
            EvaluateTickRanges.py
            OptimalDepositSplit.py
            EvaluateRebalance.py
            __init__.py
        comparison/
            CompareProtocols.py
            CompareFeeTiers.py
            DiscoverPools.py
            __init__.py
        pool_health/
            CheckPoolHealth.py
            DetectFeeAnomaly.py
            DetectRugSignals.py
            __init__.py
        portfolio/
            AggregatePortfolio.py
            __init__.py
        execution/
            CalculateSlippage.py
            DetectMEV.py
            __init__.py
        depth/
            AssessLiquidityDepth.py
            __init__.py
        __init__.py

    twin/                       # NEW — State Twin construction
        StateTwinProvider.py    # ABC + PoolSnapshot dataclass
        LiveProvider.py         # Web3scout implementation
        MockProvider.py         # Test / notebook implementation
        StateTwinBuilder.py     # Builds exchange object from snapshot
        __init__.py

    agents/                     # EXISTING — legacy agents (frozen for textbook)
        legacy/                 # Renamed from current location
            ImpermanentLossAgent.py
            TVLBasedLiquidityExitAgent.py
            VolumeSpikeNotifierAgent.py
            PriceThresholdSwapAgent.py
```

---

## Implementation Priority

| Priority | Primitives | Rationale |
|----------|-----------|-----------|
| **P0 — Core** | `AnalyzePosition`, `SimulatePriceMove`, `CalculateSlippage` | Answers the most common LP questions. Foundation for all others. |
| **P1 — Risk** | `FindBreakEvenPrice`, `CheckTickRangeStatus`, `AssessLiquidityDepth` | Risk awareness primitives. High user value. |
| **P2 — Optimization** | `OptimalDepositSplit`, `EvaluateRebalance`, `EvaluateTickRanges` | Actionable recommendations. Wraps existing SwapDeposit math. |
| **P3 — Comparison** | `CompareProtocols`, `CompareFeeTiers`, `AggregatePortfolio` | Cross-protocol and portfolio. DeFiMind's unique differentiator. |
| **P4 — Safety** | `CheckPoolHealth`, `DetectRugSignals`, `DetectFeeAnomaly` | Pool viability assessment. Bridges toward Tier 2 vision. |
| **P5 — Advanced** | `FindBreakEvenTime`, `AssessDepegRisk`, `DetectMEV`, `DiscoverPools` | Specialized capabilities. High value but narrower audience. |

---

## Coverage Summary

| Metric | Count |
|--------|-------|
| **Section 1 questions** | 38 |
| **Question categories** | 9 |
| **Section 2 primitives (original spec)** | 19 |
| **Primitives shipped from original spec** | 17 (missing: AssessLiquidityDepth, DiscoverPools) |
| **Cross-protocol sibling primitives** | 5 (AnalyzeBalancerPosition, AnalyzeStableswapPosition, SimulateBalancerPriceMove, SimulateStableswapPriceMove, + AggregatePortfolio extension) |
| **Total primitives shipped** | 22 |
| **Primitive sub-packages** | 8 |
| **New derivations required** | 4 (FindBreakEvenPrice, FindBreakEvenTime, max slippage inversion, tick traversal) |
| **New derivations completed** | 3 (FindBreakEvenPrice V2/V3 closed form, FindBreakEvenTime fee-rate annualization, AssessDepegRisk stableswap-invariant expansion) |
| **New derivations pending** | Tick traversal (AssessLiquidityDepth), FindBreakEven extensions for Balancer and Stableswap |
| **Total test count** | 504 passing |
| **Day-one launch blockers** | 0 |

---

*This document serves as the specification for DeFiPy's primitive layer and DeFiMind's diagnostic capabilities. Section 1 defines what users need. Section 2 defines how the system delivers it. The State Twin architecture connects the two — exact math on exact replicas of on-chain state.*

*DeFiMind.ai · DeFiPy · AnchorRegistry · DeFiMind Corp*
