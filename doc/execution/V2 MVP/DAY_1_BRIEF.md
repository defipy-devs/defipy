# Day 1 Brief — `defipy.tools` module (MCP schema generation)

**Audience:** Claude Code executing Day 1 of the DeFiPy v2.0 push.
**Prerequisites read before starting:** `doc/execution/DEFIPY_V2_AGENTIC_PLAN.md` (Day 1 section), `doc/execution/V2_TOOL_SET.md` (authoritative curation + verification gate), `doc/PROJECT_CONTEXT.md` (repo orientation + Key Internal Conventions).
**Baseline:** Working branch at 504 tests passing, 22 primitives across 8 sub-packages. Confirmed via `pytest python/test/primitives/ -v` before starting this brief.

---

## Objective

Ship `defipy.tools` — a library module that emits MCP tool schemas for 10 curated primitives. No dispatch, no invocation, no LLM dependencies. Schemas only.

The gate from `V2_TOOL_SET.md` §Day 1 verification is authoritative:

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

If that passes plus the additional tests below pass, Day 1 is done.

---

## Settled design decisions — do not relitigate

These were discussed and decided before this brief was written. Execute against them; don't redesign.

1. **Schemas-only module.** `defipy.tools` contains schema emission logic and the curated registry. No invokers, no dispatch, no LLM adapters. Invocation glue lives in Day 3's MCP server (`python/mcp/defipy_mcp_server.py`), not the library.

2. **MCP format only.** No Anthropic tool-use JSON, no OpenAI function-calling format. Both deferred to v2.1. The `get_schemas` function takes a `format` argument for forward compatibility; it accepts `"mcp"` and raises `NotImplementedError` with a v2.1 message for any other value.

3. **Hand-written schemas per tool, with drift-detection test.** No runtime introspection of `.apply()` signatures. Each tool's input schema is authored explicitly in `registry.py`. A test verifies the schema's `properties` keys match `inspect.signature(Primitive.apply).parameters` (minus `self` and any object-typed params like `lp`) so schemas can't silently drift if a primitive's signature changes.

4. **No `outputSchema` on MCP tool definitions.** MCP allows but doesn't require output schemas; Claude doesn't use them for tool selection. Shipping them would double the hand-curation work for zero v2.0 benefit. Add in v2.1 only if downstream consumers actually need them.

5. **Tool names match primitive class names verbatim** (PascalCase). `"AnalyzePosition"`, not `"analyze_position"`. Matches the V2_TOOL_SET.md verification gate.

6. **Balancer entry-amount shape is flat**: `{entry_base: number, entry_opp: number}`. Not nested.

---

## File layout

Create these files exactly:

```
python/prod/tools/
    __init__.py              # Public API: get_schemas, list_tool_names
    registry.py              # The 10 ToolSpec entries
    schemas.py               # MCP schema emitter — reads registry, returns list[dict]

python/test/tools/
    __init__.py              # Empty
    test_schemas.py          # V2_TOOL_SET gate tests + MCP format compliance
    test_registry.py         # Drift-detection: schema params match .apply() signatures
```

Update:

```
python/setup.py              # Add 'defipy.tools' to packages=[...]
python/prod/__init__.py      # Re-export from defipy.tools for convenience (optional — see §public API)
```

---

## Public API (`python/prod/tools/__init__.py`)

```python
from defipy.tools.schemas import get_schemas
from defipy.tools.registry import list_tool_names, TOOL_REGISTRY

__all__ = ["get_schemas", "list_tool_names", "TOOL_REGISTRY"]
```

`get_schemas(format: str = "mcp") -> list[dict]` — returns the list of tool schemas in the requested format. `format="mcp"` is the only supported value in v2.0; any other value raises `NotImplementedError("Format '<x>' deferred to v2.1. Use format='mcp'.")`.

`list_tool_names() -> list[str]` — returns the sorted list of tool names currently registered. Useful for sanity checking without pulling full schemas.

`TOOL_REGISTRY` — the registry dict, exposed for advanced use (e.g., Day 3's MCP server will read this to build its dispatch map).

Do not re-export `get_schemas` from top-level `defipy/__init__.py`. The tools module is an optional, discoverable surface accessed via `from defipy.tools import ...`. Keeping it un-re-exported matches how other specialized surfaces (`defipy.utils.data`) are scoped.

---

## Registry structure (`python/prod/tools/registry.py`)

```python
from dataclasses import dataclass
from typing import Any

from defipy.primitives.position import (
    AnalyzePosition,
    AnalyzeBalancerPosition,
    AnalyzeStableswapPosition,
    SimulatePriceMove,
    SimulateBalancerPriceMove,
    SimulateStableswapPriceMove,
)
from defipy.primitives.pool_health import CheckPoolHealth, DetectRugSignals
from defipy.primitives.risk import AssessDepegRisk
from defipy.primitives.execution import CalculateSlippage


@dataclass(frozen=True)
class ToolSpec:
    name: str                   # Tool name exposed to the LLM (matches primitive class name)
    description: str            # Hand-curated, 2-4 sentences
    primitive_cls: type         # Reference to the primitive class (for drift tests + Day 3 dispatch)
    input_schema: dict          # JSON Schema dict for .apply() arguments
    signature_params: tuple     # Expected parameter names on .apply() for drift detection
                                # (excludes self and lp — those aren't in the tool-use surface)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "AnalyzePosition": ToolSpec(
        name="AnalyzePosition",
        description=(
            "Analyze why a Uniswap V2 or V3 LP position is gaining or losing money. "
            "Decomposes PnL into impermanent loss, accumulated fees, and net result. "
            "Returns current value, hold value, IL percentage, real APR, and a diagnosis string."
        ),
        primitive_cls=AnalyzePosition,
        signature_params=("lp_init_amt", "entry_x_amt", "entry_y_amt", "holding_period_years"),
        input_schema={
            "type": "object",
            "properties": {
                "lp_init_amt": {
                    "type": "number",
                    "description": "The caller's LP token amount (position size).",
                },
                "entry_x_amt": {
                    "type": "number",
                    "description": "Amount of token0 deposited at position entry.",
                },
                "entry_y_amt": {
                    "type": "number",
                    "description": "Amount of token1 deposited at position entry.",
                },
                "holding_period_years": {
                    "type": ["number", "null"],
                    "description": "Optional holding period in years. If supplied, real_apr is computed.",
                },
            },
            "required": ["lp_init_amt", "entry_x_amt", "entry_y_amt"],
        },
    ),
    # ... 9 more entries
}


def list_tool_names() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())
```

**Before authoring the other 9 entries, do this:**

For each primitive in the curated 10, read the actual `.apply()` signature from the source to confirm parameter names and types. The example above is illustrative — verify against `python/prod/primitives/position/AnalyzePosition.py` before committing. The V2_TOOL_SET.md curation was written at the tool-selection level, not with parameter-by-parameter signatures in hand.

Reference files for each primitive:

| Tool | File |
|---|---|
| AnalyzePosition | `python/prod/primitives/position/AnalyzePosition.py` |
| AnalyzeBalancerPosition | `python/prod/primitives/position/AnalyzeBalancerPosition.py` |
| AnalyzeStableswapPosition | `python/prod/primitives/position/AnalyzeStableswapPosition.py` |
| SimulatePriceMove | `python/prod/primitives/position/SimulatePriceMove.py` |
| SimulateBalancerPriceMove | `python/prod/primitives/position/SimulateBalancerPriceMove.py` |
| SimulateStableswapPriceMove | `python/prod/primitives/position/SimulateStableswapPriceMove.py` |
| CheckPoolHealth | `python/prod/primitives/pool_health/CheckPoolHealth.py` |
| DetectRugSignals | `python/prod/primitives/pool_health/DetectRugSignals.py` |
| CalculateSlippage | `python/prod/primitives/execution/CalculateSlippage.py` |
| AssessDepegRisk | `python/prod/primitives/risk/AssessDepegRisk.py` |

**For each one, read the file, extract the `.apply()` signature, author the schema by hand.**

---

## Description-writing principles (from V2_TOOL_SET.md §Tool-description guidance)

- 2-4 sentences per tool. Claude reads all 10 on every selection decision; bloat degrades quality.
- Lead with the question it answers, not the math. ("Analyze why a position is losing money" — not "Computes UniswapImpLoss decomposition.")
- Name the protocols explicitly. Uniswap V2+V3 vs Balancer 2-asset vs Stableswap 2-asset — Claude needs this to pick between siblings.
- Flag non-obvious reachability limits (e.g., Stableswap unreachable-alpha scenarios in AssessDepegRisk).
- Don't embed dataclass fields in prose — the `input_schema` carries structure.

Write the AssessDepegRisk description carefully: the "some depeg levels may be physically unreachable at high A" quirk is genuinely surprising and an LLM that doesn't know this will misinterpret None fields as errors.

---

## Schema emitter (`python/prod/tools/schemas.py`)

```python
from defipy.tools.registry import TOOL_REGISTRY


def get_schemas(format: str = "mcp") -> list[dict]:
    if format != "mcp":
        raise NotImplementedError(
            f"Format '{format}' deferred to v2.1. Use format='mcp'."
        )
    return [_to_mcp_schema(spec) for spec in TOOL_REGISTRY.values()]


def _to_mcp_schema(spec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": spec.input_schema,
    }
```

MCP tool definition format reference: https://modelcontextprotocol.io/docs/concepts/tools — the required fields are `name`, `description`, and `inputSchema`. That's the minimal surface v2.0 ships.

---

## Test coverage (`python/test/tools/`)

### `test_schemas.py` — gate tests (~10 tests)

Implement the V2_TOOL_SET.md gate literally:

- `test_get_schemas_returns_ten` — `len(get_schemas("mcp")) == 10`
- `test_tool_names_match_curated_set` — name set equals exactly the 10 expected names
- `test_each_schema_has_mcp_required_fields` — every entry has `name`, `description`, `inputSchema`
- `test_descriptions_are_strings_under_length_cap` — each description is a non-empty string ≤ 500 chars (covers the "2-4 sentences" principle without being pedantic about counting)
- `test_input_schemas_are_valid_json_schema` — each `inputSchema` has `type: "object"` and a `properties` dict
- `test_every_property_has_type_and_description` — for every property in every input schema, both keys exist
- `test_unsupported_format_raises_notimplementederror` — `get_schemas("openai")` raises with v2.1 mention
- `test_unsupported_format_raises_notimplementederror_anthropic` — same for `"anthropic"`
- `test_tool_name_in_schema_matches_registry_key` — iterate registry, confirm `spec.name == key`
- `test_list_tool_names_sorted` — `list_tool_names()` returns sorted list matching registry keys

### `test_registry.py` — drift detection (~10-12 tests)

For each of the 10 tools:

- `test_<primitive>_schema_properties_match_apply_signature` — `inspect.signature(spec.primitive_cls.apply)` produces param names that equal `spec.signature_params`, and those equal `spec.input_schema["properties"].keys()`

Implementation pattern:

```python
import inspect
import pytest

from defipy.tools.registry import TOOL_REGISTRY


@pytest.mark.parametrize("tool_name", sorted(TOOL_REGISTRY.keys()))
def test_schema_matches_apply_signature(tool_name):
    spec = TOOL_REGISTRY[tool_name]
    sig = inspect.signature(spec.primitive_cls.apply)
    # Strip 'self' and any object-typed params (lp, provider, etc.)
    actual_params = tuple(
        p for p in sig.parameters
        if p not in ("self", "lp")  # extend if other primitives take other non-scalar args
    )
    expected_params = spec.signature_params
    schema_props = tuple(spec.input_schema["properties"].keys())

    assert actual_params == expected_params, (
        f"{tool_name}: .apply() params {actual_params} "
        f"differ from declared signature_params {expected_params}"
    )
    assert schema_props == expected_params, (
        f"{tool_name}: input_schema properties {schema_props} "
        f"differ from declared signature_params {expected_params}"
    )
```

This is the single most important test in the module. If a primitive's `.apply()` signature changes without the schema being updated, this test fires. It's the reason hand-written schemas are safe — the drift gets caught mechanically.

Additional registry tests:

- `test_primitive_cls_is_actually_a_class` — every `spec.primitive_cls` is a class, not an instance
- `test_primitive_cls_has_apply_method` — every primitive has an `.apply` attribute that's callable

---

## Checklist before declaring Day 1 done

- [ ] All 10 registry entries authored with schemas verified against source
- [ ] `get_schemas("mcp")` returns 10 entries, names match exactly
- [ ] Every input schema has `type: "object"` and `properties` with typed fields
- [ ] Every description is 2-4 sentences, leads with the question, names protocols
- [ ] `AssessDepegRisk` description flags unreachable-alpha behavior
- [ ] `get_schemas("anthropic")` and `get_schemas("openai")` raise `NotImplementedError`
- [ ] Drift-detection test passes for all 10 primitives
- [ ] `setup.py` includes `'defipy.tools'` in `packages=`
- [ ] `pytest python/test/` green across full suite (~520 tests expected: 504 + new)
- [ ] `pytest python/test/primitives/` still green (unchanged 504)
- [ ] Clean commit with message per `DEFIPY_V2_AGENTIC_PLAN.md` §Fresh Session Kickoff

Commit message template (from the plan):

```
feat(tools): defipy.tools module with MCP tool schemas

Ships v2.0 Day 1 minimal agentic skeleton piece. Curated 10-primitive
tool set covering position analysis across V2/V3/Balancer/Stableswap,
pool health, slippage, and depeg risk.

- tools/__init__.py, tools/registry.py, tools/schemas.py
- MCP format only (Anthropic tool-use + OpenAI deferred to v2.1)
- Hand-curated tool descriptions (2-4 sentences each)
- Drift-detection test verifies schemas match .apply() signatures
- Tests in python/test/tools/ (~20 new tests)
- setup.py updated

Part of the 3-4 day minimal ship per DEFIPY_V2_AGENTIC_PLAN.md.
```

---

## When to pause and ask

Do not expand scope mid-flight. If something feels like "we should also add X," note it in `doc/execution/V2_FOLLOWUPS.md` (create the file if it doesn't exist) and keep moving. Phase 2 catches every deferred item.

Do pause and ask if:

- A primitive's `.apply()` signature has object-typed parameters beyond `lp` that need a different skipping rule in the drift test
- The Balancer entry_amounts shape assumption (flat `entry_base` / `entry_opp`) doesn't match the actual primitive signature
- A description can't be written in 4 sentences while still naming the protocols explicitly and flagging reachability limits
- Any schema field has a type that doesn't map cleanly to JSON Schema primitives (e.g., a `Decimal`, a custom enum)

These are the places where earlier reasoning might not hold up against the actual code. Surface them explicitly rather than guessing.

Do not pause to ask about:

- Whether to use Option B (invokers) after all — no, Option A is settled
- Whether to add output schemas — no, deferred to v2.1
- Whether to re-export from top-level `defipy` — no, keep the namespace scoped
- Whether one of the 10 curated tools should be swapped for a different primitive — no, V2_TOOL_SET.md is authoritative

---

## After Day 1

Once the gate passes and the commit is made, Day 1 is complete. The next brief will cover Day 2 (`defipy.twin` — MockProvider + LiveProvider stub) and will be written separately. Don't preempt Day 2 work in this session.
