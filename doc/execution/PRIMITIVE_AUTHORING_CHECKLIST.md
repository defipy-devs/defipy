# Primitive Authoring Checklist

Mechanical checklist for adding a new primitive to DeFiPy. Keeps primitives
2 through 19 stylistically and structurally consistent with `AnalyzePosition`
(primitive 1), and prevents the slow drift that accumulates when each
primitive invents its own setup, test, or dataclass conventions.

Follow this exactly for the first several primitives. Once the pattern is
muscle memory, read it as a reference rather than a script.

---

## 1. Where things live

| What | Path |
|---|---|
| Implementation | `python/prod/primitives/<category>/<Primitive>.py` |
| Result dataclass | `python/prod/utils/data/<r>.py` |
| Tests | `python/test/primitives/<category>/test_<primitive>.py` |

Categories (from `DEFIMIND_TIER1_QUESTIONS.md`):

- `position/` — position-level analytics (AnalyzePosition lives here)
- `risk/` — risk-surface primitives (variance, VaR, correlation)
- `optimization/` — find-optimal-X primitives
- `comparison/` — compare two positions or two pools
- `pool_health/` — pool-state diagnostics
- `portfolio/` — multi-position aggregates
- `liquidity/` — entry/exit/rebalance execution reasoning

Create the category directory with an empty `__init__.py` if it doesn't
exist yet. Mirror the structure on the test side.

---

## 2. Implementation style

Match `primitives/position/AnalyzePosition.py` as the reference template:

- **License header** — Apache 2.0 block with `Copyright 2023–2026 Ian Moore`,
  `Email: defipy.devs@gmail.com`, em-dash horizontal rules.
- **Docstrings** — numpy style with `Parameters` and `Returns` sections
  delimited by `----------` bars. Include a `Notes` section when there's
  non-obvious behavior.
- **No type hints in class signatures** — matches uniswappy's `process/`
  style. Dataclasses do use annotations.
- **Spaces around `=` in kwargs** — `lwr_tick = None` not `lwr_tick=None`.
- **`apply()` is the main verb** — stateless construction (`__init__`
  takes minimal args or none), computation happens in `.apply()`.
- **Private helpers prefixed `_`** — e.g., `_diagnose`, `_calc_X`.
- **Blank line after class-level docstring** — before `__init__`.
- **Return a structured dataclass**, not a tuple or dict.

---

## 3. Result dataclass style

Match `utils/data/PositionAnalysis.py`:

- One dataclass per file, same name as the file — this is the default.
- **Exception: nested components of a result can colocate with their
  parent.** `PositionSummary` lives inside `PortfolioAnalysis.py` because
  it's a structural piece of `PortfolioAnalysis` rather than a standalone
  result. `DepegScenario` lives inside `DepegRiskAssessment.py` for the
  same reason. Use judgment: if a dataclass is only meaningful as a
  field of another dataclass, colocate it; if it stands alone as a
  primitive result, give it its own file.
- Stdlib `@dataclass` decorator (not `attrs`).
- Explicit field types on every field.
- `Optional[T]` for fields that legitimately may be None — including
  fields that are populated only in certain regimes of the primitive's
  input (e.g., AssessDepegRisk's value fields are `Optional[float]`
  because they're `None` when a requested depeg is physically
  unreachable for the pool's A).
- **Signed-quantity conventions should be documented on the field itself.**
  DetectFeeAnomaly's `discrepancy_bps` is signed (positive = pool
  underdelivers, negative = overdelivers), and its `direction` field
  restates that convention as a discrete label. Callers should be
  able to read the field's dataclass docstring and know the sign
  convention without reading the primitive's implementation.
- Short class-level docstring explaining what the result represents.

---

## 4. Wire it into the `__init__.py` chain

Three places must be updated for a new primitive:

1. **`python/prod/primitives/<category>/__init__.py`** —
   `from .<Primitive> import <Primitive>`

2. **`python/prod/primitives/__init__.py`** —
   If the category is new: `from .<category> import *`
   If existing: already covered by the wildcard chain, nothing to do.

3. **`python/prod/utils/data/__init__.py`** —
   `from .<r> import <r>`
   If the result file exports multiple dataclasses (e.g., a parent
   result and a nested component), export all of them:
   `from .<r> import <Parent>, <Nested>`

---

## 5. Test file structure

Pattern: `python/test/primitives/<category>/test_<primitive>.py`

Use the shared fixtures from `python/test/primitives/conftest.py`:

- `v2_setup` — fresh V2 LP, USER owns 100%, 1000 ETH / 100000 DAI at entry.
- `v3_setup` — fresh V3 LP, full-range ticks (tick_spacing=60, fee=3000),
  same entry amounts.

Both return dataclasses with `.lp`, `.eth`, `.dai`, `.lp_init_amt`,
`.entry_x_amt`, `.entry_y_amt` (V3 adds `.lwr_tick`, `.upr_tick`).

**Multi-pool tests.** If a primitive needs additional pools beyond the
fixture's single V2 and single V3, build them inline with small helpers
at the top of the test file. Don't extract a shared multi-pool fixture
until the second consumer shows up — the right shape of the shared
fixture is hard to guess from one consumer's needs (AggregatePortfolio
wants uniform-numeraire portfolios; CompareProtocols will want
cross-protocol pairs; CompareFeeTiers will want one pair at multiple
fee tiers — unlikely to be solvable by one fixture).

**Parameterized builders for regime coverage.** When a primitive's
behavior changes with a pool parameter (e.g., AssessDepegRisk's
behavior flips between reachable and unreachable regimes based on
amplification coefficient A), use a parameterized builder like
`_build_pool(ampl, n_assets=2)` and split the test class by regime
(`TestAssessDepegRiskHighA` at A=200, `TestAssessDepegRiskLowA` at
A=10). Each regime gets its own setUp and exercises the behavior the
regime surfaces.

**V3-rejection classes.** When a primitive is scoped V2-only (e.g.,
DetectFeeAnomaly) or stableswap-only (e.g., AssessDepegRisk), include
a dedicated small test class that wires up the *other* protocol's
fixture and asserts the expected ValueError. Keeps the scope
boundary visible in the test suite, not only in the docstring. See
`TestDetectFeeAnomalyV3Rejection` for the minimal pattern.

### Example test class skeleton

```python
import pytest
import unittest
from uniswappy.process.swap import Swap

from defipy.utils.data import MyResult
from defipy.primitives.<category> import MyPrimitive

USER = "user0"


class TestMyPrimitive(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def _bind_setup(self, v2_setup):
        self.setup = v2_setup

    def _invoke(self, **kwargs):
        """Helper to keep per-test call sites compact."""
        return MyPrimitive().apply(
            self.setup.lp,
            self.setup.lp_init_amt,
            self.setup.entry_x_amt,
            self.setup.entry_y_amt,
            **kwargs,
        )

    # ─── Tests here ─────────────────────────────────────────────
```

Create a category-level `__init__.py` (empty) so pytest can discover the
test package.

---

## 6. Test coverage — minimum ~10 tests per primitive

Cover these categories (adapt naming to the primitive's semantics):

- **Shape / return type** — correct dataclass returned, all fields populated,
  field types correct.
- **Entry / boundary conditions** — sensible values at identity inputs
  (no price move, no swap, zero holding period).
- **Post-state-change behavior** — after a swap or parameter shift, results
  move in the expected direction.
- **Monotonicity / invariants** — domain-specific properties the math
  guarantees (e.g., "IL with fees is never strictly worse than raw IL").
- **Edge cases** — zero inputs, missing optional params, extreme values.
- **Classification / diagnosis outputs** — if the primitive returns a string
  category, cover each possible category.
- **Threshold ceilings/floors** — if the primitive takes a threshold with
  a meaningful upper or lower bound (e.g., a concentration fraction in
  `(0, 1]`, a TVL floor ≥ 0), write an explicit test at the ceiling/floor
  value. Session 2026-04-21 lost a cycle to a `>=` vs. `>` bug at
  `threshold=1.0` that would have been caught here.
- **Breadth-chain totals** — for primitives that aggregate across N
  positions or pools, explicitly test that scalar totals equal the sum
  of per-item values, and that per-item ordering matches the input.
- **Independent-oracle cross-check** — for invariant-math primitives
  (see §10), write a separate reference implementation of the same
  math in the test file and assert the primitive matches it to tight
  precision. The reference and the primitive share a derivation but
  diverge in code paths; a bug in either shows up as a test mismatch.
  See `_reference_il` in `test_assess_depeg_risk.py`.
- **Twin/state non-mutation** — any primitive that reads `lp` state and
  claims to be non-mutating should have an explicit test asserting
  reserves (and other mutable state) are unchanged after `.apply()`.
  Matters especially for primitives that run synthetic trades through
  the math (DetectFeeAnomaly, SimulatePriceMove) where the temptation
  to actually execute on the pool is real.

---

## 7. Definition of done

A primitive is shipped when:

- [ ] ~10 or more tests pass locally
- [ ] `./resources/run_clean_test_suite.sh --with-defipy` goes green
- [ ] The three `__init__.py` files are updated
- [ ] Docstring includes purpose, numpy-style parameters, return type, and
      any non-obvious behavior in a `Notes` section
- [ ] Entry added to the "Completed primitives" list below
- [ ] Git commit references the primitive name and test count

---

## 8. Composition primitives (additional guidance)

A composition primitive is one that calls another primitive's `.apply()`
internally rather than reading `lp` state directly. DetectRugSignals
(depth-chain over CheckPoolHealth) and AggregatePortfolio (breadth-chain
over AnalyzePosition) are the two shapes shipped so far.

Extra rules that apply when writing one:

- **Read only the dependency's output, not raw `lp`.** If the data you
  need isn't on the returned dataclass, either extend the dependency to
  expose it or put the signal on a different primitive. Mixing direct
  `lp.*` access with a composed primitive call makes the composability
  claim leaky.
- **Step through each threshold's ceiling case before writing the
  comparator.** Strict vs. non-strict inequality matters at the
  boundary. Pick the comparator per signal's intuitive meaning, not
  by symmetry.
- **V3 degradation is inherited.** If the dependency reports `None` for
  V3 on a field you need (e.g., `CheckPoolHealth.num_swaps`), the
  composing primitive must document that gracefully — either skip the
  signal with a note in `details`, or raise cleanly. Do not silently
  treat `None` as zero or false.
- **Carry the dependency's result on your own result.** Callers who got
  a useful verdict often want the underlying numbers. Keeping the
  dataclass attached (e.g., `RugSignalReport.pool_health: PoolHealth`,
  `PositionSummary.analysis: PositionAnalysis`) avoids a double-fetch
  and reinforces the composability pattern.

### 8a. Depth-chain shape (one primitive composed over another)

- Single dependency call, result feeds threshold logic or derived signals.
- Output is typically one dataclass with signal booleans and a summary
  field.
- Example: `DetectRugSignals` → `CheckPoolHealth` → `RugSignalReport`.

### 8b. Breadth-chain shape (same primitive applied N times)

- Input is a list of items; primitive iterates, calls the dependency on
  each, and aggregates.
- Require shape homogeneity at the input level — raise cleanly if inputs
  mix incompatible shapes (e.g., AggregatePortfolio requires uniform
  token0 across positions).
- Preserve caller input order in the per-item result list; expose
  ordering-by-metric via a separate ranking field.
- Totals in scalar fields should match per-item sums; include an
  explicit test that does `sum(item.X for item in positions) ==
  total_X`.
- Example: `AggregatePortfolio` → N × `AnalyzePosition` →
  `PortfolioAnalysis`.

### 8c. Field naming for composition primitives

- **Signal surfacer, not verdict generator.** `pnl_ranking` not
  `exit_priority`; `shared_exposure_warnings` not `correlation_warnings`;
  `signals_detected` not `is_rug`. The primitive exposes numbers and
  orderings; the judgment belongs to the caller.
- **Spec-level verdict names are a recurring pattern worth pushing back
  on during design.** The Tier 1 spec was written at a higher level of
  abstraction than the primitives themselves, and some of its field
  names (`correlation_warnings`, `exit_priority`, `recommendation`)
  overpromise what the math actually delivers. Rename during design
  with the user's sign-off; document the rename reasoning in the
  primitive's docstring Notes section.

---

## 9. The "three rounds, then rethink" rule

If a primitive's implementation has required three or more rounds of
local fixes against failing tests, stop adding fixes and reconsider
the approach. The fourth fix is almost never the right move.

Pattern that emerged in session 2026-04-22 on `AssessDepegRisk`:

- Round 1: modeling error (wrong function to compute LP value)
- Round 2: unit-conversion bug in the same code path
- Round 3: reachability assumption violated by the engine's
  non-convergence regime
- Round 4: would have been another local patch against the same
  structurally-wrong approach

The *approach* was "drive stableswappy's integer-math Newton solver
to a target counterfactual state, then read balances out." The
solver wasn't designed for that kind of backward reconstruction at
extreme balance ratios, and each local fix was papering over a
symptom of that mismatch. Rewriting the primitive to evaluate the
stableswap invariant directly in floats (Option B in the session
transcript) shipped first try with 22 tests passing.

Concrete rule: when you reach round 3, before patching further, ask:
"is this approach compatible with what my dependency was designed
for?" If no, propose an alternative approach, name it explicitly
(not as a disguised patch), and get user sign-off before reimplementing.

---

## 10. Invariant-math primitives

Most primitives in DeFiPy drive the protocol library — they ask the
pool object "what would happen if this trade or composition change
were applied." Some primitives answer a different kind of question:
"what's the relationship between pool composition and price, given
the invariant the pool obeys?" For those questions, evaluating the
invariant directly in floats is often cleaner than driving the
protocol library's state-transition machinery to a counterfactual
target.

`AssessDepegRisk` is the first primitive of this shape. It uses
stableswappy as a read-only metadata adapter (`isinstance` check,
`A`, `N`, balances, LP supply, decimals) and performs the core
math — a closed-form expansion of the stableswap invariant — in
pure floats. No `get_y`, no `get_D`, no Newton iteration on pool
state, no deep-copying of `math_pool`.

`DetectFeeAnomaly` is a second, smaller example: the primitive
computes theoretical swap output from the constant-product formula
in pure floats, then compares to `lp.get_amount_out`. The V2 pool
object is used only as a metadata source (reserves, token
identities) plus a single query call for the actual output. The
invariant math and the pool's math are the two things being
compared; neither drives the other.

### 10a. When to use the invariant-math approach

Prefer direct invariant evaluation when:

- The question is about a *counterfactual pool state* the caller
  specifies (e.g., "what if dydx were X?"), and the protocol
  library doesn't have a cheap/safe way to construct that state.
- The protocol library's solvers (Newton loops, integer-math
  convergence) don't have iteration caps, and the state the
  caller wants is at the edge of or past the solvers' designed
  operating envelope.
- A closed-form or fixed-point expansion of the invariant is
  tractable. For stableswap at N=2, the `ε ↔ δ` relationship is
  a 1D fixed point that converges in ~5 iterations. For N>2 or
  higher-order accuracy, it gets harder; scope honestly.
- The primitive's purpose is a *consistency check* between
  invariant math and pool math (DetectFeeAnomaly). Here the
  invariant is the reference implementation; the pool is the
  subject of the test.

Prefer protocol-library-driven state threading when:

- The question is about a *forward trajectory*: "if I do this
  swap, then this deposit, what happens?" The protocol library
  is specifically designed for that and its solvers are well-
  conditioned on the regime.
- The question requires fee accounting, admin-fee handling, or
  other protocol-specific bookkeeping that lives in the library
  and isn't part of the pure invariant.

### 10b. Implementation pattern

Three layers, cleanly separated:

1. **Adapter layer**: extract scalars from the `lp` object.
   Keep this small (~20 lines). No math here.
2. **Validation layer**: type check, parameter bounds,
   protocol-specific constraints (e.g., N=2, V2-only).
3. **Computation layer**: pure-float math on the extracted
   scalars. No `lp` reference visible at this layer.

Future consideration: if a second primitive wants the same
computation layer, extract it as a module-level pure function
and have the primitive call it. The split gives quants a direct
math entry point separate from the LP-adapter entry point. No
current primitive needs this refactor, but the structure supports
it cleanly when it arrives.

### 10c. Reachability semantics

Invariant-math primitives can be asked questions that have no
physical solution (e.g., "IL at δ=0.02 in a pool with A=200"
requires `|ε| > 1`, which violates the invariant). When this
happens, the primitive should flag unreachability explicitly,
not silently return the closest reachable approximation.

Convention: fields that depend on a reachable pool state are
`Optional[T]`, set to `None` when the target is unreachable.
Fields independent of pool state (e.g., the V2 closed-form
comparison in `DepegScenario.v2_il_comparison`) remain
populated even in unreachable scenarios. Callers can check
`il_pct is None` to distinguish reachable from unreachable
without guessing at a sentinel value.

### 10d. Scope honestly when the tooling diverges from expectations

Session 2026-04-22's DetectFeeAnomaly discovered a latent issue
during implementation: `UniV3Helper.quote` (the available
non-mutating V3 quote path) hard-codes `fee = 997` rather than
reading `lp.fee`. This means a 0.05% V3 pool's quote helper
returns values as if fee were 0.3%, diverging from actual swap
behavior. That's exactly the kind of internal inconsistency
DetectFeeAnomaly was built to surface — but it also means the
primitive can't trust the helper as a ground-truth "actual
output" path on V3.

The right response was to scope the primitive V2-only and
document why, rather than paper over the issue with a synthetic
fix. The V3 extension is tracked in the PROJECT_CONTEXT cleanup
backlog; it needs a non-mutating V3 quote path that honors
`lp.fee` before DetectFeeAnomaly can honestly extend to V3.

The general pattern: when reading protocol-library source
reveals that a needed helper has limitations the caller didn't
expect, don't invent a workaround in the primitive layer.
Scope the primitive narrower than planned, document the
limitation, track the fix in the backlog, and ship small. Three
primitives this month have done this (`CalculateSlippage`
max-size V2-only, `CheckPoolHealth.num_swaps` V2-only,
`DetectFeeAnomaly` V2-only); the pattern is honest and
sustainable.

---

## 11. Cross-protocol extension pattern

When a primitive is V2/V3-specific but the question it answers is
protocol-independent (IL decomposition, PnL, break-even,
slippage), the right shape is sibling primitives — one per AMM
family — rather than a single primitive with branchy isinstance
dispatch.

The shipped pattern at the defipy level:

- `AnalyzePosition` — V2/V3 (UniswapExchange), returns `PositionAnalysis`
- `AnalyzeBalancerPosition` — Balancer 2-asset, returns `BalancerPositionAnalysis`
- `AnalyzeStableswapPosition` — Stableswap 2-asset, returns `StableswapPositionAnalysis`

This mirrors the sibling-repo IL helpers (`UniswapImpLoss` /
`BalancerImpLoss` / `StableswapImpLoss`) one layer down. Each
analyzer stays focused on its protocol's natural math and API
shape; dispatch happens at the *composition* layer
(AggregatePortfolio's isinstance-based router), which is the
correct home for it.

### 11a. When to use sibling primitives

- The question is protocol-independent (the LP wants to know
  their PnL / IL / break-even / slippage regardless of which AMM
  they're in), but the math differs by protocol (V2/V3 CP-with-
  fee, Balancer weighted, Stableswap invariant).
- Each protocol's result has its own *natural fields* that don't
  make sense for the others. Weighted pools carry `base_weight`;
  stableswap pools carry `A` and `per_token_*` lists; V2/V3 carry
  neither. Forcing one dataclass to hold all of them inflates the
  API and makes V2/V3 callers reason about Optional fields they
  never use.
- The underlying math primitives in the sibling repos already
  follow the same pattern (UniswapImpLoss, BalancerImpLoss,
  StableswapImpLoss). Mirroring the structure one layer up
  preserves the mapping between "where does the math live" and
  "where does the primitive live."

### 11b. What sibling primitives share

- **`.apply()` entry point.** Stateless construction, computation
  in `.apply()`, typed dataclass return — same contract as every
  other primitive.
- **Core scalar fields.** `current_value`, `hold_value`,
  `il_percentage`, `il_with_fees`, `fee_income`, `net_pnl`,
  `real_apr`, `diagnosis`, `alpha`. These are the fields
  composition primitives extract uniformly (see §11d).
- **Diagnosis convention.** Enum labels are the same language
  (`net_positive`, `il_dominant`, `fee_compensated` when fee
  attribution is available). Scope can narrow per protocol —
  Balancer and Stableswap v1 only have two buckets because
  fee_income = 0 — but the label *vocabulary* stays consistent
  across the sibling set.
- **Validation shape.** Type check the lp via isinstance, raise
  `ValueError` with a message naming the primitive and pointing
  the caller to the correct sibling. See
  `AnalyzeBalancerPosition._validate_lp_type` for the template:
  > `"AnalyzeBalancerPosition: lp must be a BalancerExchange;
  >  got UniswapExchange. For V2/V3 pools use AnalyzePosition;
  >  for stableswap use AnalyzeStableswapPosition."`

### 11c. What sibling primitives differ on

- **Result dataclass.** Split into distinct dataclasses
  (`BalancerPositionAnalysis`, `StableswapPositionAnalysis`),
  don't Optional-field a shared one. Protocol-specific fields
  (`base_weight`, `A`, `token_names`, `per_token_init`,
  `per_token_current`) live on the dataclass where they're
  meaningful.
- **Numeraire.** Each uses its protocol's natural numeraire. V2/V3
  use token0. Balancer uses opp-token (inherited from
  BalancerImpLoss's convention). Stableswap uses peg (tokens 1:1).
  Don't force a common numeraire at the analyzer layer —
  aggregators do their own normalization (see §11d).
- **Entry-amount API.** V2/V3/Balancer take `entry_x_amt /
  entry_y_amt` or `entry_base_amt / entry_opp_amt` (two named
  scalars). Stableswap takes `entry_amounts: list[float]`
  because N-asset extension lives in the list shape. Don't
  force the 2-asset case to pretend it's a list if it isn't;
  don't force the stableswap case to pretend it's two named
  scalars.
- **Unreachable/degenerate regimes.** Stableswap can be asked
  questions with no physical solution (unreachable alpha at
  high A + large dydx). The analyzer flags these with Optional
  fields set to None, matching AssessDepegRisk's convention.
  V2/V3 and Balancer don't have this regime — their Optional
  fields stay mandatory.

### 11d. Composition-layer dispatch

Multi-input primitives (AggregatePortfolio, future
CompareProtocols-shaped primitives) are the correct home for
isinstance dispatch. AggregatePortfolio's `_detect_protocol` +
`_analyze_uniswap` / `_analyze_balancer` / `_analyze_stableswap`
router is the template.

The rule: *stateless primitives are simpler when they know their
protocol at authoring time; aggregators / comparators are the
correct home for dispatch.* Pushing dispatch into each individual
analyzer would require every test file to fork by protocol, every
new primitive to re-solve the same problem, and each analyzer's
docstring to hedge every claim with "if V2... if Balancer..."
Don't do it.

Extracting common scalars uniformly:

```python
# In the aggregator's per-position routing method:
def _analyze_one(self, p, protocol):
    if protocol in ("uniswap_v2", "uniswap_v3"):
        return self._analyze_uniswap(p, protocol)
    if protocol == "balancer":
        return self._analyze_balancer(p, protocol)
    if protocol == "stableswap":
        return self._analyze_stableswap(p, protocol)
    raise ValueError(...)

# Each _analyze_X method returns a PositionSummary with the
# common scalars extracted from its protocol-specific result:
return PositionSummary(
    name = display_name,
    protocol = protocol,
    net_pnl = analysis.net_pnl,
    il_percentage = analysis.il_percentage,
    fee_income = analysis.fee_income,
    tokens = [<protocol-appropriate token list>],
    analysis = analysis,  # full protocol-specific dataclass preserved
)
```

`PositionSummary.analysis` is typed `Any` (not `PositionAnalysis`)
to accept any of the three variants. Callers who need protocol-
specific fields do isinstance-dispatch on `analysis`; callers who
only need the scalar totals read the PositionSummary fields
directly. Best-of-both.

### 11e. Extending the pattern

When writing the next cross-protocol sibling set (likely
`SimulateBalancerPriceMove` / `SimulateStableswapPriceMove` /
`CalculateBalancerSlippage` / `CalculateStableswapSlippage`):

1. Check whether the underlying math primitive exists in the
   sibling repo. If not, lift or write it there first — the
   analyzer should compose, not duplicate.
2. Match the core scalar fields (§11b) even if protocol-specific
   extensions are needed. Consistency across the sibling set is
   what makes composition-layer dispatch clean.
3. Scope honestly to 2-asset for v1 if the underlying IL math is
   2-asset (Balancer, Stableswap both are). N-asset extensions
   require new derivations; defer and document.
4. Return distinct dataclasses, not Optional-fielded shared ones.
5. Wire the dispatch into any existing aggregator (currently only
   AggregatePortfolio; future CompareProtocols-shaped primitives
   will follow).

---

## Completed primitives

| Primitive | Category | Tests | Date |
|---|---|---|---|
| AnalyzePosition | position/ | 17 | 2026-04-18 |
| SimulatePriceMove | position/ | 21 | 2026-04-18 |
| CalculateSlippage | execution/ | 20 | 2026-04-18 |
| CheckTickRangeStatus | risk/ | 16 | 2026-04-18 |
| FindBreakEvenPrice | position/ | 23 | 2026-04-18 |
| CheckPoolHealth | pool_health/ | 24 | 2026-04-18 |
| DetectRugSignals | pool_health/ | 23 | 2026-04-21 |
| AggregatePortfolio | portfolio/ | 21 | 2026-04-22 |
| AssessDepegRisk | risk/ | 22 | 2026-04-22 |
| DetectFeeAnomaly | pool_health/ | 20 | 2026-04-22 |
| CompareFeeTiers | comparison/ | 21 | 2026-04-23 |
| OptimalDepositSplit | optimization/ | 19 | 2026-04-23 |
| FindBreakEvenTime | position/ | 20 | 2026-04-23 |
| EvaluateTickRanges | optimization/ | 21 | 2026-04-23 |
| EvaluateRebalance | optimization/ | 20 | 2026-04-23 |
| DetectMEV | execution/ | 20 | 2026-04-23 |
| CompareProtocols | comparison/ | 23 | 2026-04-23 |
| AnalyzeBalancerPosition | position/ | 22 | 2026-04-23 |
| AnalyzeStableswapPosition | position/ | 21 | 2026-04-23 |
| AggregatePortfolio (cross-protocol extension) | portfolio/ | +13 | 2026-04-23 |
| SimulateBalancerPriceMove | position/ | 22 | 2026-04-23 |
| SimulateStableswapPriceMove | position/ | 19 | 2026-04-23 |

**Test totals:** 504 passing across all primitives + fixture smoke tests.
