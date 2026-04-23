# DeFiPy v2.0 Tool Set — MCP Curation vs. Library Coverage

**Status:** Reference document (2026-04-23)
**Context:** Day 1 of the v2.0 push. Authoritative source for which primitives ship as MCP tools in v2.0 and which stay library-only.
**Audience:** The fresh Claude session executing Day 1, any future session revisiting the curation, anyone wondering why `EvaluateRebalance` isn't an MCP tool despite being a powerful primitive.

---

## TL;DR

**Library ships 22 primitives across 8 sub-packages.** ReadTheDocs covers all 22 in full reference depth. MCP tool set for v2.0 exposes **10 curated leaf primitives**.

Two different audiences:
- **Python developers** — see all 22 primitives on ReadTheDocs, can import any of them
- **LLMs via MCP** — see 10 curated tools selected for LLM ergonomics

The curation is tactical, not permanent. More primitives may get promoted to the MCP tool set in v2.1+.

---

## The 10 primitives shipped as MCP tools in v2.0

### Position analysis (6 primitives)

Same LP question answered across four AMM families. The heart of DeFiPy's distinctive positioning.

| Tool name | Sub-package | Protocol | Answers |
|---|---|---|---|
| `AnalyzePosition` | position | Uniswap V2 + V3 | PnL decomposition: IL, fees, net result |
| `AnalyzeBalancerPosition` | position | Balancer (2-asset weighted) | PnL decomposition with weight effects |
| `AnalyzeStableswapPosition` | position | Curve-style Stableswap (2-asset) | PnL decomposition with amplification (A) effects |
| `SimulatePriceMove` | position | Uniswap V2 + V3 | "What if price moves X%?" scenarios |
| `SimulateBalancerPriceMove` | position | Balancer (2-asset weighted) | Same question, weighted-pool math |
| `SimulateStableswapPriceMove` | position | Curve-style Stableswap (2-asset) | Same question, stableswap ε↔δ fixed point |

### Pool health (2 primitives)

| Tool name | Sub-package | Protocol | Answers |
|---|---|---|---|
| `CheckPoolHealth` | pool_health | V2 + V3 | TVL, reserves, fee accrual rate, LP concentration, activity |
| `DetectRugSignals` | pool_health | V2 + V3 | Threshold-based rug signals (TVL floor, LP concentration, inactive-with-liquidity) |

Composition pattern: `DetectRugSignals` chains over `CheckPoolHealth`'s output. Demonstrates the "primitives chain into primitives" property in the MCP tool list itself.

### Risk (1 primitive)

| Tool name | Sub-package | Protocol | Answers |
|---|---|---|---|
| `AssessDepegRisk` | risk | Curve-style Stableswap (2-asset) | IL at 2%, 5%, 10%, 20%, 50% depegs + V2 comparison + reachability flags |

DeFiPy's most architecturally distinctive primitive. Evaluates the stableswap invariant directly in floats rather than driving the integer-math state solvers. Flags physically-unreachable scenarios explicitly.

### Execution (1 primitive)

| Tool name | Sub-package | Protocol | Answers |
|---|---|---|---|
| `CalculateSlippage` | execution | V2 + V3 | Slippage %, price impact %, max trade size at 1% slippage |

---

## The 12 primitives shipped library-only (not MCP tools in v2.0)

Still fully shipped. Fully tested. Full ReadTheDocs reference coverage. Just not in the v2.0 curated MCP tool set.

| Primitive | Sub-package | Reason for MCP exclusion in v2.0 |
|---|---|---|
| `FindBreakEvenPrice` | position | V2/V3 only; Balancer/Stableswap extensions deferred to v2.1. Incomplete parity → defer exposing as tool until extended. |
| `FindBreakEvenTime` | position | Same reason — V2/V3 only pending extensions. |
| `DetectMEV` | execution | Requires caller-supplied actual on-chain output. Awkward in a tool-use flow without LiveProvider context. |
| `CheckTickRangeStatus` | risk | V3-only, narrow. Useful in chained workflows; less compelling as standalone tool. |
| `EvaluateTickRanges` | optimization | V3-only. Composition-heavy. Better as a follow-up call after AnalyzePosition. |
| `EvaluateRebalance` | optimization | Composition of 4 other primitives. Let the LLM compose instead. |
| `OptimalDepositSplit` | optimization | V2-only. Composition with rebalancing workflows. V3 deferred. |
| `CompareFeeTiers` | comparison | V3-only. Multi-pool inputs (N candidates). LLM-composable from CheckPoolHealth + CheckTickRangeStatus. |
| `CompareProtocols` | comparison | Cross-protocol comparison is already implicit in calling the 6 position primitives side-by-side. |
| `AggregatePortfolio` | portfolio | Multi-position breadth-chain. LLM can aggregate by calling AnalyzePosition N times. |
| `DetectFeeAnomaly` | pool_health | V2-only (blocked on UniV3Helper fix). Shape A only. Niche audit use case. |

### Curation principles that produced this list

1. **Protocol parity matters.** Primitives with V2-only or V3-only scope stay off the MCP tool set until their other-protocol siblings ship. `AnalyzePosition` got in (V2+V3 since v1). `FindBreakEvenPrice` did not (no Balancer/Stableswap siblings yet).

2. **Leaf primitives over composition primitives.** The six position analyzers, the two pool-health checks, slippage, and depeg risk are all *leaves* — they read state and compute a result. `EvaluateRebalance` chains four other primitives. An LLM composing from leaves produces equivalent power to chain-primitives and is more flexible. Only expose compositions when they encode irreducible business logic.

3. **State-threading primitives over state-mutating-projection primitives.** `OptimalDepositSplit` and `CompareFeeTiers` are useful but require the caller to know things (candidate fee tiers, target deposit amount) that an LLM would need to reason into. Leaves are safer tool-use calls.

4. **Keep the set small.** Tool-use selection quality degrades as the tool count grows. 10 tools is near the upper edge of what Claude handles cleanly without prompting. More tools ≠ more capability; fewer sharper tools ≠ less capability.

---

## Coverage by AMM family (v2.0 MCP tool set)

| Protocol | Position analysis | Price scenarios | Pool health | Slippage | Depeg |
|---|---|---|---|---|---|
| Uniswap V2 | ✅ AnalyzePosition | ✅ SimulatePriceMove | ✅ CheckPoolHealth + DetectRugSignals | ✅ CalculateSlippage | — |
| Uniswap V3 | ✅ AnalyzePosition | ✅ SimulatePriceMove | ✅ CheckPoolHealth + DetectRugSignals | ✅ CalculateSlippage | — |
| Balancer (2-asset) | ✅ AnalyzeBalancerPosition | ✅ SimulateBalancerPriceMove | ❌ (V2/V3 only) | ❌ (V2/V3 only) | — |
| Stableswap (2-asset) | ✅ AnalyzeStableswapPosition | ✅ SimulateStableswapPriceMove | ❌ (V2/V3 only) | ❌ (V2/V3 only) | ✅ AssessDepegRisk |

**Matrix coverage:** 12 of 16 cells filled for v2.0. Balancer and Stableswap extensions to CheckPoolHealth/DetectRugSignals/CalculateSlippage are Bucket A Phase 2 work.

---

## LP questions the v2.0 MCP tool set answers

Full coverage (answerable on all 4 AMM families):
- Q1.1 — Why is my position losing money?
- Q1.2 — Am I actually earning anything after IL?
- Q1.3 — What's my real APR including IL?
- Q1.4 — How much have I actually earned in fees?
- Q2.1 — What happens if price drops X%?
- Q5.1 — What happens to my position in a market crash?
- Q5.2 — If I add more liquidity, how does risk change?

Partial coverage (V2/V3 only for v2.0):
- Q7.1 — Is this pool behaving correctly?
- Q7.2 — Are reserves consistent with TVL?
- Q7.4 — Is this pool a likely rug?
- Q7.5 — Is this pool economically viable?
- Q8.1 — What's my actual slippage?
- Q8.2 — What's the max trade size before slippage exceeds X%?
- Q9.2 — What's the price impact?

Stableswap-specific:
- Q2.3 — How exposed am I to a depeg? (AssessDepegRisk with 5 scenarios + V2 benchmark)

Not covered by v2.0 MCP tool set (but answerable via library primitives or deferred to v2.1):
- Q2.2 (Break-even price), Q2.4 (Tick range status), Q3.1-Q3.4 (Optimization), Q4.1-Q4.3 (Comparison), Q5.3 (Break-even time), Q6.1-Q6.3 (Portfolio), Q7.3 (Fee anomaly), Q8.3 (Cross-protocol slippage), Q8.4 (Rebalance slippage), Q8.5 (MEV detection), Q9.1, Q9.3-Q9.6 (Liquidity depth)

---

## Tool-description guidance for Day 1

Each of the 10 tools needs a hand-curated description in `python/prod/tools/registry.py`. The description is what Claude reads when deciding whether to call the tool. A few principles:

### Keep it short
Claude reads all 10 descriptions on every tool-selection decision. Bloat degrades selection quality. Target: 2-4 sentences per tool.

### Lead with the question it answers, not the math
```python
# GOOD
"Analyze why a Uniswap V2/V3 LP position is gaining or losing money. "
"Decomposes PnL into impermanent loss, accumulated fees, and net result. "
"Returns structured dataclass with diagnosis."

# BAD (too mathy)
"Computes UniswapImpLoss-based PnL decomposition using hand-derived "
"closed-form IL expressions with fee accumulation."
```

### Name the protocols explicitly
Claude needs protocol information to pick between siblings:
```python
"AnalyzePosition" → "... Uniswap V2 and V3 positions."
"AnalyzeBalancerPosition" → "... 2-asset Balancer weighted pool positions."
"AnalyzeStableswapPosition" → "... 2-asset Curve-style Stableswap positions."
```

### Mention reachability/scope limitations
For primitives with non-obvious edges (like Stableswap unreachable-alpha regime), flag them:
```python
"AssessDepegRisk" → "... Returns IL at multiple depeg levels. "
                    "Some levels may be physically unreachable at high A; "
                    "these are flagged explicitly in the response."
```

### Don't embed the full dataclass definition
Claude gets the JSON Schema from `input_schema`. The description is prose about purpose, not field-by-field reference.

---

## Day 1 verification

Gate for Day 1 passing:

```python
from defipy.tools import get_schemas

schemas = get_schemas("mcp")
assert len(schemas) == 10
assert {s["name"] for s in schemas} == {
    "AnalyzePosition",
    "AnalyzeBalancerPosition",
    "AnalyzeStableswapPosition",
    "SimulatePriceMove",
    "SimulateBalancerPriceMove",
    "SimulateStableswapPriceMove",
    "CheckPoolHealth",
    "DetectRugSignals",
    "CalculateSlippage",
    "AssessDepegRisk",
}
```

If that passes, Day 1 is done. Tests in `python/test/tools/test_schemas.py` should additionally verify:
- Each schema has required MCP fields (name, description, input_schema)
- Each input_schema is valid JSON Schema
- Each tool's input maps to a real `.apply()` signature on the primitive
- Descriptions are under ~4 sentences (length cap enforcement)

---

## v2.1+ candidate promotions

Primitives likely to join the MCP tool set in v2.1 once blockers clear:

| Primitive | Currently blocked on |
|---|---|
| `FindBreakEvenPrice` | Balancer + Stableswap break-even derivations (Bucket B math work) |
| `FindBreakEvenTime` | Same + fee-rate estimation story for Balancer/Stableswap |
| `CompareProtocols` | Once all four protocols have slippage and position-analysis parity, this becomes powerful as a single tool call |
| `AggregatePortfolio` | Once DeFiMind has session memory, portfolio aggregation across multiple tool calls becomes natural |
| `DetectFeeAnomaly` | UniV3Helper fee-passthrough fix (backlog item on uniswappy) |
| `AssessLiquidityDepth` | Doesn't exist yet — V3 tick-walking implementation needed first |

Each of these has a clear trigger for v2.0-to-v2.1 promotion. Keep this list up to date as blockers clear.

---

## Relationship to the ReadTheDocs Primitives section

The v2.0 ReadTheDocs Primitives section covers **all 22 primitives** across the sub-package taxonomy. The v2.0 MCP tool set selects 10. These are independent curation decisions:

- **ReadTheDocs Primitives section** organizes by *category* (Position Analysis, Pool Health, Risk, Optimization, Comparison, Execution, Portfolio, Break-Even). All 22 are reachable.
- **MCP tool set** selects *leaves across categories* with v2.0-complete protocol parity and single-call ergonomics. 10 are exposed.

The **Agentic DeFi → Tool Schemas** doc section on ReadTheDocs should link to this `V2_TOOL_SET.md` file for the curation rationale, so readers understand why library has more than MCP exposes.

---

*This doc is authoritative for v2.0. If `DEFIPY_V2_AGENTIC_PLAN.md` and this doc disagree about what's in the MCP tool set, this doc wins. Update both when the tool set changes in v2.1+.*
