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

**Constructor:** `AssessDepegRisk(depeg_levels=[0.02, 0.05, 0.10])`

**Signature:** `.apply(lp, position_size_lp) → DepegRiskAssessment`

**Returns:**
```python
@dataclass
class DepegScenario:
    depeg_pct: float
    il_at_depeg: float
    position_value_at_depeg: float

@dataclass
class DepegRiskAssessment:
    protocol_type: str          # "stableswap" | "constant_product" | "weighted"
    scenarios: list[DepegScenario]
    current_peg_deviation: float
```

**Internal calls:** Stableswap invariant evaluation, `UniswapImpLoss.calc_iloss()` for comparison

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

**Constructor:** `OptimalDepositSplit()`

**Signature:** `.apply(lp, token_in, amount_in, lwr_tick=None, upr_tick=None) → DepositSplitResult`

**Returns:**
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

---

### Primitive 9: `EvaluateRebalance`

**Answers:** Q3.4, Q8.4

**Constructor:** `EvaluateRebalance()`

**Signature:** `.apply(lp, entry_lp, token_in, position_size_lp, new_lwr_tick=None, new_upr_tick=None) → RebalanceEvaluation`

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

---

### Primitive 10: `CompareProtocols`

**Answers:** Q4.1, Q8.3

**Constructor:** `CompareProtocols()`

**Signature:** `.apply(lp_a, lp_b, amount, token=None) → ProtocolComparison`

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

---

### Primitive 11: `CompareFeeTiers`

**Answers:** Q4.3

**Constructor:** `CompareFeeTiers()`

**Signature:** `.apply(lp, position_size, fee_tiers=[100, 500, 3000, 10000]) → FeeTierComparison`

**Returns:**
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

---

### Primitive 12: `AggregatePortfolio`

**Answers:** Q6.1, Q6.2, Q6.3

**Constructor:** `AggregatePortfolio()`

**Signature:** `.apply(positions: list[tuple[lp, entry_lp, size]]) → PortfolioAnalysis`

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

**Constructor:** `DetectFeeAnomaly()`

**Signature:** `.apply(lp, token_in, test_amount) → FeeAnomalyResult`

**Returns:**
```python
@dataclass
class FeeAnomalyResult:
    stated_fee_bps: int
    theoretical_output: float       # What math says you should get
    actual_output: float            # What the contract returns (if available)
    discrepancy_bps: float          # Difference in basis points
    anomaly_detected: bool
```

**Internal calls:** `lp.get_amount_out()` vs `LPQuote.get_amount()` with fee parameters

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

## Question → Primitive Mapping

| Question | Primitives Used |
|----------|----------------|
| Q1.1 | `AnalyzePosition` |
| Q1.2 | `AnalyzePosition` |
| Q1.3 | `AnalyzePosition` |
| Q1.4 | `AnalyzePosition` |
| Q2.1 | `SimulatePriceMove` |
| Q2.2 | `FindBreakEvenPrice` |
| Q2.3 | `AssessDepegRisk` |
| Q2.4 | `CheckTickRangeStatus` |
| Q3.1 | `EvaluateTickRanges` |
| Q3.2 | `EvaluateTickRanges` |
| Q3.3 | `OptimalDepositSplit` |
| Q3.4 | `EvaluateRebalance` → chains `AnalyzePosition` + `OptimalDepositSplit` + `CalculateSlippage` |
| Q4.1 | `CompareProtocols` |
| Q4.2 | `DiscoverPools` → `CheckPoolHealth` per pool |
| Q4.3 | `CompareFeeTiers` |
| Q5.1 | `SimulatePriceMove` at multiple levels |
| Q5.2 | `SimulatePriceMove` with scaled position |
| Q5.3 | `FindBreakEvenTime` |
| Q6.1 | `AggregatePortfolio` → multiple `AnalyzePosition` |
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
| **Section 2 primitives** | 19 |
| **Primitive sub-packages** | 8 |
| **New derivations required** | 4 (FindBreakEvenPrice, FindBreakEvenTime, max slippage inversion, tick traversal) |
| **Day-one launch blockers** | 0 |

---

*This document serves as the specification for DeFiPy's primitive layer and DeFiMind's diagnostic capabilities. Section 1 defines what users need. Section 2 defines how the system delivers it. The State Twin architecture connects the two — exact math on exact replicas of on-chain state.*

*DeFiMind.ai · DeFiPy · AnchorRegistry · DeFiMind Corp*
