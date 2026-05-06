# Day 3 Brief — Packaging fix + MCP server demo

**Audience:** Claude Code executing Day 3 of the DeFiPy v2.0 push.
**Prerequisites read before starting:**
- `doc/execution/DEFIPY_V2_AGENTIC_PLAN.md` §"Day 3 — Packaging fix + DeFiMind demo script"
- `doc/execution/DAY_1_REPORT.md` + `doc/execution/DAY_2_REPORT.md` — the actual shipped surfaces Day 3 composes
- `doc/execution/V2_TOOL_SET.md` — the 10 tools exposed
- MCP Python SDK reference: https://github.com/modelcontextprotocol/python-sdk
- MCP tool format: https://modelcontextprotocol.io/docs/concepts/tools

**Baseline:** 603 tests passing (504 primitives + 52 tools + 47 twin). Day 2 complete on commit `0aca7c5`.

---

## Objective

Day 3 has two parts:

1. **Packaging fix.** `setup.py` currently registers `defipy.primitives` and `defipy.primitives.position`. Other sub-packages are missing, and a fresh `pip install defipy` from PyPI would be broken on import. This is a v2.0 ship-blocker and must be fixed before tagging.

2. **MCP server demo.** A stdio-transport MCP server at `python/mcp/defipy_mcp_server.py` that exposes the 10 curated tools, dispatches tool calls to primitives running against MockProvider-built twins, and logs receipts to stderr. The demo is "connect to Claude Desktop / Claude Code and have a live conversation" — Ian runs that part manually.

Day 3 is structurally different from Days 1-2. There is **CC work** (everything up to the MCP server running locally) and a **Ian verification step** (wiring to Claude Desktop, live session, screen capture). The brief separates them explicitly below.

---

## Settled design decisions — do not relitigate

### A. Token-resolution lives in the MCP server, not `defipy.tools`

Two primitives need non-schema params resolved to objects: `CalculateSlippage.token_in` and `AssessDepegRisk.depeg_token` are ERC20 instances in the actual `.apply()` signature. The MCP tool schemas expose them as token-name strings (e.g., `"DAI"`, `"USDC"`).

The MCP server's `call_tool` handler does the string→ERC20 mapping at dispatch time. Day 1's decision was "schemas only in `defipy.tools`, dispatch in MCP server" — extending dispatch to include token resolution is consistent with that. A helper in the library would retroactively broaden `defipy.tools`' scope without a second consumer justifying it.

Access patterns for token resolution (from Day 2 report):
- **V2 / V3:** `lp.factory.token_from_exchange[lp.name]` returns a dict keyed by token name
- **Balancer / Stableswap:** `lp.tkn_reserves` is a dict keyed by token name; the ERC20 objects are retrievable via the pool's internal token tracking — verify against Day 2's MockProvider build paths before coding this

The server's token-resolution helper is a small private function in `defipy_mcp_server.py`. Not exported.

### B. `pool_id` is injected by the MCP server at schema-exposure time, not baked into Day 1 schemas

Day 1's `get_schemas("mcp")` returns 10 schemas with no notion of "which pool." The MCP server wraps that output and adds a required `pool_id` field to each tool's `inputSchema` before exposing to the LLM:

```python
def _wrap_schema_with_pool_id(tool_schema: dict, recipe_names: list[str]) -> dict:
    wrapped = copy.deepcopy(tool_schema)
    wrapped["inputSchema"]["properties"]["pool_id"] = {
        "type": "string",
        "description": (
            "Which pool to analyze. Must match one of the MockProvider recipes. "
            "Pick the recipe that matches the protocol the user's question implies."
        ),
        "enum": recipe_names,
    }
    required = wrapped["inputSchema"].setdefault("required", [])
    if "pool_id" not in required:
        required.append("pool_id")
    return wrapped
```

The Day 1 schemas stay pure. The MCP server's additions are dispatch-layer concerns. This preserves the Day 1/Day 3 separation and means no amendment to the 556-test baseline.

**Consequence for tool matching:** the LLM will pick a tool (say `AnalyzeBalancerPosition`) and a `pool_id` (say `"eth_dai_balancer_50_50"`). The server must validate these are compatible — calling `AnalyzeBalancerPosition` with `pool_id="eth_dai_v2"` is user error and should return a clear error. See §Dispatch validation below.

### C. Receipts emit as single-line JSON to stderr

One receipt per `call_tool` invocation. Format:

```json
{"ts": "2026-04-23T14:22:05.123Z", "tool": "AnalyzePosition", "pool_id": "eth_dai_v2", "args": {"lp_init_amt": 1.0, "entry_x_amt": 1000, "entry_y_amt": 100000}, "status": "ok", "duration_ms": 12, "result_summary": "diagnosis=il_dominant, net_pnl=-3.24"}
```

On error:

```json
{"ts": "...", "tool": "AnalyzePosition", "pool_id": "eth_dai_v2", "args": {...}, "status": "error", "error_type": "ValueError", "error_message": "lp_init_amt must be positive"}
```

**Result summary** is a short hand-written extractor per tool — not the full dataclass serialization. Goal: one line that tells someone watching stderr what happened, not forensic completeness. Stderr is the v2.0 observability story; structured ingestion is v2.1 work.

Use Python `json.dumps` with `ensure_ascii=True` and no indent. Single line per event. Log with `print(..., file=sys.stderr, flush=True)`.

### D. Every `call_tool` builds a fresh twin — no state persistence

MCP server process lives for the duration of the Claude session. Each `call_tool` invocation:

1. Reads `pool_id` from args
2. Calls `provider.snapshot(pool_id)` → `builder.build(snapshot)` → fresh `lp`
3. Resolves any token-name args to ERC20 objects against that fresh `lp`
4. Calls the primitive's `.apply(...)`
5. Serializes the result
6. Returns

No caching, no cross-call state. Matches the primitive contract (stateless) and sidesteps reorg/invalidation concerns entirely. If a recipe is slow to build, that's fine for v2.0 — MockProvider is synthetic, builds are microseconds.

### E. Primitive→recipe compatibility is validated at dispatch time

Not every tool works with every recipe. Hardcode the compatibility map in the server:

```python
_COMPATIBLE_RECIPES = {
    "AnalyzePosition":              ["eth_dai_v2", "eth_dai_v3"],
    "SimulatePriceMove":            ["eth_dai_v2", "eth_dai_v3"],
    "CheckPoolHealth":              ["eth_dai_v2", "eth_dai_v3"],
    "DetectRugSignals":             ["eth_dai_v2", "eth_dai_v3"],
    "CalculateSlippage":            ["eth_dai_v2", "eth_dai_v3"],
    "AnalyzeBalancerPosition":      ["eth_dai_balancer_50_50"],
    "SimulateBalancerPriceMove":    ["eth_dai_balancer_50_50"],
    "AnalyzeStableswapPosition":    ["usdc_dai_stableswap_A10"],
    "SimulateStableswapPriceMove":  ["usdc_dai_stableswap_A10"],
    "AssessDepegRisk":              ["usdc_dai_stableswap_A10"],
}
```

If LLM calls a tool with an incompatible `pool_id`, the server returns a structured error content block (not an exception):

```
Error: tool 'AnalyzeBalancerPosition' is not compatible with pool 'eth_dai_v2'.
Compatible pools for this tool: ['eth_dai_balancer_50_50'].
```

The LLM can read this and recover. Receipts still emit with `status="error"`.

### F. `mcp` package is a demo-only dependency; **not** in `install_requires`

The MCP Python SDK (`pip install mcp`) is required to run the server but not to use the library. It goes under a new `[mcp]` extras key:

```python
extras_require={
    "book":  [...],
    "anvil": [...],
    "mcp":   ["mcp>=0.9.0"],   # version pin at Day 3 time of writing; verify against actual release
}
```

The import of `mcp` happens inside `python/mcp/defipy_mcp_server.py`, which is **outside the library tree** — users who `pip install defipy` don't encounter it. Only users following the MCP server README run `pip install defipy[mcp]`.

If `mcp` is not yet installed on Ian's machine, **step 0 for CC is `pip install mcp`** and noting the installed version in the Day 3 report so the `setup.py` pin matches reality.

---

## Part 1: Packaging fix

### File: `python/setup.py`

Current `packages=[...]` list is under-populated. The fix extends it to cover every shipped sub-package. Expected final list (verify against actual on-disk directory structure before committing):

```python
packages=[
    'defipy',
    'defipy.agents',               # legacy — keep for book ch 9
    'defipy.agents.legacy',        # if it exists (check)
    'defipy.cpt',
    'defipy.cpt.index',
    'defipy.cpt.quote',
    'defipy.math',                 # if present
    'defipy.primitives',
    'defipy.primitives.comparison',
    'defipy.primitives.execution',
    'defipy.primitives.optimization',
    'defipy.primitives.pool_health',
    'defipy.primitives.portfolio',
    'defipy.primitives.position',
    'defipy.primitives.risk',
    'defipy.process',
    'defipy.process.deposit',
    'defipy.process.join',
    'defipy.process.liquidity',
    'defipy.process.swap',
    'defipy.tools',                # Day 1
    'defipy.twin',                 # Day 2
    'defipy.utils',
    'defipy.utils.data',
    # any others present on disk
],
```

Rather than guess the full list, **run this first** and paste into setup.py:

```bash
cd python/prod
find . -type d -not -path '*/\.*' -not -path '*/__pycache__*' | \
    sed 's|^\./|defipy.|; s|/|.|g; s|^\.\.$|defipy|'
```

Also update:

- **`version`** → `"2.0.0"`
- **`description`** → `"Python SDK for Agentic DeFi"` (the new tagline from the Plan)
- **`extras_require`** → add `"mcp": ["mcp>=X.Y.Z"]` per §F

### Packaging verification (critical)

The Day 1 report flagged editable-install friction. Day 3 must confirm a *clean* install works, not just the editable one. Procedure:

```bash
# Create fresh venv
python3.11 -m venv /tmp/defipy_v2_install_test
source /tmp/defipy_v2_install_test/bin/activate

# Install from local source in non-editable mode
pip install /Users/ian_moore/repos/defipy

# Import smoke test
python -c "
from defipy import AnalyzePosition, SimulatePriceMove, CheckPoolHealth
from defipy.tools import get_schemas
from defipy.twin import MockProvider, StateTwinBuilder
schemas = get_schemas('mcp')
assert len(schemas) == 10
provider = MockProvider()
lp = StateTwinBuilder().build(provider.snapshot('eth_dai_v2'))
result = AnalyzePosition().apply(lp, lp_init_amt=1.0, entry_x_amt=1000, entry_y_amt=100000)
print('install OK:', result.diagnosis)
"

# Cleanup
deactivate
rm -rf /tmp/defipy_v2_install_test
```

If that passes, packaging is fixed. Capture the output in the Day 3 report.

### Test for packaging

Add `python/test/test_packaging.py`:

```python
"""Import smoke tests — exercise every shipped sub-package.

These tests would fail in a broken install (which the editable install
masks). Kept in the normal test suite as a continuous guard against
setup.py packages=[] drift.
"""

def test_defipy_tools_importable():
    from defipy.tools import get_schemas, TOOL_REGISTRY, list_tool_names
    assert len(get_schemas("mcp")) == 10

def test_defipy_twin_importable():
    from defipy.twin import (
        MockProvider, StateTwinBuilder, StateTwinProvider,
        PoolSnapshot, V2PoolSnapshot, V3PoolSnapshot,
        BalancerPoolSnapshot, StableswapPoolSnapshot, LiveProvider,
    )
    assert MockProvider().list_recipes() == sorted([
        "eth_dai_v2", "eth_dai_v3",
        "eth_dai_balancer_50_50", "usdc_dai_stableswap_A10",
    ])

def test_each_primitive_subpackage_importable():
    from defipy.primitives.position import AnalyzePosition
    from defipy.primitives.pool_health import CheckPoolHealth
    from defipy.primitives.risk import AssessDepegRisk
    from defipy.primitives.execution import CalculateSlippage
    from defipy.primitives.optimization import EvaluateRebalance
    from defipy.primitives.comparison import CompareProtocols
    from defipy.primitives.portfolio import AggregatePortfolio
    # Classes exist and are callable
    for cls in (AnalyzePosition, CheckPoolHealth, AssessDepegRisk,
                CalculateSlippage, EvaluateRebalance,
                CompareProtocols, AggregatePortfolio):
        assert callable(cls)
```

---

## Part 2: MCP server

### File layout

```
python/mcp/
    __init__.py                    # Empty
    defipy_mcp_server.py           # The server
    README.md                      # Install + Claude Desktop / Claude Code config
    .gitignore                     # If needed for venv / caches

python/test/mcp/
    __init__.py
    test_server.py                 # Server-level unit tests (no stdio)
```

**`python/mcp/` is outside the library tree.** It does not appear in `setup.py`'s `packages=[...]`. It ships in the git repo only. Users consuming the library don't see it; users running the demo find it via the README.

### Server structure

```python
# python/mcp/defipy_mcp_server.py

"""DeFiPy MCP Server — exposes the v2.0 curated tool set to MCP clients."""

import asyncio
import copy
import json
import logging
import sys
import time
from datetime import datetime, timezone

from mcp.server import Server            # verify actual import path against installed mcp SDK
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from defipy.tools import TOOL_REGISTRY, get_schemas
from defipy.twin import MockProvider, StateTwinBuilder


# ─── Compatibility + dispatch config ──────────────────────────────────

_PROVIDER = MockProvider()
_BUILDER = StateTwinBuilder()

_RECIPE_NAMES = sorted(_PROVIDER.list_recipes())

_COMPATIBLE_RECIPES = {
    "AnalyzePosition":              ["eth_dai_v2", "eth_dai_v3"],
    # ... (see §E above)
}

_DISPATCH_SUPPLIED_PARAMS = {"lp", "token_in", "depeg_token"}


# ─── Schema wrapping ──────────────────────────────────────────────────

def _wrap_schemas_with_pool_id() -> list[dict]:
    """Inject pool_id enum + required into each Day 1 schema."""
    schemas = get_schemas("mcp")
    wrapped = []
    for s in schemas:
        w = copy.deepcopy(s)
        w["inputSchema"]["properties"]["pool_id"] = {
            "type": "string",
            "description": (
                "Which pool to analyze. Required. Must match one of the "
                "available recipes — pick the one matching the protocol "
                "implied by the user's question."
            ),
            "enum": _COMPATIBLE_RECIPES.get(s["name"], _RECIPE_NAMES),
        }
        required = w["inputSchema"].setdefault("required", [])
        if "pool_id" not in required:
            required.append("pool_id")
        wrapped.append(w)
    return wrapped


# ─── Token resolution (see decision A) ────────────────────────────────

def _resolve_token(lp, token_name: str):
    """Resolve a token-name string to the ERC20 object the primitive expects."""
    # V2 / V3 path
    if hasattr(lp, "factory") and hasattr(lp.factory, "token_from_exchange"):
        tokens = lp.factory.token_from_exchange.get(lp.name, {})
        if token_name in tokens:
            return tokens[token_name]
    # Balancer / Stableswap path — verify against Day 2 MockProvider build paths
    if hasattr(lp, "tkn_reserves") and token_name in lp.tkn_reserves:
        # Return the actual ERC20 object as the primitive expects —
        # verify the exact attribute name during Day 3 coding
        ...
    raise ValueError(
        f"Token '{token_name}' not found in pool. "
        f"Available: {_list_pool_tokens(lp)}"
    )


def _list_pool_tokens(lp) -> list[str]:
    """For error messages."""
    ...


# ─── Receipt logging ──────────────────────────────────────────────────

def _log_receipt(tool_name: str, pool_id: str, args: dict,
                 status: str, duration_ms: float,
                 result_summary: str = "", error_type: str = "",
                 error_message: str = "") -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "pool_id": pool_id,
        "args": args,
        "status": status,
        "duration_ms": round(duration_ms, 2),
    }
    if status == "ok":
        event["result_summary"] = result_summary
    else:
        event["error_type"] = error_type
        event["error_message"] = error_message
    print(json.dumps(event, ensure_ascii=True), file=sys.stderr, flush=True)


# ─── Result summarization ─────────────────────────────────────────────

_SUMMARIZERS = {
    "AnalyzePosition": lambda r: f"diagnosis={r.diagnosis}, net_pnl={r.net_pnl:.4f}",
    "SimulatePriceMove": lambda r: f"new_value={r.new_value:.4f}, il={r.il_at_new_price:.4f}",
    "CheckPoolHealth": lambda r: f"tvl={r.tvl_in_token0:.2f}, lps={r.num_lps}, has_activity={r.has_activity}",
    # ... one per tool — hand-curated, one line each
}


def _summarize(tool_name: str, result) -> str:
    fn = _SUMMARIZERS.get(tool_name)
    if fn is None:
        return f"<no summarizer for {tool_name}>"
    try:
        return fn(result)
    except Exception as e:
        return f"<summarizer error: {e}>"


# ─── Dispatch ─────────────────────────────────────────────────────────

async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    t0 = time.monotonic()
    pool_id = arguments.get("pool_id")

    # Validate compatibility
    if name not in _COMPATIBLE_RECIPES:
        err = f"Unknown tool: {name}"
        _log_receipt(name, pool_id or "", arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type="UnknownTool", error_message=err)
        return [TextContent(type="text", text=f"Error: {err}")]

    if pool_id not in _COMPATIBLE_RECIPES[name]:
        err = (f"Tool '{name}' is not compatible with pool '{pool_id}'. "
               f"Compatible pools: {_COMPATIBLE_RECIPES[name]}")
        _log_receipt(name, pool_id or "", arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type="IncompatiblePool", error_message=err)
        return [TextContent(type="text", text=f"Error: {err}")]

    # Build fresh twin
    try:
        snapshot = _PROVIDER.snapshot(pool_id)
        lp = _BUILDER.build(snapshot)
    except Exception as e:
        _log_receipt(name, pool_id, arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type=type(e).__name__, error_message=str(e))
        return [TextContent(type="text", text=f"Error building twin: {e}")]

    # Resolve token-name args, strip pool_id from args passed to primitive
    spec = TOOL_REGISTRY[name]
    primitive_args = {k: v for k, v in arguments.items() if k != "pool_id"}

    # Token resolution for CalculateSlippage.token_in and AssessDepegRisk.depeg_token
    # ... (implement per §A)

    # Invoke primitive
    try:
        result = spec.primitive_cls().apply(lp, **primitive_args)
        duration_ms = (time.monotonic() - t0) * 1000
        summary = _summarize(name, result)
        _log_receipt(name, pool_id, arguments, "ok", duration_ms,
                     result_summary=summary)
        return [TextContent(type="text", text=_serialize_result(result))]
    except Exception as e:
        duration_ms = (time.monotonic() - t0) * 1000
        _log_receipt(name, pool_id, arguments, "error", duration_ms,
                     error_type=type(e).__name__, error_message=str(e))
        return [TextContent(type="text", text=f"Error: {e}")]


def _serialize_result(result) -> str:
    """Serialize a dataclass result to a readable text block for the LLM."""
    # Use dataclasses.asdict + json.dumps with default=str for Decimal etc.
    # Include all fields; LLM reads and decides what matters.
    from dataclasses import asdict
    return json.dumps(asdict(result), indent=2, default=str)


# ─── Server init ──────────────────────────────────────────────────────

async def main():
    server = Server("defipy")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        wrapped = _wrap_schemas_with_pool_id()
        return [
            Tool(
                name=s["name"],
                description=s["description"],
                inputSchema=s["inputSchema"],
            )
            for s in wrapped
        ]

    @server.call_tool()
    async def handle_call(name: str, arguments: dict) -> list[TextContent]:
        return await call_tool(name, arguments)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
```

**The above is structural scaffolding, not verbatim-runnable.** The `mcp` SDK's actual API (class names, method signatures, decorator patterns) may differ from what's sketched. First task once `pip install mcp` completes: open the SDK source or docs, verify the real API, adjust the imports and decorators. Flag any surprises in the Day 3 report.

### Unit tests (`python/test/mcp/test_server.py`) — no stdio

Test the dispatch logic *without* running the stdio transport. Extract `call_tool` into a pure async function that takes `(name, arguments)` and returns content blocks; test it directly.

- `test_schema_wrapping_adds_pool_id` — `_wrap_schemas_with_pool_id()` returns 10 schemas, each with `pool_id` in properties and required
- `test_schema_wrapping_pool_id_enum_matches_compatibility` — `AnalyzeBalancerPosition`'s wrapped schema has `enum=["eth_dai_balancer_50_50"]`
- `test_call_tool_ok_path` — invoke `AnalyzePosition` with valid args against `eth_dai_v2`, assert content returned, no exception
- `test_call_tool_incompatible_pool_returns_error` — invoke `AnalyzeBalancerPosition` with `pool_id="eth_dai_v2"`, assert error content
- `test_call_tool_unknown_tool_returns_error`
- `test_call_tool_bad_primitive_args_returns_error` — e.g., negative `lp_init_amt` on AnalyzePosition
- `test_call_tool_builds_fresh_twin_per_call` — call twice, assert independent `lp` objects (spy on builder or check reserve identity)
- `test_call_tool_strips_pool_id_from_primitive_args` — `pool_id` doesn't reach the primitive's `.apply()`
- `test_resolve_token_v2_path` — `_resolve_token(v2_lp, "DAI")` returns an ERC20
- `test_resolve_token_balancer_path`
- `test_resolve_token_unknown_raises`
- `test_summarizer_coverage` — every tool name in `TOOL_REGISTRY` has a summarizer entry
- `test_receipt_emitted_on_ok` — capture stderr, invoke ok path, assert single JSON line parses with `status=="ok"` and required fields
- `test_receipt_emitted_on_error` — same, invoke error path, assert `status=="error"` with `error_type`

About 15-18 tests. These ensure the server's dispatch is correct even though the stdio loop and Claude Desktop interaction are unit-test-unreachable.

### `python/mcp/README.md`

Terse, copy-pasteable. Sections:

1. **What this is** — one paragraph: MCP server exposing 10 DeFi primitives for Claude Desktop / Claude Code
2. **Install** — `pip install defipy[mcp]` in the venv of your choice
3. **Run standalone (for debugging)** — `python -m python.mcp.defipy_mcp_server` — reads stdio, no stdout but stderr shows receipts
4. **Claude Desktop config** — exact JSON snippet for `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "defipy": {
         "command": "/path/to/venv/bin/python",
         "args": ["/path/to/defipy/python/mcp/defipy_mcp_server.py"]
       }
     }
   }
   ```
5. **Claude Code config** — `claude mcp add defipy python /path/to/defipy_mcp_server.py`
6. **Example questions to try** — the 3 canonical LP questions from the Plan:
   - "I have 10 LP tokens in a 50/50 ETH/DAI Balancer pool where I deposited 5 ETH and 5000 DAI. What's my IL if ETH drops 30%?"
   - "Is the ETH/DAI V2 pool healthy? Any rug signals?"
   - "How exposed is a USDC/DAI stableswap position to a 5% USDC depeg versus holding the tokens?"
7. **Available tools** — bullet list of the 10 tools with one-line descriptions
8. **Viewing receipts** — explain that every tool call logs one line of JSON to stderr; point to Claude Desktop's MCP logs location if known
9. **Pool recipes available** — list the 4 MockProvider recipes
10. **Limitations** — MockProvider only (v2.0); LiveProvider in v2.1; positions are user-supplied numbers, not chain-state

---

## Part 3: Ian verification step

CC cannot complete this alone. After CC confirms:
- Packaging clean-venv install test passes
- All new unit tests pass (~15-18 in `test/mcp/` + 3 in `test/test_packaging.py`)
- Full suite green (~620 tests)
- `python -m python.mcp.defipy_mcp_server` starts without error (ctrl-C to exit)

...CC writes a "Ready for Ian" section at the top of the Day 3 report listing:
- Commit SHA
- Exact `claude_desktop_config.json` snippet with the absolute paths filled in for this machine
- Suggested first question to test the loop
- Where to watch for receipts (stderr log location depends on how Claude Desktop surfaces MCP stderr)

Ian then:
1. Edits `claude_desktop_config.json` per the snippet
2. Restarts Claude Desktop
3. Asks the suggested question
4. Confirms Claude uses a DeFiPy tool (visible in the Claude Desktop UI)
5. Confirms receipts appear in stderr
6. Captures a short screen recording for the v2.0 README / docs
7. Reports back whether the loop closed

If the loop doesn't close, Ian pastes the failure back to CC (or to a fresh session) for triage.

---

## Checklist before declaring Day 3 done (CC-side)

- [ ] `pip install mcp` completed; version recorded for `extras_require` pin
- [ ] `setup.py` packages list regenerated from `find` command; every on-disk sub-package present
- [ ] `setup.py` version → `2.0.0`, description → `"Python SDK for Agentic DeFi"`
- [ ] `setup.py` extras include `"mcp": ["mcp>=X.Y.Z"]`
- [ ] Clean venv install test passes (full command captured in report)
- [ ] `python/test/test_packaging.py` passes
- [ ] `python/mcp/defipy_mcp_server.py` runs via `python -m` without import error
- [ ] `python/test/mcp/test_server.py` passes (15-18 tests)
- [ ] Full suite green — target ~620 tests (603 + ~17 MCP + 3 packaging)
- [ ] `python/mcp/README.md` written and includes both Claude Desktop and Claude Code config
- [ ] Day 3 report written with "Ready for Ian" section at top

Commit message template:

```
feat(mcp): MCP server demo + packaging fix for v2.0 ship

Ships Day 3: packaging gap resolved (all 8 primitive sub-packages +
tools + twin now in setup.py packages=[...]), clean-venv install
verified, and stdio-transport MCP server at python/mcp/ that closes
the full agentic loop.

- setup.py: packages=[...] fully enumerated; version 2.0.0; new [mcp] extra
- python/mcp/defipy_mcp_server.py: MCP stdio server wrapping Day 1 schemas
  with per-call MockProvider twins and stderr JSON receipts
- python/mcp/README.md: install + Claude Desktop/Code config + examples
- python/test/test_packaging.py: import smoke tests (3 tests)
- python/test/mcp/test_server.py: dispatch unit tests (~17 tests)
- Day 3 report includes Ian verification handoff

Part of the 3-4 day minimal ship per DEFIPY_V2_AGENTIC_PLAN.md.
```

---

## When to pause and ask

**Do pause and ask if:**

- The `mcp` SDK's actual API differs materially from the sketch above — specifically if `Server`, `stdio_server`, or the `@server.list_tools()` / `@server.call_tool()` decorator pattern is wrong. Don't silently adapt to a different pattern; surface it so we can confirm the adaptation matches MCP conventions.
- Token resolution for Balancer/Stableswap requires accessing an attribute the Day 2 report didn't name explicitly. The V2/V3 path is understood; the other two may surprise.
- The clean-venv install fails with an error that *isn't* missing-sub-packages (dependency resolution, `gmpy2` compilation, platform-specific build issues). Missing-sub-packages is fixable; other failures deserve a pause.
- The MCP server won't start — check stderr for errors, but if the problem is fundamental (bad imports, async event loop issue) rather than configuration, surface it before thrashing.

**Do not pause and ask about:**

- Whether to put token resolution in the library — no, server-side (§A)
- Whether to bake `pool_id` into Day 1 schemas — no, wrap at server (§B)
- Receipt format — no, single-line JSON to stderr (§C)
- Whether to persist twins across calls — no, fresh per call (§D)
- Whether to validate tool×pool compatibility — yes, always, per §E
- Whether to expose custom pools via MCP — no, 4 recipes only for v2.0
- Whether `mcp` should be in `install_requires` — no, extras only (§F)
- Output schemas on MCP tools — no, not shipping per Day 1 decision
- Rewriting any Day 1 or Day 2 code — no, Day 3 is additive

---

## After Day 3

Once Ian verifies the end-to-end loop, Day 3 is complete and the minimal agentic ship is done. Day 4 covers polish: README refresh with the new tagline, CHANGELOG entry, `DEFIPY_V2_SHIPPED.md` retrospective (written separately — editorial work, better suited to a non-CC session), and tagging `v2.0.0` locally. PyPI push is gated on Day 4 completion, not Day 3.

**Known carry-forward from Day 3 to Day 4:**

- The MCP server's summarizers are one line per tool; Day 4's CHANGELOG should call out that richer observability (full structured events, not one-liners) is v2.1 work.
- The clean-venv install test is manual for v2.0; a CI job that runs it on every PR is Day 5/6 or Phase 2 work.
- The `[mcp]` extras pin picked in Day 3 should be revisited when the MCP Python SDK reaches 1.0. Flag in `V2_FOLLOWUPS.md`.
