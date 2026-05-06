# Day 2 Brief — `defipy.twin` module (MockProvider + LiveProvider stub)

**Audience:** Claude Code executing Day 2 of the DeFiPy v2.0 push.
**Prerequisites read before starting:**
- `doc/execution/DEFIPY_V2_AGENTIC_PLAN.md` §"Day 2 — `defipy.twin`" and §"Gap 3: State Twin"
- `doc/execution/DAY_1_REPORT.md` — what landed yesterday and why certain design choices matter
- `doc/PROJECT_CONTEXT.md` §"Key Internal Conventions" (LPQuote nucleus, numeraire convention, V2 vs V3 fee model differences)
- `python/test/primitives/conftest.py` — the existing `v2_setup` and `v3_setup` fixtures are the closest thing to a working MockProvider today; understand them before replacing them at the API level

**Baseline:** Working branch at 556 tests passing (504 primitives + 52 tools). Day 1 complete on commit `48d0d73`.

---

## Objective

Ship `defipy.twin` — the State Twin abstraction. Three public surfaces:

1. **`StateTwinProvider` ABC** — defines the `snapshot(pool_id) → PoolSnapshot` contract any provider implements
2. **`MockProvider`** — recipe-based synthetic pools (promoted fixture equivalents), for notebooks and non-chain tests
3. **`LiveProvider`** — stub only. Class shape ships; `snapshot()` raises `NotImplementedError` with a v2.1 message

Plus the data and builder glue to make them work:

- **`PoolSnapshot`** — protocol-discriminated dataclass hierarchy describing pool state
- **`StateTwinBuilder.build(snapshot)`** — constructs a fully-configured exchange object from a snapshot

The end-to-end flow a notebook user should be able to write after Day 2:

```python
from defipy.twin import MockProvider, StateTwinBuilder

provider = MockProvider()
snapshot = provider.snapshot("eth_dai_v2")
lp = StateTwinBuilder().build(snapshot)
# lp is a UniswapExchange — pass into any primitive
```

If that runs without error and the resulting `lp` behaves identically to what `v2_setup.lp` produces, Day 2 is done.

---

## Settled design decisions — do not relitigate

These were decided before this brief was written. Execute against them; don't redesign.

### 1. `PoolSnapshot` is an ABC hierarchy, not a tagged union or single discriminated dataclass

```python
class PoolSnapshot(ABC):
    """Protocol-agnostic pool state. Concrete subclasses carry protocol-specific fields."""
    pool_id: str          # opaque identifier for the provider's own bookkeeping
    protocol: str         # "uniswap_v2" | "uniswap_v3" | "balancer" | "stableswap"
```

Concrete subclasses: `V2PoolSnapshot`, `V3PoolSnapshot`, `BalancerPoolSnapshot`, `StableswapPoolSnapshot`. Each is a plain `@dataclass` that inherits from `PoolSnapshot` (make the base a `@dataclass` too — Python 3.11 supports inheritance between dataclasses cleanly).

Why this shape: matches the primitive class hierarchy (the primitives already branch on protocol internally), `isinstance` checks in `StateTwinBuilder` are explicit, adding a new protocol in v2.1 is a new subclass not a field migration. Beats a single-dataclass discriminator because V2/V3/Balancer/Stableswap fields are genuinely different — forcing them into one shape with `Optional` fields everywhere would obscure the contract.

### 2. `MockProvider` returns bare exchange objects via snapshot + builder

The existing `v2_setup` and `v3_setup` fixtures return a dataclass with `.lp`, `.eth`, `.dai`, `.lp_init_amt`, `.entry_x_amt`, `.entry_y_amt`. That dataclass mixes *pool state* (the lp object) with *test context* (entry amounts, lp init amount used for analysis primitives).

MockProvider returns pool state only. The `snapshot()` method emits a `PoolSnapshot`; the builder turns that into an exchange object. Test context (entry amounts, holding periods) is the caller's responsibility — quants track their own entry state in a notebook; the LLM gets it from the user question; Day 3's MCP server gets it from tool arguments.

### 3. Recipes are named, not arbitrary

v2.0 MockProvider ships a fixed set of four canonical recipes matching the V2_TOOL_SET coverage matrix:

| Recipe name | Protocol | Reserves |
|---|---|---|
| `"eth_dai_v2"` | Uniswap V2 | 1000 ETH / 100000 DAI (price=100) |
| `"eth_dai_v3"` | Uniswap V3 | 1000 ETH / 100000 DAI, full-range, tick_spacing=60, fee=3000 |
| `"eth_dai_balancer_50_50"` | Balancer weighted 50/50 | 1000 ETH / 100000 DAI, weights (0.5, 0.5) |
| `"usdc_dai_stableswap_A10"` | Stableswap | 50000 USDC / 50000 DAI, A=10, 2-asset |

These match the existing conftest fixtures (V2 and V3 exactly; Balancer and Stableswap newly added — see §5 below). Custom pools in v2.0 happen by constructing a `PoolSnapshot` directly and passing to the builder; no `MockProvider.custom(...)` factory in v2.0.

### 4. `LiveProvider` constructor signature is stable; `snapshot()` is what raises

```python
class LiveProvider(StateTwinProvider):
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    def snapshot(self, pool_id: str) -> PoolSnapshot:
        raise NotImplementedError(
            "LiveProvider implementation lands in v2.1. "
            "For v2.0, use MockProvider for synthetic pools or "
            "construct lp objects manually via the underlying exchange classes."
        )
```

The constructor accepts `rpc_url` so v2.1 can implement `snapshot()` without an API break. No web3 imports in this file — the stub doesn't use it, and pulling it in would break the promise that core defipy is dependency-free.

### 5. `PoolSnapshot` is minimal

Only what's needed to rebuild the exchange object. **No block numbers, no timestamps, no chain_id, no addresses beyond `pool_id`.** Those are v2.1 LiveProvider concerns — when live snapshots need provenance for caching/reorg handling, the fields get added. Forward-compatibility cost of the addition is near zero (new optional fields on the dataclass); pre-adding them now clutters the v2.0 surface.

### 6. Day 2 does not touch `conftest.py`

Leave the existing `v2_setup` and `v3_setup` fixtures exactly as-is. They return test-context dataclasses; MockProvider returns bare exchange objects. The two surfaces coexist intentionally.

Refactoring the 504 primitive tests to use MockProvider is **not** Day 2 work. That's a post-v2.0 cleanup (tracked in `V2_FOLLOWUPS.md`). Keeping fixtures untouched means the 504 existing tests stay green by construction.

### 7. No new `MockProvider` dependency on web3 or web3scout

The module imports only `uniswappy`, `balancerpy`, `stableswappy`, and stdlib. This preserves the "core defipy is dependency-free" promise from v1.2.0. `LiveProvider` ABC can be imported without triggering any chain-library import.

---

## File layout

Create these files:

```
python/prod/twin/
    __init__.py              # Public API
    provider.py              # StateTwinProvider ABC
    snapshot.py              # PoolSnapshot ABC + 4 concrete dataclasses
    builder.py               # StateTwinBuilder
    mock_provider.py         # MockProvider with 4 recipes
    live_provider.py         # LiveProvider stub

python/test/twin/
    __init__.py              # Empty
    test_snapshot.py         # Snapshot dataclass construction + validation
    test_builder.py          # Snapshot → exchange object, per protocol
    test_mock_provider.py    # Recipe names, end-to-end provider → builder → lp
    test_live_provider.py    # Stub raises with v2.1 message
    test_twin_roundtrip.py   # End-to-end flow with a primitive running against a twin-built lp
```

Update:

```
python/setup.py              # Add 'defipy.twin' to packages=[...]
```

Do not re-export `MockProvider` or `LiveProvider` at the top level `defipy/__init__.py`. Keep the namespace scoped: `from defipy.twin import MockProvider`. Matches the Day 1 convention for `defipy.tools`.

---

## Public API (`python/prod/twin/__init__.py`)

```python
from defipy.twin.provider import StateTwinProvider
from defipy.twin.snapshot import (
    PoolSnapshot,
    V2PoolSnapshot,
    V3PoolSnapshot,
    BalancerPoolSnapshot,
    StableswapPoolSnapshot,
)
from defipy.twin.builder import StateTwinBuilder
from defipy.twin.mock_provider import MockProvider
from defipy.twin.live_provider import LiveProvider

__all__ = [
    "StateTwinProvider",
    "PoolSnapshot",
    "V2PoolSnapshot",
    "V3PoolSnapshot",
    "BalancerPoolSnapshot",
    "StableswapPoolSnapshot",
    "StateTwinBuilder",
    "MockProvider",
    "LiveProvider",
]
```

---

## `StateTwinProvider` ABC (`python/prod/twin/provider.py`)

```python
from abc import ABC, abstractmethod
from defipy.twin.snapshot import PoolSnapshot


class StateTwinProvider(ABC):
    """
    Source of pool snapshots for State Twin construction.

    Implementations decide where snapshots come from — synthetic recipes
    (MockProvider), live chain reads (LiveProvider, v2.1), cached blocks,
    fork state, etc.
    """

    @abstractmethod
    def snapshot(self, pool_id: str) -> PoolSnapshot:
        """Return a PoolSnapshot for the given pool identifier."""
        ...
```

One method. No optional parameters. `pool_id` semantics are provider-specific: MockProvider treats it as a recipe name; LiveProvider (v2.1) will treat it as a chain address or chain:address string.

---

## `PoolSnapshot` dataclasses (`python/prod/twin/snapshot.py`)

```python
from abc import ABC
from dataclasses import dataclass, field


@dataclass
class PoolSnapshot(ABC):
    pool_id: str
    protocol: str  # "uniswap_v2" | "uniswap_v3" | "balancer" | "stableswap"


@dataclass
class V2PoolSnapshot(PoolSnapshot):
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    fee: float = 0.003  # default Uniswap V2 fee
    # protocol forced to "uniswap_v2" in __post_init__


@dataclass
class V3PoolSnapshot(PoolSnapshot):
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    fee: int = 3000  # fee tier in bps (V3 convention)
    tick_spacing: int = 60
    lwr_tick: int = ...    # full-range defaults; see implementation
    upr_tick: int = ...


@dataclass
class BalancerPoolSnapshot(PoolSnapshot):
    token0_name: str
    token1_name: str
    reserve0: float
    reserve1: float
    weight0: float = 0.5
    weight1: float = 0.5
    fee: float = 0.003


@dataclass
class StableswapPoolSnapshot(PoolSnapshot):
    token_names: list[str]   # e.g. ["USDC", "DAI"]
    reserves: list[float]    # same length as token_names
    A: int = 10
    fee: float = 0.0004      # typical stableswap fee
```

**Before finalizing these fields**, verify against actual exchange-object constructors:

- `UniswapExchange` → `uniswappy.process.factory.UniswapFactory` and how it's constructed in `conftest.py`
- `UniswapV3Exchange` → `uniswappy.process.factory.UniswapV3Factory`, tick math in `conftest.py`
- `BalancerExchange` → `balancerpy`, weight API
- `StableswapExchange` → `stableswappy`, A coefficient, n-asset handling

Adjust the snapshot fields to match what the builders need — don't guess. Fields listed above are illustrative; the actual exchange constructors are authoritative.

Each concrete snapshot should set `self.protocol` in `__post_init__` to prevent callers overriding the discriminator. Add validation in `__post_init__` for the non-obvious constraints: stableswap `len(reserves) == len(token_names)`, Balancer `weight0 + weight1 == 1.0` within float tolerance, V3 `lwr_tick < upr_tick`.

---

## `StateTwinBuilder` (`python/prod/twin/builder.py`)

Single method, dispatches on snapshot type:

```python
from defipy.twin.snapshot import (
    PoolSnapshot, V2PoolSnapshot, V3PoolSnapshot,
    BalancerPoolSnapshot, StableswapPoolSnapshot,
)


class StateTwinBuilder:
    """Constructs a protocol-specific exchange object from a PoolSnapshot."""

    def build(self, snapshot: PoolSnapshot):
        if isinstance(snapshot, V2PoolSnapshot):
            return self._build_v2(snapshot)
        if isinstance(snapshot, V3PoolSnapshot):
            return self._build_v3(snapshot)
        if isinstance(snapshot, BalancerPoolSnapshot):
            return self._build_balancer(snapshot)
        if isinstance(snapshot, StableswapPoolSnapshot):
            return self._build_stableswap(snapshot)
        raise TypeError(f"Unknown snapshot type: {type(snapshot).__name__}")

    def _build_v2(self, s: V2PoolSnapshot):
        # Model this on python/test/primitives/conftest.py v2_setup
        ...

    def _build_v3(self, s: V3PoolSnapshot):
        # Model on conftest.py v3_setup
        ...

    def _build_balancer(self, s: BalancerPoolSnapshot):
        # Consult balancerpy for the construction pattern
        ...

    def _build_stableswap(self, s: StableswapPoolSnapshot):
        # Consult stableswappy
        ...
```

**Critical: the `_build_v2` and `_build_v3` paths must produce an `lp` that is functionally identical to what `v2_setup.lp` and `v3_setup.lp` produce for the same reserves.** This is the consistency test that protects against silent divergence. Specifically: calling `lp.get_reserve(token)` should return the same values; calling a primitive like `CheckPoolHealth().apply(lp)` should return the same dataclass; token naming conventions must match.

---

## `MockProvider` (`python/prod/twin/mock_provider.py`)

```python
from defipy.twin.provider import StateTwinProvider
from defipy.twin.snapshot import (
    V2PoolSnapshot, V3PoolSnapshot,
    BalancerPoolSnapshot, StableswapPoolSnapshot,
)


class MockProvider(StateTwinProvider):
    """Synthetic pool snapshots for notebooks, tests, and demos."""

    RECIPES = {
        "eth_dai_v2": lambda: V2PoolSnapshot(
            pool_id="eth_dai_v2",
            protocol="uniswap_v2",
            token0_name="ETH",
            token1_name="DAI",
            reserve0=1000,
            reserve1=100000,
        ),
        "eth_dai_v3": lambda: V3PoolSnapshot(...),
        "eth_dai_balancer_50_50": lambda: BalancerPoolSnapshot(...),
        "usdc_dai_stableswap_A10": lambda: StableswapPoolSnapshot(...),
    }

    def snapshot(self, pool_id: str):
        if pool_id not in self.RECIPES:
            raise ValueError(
                f"Unknown recipe '{pool_id}'. "
                f"Available: {sorted(self.RECIPES.keys())}"
            )
        return self.RECIPES[pool_id]()

    def list_recipes(self) -> list[str]:
        return sorted(self.RECIPES.keys())
```

The recipes are lambdas that return fresh snapshots on each call — prevents mutation bugs where one test modifies a snapshot and another test inherits the mutation. Cheap, safe.

---

## `LiveProvider` stub (`python/prod/twin/live_provider.py`)

Exactly as settled in §4 above. Do not import web3 or web3scout in this file.

---

## Test coverage

### `test_snapshot.py` — ~12 tests

- Construction: each of 4 concrete snapshots instantiates with required + default fields
- Protocol discriminator: each concrete sets `protocol` correctly in `__post_init__`
- Validation: stableswap reserves/names length mismatch raises; Balancer weight sum != 1.0 raises; V3 `lwr_tick >= upr_tick` raises
- `PoolSnapshot` base cannot be instantiated directly (or if it can, it's useless — fine, don't over-test the ABC-ness)

### `test_builder.py` — ~12 tests

- Each of 4 protocols: `build(snapshot)` returns the correct exchange class (`isinstance` check against `UniswapExchange`, `UniswapV3Exchange`, `BalancerExchange`, `StableswapExchange`)
- Unknown snapshot type raises `TypeError`
- **Consistency with conftest** (the critical test): build a V2 snapshot with fixture reserves → call `lp.get_reserve("ETH")`, `lp.get_reserve("DAI")` → assert values match what `v2_setup.lp.get_reserve("ETH")` returns. Same for V3.
- Spot price consistency: `LPQuote().get_price(built_lp, token)` matches the reserve ratio

### `test_mock_provider.py` — ~10 tests

- `snapshot("eth_dai_v2")` returns a `V2PoolSnapshot` with reserves (1000, 100000)
- Same for the other 3 recipes
- `snapshot("nonexistent")` raises `ValueError` with the available recipes in the message
- `list_recipes()` returns sorted list of exactly 4 names
- Recipes produce fresh snapshots (mutate one, get a new one — no shared state)
- **End-to-end**: for each recipe, `provider.snapshot(...)` + `builder.build(...)` + a sanity-check primitive call like `CheckPoolHealth().apply(lp)` all succeed

### `test_live_provider.py` — ~4 tests

- `LiveProvider("http://anything").snapshot("x")` raises `NotImplementedError`
- Error message mentions "v2.1" and "MockProvider"
- Constructor stores `rpc_url`
- Importing the module does not import web3 (can test by checking `sys.modules` before/after)

### `test_twin_roundtrip.py` — ~6 tests

The end-to-end acceptance test. One test per recipe:

```python
def test_v2_recipe_runs_analyze_position():
    provider = MockProvider()
    snapshot = provider.snapshot("eth_dai_v2")
    lp = StateTwinBuilder().build(snapshot)

    from defipy.primitives.position import AnalyzePosition
    result = AnalyzePosition().apply(
        lp, lp_init_amt=1.0, entry_x_amt=1000, entry_y_amt=100000
    )
    assert result.current_value > 0
    assert result.diagnosis in {"il_dominant", "fee_compensated", "net_positive"}
```

One such test per protocol, using the curated-10 primitive that applies to that protocol:
- V2 → AnalyzePosition
- V3 → AnalyzePosition
- Balancer → AnalyzeBalancerPosition
- Stableswap → AnalyzeStableswapPosition (needs `entry_amounts=[...]`)
- V2 → CheckPoolHealth (extra coverage)
- V3 → CheckPoolHealth (extra coverage)

This test file is the demonstration that Day 2 actually closes the loop with Day 1's tools. If these pass, the minimal agentic loop from `MockProvider → builder → lp → primitive → dataclass result` is real code, not aspiration.

---

## Checklist before declaring Day 2 done

- [ ] `from defipy.twin import MockProvider, StateTwinBuilder` works from a fresh Python shell
- [ ] `MockProvider().list_recipes()` returns the 4 canonical recipe names
- [ ] Each of the 4 recipes produces an `lp` identical in behavior (reserves, spot price, protocol) to what a bespoke constructor would produce
- [ ] V2 and V3 builder paths match `conftest.py` fixture outputs byte-for-byte on `get_reserve` calls
- [ ] `LiveProvider("x").snapshot("y")` raises `NotImplementedError` with v2.1 message
- [ ] Importing `defipy.twin.live_provider` does not import web3
- [ ] All 6 roundtrip tests pass (primitive executes cleanly against a twin-built lp)
- [ ] `setup.py` includes `'defipy.twin'`
- [ ] Full suite green: `pytest python/test/` → expect ~600 tests passing (556 + ~44 new)
- [ ] `pytest python/test/primitives/` still green at 504 (conftest untouched)
- [ ] `pytest python/test/tools/` still green at 52 (Day 1 untouched)
- [ ] Clean commit; message template below

```
feat(twin): defipy.twin module with MockProvider and LiveProvider stub

Ships v2.0 Day 2 minimal agentic skeleton piece. State Twin abstraction
with 4 recipe-based synthetic pools covering V2, V3, Balancer 2-asset,
and Stableswap 2-asset. LiveProvider ships as stub — implementation v2.1.

- twin/provider.py: StateTwinProvider ABC
- twin/snapshot.py: PoolSnapshot hierarchy (V2/V3/Balancer/Stableswap)
- twin/builder.py: StateTwinBuilder dispatches on snapshot type
- twin/mock_provider.py: 4 canonical recipes
- twin/live_provider.py: stub with v2.1 NotImplementedError
- Tests in python/test/twin/ (~44 new tests including roundtrip)
- conftest.py untouched — fixtures coexist with MockProvider intentionally
- setup.py updated

Part of the 3-4 day minimal ship per DEFIPY_V2_AGENTIC_PLAN.md.
```

---

## When to pause and ask

**Do pause and ask if:**

- A concrete exchange-class constructor needs a parameter the snapshot doesn't currently carry (fields were illustrative — verify against source). If the snapshot needs to grow a field to support construction, surface the question rather than guessing the field name or default.
- The Balancer or Stableswap construction path in their respective packages doesn't expose the needed surface — pre-shipped fixtures in `conftest.py` only cover V2 and V3, so these two paths are genuinely new.
- The byte-for-byte consistency test between `StateTwinBuilder.build(v2_snapshot)` and `v2_setup.lp` fails on any property — this means the construction path is materially different and the difference needs to be understood before papering over it.

**Do not pause and ask about:**

- Whether to use a tagged-union instead of the ABC hierarchy — no, ABC is settled (§1)
- Whether MockProvider should return the test-context dataclass too — no, bare exchange object only (§2)
- Whether to add a 5th or 6th recipe — no, four canonical recipes exactly (§3)
- Whether `LiveProvider` should just not ship at all — no, stub ships for v2.1 API stability (§4)
- Whether snapshots should carry block numbers — no, v2.1 concern (§5)
- Whether to refactor the 504 primitive tests to use MockProvider — no, conftest untouched (§6)
- Whether to add a web3 import guard — no, just don't import it (§7)

---

## After Day 2

Once all gates pass and the commit is made, Day 2 is complete. Day 3 covers the packaging fix (clean venv install test included — flagged from Day 1's editable-install friction) and the MCP server demo that exercises the full loop: user question → Claude → MCP tool call → MockProvider → twin → primitive → result → answer. Day 3 brief written separately.

Known consequence Day 2 has for Day 3: two primitives take object-typed parameters beyond `lp` (per Day 1's `DISPATCH_SUPPLIED_PARAMS` — `token_in` on `CalculateSlippage`, `depeg_token` on `AssessDepegRisk`). Day 3's MCP server dispatch layer resolves these from tool arguments (likely as token-name strings the server maps to ERC20 objects from the lp's token list). Not a Day 2 concern, but relevant for how `MockProvider` recipes expose their tokens — verify the exchange objects built by `StateTwinBuilder` have their ERC20 tokens accessible via the same attribute pattern the conftest fixtures use.
