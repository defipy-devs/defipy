# DeFiMind — Tier 1 Question Catalog

**Date:** April 16, 2026  
**Status:** Working document — expanding through iterative review

---

## How DeFiMind Works: The State Twin Architecture

DeFiMind's diagnostic capability rests on a single architectural concept: the **State Twin** — a mathematically exact, off-chain replica of on-chain pool state.

Diagnosing a DeFi position requires running calculations that are impossible to perform on-chain: scenario simulation, cross-protocol comparison, historical decomposition, and optimization. You cannot ask a smart contract "what would my IL be if price moved 30%?" You cannot run a Curve stableswap invariant against a Uniswap pool's reserves to compare IL profiles. You cannot rewind a pool to your entry block and replay the math forward. These operations require a local twin of the pool that can be interrogated, mutated, and stress-tested without touching the blockchain.

The State Twin is only useful if the math is exact. An approximate twin gives approximate answers — useless for financial diagnostics where the difference between 3.1% IL and 3.8% IL determines whether a position is net profitable. DeFiPy's hand-derived AMM formulas provide the mathematical precision required for the twin to be trustworthy.

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

### Protocol-Specific Twins

- **Uniswap V2:** Constant product invariant `x × y = k`, fee-integrated swap math
- **Uniswap V3:** Concentrated liquidity, `sqrtPriceX96` encoding, tick-range positioning
- **Balancer:** Weighted invariant `∏(Bᵢ^wᵢ) = k`, weight-adjusted swap math
- **Curve:** Stableswap polynomial `A·n^n·∑xᵢ + D = A·D·n^n + D^(n+1)/(n^n·∏xᵢ)`

---

## 38 Questions Across 9 Categories — Zero Launch Blockers

### Category 1: Position Diagnostics — *"What's happening to my money?"*
- Q1.1 — Why is my position losing money?
- Q1.2 — Am I actually earning anything after IL?
- Q1.3 — What's my real APR including IL?
- Q1.4 — How much have I actually earned in fees?

### Category 2: Risk Assessment — *"Should I be worried?"*
- Q2.1 — What happens if price drops X%?
- Q2.2 — At what price do I start losing money overall?
- Q2.3 — How exposed am I to a depeg?
- Q2.4 — Is my tick range about to go out of range?

### Category 3: Optimization — *"What should I do differently?"*
- Q3.1 — Is my tick range too wide or too narrow?
- Q3.2 — Should I split into multiple positions?
- Q3.3 — What's the optimal amount to deposit right now?
- Q3.4 — Should I rebalance now or wait?

### Category 4: Cross-Protocol Comparison — *"Am I in the right pool?"*
- Q4.1 — Is Curve better than Uniswap for this pair?
- Q4.2 — What's the best pool for this token pair across all protocols?
- Q4.3 — Should I move to a different fee tier?

### Category 5: Scenario Planning — *"What if?"*
- Q5.1 — What happens to my position in a market crash?
- Q5.2 — If I add more liquidity, how does that change my risk?
- Q5.3 — How long do I need to stay in to break even?

### Category 6: Portfolio Level — *"Big picture across all my positions"*
- Q6.1 — What's my total IL across all my positions?
- Q6.2 — Which of my positions should I exit first?
- Q6.3 — How correlated are my positions?

### Category 7: Pool Health & Viability — *"Is this pool worth entering?"*
- Q7.1 — Is this pool behaving mathematically correctly?
- Q7.2 — Are the reserves consistent with the claimed TVL?
- Q7.3 — Is the fee structure what it claims to be?
- Q7.4 — Is this pool a likely rug pull candidate?
- Q7.5 — Is this pool economically viable?

### Category 8: Slippage & Execution — *"How much am I losing on the swap itself?"*
- Q8.1 — What's my actual slippage on a trade of this size?
- Q8.2 — What's the maximum trade size before slippage exceeds X%?
- Q8.3 — How does slippage compare across protocols for this pair?
- Q8.4 — What's the slippage cost of rebalancing my position?
- Q8.5 — Am I being frontrun?

### Category 9: Liquidity Depth — *"Can this pool handle my trade?"*
- Q9.1 — How deep is this pool at current price?
- Q9.2 — What's the price impact of my trade?
- Q9.3 — Is there enough liquidity for me to exit my position?
- Q9.4 — Where are the liquidity cliffs in this V3 pool?
- Q9.5 — How much can I deposit without significantly moving the price?
- Q9.6 — Is this pool's liquidity concentrated or distributed?

---

## Coverage Summary

| Metric | Count |
|--------|-------|
| **Total questions** | 38 |
| **Categories** | 9 |
| **Zero gaps — math exists today** | 24 |
| **Composition of existing primitives** | 6 |
| **New derivations needed (straightforward)** | 4 |
| **New wrappers needed** | 3 |
| **Needs external data** | 3 |
| **Day-one launch blockers** | 0 |

---

Full details, primitive mappings, and gap analysis in repo at:
/Users/ian_moore/repos/defipy/DEFIMIND_TIER1_QUESTIONS.md

*DeFiMind.ai · DeFiPy · AnchorRegistry · DeFiMind Corp*
