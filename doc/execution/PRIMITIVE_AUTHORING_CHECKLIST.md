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
  result. Use judgment: if a dataclass is only meaningful as a field of
  another dataclass, colocate it; if it stands alone as a primitive
  result, give it its own file.
- Stdlib `@dataclass` decorator (not `attrs`).
- Explicit field types on every field.
- `Optional[T]` for fields that legitimately may be None.
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
