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
| Result dataclass | `python/prod/utils/data/<Result>.py` |
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

- One dataclass per file, same name as the file.
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
   `from .<Result> import <Result>`

---

## 5. Test file structure

Pattern: `python/test/primitives/<category>/test_<primitive>.py`

Use the shared fixtures from `python/test/primitives/conftest.py`:

- `v2_setup` — fresh V2 LP, USER owns 100%, 1000 ETH / 100000 DAI at entry.
- `v3_setup` — fresh V3 LP, full-range ticks (tick_spacing=60, fee=3000),
  same entry amounts.

Both return dataclasses with `.lp`, `.eth`, `.dai`, `.lp_init_amt`,
`.entry_x_amt`, `.entry_y_amt` (V3 adds `.lwr_tick`, `.upr_tick`).

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

## Completed primitives

| Primitive | Category | Tests | Date |
|---|---|---|---|
| AnalyzePosition | position/ | 17 | 2026-04-18 |
| SimulatePriceMove | position/ | 21 | 2026-04-18 |
| CalculateSlippage | execution/ | 20 | 2026-04-18 |
| CheckTickRangeStatus | risk/ | 16 | 2026-04-18 |
