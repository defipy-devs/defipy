# DeFiPy v2: Agentic-Ready Substrate

**Status:** Planning document (2026-04-23)
**Context:** Transition from DeFiPy v1 (Analytics SDK, 22 primitives, 504 tests) to v2 (Agentic-Ready Substrate). New tagline: *"Python SDK for Agentic DeFi."*
**Scope:** What DeFiPy v2 does, what it explicitly does not do, and the clean boundary between DeFiPy (library) and DeFiMind (application).

---

## TL;DR

DeFiPy v2 is the **substrate** that any agentic DeFi system needs — exact-math primitives, self-describing tool schemas, chain-state acquisition, structured plans, and traceable invocations. It's not an agent. It doesn't run an LLM. It doesn't hold session state. It doesn't sign transactions.

DeFiMind is **one** agent built on top of that substrate. Other agents — custom LangChain pipelines, MCP-exposed Claude Desktop tools, protocol-team monitoring dashboards, quant notebooks — will build on the same substrate. The boundary is drawn so that DeFiPy earns its "Agentic DeFi" positioning without becoming coupled to any single agent framework.

Tagline test:
- *"scikit-learn is for ML"* — scikit-learn isn't an ML product, it's the substrate everyone builds ML products on top of. Nobody asks "but where's the classifier?" because the library's value is the substrate, not a packaged product.
- *"DeFiPy is for Agentic DeFi"* — same logic. DeFiPy is the foundation; DeFiMind is one thing built on it; so are third-party agents.

---

## Two-Phase Release Strategy

The DeFiPy v2 story unfolds in two distinct phases. Confusing the two has real costs — it either delays shipping working code while waiting for a perfect launch moment, or it burns the launch moment on a minimal ship. Separating them is the strategy.

### Phase 1 — Technical v2.0 ship (now, ~6 days)

**What happens:**
- Minimal agentic skeleton (Days 1-4): `defipy.tools` (Anthropic schemas), `defipy.twin` (MockProvider + LiveProvider stub), packaging fix, DeFiMind demo script
- ReadTheDocs IA reorg (Days 5-6): Option A sidebar, drop v1 Analytics/Onchain sections, add Primitives / Agentic DeFi / State Twin sections, update home page tagline
- Library gets released to PyPI as 2.0.0
- ReadTheDocs gets the v2 structure

**What this is:**
- A technical release that earns the "Python SDK for Agentic DeFi" tagline in code
- Visible to users who find DeFiPy organically via GitHub, PyPI, or existing Google index on RTD
- A foundation real users can start building on today

**What this explicitly is *not*:**
- Not the public launch moment
- Not announced on HN / socials / blog
- Not paired with defipy.org (which doesn't exist yet)
- Not the end of v2 work

ReadTheDocs role in Phase 1: it's the docs site for serious users who find the project. It gets the v2 IA but not a v2 visual rebrand. That's fair to what RTD is — reference docs, not a launch vehicle.

### Phase 2 — Feature depth + defipy.org build (~9-12 months in parallel)

**Library work (v2.1 through v2.3):**
- `LiveProvider` implementation for V2+V3, then Balancer+Stableswap
- Multi-format tool schemas (OpenAI, MCP)
- `defipy.observability` module (decorator-based tracing, structured event emission)
- Planning primitives category (`PlanRebalance`, `PlanZapIn`, `PlanExit`)
- Slippage extensions for Balancer and Stableswap
- Break-even extensions for Balancer and Stableswap
- Possibly: `AssessLiquidityDepth` (V3 tick-walking, the largest remaining original-spec primitive)
- DeFiMind reference agent as a sibling repo

**Website work:**
- defipy.org design and build — treated as its own project with its own plan doc
- Modern static site (Docusaurus / Astro / similar SSG, not Sphinx)
- Information architecture beyond pure docs — gallery, tutorials, community, news, case studies
- Design system / visual identity
- Hosting + deploy pipeline
- Analytics + SEO
- A proper "DeFiPy vs X" comparison page
- DeFiMind reference agent gets a dedicated sub-story on the site

**During Phase 2, ReadTheDocs:**
- Stays live and in sync with library changes
- Continues to serve users who find the project organically
- Accumulates SEO value that the new defipy.org will eventually cross-link to

### Phase 3 — Public launch (end of Phase 2)

**What happens:**
- defipy.org goes live with full v2 feature set, brand, and positioning
- HN post, social announcements, blog post explaining substrate framing
- Cross-links from RTD point to defipy.org as primary
- RTD stays live indefinitely as a mirror or frozen archive — **not hard-deprecated**

### Why RTD is never hard-deprecated

RTD has compounded SEO value over multiple years of indexing. Once Google has indexed a domain's pages, 301-redirecting them forces a re-crawl and re-rank that loses link juice permanently. Scipy, NumPy, and similar packages kept their legacy doc URLs live for years during transitions to new sites — the old URLs either mirror or redirect softly, but don't 404.

Deprecation, if it ever happens, is a 2027+ decision based on actual traffic patterns. Not a pre-scheduled event. The Phase 2 plan assumes RTD lives on.

### Ghost ship risk and mitigation

If v2.0 ships quietly to RTD without any visible change, existing users won't notice the shift. When defipy.org launches months later, they see what looks like a new project and get confused about continuity.

Mitigation: the single visible change on RTD the day v2.0 ships is the home page — new tagline ("Python SDK for Agentic DeFi"), a "What's new in v2.0" banner pointing to the Agentic DeFi section, a link to the demo script. Not a rewrite, just enough signal that v2.0 happened.

### What this means for the 6-day push

The 6-day push is **sized correctly for Phase 1, not Phase 3.** Judge it by:
- Does the library work? (yes, if tests pass and demo closes the loop)
- Does RTD represent v2.0 accurately? (yes, if Option A IA is live and the home page reflects the new tagline)
- Can someone who finds DeFiPy tomorrow build on v2.0? (yes, if Days 1-4 ship)

Don't judge it by:
- Brand polish
- Announcement splash
- defipy.org readiness (doesn't exist)
- Feature completeness of the v2 library roadmap (90%+ is Phase 2)

---

## Competitive Landscape

Before the v2.0 README or Phase 3 announcement commits to positioning claims, the landscape needs to be named honestly. The short version: **DeFiPy is effectively uncontested in the search space where Python developers actually find DeFi libraries.** The longer version separates discoverability from existence.

### Discovery by Python developers (Google "defi python", "python AMM library", "uniswap python SDK")

DeFiPy is the answer. The closest precedent is `gauss314/defi` on PyPI — named literally `defi`, which should make it the default result — but:
- Largely stale; last substantive updates years ago
- V2-only, uses the generic textbook IL formula `IL = 2√p/(1+p) − 1`
- Utilities grab-bag (IL calculator + CoinGecko wrappers + PancakeSwap API queries), not a primitives library
- No agentic claims, no composition pattern, no multi-protocol invariant math
- No MCP integration

Nothing else ranks for these queries. A handful of one-off simulators, hedging calculators, and Excel workbooks exist in the long tail but don't surface on real searches.

DeFiPy's existing ReadTheDocs presence has compounded search equity over multiple years. It ranks above anything else for the relevant Python-developer queries today. That's a real asset, and the Two-Phase release plan is specifically structured to preserve it (see the "Why RTD is never hard-deprecated" section).

### Discovery inside MCP ecosystem catalogs (mcpmarket.com, FlowHunt, MCP server lists)

A small set of DeFi-adjacent MCP servers exist:
- **Uniswap PoolSpy MCP** — tracks newly-created V3 pools across 9 chains (pool discovery only; overlaps DeFiPy's deferred `DiscoverPools` stretch goal, not any shipped primitive)
- **Uniswap Trader MCP** — AI agents executing token swaps with routing (execution-focused, which DeFiPy explicitly doesn't do)
- **Uniswap Pools MCP** — V2/V3/V4 pool data fetching
- **"Crypto Liquidity Pool Analyzer" Claude Code Skill** — claims IL calculations across Uniswap/Curve/Balancer; almost certainly uses textbook approximations rather than hand-derived multi-protocol invariants
- **WAIaaS MCP** — 45-tool wallet/DeFi/NFT/payments surface (much broader, much less depth; different category)

None of these surface on Python-package searches. All are discoverable only by users already browsing MCP directories — a near-disjoint audience from the Python developers who would find DeFiPy on Google. None ship exact cross-protocol invariant math. Most wrap chain queries from The Graph.

### What this means for positioning

**Safe claims for the v2.0 README and Phase 3 announcement:**
- "The Python SDK for agentic DeFi" — defensible because alternatives don't surface on `defi python`
- "Hand-derived exact math across four AMM families" — verifiable, specific, true
- "Composable typed primitives, substrate not agent" — architectural claim backed by the codebase
- "Most DeFi tools wrap APIs. DeFiPy ships the math." — accurate contrast against both Python competitors and MCP servers

**Claims to avoid:**
- "The first DeFi Python library" — gauss314/defi predates it by years, even if stale
- "The only" or "no alternatives exist" — MCP servers exist, they just don't compete in the same discovery space
- "Unique" as a standalone word — always pair with the specific axis (math depth, primitive composition, substrate framing)

### Strategic implication for Phase 2

Two forces could erode the current positioning over the 9-12 month Phase 2 window:

1. **AI-search shift.** If developers start asking Claude or ChatGPT "what's a Python library for DeFi agents?" instead of Googling, the answer depends on what's in LLM training data and MCP catalog signals — not on ReadTheDocs rank. This risk argues *for* MCP-native v2.0 positioning: being the MCP-discoverable Python DeFi library compounds on both search surfaces.

2. **New entrants.** 9-12 months is enough for a direct competitor to ship. The incumbent advantage matters here — shipping v2.0 now and claiming the "agentic DeFi Python SDK" category before anyone else does is worth more than shipping a perfect v2.0 six months late.

Both risks argue for the ship-now-iterate posture the 6-day push codifies.

---

## The constitutional distinction

The boundary is drawn by **what kind of thing each library is**, not by feature-by-feature decisions:

### DeFiPy is a library
- `pip install defipy`, `import defipy`, call functions, get typed results back
- Deterministic, stateless, reproducible
- Zero network calls at core (chain reads behind an optional extra)
- Zero LLM dependencies, ever
- Zero signing keys, ever
- A quant in a Jupyter notebook is the canonical user
- Works identically whether or not an LLM ever touches it

### DeFiMind is an application
- It *runs*. It holds state. It talks to things (LLMs, chains, users).
- Has opinions (prompt strategies, conversation flow, error recovery)
- Imports DeFiPy; DeFiPy doesn't know DeFiMind exists
- Canonical consumer: a developer building an agentic product, or an end user asking an agent a DeFi question
- Not the only such consumer — others build on DeFiPy too

Get those two framings right, and every individual feature slots in obviously.

---

## Why the boundary matters for third-party use

The substrate/application split is the **precondition** for third parties using DeFiPy. Consider these use cases, all of which DeFiPy v2 must support cleanly:

| Consumer | Wants | Needs from DeFiPy | Would reject |
|---|---|---|---|
| Quant in a notebook | Exact-math analytics, no LLM | Primitives + Twin + `MockProvider` | LLM dependencies |
| DeFi protocol team | Internal monitoring dashboard | Primitives + `LiveProvider` for chain reads | Agent runtime pulling in LangChain |
| LangChain-based project | DeFi tools for their own agent | Tool schemas + Twin + primitives | An opinionated DeFiMind runtime they can't customize |
| MCP server developer | Claude Desktop tools | MCP schema export + primitives | Session state, memory, any opinionated wrapper |
| Auditor investigating a pool | Fee-anomaly / rug checks at a specific block | `LiveProvider` at block N + pool-health primitives | Full agent loop |
| **DeFiMind itself** | **All of the above as a clean substrate** | **Everything** | **Substrate decisions made for it by someone else** |

If tool schemas live in DeFiMind, every other LLM framework has to write its own schema adapter. If the State Twin lives in DeFiMind, non-agent consumers can't touch live pools. If the action surface is execution-capable, every consumer inherits a signing-key attack surface they didn't ask for.

The substrate/application split is not architectural elegance for its own sake. It's the thing that makes DeFiPy valuable to more than one agent.

---

## The six gaps, assigned

Each of the gaps between v1 Analytics and v2 Agentic-Ready maps to one side of the line (sometimes both):

| Gap | DeFiPy (substrate) | DeFiMind (application) |
|---|---|---|
| 1. Tool definitions | ✅ Complete ownership | — |
| 2. Agent runtime | — | ✅ Complete ownership |
| 3. State Twin | ✅ Abstraction, builders, providers (Mock + Live via `[chain]` extra) | Operational layer (RPC mgmt, caching, persistence, reorgs) |
| 4. Memory / session | — | ✅ Complete ownership |
| 5. Action surface | ✅ Planning primitives (non-mutating projections) | Execution (if v2 DeFiMind chooses to execute at all) |
| 6. Observability | ✅ Primitive-level hooks | Agent-level receipts, AnchorRegistry |

### Gap 1: Tool definitions → DeFiPy

**What ships:** A `defipy.tools` module that introspects primitive signatures and emits machine-readable schemas in the three common formats (Anthropic tool-use, OpenAI function-calling, MCP).

```python
from defipy.tools import schemas

schemas("anthropic")  # → list of tool-use JSON objects
schemas("openai")     # → list of function-calling JSON objects
schemas("mcp")        # → list of MCP tool definitions
```

**Why in DeFiPy:** Tool schemas are just a different serialization of the primitive interfaces. The primitives already have typed signatures, numpy-style docstrings, and typed dataclass returns. The schemas are *properties of the primitives*, not properties of any particular agent framework. Generated programmatically, versioned with the primitives themselves.

**What stays out of DeFiPy:** Binding the tools to an LLM, running a tool-use loop, handling LLM retries. Those are application concerns.

**Effort:** ~1 day. The primitives were designed for this from session 2026-04-18 onwards; this is plumbing, not design.

### Gap 2: Agent runtime → DeFiMind

**What stays out of DeFiPy:** Planner, orchestrator, conversation handler, intent classifier, tool-binding adapters, LLM call loop, error recovery.

**Why:** The minute DeFiPy imports `anthropic` or `openai` or `langchain`, the library is no longer a pure analytics SDK. The "scipy of DeFi" framing dies, quants get dependencies they don't want, and the library becomes coupled to whichever LLM framework was picked — which ages badly.

**Effort in DeFiMind:** Highly variable. Light (thin SDK wrapper with the LLM doing planning) is days. Heavy (hand-built planner with explicit routing, retries, fallback primitives) is weeks to months. Scoped separately from DeFiPy v2.

### Gap 3: State Twin → split, most in DeFiPy

This is the only gap where the line is genuinely subtle. Split it by concern:

**DeFiPy owns:**
- `StateTwinProvider` abstract base class — defines the `snapshot(pool_id, block_number) → PoolSnapshot` contract
- `PoolSnapshot` dataclass — protocol-agnostic representation of pool state (reserves, LP supply, tick bitmap, weights, A coefficient, etc., in a discriminated union)
- `StateTwinBuilder` — takes a `PoolSnapshot`, returns a fully-constructed `UniswapExchange` / `UniswapV3Exchange` / `BalancerExchange` / `StableswapExchange`
- `MockProvider` — synthetic pools for notebooks and tests (replaces/formalizes the existing conftest fixtures)
- `LiveProvider` — chain reads via web3scout/web3, behind the optional `[chain]` extra

**DeFiMind owns:**
- Caching layer (don't re-read the same pool at the same block twice)
- RPC endpoint management (rate limiting, failover, multi-provider)
- Block reorganization handling (snapshot invalidation)
- Multi-chain routing
- Snapshot persistence across agent sessions

**The test of this split:** A quant should be able to write a notebook that constructs a twin of Uniswap V3 USDC/WETH at block 19,500,000 and runs `AnalyzePosition` on it, *without* installing DeFiMind. If that's not possible, the library is crippled. The `[chain]` extra makes it possible.

**Effort:**
- Abstraction + MockProvider + StateTwinBuilder: ~1 week
- LiveProvider for V2 + V3 first (most common protocols): ~1-2 weeks
- Balancer + Stableswap LiveProviders: ~1 additional week each (can be deferred)

### Gap 4: Memory / session → DeFiMind

**What stays out of DeFiPy:** Nothing here belongs in the library. Primitives are stateless by design; adding memory breaks that. Session continuity is an application concern.

### Gap 5: Action surface → split along the execute/plan line

This is where a major product decision lives. My strong recommendation: **DeFiPy v2 ships plan-only.**

**DeFiPy owns — Planning primitives:**
- Generalize the existing `OptimalDepositSplit` pattern (non-mutating projection of `SwapDeposit`) into a first-class category
- `PlanRebalance`, `PlanZapIn`, `PlanExit`, etc. — return structured `Plan` objects describing what swaps / deposits / withdrawals would happen, with pre-state and projected post-state
- Still pure library code, still deterministic, still no signing keys
- The output is a data structure the caller can inspect, serialize, approve, or hand to whatever execution runtime they use

**DeFiMind owns — Execution (if it chooses to execute):**
- Signing abstraction (hardware wallet, eth_account, Gnosis Safe bundle builder)
- Transaction simulator (fork-and-replay before sending)
- Human-in-the-loop confirmation flow
- Failure handling (RPC drops, gas spikes, reverts)

**Why plan-only for DeFiPy:**
1. Keeps the safety surface small — no signing keys ever in the library
2. Matches the pattern already established by `OptimalDepositSplit`
3. Makes plans portable — the same plan can be executed by Foundry, a Safe bundle, a custom pipeline, or DeFiMind
4. "DeFiPy does the math, you do the trusting" is a defensible positioning

**DeFiMind can choose** whether to build an execution layer at all. Plausibly, DeFiMind v1 ships as plan-only too, and execution is a later tier.

**Effort:**
- Upgrading the projection pattern to a formal `Plan` category: ~1 week
- Wiring existing `OptimalDepositSplit` into the new shape: small

### Gap 6: Observability → split

**DeFiPy owns — Primitive-level instrumentation:**
- Decorator or context manager that emits structured events per `.apply()` call
- Each event includes: primitive name, inputs (dataclass-serialized), output (dataclass-serialized), duration, any errors
- Opt-in — off by default, enabled via context manager or config
- Output format: structured dict / JSON, consumable by any downstream tool

```python
from defipy.observability import trace

with trace() as events:
    result = AnalyzePosition().apply(lp, lp_init_amt, entry_eth, entry_dai)
    scenario = SimulatePriceMove().apply(lp, -0.30, lp_init_amt)

# events is a list of structured records — one per .apply() call
```

**DeFiMind owns:**
- Agent-level receipts (the chain of primitive calls plus reasoning trace plus final recommendation)
- Human-readable summaries
- AnchorRegistry (cryptographic commitment, on-chain anchoring) — real product decision, likely its own separable surface

**Effort in DeFiPy:** ~1-2 days.

---

## The v2 scope for DeFiPy — Minimal Agentic Ship (3-4 days code + 2 days docs)

Strategic decision: ship a **minimal agentic skeletal structure** as DeFiPy v2.0, then iterate from real user feedback rather than pre-building every piece the long-form plan anticipated. The fuller scope (LiveProvider, observability module, planning-primitive category, multi-format tool schemas) becomes v2.1+.

The bar for v2.0: *someone can bind DeFiPy primitives to an LLM and ask an LP question, get an answer backed by exact math.* That's it. If that loop closes end-to-end on Day 3, the "Python SDK for Agentic DeFi" tagline is earned.

### Day 1 — `defipy.tools` (MCP schema generation)

**Goal:** Primitives are self-describing. One function call returns MCP tool definitions for a curated set of ~10 primitives.

**Deliverables:**
- `python/prod/tools/__init__.py` — module init, public API
- `python/prod/tools/schemas.py` — introspects primitive classes, emits MCP tool definitions
- `python/prod/tools/registry.py` — curated list of exposed primitives (not all 22 — curated to the most useful leaf primitives for v2.0)
- Tests in `python/test/tools/test_schemas.py`
- Update `setup.py` to include `defipy.tools`

**Scope cuts for minimal ship:**
- **MCP format only.** Anthropic tool-use JSON and OpenAI function-calling deferred to v2.1 (both derivable from MCP schemas with small wrappers).
- **Hand-curated tool descriptions** (not auto-generated from docstrings). Docstrings are verbose; LLMs want tight tool descriptions.
- **Primitive-to-tool mapping is manual.** Not all 22 primitives make sense as tools — expose the leaf primitives first, let composition happen LLM-side.

**Why MCP-first for v2.0:** Strategic. MCP is the direction the agent ecosystem is heading (Claude Desktop, Claude Code, and third-party MCP clients). Shipping DeFiPy as an MCP-native tool is a stronger positioning than "we emit vendor-specific tool-use JSON." A developer who wants the Anthropic SDK path can derive it trivially from MCP schemas; the reverse is more work. MCP-native also aligns with the el-cheapo execution path — demo runs on Claude Max via Claude Desktop / Claude Code, zero API-billing exposure.

**Curated v2.0 tool set (~10 primitives):**
- `AnalyzePosition` (V2/V3)
- `AnalyzeBalancerPosition`
- `AnalyzeStableswapPosition`
- `SimulatePriceMove` (V2/V3)
- `SimulateBalancerPriceMove`
- `SimulateStableswapPriceMove`
- `CheckPoolHealth`
- `DetectRugSignals`
- `CalculateSlippage`
- `AssessDepegRisk`

Covers the bulk of Q1-Q9 across protocols. Position analytics + scenario simulation + pool health + slippage + depeg risk.

**Full rationale, coverage matrix, per-primitive tool descriptions, and Day 1 assertion shape:** see `doc/execution/V2_TOOL_SET.md`. That doc is authoritative for "what primitives ship as MCP tools in v2.0" — if this section and that doc ever disagree, V2_TOOL_SET.md wins.

### Day 2 — `defipy.twin` (MockProvider + abstraction, LiveProvider stub)

**Goal:** Formalize the test fixtures as a public Provider API. Anyone can build a twin without knowing the fixture internals.

**Deliverables:**
- `python/prod/twin/__init__.py`
- `python/prod/twin/provider.py` — `StateTwinProvider` ABC (skeleton, just the interface)
- `python/prod/twin/snapshot.py` — `PoolSnapshot` discriminated-union dataclass
- `python/prod/twin/builder.py` — `StateTwinBuilder` (snapshot → exchange object)
- `python/prod/twin/mock_provider.py` — `MockProvider` with pre-configured pool recipes (ETH/DAI V2, ETH/DAI V3, 50-50 ETH/DAI Balancer, USDC/DAI A=10 Stableswap)
- `python/prod/twin/live_provider.py` — **stub only.** Class defined, `snapshot()` raises `NotImplementedError("LiveProvider lands in v2.1 — use MockProvider or construct lp objects manually")`. This is deliberate: the ABC ships, LiveProvider is announced but not delivered.
- Tests in `python/test/twin/test_mock_provider.py`
- Update `setup.py`

**Scope cuts:**
- **No LiveProvider implementation.** Ship the ABC and stub only. Makes the v2.1 promise explicit in code.
- **MockProvider is recipe-based, not arbitrary.** Ships with a fixed set of canonical pools (the fixture pools promoted to public API). Custom pools happen by constructing `PoolSnapshot` directly.
- **`PoolSnapshot` is minimal.** Just what's needed to rebuild the exchange object. No block numbers, no timestamps, no chain_id — those are v2.1 concerns.

### Day 3 — Packaging fix + DeFiMind demo script

**Goal:** (1) Fix the `setup.py` packaging gap. (2) Write the reference demo that proves the agentic loop closes.

**Morning — Packaging fix:**

`setup.py` currently registers only `defipy.primitives` and `defipy.primitives.position`. A fresh PyPI install would be missing the other six primitive sub-packages. v2.0 must fix this:

```python
packages=[
    # ... existing ...
    'defipy.primitives',
    'defipy.primitives.position',
    'defipy.primitives.optimization',    # MISSING in 1.2.0
    'defipy.primitives.comparison',      # MISSING in 1.2.0
    'defipy.primitives.pool_health',     # MISSING in 1.2.0
    'defipy.primitives.portfolio',       # MISSING in 1.2.0
    'defipy.primitives.risk',            # MISSING in 1.2.0
    'defipy.primitives.execution',       # MISSING in 1.2.0
    'defipy.tools',                      # NEW v2.0
    'defipy.twin',                       # NEW v2.0
],
```

Also: bump version to `2.0.0`, update description to `"Python SDK for Agentic DeFi"`, verify install in a clean venv with `pip install -e .` + import test.

**Afternoon — MCP server (the demo):**
- Location: `python/mcp/defipy_mcp_server.py` — **not** inside the library core (runs as an MCP server, imports defipy as a dependency)
- Uses `mcp` Python SDK from Anthropic (https://github.com/modelcontextprotocol/python-sdk) — demo-only dep, not in `install_requires`
- Implements MCP stdio transport: exposes the curated 10-primitive tool set via `list_tools()` and `call_tool()`
- Each `call_tool` invocation: builds a twin from MockProvider, runs the primitive against it, returns the typed dataclass result as a structured MCP content block
- **Print receipts to stderr** — every primitive call logs (tool name, inputs, result). Users see this when running the MCP server with verbose logging. This is the "observability" story without building observability infrastructure.
- Also ship: `python/mcp/README.md` with `claude_desktop_config.json` snippet showing how to wire the server to Claude Desktop, and `claude mcp add` command for Claude Code

**What the "demo" looks like:**

There's no Python script that runs programmatically. The demo is connecting the MCP server to Claude Desktop (or Claude Code) and having a live conversation. User opens Claude Desktop, sees DeFiPy tools available, asks an LP question, Claude calls the tools, answer appears. **Zero API-billing cost** — Claude Max covers it.

Record a short screen capture of the Claude Desktop session for the README / docs. That video is the visible artifact for v2.0.

**Example questions the demo handles:**
1. "I have 10 LP tokens in a 50/50 ETH/DAI Balancer pool where I deposited 5 ETH and 5000 DAI. What's my IL if ETH drops 30%?"
2. "Is this Uniswap V2 pool healthy? Any rug signals?"
3. "Compare how bad a 5% USDC depeg would hit my stableswap position vs a V2 USDC/DAI position."

### Day 4 — Polish and documentation

**Goal:** Presentable. Announcable without embarrassment.

**Deliverables:**
- **README update** — new tagline, "What's new in v2.0" section, 20-line quickstart showing the agentic flow
- **CHANGELOG** — v2.0 entry listing what landed (new modules, curated tool set, MockProvider, LiveProvider stub) and what's deferred (LiveProvider impl, OpenAI/MCP, observability, planning primitives)
- **`doc/execution/DEFIPY_V2_SHIPPED.md`** — retrospective: "this is what v2.0 actually ships vs. what the plan said," naming deferred items explicitly
- **Update `PROJECT_CONTEXT.md`** — primitive count, test count, new v2 modules in file structure reference, new conventions if any emerged
- **Release notes draft** — ~200-word announcement explaining the substrate positioning, ready to paste into GitHub release / social
- **Run the full test suite** — 504 + new tools tests + new twin tests should land somewhere around ~540 passing
- **Tag v2.0.0 locally** — don't push to PyPI until the install is verified end-to-end
- **Prepare MCP catalog listing copy** — draft short + long descriptions, screenshot of the Claude Desktop session from Day 3, list of tools exposed, GitHub URL, installation command. Submissions happen post-ship (Day 7+), but the copy gets written here while the context is fresh.

### MCP catalog submissions (post-ship, Day 7+)

Once v2.0.0 is tagged and pushed to PyPI, submit to MCP directories. Each listing is low-cost (minutes to hours), additive, and compounds for AI-search-era discovery. DeFiPy's distinctive positioning (exact math across 4 AMMs, 22 composable primitives) plays well in these catalogs because they're browsed by agent builders specifically looking for depth beyond chain-query wrappers.

**Priority catalogs:**
1. **modelcontextprotocol.io community servers list** — the official MCP site maintained by Anthropic. Highest-signal listing. PR to the community servers repo.
2. **mcpmarket.com** — the biggest aggregated MCP catalog. Self-serve submission. Appears to be the primary discovery surface for non-technical users exploring MCP tools.
3. **awesome-mcp-servers** GitHub repo — community-maintained curated list. PR-based. High visibility for developers doing GitHub topic searches.
4. **FlowHunt MCP directory** — FlowHunt catalogs the servers and integrates them into their platform. Submission likely requires creating an account.
5. **SERP AI MCP server directory** — another aggregator. Appears to pull from GitHub automatically but confirmation not hurt.

**What each listing needs:**
- Short description (1-2 sentences): "MCP server exposing exact-math DeFi primitives for LP diagnostics across Uniswap V2, Uniswap V3, Balancer, and Curve-style Stableswap. Built on DeFiPy's 22 composable typed primitives."
- Long description (3-5 paragraphs): what it does, what makes it different (hand-derived invariant math, substrate not agent, non-executing/read-only), installation steps, example queries
- Installation command: `pip install defipy` + the Claude Desktop config snippet from `python/mcp/README.md`
- Example queries: the 3 canonical LP questions from Day 3 demo
- Screenshot or short video: the Claude Desktop session capture from Day 3
- GitHub URL, PyPI URL, ReadTheDocs URL
- Category tags: DeFi, Analytics, Uniswap, Balancer, Curve, Python
- License (Apache 2.0)

**Positioning language (reuse from Competitive Landscape section):**
- "Most DeFi MCP tools wrap APIs. DeFiPy ships the math."
- "Hand-derived exact math across four AMM families."
- "22 composable typed primitives — substrate, not agent."
- Do not claim "the first" or "the only" in any listing.

**Expected impact:**
- **Modest initial traffic** — tens to low hundreds of visits in the first weeks. MCP directory audiences are smaller than Google's Python-developer audience.
- **Compounding AI-search signal** — when users in 6-12 months ask Claude/ChatGPT "is there a Python library for DeFi with MCP support?", training-time and retrieval signals from these catalogs affect the answer.
- **Category incumbency** — being the listed "Python DeFi MCP library" means new entrants in Phase 2 arrive second.

Treat catalog submissions as quiet technical distribution, separate from the Phase 3 public launch. Don't conflate them with the defipy.org announcement — they're compounding infrastructure for discovery, not a launch moment.

### What's explicitly deferred to v2.1+

Written down so expectations are clear:

- ❌ `LiveProvider` implementation (ABC ships; impl is v2.1)
- ❌ Anthropic tool-use JSON + OpenAI function-calling schema formats (MCP only for v2.0; both derivable from MCP schemas with small wrappers)
- ❌ `defipy.observability` module (MCP server stderr receipts are enough for v2.0)
- ❌ Planning primitives category (`OptimalDepositSplit` demonstrates the pattern; formalization is v2.1)
- ❌ `FindBreakEvenPrice` / `CalculateSlippage` Balancer+Stableswap extensions (Bucket B, separate track)
- ❌ `AssessLiquidityDepth` (original Tier 1 remaining, V3 tick-walking — dedicated session)
- ❌ `DiscoverPools` (stretch goal from original spec)
- ❌ DeFiMind as a proper separate repo (the MCP server is enough signal for v2.0)

### Risk list for the 3-4 day code push

**1. MCP schema format subtleties.** MCP tool definitions wrap JSON Schema for the input, but require specific content-block types for the response. Complex return types like `Optional[List[float]]` on `PortfolioPosition.entry_amounts` might need hand-curated schemas. Mitigation: curated mapping in `registry.py`, not pure introspection.

**2. MCP server state across calls.** MCP server process lives for the duration of the Claude session. Each `call_tool` invocation should build a fresh twin (stateless) rather than maintain state — matches DeFiPy's primitive contract. Mitigation: explicit "build fresh twin per call" pattern documented in the server code.

**3. MockProvider recipe API design.** Test fixtures evolved organically (factory fixtures for parameter sweeps, simple fixtures for defaults). Deciding MockProvider's canonical API (recipe names? factory methods? both?) deserves 30 minutes of design before coding on Day 2.

**4. `gmpy2` install pain on clean machines.** Fresh `pip install defipy` might trip on `gmpy2` compilation. Test install in a clean venv before announcing. If `gmpy2` is a real headache, consider whether it's essential or can become optional.

**5. Packaging sub-packages correctly.** Fix flagged for Day 3 morning. Verify against actual `pip install` output — egg-info may need rebuilding.

**6. MCP config paths.** Claude Desktop's config lives at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS); Claude Code uses `claude mcp add` command or per-project `.mcp.json`. Document both paths explicitly in `python/mcp/README.md` so users don't have to hunt.

---

## Days 5-6 — ReadTheDocs reorg for DeFiPy v2

Docs reorg is its own concentrated work, not squeezed into Day 4 polish. Target: **ReadTheDocs IA that reflects the substrate/application framing** — visitors understand within 30 seconds that DeFiPy is exact-math infrastructure, not an agent product.

### MCP tool set vs. ReadTheDocs coverage — important distinction

Two different audiences, two different coverage scopes. Don't conflate them:

| Surface | Audience | Scope | Why |
|---|---|---|---|
| **MCP tool set (Day 1)** | LLM calling tools via Claude Desktop/Code | **10 curated primitives** | Tool-use selection degrades with too many options. Curated leaves. Composition happens LLM-side. |
| **ReadTheDocs (Days 5-6)** | Python developers reading reference docs | **All 22 primitives** | A developer doing `from defipy import EvaluateRebalance` expects docs for it. Library surface is fully visible. |

The Primitives section of the v2 ReadTheDocs covers **all 22 primitives across 8 sub-packages.** The curation of 10 for MCP is a tactical v2.0 decision about LLM ergonomics; it's not a statement about which primitives are "real." Every shipped primitive is importable, documented, and tested.

The **Agentic DeFi → Tool Schemas** section of the docs explicitly names which 10 are in the v2.0 MCP tool set and why, with a link to `doc/execution/V2_TOOL_SET.md` for the rationale. Readers who want to compose beyond the 10 get pointed at the full 22 in the Primitives section.

### Decisions locked in

- **Sections kept from v1 docs:** DeFiPy Ecosystem, Getting Started, Tutorials, DeFi Math, API Reference
- **Sections dropped from v1 docs:** Analytics (v1 framing), Onchain (legacy agents)
- **Sidebar ordering: Option A** — foundations first, agentic as capstone
- **Home page title change:** "DeFiPy: Python SDK for DeFi Analytics and Agents" → "DeFiPy: Python SDK for Agentic DeFi" with subtitle "Exact-math substrate for autonomous and LLM-driven DeFi systems."
- **Primitives section coverage: full 22 primitives**, not the 10-primitive MCP curation

### Target IA (Option A)

```
DeFiPy v2 Documentation
│
├── [KEPT] DeFiPy Ecosystem
│   ├── TextBook
│   ├── Courses
│   ├── Hackathons
│   └── Presentations
│
├── [KEPT] Getting Started
│   ├── Quick Start             ← rewritten for v2 primitives
│   ├── Installation            ← mentions [chain] extra (coming v2.1)
│   ├── Licensing
│   └── Migrating from v1       ← NEW: "old code still works; here's what's new"
│
├── [KEPT] DeFi Math
│   ├── Uniswap V2
│   ├── Uniswap V3
│   ├── Balancer                ← NEW (math deserves own page alongside Uni V2/V3)
│   └── Stableswap              ← NEW (same)
│
├── [KEPT] Tutorials
│   ├── Uniswap V2
│   ├── Uniswap V3
│   ├── Balancer
│   └── Stableswap
│
├── [NEW] Primitives            ← the v2 story, autogenerated reference pages
│   ├── The Primitive Contract
│   ├── Position Analysis       ← AnalyzePosition family (4 protocols)
│   ├── Price Scenarios         ← SimulatePriceMove family (3 shipped)
│   ├── Pool Health             ← CheckPoolHealth, DetectRugSignals, DetectFeeAnomaly
│   ├── Risk                    ← CheckTickRangeStatus, AssessDepegRisk
│   ├── Optimization            ← OptimalDepositSplit, EvaluateRebalance, EvaluateTickRanges
│   ├── Comparison              ← CompareFeeTiers, CompareProtocols
│   ├── Execution               ← CalculateSlippage, DetectMEV
│   ├── Portfolio               ← AggregatePortfolio
│   └── Break-Even              ← FindBreakEvenPrice, FindBreakEvenTime
│
├── [NEW] Agentic DeFi          ← substrate framing, crown jewel of v2
│   ├── Overview (Why Agentic?)
│   ├── Tool Schemas (defipy.tools)
│   ├── Binding to Claude
│   ├── Binding to Other LLMs   ← placeholder: "v2.1 — OpenAI, MCP"
│   └── DeFiMind Demo Walkthrough
│
├── [NEW] State Twin
│   ├── Concept
│   ├── MockProvider            ← shipped in v2.0
│   ├── LiveProvider            ← "announced for v2.1, ABC exists"
│   └── Building Custom Twins
│
├── [KEPT] API Reference
│   ├── defipy.primitives       ← autogenerated from docstrings
│   ├── defipy.tools            ← NEW v2 module
│   ├── defipy.twin             ← NEW v2 module
│   ├── defipy.utils.data       ← result dataclasses
│   ├── defipy.process          ← existing process layer
│   ├── defipy.analytics        ← existing analytics
│   └── defipy.agents (legacy)  ← v1 event-driven agents with legacy marker
│
└── [NEW] Roadmap & Changelog
    ├── v2.0 (shipped)
    ├── v2.1 (LiveProvider, OpenAI/MCP schemas, observability, planning primitives)
    ├── v2.2+ (AssessLiquidityDepth, break-even extensions, N-asset)
    └── Changelog
```

### Content migration from v1 sections

Dropped sections' content doesn't die — it's redistributed:

| v1 location | v1 content | v2 destination |
|---|---|---|
| Analytics → Uniswap V2 Simulation | V2 simulation walkthrough | Tutorials → Uniswap V2 |
| Analytics → Uniswap V3 Order Book | V3 order book sim | Tutorials → Uniswap V3 |
| Analytics → Impermanent Loss | IL derivation | DeFi Math (spans both Uni V2 and V3) |
| Analytics → Finite State Machine | FSM walkthrough | Tutorials → Uniswap V2 |
| Analytics → Simple Uni V2 Tree (Parts 1 & 2) | V2 tree sim | Tutorials → Uniswap V2 |
| Onchain → Price Agent | PriceThresholdSwapAgent | API Reference → `defipy.agents` (legacy marker) |
| Onchain → Liquidity Exit Agent | TVLBasedLiquidityExitAgent | API Reference → `defipy.agents` (legacy marker) |
| Onchain → Volume Spike Agent | VolumeSpikeNotifierAgent | API Reference → `defipy.agents` (legacy marker) |
| Onchain → Impermanent Loss Agent | ImpermanentLossAgent | API Reference → `defipy.agents` (legacy marker) |
| Onchain → Pool Events | web3scout pool event decoding | Ecosystem or Web3Scout subsection |
| Onchain → Solidity Script Interfacing | UniswapScriptHelper walkthrough | Ecosystem or Web3Scout subsection |

Legacy markers matter: book chapter 9 readers still need the event-driven agent pages to work. They get a clear "these are v1; v2 uses composable primitives — see Agentic DeFi" banner.

### Day 5 — IA design + core pages (~6 hours)

**Morning (~2 hours) — IA wiring:**
- Set up Sphinx `conf.py` producing the Option A sidebar
- `.readthedocs.yaml` for automatic builds on push
- Theme: **Furo** (lean: clean, modern, good for API docs; small dep)
- `docs/requirements.txt` pinning sphinx + furo + sibling repos needed for autodoc (uniswappy, balancerpy, stableswappy)

**Afternoon (~4 hours) — Core narrative pages:**
- `index.md` (Home) — new tagline, positioning, 10-line quickstart
- `why-defipy.md` — substrate framing, five-consumer table lifted from the v2 plan doc
- `getting-started/quick-start.md` — rewritten for v2 primitives (replaces v1 quick start)
- `getting-started/installation.md` — install surface including `[chain]` extra (coming v2.1)
- `getting-started/licensing.md` — kept as-is (just verify content is current)
- `getting-started/migrating-from-v1.md` — NEW: "your v1 code still works; here's what's new"
- `roadmap.md` — v2.0 shipped items, v2.1 roadmap, v2.2+

### Day 6 — Primitives reference + Core Concepts + polish (~8 hours)

**Morning (~4 hours) — Primitives reference:**
- Sphinx autodoc setup pulling from numpy-style docstrings
- One category-level index page per primitive category (10 total: Position Analysis, Price Scenarios, Pool Health, Risk, Optimization, Comparison, Execution, Portfolio, Break-Even, plus The Primitive Contract overview)
- Each category page: one-line description, list of primitives in the category with links, cross-references to relevant tutorials
- Autogenerated per-primitive pages from docstrings — this is why the numpy-style docstring discipline pays off
- Result dataclass reference autogenerated from `defipy.utils.data` module

**Afternoon (~4 hours) — Core Concepts + Agentic DeFi pages:**
- `agentic/overview.md` — why the substrate framing exists, what v2.0 delivers, what's coming
- `agentic/tool-schemas.md` — how `defipy.tools` works, curated tool set, schema examples
- `agentic/binding-to-claude.md` — Claude Sonnet tool-use loop walkthrough (refer to `defimind_demo.py`)
- `agentic/binding-to-other-llms.md` — placeholder: "OpenAI and MCP support coming in v2.1"
- `agentic/defimind-demo.md` — walkthrough of the demo script shipped Day 3
- `twin/concept.md` — State Twin concept, why it matters
- `twin/mock-provider.md` — MockProvider API, recipes, examples
- `twin/live-provider.md` — LiveProvider announced for v2.1, ABC exists, use MockProvider for now
- `twin/custom-twins.md` — constructing `PoolSnapshot` directly for non-recipe pools
- First local `sphinx-build` to verify compile
- Push to docs repo, verify ReadTheDocs build succeeds
- Add link to docs from DeFiPy README

### Risk list for Days 5-6

**1. Sphinx autodoc cross-repo imports.** Primitives reference `UniswapImpLoss` from uniswappy, `BalancerImpLoss` from balancerpy, `StableswapImpLoss` from stableswappy. Autodoc needs to import those at build time. Mitigation: pin sibling versions in `docs/requirements.txt`; verify RTD build installs them.

**2. Agentic quickstart example and `anthropic` dep.** Docs shouldn't pull in anthropic just to render an example. Mitigation: show code as non-executed `.. code-block::`; link to the demo script for runnable version.

**3. ReadTheDocs free-tier build time.** Usually fine for a library this size, but worth checking build time once autodoc is running across the sibling packages.

**4. v1 docs and inbound links.** Dropping Analytics and Onchain sections may break links from the book or external references. Mitigation: if RTD versioning is live, v1 docs stay at `/en/v1.x/`; v2 goes to `/en/latest/`. Content isn't deleted, just reframed. If versioning isn't live, add redirect notes on the old URLs.

**5. Theme dep pain.** Furo is stable but is an extra dep. Fallback: stick with `sphinx_rtd_theme` (default), ship, upgrade theme post-v2.0 if needed.

### What's deferred to post-v2.0 docs work

- Tutorial notebooks as rendered pages (myst-nb / jupyter-sphinx)
- Search functionality polish
- Versioned docs selector UI if not already configured
- Migration guide depth beyond the one-page overview
- Custom styling / branding
- Interactive API playground

### Total v2.0 timeline

| Days | Work | Outcome |
|---|---|---|
| 1 | `defipy.tools` (Anthropic schemas) | Primitives are self-describing to Claude |
| 2 | `defipy.twin` (MockProvider + ABC + LiveProvider stub) | State Twin concept is real in code |
| 3 | Packaging fix + DeFiMind demo script | Agentic loop closes end-to-end |
| 4 | README / CHANGELOG / PROJECT_CONTEXT / release notes | Presentable, announcable |
| 5 | Docs IA + core narrative pages | ReadTheDocs v2 structure live |
| 6 | Primitives autodoc + Agentic/Twin pages + conf.py polish | Full v2 doc set deployed |

**Total: ~6 days** to a credible DeFiPy v2.0 that earns the "Python SDK for Agentic DeFi" tagline and ships with updated public documentation.

Nothing about this scope is precious. Iterate from user feedback after shipping.

---

## The original 3-4 week scope (deferred to v2.1+)

Originally planned for v2.0, now tracked against v2.1 and beyond:

1. **`defipy.tools` — multi-format schemas** (Anthropic + OpenAI + MCP)
2. **`defipy.twin.LiveProvider` — chain reads** (V2 + V3 first, then Balancer + Stableswap)
3. **`defipy.observability` — primitive-level hooks** (decorator-based tracing, structured event emission)
4. **Planning primitives category** (`PlanRebalance`, `PlanZapIn`, `PlanExit` — formalize the `OptimalDepositSplit` non-mutating-projection pattern)

Reasoning for deferral: each of these is real work (1-2 weeks each for LiveProvider alone), and shipping them together blocks the "Agentic DeFi" positioning on features that can land incrementally post-v2.0. Users who want the agentic loop today don't need OpenAI schemas — they can use Claude. Users who want live chain reads can construct `lp` objects manually in the short term. The minimal v2.0 earns the tagline; v2.1+ fills in the depth.

---

## What DeFiPy v2 is *not*

Important to name explicitly, because the tagline will attract wrong assumptions:

- **Not an LLM wrapper.** No `pip install defipy` dependency on anthropic / openai / langchain. Ever.
- **Not an agent.** No planner, no conversation, no session state, no memory.
- **Not a transaction executor.** No signing keys, no transaction broadcasting.
- **Not opinionated about which LLM you use.** Tool schemas work across frameworks; the library doesn't care.
- **Not a chatbot platform.** User-facing experience is DeFiMind's problem.

What DeFiPy v2 *is*:

- An exact-math primitive library (v1, continuing)
- Self-describing (tool schemas)
- Chain-aware (State Twin with LiveProvider)
- Traceable (observability hooks)
- Action-oriented but non-executive (planning primitives)

---

## Interactions with third-party consumers

Concrete usage patterns DeFiPy v2 enables. Each of these is a real person/project that benefits from the library being substrate rather than agent:

### 1. Quant in a notebook
```python
from defipy.twin import LiveProvider
from defipy import AnalyzePosition, SimulatePriceMove

# Construct a twin of a real pool at a specific block
provider = LiveProvider(rpc_url="https://...")
snapshot = provider.snapshot(
    pool_address="0x88e6...",
    protocol="uniswap_v3",
    block_number=19_500_000,
)
lp = snapshot.build()

# Run standard analytics — no LLM, no agent
result = AnalyzePosition().apply(lp, lp_init_amt, entry_eth, entry_dai)
scenario = SimulatePriceMove().apply(lp, -0.30, lp_init_amt)
```

No LLM involved. Pure library use. This is DeFiPy v1 + state acquisition.

### 2. LangChain-based agent project
```python
from langchain.agents import create_tool_calling_agent
from defipy.tools import schemas
from defipy.tools import bindings  # returns LangChain-compatible Tool objects

tools = bindings.langchain()  # auto-generated from primitive signatures
agent = create_tool_calling_agent(llm, tools, prompt)
```

The LangChain user binds DeFiPy primitives to their own agent runtime. They never touch DeFiMind. DeFiPy's tool schemas and binding helpers make this straightforward.

### 3. MCP server for Claude Desktop
```python
from mcp.server import FastMCP
from defipy.tools import schemas

mcp = FastMCP("defipy")

for tool_def in schemas("mcp"):
    mcp.register(tool_def)

mcp.run()
```

A developer exposes DeFiPy primitives to Claude Desktop users via MCP. No agent code, no runtime — just schema export + MCP server.

### 4. Protocol monitoring dashboard
```python
from defipy.twin import LiveProvider
from defipy import CheckPoolHealth, DetectRugSignals

provider = LiveProvider(rpc_url=..., cache_dir="...")

for pool_address in our_protocol_pools:
    snapshot = provider.snapshot(pool_address, "uniswap_v2")
    lp = snapshot.build()
    health = CheckPoolHealth().apply(lp)
    signals = DetectRugSignals().apply(lp)
    emit_alerts_if_needed(health, signals)
```

No LLM, no agent — just analytics against live chain state. DeFiPy v2 is the whole stack.

### 5. DeFiMind (reference agent)
```python
from anthropic import Anthropic
from defipy.tools import schemas
from defipy.twin import LiveProvider

client = Anthropic()
tools = schemas("anthropic")

def run_defimind(user_question, session):
    # Agent runtime orchestrates primitive calls via tool-use loop
    # Manages session memory, conversation state, receipts
    # Builds State Twins on demand via LiveProvider
    ...
```

DeFiMind is one of many consumers. It happens to be the reference implementation, but architecturally it's on equal footing with the LangChain user or the MCP server developer.

---

## Release strategy

### DeFiPy v1.x (current)
- 1.2.0 on PyPI
- Working branch at 22 primitives, 504 tests, three additional cross-protocol siblings
- Consider a 1.3.0 release before v2 work begins — lets users get the cross-protocol primitives without waiting

### DeFiPy v2.0
- New major version signals the "Agentic DeFi" positioning shift
- Required: `defipy.tools`, `defipy.twin` abstraction + MockProvider + StateTwinBuilder, `defipy.observability`, planning primitives
- Optional (via `[chain]` extra): LiveProvider for V2 + V3
- Balancer + Stableswap LiveProvider can ship in 2.1

### DeFiPy v2.1+
- LiveProvider for Balancer + Stableswap
- Additional planning primitives
- AssessLiquidityDepth (the remaining Tier 1 piece, needs V3 tick-walking)
- FindBreakEven extensions for Balancer and Stableswap
- N-asset extensions for the cross-protocol siblings (post v2.x)

### DeFiMind separate-repo release
- DeFiMind the reference agent ships as a sibling repo (defimind or similar)
- Depends on defipy ≥ 2.0
- Its own versioning, its own release cadence
- Explicitly positioned as "one agent built on DeFiPy" — not the only one

---

## What to do first

The DeFiPy v2 work has a clear priority ordering based on what unlocks the most downstream value per unit effort:

1. **`defipy.tools` schema generation** (1 day) — unblocks every downstream agent/MCP/framework consumer immediately, even before the rest of v2 lands
2. **`defipy.twin` abstraction + MockProvider** (3-4 days) — formalizes what the test fixtures already do; no external dependencies; makes the State Twin concept real in code
3. **`defipy.observability` hooks** (1-2 days) — small win, high leverage for debugging and receipts
4. **Planning primitives category** (1 week) — upgrades the existing pattern, ships `PlanRebalance` / `PlanZapIn` / `PlanExit`
5. **`LiveProvider` for V2 + V3** (1-2 weeks, `[chain]` extra) — the biggest item, but only needed once items 1-4 are in place

Total: ~3-4 weeks to a credible DeFiPy v2.0 ship. That earns the tagline without overpromising.

---

## The honest marketing story

The risk with the substrate/application split is that DeFiPy v2 can look modest to outside observers. *"You added tool schemas and a state twin? Cool, where's the agent?"*

Two mitigations, both of which should be in place before the v2 announcement:

### 1. DeFiMind reference implementation alongside
Not inside defipy, but as a sibling repo using only DeFiPy as a dependency. Demonstrates what the substrate enables. The announcement pairs:
- *"DeFiPy v2.0: Python SDK for Agentic DeFi — the exact-math foundation for autonomous and LLM-driven DeFi systems"*
- *"DeFiMind v0.1: reference agent built on DeFiPy v2.0, demonstrating the stack end-to-end"*

This is the scikit-learn + sklearn-examples pattern. The substrate earns the framing; the reference app proves it works.

### 2. Explicit substrate positioning in the tagline
Not: *"DeFiPy: The Agent for DeFi"* (overclaims, and anyone inspecting the repo realizes it's not an agent)
Instead: *"DeFiPy: Python SDK for Agentic DeFi — exact-math substrate for autonomous and LLM-driven DeFi systems"*

Positions DeFiPy precisely:
- Not competing with individual agent projects
- The infrastructure those projects all want
- Value is in *enabling* agents, not *being* an agent

---

## Answering "will others be able to use this toolkit?"

Yes, by design. The substrate/application split is specifically structured so DeFiPy v2 is useful to:

- **Quants** who want exact-math analytics with no LLM anywhere near their code
- **Protocol teams** who want monitoring dashboards, not agents
- **LangChain / LlamaIndex / AutoGen / any-LLM-framework developers** who want DeFi tools to bind into their own agent
- **MCP server developers** exposing tools to Claude Desktop
- **Auditors and researchers** investigating pools at specific blocks
- **DeFiMind** — the reference agent, on equal footing with every other consumer

If DeFiPy were the agent, it could only be used one way. Because DeFiPy is the substrate, it can be used by any of the above — and by categories of consumers nobody's thought of yet. That's the point.

---

## Decision record

| Decision | Rationale |
|---|---|
| DeFiPy ships tool schemas | Properties of the primitives, not of any particular LLM framework. Enables third-party agents. |
| DeFiPy does not ship an agent runtime | Would couple the library to a specific LLM framework, alienate non-LLM users, lose the "scipy of DeFi" framing. |
| State Twin abstraction in DeFiPy, operational concerns in DeFiMind | Quants must be able to construct twins without installing an agent. Operational concerns (caching, RPC mgmt) are application-level. |
| DeFiPy v2 is plan-only, not execution-capable | Keeps safety surface small, makes plans portable across execution runtimes, matches the existing non-mutating pattern. |
| Primitive-level observability in DeFiPy, agent-level receipts in DeFiMind | Primitives can be traced by any consumer; agent-level receipts only make sense for agent runs. |
| LiveProvider behind `[chain]` extra, not default install | Core install stays dependency-free. Quants who don't need chain reads don't install web3. |
| V2.0 ships V2+V3 LiveProvider; Balancer+Stableswap in 2.1 | Focused delivery, ships sooner, can iterate. |
| DeFiMind in a separate repo | Clean dependency direction; DeFiMind imports DeFiPy, not vice versa. Explicitly positions DeFiPy as substrate. |
| Two-phase release (technical v2.0 now, public launch later) | Separates shipping working code from burning the launch moment on minimal ship. Protects RTD SEO by never hard-deprecating. |

---

## Fresh Session Kickoff

A fresh Claude session landing on this plan should be able to start Day 1 without re-litigating the strategy. Follow this sequence.

### 0. Read orientation docs (in this order)

1. `doc/PROJECT_CONTEXT.md` — current library state (22 primitives, 504 tests, architecture highlights, Key Internal Conventions, test fixtures). This orients on what already exists.
2. `doc/execution/DEFIPY_V2_AGENTIC_PLAN.md` — this doc. The substrate/application split, the six gaps, the Two-Phase strategy, the Day 1-6 execution plan.
3. `doc/execution/V2_TOOL_SET.md` — **authoritative spec for the 10 curated MCP tools**. Read before Day 1. Covers which primitives ship as MCP, which stay library-only, why, coverage matrix, LP-question mapping, per-primitive tool-description style, and the exact Day 1 assertion shape.
4. `doc/execution/PRIMITIVE_AUTHORING_CHECKLIST.md` — mechanical conventions for adding primitives, including §10 (invariant-math vs state-threading) and §11 (sibling primitives). Relevant if any primitive-layer work surfaces during v2 build (unlikely — no new primitives ship in v2.0).
5. `doc/execution/DEFIMIND_TIER1_QUESTIONS.md` — full 22-primitive spec with dataclass definitions and v1 implementation notes. Reference during Day 1 when writing MCP tool descriptions (for the 10 curated primitives, read the corresponding implementation notes here).

### 1. Verify working-branch state

Before writing any new code:

```bash
cd ~/repos/defipy
pytest python/test/primitives/ -v 2>&1 | tail -5
```

Expected: **504 passed.** If not 504, something has drifted and needs investigation before proceeding.

Also verify:
```bash
git status
git log --oneline -5
```

Working tree should be clean. Recent commits should include the cross-protocol price-move simulators (SimulateBalancerPriceMove, SimulateStableswapPriceMove) and doc updates.

### 2. Begin Day 1 — `defipy.tools`

The first file to create is `python/prod/tools/__init__.py`. Before writing, read:

- `python/prod/primitives/position/AnalyzePosition.py` — canonical primitive pattern
- `python/prod/utils/data/PositionAnalysis.py` — canonical result dataclass
- MCP tool definition format at https://modelcontextprotocol.io/docs/concepts/tools
- MCP Python SDK at https://github.com/modelcontextprotocol/python-sdk

Curated v2.0 tool set is defined in the Day 1 section above (~10 primitives). Don't expand the set in v2.0 — broader coverage is v2.1 work.

**Important:** MCP-only for v2.0. Don't also emit Anthropic tool-use JSON or OpenAI function-calling format — both deferred to v2.1.

First commit for Day 1 should be the `defipy/tools/` scaffold with the curated tool set and passing tests. Commit message pattern:

```
feat(tools): defipy.tools module with MCP tool schemas

Ships v2.0 Day 1 minimal agentic skeleton piece. Curated 10-primitive
tool set covering position analysis, price scenarios, pool health,
slippage, and depeg risk across V2/V3/Balancer/Stableswap.

- tools/__init__.py, tools/schemas.py, tools/registry.py
- MCP format only (Anthropic tool-use + OpenAI deferred to v2.1)
- Hand-curated tool descriptions (not auto-generated from docstrings)
- Tests in python/test/tools/test_schemas.py
- setup.py updated

Part of the 3-4 day minimal ship per DEFIPY_V2_AGENTIC_PLAN.md.
```

### 3. Day-by-day gates

Each day has a concrete pass/fail gate. Don't proceed to the next day until the gate passes.

| Day | Gate |
|---|---|
| Day 1 | `from defipy.tools import get_schemas; schemas = get_schemas("mcp")` returns a list of ~10 MCP tool definitions. Tests pass. |
| Day 2 | `from defipy.twin import MockProvider; p = MockProvider(); lp = p.v2_eth_dai()` returns a UniswapExchange. LiveProvider stub raises NotImplementedError with v2.1 message. |
| Day 3 | MCP server runs: wired to Claude Desktop / Claude Code, LP question asked, Claude calls a DeFiPy tool via MCP, primitive executes against a MockProvider twin, answer synthesized. Packaging fix verified by fresh venv install. |
| Day 4 | README shows new tagline. CHANGELOG has v2.0 entry. Full suite ~540 tests passing. MCP server README + config snippets included. |
| Day 5 | Sphinx builds locally without errors. Option A sidebar renders correctly. Home page tagline updated. |
| Day 6 | ReadTheDocs build succeeds on push. All primitive categories have reference pages (autogenerated). Agentic DeFi + State Twin sections render. |

### 4. Three things to explicitly NOT do during the 6-day push

1. **Don't expand scope mid-flight.** If something seems like "we should also add X," note it in `doc/execution/V2_FOLLOWUPS.md` and keep moving. Phase 2 catches every deferred item.
2. **Don't polish RTD beyond the Option A reorg.** Visual redesign, custom theming beyond Furo, interactive elements — all Phase 2/defipy.org work. RTD just needs the v2 IA and the new tagline.
3. **Don't push v2.0.0 to PyPI until the full 6-day cycle completes and Day 3's packaging fix is verified in a clean venv.** Tag locally, hold the PyPI push until Day 4 polish confirms everything installs and imports correctly.

### 5. If blocked

Common blockers and where to look:

- **MCP schema format questions** → https://modelcontextprotocol.io/docs/concepts/tools
- **MCP Python SDK reference** → https://github.com/modelcontextprotocol/python-sdk
- **Claude Desktop MCP config** → `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS; see `python/mcp/README.md` (shipped Day 3) for exact format
- **Claude Code MCP config** → `claude mcp add` command, or per-project `.mcp.json`
- **MockProvider API design questions** → mirror `python/test/primitives/conftest.py` structure; promote fixture pools to public API unchanged
- **Packaging failures on fresh install** → run `pip install -e .` in a clean venv, then `python -c "from defipy import AnalyzePosition"`; if ImportError, check the `packages=` list in `setup.py`
- **Primitive authoring questions** (if any surface during v2 build) → PRIMITIVE_AUTHORING_CHECKLIST.md, especially §10 and §11

### 6. Close out

At end of Day 6:
- All tests passing
- v2.0.0 tagged locally (not yet on PyPI)
- RTD build succeeding with Option A IA
- `doc/execution/DEFIPY_V2_SHIPPED.md` written as retrospective
- `PROJECT_CONTEXT.md` updated with v2.0 state

After Day 6 verification, push to PyPI. v2.0 is live on both PyPI and RTD. No public announcement yet — that's Phase 3.

---

*DeFiPy v2 is the substrate; DeFiMind is one application. Others will build other applications. The split is what makes that possible. Phase 1 ships the substrate; Phase 2 builds the depth and the website; Phase 3 launches publicly when both are ready.*
