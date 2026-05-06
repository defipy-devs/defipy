# Claude Code Handoff — DeFiPy v2.1 Phase 2 (V3 + Multicall + Schema Enrichment)

**Status as of handoff:** Phase 1 shipped clean (commit `338f42d`, 649 passed / 5 skipped). Phase 2 design fully settled in `STATE_TWIN_PHASE_2_EXPANDED.md`. No code written yet.

**Branch:** Phase 1 is on `main` (origin/main push may still be pending — check). Create `feat/liveprovider-v3-phase2` off `main` before any further work.

**Version target after Phase 2:** `2.1.0a2` (still alpha — no PyPI push yet; that batches at the end of Phase 3 per the release strategy decided in chat).

---

## Read these first, in this order

1. `doc/state_twin_execution/STATE_TWIN_PHASE_2.md` — base Phase 2 plan
2. `doc/state_twin_execution/STATE_TWIN_PHASE_2_EXPANDED.md` — **authoritative.** Settles design decisions C4-C9, D6-D15, R14-R15. Test surface enumerated as 24 V3 tests + 4 retrofits + 3 enrichment tests.
3. `doc/state_twin_execution/STATE_TWIN_PHASE_1_EXPANDED.md` — reference for how Phase 1 was executed. Same shape applies to Phase 2.
4. `doc/state_twin_execution/STATE_TWIN_COMPLETION_PLAN.md` — umbrella plan
5. `doc/state_twin_execution/PHASE_1_CLAUDE_CODE_HANDOFF.md` — predecessor handoff doc, useful as a style template

The EXPANDED brief overrides the base Phase 2 doc on every point it covers. If they disagree, EXPANDED wins. Same convention as Phase 1.

---

## What Phase 2 ships

**V3 LiveProvider** — chain-reading provider for Uniswap V3 pools, active-liquidity-only. Pool reads via Multicall3 batched into one round trip. Mirrors Phase 1's V2 shape but with V3-specific reads (`slot0`, `liquidity`, `fee`, `tickSpacing`).

**Multicall3 wrapper** — Lives in `_rpc.py` per D14, NOT a separate `_multicall.py`. One ABI fragment, one helper `multicall_aggregate3(w3, calls)`, one decoder. Used by V3 LiveProvider; V2 LiveProvider continues with sequential reads (no need to refactor).

**PoolSnapshot enrichment** — `block_number`, `timestamp`, `chain_id` added to base `PoolSnapshot` as `Optional[int] = None` per C5. Phase 1 V2 LiveProvider gets retrofitted to populate them. New V3 LiveProvider populates them from the start. MockProvider snapshots stay None.

**Test infrastructure refactored in place** — `_fake_rpc.py` extends to handle V2+V3 (per C6/C7). The 19 Phase 1 V2 tests must pass post-refactor without modification — this is the gate that the refactor stayed within scope.

**Smoke pool:** USDC/WETH V3 3000bps (`0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`).

---

## Locked-in decisions (do NOT relitigate without flagging)

These came out of the EXPANDED brief and are now load-bearing on the implementation:

### Structural corrections (C-series)

- **C4: V3 reserves derivation.** `(reserve0, reserve1)` are token amounts deposited into a position spanning `[lwr_tick, upr_tick]`. Default tick range is full-range (matches MockProvider's eth_dai_v3 default). Caller can override via `lwr_tick` / `upr_tick` kwargs. Math via `uniswappy.utils.tools.v3.SqrtPriceMath.getAmount0Delta` and `getAmount1Delta` — these exist; do NOT reimplement.
- **C5: Schema enrichment.** Three new optional fields on `PoolSnapshot` base, default `None`. MockProvider stays None. LiveProvider always populates.
- **C6: `_fake_rpc.py` refactored in place.** NOT moved to conftest. All 19 Phase 1 V2 tests must pass post-refactor — the gate.
- **C7: Multicall3 fake mechanics.** Fake intercepts at `aggregate3(calls)` level, dispatches by selector, returns ABI-encoded responses from existing `_PairFunctions`/`_V3PoolFunctions` methods. Selector dispatch table is small and explicit (~10 entries). Real work — half a day.
- **C8: timestamp via `getCurrentBlockTimestamp()`** folded into the same multicall as pool reads. No separate `eth_getBlockByNumber` round trip.
- **C9: `chain_id` cached on `RpcClient`** lazily, not on LiveProvider.

### Design decisions (D-series)

- **D6:** Multicall3 address is `0xcA11bde05977b3631167028862bE2a173976CA11`. Hardcode in `_rpc.py`.
- **D7:** `aggregate3` with `allowFailure=false` on every call. Snapshot fails loudly on any read failure.
- **D8:** V3 active-liquidity-only. No tick bitmap walking. Document in LiveProvider docstring + V3PoolSnapshot docstring + live-provider.md.
- **D9:** "latest" resolves once at top of `.snapshot()`. Populate snapshot's `block_number` field with the resolved value.
- **D10:** timestamp from Multicall3's `getCurrentBlockTimestamp()` folded into the batch.
- **D11:** chain_id cached on `RpcClient` per C9.
- **D12:** Refactor `_fake_rpc.py` in place. Phase 1 import paths (`from twin._fake_rpc import ...`) preserved.
- **D13:** V3 tick range default is full-range. `lwr_tick` / `upr_tick` are kwargs, NOT part of the pool_id string.
- **D14:** Multicall3 lives in `_rpc.py`, not a separate `_multicall.py`.
- **D15:** V3 reserves are decimal-adjusted floats, same as V2 contract from Phase 1's C2.

### Risks (R-series)

- **R14:** Boundary-case zero-reserve handling. Active tick at range boundary → one reserve = 0. Document, test in `test_v3_active_tick_at_range_boundary_produces_single_sided`.
- **R15:** sqrtPriceX96 precision. Keep as Python `int` until decimal-adjustment step; `getAmount0Delta`/`getAmount1Delta` return int, then `int / 10**decimals` is the final float conversion.

---

## File inventory

### Production code

| File | Status | Purpose |
|---|---|---|
| `python/prod/twin/snapshot.py` | MODIFY | Add three `Optional[int] = None` fields to `PoolSnapshot` base. All four subclasses inherit. |
| `python/prod/twin/_rpc.py` | MODIFY | Add `MULTICALL3_ADDRESS` const, Multicall3 ABI fragment, `multicall_aggregate3(w3, calls, block_number)` helper, `load_v3_pool_contract(w3, address)`, multicall response decoder. Cache `chain_id` lazily on `RpcClient` per C9. |
| `python/prod/twin/live_provider.py` | MODIFY | Add `_snapshot_v3` path. Retrofit `_snapshot_v2` to populate new enrichment fields. Both paths read `block_number`, `timestamp`, `chain_id` and write them onto the snapshot. |
| `python/prod/twin/mock_provider.py` | unchanged | Recipe lambdas already produce snapshots without enrichment fields; defaults are None. No work needed. |
| `python/prod/twin/builder.py` | unchanged | Already handles `V3PoolSnapshot`. |
| `python/prod/twin/provider.py` | unchanged | ABC already widened in Phase 1. |

### Test code

| File | Status | Purpose |
|---|---|---|
| `python/test/twin/_fake_rpc.py` | MODIFY | Add `V3PoolSpec`, `_V3PoolFunctions`, `_MulticallFunctions`. `build_fake_client` dispatches on `V2PoolSpec` vs `V3PoolSpec`. Add canonical USDC/WETH V3 fixture helpers. Per C6 — keep V2 surface unchanged so Phase 1 tests pass. |
| `python/test/twin/test_live_provider_v3.py` | NEW | The 24 V3 tests enumerated in the EXPANDED brief. |
| `python/test/twin/test_live_provider_v3_live.py` | NEW | 4-5 opt-in live-RPC tests against USDC/WETH V3 3000bps. Gated by `DEFIPY_LIVE_RPC` env var. |
| `python/test/twin/test_live_provider_v2.py` | MODIFY (small) | Add 1 test verifying V2 LiveProvider snapshot now carries non-None `block_number`/`timestamp`/`chain_id`. Existing 19 tests untouched. |
| `python/test/twin/test_live_provider_v2_live.py` | MODIFY (small) | Add 1 test verifying live V2 snapshot has populated enrichment fields. |
| `python/test/twin/test_snapshot.py` | MODIFY | Add 3 tests: enrichment fields default to None on `V2PoolSnapshot`, `V3PoolSnapshot`, `BalancerPoolSnapshot`/`StableswapPoolSnapshot`. |
| `python/test/twin/test_mock_provider.py` | MODIFY (small) | Add 1 test verifying recipe snapshots have `block_number is None` etc. |
| `python/test/twin/test_live_provider.py` | unchanged | Module invariants still hold. |
| `python/test/twin/test_builder.py` | unchanged | |
| `python/test/twin/test_twin_roundtrip.py` | unchanged | |
| `python/test/twin/conftest.py` | unchanged | |

### Config / docs

| File | Status | Purpose |
|---|---|---|
| `setup.py` | MODIFY | Version bump `2.1.0a1` → `2.1.0a2` |
| `CHANGELOG.md` | MODIFY | Add 2.1.0a2 entry (template below) |
| `pytest.ini` | unchanged | `live_rpc` marker already registered |
| `doc/source/twin/live-provider.md` | NEW (deferred from Phase 1) | V2+V3 examples, multicall behavior, active-liquidity-only caveat. **Optional for Phase 2 — can defer to Phase 3 if time-pressured. If skipped, list as a Phase 3 carryover.** |
| `doc/source/twin/snapshot.md` | NEW | Document enrichment field semantics. **Same optionality as live-provider.md.** |

---

## Execution order

The order matters because some changes block others. Follow this sequence:

### 1. Branch + baseline check

```bash
cd ~/repos/defipy
git checkout main
git pull origin main   # confirm Phase 1 is in
git checkout -b feat/liveprovider-v3-phase2
pytest python/test -q | tail -3   # confirm 649 baseline
```

### 2. Schema enrichment first (smallest change, most tests touched)

Edit `python/prod/twin/snapshot.py` — add three `Optional[int] = None` fields to `PoolSnapshot` base. Run:

```bash
pytest python/test/twin/test_snapshot.py -v
```

Existing snapshot tests should pass unchanged. Add the 3 new tests for default-None behavior.

Then update `python/test/twin/test_mock_provider.py` with the kwargs/None-default test, and `python/test/twin/test_snapshot.py` with the 3 enrichment-default tests.

```bash
pytest python/test/twin/ -q   # all twin tests should pass; total +4 (3 snapshot + 1 mock_provider)
```

### 3. Retrofit Phase 1 V2 LiveProvider for enrichment

Edit `python/prod/twin/live_provider.py:_snapshot_v2` to read `block_number` (already has it), pull `timestamp` from a new helper, populate `chain_id` from the client cache, and write all three onto the V2PoolSnapshot.

This requires the timestamp helper to exist first — but in V2 we don't use multicall, so we add a sequential `eth_getBlockByNumber` read for V2 retrofit (one extra round trip is acceptable for V2; the multicall optimization is V3-only). OR fold V2 into the multicall path. **Recommendation: keep V2 sequential, add a `block_timestamp(block_number)` helper to RpcClient.** Less cross-cutting change.

Update `RpcClient` in `_rpc.py`:
- Add `chain_id()` lazy cache per C9.
- Add `block_timestamp(block_number) -> int` helper that calls `w3.eth.get_block(block_number).timestamp`.

```bash
pytest python/test/twin/test_live_provider_v2.py -v
```

Phase 1's 19 tests must still pass. Add 1 new test asserting V2 snapshot now carries enrichment fields.

### 4. Multicall3 production wrapper

Edit `python/prod/twin/_rpc.py`:
- Add `MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"`.
- Add minimal Multicall3 ABI fragment (`aggregate3`, `getCurrentBlockTimestamp`).
- Add `multicall_aggregate3(w3, calls, block_number)` helper. `calls` is a list of `(target_address, function_signature, decode_output_types, args)` tuples. Returns list of decoded values. Set `allowFailure=False` on every call per D7.
- Add `load_v3_pool_contract(w3, address)` mirroring `load_v2_pair_contract`.

No tests yet — wired up in step 6.

### 5. Refactor `_fake_rpc.py` for V3 + multicall

Edit `python/test/twin/_fake_rpc.py`:
- Add `V3PoolSpec` dataclass with sqrtPriceX96, liquidity, fee, tickSpacing, tick.
- Add `_V3PoolFunctions` class (slot0, liquidity, fee, tickSpacing, token0, token1) mirroring `_PairFunctions`.
- Add `_MulticallFunctions` class with `aggregate3` and `getCurrentBlockTimestamp`. Per C7: receives the call list, dispatches each by `(target, selector)` to the appropriate fake's method, ABI-encodes responses.
- Update `build_fake_client` to dispatch on `V2PoolSpec` vs `V3PoolSpec`.
- Add `block_timestamp` parameter to `build_fake_client`.
- Add canonical USDC/WETH V3 helpers: `USDC_WETH_V3_3000_POOL` constant, `canonical_usdc_weth_v3_spec(...)`, possibly `canonical_usdc_weth_v3_token_specs()`.

Critical gate after this step:

```bash
pytest python/test/twin/test_live_provider_v2.py -v
pytest python/test/twin/test_live_provider.py -v
```

**All 19 Phase 1 V2 tests + 4 module invariants must pass without modification.** If any break, the refactor went too far — back off. This is the C6 gate.

### 6. V3 LiveProvider implementation

Edit `python/prod/twin/live_provider.py`:
- Add `_snapshot_v3(pool_address, block_number, lwr_tick, upr_tick)` method.
- Parse `lwr_tick` / `upr_tick` from kwargs in `.snapshot()`. Default to full-range using `UniV3Utils.getMinTick(tick_spacing)` and `getMaxTick(tick_spacing)` after reading `tick_spacing` from chain.
- Build the multicall request (token0, token1, slot0, liquidity, fee, tickSpacing, getCurrentBlockTimestamp).
- After multicall response: derive `(amount0, amount1)` via `getAmount0Delta(sqrt_current, sqrt_upper, L, False)` and `getAmount1Delta(sqrt_lower, sqrt_current, L, False)` per R14.
- Convert to decimal floats per D15: `int / 10**decimals`.
- Read token symbols + decimals separately via `FetchToken` (sequential, same as V2 — token metadata reads can't easily fold into multicall because FetchToken's API is closed). This is fine; the savings from multicall are on the V3-specific reads.
- Construct `V3PoolSnapshot` with reserves, ticks, fee, tickSpacing, and enrichment fields.

Then write the 24 tests in `python/test/twin/test_live_provider_v3.py`. Run:

```bash
pytest python/test/twin/test_live_provider_v3.py -v   # expect 24 pass
pytest python/test/twin/ -q                            # full twin suite
```

### 7. Live RPC verification

Write `python/test/twin/test_live_provider_v3_live.py`:
- 4-5 tests against USDC/WETH V3 3000bps (`0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`).
- Same shape as Phase 1's `test_live_provider_v2_live.py`: gated by `DEFIPY_LIVE_RPC` env var, marked `live_rpc`, defensive bounds rather than exact values.
- Tests: snapshot constructs, token symbols are USDC/WETH, reserves positive and in realistic bounds, runs through CheckPoolHealth, deterministic at specific historical block.
- Also add a 1-test extension to `test_live_provider_v2_live.py` asserting V2 live snapshot has populated enrichment fields.

```bash
DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key> pytest -m live_rpc -v
```

All V3 live tests should pass. If any fail, that's a real production bug the mocked tests didn't catch — debug before committing.

### 8. Full suite + version bump

```bash
pytest python/test -q | tail -5
```

Expected: ~677 passed (649 + 24 V3 + 3 enrichment + 1 V2 retrofit + ~0 displaced). Add the 5 V3 live tests to skipped count → 10 skipped total.

Bump version in `setup.py`: `2.1.0a1` → `2.1.0a2`.

### 9. Docs (optional — see file inventory)

If shipping docs with Phase 2: write `doc/source/twin/live-provider.md` and `doc/source/twin/snapshot.md`. Per the EXPANDED brief, these can be deferred to Phase 3 if time-pressured. **Recommendation: defer unless live RPC verification surfaced things worth documenting.** Phase 3 will need docs anyway, and writing them once with V2+V3+demo material is cleaner than twice.

### 10. CHANGELOG + commit + push

Add to `CHANGELOG.md`:

```markdown
## [2.1.0a2] — 2026-MM-DD (UNRELEASED)

Second alpha of v2.1 "State Twin Completion" cycle. Phase 2 ships V3
LiveProvider with Multicall3 batching and PoolSnapshot enrichment.

### Added

- **V3 LiveProvider** — `provider.snapshot("uniswap_v3:0xADDR")` returns
  a `V3PoolSnapshot` with reserves, ticks, fee, tickSpacing populated
  from on-chain reads. Active-liquidity only — tick bitmap walking is
  deferred to v2.1.x or pairing with `AssessLiquidityDepth`. Optional
  `lwr_tick` / `upr_tick` kwargs override the full-range default for
  callers who want a tight position.
- **Multicall3 batching** for V3 reads. Single round trip for token0,
  token1, slot0, liquidity, fee, tickSpacing, and block timestamp.
  Hardcoded canonical Multicall3 address
  (0xcA11bde05977b3631167028862bE2a173976CA11) — same on every major
  EVM chain.
- **PoolSnapshot enrichment** — `block_number`, `timestamp`, `chain_id`
  fields added to the base `PoolSnapshot` class. Optional, default
  None. LiveProvider populates from chain reads (V2 retrofit + V3
  native); MockProvider snapshots stay None to honestly signal
  "this is synthetic, not a chain read."

### Changed

- **Phase 1 V2 LiveProvider retrofit** — V2 snapshots now carry the
  three enrichment fields. One extra `eth_getBlockByNumber` round
  trip per V2 snapshot vs Phase 1; acceptable for V2 (no multicall).
- **Test infrastructure** — `_fake_rpc.py` extended with `V3PoolSpec`,
  `_V3PoolFunctions`, `_MulticallFunctions`. V2 fixture surface
  unchanged; all Phase 1 V2 tests pass without modification.

### Notes

- Tick bitmap walking explicitly out of scope. Primitives that need
  liquidity at non-active ticks (e.g., `AssessLiquidityDepth` when
  it ships) will need additional reads. Active-liquidity primitives
  (`AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth`,
  `CalculateSlippage`, `DetectRugSignals`) work against V3 LiveProvider
  twins.
- `[chain]` extra still pins `web3 < 7.0` due to web3scout's reliance
  on `eth_utils.abi.get_abi_input_types` (web3 6 only). Tracking
  upstream as v2.2 work.
```

Suggested commit message:

```
feat(twin): LiveProvider V3 + Multicall3 + PoolSnapshot enrichment (v2.1 Phase 2)

- V3 LiveProvider for active-liquidity reads via Multicall3 aggregate3
- Multicall3 wrapper in _rpc.py (D6/D14): hardcoded canonical address,
  allowFailure=false (D7)
- PoolSnapshot enrichment: block_number, timestamp, chain_id as
  Optional[int] = None on base class (C5)
- V2 LiveProvider retrofit to populate enrichment fields
- _fake_rpc.py refactored in place to support V3 + multicall (C6/C7);
  Phase 1 V2 tests pass without modification
- pool_id format unchanged: "<protocol>:<address>"
- V3 tick range: full-range default, caller can override via
  lwr_tick/upr_tick kwargs (D13)
- V3 reserves: decimal-adjusted floats matching V2 contract (D15)
- chain_id cached lazily on RpcClient (C9)
- timestamp via Multicall3 getCurrentBlockTimestamp (C8)
- Version bump to 2.1.0a2

Tests: +28 net (24 V3 + 3 enrichment + 1 V2 retrofit). Live-RPC tests
gated by DEFIPY_LIVE_RPC; 5 new V3 live tests against USDC/WETH V3
3000bps mainnet.

Active-liquidity only — tick bitmap walking explicitly deferred to
v2.1.x or AssessLiquidityDepth pairing.

Refs: doc/state_twin_execution/STATE_TWIN_PHASE_2{,_EXPANDED}.md
```

```bash
git add -A
git commit -m "<above>"
git push -u origin feat/liveprovider-v3-phase2
```

---

## Likely fragile points

I (the prior Claude session writing this handoff) wrote the brief without running any V3 code. These are the spots most likely to need a fix during execution:

### C7 — Multicall3 fake mechanics

**This is the largest single risk.** The fake intercepts `aggregate3(calls).call(block_identifier=N)` at the contract-functions level, decodes each call's `(target, selector, calldata)`, dispatches to the right `_PairFunctions` / `_V3PoolFunctions` method, and re-encodes the return into the multicall response shape `(success: bool, returnData: bytes)[]`.

The decode/encode round-trip is fiddly. Likely failure modes:

- **Selector mismatch** — the dispatch table I gave in the brief lists ten function selectors. If web3.py uses a different ABI signature for any of them, the selector hex won't match. Verify the V3 selectors against `web3._utils.abi.function_abi_to_4byte_selector` for the contract's actual ABI.
- **Return-type encoding mismatch** — `eth_abi.encode(["uint256"], [value])` is straightforward for simple types; tuples (slot0 returns 7 fields) need `eth_abi.encode([["uint160","int24","uint16","uint16","uint16","uint8","bool"]], [(...)])`. Watch the array-vs-tuple distinction.
- **slot0 specifically** — returns 7 values, only sqrtPriceX96 (uint160) and tick (int24) are used. Encode all 7 anyway for ABI compliance; pad with zeros for the unused fields.

Mitigation: write a small unit test for the fake itself before wiring it into the V3 LiveProvider tests. Test encodes a known set of values, decodes the result, asserts round-trip equality.

### V3 reserve derivation math

`getAmount0Delta(sqrt_current, sqrt_upper, L, False)` and `getAmount1Delta(sqrt_lower, sqrt_current, L, False)` should produce the right amounts for a position spanning `[lwr_tick, upr_tick]` with active liquidity `L` at price `sqrt_current`. But:

- The function signatures take `sqrtRatioAX96` and `sqrtRatioBX96` and swap internally if A > B. Make sure the args are in the order the math expects, regardless of swap.
- For amount0: pass `(sqrt_current, sqrt_upper)` — produces amount0 needed to "fill up" from current to upper.
- For amount1: pass `(sqrt_lower, sqrt_current)` — produces amount1 needed to "fill up" from lower to current.

Sanity check on a known case before running the parity test: USDC/WETH at price 3000 USDC/ETH (sqrt = ~1.366e29 in Q96.96), full-range, L = 1e22. Computed amounts should be in the realistic 10M USDC / 3k WETH range.

### `_fake_rpc.py` refactor blast radius

C6 says "all 19 Phase 1 V2 tests must pass post-refactor without modification." This is the gate. If any V2 test breaks, it's a sign the refactor introduced an incompatibility — most likely in `build_fake_client` dispatch or `_FakeContract.functions` access patterns.

Mitigation: refactor in small commits, run V2 tests after each. If you see `AttributeError` or `TypeError` on V2 tests, rewind the last change and try a smaller step.

### V2 retrofit: extra `eth_getBlockByNumber` round trip

Phase 1's V2 LiveProvider made 4 reads: token0, token1, getReserves, totalSupply. Adding timestamp via `eth_getBlockByNumber` makes it 5. That's a 25% latency increase on V2 snapshots vs Phase 1.

**Acceptable for Phase 2 — keep V2 sequential, don't try to fold it into multicall.** Multicall introduces complexity to V2 that doesn't pay off for 5 reads. If V2 latency becomes a real concern later, that's Phase 2.x optimization work.

### Live RPC test stability

V3 pools' `slot0` and `liquidity` change every block. Tests must use defensive bounds (reserves > 0, ratio in 0.1x to 10x of expected) rather than exact values. The exception is the historical-block test (`block_number=19_500_000`) which should produce identical reads on repeated calls.

If a V3 live test starts flaking, check: (a) is the bound too tight, (b) did the pool's liquidity meaningfully shift, (c) is `block_identifier` actually being honored.

### Web3 version still pinned at < 7.0

Phase 1 noted this. Phase 2 doesn't change it. If `pip install -e .[chain]` produces a different web3 version on this machine vs the Phase 1 verification machine, expect web3scout's `abi_load.py` to fail on `get_abi_input_types`. Run `pip show web3 web3scout` and confirm web3 6.x is installed.

---

## Verification gate (Phase 2 ships when all of these pass)

In order:

1. **Phase 1 V2 tests still pass post-refactor.** `pytest python/test/twin/test_live_provider_v2.py python/test/twin/test_live_provider.py -v` — 23 tests pass without modification.
2. **24 V3 mocked tests pass.** `pytest python/test/twin/test_live_provider_v3.py -v`.
3. **Schema enrichment tests pass.** `pytest python/test/twin/test_snapshot.py python/test/twin/test_mock_provider.py -v` — including the +4 new tests.
4. **Full twin suite passes.** `pytest python/test/twin/ -v`.
5. **Full repo suite passes.** `pytest python/test -q | tail -3` — expect ~677 passed.
6. **V3 live RPC smoke passes.** `DEFIPY_LIVE_RPC=https://... pytest -m live_rpc -v` — 5 V2 (existing) + 5 V3 (new) + 1 V2 enrichment retrofit = 11 live tests pass.
7. **Multicall actually batches.** During the V3 live test, inspect that exactly ONE multicall round trip happens for the V3 pool reads (plus separate token-metadata reads). Easiest verification: add a `print(client.call_log)` temporarily and confirm one `aggregate3` call.
8. **Version bumped:** `setup.py` shows `2.1.0a2`.
9. **CHANGELOG.md updated.**
10. **Commit + push to `feat/liveprovider-v3-phase2`.**

---

## Items deferred from Phase 2

Do NOT pick these up opportunistically:

- **V3 tick bitmap walking** — pairs with `AssessLiquidityDepth`, v2.1.x or v2.2.
- **Balancer / Stableswap LiveProvider** — v2.2+.
- **Anvil fork integration tests** — separate optional CI lane, not gating Phase 2.
- **Caching layer** — consumer concern, not LiveProvider's job.
- **Reorg detection** — consumer concern; `block_number` enrichment is the substrate for it.
- **Fee growth tracking for V3** — fee-PnL primitive territory, irrelevant to Phase 2's active-liquidity primitives.
- **web3scout web3 7.x support** — track upstream, v2.2 work.
- **Sphinx docs (`live-provider.md`, `snapshot.md`)** — optional for Phase 2; defer to Phase 3 unless time allows.
- **PyPI release** — batches at end of Phase 3 per the chat-decided release strategy. 2.1.0a2 is git-tag-only.

---

## When Phase 2 lands cleanly

Come back to the chat interface for the Phase 3 EXPANDED brief before any demo / doc code is written. Phase 3 is smaller than Phase 2 (one demo file + Sphinx docs) but has its own design questions:

- What scenario does the fork-and-evaluate demo actually demonstrate?
- Does it use Anvil locally, or just a real RPC against a historical block?
- Does it pair with a notebook in `notebooks/` or stay as a `.py` script?
- What's the docs structure on RTD — one big page or split into V2 + V3 + multicall sub-pages?

Same shape as Phase 1 → Phase 2: settle the design questions in prose first, hand the implementation off after.

Hand off to Phase 3 with:
- Phase 2 commit hash on `main` (after PR merge)
- Test count baseline post-merge (should be ~677)
- Clean working tree
- Live RPC verification confirmed working against current mainnet state

Phase 3 scope per `STATE_TWIN_PHASE_3.md`: fork-and-evaluate demo + RTD docs + final 2.1.0 tag and PyPI push. Estimated 1-2 weeks.
