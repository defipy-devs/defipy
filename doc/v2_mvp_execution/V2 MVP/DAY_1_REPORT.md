# DeFiPy v2.0 — Day 1 Completion Report

## Objective

Ship `defipy.tools` — a library module that emits MCP tool schemas for 10 curated primitives. Schemas only, no dispatch, no LLM dependencies.

## Deliverables

**Module:** `python/prod/tools/`
- `__init__.py` — public API (`get_schemas`, `list_tool_names`, `TOOL_REGISTRY`)
- `registry.py` — 10 `ToolSpec` entries, each with a hand-written MCP input schema verified against the primitive's actual `.apply()` signature
- `schemas.py` — `get_schemas(format="mcp")`; raises `NotImplementedError` with v2.1 message for `"openai"` / `"anthropic"`

**Tests:** `python/test/tools/` (52 new tests)
- V2_TOOL_SET.md gate tests (count=10, exact name set)
- MCP format compliance (required fields, properties have type+description, required is subset of properties)
- Format selector (default is mcp; unsupported formats raise)
- **Drift detection** — parametrized over all 10 tools; fires if any primitive's `.apply()` signature diverges from its declared schema
- Registry sanity (primitive_cls is a class, has callable `.apply`, name matches class name)

**Packaging:** `setup.py` updated with `'defipy.tools'`

## The 10 curated tools

| Tool | Protocol | Answers |
|---|---|---|
| `AnalyzePosition` | V2 / V3 | PnL decomposition (IL, fees, net) |
| `AnalyzeBalancerPosition` | Balancer 2-asset | PnL with weight effects |
| `AnalyzeStableswapPosition` | Stableswap 2-asset | PnL with A-coefficient effects |
| `SimulatePriceMove` | V2 / V3 | "What if price moves X%?" |
| `SimulateBalancerPriceMove` | Balancer 2-asset | Same, weighted-pool math |
| `SimulateStableswapPriceMove` | Stableswap 2-asset | Same, stableswap fixed point |
| `CheckPoolHealth` | V2 / V3 | TVL, reserves, LP concentration, activity |
| `DetectRugSignals` | V2 / V3 | Threshold-based rug signals |
| `CalculateSlippage` | V2 / V3 | Slippage %, price impact, max trade size |
| `AssessDepegRisk` | Stableswap 2-asset | IL across depeg levels + V2 benchmark |

## Results

- **Gate passed:** `len(get_schemas("mcp")) == 10`, name set matches V2_TOOL_SET.md exactly
- **Tests:** 556 passing (504 baseline + 52 new)
- **Commit:** `48d0d73` on `main` (not pushed to remote)

## Design notes worth carrying forward

1. **Brief correction:** brief example used `holding_period_years`; actual primitive param is `holding_period_days`. Verified against source, used the real name.

2. **Dispatch-supplied params beyond `lp`:** Two primitives take ERC20 object params (`token_in` on CalculateSlippage, `depeg_token` on AssessDepegRisk). Per the brief's inline "extend if other primitives take other non-scalar args," these are collected into a `DISPATCH_SUPPLIED_PARAMS` frozenset that the drift test strips out, and they don't appear in the MCP schemas. **Day 3's MCP server will need to resolve these (plus `lp`) from context** — likely as tool-level pool address + token-name string fields the dispatch layer maps to objects before calling `.apply()`.

3. **Optional numeric params use `"type": ["number", "null"]`** per the brief's example — explicit nullability, matches JSON Schema. Required fields list the strictly-required params only.

4. **No output schemas.** MCP allows but doesn't require them, Claude doesn't use them for tool selection, and shipping them would double the hand-curation work. Defer to v2.1 if downstream consumers need them.

5. **AssessDepegRisk description** flags the "some levels may be physically unreachable at high A" quirk explicitly — otherwise an LLM would misinterpret `None`-valued fields as errors.

## Environment note

The editable install at `/opt/homebrew/lib/python3.11/site-packages/__editable___DeFiPy_1_2_0_finder.py` was re-pointed from main-repo `python/prod` to the worktree path so `defipy.tools` would resolve during test runs. Run `pip install -e /Users/ian_moore/repos/defipy --no-deps` to repoint after Day 1 if needed.

## Next

Day 2 brief — `defipy.twin` (MockProvider + PoolSnapshot + StateTwinBuilder + LiveProvider stub) — to be written separately per the Agentic Plan.
