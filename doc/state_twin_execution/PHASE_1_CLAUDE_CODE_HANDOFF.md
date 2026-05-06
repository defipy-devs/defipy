# Claude Code Handoff — DeFiPy v2.1 Phase 1 Finalization

**Status as of handoff:** All Phase 1 production + test code has been written to disk on the working tree (no commits yet). Need to verify, fix any breakage, and push.

**Branch:** Currently on `main`. Create `feat/liveprovider-v2-phase1` before any further work.

---

## Read these first, in this order

1. `doc/state_twin_execution/STATE_TWIN_PHASE_1.md` — base Phase 1 plan
2. `doc/state_twin_execution/STATE_TWIN_PHASE_1_EXPANDED.md` — **authoritative.** Settles design decisions C1, C2, C3, D1, D5, D6, R1, R7, R8 that the base doc left under-specified. Tests 1–19 enumerated here.
3. `doc/state_twin_execution/STATE_TWIN_COMPLETION_PLAN.md` — umbrella plan (Phase 1, 2, 3)
4. `doc/v2_mvp_execution/DEFIPY_V2_SHIPPED.md` — v2.0 retrospective (helpful context)

The EXPANDED brief overrides the base Phase 1 doc on every point it covers. If they disagree, the EXPANDED brief wins.

---

## What's been written

### Production code (already on disk)

| File | Status | Purpose |
|---|---|---|
| `python/prod/twin/provider.py` | REPLACED | ABC widened to `snapshot(pool_id: str, **kwargs)` per C1 |
| `python/prod/twin/snapshot.py` | REPLACED | R8 docstring on `pool_id` semantics + decimal-floats note |
| `python/prod/twin/mock_provider.py` | REPLACED | Silently absorbs `**kwargs` for cross-provider portability |
| `python/prod/twin/_rpc.py` | NEW | Thin web3scout wrapper. `make_client`, `RpcClient`, `load_v2_pair_contract`, `fetch_token`, `amt_to_decimal` |
| `python/prod/twin/live_provider.py` | REPLACED | V2 implementation. `_parse_pool_id` for `"<protocol>:<address>"`, R1 block-pinning, C2 decimal scaling, `_with_client()` test injection |

### Test code (already on disk)

| File | Status | Purpose |
|---|---|---|
| `python/test/twin/_fake_rpc.py` | NEW | `FakeRpcClient`, `V2PoolSpec`, `TokenSpec`, `build_fake_client`, canonical WETH/USDC fixtures |
| `python/test/twin/test_live_provider.py` | REPLACED | 4 module-level invariant tests (2 preserved from v2.0, 2 rewritten for phase boundary) |
| `python/test/twin/test_live_provider_v2.py` | NEW | All 19 tests from the EXPANDED brief enumeration |
| `python/test/twin/test_live_provider_v2_live.py` | NEW | 5 opt-in live-RPC tests (skipped without `DEFIPY_LIVE_RPC` env var) |

### Config (already on disk)

| File | Status | Purpose |
|---|---|---|
| `pytest.ini` (repo root) | NEW | Registers `live_rpc` marker |
| `setup.py` | REPLACED | Version bumped to `2.1.0a1`, `[chain]` extra added (`web3scout >= 0.2.0`, `web3 >= 6.0, < 7.0`) |

---

## Remaining tasks (in order)

### 1. Add the `test_mock_provider.py` kwargs-absorption test

The EXPANDED brief calls for a "small modify" to `test_mock_provider.py` verifying `**kwargs` are silently absorbed. Append this test to the existing file (don't replace the file — preserve all existing tests):

```python
def test_snapshot_silently_absorbs_kwargs():
    """MockProvider.snapshot ignores arbitrary kwargs for cross-provider
    portability. Per C1 of STATE_TWIN_PHASE_1_EXPANDED.md, callers writing
    code generic over providers can pass `block_number=N` and have
    MockProvider ignore it; LiveProvider would honor it."""
    snap = MockProvider().snapshot(
        "eth_dai_v2", block_number=18_000_000, chain_id=1, foo="bar",
    )
    assert snap.protocol == "uniswap_v2"
    assert snap.reserve0 == 1000.0
```

Place it at the bottom of `test_mock_provider.py`, after the existing `test_v3_recipe_check_pool_health` test.

### 2. Create the branch

```bash
cd ~/repos/defipy
git checkout -b feat/liveprovider-v2-phase1
git status   # confirm all the new/replaced files show up
```

### 3. Install the chain extra

```bash
pip install -e .[chain]
python -c "from defipy.twin import LiveProvider; print('ok')"
```

The import should succeed without web3 errors. If it fails with `ImportError: web3scout`, the install didn't pick up the extra — check `pip show defipy` to verify version is `2.1.0a1`.

### 4. Run the new test files in isolation first

```bash
# The new V2 implementation tests (19 expected pass)
pytest python/test/twin/test_live_provider_v2.py -v

# The rewritten module-invariant tests (4 expected pass)
pytest python/test/twin/test_live_provider.py -v

# All twin tests together — ensures the expanded ABC + kwargs absorption
# don't break MockProvider, builder, snapshot, or roundtrip tests
pytest python/test/twin/ -v
```

### 5. Run the full suite

```bash
pytest python/test -q | tail -5
```

**Expected count: ~648 tests passing.** Math: 629 (v2.0 baseline) + 19 (new V2 tests) + 1 (kwargs absorption test from step 1) − 1 (pre-existing test that may be displaced — see "Likely fragile points" below) = ~648.

### 6. Optional — live RPC smoke test

```bash
DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key> pytest -m live_rpc -v
```

Public Alchemy / Infura free-tier RPCs work. The 5 tests against WETH/USDC V2 should all pass; if any fail, that's a real bug in the production read path that the mocked tests didn't catch.

### 7. Commit and push

Suggested commit message:

```
feat(twin): LiveProvider V2 implementation (v2.1 Phase 1)

- Widen StateTwinProvider ABC to snapshot(pool_id, **kwargs)
- LiveProvider V2 reads via web3scout (ConnectW3, ABILoad, FetchToken)
- pool_id format: "<protocol>:<address>", parsed in LiveProvider
- R1 block consistency: resolve "latest" once at top of .snapshot()
- C2 decimal-adjusted float reserves matching MockProvider contract
- C3 _with_client(client) test injection + FakeRpcClient
- D6 canonical smoke pool: WETH/USDC V2
- New [chain] extras_require: web3scout + web3
- Version bump to 2.1.0a1

Tests: +20 (19 new test_live_provider_v2.py + 1 kwargs absorption).
Live-RPC tests gated by DEFIPY_LIVE_RPC env var.

Refs: doc/state_twin_execution/STATE_TWIN_PHASE_1{,_EXPANDED}.md
```

```bash
git add -A
git commit -m "<above>"
git push -u origin feat/liveprovider-v2-phase1
```

---

## Likely fragile points

I (the prior Claude session) wrote this code without being able to run it. These are the spots most likely to need a fix:

### Test 14 — `test_snapshot_rpc_failure_propagates`

The test triggers failure by giving a pool a `token0_address` with no matching `TokenSpec`. The fake's `eth.contract()` raises `KeyError`. But `FetchToken` inside web3scout has try/except blocks that print the error and **return None** — so the failure may surface as `AttributeError: 'NoneType' object has no attribute 'token_name'` further downstream rather than as the original `KeyError`.

The test currently uses `with pytest.raises(Exception):` which should be permissive enough, but if the real behavior is different (e.g. `FetchToken` succeeds and returns a corrupted ERC20), the test silently passes for the wrong reason. **Run it, read the actual output, tighten the assertion to match reality.**

### Test 10 — `test_live_twin_matches_mock_twin_total_supply`

Asserts `live_lp.total_supply == mock_lp.total_supply` with raw `==`. Both paths build the twin via the same `add_liquidity` arithmetic with the same inputs (1000.0 ETH / 100_000.0 DAI as floats), so this *should* be exact. But if there's any path-dependent precision difference in how the inputs flow through `_rpc.amt_to_decimal` vs MockProvider's literal floats, **swap to `pytest.approx`**.

### Import path — `from twin._fake_rpc import ...`

The existing twin tests use this pattern: `from primitives.conftest import (...)` works because `python/test/conftest.py` puts `python/test` on `sys.path`. So `from twin._fake_rpc import ...` *should* resolve. If it doesn't, two fixes:

1. Quick: change to `from _fake_rpc import ...` and add a path insertion in `test_live_provider_v2.py`'s top:
   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
   ```
2. Cleaner: add `from . import _fake_rpc` to `python/test/twin/__init__.py` (if pytest is configured for package-mode discovery).

### `web3scout` version on disk

Verify with `pip show web3scout`. If it's older than `0.2.0`, `ABILoad(PlatformsEnum.AGNOSTIC, "UniswapV2Pair")` may fail because `agnostic/UniswapV2Pair.json` was added in a recent version. Confirmed present in the local `~/repos/web3scout/` checkout.

### `ConnectW3` URL fallthrough

The production `_rpc.make_client(rpc_url)` constructs `ConnectW3(rpc_url)` and relies on `web3scout.enums.RPCEnum.get_rpc()`'s fallthrough behavior (named net → URL; unknown → use as URL literally). The v1 `ImpermanentLossAgent` uses this same path successfully. If the live_rpc test fails to connect, that fallthrough is the place to look.

---

## Architectural decisions locked in (don't revisit without flagging)

These came out of the session before this handoff and are now load-bearing on the implementation:

- **C1: ABC is `snapshot(pool_id: str, **kwargs)`** — single string + kwargs, not separate `protocol=` arg. `pool_id` for LiveProvider is `"<protocol>:<address>"`.
- **C2: Reserves are decimal-adjusted floats** — `raw / 10**decimals`, native Python float, not `mpz`. Matches MockProvider's contract.
- **C3: Test injection via `LiveProvider._with_client(client)`** — not monkeypatching. `FakeRpcClient` lives in `python/test/twin/_fake_rpc.py`.
- **D1: web3scout's `ConnectW3` + `ABILoad` + `FetchToken`** — not raw web3.py. Reuses the v1 ImpermanentLossAgent's tested path.
- **D5: Token decimals + symbols read at "latest"** — FetchToken doesn't accept block_identifier, but token metadata is effectively immutable. Acceptable for Phase 1.
- **D6: WETH/USDC V2** (`0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc`) is the canonical smoke pool, not USDC/DAI V2.
- **R1: "latest" resolves once at top of `.snapshot()`**. All four V2 pair reads pin to that resolved block.
- **R7: Native floats end-to-end into the snapshot.** No `mpz` until the builder pulls them in.
- **R8: `pool_id` semantics are provider-dependent.** Documented in `V2PoolSnapshot` docstring.

---

## Items deferred from Phase 1 (do NOT do now)

These were intentionally cut from Phase 1 scope. Don't pick them up opportunistically:

- **`doc/source/twin/live-provider.md`** — no Sphinx tree exists yet. Deferred to Phase 3 paper/RTD work.
- **`CHANGELOG.md` v2.1.0a1 entry** — paste manually after files land. Suggested entry below.
- **Bytes32 symbol fallback unit test (legacy MKR-style tokens)** — production code has try/except via FetchToken, exercised via live_rpc test if it ever surfaces. Not worth elaborate mocking for a rare case.
- **V3 / Balancer / Stableswap LiveProvider implementation** — Phase 2 / v2.2.
- **Multicall3 wrapper** — Phase 2.
- **PoolSnapshot enrichment (`block_number`, `timestamp`, `chain_id`)** — Phase 2.

### Suggested CHANGELOG entry

```markdown
## [2.1.0a1] — 2026-05-DD (UNRELEASED)

First alpha of the v2.1 "State Twin Completion" cycle. Phase 1 ships
LiveProvider V2 — chain-reading State Twin construction for Uniswap V2
pools. V3, Balancer, and Stableswap LiveProviders raise
NotImplementedError pointing at later phases / versions.

### Added

- **`defipy.twin.LiveProvider`** — chain-reading provider for V2 pools.
  Pass `pool_id="uniswap_v2:0xADDR"` and an `rpc_url` to construct
  V2PoolSnapshots from on-chain state. Optional `block_number` kwarg
  pins the snapshot to a historical block; without it, `"latest"`
  resolves once at the top of `.snapshot()` and all reads pin to that
  block (R1 block consistency).
- **`[chain]` install extra** — `pip install defipy[chain]` adds
  web3scout + web3 for users who want LiveProvider. Same packages as
  `[book]` and `[anvil]`; intent-based naming.
- **20 new tests** — 19 enumerated mocked-RPC tests for the V2
  implementation, plus 5 opt-in live-RPC tests gated by
  `DEFIPY_LIVE_RPC` env var, plus a kwargs-absorption test for
  MockProvider's portability contract.

### Changed

- **`StateTwinProvider` ABC widened** — `snapshot(pool_id, **kwargs)`
  replaces `snapshot(pool_id)`. MockProvider absorbs kwargs silently;
  LiveProvider uses `block_number` kwarg. Existing single-arg
  MockProvider callers continue to work unchanged.
- **`pool_id` semantics now documented as provider-dependent** in
  `V2PoolSnapshot` docstring. MockProvider uses recipe names;
  LiveProvider uses on-chain pool addresses.
```

---

## When Phase 1 lands cleanly

Come back to the chat interface for the Phase 2 EXPANDED brief before any V3 code is written. The pre-execution brief saved real time on Phase 1 and Phase 2 is bigger.

Hand off to Phase 2 with:
- Phase 1 commit hash on `main` (or wherever you merge to)
- Test count baseline post-merge (should be ~648)
- Clean working tree

Phase 2 scope per `STATE_TWIN_PHASE_2.md`: V3 LiveProvider + Multicall3 + PoolSnapshot enrichment. Estimated 1–2 weeks.
