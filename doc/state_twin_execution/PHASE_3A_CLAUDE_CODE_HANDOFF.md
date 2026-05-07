# Claude Code Handoff — DeFiPy v2.1 Phase 3a (Substrate Completeness)

**Status as of handoff:** Phase 1 + Phase 2 shipped clean. V2 + V3 LiveProvider verified against real mainnet pools. PoolSnapshot enrichment landed. Test baseline ~677. Phase 3a scope settled in `STATE_TWIN_PHASE_3.md` via two addenda. No code written yet.

**Branch:** `main` after Phase 2 merge. Create `feat/v2.1-substrate-completeness` off `main` before any further work.

**Version target after Phase 3a:** `2.1.0a3` (still alpha — Phase 3b ships the demo, then 2.1.0 final tags + PyPI push).

---

## Read these first, in this order

1. `doc/state_twin_execution/STATE_TWIN_PHASE_3.md` — **authoritative.** Two addenda at the bottom of the file: `## Addendum — Surface LiveProvider.get_w3()` and `## Addendum — PoolHealth ergonomics for V3`. Both addenda settle design decisions D20-D28 and risks R21-R28.
2. `doc/state_twin_execution/STATE_TWIN_COMPLETION_PLAN.md` — umbrella plan
3. `doc/state_twin_execution/PHASE_2_CLAUDE_CODE_HANDOFF.md` — predecessor handoff doc, useful as a style template
4. `doc/state_twin_execution/STATE_TWIN_PHASE_2_EXPANDED.md` — Phase 2's design context, reference for `RpcClient` shape and `_fake_rpc.py` patterns

The two addenda in `STATE_TWIN_PHASE_3.md` are the spec for this phase. The body of `STATE_TWIN_PHASE_3.md` (above the addenda) is Phase 3b scope (fork-and-evaluate demo) — **not part of this handoff.** Phase 3b is a separate handoff after Phase 3a lands.

---

## What Phase 3a ships

Two small substrate-completeness fixes that earned their place during Phase 2's first real-world LiveProvider session against USDC/WETH V3 mainnet:

**1. `LiveProvider.get_w3()`** — public method exposing the underlying `web3.Web3` instance for callers who need to sign transactions, run direct contract calls outside the snapshot path, or wire LiveProvider into broader chain tooling. DeFiPy stays read-only by design; `get_w3()` is the substrate boundary that lets consumers reach the layer underneath. Lazy client caching: first call to `get_w3()` or `.snapshot()` constructs the `RpcClient`; subsequent calls reuse it. Both paths share one connection per `LiveProvider` instance.

**2. `PoolHealth` ergonomics for V3** — three additive fields surfaced when the dataclass was first read in a notebook session:
- `fee_pips: Optional[int]` — V3 fee tier in pips (None for V2; from `lp.fee`)
- `tvl_in_token1: float` — symmetric to existing `tvl_in_token0`
- `tick_current: Optional[int]` — V3 current tick (None for V2; from `lp.slot0.tick`)

All three populated by `CheckPoolHealth.apply()` at construction. Strictly additive; no API breakage. `RugSignalReport` (which embeds `PoolHealth`) gets the new fields transitively without code change.

Both fixes are mechanical. Combined scope: ~40 lines of substrate code + ~25 lines of tests + four small docs/changelog updates.

---

## Locked-in decisions (do NOT relitigate without flagging)

These came out of the addenda and are now load-bearing on the implementation:

### `get_w3()` decisions (D-series, 20-23)

- **D20: Cache scope.** Cache the `RpcClient` (not just the `web3.Web3`) on the `LiveProvider` instance. First `get_w3()` or `.snapshot()` call constructs it via `make_client()`; both methods reuse it thereafter. The "stateless across calls" property in the existing docstring needs updating to specify *snapshots are stateless* while *the connection is reused*.
- **D21: Method name `get_w3()`.** Mirrors `RpcClient.get_w3()` exactly. Not `web3` (collides with package), not `client` (exposes too much), not `get_web3_client()` (verbose).
- **D22: Method, not property.** First call has side effects (opens HTTP connection); methods make the cost visible at the call site.
- **D23: No change to import-time behavior.** `from defipy.twin import LiveProvider` continues to work without `[chain]` installed; only calling `get_w3()` (or `.snapshot()`) triggers the lazy import.

### `PoolHealth` decisions (D-series, 24-28)

- **D24: Fee tier lives on `PoolHealth`.** Not on a separate `V3PoolMetadata` dataclass; not "callers read `lp.fee` directly." Fee tier is *the* defining metadata of a V3 pool — pool-level health is incomplete without it.
- **D25: Naming `fee_pips`.** Disambiguated against the V3 convention of expressing fees as integer pips (1/10000ths). `fee_tier` is ambiguous on units; `fee` collides with `lp.fee`.
- **D26: `tvl_in_token1` formula.** `reserve1 + reserve0 * spot_price` where `spot_price = lp.get_price(token0)`. Same zero-spot-price fallback as `tvl_in_token0`.
- **D27: `tick_current = None` for V2.** V2 has no tick concept; `None` is the honest answer (not `0`, not `-1`).
- **D28: Extend existing `test_check_pool_health.py`.** Don't add a new test file. Three assertion lines per existing V2/V3 test is less infrastructure than a new file.

### Risks (R-series, 21-28)

**`get_w3()`:**
- **R21:** Cached `RpcClient` lives for life of LiveProvider instance. Long-running processes may see connection go stale. Document in docstring; don't fix.
- **R22:** Test mock coverage uses existing `FakeRpcClient` from `_fake_rpc.py`. The fake already exposes `get_w3()` for the snapshot path; the new test just verifies passthrough.
- **R23:** Documentation framing pressure on defipy-org page — lead with *why* (signing is opinion-shaped), then *how* (snippet), then *what's-not-here* (DeFiPy doesn't sign).
- **R24:** Future demand for transaction tooling — keep saying no. Sibling library, not absorption.

**`PoolHealth`:**
- **R25: Backward compatibility.** Three new dataclass fields need defaults so existing direct-construction callers (test fixtures) continue to work. `fee_pips: Optional[int] = None`, `tvl_in_token1: float = 0.0`, `tick_current: Optional[int] = None`.
- **R26: `RugSignalReport` field-order.** `RugSignalReport` embeds `PoolHealth` as a single object, not unpacked. Adding fields to `PoolHealth` shouldn't affect any `RugSignalReport` construction. Verify but expect no-op.
- **R27: Eyeball-pass standard.** Already done — `PositionAnalysis`, `PriceMoveScenario`, `SlippageAnalysis`, `RugSignalReport`, `TickRangeStatus` all reviewed; `PoolHealth` is the only result dataclass with the gap. No more fields to add.
- **R28: `tick_current` precision.** `lp.slot0.tick` is an integer; field is `Optional[int]`. No conversion needed. `sqrtPriceX96` deliberately *not* exposed (that's `CheckTickRangeStatus` / `AssessLiquidityDepth` territory).

---

## File inventory

### Production code

| File | Status | Purpose |
|---|---|---|
| `python/prod/twin/live_provider.py` | MODIFY | Add `get_w3()` method per D20-D22. Refactor existing `_get_client()` / `_injected_client` field to support both injected fakes and cached production `RpcClient`. Update class docstring to reflect connection-reuse-but-stateless-snapshots property. |
| `python/prod/utils/data/PoolHealth.py` | MODIFY | Add three new fields with defaults per R25: `fee_pips: Optional[int] = None`, `tvl_in_token1: float = 0.0`, `tick_current: Optional[int] = None`. Update docstring's `Attributes` section to describe each. |
| `python/prod/primitives/pool_health/CheckPoolHealth.py` | MODIFY | Populate the three new fields in `apply()` at the `PoolHealth(...)` construction site. Use `lp.version == UniswapExchangeData.VERSION_V3` discriminator (same pattern as existing fee-handling code in this file). |

### Test code

| File | Status | Purpose |
|---|---|---|
| `python/test/twin/test_live_provider_v2.py` (or new `test_live_provider_get_w3.py`) | NEW tests added | Three new tests: (a) repeated `get_w3()` returns same instance (caching), (b) `.snapshot()` after `get_w3()` reuses cached client (no new `make_client()`), (c) injected-client passthrough: `LiveProvider._with_client(fake).get_w3() is fake.get_w3()`. |
| `python/test/primitives/pool_health/test_check_pool_health.py` | MODIFY | Extend existing V2 and V3 tests with assertions for the three new fields. V2: `(None, real, None)`. V3: `(real, real, real)`. ~3 assertion lines per test. |

### Config / docs

| File | Status | Purpose |
|---|---|---|
| `setup.py` | MODIFY | Version bump `2.1.0a2` → `2.1.0a3` |
| `CHANGELOG.md` | MODIFY | Add 2.1.0a3 entry with both fixes (template below) |
| `README.md` | MODIFY | Add bullet to v2.1 "What's new" section for `get_w3()` (the `PoolHealth` fix is too internal for README billing — CHANGELOG entry suffices) |

### defipy-org docs

| File | Status | Purpose |
|---|---|---|
| `src/content/docs/live-provider.mdx` | MODIFY | Add `## Signing transactions: bring your own` section (~150 words, one code example). Frame per R23: lead with *why*, then *how*, then *what's-not-here*. |

---

## Execution order

The order matters; some changes are smaller and safer to land first. Follow this sequence:

### 1. Branch + baseline check

```bash
cd ~/repos/defipy
git checkout main
git pull origin main   # confirm Phase 2 is in
git checkout -b feat/v2.1-substrate-completeness
pytest python/test -q | tail -3   # confirm ~677 baseline
```

### 2. PoolHealth field additions (smallest blast radius)

Edit `python/prod/utils/data/PoolHealth.py`:
- Add three new dataclass fields with defaults per R25.
- Update the `Attributes` section of the docstring to describe each field, including the V2-vs-V3 semantic differences.

Edit `python/prod/primitives/pool_health/CheckPoolHealth.py`:
- Locate the `PoolHealth(...)` construction site at the bottom of `apply()`.
- Compute `tvl_in_token1` alongside `tvl_in_token0` using the same zero-spot-price guard (per D26).
- Compute `fee_pips = lp.fee if lp.version == UniswapExchangeData.VERSION_V3 else None`.
- Compute `tick_current = lp.slot0.tick if lp.version == UniswapExchangeData.VERSION_V3 else None`.
- Pass all three to the `PoolHealth(...)` constructor.

Run existing tests:

```bash
pytest python/test/primitives/pool_health/test_check_pool_health.py -v
```

Should pass unchanged because the new fields have defaults.

Then extend the tests per D28 — add three assertion lines to each existing V2 test (assert `fee_pips is None`, `tvl_in_token1 > 0`, `tick_current is None`) and three to each V3 test (`fee_pips == 3000` for the canonical V3 fixture, `tvl_in_token1 > 0`, `tick_current == <expected>`).

```bash
pytest python/test/primitives/pool_health/test_check_pool_health.py -v
```

All passing including new assertions.

### 3. RugSignalReport spot-check

Per R26: verify that `RugSignalReport` tests still pass without modification, since `PoolHealth` is passed as a whole object. Run:

```bash
pytest python/test/primitives/pool_health/test_detect_rug_signals.py -v
```

If anything fails, the failure is structural (positional construction of `PoolHealth` somewhere) — back off and fix the construction site to use keyword args.

### 4. `get_w3()` implementation

Edit `python/prod/twin/live_provider.py`:

- Inspect the current `_injected_client` / `_get_client()` pattern. The current code (per Phase 2's V3 path) constructs an `RpcClient` per `.snapshot()` call. We need to change this to lazy-cache on first use.

- Refactor: replace `_injected_client` with `_cached_client = None`. Refactor `_get_client()` to:
  - Return the cached client if set.
  - Otherwise call `make_client(self._rpc_url)`, cache the result, and return it.
  - The injected-client test path (`_with_client(fake)`) continues to work because `_with_client` sets `_cached_client = fake` directly.

- Add the public method:

  ```python
  def get_w3(self):
      """ get_w3
      
          Returns the underlying web3.Web3 instance for callers who need
          to sign transactions, run direct contract calls outside the
          snapshot path, or wire LiveProvider into their own broader
          chain tooling.
          
          DeFiPy is read-only by design; LiveProvider does not sign or
          send transactions. Consumers needing to act on-chain pull the
          web3 instance via this method and bring their own signing
          infrastructure (private key management, hardware wallet,
          MPC vault, signing service — DeFiPy stays out of that
          opinion).
          
          Lazy construction. The underlying RpcClient is constructed on
          first call to get_w3() or .snapshot() (whichever comes first)
          and cached for the life of the LiveProvider instance. Both
          methods share one connection. For long-running processes that
          may see the connection go stale, construct a fresh
          LiveProvider periodically or build your own
          connection-management layer around get_w3().
          
          Returns
          -------
          web3.Web3
              The underlying web3 instance, ready for direct use.
          
          Raises
          ------
          ImportError
              If [chain] extra is not installed; surfaced from
              _rpc.make_client() with the install instructions.
      """
      return self._get_client().get_w3()
  ```

- Update the class docstring per D20's implication note. The existing "stateless across calls" sentence should specify that *snapshots are stateless* (no caching of pool state, block data, or snapshot results) while *the connection is reused*.

### 5. `get_w3()` tests

Add tests to `python/test/twin/test_live_provider_v2.py` (or a new file `test_live_provider_get_w3.py` if you prefer separation):

```python
def test_get_w3_returns_web3_instance():
    """get_w3 surfaces the underlying web3.Web3 instance."""
    fake = build_fake_client(...)  # existing helper
    provider = LiveProvider("http://fake-rpc")._with_client(fake)
    w3 = provider.get_w3()
    assert w3 is fake.get_w3()  # passthrough


def test_get_w3_caches_client():
    """Repeated get_w3() calls return the same web3 instance."""
    fake = build_fake_client(...)
    provider = LiveProvider("http://fake-rpc")._with_client(fake)
    w3_first = provider.get_w3()
    w3_second = provider.get_w3()
    assert w3_first is w3_second


def test_snapshot_after_get_w3_reuses_cached_client():
    """Calling .snapshot() after get_w3() does not trigger a new client construction."""
    fake = build_fake_client(...)
    provider = LiveProvider("http://fake-rpc")._with_client(fake)
    _ = provider.get_w3()
    # Now snapshot — should use the same fake client, not construct a new one.
    snap = provider.snapshot("uniswap_v2:0x...")
    assert snap is not None
    # Verify the fake's call log shows the snapshot reads against the SAME client instance.
```

Run:

```bash
pytest python/test/twin/test_live_provider_v2.py -v
```

All passing including the three new tests.

### 6. Full suite check

```bash
pytest python/test -q | tail -5
```

Expected: ~683 passed (~677 baseline + 6 new: 3 PoolHealth assertions added × 2 versions + 3 get_w3 tests). Confirm clean. No regressions, no new skips.

### 7. defipy-org docs

Switch to defipy-org repo:

```bash
cd ~/repos/defipy-org
git status   # confirm clean working tree
git checkout -b docs/v2.1-substrate-completeness   # or use existing docs branch
```

Edit `src/content/docs/live-provider.mdx`. Add a new section (likely between the existing "Block pinning" section and the V3 tick range section, or at the end before the "What's coming v2.2" section — pick the spot that flows best when you read the page top-to-bottom):

```markdown
## Signing transactions: bring your own

LiveProvider is read-only by design. The substrate exposes pool state
via typed snapshots; it does not sign or send transactions. Signing
infrastructure varies enormously across users — local key, hardware
wallet, MPC vault, signing service, hosted custodial flow — and
embedding any opinion would be wrong for most. DeFiPy stays out of
the keys-and-execution layer because that's where security and policy
opinions diverge most.

For consumers who need to act on-chain after analysis, the underlying
`web3.Web3` instance is available via `provider.get_w3()`:

```python
from defipy.twin import LiveProvider

provider = LiveProvider("https://eth-mainnet.example.com/v2/<key>")
w3 = provider.get_w3()

# Bring your own signing infrastructure.
account = w3.eth.account.from_key("0x...")  # or a hardware wallet, etc.
tx = my_contract.functions.someAction().build_transaction({...})
signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
```

The `web3.Web3` instance is shared with the snapshot path — both
`provider.get_w3()` and `provider.snapshot(...)` use the same
connection, lazily constructed on first use and reused for the life
of the `LiveProvider` instance. For long-running processes that may
see the connection go stale, construct a fresh `LiveProvider`
periodically.

What's not here, by design: no `provider.sign()`, no
`provider.send_transaction()`, no transaction-builder pattern, no
key management, no gas estimation helpers. The substrate exposes
the underlying web3 instance and stops. Transaction tooling beyond
`get_w3()` is the consumer's domain or sibling-library territory,
not DeFiPy's.
```

Run the production build to verify:

```bash
npm run build
```

If the build is clean, the page renders.

### 8. README + CHANGELOG (defipy repo)

Switch back to defipy:

```bash
cd ~/repos/defipy
```

Edit `README.md` — find the v2.1 "What's new" section. Add one bullet for `get_w3()`:

```markdown
* **`provider.get_w3()`** — the underlying `web3.Web3` instance is now public, for callers who want to sign transactions or wire LiveProvider into their own broader chain tooling. DeFiPy stays read-only by design; bring your own signing opinion.
```

Edit `CHANGELOG.md` — add a new 2.1.0a3 entry above the 2.1.0a2 entry:

```markdown
## [2.1.0a3] — 2026-MM-DD (UNRELEASED)

Third alpha of the v2.1 "State Twin Completion" cycle. Phase 3a ships
two substrate-completeness fixes surfaced when LiveProvider was first
exercised against real V3 mainnet pools.

### Added

- **`LiveProvider.get_w3()`** — public method returning the underlying
  `web3.Web3` instance. DeFiPy stays read-only by design; consumers
  needing to sign transactions reach the substrate underneath via this
  method rather than monkey-patching internals or rebuilding their own
  `ConnectW3`. Lazy client caching: first `get_w3()` or `.snapshot()`
  call constructs the `RpcClient`; both methods share one connection
  per `LiveProvider` instance for the rest of its lifetime.
- **`PoolHealth` ergonomics for V3** — three additive fields:
  - `fee_pips: Optional[int]` — V3 fee tier in pips (None for V2).
  - `tvl_in_token1: float` — symmetric to existing `tvl_in_token0`.
  - `tick_current: Optional[int]` — V3 current tick (None for V2).
  All populated by `CheckPoolHealth.apply()`. Strictly additive; no
  API breakage. `RugSignalReport` (which embeds `PoolHealth`) gets
  the new fields transitively without code change.

### Changed

- **`LiveProvider` connection lifecycle** — connection is now cached
  on the instance from first use through GC, rather than
  reconstructed per snapshot. Snapshots themselves remain stateless
  (no caching of pool state or block data); the connection reuse is
  a pure efficiency win for callers making multiple snapshots from
  one provider.

### Notes

- `get_w3()` is the substrate boundary for execution. Transaction
  tooling beyond it (signing helpers, gas estimation, transaction
  builders) is consumer-domain or sibling-library territory, not
  DeFiPy's. The substrate stays small.
- "Result dataclasses should be complete against the notebook user's
  first attempt to read them" — the principle the PoolHealth fix
  establishes for future result dataclass design.
```

### 9. Version bump

Edit `setup.py`:

```python
version='2.1.0a3',
```

Update the in-comment header to reflect Phase 3a.

### 10. Final verification

```bash
pytest python/test -q | tail -3   # ~683 passed
```

Confirm no regressions. If any V2 or V3 test from earlier phases failed, back off the relevant change.

### 11. Commit + push

Suggested commit message for the defipy repo:

```
feat(twin): substrate completeness for v2.1 (Phase 3a)

Two fixes surfaced when LiveProvider was first exercised against real
V3 mainnet pools in a notebook session:

1. LiveProvider.get_w3() — public method exposing the underlying
   web3.Web3 instance. DeFiPy stays read-only by design; consumers
   needing to sign transactions reach the substrate underneath via
   this method. Lazy caching: first get_w3() or .snapshot() constructs
   the RpcClient; both methods share one connection per LiveProvider
   instance.

2. PoolHealth ergonomics — three additive fields populated by
   CheckPoolHealth.apply(): fee_pips (V3 fee tier, None for V2),
   tvl_in_token1 (symmetric to tvl_in_token0), tick_current (V3 tick,
   None for V2). RugSignalReport gets the new fields transitively.

Strictly additive. No API breakage. ~40 lines of substrate code,
~25 lines of tests.

Per Phase 3 addenda (STATE_TWIN_PHASE_3.md). Establishes the
"result dataclasses should be complete against the notebook user's
first attempt to read them" principle for future result dataclass
work.

Version bump to 2.1.0a3. v2.1.0 final tag follows after Phase 3b
(fork-and-evaluate demo) lands.

Refs: doc/state_twin_execution/STATE_TWIN_PHASE_3.md
```

```bash
git add -A
git commit -m "<above>"
git push -u origin feat/v2.1-substrate-completeness
```

For defipy-org:

```bash
cd ~/repos/defipy-org
git add -A
git commit -m "docs: add 'Signing transactions: bring your own' section to LiveProvider page"
git push -u origin docs/v2.1-substrate-completeness
```

---

## Likely fragile points

I (the prior Claude session writing this handoff) wrote this without running any of the new code. These are the spots most likely to need a fix during execution:

### LiveProvider's existing `_injected_client` / `_get_client()` shape

The current Phase 2 implementation has some pattern for injecting a fake client during tests (the `_with_client` test helper). The exact shape may be:

- A `_injected_client` field that's checked in `_get_client()`.
- A direct `_client` attribute that gets swapped in.
- A factory function that returns either the production client or the injected fake.

The refactor needs to:
1. Locate the existing pattern (read the file first).
2. Replace the "construct per snapshot" behavior with "construct once, cache" behavior.
3. Preserve the test injection path.

The cleanest version is probably: a `_cached_client = None` attribute, a `_get_client()` method that returns it if set or constructs+caches+returns otherwise, and `_with_client(fake)` sets `_cached_client = fake` directly. But verify against what's actually in the file before assuming.

### `lp.version` discriminator string

The existing `CheckPoolHealth.apply()` already uses `lp.version == UniswapExchangeData.VERSION_V3` for fee handling. Match that exact pattern for the new field population — don't import `UniswapExchangeData` differently or compare to a string literal. Consistency with the existing code is the goal.

### `RugSignalReport` test surface

R26 says this should be a no-op, but verify. Specifically: search for any place that constructs `PoolHealth` with positional args (vs. kwargs). If any test fixture does `PoolHealth(version, token0_name, token1_name, ...)` positionally, adding new fields with defaults is *technically* fine because they're at the end of the dataclass, but only if they remain at the end. Make sure the three new fields go *after* all existing fields in the dataclass declaration order.

### web3 < 7.0 pin still applies

`get_w3()` returns whatever `web3.Web3` instance `make_client()` constructed. That's still pinned to web3 6.x via the `[chain]` extra. Don't add web3 7-specific features in the new method or its docstring; the substrate's web3 contract is still 6.x until v2.2.

### defipy-org production build strictness

Vite dev mode tolerates some MDX issues that the production build rejects. Run `npm run build` after the docs edit before committing — the build will catch malformed code blocks, broken links, and frontmatter issues that `npm run dev` won't.

### Version bump consistency

Three places mention the version: `setup.py`, `CHANGELOG.md`, and the in-file comment in `setup.py`. Make sure all three say `2.1.0a3` after the bump. The CHANGELOG entry in particular is what shows up on PyPI when 2.1.0 ships, so it should be accurate.

---

## Verification gate (Phase 3a ships when all of these pass)

In order:

1. **Existing tests still pass.** `pytest python/test -q | tail -3` — no regressions.
2. **PoolHealth field tests pass.** `pytest python/test/primitives/pool_health/test_check_pool_health.py -v` — V2 returns `(None, real, None)`, V3 returns `(real, real, real)` for the three new fields.
3. **RugSignalReport tests still pass.** `pytest python/test/primitives/pool_health/test_detect_rug_signals.py -v` — no modifications needed.
4. **`get_w3()` tests pass.** Three new tests (caching, snapshot-reuses-cache, injected-passthrough) — all green.
5. **Full suite passes.** `pytest python/test -q | tail -3` — expected ~683 passed.
6. **Live RPC verification.** Re-run the failing notebook session that surfaced the bugs:

   ```python
   from defipy.twin import LiveProvider, StateTwinBuilder
   from defipy import CheckPoolHealth

   provider = LiveProvider("https://mainnet.infura.io/v3/<key>")
   snap = provider.snapshot("uniswap_v3:0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")
   lp = StateTwinBuilder().build(snap)
   health = CheckPoolHealth().apply(lp)

   print(f"V3 fee:    {health.fee_pips} pips")     # 3000
   print(f"TVL ratio: {health.tvl_in_token0 / health.tvl_in_token1:.2e}")
   print(f"Current tick: {health.tick_current}")    # some integer

   # And the get_w3 path:
   w3 = provider.get_w3()
   print(f"Chain ID: {w3.eth.chain_id}")            # 1 (mainnet)
   ```

   All four print lines produce sensible output without errors.
7. **Version bumped:** `setup.py` shows `2.1.0a3`.
8. **README updated** with `get_w3()` bullet in v2.1 What's new section.
9. **CHANGELOG.md updated** with 2.1.0a3 entry.
10. **defipy-org docs page updated** — `live-provider.mdx` has the new "Signing transactions: bring your own" section, `npm run build` is clean.
11. **Commit + push to `feat/v2.1-substrate-completeness`** (defipy) and `docs/v2.1-substrate-completeness` or equivalent (defipy-org).

---

## Items deferred from Phase 3a

Do NOT pick these up opportunistically:

- **Fork-and-evaluate demo** — Phase 3b. Separate handoff coming after Phase 3a lands.
- **Multi-format schemas** — `get_schemas("anthropic")` / `get_schemas("openai")` error message says "deferred to v2.1" which is now stale; either implement the wrappers or fix the error message to say "v2.2." Tracked separately; not part of this handoff.
- **`with_custom_abi()` kwarg on `.snapshot()`** — discussed during the substrate-completeness conversations but explicitly deferred. Demand-driven; v2.2+ work if a real consumer needs V2/V3 ABI variants.
- **`get_w3()` on MockProvider** — asymmetry between `LiveProvider` (chain-backed) and `MockProvider` (synthetic) is honest. Don't add unless consumer demand surfaces.
- **Liquidity / sqrt price / additional V3 metadata on PoolHealth** — `liquidity_active`, directional spot-price variants, `sqrtPriceX96` exposure all considered and rejected per the addendum. Don't add unless new consumer demand surfaces them.
- **PyPI release** — batches at end of Phase 3b per the chat-decided release strategy. 2.1.0a3 is git-tag-only (and even the tag waits for Phase 3b).
- **Sphinx docs (`live-provider.md`, `snapshot.md`)** — defipy-org is the canonical docs surface now. Do NOT write these.

---

## When Phase 3a lands cleanly

Come back to the chat interface for the Phase 3b EXPANDED brief before any demo code is written. Phase 3b is the fork-and-evaluate demo per `STATE_TWIN_PHASE_3.md` body (above the addenda).

Hand off to Phase 3b with:
- Phase 3a commit hash on `main` (after merge)
- Test count baseline post-merge (should be ~683)
- Clean working tree on both defipy and defipy-org
- Live RPC verification confirmed working with new `get_w3()` and `PoolHealth` fields

Phase 3b scope per `STATE_TWIN_PHASE_3.md` body: fork-and-evaluate demo + defipy-org docs page + final 2.1.0 tag and PyPI push. Estimated 1-2 days of focused work.

The substrate is now feature-complete for v2.1. What remains is the worked example that proves the substrate's promise, then the operational push to PyPI.
