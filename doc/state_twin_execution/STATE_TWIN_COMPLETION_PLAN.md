# State Twin Completion — v2.1 Plan

**Status:** Forward-looking plan (2026-04-25)
**Predecessor:** `DEFIPY_V2_AGENTIC_PLAN.md` (the v2.0 plan), `DEFIPY_V2_SHIPPED.md` (the v2.0 retrospective)
**Successor docs:** `STATE_TWIN_PHASE_1.md`, `STATE_TWIN_PHASE_2.md`, `STATE_TWIN_PHASE_3.md`
**Purpose:** Authoritative source-of-truth for what State Twin Completion ships and what it explicitly does not. Strategic frame for the three phase docs.

---

## TL;DR

State Twin Completion is the v2.1 work that closes out the State Twin promise made in v2.0's release notes. v2.0 shipped the abstraction (`StateTwinProvider` ABC + `MockProvider` + `StateTwinBuilder`); v2.1 ships the live-state implementation and demonstrates the multi-scenario decision-making pattern.

Three phases, each independently shippable, each with its own acceptance criterion:

1. **Phase 1 — Happy-path V2 LiveProvider** (~1 week dedicated). V2-only, minimal multicall, basic test infrastructure. Independently shippable.
2. **Phase 2 — V2+V3 strategically-tight LiveProvider** (~1-2 additional weeks). Adds V3, multicall batching, `PoolSnapshot` enrichment, real test infrastructure.
3. **Phase 3 — Fork-and-evaluate demo** (~1-2 weeks). Self-contained script proving the multi-scenario simulation pattern against a real V3 pool.

Total dedicated work: **3-5 weeks**. Calendar pace: 4-8 weeks at sustainable part-time effort.

After phase 3 ships, v2.1 tags. The State Twin abstraction is infrastructurally complete (live chain reads work) and demonstrably exercised (the multi-scenario pattern has a worked example in code).

---

## Why three phases, not one release

Each phase has a clean acceptance criterion and ends with substrate-plus-something-shippable. This matters for two reasons:

1. **Independent shippability is risk insulation.** If something pulls you away mid-rollout — an unrelated commitment, an inbound conversation that wants velocity — you can stop after any phase with a defensible artifact in hand. Phase 1's V2-only LiveProvider is real substrate. Phase 2's V2+V3 LiveProvider is the version worth pitching from. Phase 3's demo is what makes the State Twin paper writable.

2. **Each phase shapes the next.** Phase 1's test infrastructure decisions get reused (and possibly elevated) in phase 2. Phase 2's V3 substrate is what makes phase 3's demo land hard rather than land politely. Doing them in order is cheaper than doing them in parallel because earlier work informs later work — same dynamic that made the v2.0 push fast.

The three-phase structure is also what makes "completion" honest as a label. A single-release v2.1 with everything bundled would either ship slowly (waiting for the demo before tagging) or ship incomplete (LiveProvider without the demonstration that justifies the State Twin framing). Three phases lets each piece complete on its own terms.

---

## Scope discipline — what's in and what's out

State Twin Completion is **strictly defipy OSS**. No third-party orchestration, no sibling repos, no external services. The work lives entirely in the defipy repo and merges to main as v2.1.

### In scope

- `defipy.twin.LiveProvider` implementation for Uniswap V2 and V3
- `PoolSnapshot` enrichment with `block_number`, `timestamp`, `chain_id`
- Test infrastructure for chain-reading code (mocked-RPC patterns, fixture parity with `MockProvider`)
- Multicall batching where it materially affects performance (V3 reads)
- A self-contained demo script in `python/examples/` (or equivalent) demonstrating fork-and-evaluate
- Whatever small library utilities surface naturally during demo work (probably `PoolSnapshot.clone()`; possibly nothing)
- README updates and CHANGELOG entry for v2.1
- ReadTheDocs pages for `LiveProvider` and the State Twin pattern as a worked example
- `[chain]` extras_require slot populated with web3 / web3scout dependencies

### Out of scope

- **Balancer + Stableswap LiveProviders.** Substrate *expansion*, not completion. Demand-driven for v2.2+.
- **`AssessLiquidityDepth` (V3 tick-walking primitive).** Original-spec Tier 1 item still unshipped. Dedicated session, not bundled into Completion.
- **Multi-format tool schemas (Anthropic tool-use JSON, OpenAI function-calling).** Derivable from MCP schemas with small wrappers when a consumer asks. Out for now.
- **`defipy.observability` module.** v2.0's MCP server stderr receipts continue to serve as the observability story for v2.1.
- **Planning primitives category formalization.** `OptimalDepositSplit` continues to demonstrate the pattern. Formalization waits for an execution-capable consumer to pull on it.
- **DeFiMind sibling repo.** No agent runtime, no LLM orchestration, no tool-use loops. The fork-and-evaluate demo is a Python script invoked from the command line. Not an agent.
- **MCP server changes.** The v2.0 MCP server at `python/mcp/defipy_mcp_server.py` continues to work as shipped. State Twin Completion does not add new tools to it, does not expose fork-and-evaluate via MCP, does not modify dispatch.
- **Third-party agent framework adapters.** No LangChain bindings, no MCP catalog of additional servers.
- **Distribution work.** PyPI push for v2.1, MCP catalog submissions, screen recordings, reference notebooks — these are distribution-thread items, not Completion-thread items. They run in parallel as background work but are tracked separately.
- **State Twin paper drafting.** The paper is writing-paced work that compounds after Completion ships. Tracked separately.
- **Conditional engagement work (Odos/Veda pitches, foundation grant outreach).** External and demand-driven. Tracked separately.

The "Completion" name is doing real scope-discipline work. Anything that doesn't close the State Twin promise as written in v2.0's release notes goes on the deferred list, not in this rollout.

---

## What "the State Twin promise" actually means

Pulled apart from the v2.0 release notes and `DEFIPY_V2_AGENTIC_PLAN.md`, the State Twin idea bundles three claims:

1. **Abstraction claim** — *"there is a Provider interface that produces twins from any source (mock, live), and the same primitives work against any of them."* Architectural statement about substrate. **Already done in v2.0.**

2. **Live-state claim** — *"twins reflect real chain state at a specific block, so analysis runs against actual mainnet pools, not synthetic ones."* What makes the substrate useful for the protocol-team and notebook-quant use cases. **Phase 1 + Phase 2 deliver this.**

3. **Decision-making claim** — *"the agent chews through dozens of analytical scenarios on the fly in memory, offchain, before landing on an execution path... no one is doing this."* The strategically distinctive claim that makes State Twin paper-worthy rather than a competent abstraction. **Phase 3 demonstrates this.**

Phase 1 + Phase 2 alone fulfill the claim infrastructurally — the substrate works against real chain state. Phase 3 fulfills the claim *strategically* — the multi-scenario pattern has a worked example that's demonstrably defensible. Both are needed for "Completion" to mean what the name says.

---

## Phase summary

Detail lives in the per-phase docs. High-level shape:

### Phase 1 — Happy-path V2 LiveProvider

- **Time:** ~1 week dedicated
- **Deliverable:** `LiveProvider().snapshot(pool_address, "uniswap_v2")` returns a working `V2PoolSnapshot` from mainnet
- **Acceptance:** Real V2 pool (canonical: USDC/DAI on mainnet) constructs a twin that runs through `AnalyzePosition` and `CheckPoolHealth` producing sensible output
- **What ships:** V2 RPC reads, snapshot construction, basic mocked-RPC tests, `[chain]` extras slot
- **What doesn't ship yet:** V3, multicall batching, `PoolSnapshot` field enrichment, fork-test infrastructure
- **See:** `STATE_TWIN_PHASE_1.md`

### Phase 2 — V2+V3 strategically-tight LiveProvider

- **Time:** ~1-2 additional weeks dedicated (on top of phase 1)
- **Deliverable:** Same as phase 1, plus V3 active-liquidity reads, multicall batching, `PoolSnapshot` enrichment
- **Acceptance:** Real V3 pool (canonical: USDC/WETH 3000bps on mainnet) constructs a twin that runs through V3 primitives at the active price; test infrastructure handles both protocols cleanly
- **What ships:** V3 RPC reads (active-liquidity), multicall via Multicall3, `block_number`/`timestamp`/`chain_id` on snapshots, elevated test infrastructure with mocked-RPC fixtures
- **What doesn't ship yet:** V3 full tick bitmap reads (deferred to v2.1.x or AssessLiquidityDepth work), Balancer/Stableswap LiveProviders
- **See:** `STATE_TWIN_PHASE_2.md`

### Phase 3 — Fork-and-evaluate demo

- **Time:** ~1-2 weeks dedicated
- **Deliverable:** Self-contained script (or notebook) that builds a twin via LiveProvider, forks it N ways under price scenarios, runs primitives against each fork, aggregates into a recommendation
- **Acceptance:** Script runs end-to-end against a real V3 pool, produces interpretable scenario distribution + recommended path; demo lives in `python/examples/` and is referenced from ReadTheDocs as a worked example
- **What ships:** The demo script, possibly a small `PoolSnapshot.clone()` utility if forking surfaces a clean library shape
- **What doesn't ship yet:** Fork-and-evaluate as a first-class library primitive (kept as ad-hoc demo code; promote to library only if a consumer asks)
- **See:** `STATE_TWIN_PHASE_3.md`

---

## Release shape

State Twin Completion tags as **v2.1.0**. Each phase merges to main as a separate branch + PR. Single CHANGELOG entry covers all three phases under a "v2.1 — State Twin Completion" heading.

GitHub release title: `v2.1.0 — State Twin Completion`. Release notes call out:

- What's in (V2+V3 LiveProvider, PoolSnapshot enrichment, fork-and-evaluate demo)
- What's deferred to v2.2+ (Balancer/Stableswap LiveProviders, AssessLiquidityDepth, observability, planning primitives, multi-format tool schemas)
- The State Twin pattern as the conceptual contribution

Same release shape as v2.0: tight scope, named completion criterion, explicit deferral list.

---

## Decisions locked in up-front

These are settled before phase 1 starts. Don't relitigate during execution.

| Decision | Rationale |
|---|---|
| State Twin Completion is OSS-only, no third-party orchestration | Preserves substrate-not-product framing; keeps work bounded; makes pitches cleaner |
| V2+V3 only for v2.1; Balancer/Stableswap deferred | V2+V3 cover ~80% of relevant DeFi liquidity; substrate expansion is demand-driven |
| Fork-and-evaluate demo is a script, not a library primitive | Keeps substrate small; promote to library utility only if consumer asks |
| MCP server unchanged | v2.0 demo continues to work; phase 3 demo is invoked directly, not via MCP |
| `[chain]` extras_require for web3/web3scout deps | Core install stays dependency-free; chain reads opt-in |
| Test infrastructure: mocked-RPC primary, Anvil fork as optional integration tier | Mocked-RPC keeps CI fast; Anvil for genuine integration confidence; decision fully made in phase 1 |
| No LiveProvider state across calls | Stateless per `.snapshot()` invocation. Caching/persistence is a consumer concern. |
| `PoolSnapshot` carries minimum chain context (block_number, timestamp, chain_id) | Enough for consumer-side caching and reorg awareness; no more |
| Demo uses a real mainnet block, not synthetic data | Pitch credibility requires the demo to run against actual liquidity, not toy state |

---

## What's explicitly NOT this rollout

Repeating because the temptation will be real during execution:

1. **Speculative v2.1 items from `DEFIPY_V2_AGENTIC_PLAN.md`** — observability module, planning primitives category, multi-format tool schemas, AssessLiquidityDepth. All deferred. The plan doc treated v2.1 as a grab-bag; State Twin Completion narrows it to the items that actually close the State Twin promise.

2. **Balancer + Stableswap LiveProviders** — substrate expansion, demand-driven, v2.2 work.

3. **Fork-and-evaluate as a primitive in `defipy.twin`** — stays in the demo. Promote only on consumer pull.

4. **Distribution work** — PyPI push, catalog submissions, screen recording, reference notebooks. Background-paced, tracked in a separate thread.

5. **State Twin paper** — writing-paced, after Completion ships, tracked separately.

6. **Odos/Veda pitches and foundation grant outreach** — conditional-engagement work, external and demand-driven.

If something looks like it doesn't fit on the in-scope list, default to "out." The Completion framing is the scope discipline.

---

## Fresh session kickoff

A fresh Claude session landing on this plan should:

1. **Read this doc first.** It's the strategic frame.
2. **Read `DEFIPY_V2_SHIPPED.md`.** Establishes what v2.0 actually shipped — the substrate Completion builds on.
3. **Read the relevant phase doc** (`STATE_TWIN_PHASE_1.md` for phase 1 work, etc.). Each phase doc is self-contained for execution purposes.
4. **Verify working-branch state.** Tests pass at 629 (504 primitives + 52 tools + 47 twin + 3 packaging + 23 MCP). If not, drift has occurred and needs investigation before phase work begins.
5. **Begin the phase per its doc.** Each phase has explicit deliverables, acceptance criteria, and design decisions to make up-front.

### Three things explicitly NOT to do during State Twin Completion

1. **Don't expand scope.** If something seems like "we should also add X," note it in `V2_FOLLOWUPS.md` (creating it if needed) and keep moving. The Completion framing catches every deferred item.
2. **Don't pre-build orchestration.** Fork-and-evaluate stays a demo script. Anything LLM-shaped, agent-shaped, or session-shaped is not part of this rollout.
3. **Don't tag v2.1.0 until phase 3 ships.** Each phase merges to main, but the version tag waits for the full Completion. v2.1 = all three phases; partial ships use prerelease tags (`v2.1.0-rc1`, etc.) if release-shaped at all.

### When to tag v2.1.0

After phase 3 ships:
- All tests passing (target: ~700+, depending on phase additions)
- LiveProvider works against real V2 + V3 pools
- Demo script runs end-to-end against a real V3 pool
- README and CHANGELOG updated
- ReadTheDocs reflects v2.1
- This doc and the three phase docs all have their retrospective sections populated

PyPI push for v2.1 is distribution-thread work, not Completion-thread work. Tag locally first, push to PyPI as part of distribution.

---

## State at close

When State Twin Completion finishes:

- v2.1.0 tagged
- LiveProvider V2+V3 working against mainnet
- Fork-and-evaluate demo in `python/examples/`
- Substrate fully supports the State Twin promise as written
- Foundation laid for the State Twin paper (separate writing work)
- Foundation laid for Odos/Veda pitches and conditional engagements (separate distribution/conversation work)

After Completion, the next decision points are external — does demand pull on Balancer/Stableswap LiveProviders? does the paper land? does a sponsored-development conversation materialize? — not internal substrate work. The library is in the state where adoption can drive the next round of work, rather than speculative completionism.

*State Twin Completion finishes the substrate's promise. What happens next depends on what the world sends back.*
