# DeFiPy v2.0 — What Actually Shipped

**Status:** Phase 1 technical ship complete as of 2026-04-23. PyPI push gated on upstream `uniswappy 1.7.9` fix (see §Ship blockers below).
**Predecessor:** `DEFIPY_V2_AGENTIC_PLAN.md` (the plan), `DAY_1_REPORT.md`, `DAY_2_REPORT.md`, `DAY_3_REPORT.md` (execution reports per day).
**Purpose:** Lock in what v2.0 actually ships vs. what the plan said. Source-of-truth for Day 5-6 docs work and Phase 2 planning. Internal working doc, not public-facing marketing.

---

## TL;DR

v2.0 ships a 6-day minimal agentic skeleton on top of the v1.2.0 primitives library. Three new modules: `defipy.tools` (MCP schema emission), `defipy.twin` (State Twin abstraction with MockProvider + LiveProvider stub), and a demo MCP server at `python/mcp/defipy_mcp_server.py` that closes the end-to-end agentic loop.

The loop was verified live: a real Claude Desktop session asked "check the health of the eth_dai_v2 pool," Claude selected `CheckPoolHealth`, the MCP server dispatched to a MockProvider-built twin, the primitive ran, the result came back, Claude reasoned about it correctly and suggested composing `DetectRugSignals` as a follow-up. The curation principle from `V2_TOOL_SET.md` ("leaf primitives over composition primitives, let composition happen LLM-side") worked in production.

Test suite: 629 passing (504 primitives + 52 tools + 47 twin + 3 packaging + 23 MCP). Zero regressions against the v1.2.0 baseline.

---

## What the plan said vs. what shipped

### Day 1 — `defipy.tools` (MCP schema generation)

**Planned:** Module emitting MCP tool definitions for a curated set of ~10 primitives. Anthropic tool-use and OpenAI function-calling formats deferred to v2.1. Hand-curated descriptions. Tests verifying schemas match primitive signatures.

**Shipped:** As planned. 10 tool schemas, MCP format only, hand-written per-tool descriptions following the V2_TOOL_SET.md guidance (lead with the question, name protocols explicitly, flag reachability limits). 52 tests including parametrized drift detection across all 10 tools.

**Deviations from the brief:**
- Brief example used `holding_period_years`; actual primitive parameter is `holding_period_days`. Caught by verifying against source before authoring.
- Two primitives take ERC20-object parameters beyond `lp` — `CalculateSlippage.token_in`, `AssessDepegRisk.depeg_token`. Brief's "extend if other primitives take other non-scalar args" inline guidance generalized cleanly into a `DISPATCH_SUPPLIED_PARAMS` frozenset. This has a downstream consequence for the MCP server (§Day 3).

**Design decisions carried forward:**
- Schemas-only in `defipy.tools` — no dispatch, no invocation, no LLM adapters. Preserves the "library is pure analytics; agent runtime lives elsewhere" boundary.
- No `outputSchema` on MCP tool definitions. Claude doesn't use output schemas for tool selection; shipping them would double hand-curation work for zero v2.0 benefit. Reconsider in v2.1 if any consumer needs them.
- Tool names match primitive class names verbatim (PascalCase), not snake_case. Matches V2_TOOL_SET.md verification gate and the "primitives are the tools" framing.

**Commit:** `48d0d73`

### Day 2 — `defipy.twin` (MockProvider + LiveProvider stub)

**Planned:** State Twin abstraction. `StateTwinProvider` ABC, `PoolSnapshot` discriminated union, `StateTwinBuilder`, `MockProvider` with 4 canonical recipes, `LiveProvider` stub raising `NotImplementedError`.

**Shipped:** As planned. 4 recipes: `eth_dai_v2`, `eth_dai_v3`, `eth_dai_balancer_50_50`, `usdc_dai_stableswap_A10`. 47 tests including byte-for-byte consistency with the existing conftest fixtures (V2/V3 reserves, total_supply, liquidity; Balancer tkn_reserves/tkn_weights; Stableswap tkn_reserves/A/dydx all match the fixture outputs exactly). LiveProvider ships with a stable constructor signature (takes `rpc_url`) so v2.1 implementation is not an API break.

**Deviations from the brief:**
- `PoolSnapshot` chose `kw_only=True` on the dataclass hierarchy to avoid inheritance default-value traps (base has `pool_id` required, subclasses add their own required fields cleanly).
- Protocol discriminator set in `__post_init__`, not caller-supplied — prevents `V2PoolSnapshot(..., protocol="balancer")` confusion.
- `V3PoolSnapshot` defers `UniV3Utils.getMinTick/getMaxTick` import to `__post_init__` when full-range defaults are needed — keeps module import lightweight.
- Balancer `pool_shares_init` and Stableswap `decimals` defaulted from conftest values. Brief was ambiguous; CC chose defaults that keep `V2PoolSnapshot(...)` minimal-args while supporting custom pools.
- Local `python/test/twin/conftest.py` re-exports fixture factories from `python/test/primitives/conftest.py` via `from primitives.conftest import ...` — avoids ~80 lines of duplication while respecting the rule that the primitives conftest not be modified.

**Design decisions carried forward:**
- `MockProvider` returns bare exchange objects via the snapshot → builder path. The existing conftest fixtures return test-context dataclasses (`.lp`, `.eth`, `.dai`, `.entry_x_amt`, etc.) — MockProvider does not. Test context is the caller's responsibility (notebook quant, MCP server, future agent).
- Custom pools bypass MockProvider's recipe registry entirely — construct a `PoolSnapshot` directly and pass to `StateTwinBuilder`. No `MockProvider.custom(...)` factory in v2.0.
- `PoolSnapshot` stays minimal — no block_number, timestamp, or chain_id. Those are LiveProvider concerns, added in v2.1 when they're actually needed.
- `conftest.py` not touched. Refactoring the 504 primitive tests to use MockProvider is a post-v2.0 cleanup, tracked in `V2_FOLLOWUPS.md`.

**Commit:** `0aca7c5`

### Day 3 — Packaging fix + MCP server demo

**Planned:** Fix `setup.py` `packages=[...]` so fresh PyPI installs are importable. Build stdio-transport MCP server at `python/mcp/defipy_mcp_server.py` exposing the 10 curated tools, dispatching to MockProvider-built twins, logging receipts to stderr. README with Claude Desktop / Claude Code config. Verification via a live session.

**Shipped:** As planned, plus two gotchas worth preserving.

- **Packaging:** 35 concrete packages enumerated from on-disk scan. `version` → `2.0.0`, `description` → `"Python SDK for Agentic DeFi"`, new `extras_require["mcp"] = ["mcp >= 1.27.0"]` (demo-only dep, not in `install_requires`).
- **MCP server:** ~330 lines. Async stdio using `mcp.server.Server` + `mcp.server.stdio.stdio_server`. Wraps Day 1's `get_schemas("mcp")` output by injecting a per-tool `pool_id` enum (narrowed to each tool's compatible recipes via `_COMPATIBLE_RECIPES`). Token resolution (`_resolve_token(lp, name)`) handles V2/V3 via `lp.factory.token_from_exchange[lp.name]` and Balancer/Stableswap via `lp.vault.get_token(name)`. Receipts emit as single-line JSON to stderr — one line per `call_tool` invocation with `ts / tool / pool_id / args / status / duration_ms / result_summary` (ok) or `error_type / error_message` (error).
- **Unit tests:** 23 tests in `python/test/mcp/test_server.py` covering schema wrapping, dispatch paths, token resolution per protocol, compatibility enforcement, fresh-twin-per-call semantics, summarizer coverage, and receipt emission.
- **README:** install, Claude Desktop config, Claude Code config, example questions, tool inventory, pool recipes, receipts viewing, troubleshooting.

**Two gotchas — preserve these.**

1. **`python/mcp/` cannot have an `__init__.py`.** If it does, and `python/` or an ancestor is on `sys.path`, Python's import resolver treats the local directory as the `mcp` top-level package and shadows the installed MCP SDK. `from mcp.server import Server` then fails with `ModuleNotFoundError: No module named 'mcp.server'`. Don't reintroduce `__init__.py`.

2. **`python/test/mcp/` cannot have an `__init__.py` either.** Same root cause: combined with `python/test/` on sys.path (which the top-level test conftest does) the shadowing recurs. Test conftest loads `defipy_mcp_server.py` via `importlib.util.spec_from_file_location` to sidestep the issue entirely.

**Design decisions carried forward:**
- Token resolution lives in the MCP server, not `defipy.tools`. Day 1's "schemas only" promise stays clean. If a second consumer emerges (notebook agent, LangChain adapter), extract at that point.
- `pool_id` injected by the server at schema-exposure time, not baked into Day 1 schemas. Server wraps `get_schemas("mcp")` output with a `pool_id` enum per-tool. Day 1's 52 tests don't change.
- Single-line JSON receipts. Structured enough to grep and parse, simple enough to not justify a full observability module in v2.0. Richer observability is v2.1 work.
- Fresh twin per `call_tool` invocation — no cross-call state. Matches the primitive contract (stateless) and sidesteps reorg/invalidation concerns entirely for v2.0.
- Primitive × recipe compatibility validated at dispatch. Incompatible combos return a structured error content block (not an exception) with the compatible pools enumerated in the message — Claude can read and recover.
- `mcp` SDK is extras-only (`pip install defipy[mcp]`), never in `install_requires`. Users running `pip install defipy` don't pay the dependency cost.

**Commit:** `<day-3-commit-sha-pending>` — resolve from `git log` after editorial work commits.

### End-to-end verification

**Query:** "Using the DeFiPy tools, check the health of the eth_dai_v2 pool."

**Claude's behavior:** Selected `CheckPoolHealth` with `pool_id="eth_dai_v2"`. Received the serialized dataclass, rendered pool state + activity + LP structure into clean prose, correctly inferred the "single LP + zero activity = MockProvider initial state" pattern, proactively offered `DetectRugSignals` as the follow-up for formal risk classification. All numbers matched the recipe exactly (1000 ETH / 100000 DAI, spot price 100, 10000 LP tokens outstanding, 1 LP at 100% share, 2000 ETH-equivalent TVL).

The substrate works as designed. The curation principle (leaf primitives, let composition happen LLM-side) held — Claude composed `CheckPoolHealth → (mentions) DetectRugSignals` correctly based solely on the tool descriptions, without needing an explicit composition primitive in the curated set.

---

## Ship blockers for PyPI push

Three upstream sibling packages needed fixes. All three shipped.

### Shipped

- **`balancerpy 1.1.0`** — added `balancerpy.analytics.risk` to `packages=[...]`. Previously 1.0.6 was missing the sub-package; fresh PyPI installs got ImportError on `from balancerpy.analytics.risk import BalancerImpLoss` despite the code existing in the source tree.

- **`stableswappy 1.1.0`** — same fix for `stableswappy.analytics.risk`.

- **`uniswappy 1.7.9`** — removed the spurious `import pytest` at `UniV3Utils.py:30` that was breaking non-dev environment installs. Note: an earlier `uniswappy 1.7.8` attempt to fix this shipped to PyPI without the actual source change landing (version bump built from an unchanged tree); the 1.7.8 slot on PyPI remains burned. The 1.7.9 release was verified by inspecting the wheel contents with `unzip -p dist/UniswapPy-1.7.9-py3-none-any.whl uniswappy/utils/tools/v3/UniV3Utils.py | grep -c "^import pytest"` before upload, which returned 0.

### Post-push follow-ups

- Bump defipy's `install_requires` has already been updated to pin `uniswappy>=1.7.9`, `balancerpy>=1.1.0`, `stableswappy>=1.1.0`.
- The `uniswappy 1.7.8` slot on PyPI is permanently broken for new installs. Any user pinned to `uniswappy==1.7.8` hits the `import pytest` error.

**Gate for PyPI push: clean-venv `pip install defipy` succeeds, imports resolve, the end-to-end smoke test runs through AnalyzePosition against an `eth_dai_v2` MockProvider recipe.** Verified locally 2026-04-23. Ready for `twine upload`.

---

## What's explicitly deferred to v2.1+

Written down so expectations stay honest across Phase 2 planning.

### Library modules
- **`LiveProvider` implementation.** ABC + stub shipped; on-chain snapshot construction via web3scout/web3 is v2.1. The constructor signature is stable — implementing `.snapshot()` is not an API break.
- **`defipy.observability` module.** MCP server stderr receipts are the v2.0 observability story. Structured event sink (decorator-based tracing with opt-in context manager) lands in v2.1.
- **Planning primitives category.** `OptimalDepositSplit` demonstrates the non-mutating projection pattern; formalizing `PlanRebalance` / `PlanZapIn` / `PlanExit` as a first-class category with typed `Plan` return objects is v2.1.
- **Anthropic tool-use and OpenAI function-calling schema formats.** Derivable from MCP schemas with small wrappers when a consumer needs them.

### Primitive extensions
- **`FindBreakEvenPrice` / `FindBreakEvenTime` Balancer + Stableswap extensions** — requires break-even derivations in the sibling IL libraries.
- **`CalculateSlippage` Balancer + Stableswap extensions** — Bucket A remaining item.
- **`AssessLiquidityDepth`** — V3 tick-walking primitive, largest remaining unshipped original-spec item. Dedicated session when scheduled.
- **`DiscoverPools`** — stretch goal from original Tier 1 spec, web3scout-dependent.

### Curated MCP tool set expansions
The v2.0 tool set is 10 leaf primitives. v2.1+ candidate promotions once blockers clear are tracked in `V2_TOOL_SET.md §v2.1+ candidate promotions`:
- `FindBreakEvenPrice` / `FindBreakEvenTime` (blocked on Balancer/Stableswap extensions)
- `CompareProtocols` (once all 4 protocols have slippage + position parity)
- `AggregatePortfolio` (once DeFiMind has session memory)
- `DetectFeeAnomaly` (blocked on UniV3Helper fee passthrough)
- `AssessLiquidityDepth` (doesn't exist yet)

### Infrastructure
- **DeFiMind as a separate repo.** The MCP server at `python/mcp/defipy_mcp_server.py` is the v2.0 reference-agent signal — enough to earn the "Python SDK for Agentic DeFi" tagline without committing to a full sibling repo.
- **CI job running the clean-venv install test on every PR** — manual verification for v2.0; automated in Day 5/6 or Phase 2.
- **defipy.org site** — all Phase 2 work. ReadTheDocs carries the v2 IA alone in Phase 1.

---

## Metrics

| | v1.2.0 baseline | v2.0 shipped |
|---|---|---|
| Primitives | 22 | 22 (unchanged) |
| Library modules | `primitives`, `cpt`, `process`, `analytics`, `agents`, `math`, `utils` | + `tools`, + `twin` |
| Tool schemas emitted | 0 | 10 (MCP) |
| Providers | 0 | 2 (MockProvider + LiveProvider stub) |
| MCP servers shipped | 0 | 1 (demo at `python/mcp/`) |
| Tests | 504 | 629 |
| Sub-packages in `setup.py` | 10 (incomplete — 6 primitive sub-packages missing) | 35 (complete) |
| Clean-venv install works | broken (missing sub-packages + upstream bugs) | verified end-to-end 2026-04-23 |
| End-to-end agentic loop | not present | live-verified in Claude Desktop |

---

## Decisions that held across the 6-day push

These were made up-front in `DEFIPY_V2_AGENTIC_PLAN.md` and re-confirmed in each day's brief. None were relitigated mid-execution.

1. **DeFiPy is library, DeFiMind is application.** The substrate/application split is the architectural axis that makes DeFiPy valuable to more than one agent.
2. **Plan-only, not execution-capable.** Zero signing keys in the library, ever. Planning primitives return `Plan` objects; execution (if any consumer wants it) lives above DeFiPy.
3. **Tool schemas in DeFiPy, agent runtime in DeFiMind.** Schemas are properties of the primitives, not of any specific LLM framework. Runtime is an application concern.
4. **LiveProvider behind `[chain]` extra** (not yet implemented but the extras slot is reserved). Core install stays dependency-free.
5. **Curated 10-tool MCP set.** `V2_TOOL_SET.md` is authoritative. More primitives may get promoted in v2.1 as protocol parity fills in, but v2.0 ships exactly 10.
6. **Two-phase release.** Phase 1 is the technical ship; Phase 3 is the public launch months later when defipy.org is ready. Phase 1 doesn't get announced on HN / socials.
7. **ReadTheDocs never hard-deprecated.** The compounded SEO equity from multiple years of indexing is a real asset. RTD stays live indefinitely; defipy.org eventually cross-links to it.

---

## What the end-to-end loop means

The plan's success criterion was: *"someone can bind DeFiPy primitives to an LLM and ask an LP question, get an answer backed by exact math."* That criterion was met in the verified Claude Desktop session. But the more substantial outcome is the confirmation of two non-obvious claims from the plan:

**1. "Leaf primitives over composition primitives" is the right curation.** Claude composed `CheckPoolHealth` with an implicit reference to `DetectRugSignals` based on tool descriptions alone. The curation deliberately excluded `EvaluateRebalance` (composition-heavy), `AggregatePortfolio` (breadth-chain), and other N-primitive compositions in favor of leaves. The assumption was that LLM-side composition would match or exceed primitive-layer composition in flexibility. The verification session confirmed it — Claude inferred the composition from descriptions without needing a pre-baked composite primitive.

**2. "Hand-derived exact math across four AMM families" is distinctive in a way the user-facing surface exposes.** The LLM response correctly handled numeraire conventions (ETH-equivalent, not USD), correctly interpreted MockProvider initial state (100% single LP wasn't flagged as malicious — correctly attributed to seed state), and correctly anticipated a rug-signal trigger. None of this would have been the default behavior for an LLM wrapping generic DeFi APIs; the primitives' discipline about what they expose (and how they expose it) shaped the agent's reasoning quality.

Both claims are now defensible in the Phase 3 launch content — they're not just architectural assertions but observed behaviors.

---

## State at close

- **Phase 1 technical substrate:** shipped
- **v2.0.0 tagging:** pending commit of Day 4 editorial artifacts
- **PyPI push:** ready; clean-venv install verified end-to-end
- **ReadTheDocs v2 reorg:** Day 5-6
- **Public launch (Phase 3):** months out, paired with defipy.org

Working branch at 629 tests passing. Zero regressions against v1.2.0. Editable install and clean-venv PyPI install both functional.

*DeFiPy v2 is the substrate; DeFiMind is the eventual application; others will build other applications. The split was set in the plan and held through execution. Phase 1 made the substrate real.*
