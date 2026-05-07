# Claude Code Handoff — DeFiPy v2.1 Phase 3b (Fork-and-Evaluate Demo)

**Status as of handoff:** Phase 1 + Phase 2 + Phase 3a all shipped. Substrate is feature-complete for v2.1: V2+V3 LiveProvider, PoolSnapshot enrichment, `get_w3()` escape hatch, `PoolHealth` ergonomics for V3. Test baseline 686. Phase 3b scope settled in `STATE_TWIN_PHASE_3.md` body (above the addenda). No demo code written yet.

**Branch:** `main` after Phase 3a merge (commit `bd139d9`). Create `feat/v2.1-fork-evaluate-demo` off `main` before any further work.

**Version target after Phase 3b:** `2.1.0` (final). The PyPI push itself is **NOT** part of this handoff — it batches the morning after Phase 3b lands. This handoff stops at "demo shipped, docs page live, version bumped, ready for tomorrow's PyPI push."

---

## Read these first, in this order

1. `doc/state_twin_execution/STATE_TWIN_PHASE_3.md` — **authoritative for Phase 3b.** The body of the file (above the two addenda) is Phase 3b scope. Decisions D13–D19 settled there; risks R14–R20 flagged. The addenda below are Phase 3a (already shipped); ignore them for execution but reference them for context on `get_w3()` and `PoolHealth` shape since the demo uses both.
2. `doc/state_twin_execution/STATE_TWIN_COMPLETION_PLAN.md` — umbrella plan
3. `doc/state_twin_execution/PHASE_3A_CLAUDE_CODE_HANDOFF.md` — predecessor handoff doc, useful as a style template
4. `doc/state_twin_execution/STATE_TWIN_PHASE_2_EXPANDED.md` — Phase 2's design context, reference for V3 LiveProvider semantics that the demo consumes

The Phase 3 brief body overrides earlier framing on every point it covers. If something in the body disagrees with an addendum, the body wins for Phase 3b purposes (the addenda are about already-shipped substrate; the body is about the demo that uses it).

---

## What Phase 3b ships

**A self-contained Python demo script** (`python/examples/state_twin_fork_evaluate.py`) that demonstrates the State Twin's strategic claim with code: pull live state once, fork the twin into N independent copies under different price scenarios, run primitives against each fork, aggregate into an interpretable distribution, produce a recommendation.

**A defipy-org docs page** (`/fork-evaluate/`) that explains the pattern, embeds key code excerpts from the demo, and serves as the canonical reference a reader can follow to apply fork-and-evaluate to their own pool.

**README + CHANGELOG updates** mentioning the demo as the headline v2.1 worked example.

**Version bump** `2.1.0a3` → `2.1.0` (final). Tag `v2.1.0` locally. **PyPI push is the user's separate task tomorrow morning** — Phase 3b stops at the local tag.

The demo is a script, not a notebook (D14 locked). The demo runs against USDC/WETH V3 3000bps mainnet by default (D18), with an `--offline` flag that switches to MockProvider for CI/no-RPC environments (D19).

---

## Locked-in decisions (do NOT relitigate without flagging)

These came out of the Phase 3 brief and are now load-bearing on the implementation:

### Demo design (D13–D19)

- **D13: Scenario shape.** Hand-specified scenarios are the demo body — `[-30%, -20%, -10%, 0%, +10%, +20%, +30%]` or similar at N=20-50. They're easier to interpret in output and easier to debug than sampled scenarios. A short comment in the script points to where a consumer would swap in log-normal sampling for rigor; don't ship two variants.

- **D14: Script only.** **Locked.** `python/examples/state_twin_fork_evaluate.py` is the canonical and only demo artifact. NO notebook variant. The defipy-org docs page embeds code excerpts from the script rather than rendering a notebook.

- **D15: Forking mechanism — try `copy.deepcopy(lp)` first.** The exchange object is what primitives operate on; the snapshot is just data. If `copy.deepcopy(lp)` produces clean independent forks, no new utility ships. If it surfaces issues (shared factory references, recursive references, performance pain at N=50), then add a targeted `PoolSnapshot.clone()` method that rebuilds via `StateTwinBuilder` and verify clone-then-build is fast enough. **Don't preemptively build the helper — only if `deepcopy` fails the simplicity test.**

- **D16: Aggregation = mean + 5th/95th percentile + median.** Plus `value_change_pct` and `il_percentage` as the readable axes. Risk-adjusted metrics (Sharpe-like, utility functions) are explicitly out — the demo's job is to show the distribution is *reachable*, not to prescribe scoring.

- **D17: 70% threshold.** **Locked.** If ≥ 70% of price scenarios produce IL worse than -5% (`il_percentage < -0.05`), recommendation is `"rebalance"`; otherwise `"hold"`. The script prints the threshold and the count of breaching scenarios so the recommendation is transparent ("42 of 50 scenarios show IL worse than -5% → rebalance"). A comment in the script names where consumers plug in their own threshold.

- **D18: Pool = USDC/WETH V3 3000bps mainnet** (`0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`). Same pool as Phase 2's smoke test and Phase 3a's verification. Large liquidity, well-known pair, V3 with active range positioning. The demo's narrative is more compelling against a pool readers actually know.

- **D19: Offline mode + LiveProvider canonical.** Demo body runs LiveProvider against the canonical pool. `--offline` flag switches to MockProvider's `eth_dai_v3` recipe so the demo runs without network access (CI, no-RPC environments, doc-build environments). LiveProvider is the canonical narrative; offline is the fallback.

### Risks (R14–R20)

- **R14: `deepcopy` performance.** At N=50, profile early. If slow, fall back to `PoolSnapshot.clone() → StateTwinBuilder.build()` per fork. Don't optimize prematurely; measure once, decide.

- **R15: Primitive mutation of `lp`.** The contract is "stateless / non-mutating," but verify before assuming. If `AnalyzePosition.apply(lp, ...)` mutates `lp` even slightly, fork contamination will surface. Fix if it appears: deepcopy the lp inside the demo before each primitive call, not just once at fork time. Note as a caveat in the docs page if it surfaces.

- **R16: Scenario realism.** `[-30%, -10%, +10%, +30%]` is easy to interpret but unrealistic for short horizons. Mitigation: frame the scenarios as "rebalance-decision-relevant moves" rather than "expected market moves" in the docs and the script comments. Add an explicit "this is illustrative; calibrate to your own assumptions" line in the docs.

- **R17: Output verbosity.** N=50 scenario dump is unreadable. Bias toward summarized output (3-line summary + recommendation) with optional `--verbose` mode for the full per-scenario breakdown. The summary is the default; verbose is opt-in.

- **R18: Demo as scope-creep bait.** "While we're at it, multi-pool variant / Click CLI / rebalance simulation" — all out of scope. The demo's job is the existence proof for the multi-scenario pattern. Anything that feels like a great addition goes in `V2_FOLLOWUPS.md`, not the demo.

- **R19: RPC cost during iteration.** Use `--offline` MockProvider during script iteration; reserve LiveProvider for end-to-end verification. Saves Alchemy/Infura free-tier credits and works in environments without RPC access.

- **R20: Notebook-vs-script divergence.** Resolved by D14 — script only, no notebook ships. R20 stops being an active risk.

---

## File inventory

### Production code

| File | Status | Purpose |
|---|---|---|
| `python/examples/state_twin_fork_evaluate.py` | NEW | The demo script. ~150-250 lines including imports, scenario definition, fork loop, aggregation, summary output, and `--offline` / `--verbose` argparse handling. |
| `python/prod/twin/snapshot.py` | MODIFY (conditional) | Add `PoolSnapshot.clone()` method **only if** `copy.deepcopy(lp)` fails the simplicity test per D15/R14. Default expectation: not needed. |

### Test code

| File | Status | Purpose |
|---|---|---|
| `python/test/twin/test_snapshot_clone.py` | NEW (conditional) | Tests for `PoolSnapshot.clone()` semantics if the helper was added. Default: no test file needed. |

### Config / docs (defipy repo)

| File | Status | Purpose |
|---|---|---|
| `setup.py` | MODIFY | Version bump `2.1.0a3` → `2.1.0` (final). Update in-comment header to reflect Phase 3b completion + v2.1.0 release framing. |
| `CHANGELOG.md` | MODIFY | Collapse the `2.1.0a1`, `2.1.0a2`, `2.1.0a3` entries into a single `2.1.0` entry (template below). Move the alpha-series entries to a brief "Pre-release alphas" footnote or delete; the published v2.1.0 changelog should read as one coherent release, not three. |
| `README.md` | MODIFY | Add bullet to "What's new in v2.1" section mentioning the fork-and-evaluate demo with link to `https://defipy.org/fork-evaluate/`. |

### Defipy-org docs

| File | Status | Purpose |
|---|---|---|
| `src/content/docs/fork-evaluate.mdx` | NEW | Page walking through the fork-and-evaluate pattern. Code excerpts from the demo script, prose explaining what the pattern is and why it's interesting, pointer to `python/examples/state_twin_fork_evaluate.py` as the runnable artifact. ~400-600 words. |
| `astro.config.mjs` | MODIFY | Add `fork-evaluate` entry under the existing State Twin sub-group in the sidebar IA. The sub-group currently contains: Concept, LiveProvider. Add fork-evaluate as the third entry. |
| `src/content/docs/index.mdx` | MODIFY (small) | Add a one-line pointer to `/fork-evaluate/` as the canonical v2.1 worked example. Likely best placed near the existing v2.1 framing section. |
| `src/content/docs/twin-concept.mdx` | OPTIONAL | Closing-section pointer to `/fork-evaluate/` as "this is what fork-and-evaluate looks like in practice." Skip if it doesn't read naturally; the home-page pointer alone is enough. |

---

## Execution order

The order matters because some changes are easier to validate in isolation. Follow this sequence:

### 1. Branch + baseline check

```bash
cd ~/repos/defipy
git checkout main
git pull origin main   # confirm Phase 3a is in (commit bd139d9)
git checkout -b feat/v2.1-fork-evaluate-demo
pytest python/test -q | tail -3   # confirm 686 baseline
pip show defipy | grep -i location   # confirm editable install — should
                                     # point at ~/repos/defipy/python/prod
                                     # NOT site-packages. If it points at
                                     # site-packages, run pip install -e '.[chain]'
                                     # to fix. (See "Likely fragile points"
                                     # below — this gotcha bit Phase 3a.)
```

### 2. Demo script — offline path first

Build the demo in three passes. First pass: make it work against MockProvider only.

Create `python/examples/state_twin_fork_evaluate.py` with:

- Imports: `LiveProvider`, `MockProvider`, `StateTwinBuilder`, `AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth`. Standard library: `argparse`, `copy`, `os`, `statistics`, `time`.
- Module docstring naming the State Twin Completion Plan and the goal: "demonstrate the multi-scenario simulation pattern against the V2.1 substrate."
- `argparse` for `--offline` (default: False, uses LiveProvider) and `--verbose` (default: False, summary output only) and `--n-scenarios` (default: 50). Optional `--block-number` for historical-block reproducibility.
- A `SCENARIOS` constant — hand-specified price multipliers (e.g., `[0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30]` for the 7-scenario base set; expand to N=50 by interpolating or by using a denser grid, document the expansion in a comment).
- Helper functions:
  - `build_initial_twin(offline: bool, block_number: int | None) -> lp` — runs LiveProvider or MockProvider, builds the twin, returns the `lp` exchange object.
  - `fork_twin(lp, n: int) -> list[lp]` — uses `copy.deepcopy` per D15. Comment notes that R14 fallback (`PoolSnapshot.clone() + StateTwinBuilder.build()`) lives here if performance demands it.
  - `evaluate_scenarios(lp_forks, scenarios, scoring_kwargs) -> list[result]` — runs `AnalyzePosition` and `SimulatePriceMove` against each fork at the corresponding scenario price, returns the per-fork analysis dataclass.
  - `aggregate(results) -> dict` — per D16, computes mean / 5th / 95th / median of `il_percentage` and `value_change_pct` across the scenario set. Returns a small dict the summary printer consumes.
  - `recommend(results, threshold_breach_pct=0.70, il_threshold=-0.05) -> tuple[str, dict]` — per D17, counts how many scenarios have `il_percentage < il_threshold`, compares against `threshold_breach_pct`, returns `("rebalance" | "hold", {breach_count, total, ratio, threshold})`.
  - `print_summary(aggregate_dict, recommendation, breach_info, threshold_pct, n_scenarios, verbose)` — formats the output. R17 — bias toward 3-line summary; opt-in verbose.
- `main()` orchestrating all of the above with timing instrumentation that R14 wants (print fork+evaluate wall-clock time for the verification gate).

Run it offline first to verify the structural code:

```bash
python python/examples/state_twin_fork_evaluate.py --offline --n-scenarios 20 --verbose
```

If it runs without errors and the output is interpretable, the structure is right. Iterate on output formatting until it reads cleanly per R17.

### 3. Demo script — live path

With `--offline` removed, switch to LiveProvider against the canonical pool. Requires `DEFIPY_LIVE_RPC` env var or hardcoded `RPC_URL` constant in the script (use `os.environ.get("DEFIPY_LIVE_RPC")` with an informative error message if absent).

```bash
DEFIPY_LIVE_RPC=https://eth-mainnet.example.com/v2/<key> \
  python python/examples/state_twin_fork_evaluate.py --n-scenarios 50
```

Verify:
- Wall-clock time (excluding initial chain read) under ~10 seconds per V3 above. If significantly slower, profile per R14.
- Forks are independent: scenarios with different prices produce different `il_percentage` values. (Add a sanity check inside the demo per acceptance criterion 2.)
- The recommendation matches expectations — for USDC/WETH V3 3000bps full-range, most ±10% to ±30% scenarios should produce moderate IL; the recommendation will likely be `"hold"` at the 70% threshold unless the scenario set is asymmetric. If the recommendation is consistently `"rebalance"` for all-symmetric scenarios, the IL math may be off — investigate before committing.

If `copy.deepcopy(lp)` is slow or surfaces shared-reference issues at N=50, fall back to D15's clone path: add `PoolSnapshot.clone()` to `python/prod/twin/snapshot.py`, plus tests, plus update the `fork_twin` helper to use it. Note the path taken in the commit message.

### 4. defipy-org docs page

Switch to defipy-org repo:

```bash
cd ~/repos/defipy-org
git status   # confirm clean working tree (or use existing docs branch)
git checkout -b docs/v2.1-fork-evaluate
```

Create `src/content/docs/fork-evaluate.mdx`. Suggested structure (~500 words):

- **Frontmatter:** `title: "Fork and evaluate"`, `description: "Pull live state once. Fork N ways. Run primitives. Decide."`
- **Lede paragraph:** what the fork-and-evaluate pattern is, in two sentences. Frame it as the canonical demonstration of the State Twin's strategic claim — multi-scenario reasoning against real chain state, in memory, before any execution.
- **Why this is interesting** (~100 words): contrast with reactive-only DeFi tools; name the property that makes it possible (LiveProvider gives you the chain state in a typed dataclass; `copy.deepcopy(lp)` gives you N independent forks; primitives are deterministic against any twin).
- **The demo** (~150 words): point at `python/examples/state_twin_fork_evaluate.py` as the runnable artifact. Show the canonical invocation:
  ```bash
  pip install defipy[chain]
  DEFIPY_LIVE_RPC=https://... python state_twin_fork_evaluate.py
  ```
  Embed a small code excerpt (~10 lines) showing the fork loop + primitive call pattern.
- **What the output looks like** (~100 words): show a sample summary block (3-line recommendation output + the threshold framing per R17). Make it look like real output, not pseudocode.
- **Adapting it to your pool** (~100 words): point at the helper functions in the script (`build_initial_twin`, `fork_twin`, `evaluate_scenarios`, `aggregate`, `recommend`) and note where consumers plug in their own pool ID, scenario set, scoring threshold, or analysis primitive. Frame the recommendation logic as "illustrative — calibrate to your own thresholds" per D17.
- **Caveat block** at the end (~50 words): hand-specified scenarios are illustrative, not predictive (R16); the substrate provides the distribution, the scoring is the consumer's opinion.

Update `astro.config.mjs` — add `fork-evaluate` entry to the State Twin sub-group:

```js
{
  label: 'State Twin',
  collapsed: true,
  items: [
    { label: 'Concept', slug: 'twin-concept' },
    { label: 'LiveProvider', slug: 'live-provider' },
    { label: 'Fork and evaluate', slug: 'fork-evaluate' },  // NEW
  ],
},
```

(Adjust slug capitalization to match the existing pattern — `fork-evaluate` matches `live-provider`.)

Update `src/content/docs/index.mdx` — add a one-line pointer near the v2.1 framing. Likely something like:

> **New in v2.1:** the [fork-and-evaluate worked example](/fork-evaluate/) demonstrates the State Twin pattern against live mainnet state.

Optionally add a closing pointer to `twin-concept.mdx` if it reads naturally; skip if it feels forced.

Run the production build to verify:

```bash
npm run build
```

Build must be clean. If it's not, fix any MDX issues (broken links, frontmatter problems, missing slugs) before committing.

### 5. Test suite verification

Switch back to defipy:

```bash
cd ~/repos/defipy
pytest python/test -q | tail -3
```

If `PoolSnapshot.clone()` was added (D15 fallback path), the test count should be 686 + N (where N is the number of clone tests added). If the deepcopy path worked without modification, count stays at 686.

If anything regressed, debug before continuing. The Phase 3b demo is read-only against the substrate — it shouldn't break existing tests. If something broke, the cause is likely in the optional clone helper, not in the demo itself.

### 6. README + CHANGELOG (defipy repo)

Edit `README.md` — find the v2.1 "What's new" section. Add:

```markdown
* **Fork-and-evaluate worked example** — `python/examples/state_twin_fork_evaluate.py` demonstrates the State Twin's multi-scenario reasoning pattern against live mainnet state. Pull a V3 pool snapshot once, fork the twin N ways under price scenarios, run primitives against each fork, aggregate into a recommendation. Walks through the pattern at [defipy.org/fork-evaluate/](https://defipy.org/fork-evaluate/).
```

Edit `CHANGELOG.md` — collapse the `2.1.0a1`, `2.1.0a2`, `2.1.0a3` alpha entries into a single `2.1.0` entry. Suggested template:

```markdown
## [2.1.0] — 2026-MM-DD

The "State Twin Completion" cycle. v2.1 makes the State Twin substrate
real — chain reads compose with every primitive in the library, the
same way `MockProvider` recipes do. The "what would happen if?" loop
is now local: pull state once, simulate forever, decide before
executing.

### Added

- **V2 LiveProvider** — `provider.snapshot("uniswap_v2:0xADDR")` builds
  a `V2PoolSnapshot` from real on-chain state. Block-pinned reads,
  decimal-adjusted reserves, ERC20 metadata via web3scout's
  `FetchToken`. (Phase 1.)
- **V3 LiveProvider** — `provider.snapshot("uniswap_v3:0xADDR")` builds
  a `V3PoolSnapshot` with reserves, ticks, fee, tickSpacing populated
  from on-chain reads via Multicall3 (single round trip for token0,
  token1, slot0, liquidity, fee, tickSpacing, block timestamp).
  Active-liquidity only — tick bitmap walking deferred to v2.2 or
  pairing with `AssessLiquidityDepth`. (Phase 2.)
- **Multicall3 batching** for V3 reads. Hardcoded canonical Multicall3
  address (`0xcA11bde05977b3631167028862bE2a173976CA11`) — same on
  every major EVM chain.
- **PoolSnapshot enrichment** — `block_number`, `timestamp`, `chain_id`
  fields on the base `PoolSnapshot` class. Optional, default `None`.
  LiveProvider populates from chain reads; MockProvider snapshots
  stay `None` to honestly signal "synthetic, not chain state."
- **`LiveProvider.get_w3()`** — public method exposing the underlying
  `web3.Web3` instance. DeFiPy stays read-only by design; consumers
  needing to sign transactions reach the substrate underneath via
  `get_w3()` rather than monkey-patching internals or rebuilding their
  own ConnectW3. Lazy client caching: first `get_w3()` or `.snapshot()`
  call constructs the `RpcClient`; both methods share one connection
  per `LiveProvider` instance. (Phase 3a.)
- **`PoolHealth` ergonomics for V3** — three additive fields populated
  by `CheckPoolHealth.apply()`: `fee_pips` (V3 fee tier in pips, `None`
  for V2), `tvl_in_token1` (symmetric to existing `tvl_in_token0`),
  `tick_current` (V3 current tick from `lp.slot0.tick`, `None` for V2).
  `RugSignalReport` gets the new fields transitively via its embedded
  `PoolHealth`. (Phase 3a.)
- **`[chain]` install extra** — `pip install defipy[chain]` adds
  `web3scout` and `web3.py` for users who want LiveProvider. Core
  install (no extras) remains free of any chain or LLM dependencies.
- **`[agentic]` install extra** — composes `[chain]` and `[mcp]` for
  the canonical "Python SDK for Agentic DeFi" install.
- **Fork-and-evaluate worked example** — `python/examples/state_twin_fork_evaluate.py`
  demonstrates the State Twin's multi-scenario reasoning pattern. Pulls
  a V3 pool snapshot once, forks the twin N ways under price scenarios,
  runs primitives against each fork, aggregates into a recommendation.
  Walks through the pattern at [defipy.org/fork-evaluate/](https://defipy.org/fork-evaluate/).
  (Phase 3b.)

### Changed

- **`LiveProvider` connection lifecycle** — connection cached on the
  instance from first use through GC, rather than reconstructed per
  snapshot. Snapshots themselves remain stateless (no caching of pool
  state or block data); the connection reuse is a pure efficiency win
  for callers making multiple snapshots from one provider.

### Notes

- v2.1 is a strict superset of v2.0 — every v2.0 primitive,
  `MockProvider` recipe, and MCP server pattern works identically.
- Tick bitmap walking deferred to v2.2. Active-liquidity primitives
  (`AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth`,
  `CalculateSlippage`, `DetectRugSignals`) work against V3 LiveProvider
  twins.
- Balancer / Stableswap LiveProvider deferred to v2.2.
- `[chain]` extra pins `web3 < 7.0` due to `web3scout 0.2.0`'s reliance
  on `eth_utils.abi.get_abi_input_types` (web3 6 only). Tracking
  upstream as v2.2 work.
- "Result dataclasses should be complete against the notebook user's
  first attempt to read them" — the principle the `PoolHealth`
  ergonomics fix establishes for future result dataclass design.
```

Decide on the pre-release alpha entries. Two reasonable approaches:

- **Delete them.** The published v2.1.0 changelog reads as one coherent release. Cleanest.
- **Keep as a footnote.** "Pre-release alphas: 2.1.0a1, 2.1.0a2, 2.1.0a3 shipped during the State Twin Completion cycle for internal testing; superseded by 2.1.0 final."

Recommend deletion. The published changelog is what users see on PyPI; the alpha tags exist in git history for anyone who needs them.

### 7. Version bump

Edit `setup.py`:

```python
version='2.1.0',
```

Update the in-comment header — replace the alpha-series framing with a v2.1.0-shipped framing. Something like:

```python
# 2.1.0: State Twin Completion cycle complete. V2+V3 LiveProvider,
# Multicall3 batching, PoolSnapshot enrichment, get_w3() escape hatch,
# PoolHealth ergonomics for V3, fork-and-evaluate worked example.
# Phases 1-3 of STATE_TWIN_COMPLETION_PLAN.md all shipped. Substrate
# is feature-complete for v2.1; v2.2 work is demand-driven.
```

### 8. Final verification

```bash
pytest python/test -q | tail -3   # 686 (or 686 + clone tests if D15 fallback)

# Run the demo offline:
python python/examples/state_twin_fork_evaluate.py --offline --n-scenarios 20

# Run the demo against live RPC:
DEFIPY_LIVE_RPC=https://... python python/examples/state_twin_fork_evaluate.py --n-scenarios 50
```

Both demo runs should complete without errors and produce interpretable output.

### 9. Commit + tag (defipy repo)

Suggested commit message:

```
feat(examples): fork-and-evaluate demo + v2.1.0 release (Phase 3b)

Demonstrates the State Twin pattern's multi-scenario decision-making
claim with a worked example. Builds a twin via LiveProvider against
USDC/WETH V3 3000bps mainnet, forks the twin N=50 ways under hand-
specified price scenarios, runs AnalyzePosition + SimulatePriceMove
against each fork, aggregates into a distribution, applies a 70%
threshold rule for hold-vs-rebalance recommendation.

- python/examples/state_twin_fork_evaluate.py: canonical demo script
  (script only per D14; notebook deferred)
- --offline flag for MockProvider fallback (CI, no-RPC environments,
  doc-build environments)
- 70% threshold + IL < -5% rule for the recommendation per D17 —
  illustrative not prescriptive; consumers calibrate their own
- Wall clock: <10s for N=50 scenarios on a typical laptop, excluding
  initial chain-read time (D14 / R14)
- copy.deepcopy(lp) used for forking per D15; PoolSnapshot.clone()
  not added (deepcopy was sufficient).  [OR: PoolSnapshot.clone()
  added per D15 fallback after deepcopy surfaced X.]

defipy-org docs page added at /fork-evaluate/, sidebar IA updated
with State Twin sub-group entry, home page pointer updated.

Version bump 2.1.0a3 -> 2.1.0 (final). CHANGELOG collapsed from
three alpha entries into one coherent v2.1.0 entry.

This is NOT an agent. It's a Python script demonstrating the substrate
pattern. DeFiMind / LLM orchestration remain explicitly out of scope
per STATE_TWIN_COMPLETION_PLAN.md.

With this commit, State Twin Completion is functionally complete.
v2.1.0 tagged locally. PyPI push is the next-day operational task —
NOT performed by this commit.

Refs: doc/state_twin_execution/STATE_TWIN_PHASE_3.md
```

```bash
git add -A
git commit -m "<above>"
git tag v2.1.0
git push -u origin feat/v2.1-fork-evaluate-demo
git push origin v2.1.0   # push the tag too
```

### 10. Commit + push (defipy-org repo)

```bash
cd ~/repos/defipy-org
git add -A
git commit -m "docs: add fork-evaluate page + sidebar IA entry (v2.1.0)"
git push -u origin docs/v2.1-fork-evaluate
```

---

## Likely fragile points

I (the prior Claude session writing this handoff) wrote the brief without running any of the demo code. These are the spots most likely to need a fix during execution:

### Editable install degradation

This bit Phase 3a — the editable install of `defipy` had silently degraded to a static copy at `/opt/homebrew/lib/python3.11/site-packages/defipy/`, and the symptom was an `AttributeError` on a method that existed in the source. **Pre-flight check:** run `pip show defipy | grep -i location` before touching code; should point at `~/repos/defipy/python/prod`, not site-packages. If wrong, run `pip install -e '.[chain]'` to re-establish the editable install.

### `copy.deepcopy(lp)` and shared factory references

The `UniswapV3Exchange` object holds a reference to a `factory` object that contains the token registry. `deepcopy` will recursively copy the factory and all its tokens, which might:

- Break if the factory has circular references that exceed deepcopy's recursion limit
- Be slow at N=50 because each fork copies the entire factory + token graph
- Produce forks that have *separate* token instances, which means primitive calls like `lp.factory.token_from_exchange[lp.name][lp.token0]` will return different objects per fork, but that's actually fine — primitives only care about the math, not object identity

The honest test is: deepcopy one fork, run a primitive on it, check the result is a sensible number, deepcopy a different fork with a different price, run the same primitive, check the result is *different* in the expected direction. If both work, deepcopy is fine. If you see contamination (same result across different scenarios), that's R15 (primitive mutation), not R14 (deepcopy).

### Primitive mutation of `lp` (R15)

`AnalyzePosition` and `SimulatePriceMove` are documented as non-mutating. Verify by running the same primitive twice on the same `lp` and checking that the second result equals the first. If they differ, the primitive is mutating internal state and the demo needs to deepcopy `lp` *per primitive call*, not just per fork.

The most likely mutator is `SimulatePriceMove` — its job is to "project" a position state at a hypothetical price, which might involve temporarily setting state on the lp. If this surfaces, the workaround is to deepcopy inside the scenario loop. Note in the docs page if so.

### `--offline` mode pool selection

The Phase 3 brief mentions MockProvider's `eth_dai_v3` recipe as the offline fallback. Verify this recipe exists and is V3-shaped — if MockProvider only ships `eth_dai_v2`, the offline path needs to use that or a different V3 recipe. If neither V3 recipe exists, file the gap and use V2 for the offline path. Note in the script comment which recipe is in use and why.

### Scenario set construction at N=50

Hand-specified scenarios at N=7 is `[-30, -20, -10, 0, +10, +20, +30]`. Expanding to N=50 needs a scheme — uniform interpolation over `[-30%, +30%]` gives `np.linspace(-0.30, 0.30, 50)` (or pure Python `[i/50 * 0.6 - 0.3 for i in range(50)]`). The scheme matters less than that it's transparent in the script — comment what it is and why.

### V3 reserve-at-scenario calculation

`SimulatePriceMove` takes a price-move ratio and computes the position state at the new price. For V3, this involves moving the active tick. Verify the primitive handles this correctly — a position currently at tick T with a scenario of -30% price means the new price is 0.7 * current, which means a new tick. If the position's tick range is full-range (default), the position remains in-range and the math is straightforward. If you set a custom narrower range, the position may go out-of-range at extreme scenarios, which is itself an interesting demo finding but worth flagging in the output rather than failing silently.

### Live RPC test stability

USDC/WETH V3 3000bps `slot0` and `liquidity` change every block. The demo's output will vary slightly run-to-run because it pulls a fresh snapshot each invocation. That's fine — note in the docs page that "exact numbers will differ from what you see here; the *shape* of the distribution is the artifact, not the specific percentages."

### CHANGELOG collapse pre-flight

Before you collapse the alpha entries, save them somewhere — paste them into a temporary scratch file or copy the relevant text. If anyone needs to look up "what changed in 2.1.0a2 specifically?", the answer should be reproducible from git history (`git show v2.1.0a2-tag` if a tag exists, or commit-archaeology). If neither tag exists in the repo's actual history, the alpha entries become the only record, and deleting them loses information. Worth checking `git tag -l 'v2.1.0a*'` before deletion — if no alpha tags exist, lean toward keeping the alpha entries as a "Pre-release alphas" footnote rather than deleting them.

### defipy-org production build strictness

Vite dev mode tolerates MDX issues that production rejects. Always run `npm run build` before committing — the build catches malformed code blocks, broken links, and frontmatter issues that `npm run dev` won't.

---

## Verification gate (Phase 3b ships when all of these pass)

In order:

1. **Existing tests still pass.** `pytest python/test -q | tail -3` — 686 (or 686 + clone tests if D15 fallback was needed).
2. **Demo runs offline.** `python python/examples/state_twin_fork_evaluate.py --offline --n-scenarios 20` — no errors, output is interpretable.
3. **Demo runs live.** `DEFIPY_LIVE_RPC=https://... python python/examples/state_twin_fork_evaluate.py --n-scenarios 50` — no errors, output is interpretable.
4. **Fork independence verified.** The in-script sanity check confirms scenarios with different inputs produce different outputs (acceptance criterion 2).
5. **Wall-clock budget met.** N=50 fork-and-evaluate completes in <10 seconds excluding initial chain read.
6. **Recommendation logic transparent.** Output names the threshold (70%), the count of breaching scenarios, and the resulting recommendation.
7. **Verbose mode works.** `--verbose` flag produces the full per-scenario breakdown without breaking the summary path.
8. **defipy-org docs page renders.** `npm run build` is clean; the page is accessible at `/fork-evaluate/`; sidebar IA shows the new entry.
9. **README updated** with the v2.1 "What's new" bullet for fork-evaluate.
10. **CHANGELOG collapsed** to a single v2.1.0 entry.
11. **Version bumped** to `2.1.0` final in `setup.py`.
12. **Commit + tag.** `feat/v2.1-fork-evaluate-demo` branch pushed; `v2.1.0` tag created and pushed; defipy-org docs branch pushed.

---

## Items deferred from Phase 3b

Do NOT pick these up opportunistically:

- **PyPI push.** Explicitly NOT part of this handoff. Phase 3b stops at the local `v2.1.0` tag; the user runs `python -m build` + `twine upload` + GitHub release notes the morning after Phase 3b lands. Doing this in the same session as the demo work risks shipping a regression you wouldn't catch without fresh-morning attention.
- **Multi-format schemas error message.** `get_schemas("anthropic")` and `get_schemas("openai")` say "deferred to v2.1" which is now stale. Either implement the wrappers or update the message to "v2.2." Tracked separately as a 2.1.x patch; not blocking v2.1.0.
- **Notebook variant of the demo.** D14-locked. Script only.
- **`PoolSnapshot.clone()` if not needed.** D15 — only add if `copy.deepcopy(lp)` fails the simplicity test. Don't preemptively build it.
- **Multi-pool / multi-protocol fork-evaluate.** Single pool, N forks. Cross-protocol is v2.2+ if anyone asks.
- **Fork-evaluate as a `defipy.twin` library primitive.** Stays in the demo file. Promote only on consumer pull.
- **Click-based CLI / argparse expansion / config-file support.** R18 — scope creep. The demo's argparse surface is `--offline`, `--verbose`, `--n-scenarios`, optionally `--block-number`. Stop there.
- **Plotting beyond minimal matplotlib output.** Text summary is the default. A simple histogram is fine if it adds value but optional.
- **Sphinx docs (`doc/source/...`).** Defipy-org is the canonical docs surface. Do NOT write any `doc/source/` files.
- **`THIRD_PARTY_LICENSES.md`.** Tracked separately as institutional-positioning polish; not blocking v2.1.0.
- **State Twin paper drafting.** Calendar-paced separate work, not part of Phase 3b.
- **Any agent / LLM / DeFiMind work.** Strictly out of scope. The demo is `python script.py`, not "ask Claude a question."

---

## When Phase 3b lands cleanly

Come back to the chat interface for the **PyPI Push Checklist** before any distribution work. The PyPI push is the user's separate task tomorrow morning; Phase 3b's job ends at the local `v2.1.0` tag.

Hand off to the PyPI push with:

- Commit hash on `main` (after PR merge) for v2.1.0
- Test count baseline post-merge (686 or 686 + clone tests)
- Local `v2.1.0` tag created and pushed
- Defipy-org `fork-evaluate` page live on production (after Vercel auto-deploy from main)
- Demo runs verified end-to-end against mainnet
- Clean working tree on both repos

The PyPI push will need:

- `python -m build` clean on a fresh checkout
- `pip install dist/defipy-2.1.0-*.whl` smoke test in a fresh venv
- `pip install dist/defipy-2.1.0-*.whl[chain]` smoke test running the README's quick example against real RPC
- `pip install dist/defipy-2.1.0-*.whl[agentic]` smoke test confirming the new persona extra installs cleanly
- `twine upload dist/*` to PyPI
- GitHub release notes (use the v2.1.0 CHANGELOG entry verbatim or tightened)

After the PyPI push, State Twin Completion is fully done — substrate shipped, demo shipped, on PyPI under a version users can pin to. The next milestone is DeFiMind v1, which depends on v2.1.0 being available on PyPI as a stable substrate.
