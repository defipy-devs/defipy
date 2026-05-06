# State Twin Phase 2 — Expansion / Pre-Execution Brief

**Status:** Companion to `STATE_TWIN_PHASE_2.md`. Tightens the spec where the original is under-specified, locks in design recommendations, enumerates the concrete test surface. Read after the Phase 2 doc; does not replace it.

**Authored:** 2026-05-DD, after Phase 1 ship (commit `338f42d`), before Phase 2 implementation begins.

**Purpose:** Same as the Phase 1 expanded brief — surface the judgment calls that would otherwise be discovered mid-implementation, settle them in prose, and produce a checklist concrete enough that the actual coding session is mostly mechanical. Phase 2 is bigger than Phase 1; the brief earns its keep proportionally.

---

## What the Phase 2 doc gets right

Worth saying, because the corrections below shouldn't read as criticism of an otherwise-tight spec:

- The phase boundary is correct: V2+V3 active-liquidity, no tick bitmap walking, no Balancer/Stableswap LiveProvider
- The active-liquidity-only stance (D8) is the right scope for v2.1 — the alternative (full tick bitmap) is its own chunky piece of work and pairs better with `AssessLiquidityDepth`
- `Multicall3` aggregate3 (D7) is the right choice for partial-failure tolerance
- The `block_number` resolution-once pattern (D9) is the carry-forward of Phase 1's R1
- Recommendation D11 (chain_id cached on LiveProvider construction) is correct and zero-cost
- The Phase 1 EXPANDED brief's prediction that `_fake_rpc.py` would lift in Phase 2 is now real work; the doc flags this correctly under "Test infrastructure elevation"

What follows is the delta — places the Phase 2 doc says something general where execution needs it specific, plus the structural corrections needed before code starts.

---

## Three structural corrections to the Phase 2 doc

### C4 — V3 reserves derivation: the doc says "active-liquidity reads" but doesn't say what `(reserve0, reserve1)` means in the snapshot

**The Phase 2 doc says** the snapshot captures "current sqrtPriceX96, tick, active liquidity, fee, tick spacing." All true. But the resulting `V3PoolSnapshot` has shape `(token0_name, token1_name, reserve0, reserve1, fee, tick_spacing, lwr_tick, upr_tick)` — and the builder calls `Join().apply(...)` from `uniswappy.process.join` (imported into `builder.py` as `UniJoin` to disambiguate from balancerpy's and stableswappy's identically-named `Join` classes):

```python
Join().apply(lp, _TWIN_USER, s.reserve0, s.reserve1, s.lwr_tick, s.upr_tick)
```

So `reserve0`/`reserve1` for V3 are **token amounts deposited into a position** spanning `[lwr_tick, upr_tick]`, NOT virtual reserves at the active tick. The chain returns `slot0.sqrtPriceX96` and `liquidity` (active L). Going from `(sqrtPriceX96, L)` to `(amount0, amount1)` requires choosing **which tick range** the snapshot represents.

Three options:

**(a) Full range.** Use `UniV3Utils.getMinTick(tick_spacing)` and `getMaxTick(tick_spacing)` for the range, derive `(amount0, amount1)` for that range. Matches MockProvider's `eth_dai_v3` recipe exactly (its default ticks are full-range). Conceptually: "twin captures the pool as if all active liquidity were a single full-range position."

**(b) Active-tick narrow range.** Pick a tight window around the current tick (e.g. ±10 tick spacings) and derive amounts for that range. More directly captures "active liquidity at current tick" but the range width is arbitrary.

**(c) Caller-provided.** User passes `lwr_tick` / `upr_tick` as kwargs; LiveProvider derives `(amount0, amount1)` for that range using the chain's `liquidity`. Most flexible.

**Recommendation:** **(a) as the default, (c) as the kwarg escape hatch.** Concretely:

```python
provider.snapshot("uniswap_v3:0x88e6...")
# Default: full-range ticks, amounts derived for the full range

provider.snapshot("uniswap_v3:0x88e6...", lwr_tick=-887220, upr_tick=887220)
# Caller-specified ticks; amounts derived for that range
```

Reasoning:

- Default-full-range gives MockProvider parity tests something concrete to compare against. A live snapshot of USDC/WETH V3 with full-range ticks should produce a twin where `lp.get_reserve(token)` and `lp.get_liquidity()` match what MockProvider's eth_dai_v3 produces *if MockProvider's reserves were scaled to the live pool's liquidity*. That's a cleaner test contract than "amounts at some narrow range I picked."
- (c) preserves user agency for cases where a tight range matters (e.g. simulating IL at a specific concentration).
- (b) adds an arbitrary parameter without meaningful benefit. Skip.

**The math:** Use `uniswappy.utils.tools.v3.SqrtPriceMath.getAmount0Delta(sqrt_lower, sqrt_current, L, roundUp=False)` and `getAmount1Delta(sqrt_current, sqrt_upper, L, roundUp=False)`. These exist already; do NOT reimplement.

### C5 — `PoolSnapshot` enrichment is a breaking change to the dataclass shape

**The Phase 2 doc says** "add `block_number`, `timestamp`, `chain_id` to `PoolSnapshot` base class." Treats it as a small modify. It isn't.

The current `PoolSnapshot` base class has `pool_id` and `protocol`. Adding three required fields breaks every `MockProvider` recipe (which uses positional-style construction via the recipe lambdas) and every test that constructs a `PoolSnapshot` subclass directly (snapshot tests, builder tests, the new V2 LiveProvider tests).

Two options:

**(a) Required fields with no defaults.** Cleanest contract: every snapshot has populated chain context. Requires updating all four MockProvider recipes plus every test that constructs a snapshot.

**(b) Optional fields with `None` defaults.** Backward-compatible. MockProvider snapshots have `block_number=None, timestamp=None, chain_id=None` unless explicitly populated. LiveProvider always populates them.

**Recommendation:** **(b) — Optional fields with `None` defaults.** Reasoning:

- MockProvider's purpose is synthetic recipes for testing primitives. Forcing it to invent fake `block_number=0, chain_id=1` values is misleading — it's not actually live state, and a `block_number=0` would falsely imply "very early block" to a consumer that introspects the field.
- `None` defaults are honest: "this snapshot has no chain context because it didn't come from a chain." Consumers that need chain context (caching, reorg awareness) check for None and handle accordingly.
- Existing tests don't break. Phase 1's V2 LiveProvider tests don't break — they don't introspect these fields.
- The cost of (b) is one branch in any consumer that wants to use the fields ("if `snap.block_number is None: ...`"). That's tolerable.

**Concrete shape:**

```python
# snapshot.py — PoolSnapshot base
@dataclass(kw_only=True)
class PoolSnapshot(ABC):
    pool_id: str
    protocol: str = ""
    # New in v2.1 Phase 2. None when the snapshot doesn't come from a
    # chain read (e.g. MockProvider). Populated by LiveProvider with
    # the resolved concrete block_number, the corresponding block
    # header timestamp, and the LiveProvider's cached chain_id.
    block_number: Optional[int] = None
    timestamp: Optional[int] = None
    chain_id: Optional[int] = None
```

Phase 1 V2 LiveProvider gets retrofitted to populate these (small change to `_snapshot_v2`). New V3 LiveProvider populates them from the start.

### C6 — Test infrastructure elevation: lift `_fake_rpc.py` into shared conftest, but preserve the V2 fixture API

**The Phase 2 doc says** "test infrastructure elevation: shared mocked-RPC fixture patterns that handle both V2 and V3 cleanly." True intent, but the doc and Phase 1 brief both gestured at this without saying what "shared" means in practice.

The current state (post-Phase 1):

- `python/test/twin/_fake_rpc.py` — `FakeRpcClient`, `V2PoolSpec`, `TokenSpec`, `build_fake_client`, canonical WETH/USDC fixtures
- The fakes are V2-shaped: `_PairFunctions` has `token0`, `token1`, `getReserves`, `totalSupply`. `build_fake_client` takes a `V2PoolSpec`.

The Phase 2 elevation needs:

- `V3PoolSpec` alongside `V2PoolSpec` with V3-shaped fields (sqrtPriceX96, liquidity, fee, tickSpacing, ticks)
- `_V3PoolFunctions` alongside `_PairFunctions` with `slot0`, `liquidity`, `fee`, `tickSpacing`, `token0`, `token1`
- A V3-aware variant of `build_fake_client` (or a single `build_fake_client(pool=V2PoolSpec | V3PoolSpec, ...)` that dispatches on type)
- Multicall3 response support — the fake needs to handle a multicall request and return the equivalent decoded response, so the production code path that uses multicall is exercised
- A way for tests to construct V2 *or* V3 pool fixtures without duplicating canonical-fixture-helper code

**Recommendation:** **Refactor in place; don't move out of `_fake_rpc.py`.** Phase 1 brief said "Phase 2 will lift this into the twin/ conftest as a shared factory." On reflection, that's wrong. `conftest.py` is for fixtures that pytest auto-injects; `_fake_rpc.py` is a library of test helpers explicitly imported. The shape we want is the latter, not the former. Keep `_fake_rpc.py` as the home; refactor it to handle V2+V3.

Concrete shape:

```python
# python/test/twin/_fake_rpc.py — refactored

# Existing (unchanged):
@dataclass class V2PoolSpec: ...
@dataclass class TokenSpec: ...
class FakeRpcClient: ...

# New:
@dataclass class V3PoolSpec:
    address: str
    token0_address: str
    token1_address: str
    sqrt_price_x96: int          # from slot0
    tick: int                    # from slot0
    liquidity: int               # active liquidity
    fee: int                     # 500/3000/10000
    tick_spacing: int            # 10/60/200

# build_fake_client dispatches on pool type:
def build_fake_client(*, pool, tokens, latest_block=..., chain_id=1, block_timestamp=...):
    if isinstance(pool, V2PoolSpec): ...
    elif isinstance(pool, V3PoolSpec): ...
    else: raise TypeError

# Canonical USDC/WETH V3 helper alongside the V2 one:
USDC_WETH_V3_3000_POOL = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
def canonical_usdc_weth_v3_spec(...) -> V3PoolSpec: ...

# Multicall3 fake handler — see C7 below
class _MulticallFunctions: ...
```

Phase 1's V2 tests use `build_fake_client(pool=canonical_weth_usdc_v2_spec(), ...)`. After refactor, same call site works because `V2PoolSpec` is still a valid input to `build_fake_client`. The 19 Phase 1 tests should pass post-refactor with zero changes. **If they don't, the refactor went too far** — back off.

---

## Three more structural items the doc doesn't enumerate

### C7 — Multicall3 fake mechanics

The Phase 2 doc says (under R8) "Build a typed wrapper that takes a list of `(target_address, function_signature, decode_type)` tuples and returns decoded values." Good production guidance. But it doesn't say how the **test fake** mimics multicall.

The honest answer: when LiveProvider invokes the multicall (via `_rpc.multicall_aggregate3(w3, calls)`), the production code does this:

1. Encode each `(target, fn_signature, args)` into ABI-encoded calldata
2. Construct a Multicall3 contract proxy at the canonical address
3. Call `aggregate3(calls).call(block_identifier=N)` — returns `(success, returnData)[]`
4. Decode each returnData per the per-call expected type

The fake needs to satisfy step 3 — `FakeWeb3.eth.contract(address=MULTICALL3_ADDR, abi=...)` should return a contract whose `aggregate3(calls).call(block_identifier=N)` returns the right shape of canned data.

**Recommendation:** Don't try to fake the encode/decode round-trip. The fake intercepts at a higher level: when `aggregate3` is called with a list of `(target, allowFailure, callData)` tuples, the fake **decodes the calldata to identify which function** was being called against which target, **looks up the canned return** the same way `_PairFunctions` and `_V3PoolFunctions` do, and **returns it pre-encoded** in the multicall response shape.

Concretely: `_MulticallFunctions.aggregate3(calls)._BoundCall` receives the list, iterates, dispatches each entry to the appropriate `_PairFunctions` or `_V3PoolFunctions` method via address+selector lookup, and packages the responses as `[(True, encoded_bytes)]`. The selector→fn mapping is small and explicit:

```python
_SELECTOR_DISPATCH = {
    "0x0902f1ac": "getReserves",   # V2
    "0x3850c7bd": "slot0",          # V3
    "0x1a686502": "liquidity",      # V3
    "0xddca3f43": "fee",             # V3
    "0xd0c93a7c": "tickSpacing",    # V3
    "0x0dfe1681": "token0",
    "0xd21220a7": "token1",
    "0x18160ddd": "totalSupply",
    "0x95d89b41": "symbol",
    "0x313ce567": "decimals",
}
```

Each fake function returns its raw value; the multicall handler ABI-encodes per the function's known return type. ABI encoding of simple types (uint, int, address, string) is one-line via `eth_abi.encode([type], [value])`.

**This is real work.** Not "small refactor." Budget half a day.

### C8 — `eth_getBlockByNumber` for block timestamp

The Phase 2 doc (D10) says: "Read block header timestamp via `eth_getBlockByNumber`. The block-header read can be folded into the multicall batch on chains where Multicall3 supports `getCurrentBlockTimestamp`."

Multicall3 does ship `getCurrentBlockTimestamp()` (it's an immutable view that returns `block.timestamp` of the multicall execution itself). **However**, that returns the *current* block's timestamp at the time the multicall executes — useful for "latest" snapshots but **wrong for historical block reads**. If the user passes `block_number=18_500_000`, calling Multicall3 against block 18_500_000 returns block 18_500_000's timestamp via `getCurrentBlockTimestamp()`. That's actually correct — the call is pinned to that block.

**Recommendation:** Use Multicall3's `getCurrentBlockTimestamp()` folded into the same multicall as the pool reads. Saves a round trip vs `eth_getBlockByNumber`. The test fake exposes `block_timestamp` as a parameter to `build_fake_client(...)` and returns it from the multicall response.

### C9 — `chain_id` is read at LiveProvider construction time

The Phase 2 doc (D11) says read once on construction and cache. This is correct, but: **construction is currently lazy** in Phase 1 — the RpcClient is built on the first `.snapshot()` call, not in `__init__`. So "construction time" for chain_id is really "first snapshot call." That's fine, but document it.

**Recommendation:** Cache `chain_id` on the `RpcClient` object on first read, not on the LiveProvider. The LiveProvider reads `client.chain_id()` on every snapshot; the RpcClient caches internally. Same end state, cleaner separation of concerns.

```python
class RpcClient:
    def __init__(self, connector):
        ...
        self._chain_id = None   # lazy

    def chain_id(self) -> int:
        if self._chain_id is None:
            self._chain_id = int(self._w3.eth.chain_id)
        return self._chain_id
```

This is a small change to the existing Phase 1 `RpcClient` class.

---

## Design decisions — recommendations locked in

The Phase 2 doc lists D6-D12 as decisions to make up-front. Below is what each should be set to.

### D6 — Multicall3 contract address

**Lock in:** `0xcA11bde05977b3631167028862bE2a173976CA11`. Hardcode as a module-level constant in `_rpc.py`. Same address on every chain Multicall3 is deployed to. If a chain doesn't have Multicall3, `aggregate3` calls fail with a descriptive error and that's a v2.2 problem.

### D7 — V3 read pattern: aggregate3

**Lock in:** `aggregate3` per the doc. Allows partial failure with `allowFailure=true` per call. **For Phase 2 implementation, set `allowFailure=false` on every call** — we want the snapshot to fail loudly if any read fails, not silently produce a half-populated snapshot. The `aggregate3` choice is about protocol selection; the failure semantics are about call-site policy. Set them tight.

### D8 — V3 active-liquidity-only stance

**Lock in:** Active-liquidity only. Document in the LiveProvider class docstring AND in the V3PoolSnapshot docstring AND in the live-provider.md page. The doc says "primitives that try to walk ticks against a LiveProvider-built V3 twin will hit empty tick data." Keep that as-is — the V3 twin's tick bitmap is the same shape as MockProvider's eth_dai_v3 (only the active range is meaningful).

### D9 — block_number resolution for "latest"

**Lock in:** Resolve once at top of `.snapshot()` per Phase 1 R1. Populate snapshot's `block_number` field with the resolved concrete value.

### D10 — timestamp source

**Lock in:** Multicall3's `getCurrentBlockTimestamp()`, folded into the same multicall batch as the pool reads. Per C8 above.

### D11 — chain_id source

**Lock in:** Cached on `RpcClient` per C9 above. Read lazily on first access.

### D12 — Test fixture refactor scope

**Lock in:** Refactor `_fake_rpc.py` in place per C6. Keep the import paths Phase 1 tests already use (`from twin._fake_rpc import ...`). All 19 Phase 1 V2 tests should pass post-refactor without modification.

### D13 (NEW) — V3 tick range default

**Lock in:** Full-range default per C4. Caller can override via `lwr_tick` / `upr_tick` kwargs. The pool_id format does NOT carry tick range — that stays a kwarg.

### D14 (NEW) — Where Multicall3 lives — `_rpc.py` or `_multicall.py`?

The Phase 2 doc says: "`_multicall.py` is conditional on `_rpc.py` getting unwieldy. If multicall fits cleanly inside `_rpc.py`, keep it there."

**Lock in:** Keep in `_rpc.py`. The multicall surface is small (one ABI fragment, one helper function `multicall_aggregate3(w3, calls)`, one decode function). Splitting into `_multicall.py` adds an import without reducing complexity. Revisit in v2.2 if multicall surface grows.

### D15 (NEW) — V3 snapshot's `reserve0` / `reserve1` units

**Lock in:** **Decimal-adjusted floats**, same as V2 (Phase 1's C2). The chain returns `liquidity` (uint128) and `sqrtPriceX96` (uint160). LiveProvider uses `getAmount0Delta` and `getAmount1Delta` to compute raw amounts (uint), then divides by `10**decimals` per token. Final snapshot has `reserve0` and `reserve1` as Python floats in whole-token units, matching `MockProvider.snapshot("eth_dai_v3").reserve0 == 1000.0` shape.

This is critical for the V3 builder path, which calls `Join().apply(lp, user, s.reserve0, s.reserve1, lwr, upr)` expecting decimal-adjusted amounts.

---

## Two more risks the doc doesn't flag

### R14 — `getAmount0Delta` / `getAmount1Delta` boundary cases

Both functions assume `sqrtRatioAX96 != sqrtRatioBX96` and `sqrtRatioAX96 > 0`. They handle `sqrtRatioAX96 > sqrtRatioBX96` by swapping internally. But if the **current price** is exactly at the lower or upper tick boundary, one of the deltas is zero. That's mathematically correct but produces a snapshot with one reserve = 0, which the builder may or may not handle gracefully.

**Mitigation:** Derive `sqrt_lower`, `sqrt_current`, `sqrt_upper`. Use `getAmount0Delta(sqrt_current, sqrt_upper, L, False)` for amount0 and `getAmount1Delta(sqrt_lower, sqrt_current, L, False)` for amount1. If either is 0, that's the actual chain state and a true mathematical zero — pass through as 0.0 in the snapshot. Document in V3 LiveProvider docstring: "If the active tick is at the boundary of the requested range, one reserve will be 0; this matches V3 single-sided liquidity semantics."

### R15 — `sqrtPriceX96` precision in float conversion

The chain returns `sqrtPriceX96` as a uint160 — up to ~2^160. Converting to a Python float for use in primitives loses precision (Python float is IEEE 754 double, ~15.9 decimal digits). For mainnet pools the precision loss is invisible (sqrtPriceX96 is typically much smaller than uint160's ceiling), but the V3 helpers in uniswappy already mix `int` and `float` paths.

**Mitigation:** Keep `sqrtPriceX96` as Python `int` until the very last step where it converts to a `float` for the snapshot's amount derivation. Use `getAmount0Delta` / `getAmount1Delta` (which take int, return int), then `int / 10**decimals` produces a precision-safe float for typical mainnet values. Only write a precision-checking unit test if the live RPC test surfaces a discrepancy.

---

## Concrete test surface for `test_live_provider_v3.py` and Phase 2 modifications

The Phase 2 doc says "tests in `python/test/twin/test_live_provider_v3.py`" without enumeration. Below is the specific test list. Total: **24 new tests**, plus a small modify to `test_live_provider_v2.py` (3-4 tests added for snapshot enrichment) and to `test_snapshot.py` (3 tests for the new fields).

### V3 snapshot construction (5 tests)

1. **`test_v3_snapshot_returns_v3_pool_snapshot`** — `provider.snapshot("uniswap_v3:0xPOOL")` returns a `V3PoolSnapshot` (not V2).

2. **`test_v3_snapshot_default_full_range_ticks`** — Without `lwr_tick`/`upr_tick` kwargs, snapshot's ticks are full-range per the pool's `tick_spacing`. Matches MockProvider eth_dai_v3 default.

3. **`test_v3_snapshot_caller_provided_ticks`** — Pass `lwr_tick=-600, upr_tick=600` kwargs; snapshot reflects them, amounts derived for that range via `getAmount0Delta`/`getAmount1Delta`.

4. **`test_v3_snapshot_reserves_decimal_adjusted`** — Mocked sqrtPriceX96 + L produces snapshot reserves in whole-token units (D15 contract). For mocked USDC/WETH at known price + liquidity, the resulting `reserve0` and `reserve1` match the `getAmount0Delta`/`getAmount1Delta` outputs after decimal adjustment.

5. **`test_v3_snapshot_handles_mixed_decimals`** — USDC (6) / WETH (18) — reserves come out in human-readable units regardless of decimal mismatch. Same shape as Phase 1's V2 mixed-decimals test.

### V3 read pattern (4 tests)

6. **`test_v3_snapshot_reads_slot0_and_liquidity`** — Mocked V3 pool returns specific sqrtPriceX96 and liquidity; snapshot is constructed from those values. Verify by inspecting `client.call_log` for `slot0` and `liquidity` selectors.

7. **`test_v3_snapshot_reads_fee_and_tick_spacing`** — Mocked pool returns `fee=3000, tickSpacing=60`; snapshot has those fields populated. (Not derived; read directly.)

8. **`test_v3_snapshot_reads_token_addresses_and_metadata`** — `token0`/`token1` reads happen; `FetchToken` is invoked for each; symbols and decimals land in the snapshot.

9. **`test_v3_active_tick_at_range_boundary_produces_single_sided`** — When `sqrtPriceX96` equals `sqrt(getSqrtRatioAtTick(lwr_tick))`, `reserve1 == 0` (R14 contract). Same when at `upr_tick`, `reserve0 == 0`. Document semantics, verify in test.

### Multicall batching (4 tests)

10. **`test_v3_snapshot_uses_multicall`** — Inspecting `client.call_log` shows ONE `aggregate3` call against the Multicall3 address, not 6+ separate calls against the pool address. Verifies the multicall path is actually engaged.

11. **`test_v3_multicall_pin_to_block`** — All calls inside the multicall pin to the resolved block. Same R1 discipline as Phase 1 V2.

12. **`test_v3_multicall_block_timestamp_via_getCurrentBlockTimestamp`** — The multicall batch includes a `getCurrentBlockTimestamp()` call against Multicall3; the response populates the snapshot's `timestamp` field. Verifies C8.

13. **`test_v3_multicall_partial_failure_propagates`** — When one call inside `aggregate3` fails (`allowFailure=false` per D7), the snapshot fails loudly with a clear error, not a partial snapshot.

### MockProvider parity (2 tests)

14. **`test_v3_live_twin_matches_mock_twin_at_known_state`** — Build a fake V3 client whose `(sqrtPriceX96, L, fee, tick_spacing)` produces full-range amounts of `(1000.0, 100000.0)` after decimal adjustment. Compare to `MockProvider().snapshot("eth_dai_v3")` → builder. Reserves should match.

15. **`test_v3_live_twin_token_from_exchange_populated`** — Same R6 check as Phase 1, V3 path. Critical for MCP server compatibility.

### Schema enrichment (5 tests, new file `test_pool_snapshot_enrichment.py` OR added to `test_snapshot.py`)

16. **`test_v2_mock_snapshot_has_none_chain_context`** — `MockProvider().snapshot("eth_dai_v2")` has `block_number is None, timestamp is None, chain_id is None`. C5 contract.

17. **`test_v3_mock_snapshot_has_none_chain_context`** — Same for eth_dai_v3.

18. **`test_v2_live_snapshot_populates_chain_context`** — Phase 1 V2 LiveProvider, after Phase 2 retrofit, populates `block_number`, `timestamp`, `chain_id` on the resulting snapshot.

19. **`test_v3_live_snapshot_populates_chain_context`** — V3 LiveProvider populates the three fields.

20. **`test_chain_id_cached_across_snapshots`** — Two `.snapshot()` calls on the same `LiveProvider` instance — `chain_id()` is read from the chain only once (C9 contract). Inspect `client.call_log` for `eth_chainId` count.

### Error paths (3 tests)

21. **`test_v3_unknown_pool_id_protocol`** — `provider.snapshot("uniswap_v4:0xpool")` raises ValueError. Same as Phase 1's test_snapshot_unknown_protocol_raises.

22. **`test_v3_invalid_tick_range_kwargs`** — `provider.snapshot("uniswap_v3:0xpool", lwr_tick=100, upr_tick=50)` raises ValueError (lwr >= upr). Catches the same condition `V3PoolSnapshot.__post_init__` already validates; this test verifies the error surfaces from LiveProvider before chain reads happen.

23. **`test_v3_multicall_unreachable_chain`** — RPC client raises on the `aggregate3` call; LiveProvider propagates with context.

### Test infrastructure smoke (1 test)

24. **`test_phase_1_v2_tests_pass_after_fake_rpc_refactor`** — Implicit, not a new test. The 19 Phase 1 V2 tests + 4 module invariant tests must all pass post-refactor. If any break, `_fake_rpc.py` refactor went too far. Use `pytest python/test/twin/test_live_provider_v2.py python/test/twin/test_live_provider.py -v` as the gate.

### Modifications to existing tests

- `test_live_provider_v2.py`: add 1 test verifying V2 LiveProvider's snapshot now carries non-None `block_number`, `timestamp`, `chain_id` after the Phase 2 retrofit. Existing 19 tests untouched.
- `test_snapshot.py`: add 3 tests covering the enrichment fields' optional-ness — `V2PoolSnapshot(...)` constructs with no chain-context kwargs, fields default to None. Same for V3, Balancer, Stableswap.

**Total Phase 2 net delta: +24 new tests + 1 V2 retrofit test + 3 enrichment tests + 0 displaced = +28 tests.** Post-Phase-2 baseline: ~677 (649 + 28).

---

## File layout — final, concrete

After Phase 2:

```
python/prod/twin/
├── __init__.py                  # MODIFY (small) — re-export changes if any
├── builder.py                   # unchanged (already handles V3PoolSnapshot)
├── live_provider.py             # MODIFY — add V3 snapshot path,
│                                # populate enrichment fields on V2 path
├── mock_provider.py             # MODIFY (small) — recipes default
│                                # block_number/timestamp/chain_id to None
├── provider.py                  # unchanged (ABC already widened in Phase 1)
├── snapshot.py                  # MODIFY — add Optional[int] fields to base
└── _rpc.py                      # MODIFY — add Multicall3 ABI fragment,
                                 # multicall_aggregate3() helper, V3 loaders;
                                 # cache chain_id on RpcClient

python/test/twin/
├── __init__.py                  # unchanged
├── _fake_rpc.py                 # MODIFY — add V3PoolSpec, _V3PoolFunctions,
│                                # _MulticallFunctions, build_fake_client
│                                # dispatches on V2/V3, canonical V3 fixtures
├── conftest.py                  # unchanged
├── test_builder.py              # unchanged
├── test_live_provider.py        # unchanged (4 module invariants still hold)
├── test_live_provider_v2.py     # MODIFY (small) — add 1 enrichment test
├── test_live_provider_v2_live.py # MODIFY (small) — add 1 live test
│                                # asserting enrichment fields populated
├── test_live_provider_v3.py     # NEW — the 24 V3 tests above
├── test_live_provider_v3_live.py # NEW — opt-in live-RPC tests against
│                                # USDC/WETH 3000bps mainnet (4-5 tests)
├── test_mock_provider.py        # MODIFY (small) — verify recipe snapshots
│                                # have None enrichment fields
├── test_snapshot.py             # MODIFY — 3 tests for enrichment field
│                                # defaults
└── test_twin_roundtrip.py       # unchanged

setup.py                          # MODIFY — version bump to 2.1.0a2

CHANGELOG.md                      # MODIFY — add 2.1.0a2 entry

doc/source/twin/live-provider.md  # NEW (deferred from Phase 1) — V2+V3
                                  # examples, multicall behavior,
                                  # active-liquidity-only caveat
doc/source/twin/snapshot.md       # NEW — document enrichment field
                                  # semantics
```

---

## Pre-execution checklist

Before any code is written:

- [ ] C4 settled: V3 snapshot reserves derived via `getAmount0Delta`/`getAmount1Delta` for full-range default; caller can override with `lwr_tick`/`upr_tick` kwargs.
- [ ] C5 settled: enrichment fields `Optional[int] = None` on `PoolSnapshot` base, retrofit V2 LiveProvider, populate from V3 LiveProvider, MockProvider leaves None.
- [ ] C6 settled: `_fake_rpc.py` refactored in place, not moved to conftest. All 19 Phase 1 V2 tests must pass post-refactor.
- [ ] C7 settled: Multicall3 fake intercepts at `aggregate3` level, dispatches by selector, returns ABI-encoded responses from existing `_PairFunctions`/`_V3PoolFunctions`.
- [ ] C8 settled: timestamp via Multicall3's `getCurrentBlockTimestamp()` folded into the same batch as pool reads.
- [ ] C9 settled: `chain_id` cached on `RpcClient`, lazily read on first access.
- [ ] D6-D15 locked in (above).
- [ ] R14 acknowledged: boundary-case zero-reserve handling documented, tested.
- [ ] R15 acknowledged: int → float conversion happens at decimal-adjustment step, not earlier.
- [ ] Smoke pool: USDC/WETH V3 3000bps (`0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`) per the doc.

Once these are settled, Phase 2 implementation can run mostly mechanically. The longest remaining unknowns are:

- Whether the test `test_v3_live_twin_matches_mock_twin_at_known_state` actually produces matching reserves on first try (depends on cleanly composing `getAmount0Delta` + `getAmount1Delta` + decimal scaling — likely needs a small math debug session).
- Whether `aggregate3` partial-failure semantics surface cleanly (R8 mitigation).
- Whether the Multicall3 fake's selector-dispatch produces ABI-encoded responses that decode cleanly back into the production code path's expected types (C7 — real work).

---

## Pacing notes

The Phase 2 doc estimates "~1-2 weeks." The honest read on the work above is:

- **Multicall3 fake (C7):** half a day to one day. ABI encoding/decoding for ~10 functions, dispatch table.
- **`_fake_rpc.py` V3 surface:** half a day. V3PoolSpec, _V3PoolFunctions, build_fake_client dispatch.
- **V3 LiveProvider implementation:** half a day. The `getAmount0Delta`/`getAmount1Delta` math is the only novel piece; everything else mirrors Phase 1's V2 path.
- **Schema enrichment (snapshot, V2 retrofit, V3 native):** half a day. Touches multiple files but each touch is small.
- **24 V3 tests + ~5 live tests + retrofits:** one to one and a half days.
- **Live RPC verification:** half a day (run, fix surprises, run again).
- **Docs:** half a day if writing the Sphinx pages from scratch (deferred from Phase 1).

Total: 4-5 focused days. The "1-2 weeks" estimate has slack for: dealing with `gmpy2` precision surprises during V3 math debugging (R15), Multicall3 fake decode bugs that only surface during live RPC (C7), and any documentation work that accretes if you choose to ship `2.1.0a2` with the docs that were deferred from Phase 1.

---

## What this expansion does NOT do

- Does not change Phase 2 scope. Active-liquidity only, no tick walking, no Balancer/Stableswap.
- Does not pre-resolve Phase 3 work.
- Does not commit to specific Phase 2 timing.
- Does not change the commit / PR strategy. Phase 2 still ships as a single feature branch.
- Does not gate on external blockers (web3scout supporting web3 7.x is independent — keep `[chain]` pinned at `web3 < 7.0`; track the upgrade as a v2.2 item).

---

## Handoff target

After this brief is approved, the Claude Code handoff doc for Phase 2 (`PHASE_2_CLAUDE_CODE_HANDOFF.md`) follows the same shape as Phase 1's:

- Read order: Phase 2 base + this EXPANDED brief + Phase 1 expanded for reference
- File inventory: from "File layout — final, concrete" above
- Remaining tasks: in execution order
- Likely fragile points: C7 multicall fake, V3 math precision, the V2 retrofit not breaking Phase 1 tests
- Locked-in decisions: D6-D15, C4-C9, R14-R15
- Suggested CHANGELOG entry for 2.1.0a2
- Verification gate: ~677 tests passing, USDC/WETH V3 3000bps live RPC smoke test passes all 5 V3 acceptance primitives

---

*Once these are confirmed, Phase 2 can begin. The expansion exists so the implementation session is mostly typing, not deciding.*
