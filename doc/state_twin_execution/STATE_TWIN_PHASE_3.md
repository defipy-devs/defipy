# State Twin Phase 3 — Fork-and-Evaluate Demo

**Status:** Forward-looking brief, work not yet started
**Umbrella plan:** `STATE_TWIN_COMPLETION_PLAN.md`
**Predecessor:** Phase 2 (`STATE_TWIN_PHASE_2.md`) — V2+V3 LiveProvider shipped, `PoolSnapshot` enriched, test infrastructure generalized
**Estimated dedicated time:** ~1-2 weeks
**Acceptance gate:** Self-contained Python script builds a twin via LiveProvider against a real V3 pool, forks it N ways under price scenarios, runs primitives against each fork, and produces an interpretable scenario distribution with a recommended path. Demo lives in `python/examples/` and is referenced from a defipy-org page as a worked example.

---

## Goal

Demonstrate the State Twin promise's *strategic* claim — *"the agent chews through dozens of analytical scenarios on the fly in memory, offchain, before landing on an execution path... no one is doing this"* — with an existence proof that runs in code.

Phase 3 is not an agent. It's not DeFiMind. It's a worked example of the multi-scenario simulation pattern, demonstrated against substrate that's now real (V2+V3 LiveProvider from phases 1-2). The demo is what makes the State Twin paper writable and what makes the Odos/Veda pitches lean on a demonstrated artifact rather than an architectural claim.

The acceptance criterion is "the script runs and produces an interpretable result," not "an LLM does this end-to-end." Strictly OSS substrate composition.

---

## Scope — what's in

- A self-contained demo script — `python/examples/state_twin_fork_evaluate.py`. Notebook variant deferred per D14.
- The demo:
  1. Builds a twin via `LiveProvider` against a real V3 pool at a recent block (USDC/WETH 3000bps recommended — same pool used in phase 2's smoke test)
  2. Forks the twin into N copies (N = 20-50, configurable) under different price scenarios — uniform spread, log-normal sample, or hand-specified scenarios
  3. Runs one or more primitives against each fork (recommended: `AnalyzePosition` + `SimulatePriceMove` for position context, optionally `CheckPoolHealth` for health context)
  4. Aggregates results into a scenario distribution — expected value, percentile bounds, dispersion
  5. Produces a recommendation — e.g., "stay in current range" / "rebalance to range X" / "exit position" — with a confidence/score basis
  6. Outputs a clean human-readable summary (text or simple plot)
- Whatever small library utilities surface naturally during demo work — most likely `PoolSnapshot.clone()` or a fork helper, possibly nothing if Python's `copy.deepcopy` handles snapshots cleanly
- defipy-org docs page at `src/content/docs/fork-evaluate.mdx` (slug: `/fork-evaluate/`) walking through the pattern with code excerpts from the demo. Lives under the existing State Twin sub-group in the sidebar (`astro.config.mjs` update required to add it).
- A short pointer on the home page (`src/content/docs/index.mdx` on defipy-org) and/or the State Twin Concept page, linking to the fork-evaluate page as the canonical worked example
- README update mentioning the demo and how to run it (links to `https://defipy.org/fork-evaluate/`, not RTD)

## Scope — what's out

- **Fork-and-evaluate as a first-class library primitive in `defipy.twin`.** Stays in the demo. Promote to library utility (e.g. `defipy.twin.MultiScenarioEvaluator`) only on consumer pull.
- **Agent / LLM orchestration.** Strictly substrate composition. The demo is invoked from the command line via `python state_twin_fork_evaluate.py`, not via a chat interface.
- **MCP server changes.** The v2.0 MCP server is unchanged. Phase 3's demo is not exposed as an MCP tool.
- **Plotting / visualization beyond minimal matplotlib output.** A simple histogram or distribution plot is fine if the script benefits; full dashboard work is out.
- **Sensitivity analysis or formal Monte Carlo machinery.** N hand-specified or sampled scenarios is enough. Variance reduction techniques, quasi-Monte Carlo, importance sampling — all out.
- **Multi-pool / multi-protocol fork-and-evaluate.** Single pool, single twin, N forks of that twin. Cross-protocol scenarios are v2.2+ if anyone asks.
- **Persistent fork results** — the demo runs, prints, exits. No state saved between runs.
- **Anything Balancer or Stableswap.** V3 only for the demo (V2 forking would also work but V3 is more interesting for the multi-scenario claim because it has tick-range positioning).

---

## Deliverables

Files to create or modify in `defipy` repo:

```
python/examples/state_twin_fork_evaluate.py    # NEW — the demo script
                                                # (script only; notebook
                                                # deferred per D14)

python/prod/twin/snapshot.py                   # MODIFY (likely) — add
                                                # PoolSnapshot.clone() or
                                                # equivalent fork helper IF
                                                # demo work surfaces a clean
                                                # need; else leave alone

python/test/twin/test_snapshot_clone.py        # NEW (conditional on the
                                                # above) — tests for clone
                                                # semantics if a clone helper
                                                # is added

README.md                                       # MODIFY — short mention
                                                # of the demo in the
                                                # "What's new in v2.1" or
                                                # "Examples" section, with
                                                # link to defipy.org/fork-evaluate/

CHANGELOG.md                                    # MODIFY — v2.1 entry
                                                # mentioning fork-evaluate
                                                # demo
```

Files to create or modify on `defipy-org`:

```
src/content/docs/fork-evaluate.mdx              # NEW — page walking through
                                                # the fork-and-evaluate
                                                # pattern with code excerpts
                                                # from the demo script

astro.config.mjs                                # MODIFY — add fork-evaluate
                                                # entry under the existing
                                                # State Twin sub-group in
                                                # the sidebar IA

src/content/docs/index.mdx                      # MODIFY (small) — pointer
                                                # to /fork-evaluate/ as the
                                                # canonical v2.1 worked example

src/content/docs/twin-concept.mdx               # OPTIONAL — closing-section
                                                # pointer to /fork-evaluate/
                                                # as "this is what fork-and-
                                                # evaluate looks like in
                                                # practice"
```

---

## Acceptance criteria

Phase 3 ships when all of these pass:

1. **Demo runs end-to-end.** With a working RPC endpoint, `python python/examples/state_twin_fork_evaluate.py` (or the notebook equivalent) runs to completion without errors against the live USDC/WETH V3 pool.

2. **Forks are independent.** N twin forks running primitives in sequence produce independent results — no cross-fork contamination. Asserted by an in-script sanity check (e.g., scenario A's IL ≠ scenario B's IL when scenarios A and B differ).

3. **Output is interpretable.** A reader unfamiliar with the demo can run it, look at the output, and understand: (a) what scenarios were evaluated, (b) what the distribution of outcomes looks like, (c) what the recommended path is, (d) why that path was recommended.

4. **The "no one is doing this" claim has a worked example.** The demo demonstrably runs N scenarios in memory against an offchain twin built from real chain state, with single-digit-second wall-clock time on a typical laptop. This is what makes the multi-scenario claim defensible.

5. **Demo is referenced from docs.** The fork-and-evaluate pattern has a dedicated defipy-org page (`/fork-evaluate/`); the home page or State Twin Concept page links to it; the README mentions it as a v2.1 example.

6. **No new substrate dependencies.** The demo uses LiveProvider, MockProvider (optionally for offline mode), the existing primitives, and standard library tools. No new top-level dependencies in `install_requires`. If matplotlib is used for output, it's optional and the demo runs without it (text fallback).

7. **Existing test suite unaffected.** All v2.0 + phase 1 + phase 2 tests still pass. Any new tests (e.g., for `PoolSnapshot.clone()` if added) pass.

8. **Docs page captures the pattern, not just the demo.** The fork-and-evaluate page on defipy-org explains what the pattern is, why it's useful, and points to the demo as the existence proof. A reader who wants to apply the pattern to their own pool / their own scenarios can follow the page without reading the demo line-by-line.

---

## Design decisions to make up-front

### D13 — Scenario shape

**Options:** Hand-specified scenarios (e.g., `[-30%, -20%, -10%, 0%, +10%, +20%, +30%]`) | Uniformly sampled price moves over a range | Log-normal samples (statistically more realistic for crypto returns) | All of the above

**Recommendation:** Start with **hand-specified scenarios** for the demo body — they're easier to interpret in the output and easier to debug. Add a "sampled" variant as a secondary code path or a notebook cell, with a comment explaining when each is appropriate. Hand-specified scenarios make the demo legible; sampled scenarios make it rigorous. Both serve the "worked example" purpose.

### D14 — Script vs. notebook format

**Decision (locked):** **Script only. Notebook deferred.**

A `.py` file in `python/examples/state_twin_fork_evaluate.py` is the canonical and only demo artifact for v2.1.0. No `doc/notebooks/state_twin_fork_evaluate.ipynb` ships in this phase.

**Why:** Per R20 — two formats means two implementations to keep in sync, and the divergence cost grows fast. Script-only avoids the failure mode entirely. The script is unambiguously runnable, easy to test in CI later, and doesn't require notebook infrastructure to render. If a notebook adds value later (e.g., for a tutorial blog post or a workshop), it gets built post-v2.1.0 from the script as a thin wrapper, not maintained alongside it.

**Implication for the docs page:** the defipy-org `fork-evaluate.mdx` page embeds code snippets *from* the script (copied or referenced) rather than rendering a notebook. This keeps the script as the single source of truth.

### D15 — Forking mechanism

**Options:** `copy.deepcopy()` on the snapshot | `copy.deepcopy()` on the built `lp` exchange object | Add a `PoolSnapshot.clone()` method | Add a `defipy.twin.fork(snapshot, n)` helper

**Recommendation:** **Try `copy.deepcopy()` on the built `lp` first.** The exchange objects are the things primitives mutate (or operate on); the snapshot is just data. If `copy.deepcopy(lp)` produces clean independent forks, no new utility is needed. If it has issues — e.g., shared references to factory objects, recursive references, performance pain at N=50 — then add a targeted `PoolSnapshot.clone()` method that rebuilds via `StateTwinBuilder` and verify clone-then-build is fast enough at scale.

The right answer is the simpler one. Don't preemptively build a fork helper — build it only if `copy.deepcopy` fails the simplicity test.

### D16 — Aggregation / scoring approach

**Options:** Simple mean and percentile bounds | Risk-adjusted metrics (Sharpe-like) | Decision-theoretic (utility function over outcomes) | Something else

**Recommendation:** **Simple mean + 5th/95th percentile + median for the demo body.** Plus an explicit "value-change %" or "IL %" axis so the distribution is interpretable in the units the primitives produce. Risk-adjusted metrics are a layer the consumer adds; the demo's job is to show that the *distribution* is reachable, not to prescribe how to score it.

A short comment in the demo pointing to where a consumer would plug in their own scoring function is more useful than building one in.

### D17 — Recommendation logic

**Decision (locked):** **70% threshold.** If ≥ 70% of price scenarios produce IL worse than -5% (i.e., `il_percentage < -0.05`), the demo's recommendation is `"rebalance"`; otherwise `"hold"`.

**Why:** The demo needs *one* concrete threshold so the output reads cleanly ("42 of 50 scenarios show IL worse than -5% → recommendation: rebalance"). 70% is illustrative-but-defensible — a mild majority signal, not so strict (>90%) that the demo always says hold, not so loose (>50%) that it triggers on coin-flip dispersion. The number is a demo choice, not a substrate prescription.

**Output framing:** the script prints the threshold it used and the count of scenarios that breached it, so a reader understands the recommendation isn't magic — it's a one-line rule applied to a transparent distribution. A short comment in the script points to where a consumer would plug in their own threshold or scoring function. The recommendation is illustrative, not prescriptive — consumers calibrate to their own thresholds.

The point is to demonstrate that *a recommendation is producible from the distribution*, not to prescribe THE recommendation logic.

### D18 — Pool selection for the demo

**Recommendation:** USDC/WETH V3 3000bps on mainnet (`0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`). Same pool used in phase 2's smoke test. Reasons: large liquidity (~$100M+ TVL typically), well-known token pair, V3 with active range positioning, no exotic fee-on-transfer or rebasing weirdness. The demo's narrative is more compelling against a pool readers actually know.

If for some reason the demo needs a V2 variant (simpler pedagogy), USDC/DAI V2 from phase 1 is the same logic.

### D19 — Offline mode / fallback

**Question:** Does the demo require a working RPC endpoint, or can it run fully against MockProvider?

**Recommendation:** **Both, with LiveProvider as the canonical mode.** The demo body uses LiveProvider against the canonical pool. A fallback flag (e.g., `--offline` or a top-of-script constant) switches to MockProvider's `eth_dai_v3` recipe so the demo can run without network access. The fallback exists for CI, for users without RPC access, and for documentation-build environments. The canonical narrative is LiveProvider.

---

## Risks and gotchas to watch

### R14 — `copy.deepcopy` performance on built lp objects
At N=50, deep-copying a `UniswapV3Exchange` with all its nested structures might be measurable. Profile early. If deepcopy is slow, the right fix is probably `PoolSnapshot.clone() → StateTwinBuilder.build()` per fork, which rebuilds the exchange object from scratch — slower per fork but more controlled. Don't optimize prematurely; just measure once and decide.

### R15 — Primitives that mutate `lp`
The primitive contract is "stateless / non-mutating," but verify before assuming. If `AnalyzePosition().apply(lp, ...)` mutates `lp` even in a small way (e.g., updates internal state on the exchange object), running primitives against forks will produce contaminated forks unless the mutation is harmless. The fix if it surfaces: deepcopy the lp inside the demo before each primitive call, not just once at fork time. Note this in the demo's documentation as a substrate caveat.

### R16 — Scenario realism
Hand-specified scenarios like `[-30%, -10%, +10%, +30%]` are easy to interpret but unrealistic for short time horizons. A reader who knows DeFi will notice. Either: (a) frame the scenarios as "rebalance-decision-relevant moves" rather than "expected market moves," (b) add a sampled variant that uses log-normal returns calibrated to recent ETH volatility, (c) explicitly say "this is illustrative; calibrate scenarios to your own price assumptions" in the docs. Probably do (a) and (c).

### R17 — Output verbosity
N=50 scenarios produces a lot of numbers. The demo's output has to be readable. A 50-line dump of "scenario K: IL = X%, value = Y" is unreadable; a 3-line summary "expected IL: -2.1%, 5th %ile: -8.4%, 95th %ile: +1.2%, recommendation: hold" is. Bias toward summarized output with an optional `--verbose` mode for the full per-scenario breakdown.

### R18 — Demo as bait for scope creep
"While we're at it, we could add a multi-pool variant" / "what if the demo also did rebalance simulation" / "shouldn't this be wrapped in a Click CLI." All tempting, all out of scope. The demo's job is to be the existence proof for the multi-scenario pattern, not to be a comprehensive tool. If something feels like it'd make a great addition, it goes in `V2_FOLLOWUPS.md`, not the demo.

### R19 — RPC cost during development
Iterating on the demo will burn through Alchemy/Infura free-tier credits if every test run hits mainnet. Use the `--offline` MockProvider fallback during iteration; reserve LiveProvider mode for end-to-end verification. This is also the right pattern for the eventual ReadTheDocs build environment, which won't have RPC access.

### R20 — Notebook-vs-script divergence
If both formats end up shipping, they have to stay in sync. The cheapest way: build the script first as canonical, generate the notebook from the script (or maintain it manually as a *thin* wrapper that imports from the script). Two independent implementations of the same demo is the failure mode to avoid.

---

## Verification steps before declaring phase 3 done

In order:

1. Run full test suite — all v2.0 + phase 1 + phase 2 + any phase 3 additions pass.
2. Run the demo script against MockProvider (offline mode): `python python/examples/state_twin_fork_evaluate.py --offline`. Output is interpretable, no errors.
3. Run the demo script against LiveProvider (canonical mode): `python python/examples/state_twin_fork_evaluate.py` with a working RPC URL. Output is interpretable, no errors.
4. Wall-clock time for N=50 scenario evaluation against a live snapshot is under ~10 seconds on a typical laptop (excluding the initial chain-read time, which depends on RPC latency).
5. Verify fork independence: instrument the demo to print scenario inputs and outputs, confirm no two scenarios with different inputs produce identical outputs (would indicate cross-fork contamination).
6. Read the defipy-org `fork-evaluate.mdx` page draft. A reader unfamiliar with the work understands: what fork-and-evaluate is, why it's interesting, where the demo lives, how to adapt it to their own use case.
7. Verify README links to `defipy.org/fork-evaluate/`; the home page on defipy-org points at `/fork-evaluate/`; `npm run build` on defipy-org is clean.
8. Verify the CHANGELOG v2.1 entry mentions the demo as one of the v2.1 deliverables.
9. Commit. Suggested message:

   ```
   feat(examples): fork-and-evaluate demo (Phase 3 of State Twin Completion)

   Demonstrates the State Twin pattern's multi-scenario decision-making
   claim with a worked example. Builds a twin via LiveProvider against
   a real V3 pool, forks N=50 ways under price scenarios, runs primitives
   against each fork, aggregates into a recommendation.

   - python/examples/state_twin_fork_evaluate.py: canonical demo script
   - --offline flag for MockProvider fallback (CI, no-RPC environments)
   - ReadTheDocs page documenting the fork-and-evaluate pattern
   - PoolSnapshot.clone() utility added IF deepcopy approach surfaced
     pain (else ad-hoc deepcopy in demo)

   Demo runs end-to-end against USDC/WETH V3 3000bps, N=50 scenarios,
   under 10s wall clock excluding initial chain read.

   This is NOT an agent. It's a Python script demonstrating the substrate
   pattern. DeFiMind / LLM orchestration remain explicitly out of scope
   per STATE_TWIN_COMPLETION_PLAN.md.

   With this commit, State Twin Completion is functionally complete.
   v2.1.0 tag follows after CHANGELOG / README polish.
   ```

10. Tag `v2.1.0` locally (don't push to PyPI yet — that's distribution-thread work).

---

## What this phase does NOT do

- **No agent.** The demo is `python script.py`, not "ask Claude a question."
- **No LLM in the demo.** Substrate composition only.
- **No MCP exposure.** Phase 3's demo is not a new MCP tool.
- **No persistent state.** Demo runs, prints, exits.
- **No multi-pool / multi-protocol.** Single V3 pool, N forks of that one pool.
- **No fork-evaluate as a library primitive.** Stays in the demo file. Promote only if a real consumer asks.
- **No PyPI push for v2.1.** Tagging is fine; PyPI is distribution-thread work.

---

## Stopping point

When phase 3 ships, State Twin Completion is functionally done:

- v2.0 abstraction shipped (substrate)
- Phases 1+2 shipped live-state implementation (V2+V3 LiveProvider, enriched snapshots)
- Phase 3 shipped the multi-scenario demonstration (fork-and-evaluate worked example)
- v2.1.0 tagged locally
- All three claims of the State Twin promise are now substantiated in code

What happens next:
- **State Twin paper drafting.** Writing-paced, separate work, calendar-paced over weeks.
- **Distribution thread.** PyPI push, MCP catalog submissions, screen recording. Background-paced.
- **Conditional engagements.** Odos / Veda / foundation grant outreach. External and demand-driven.
- **v2.2+ substrate work.** Demand-driven only. Balancer/Stableswap LiveProviders, AssessLiquidityDepth, Anvil fork CI lane, observability module — all wait for consumer pull.

State Twin Completion ends here. It's the substrate's promise fulfilled. What happens after depends on what the world sends back.

---

## What actually shipped

*Populated after phase ships. Retrospective voice — what shipped vs. what the plan said, deviations, gotchas that surfaced (especially around D13-D19 and R14-R20), decisions made mid-flight, follow-ups identified for V2_FOLLOWUPS.md or post-Completion work (paper drafting, distribution, conditional engagements).*

*[Reserved.]*

---

## Addendum — Surface `LiveProvider.get_w3()`

**Status:** Added during Phase 3 execution day. Scoped post-Phase 2 after the `with_custom_abi()` and execution-surface conversations crystallized into a clear principle: DeFiPy stays read-only, but the substrate underneath should not be hidden.

**Goal:** Expose the underlying `web3.Web3` instance via a public `LiveProvider.get_w3()` method so callers who need to sign transactions, run direct contract calls outside the snapshot path, or wire LiveProvider into their own broader chain tooling can do so without monkey-patching `_client` or rebuilding their own `ConnectW3`. Keeps DeFiPy's substrate boundary explicit ("we expose the web3 instance, you bring your own signing opinion") rather than implicit ("DeFiPy just doesn't sign txs").

This is the structurally correct escape hatch from earlier conversations — not `with_custom_abi()` (premature flexibility), not `provider.sign_and_send()` (substrate growing into use cases that aren't its job), but the minimum surface that lets the substrate stay small while letting consumers reach the layer underneath.

### Scope — what's in

- `LiveProvider.get_w3()` returns the underlying `web3.Web3` instance
- Lazy client construction: first call to `get_w3()` triggers `_rpc.make_client()`; the resulting `RpcClient` is cached on the instance and shared with subsequent `.snapshot()` calls
- Test path preserved: `LiveProvider._with_client(injected)` continues to work; `get_w3()` returns the injected client's `get_w3()` result
- Docstring captures the read-only-by-design framing and the "bring your own signing opinion" stance
- LiveProvider docs page on defipy-org gets a `## Signing transactions: bring your own` section (≈150 words, one code example showing the pattern — pull `w3` via `get_w3()`, sign and send via the user's own infrastructure)
- README v2.1 "What's new" list gets one bullet for `get_w3()`
- CHANGELOG v2.1 entry adds a line for `get_w3()`
- One new test verifying caching (repeated `get_w3()` calls return the same instance) and one verifying the snapshot path reuses the cached client

### Scope — what's out

- **Any signing logic in DeFiPy itself.** No `provider.sign()`, no `provider.send_transaction()`, no transaction-builder pattern, no key management. The substrate exposes the underlying `web3.Web3` and stops.
- **Connection pooling, retry logic, RPC failover.** The cached client is a single `web3.Web3` instance from one `ConnectW3.apply()` call. Production-grade RPC management is the consumer's responsibility — they can build their own pool around `get_w3()` if they need one.
- **Reconnection on failure.** If the underlying connection dies, `get_w3()` keeps returning the dead instance. Consumers who need reconnection logic build it themselves. (DeFiPy doesn't currently have reconnection logic in the snapshot path either; this is consistent.)
- **Multiple endpoints per LiveProvider.** One `rpc_url` in, one `web3.Web3` out. Multi-endpoint patterns are consumer-side.
- **A `get_client()` method exposing the full `RpcClient`.** Considered briefly during the design conversation. Decided no — `RpcClient` is internal to defipy.twin._rpc and exposing it would lock in the `block_number()` / `chain_id()` / `block_timestamp()` shape as a public surface. `get_w3()` is the minimum useful surface; `RpcClient` stays internal.
- **A `get_w3()` method on `MockProvider`.** MockProvider has no chain connection; the method would have nothing to return. If consumer demand surfaces (e.g., a unified provider interface that callers want to type-check against), revisit — but for now, asymmetry between `LiveProvider` (chain-backed) and `MockProvider` (synthetic) is honest.

### Deliverables

Files to modify:

```
python/prod/twin/live_provider.py              # MODIFY — add get_w3() method
                                                # + lazy client caching
                                                # + docstring update

python/test/twin/test_live_provider_basic.py   # MODIFY (or new file) — add
                                                # caching test + injected-
                                                # client passthrough test

README.md                                       # MODIFY — add bullet to
                                                # v2.1 "What's new" section

CHANGELOG.md                                    # MODIFY — add line under
                                                # v2.1 entry
```

Files to modify on `defipy-org`:

```
src/content/docs/live-provider.mdx              # MODIFY — add
                                                # "Signing transactions:
                                                # bring your own" section
```

### Acceptance criteria

1. `provider = LiveProvider(rpc_url); w3 = provider.get_w3()` returns a `web3.Web3` instance.
2. Subsequent calls to `provider.get_w3()` on the same instance return the same `web3.Web3` (caching verified).
3. Subsequent calls to `provider.snapshot(...)` on the same instance use the same cached client (no new `ConnectW3.apply()` triggered).
4. The injected-client path (`LiveProvider._with_client(fake)`) continues to work; `get_w3()` returns the fake client's `get_w3()` result.
5. The bare install (`pip install defipy` without `[chain]`) does not import web3 at module load time — `from defipy.twin import LiveProvider` still works without the extra. Only calling `get_w3()` (or `.snapshot()`) triggers the lazy import.
6. Calling `get_w3()` without the `[chain]` extra installed surfaces the existing `ImportError` from `_rpc.make_client()` with the same install instructions.
7. Existing test suite passes unchanged.
8. New tests pass: caching test, injected-client passthrough test.
9. README and CHANGELOG entries land. Defipy-org docs page section lands.

### Design decisions made up-front

#### D20 — Cache scope

**Decision:** Cache the `RpcClient` (not just the `web3.Web3`) on the `LiveProvider` instance. First `get_w3()` or `.snapshot()` call constructs it via `make_client()`; both methods reuse it thereafter.

**Why:** `RpcClient` already wraps `web3.Web3` and exposes `block_number()` / `chain_id()` / `block_timestamp()` that `.snapshot()` uses. Caching at the `RpcClient` level keeps both code paths sharing one connection. Caching at the `web3.Web3` level would mean `.snapshot()` has to either reconstruct the wrapper or duplicate the caching. Cleaner to cache once.

**Implication:** `LiveProvider` becomes slightly stateful — it holds one cached `RpcClient` from first use until the instance is GC'd. The "stateless across calls" property in the existing docstring needs updating to specify that *snapshots are stateless* (no caching of pool state, block data, or snapshot results) while *the connection is reused*. Connection reuse is a feature, not a violation of the substrate's discipline.

#### D21 — Method name

**Decision:** `get_w3()`.

**Why:** Mirrors `RpcClient.get_w3()` exactly. The naming convention is already established. Alternatives considered: `web3` as a property (Pythonic but creates a name collision with the `web3` package), `client` as a property (exposes too much surface, locks in `RpcClient` shape), `get_web3_client()` (unnecessarily verbose). `get_w3()` is short, unambiguous, and consistent with the codebase's existing naming.

#### D22 — Method vs. property

**Decision:** Method, not property.

**Why:** The first call has side effects — it triggers `ConnectW3.apply()` which opens an HTTP connection. Properties should generally be cheap and side-effect-free; methods make the cost visible at the call site. Subsequent calls are cheap (cached return), but the first one isn't. Method form makes that asymmetry explicit. Also matches `RpcClient.get_w3()` which is a method for the same reason.

#### D23 — Import-time cost

**Decision:** No change to import-time behavior. `from defipy.twin import LiveProvider` continues to work without `[chain]` installed; only calling `get_w3()` (or `.snapshot()`) triggers the lazy import that fails informatively if web3scout is missing.

**Why:** Preserves the v2.0 invariant that the bare install is dependency-free. The `get_w3()` addition routes through the same `_rpc.make_client()` lazy import that `.snapshot()` uses, so there's nothing to change.

### Risks and gotchas to watch

#### R21 — Connection lifecycle

The cached `RpcClient` lives for the life of the `LiveProvider` instance. Long-running consumer processes that hold a `LiveProvider` for hours may see the underlying connection go stale. The existing snapshot path doesn't address this either, and adding reconnection logic would expand the substrate's responsibility. Document the lifecycle in the docstring ("connection cached for the life of the LiveProvider instance; for long-running processes, construct a fresh LiveProvider periodically or build your own connection-management layer around `get_w3()`"). Don't fix it.

#### R22 — Test mock coverage

The injected-client test path uses a duck-typed `FakeRpcClient`. The new `get_w3()` test must use the existing fake (in `python/test/twin/_fake_rpc.py`) rather than reaching for a separate web3 mock. The `FakeRpcClient` already exposes `get_w3()` (it has to, for the snapshot path); the new test just verifies that `LiveProvider.get_w3()` returns whatever the fake's `get_w3()` returns.

#### R23 — Documentation framing pressure

The "bring your own signing opinion" framing on the docs page could read as either a principled stance (substrate boundary is explicit, consumers retain sovereignty) or a cop-out ("we won't help you sign"). Get the framing right: lead with the *why* (signing infrastructure is opinion-shaped and varies enormously across users; embedding any opinion would be wrong for most), then show the *how* (the snippet), then close with the *what's-not-here* (DeFiPy doesn't sign, and that's deliberate). This matches the read-only-by-design framing already in twin-concept.mdx.

#### R24 — Future demand for transaction tooling

Once `get_w3()` is exposed, consumers will inevitably ask "can DeFiPy also do X with the web3 instance?" — transaction builders, gas estimation helpers, simulation-before-send patterns. The discipline is to keep saying no. `get_w3()` is the substrate boundary; everything beyond it is the consumer's domain or a separate library's. If transaction-tooling demand becomes loud, the right answer is a sibling library (e.g., `defipy-tx` or similar), not absorption into DeFiPy. Track this in `V2_FOLLOWUPS.md` if it surfaces.

### Verification steps

In order:

1. Implement `get_w3()` on `LiveProvider` per D20-D22.
2. Run existing test suite — all passing.
3. Add caching test (repeated `get_w3()` returns same instance).
4. Add snapshot-reuses-cache test (calling `.snapshot()` after `get_w3()` doesn't trigger a new `make_client()`).
5. Add injected-client passthrough test (`LiveProvider._with_client(fake).get_w3() is fake.get_w3()`).
6. Run full test suite — new tests pass, existing tests unaffected.
7. Update README v2.1 "What's new" with the bullet.
8. Update CHANGELOG v2.1 entry.
9. Switch to `defipy-org` repo, add the "Signing transactions: bring your own" section to `live-provider.mdx`.
10. Eyeball the docs section — does the framing land per R23?
11. Run `npm run build` on defipy-org to verify the production build is clean.
12. Commit on the appropriate branches (defipy: directly to main or via a small `feat/get-w3` branch; defipy-org: via the docs branch you've been using).
13. Suggested defipy commit message:

    ```
    feat(twin): expose LiveProvider.get_w3() for signing escape hatch

    Surfaces the underlying web3.Web3 instance as a public method.
    DeFiPy stays read-only by design; consumers needing to sign
    transactions (or do anything else outside the snapshot path) reach
    the substrate underneath via provider.get_w3() rather than monkey-
    patching internals or rebuilding their own ConnectW3.

    Lazy client caching: first get_w3() or .snapshot() call constructs
    the RpcClient via _rpc.make_client(); subsequent calls reuse it.
    Both paths share one connection per LiveProvider instance.

    Per Phase 3 addendum (STATE_TWIN_PHASE_3.md). Closes the substrate
    boundary discussion: get_w3() is the minimum useful escape hatch;
    transaction tooling beyond that is consumer-domain or sibling-
    library territory, not DeFiPy's job.
    ```

### What this addendum does NOT do

- **No transaction signing in DeFiPy.** The substrate exposes `web3.Web3`; consumers sign.
- **No connection pooling or reconnection logic.** One connection, lifetime of the LiveProvider instance.
- **No expansion of `MockProvider`.** Asymmetry between `LiveProvider.get_w3()` (real) and `MockProvider` (no chain) stays explicit.
- **No new dependencies.** Routes through the existing `_rpc.make_client()` path; same `[chain]` extra requirement.
- **No change to `_with_client()` test path.** Existing injection mechanism continues to work.

### Why this lands in Phase 3 (and not v2.2)

The `get_w3()` addition is small (≈25 lines + tests + docs) and structurally complete with the rest of the v2.1 surface — it closes the "how do I sign txs" question that LiveProvider's existence raises but doesn't answer. Shipping it in v2.1 means the v2.1 surface is whole: chain-reading via LiveProvider, optional signing via `get_w3()`, MCP tooling via `defipy.tools`, all read-only by design, all internally consistent.

Deferring it to v2.2 would have left a small but real gap — readers of the v2.1 docs would correctly ask "this is read-only, but what if I need to sign?" and the answer would be "wait for v2.2," which is a worse answer than "call `get_w3()` and bring your own infrastructure." Better to land it now and let v2.2 focus on the larger substrate work (Balancer/Stableswap LiveProvider, V3 tick walking, observability).

### Stopping point for this addendum

When `get_w3()` ships, the v2.1 substrate surface is feature-complete. What remains for the v2.1.0 tag is:

- The fork-and-evaluate demo (the original Phase 3 body above)
- Optional honest-disclosures cleanup (multi-format schemas error message, etc.)
- Operational PyPI push tasks (version bump, build, smoke tests, twine upload)

`get_w3()` doesn't gate any of those — they can land in any order. But it's the cleanest substrate-level addition to ship alongside the rest of the v2.1 work because it's the smallest and most principled of the open items.

---

## Addendum — `PoolHealth` ergonomics for V3

**Status:** Added during Phase 3 execution day. Surfaced when `LiveProvider` was first exercised against a real V3 pool (USDC/WETH 3000bps) in a notebook session — two attribute lookups failed, both on intuitively-named fields a notebook user would naturally reach for. A subsequent eyeball pass over other result dataclasses (`PositionAnalysis`, `PriceMoveScenario`, `SlippageAnalysis`, `RugSignalReport`, `TickRangeStatus`) found them clean — `PoolHealth` is the only result dataclass with the ergonomic gap.

**Goal:** Add three optional fields to `PoolHealth` so that the result dataclass is *complete* against a real V3 pool — fee tier, symmetric TVL, current tick. None of the missing data is unavailable; the substrate has it all on `lp`. The fix is making the dataclass surface what the substrate already knows.

The principle this enforces: result dataclasses should be complete against the *notebook user's first attempt to read them*, not just complete against the primitive author's design intent. Notebook users reach for symmetry (token0 fees → token1 fees → token0 TVL → token1 TVL); for V3 pools they reach for the metadata that distinguishes V3 from V2 (which fee tier? which tick?). PoolHealth was missing those.

### Scope — what's in

Three additive fields on `PoolHealth`:

- **`fee_pips: Optional[int]`** — V3 fee tier in pips (1/10000ths). `None` for V2 (always 30 bps; no per-pool variation). Populated from `lp.fee` when `lp.version == VERSION_V3`.
- **`tvl_in_token1: float`** — TVL expressed in token1 numeraire. Symmetric to existing `tvl_in_token0`. Computed as `reserve1 + reserve0 * spot_price` with the same zero-spot-price guard the existing field uses.
- **`tick_current: Optional[int]`** — V3 current tick from `lp.slot0.tick`. `None` for V2 (no tick concept). Useful for pool-level "where in price space am I?" inspection without requiring `CheckTickRangeStatus` (which needs lower/upper bounds).

`CheckPoolHealth.apply()` populates all three at construction time. No primitive contract changes. No new tests needed beyond confirming the new fields are populated correctly for V2 (None for `fee_pips` and `tick_current`, real value for `tvl_in_token1`) and V3 (real values across the board).

### Scope — what's out

- **No removal or rename of existing fields.** Strictly additive. `tvl_in_token0` stays. The existing primary-numeraire convention (token0 first) stays intact; `tvl_in_token1` is the symmetric companion.
- **No new fields beyond the three above.** `liquidity_active` (V3's `lp.liquidity` at the active tick) was considered and rejected — that's `AssessLiquidityDepth`'s territory, not pool-level health. Directional spot-price variants (`spot_price_token1_per_token0` vs. `spot_price_token0_per_token1`) were considered and rejected — `spot_price` is documented as `lp.get_price(token0)` and the inverse is one division away; adding both would double the field count without doubling the value.
- **No changes to other result dataclasses.** `PositionAnalysis`, `PriceMoveScenario`, `SlippageAnalysis`, `RugSignalReport`, `TickRangeStatus` were all reviewed; all are complete against their intended use case.
- **No changes to V2 behavior.** V2 pools continue to return `None` for `fee_pips` and `tick_current` (as is correct; V2 has no fee tier variation and no tick concept). V2 gets `tvl_in_token1` populated alongside `tvl_in_token0` since the math works for both versions.
- **No deprecation of `tvl_in_token0`.** Both fields ship; the user picks the numeraire they want.

### Deliverables

Files to modify:

```
python/prod/utils/data/PoolHealth.py            # MODIFY — add 3 fields
                                                # to dataclass + docstring
                                                # entries describing them

python/prod/primitives/pool_health/             # MODIFY — populate new
  CheckPoolHealth.py                              # fields at construction
                                                # site in apply()

python/test/primitives/pool_health/             # MODIFY — extend existing
  test_check_pool_health.py                       # tests to assert the
                                                # three new fields are
                                                # populated correctly for
                                                # V2 (None / real / None)
                                                # and V3 (real / real / real)

CHANGELOG.md                                    # MODIFY — add line under
                                                # v2.1 entry
```

No defipy-org docs changes required — the result dataclass docstrings carry their own reference documentation.

### Acceptance criteria

1. `CheckPoolHealth().apply(lp)` against a V3 LiveProvider-built twin returns a `PoolHealth` where `fee_pips` is the integer fee (e.g., `3000` for the canonical USDC/WETH 3000bps test pool), `tvl_in_token1` is a positive float (symmetric to `tvl_in_token0`), and `tick_current` is the integer tick from `lp.slot0.tick`.
2. The same call against a V2 twin returns `PoolHealth` where `fee_pips` is `None`, `tvl_in_token1` is a positive float (symmetric to `tvl_in_token0`), and `tick_current` is `None`.
3. `tvl_in_token1` honors the same zero-spot-price fallback as `tvl_in_token0`: when `spot_price` is zero or None, `tvl_in_token1` falls back to `reserve1` alone.
4. The existing `tvl_in_token0`, `total_fee0`, `total_fee1`, `num_swaps`, `num_lps`, `top_lp_share_pct`, and `has_activity` fields are unchanged in value — strictly additive change.
5. `RugSignalReport` (which embeds `PoolHealth`) gets the new fields transitively without code change. Verify by spot-checking one rug-signal test that the embedded `pool_health` carries the new attributes.
6. Existing test suite passes unchanged.

### Design decisions made up-front

#### D24 — Where the V3 fee tier lives

**Decision:** On `PoolHealth.fee_pips`, populated by `CheckPoolHealth`.

**Why:** Considered three options. (a) Put fee on `PoolHealth` because it's pool-level metadata. (b) Put fee on a separate `V3PoolMetadata` dataclass that `CheckPoolHealth` also returns or that callers query separately. (c) Document that callers should read `lp.fee` directly.

Option (a) wins because fee tier is *the* defining metadata of a V3 pool — the question "is this pool healthy?" is incomplete without naming which fee tier is being evaluated. Option (b) over-engineers a problem that a single `Optional[int]` field solves. Option (c) leaks substrate internals into the user's notebook code — the dataclass surface should be self-contained.

#### D25 — Naming: `fee_pips` vs. `fee_tier` vs. `fee`

**Decision:** `fee_pips`. Disambiguated against the V3 convention of expressing fees as integer pips (1/10000ths), matching what the V3 pool's `fee()` selector returns.

**Why:** `fee_tier` is human-friendly but ambiguous about units (basis points? percent? pips?). `fee` collides with `lp.fee`, which is the same value but lives at a different layer. `fee_pips` is precise about both presence (this is the V3 fee tier) and units (pips). Users who want bps divide by 10; users who want percent divide by 10000. Both are one-liners.

#### D26 — `tvl_in_token1` formula

**Decision:** `tvl_in_token1 = reserve1 + reserve0 * spot_price` where `spot_price = lp.get_price(token0)` (i.e., price of token0 in token1 units).

**Why:** Mirrors the existing `tvl_in_token0` formula via algebraic inversion. `reserve0 / spot_price` becomes `reserve0 * spot_price` because we're converting in the opposite direction. Same zero-spot-price fallback semantics — when the price is undefined, fall back to the same-side reserve and don't try to value the other side.

#### D27 — `tick_current` for V2

**Decision:** `None` for V2.

**Why:** V2 pools have no concept of ticks. Returning `0` would be a misleading signal (could be confused with "current tick is zero" when actually the field doesn't apply). Returning a sentinel like `-1` would impose a convention that doesn't match the V3 semantic. `None` is the honest answer: "this concept does not exist for this pool version."

#### D28 — Test infrastructure changes

**Decision:** Extend existing `test_check_pool_health.py` rather than add a new test file.

**Why:** The new fields are additive on the same primitive; the existing test fixture (V2 and V3 mock pools) already exists and exercises the right code paths. Adding three assertion lines per test is less infrastructure than a new file.

### Risks and gotchas to watch

#### R25 — Backward compatibility

Dataclass field additions in Python are backward-compatible if the new fields have defaults. Without defaults, existing code that constructs `PoolHealth` directly (test fixtures, custom callers) breaks. Mitigation: give the three new fields appropriate defaults (`fee_pips: Optional[int] = None`, `tvl_in_token1: float = 0.0`, `tick_current: Optional[int] = None`) so existing constructors continue to work. The `CheckPoolHealth.apply()` site populates them explicitly, so end-users see real values; only direct-construction callers (tests) get defaults.

#### R26 — `RugSignalReport` field-order dependencies

`RugSignalReport` embeds `PoolHealth`. If any test or caller constructs `RugSignalReport` with positional arguments, adding new fields to `PoolHealth` doesn't affect them — `PoolHealth` is passed in as a single object, not unpacked. Verify but expect this to be a no-op.

#### R27 — The eyeball-pass standard

Adding three fields to `PoolHealth` because a notebook user's first session surfaced them is the right move. But it raises the question: "what's the principle for *future* additions?" Answer for the docstring or follow-up notes: result dataclasses should expose the metadata a notebook user reaches for during normal exploration, not just the metadata required to answer the primitive's headline question. New fields ship in patch releases; field removal would be a major-version concern.

This principle is worth writing down in `V2_FOLLOWUPS.md` or a contributor-facing doc once one exists. For now the decision is captured here.

#### R28 — `tick_current` precision

`lp.slot0.tick` is an integer. The dataclass field is `Optional[int]`. No precision loss; no conversion needed. The `lp.slot0.sqrtPriceX96` value is *not* exposed — that's a layer of detail (raw Q64.96) that callers wanting price-precision work would reach for via `CheckTickRangeStatus` or `AssessLiquidityDepth`, not via `CheckPoolHealth`.

### Verification steps

In order:

1. Update `PoolHealth.py` with three new fields (with defaults per R25). Update docstring's `Attributes` section.
2. Update `CheckPoolHealth.apply()` to populate `fee_pips`, `tvl_in_token1`, and `tick_current` at the construction site.
3. Run existing `test_check_pool_health.py` — should pass unchanged (defaults handle any positional-arg test fixtures).
4. Extend tests: add assertions that V2 produces `(None, real, None)` for `(fee_pips, tvl_in_token1, tick_current)` and V3 produces `(real, real, real)`.
5. Run full test suite — all passing.
6. Spot-check `RugSignalReport` test: verify `report.pool_health.fee_pips` is accessible and has the right value when the underlying pool is V3.
7. Re-run the failing notebook session that surfaced the bug:

   ```python
   from defipy import CheckPoolHealth
   health = CheckPoolHealth().apply(lp)
   print(f"V3 fee:    {health.fee_pips} pips")
   print(f"TVL ratio: {health.tvl_in_token0 / health.tvl_in_token1:.2e}")
   print(f"Current tick: {health.tick_current}")
   ```

   Should run without errors and produce sensible output.
8. Update `CHANGELOG.md` v2.1 entry with one bullet for the addition.
9. Commit. Suggested message:

    ```
    feat(pool-health): expose V3 fee tier, symmetric TVL, current tick

    PoolHealth now reports fee_pips (V3 only), tvl_in_token1 (symmetric to
    tvl_in_token0), and tick_current (V3 only). Surfaced when LiveProvider
    was first exercised against a real V3 pool in a notebook — three
    fields that a user naturally reaches for were missing. All additive,
    no API breakage. RugSignalReport gets the new fields transitively
    via its embedded PoolHealth.

    Per Phase 3 addendum (STATE_TWIN_PHASE_3.md). Establishes the
    "result dataclasses should be complete against the notebook user's
    first attempt to read them" principle for future result dataclass
    work.
    ```

### Why this lands in Phase 3 (and not v2.1.1)

The ergonomic holes were surfaced *the first time the substrate was used against a real V3 pool in production-style notebook code*. That's exactly the moment to fix them — before v2.1.0 ships and a wider audience hits the same friction.

Deferring to v2.1.1 would mean v2.1.0 ships with the substrate-grade-feeling story partly contradicted by its own primary result dataclass. Better to land the fix now and ship a coherent v2.1.0.

The scope is small (~15 lines of substrate code, ~10 lines of test, no API breakage) and the work is mechanical — well-suited to Claude Code.

### Stopping point for this addendum

When the three fields land, the `PoolHealth` ergonomic gap is closed. What remains for v2.1.0 is unchanged from before this addendum:

- The fork-and-evaluate demo (the original Phase 3 body)
- Optional honest-disclosures cleanup (multi-format schemas error message)
- Operational PyPI push tasks (version bump, build, smoke tests, twine upload)

This addendum is a substrate-completeness fix, same shape and same urgency as the `get_w3()` addendum above. Both ship together in workstream 3a; the demo is workstream 3b.
