# State Twin Phase 3 — Fork-and-Evaluate Demo

**Status:** Forward-looking brief, work not yet started
**Umbrella plan:** `STATE_TWIN_COMPLETION_PLAN.md`
**Predecessor:** Phase 2 (`STATE_TWIN_PHASE_2.md`) — V2+V3 LiveProvider shipped, `PoolSnapshot` enriched, test infrastructure generalized
**Estimated dedicated time:** ~1-2 weeks
**Acceptance gate:** Self-contained Python script (or notebook) builds a twin via LiveProvider against a real V3 pool, forks it N ways under price scenarios, runs primitives against each fork, and produces an interpretable scenario distribution with a recommended path. Demo lives in `python/examples/` and is referenced from ReadTheDocs as a worked example.

---

## Goal

Demonstrate the State Twin promise's *strategic* claim — *"the agent chews through dozens of analytical scenarios on the fly in memory, offchain, before landing on an execution path... no one is doing this"* — with an existence proof that runs in code.

Phase 3 is not an agent. It's not DeFiMind. It's a worked example of the multi-scenario simulation pattern, demonstrated against substrate that's now real (V2+V3 LiveProvider from phases 1-2). The demo is what makes the State Twin paper writable and what makes the Odos/Veda pitches lean on a demonstrated artifact rather than an architectural claim.

The acceptance criterion is "the script runs and produces an interpretable result," not "an LLM does this end-to-end." Strictly OSS substrate composition.

---

## Scope — what's in

- A self-contained demo script — `python/examples/state_twin_fork_evaluate.py` — or an equivalent Jupyter notebook in `doc/notebooks/state_twin_fork_evaluate.ipynb`
- The demo:
  1. Builds a twin via `LiveProvider` against a real V3 pool at a recent block (USDC/WETH 3000bps recommended — same pool used in phase 2's smoke test)
  2. Forks the twin into N copies (N = 20-50, configurable) under different price scenarios — uniform spread, log-normal sample, or hand-specified scenarios
  3. Runs one or more primitives against each fork (recommended: `AnalyzePosition` + `SimulatePriceMove` for position context, optionally `CheckPoolHealth` for health context)
  4. Aggregates results into a scenario distribution — expected value, percentile bounds, dispersion
  5. Produces a recommendation — e.g., "stay in current range" / "rebalance to range X" / "exit position" — with a confidence/score basis
  6. Outputs a clean human-readable summary (text or simple plot)
- Whatever small library utilities surface naturally during demo work — most likely `PoolSnapshot.clone()` or a fork helper, possibly nothing if Python's `copy.deepcopy` handles snapshots cleanly
- ReadTheDocs page in `doc/source/state-twin/fork-evaluate.md` (or adjacent) walking through the pattern with code excerpts from the demo
- A short paragraph in the main ReadTheDocs landing page pointing to the demo as the canonical State Twin worked example
- README update mentioning the demo and how to run it

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

Files to create or modify:

```
python/examples/state_twin_fork_evaluate.py    # NEW — the demo script
                                                # (alternatively: a notebook
                                                # at doc/notebooks/...)

python/prod/twin/snapshot.py                   # MODIFY (likely) — add
                                                # PoolSnapshot.clone() or
                                                # equivalent fork helper IF
                                                # demo work surfaces a clean
                                                # need; else leave alone

python/test/twin/test_snapshot_clone.py        # NEW (conditional on the
                                                # above) — tests for clone
                                                # semantics if a clone helper
                                                # is added

doc/source/state-twin/fork-evaluate.md         # NEW — ReadTheDocs page
                                                # walking through the
                                                # fork-and-evaluate pattern

doc/source/index.md                            # MODIFY — landing-page
                                                # pointer to the demo

README.md                                       # MODIFY — short mention
                                                # of the demo in the
                                                # "What's new in v2.1" or
                                                # "Examples" section

CHANGELOG.md                                    # MODIFY — v2.1 entry
                                                # mentioning fork-evaluate
                                                # demo
```

The demo file format (script vs. notebook) is a decision point — see D14.

---

## Acceptance criteria

Phase 3 ships when all of these pass:

1. **Demo runs end-to-end.** With a working RPC endpoint, `python python/examples/state_twin_fork_evaluate.py` (or the notebook equivalent) runs to completion without errors against the live USDC/WETH V3 pool.

2. **Forks are independent.** N twin forks running primitives in sequence produce independent results — no cross-fork contamination. Asserted by an in-script sanity check (e.g., scenario A's IL ≠ scenario B's IL when scenarios A and B differ).

3. **Output is interpretable.** A reader unfamiliar with the demo can run it, look at the output, and understand: (a) what scenarios were evaluated, (b) what the distribution of outcomes looks like, (c) what the recommended path is, (d) why that path was recommended.

4. **The "no one is doing this" claim has a worked example.** The demo demonstrably runs N scenarios in memory against an offchain twin built from real chain state, with single-digit-second wall-clock time on a typical laptop. This is what makes the multi-scenario claim defensible.

5. **Demo is referenced from docs.** The fork-and-evaluate pattern has a dedicated ReadTheDocs page; the main docs landing page links to it; the README mentions it as a v2.1 example.

6. **No new substrate dependencies.** The demo uses LiveProvider, MockProvider (optionally for offline mode), the existing primitives, and standard library tools. No new top-level dependencies in `install_requires`. If matplotlib is used for output, it's optional and the demo runs without it (text fallback).

7. **Existing test suite unaffected.** All v2.0 + phase 1 + phase 2 tests still pass. Any new tests (e.g., for `PoolSnapshot.clone()` if added) pass.

8. **Docs page captures the pattern, not just the demo.** The fork-and-evaluate ReadTheDocs page explains what the pattern is, why it's useful, and points to the demo as the existence proof. A reader who wants to apply the pattern to their own pool / their own scenarios can follow the page without reading the demo line-by-line.

---

## Design decisions to make up-front

### D13 — Scenario shape

**Options:** Hand-specified scenarios (e.g., `[-30%, -20%, -10%, 0%, +10%, +20%, +30%]`) | Uniformly sampled price moves over a range | Log-normal samples (statistically more realistic for crypto returns) | All of the above

**Recommendation:** Start with **hand-specified scenarios** for the demo body — they're easier to interpret in the output and easier to debug. Add a "sampled" variant as a secondary code path or a notebook cell, with a comment explaining when each is appropriate. Hand-specified scenarios make the demo legible; sampled scenarios make it rigorous. Both serve the "worked example" purpose.

### D14 — Script vs. notebook format

**Options:** Pure Python script in `python/examples/` | Jupyter notebook in `doc/notebooks/` | Both

**Recommendation:** **Script primary, notebook secondary if time permits.** A `.py` file in `python/examples/` is unambiguously runnable, easy to test in CI later, and doesn't require notebook infrastructure to render. If a notebook adds value (e.g., for the docs page), build it second from the script as a thin wrapper. Don't ship two divergent versions; the script is canonical.

### D15 — Forking mechanism

**Options:** `copy.deepcopy()` on the snapshot | `copy.deepcopy()` on the built `lp` exchange object | Add a `PoolSnapshot.clone()` method | Add a `defipy.twin.fork(snapshot, n)` helper

**Recommendation:** **Try `copy.deepcopy()` on the built `lp` first.** The exchange objects are the things primitives mutate (or operate on); the snapshot is just data. If `copy.deepcopy(lp)` produces clean independent forks, no new utility is needed. If it has issues — e.g., shared references to factory objects, recursive references, performance pain at N=50 — then add a targeted `PoolSnapshot.clone()` method that rebuilds via `StateTwinBuilder` and verify clone-then-build is fast enough at scale.

The right answer is the simpler one. Don't preemptively build a fork helper — build it only if `copy.deepcopy` fails the simplicity test.

### D16 — Aggregation / scoring approach

**Options:** Simple mean and percentile bounds | Risk-adjusted metrics (Sharpe-like) | Decision-theoretic (utility function over outcomes) | Something else

**Recommendation:** **Simple mean + 5th/95th percentile + median for the demo body.** Plus an explicit "value-change %" or "IL %" axis so the distribution is interpretable in the units the primitives produce. Risk-adjusted metrics are a layer the consumer adds; the demo's job is to show that the *distribution* is reachable, not to prescribe how to score it.

A short comment in the demo pointing to where a consumer would plug in their own scoring function is more useful than building one in.

### D17 — Recommendation logic

**Question:** What does "recommended path" mean given that the demo runs N price scenarios on a single position?

**Recommendation:** **Recommend "hold" vs. "rebalance" based on whether the active range covers ≥ X% of scenarios in the IL-positive zone.** Or simpler: report the IL distribution and let the demo's narrative be "if 80% of scenarios show IL > 5%, consider rebalancing." The recommendation is illustrative, not prescriptive — consumers calibrate to their own thresholds.

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
6. Read the ReadTheDocs page draft. A reader unfamiliar with the work understands: what fork-and-evaluate is, why it's interesting, where the demo lives, how to adapt it to their own use case.
7. Verify README and main docs landing page link to the demo and the pattern page.
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
