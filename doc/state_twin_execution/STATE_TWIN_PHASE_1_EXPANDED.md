# State Twin Phase 1 — Expansion / Pre-Execution Brief

**Status:** Companion to `STATE_TWIN_PHASE_1.md`. Tightens the spec where the original is under-specified, locks in design recommendations, enumerates the concrete test surface. Read after the Phase 1 doc; does not replace it.

**Authored:** 2026-04-25, before Phase 1 implementation begins.

**Purpose:** Surface the judgment calls that would otherwise be discovered mid-implementation, settle them in prose, and produce a checklist concrete enough that the actual coding session is mostly mechanical.

---

## What the Phase 1 doc gets right

Worth saying, because the corrections below shouldn't read as criticism of an otherwise-tight spec:

- The phase boundary is correct: V2-only, no V3 sketching, no multicall, no demo work
- R1 (block consistency) and R6 (`token_from_exchange` parity) are real and would have eaten a session each if discovered late
- The `_rpc.py` wrapper as conditional-but-recommended is the right framing
- The `[chain]` extra as the install gate is the right shape — keeps core dependency-free, opts users into chain reads explicitly
- The verification checklist at the end is useful as-written

What follows is the delta — the things the doc says generally but where execution needs them said specifically, plus three structural points that need correcting before code is written.

---

## Three structural corrections to the Phase 1 doc

### C1 — The `.snapshot()` signature contract is misstated

**Phase 1 doc says** (acceptance criterion 7): *"`.snapshot()` signature stays `(pool_address, protocol, block_number=None) -> PoolSnapshot`."*

**v2.0 actually shipped:**
```python
class StateTwinProvider(ABC):
    @abstractmethod
    def snapshot(self, pool_id: str) -> PoolSnapshot: ...
```

Single string arg. `MockProvider.snapshot("eth_dai_v2")` works because `pool_id` is the recipe name. The doc is describing a contract that would be a *change* in Phase 1, not a preservation.

**Resolution options:**

**(a) Keep the single-string ABC, parse a structured pool_id in LiveProvider.** Caller passes `"uniswap_v2:0xAE46..."` or `"uniswap_v2:0xAE46...@18000000"`. LiveProvider parses. Awkward but ABC-compatible.

**(b) Widen the ABC to accept additional keyword arguments.** Change `snapshot(self, pool_id: str)` to `snapshot(self, pool_id: str, **kwargs)`. MockProvider ignores kwargs. LiveProvider uses `block_number` from kwargs. ABC-compatible at the call-site level for existing MockProvider users.

**(c) Treat `pool_id` as overloaded by provider semantics, add `block_number` only on LiveProvider's own method.** Keep ABC as-is. LiveProvider's `.snapshot(pool_id, block_number=None)` extends the ABC signature. Type-checkers will warn about Liskov violation; runtime is fine.

**Recommendation:** **(b)** — widen the ABC. Smallest disruption to existing MockProvider tests, gives LiveProvider clean access to `block_number`, and the kwargs surface can absorb future additions (chain_id override, factory address) without further ABC changes. The `protocol` argument from the doc's stated signature isn't actually needed — the pool_id format `"uniswap_v2:0xAE46..."` carries the protocol prefix, and LiveProvider parses it.

Concrete shape:
```python
# provider.py — UPDATE
class StateTwinProvider(ABC):
    @abstractmethod
    def snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot: ...

# mock_provider.py — no change to behavior, just absorb kwargs
def snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot:
    if pool_id not in self.RECIPES:
        raise ValueError(...)
    return self.RECIPES[pool_id]()

# live_provider.py — parse pool_id, use kwargs.get('block_number')
def snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot:
    protocol, address = self._parse_pool_id(pool_id)
    block_number = kwargs.get('block_number', 'latest')
    if protocol == "uniswap_v2":
        return self._snapshot_v2(address, block_number)
    raise ValueError(f"LiveProvider phase 1: only uniswap_v2 supported, got {protocol!r}")
```

The acceptance criterion 7 in the original Phase 1 doc should be **revised** to: *"ABC widened to `snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot`. MockProvider behavior unchanged. LiveProvider's pool_id format is `<protocol>:<address>`."*

### C2 — Reserves are decimal-adjusted floats, not raw wei

The Phase 1 doc says the snapshot is "structurally equivalent" to MockProvider's `eth_dai_v2`. MockProvider produces `reserve0 = 1000.0`, `reserve1 = 100000.0` — human-readable decimal floats.

`getReserves()` on-chain returns `(reserve0_wei, reserve1_wei, blockTimestampLast)` where `reserve0_wei` is a uint112 in the token's smallest unit. For USDC/DAI that's USDC at 6 decimals (`100_000_000` = 100 USDC) and DAI at 18 decimals (`10**20` = 100 DAI).

`StateTwinBuilder._build_v2` passes reserves straight to `lp.add_liquidity(_TWIN_USER, s.reserve0, s.reserve1, s.reserve0, s.reserve1)`. This expects decimal-adjusted amounts — passing raw wei would build a twin with reserves in wei, and primitives like `AnalyzePosition` would produce nonsense.

**Decision (lock in):** `LiveProvider._snapshot_v2()` reads raw wei from `getReserves()`, reads decimals from each token contract, and **produces a `V2PoolSnapshot` with `reserve0` / `reserve1` already converted to decimal floats**. The conversion is `raw / 10**decimals`. Same for `total_supply` — though phase 1's snapshot doesn't carry total_supply explicitly (the builder reconstructs it via `add_liquidity`'s mint logic), so this only matters for tests that want to assert against on-chain total_supply.

The v1 `ImpermanentLossAgent.prime_mock_pool` uses `FetchToken.amt_to_decimal(tkn, raw)` — that helper does exactly this conversion. **Reuse it directly** rather than reimplementing.

This needs to be stated explicitly in the implementation comments because someone reading `LiveProvider._snapshot_v2` cold will reasonably wonder why we're throwing away decimal precision. The answer is: we're not — we're meeting `StateTwinBuilder`'s decimal-float contract. Document it inline.

### C3 — "Fixture parity with MockProvider" needs a worked sketch

D4 in the Phase 1 doc says: *"Shared fixture factories in `conftest.py`, mirroring MockProvider's fixture structure."*

But MockProvider's structure is *callable recipes returning PoolSnapshot dataclasses*. The mocked-RPC structure is *protocol-specific fake RPC clients that return canned bytes when `eth_call(to, data, block)` is invoked with the right calldata*. These are not the same shape — pretending they are will produce confused fixtures.

**What "fixture parity" actually means in practice:**

Two concentric layers of fixtures:

**Layer 1 — Mocked RPC client.** A fixture `mocked_rpc_v2_eth_dai` returns a `FakeRpcClient` preloaded with the canned responses needed to satisfy a snapshot read of the eth/dai V2 pool. Mocked-out methods: `eth_call`, `eth_blockNumber`, `eth_chainId`. Per-call response keyed by `(to_address, calldata_selector)`.

```python
@pytest.fixture
def mocked_rpc_v2_eth_dai():
    """RPC client that returns canned responses matching the eth_dai_v2
    MockProvider recipe — reserves 1000/100000, decimals 18/18."""
    client = FakeRpcClient(chain_id=1, latest_block=18000000)
    pool = "0xPOOL"
    tkn0 = "0xTKN0"  # ETH-like, 18 decimals
    tkn1 = "0xTKN1"  # DAI-like, 18 decimals

    # getReserves() returns (uint112 r0, uint112 r1, uint32 blockTimestamp)
    client.preload_call(pool, _selector("getReserves()"),
                        _encode_uint112_uint112_uint32(
                            int(1000 * 10**18), int(100000 * 10**18), 0))
    client.preload_call(pool, _selector("token0()"), _encode_address(tkn0))
    client.preload_call(pool, _selector("token1()"), _encode_address(tkn1))
    client.preload_call(pool, _selector("totalSupply()"),
                        _encode_uint256(int(10000 * 10**18)))
    client.preload_call(tkn0, _selector("decimals()"), _encode_uint8(18))
    client.preload_call(tkn1, _selector("decimals()"), _encode_uint8(18))
    client.preload_call(tkn0, _selector("symbol()"), _encode_string("ETH"))
    client.preload_call(tkn1, _selector("symbol()"), _encode_string("DAI"))
    return client
```

**Layer 2 — Built twin via the mocked client.** A fixture `live_twin_v2_eth_dai` that injects the mocked RPC into a LiveProvider, calls `.snapshot()`, then runs it through `StateTwinBuilder().build()`. This is what tests assert against. The byte-equivalence check (criterion R6) compares this twin to the one produced by `MockProvider().snapshot("eth_dai_v2") → builder.build()`.

```python
@pytest.fixture
def live_twin_v2_eth_dai(mocked_rpc_v2_eth_dai):
    provider = LiveProvider.from_rpc_client(mocked_rpc_v2_eth_dai)
    snap = provider.snapshot("uniswap_v2:0xPOOL")
    return StateTwinBuilder().build(snap), snap
```

This requires a `LiveProvider.from_rpc_client(client)` test-only constructor or a way to inject the RPC client around the `rpc_url` parameter. **Recommendation:** a private `LiveProvider._with_client(client)` classmethod intended for tests, alongside the public `LiveProvider(rpc_url)`. Documented as test-internal in the docstring.

**The fixture parity claim, made specific:** `live_twin_v2_eth_dai[0]` and `MockProvider().snapshot("eth_dai_v2") → builder.build()` should produce twins where `lp.get_reserve(token0)`, `lp.get_reserve(token1)`, `lp.total_supply`, `lp.get_price(token0)`, and `lp.factory.token_from_exchange[lp.name]` all match. That's the MockProvider–LiveProvider equivalence test.

---

## Design decisions — recommendations locked in

The Phase 1 doc lists D1-D5 as decisions to be made before code starts. Below is what each should be set to, plus a sixth decision the doc didn't enumerate.

### D1 — RPC client library: **web3scout** (as a dep, used selectively)

**Reasoning:**

- `web3scout >= 0.2.0` is already in `setup.py`'s `[book]` extra. It's a known, working dep on Ian's machine. Adding it as a `[chain]` dep is shipping a tested config, not introducing new install risk.
- v1's `ImpermanentLossAgent` uses `ConnectW3` (URL → `Web3` instance), `ABILoad` (load V2 pair ABI), and `FetchToken` (resolve token address → `ERC20` with name/symbol/decimals). All three solve real problems Phase 1 needs solved.
- `FetchToken.amt_to_decimal()` handles C2's decimal conversion. Reusing it instead of reimplementing avoids R2 (token contract weirdness) gotchas — they've already been encountered and handled there.
- Pure-web3.py would mean reimplementing ABI loading and token decimal fetching. That's two more code paths to test, with no gain for Phase 1's scope.

**Concrete `[chain]` extra:**
```python
'chain': ['web3scout >= 0.2.0', 'web3 >= 6.0, < 7.0'],
```
Same as `[book]`, but the naming separates intent — `[book]` is for textbook readers, `[chain]` is for production live-state reads. They share the same packages today. If they diverge in the future (e.g. `[chain]` needs an event-streaming dep that `[book]` doesn't), the slot is already there.

**What gets used vs. not:**
- Used: `ConnectW3`, `ABILoad`, `FetchToken`
- Not used: web3scout's event/retrieve infrastructure (that's v1 agent territory, irrelevant for stateless snapshot reads)

### D2 — Pool address vs. token-pair lookup: **address only**

Phase 1 doc's recommendation is correct. Lock in: `LiveProvider.snapshot(pool_id="uniswap_v2:0xADDRESS")` requires the caller to provide the pool address. No factory `getPair()` lookup in `LiveProvider`.

Convenience helper deferred — if it ever ships, it's `defipy.twin.utils.find_v2_pool(factory_address, token_a, token_b, rpc_url) -> str`, and it lives outside `LiveProvider`. Not Phase 1.

### D3 — `block_number` behavior: **accept and use, don't introspect yet**

Phase 1 doc's recommendation is correct. Lock in: `block_number` flows through `kwargs.get('block_number', 'latest')`. If `'latest'` is passed (or default), resolve to a concrete block_number once via `eth_blockNumber` and pass that concrete value into every subsequent `eth_call`. Phase 2 adds the snapshot field that exposes which block was read.

**Implementation note:** the resolution-once pattern is what fixes R1 (block consistency). Document it inline:

```python
def _snapshot_v2(self, address: str, block_number):
    # Resolve "latest" once at the start of the read so every subsequent
    # eth_call uses the same concrete block_number. Without this, reserves
    # could be read at block N and total_supply at block N+1 if a new
    # block lands mid-snapshot. R1 fix per STATE_TWIN_PHASE_1.md.
    if block_number == 'latest':
        block_number = self._w3.eth.block_number
    ...
```

### D4 — Test infrastructure: **two-layer fixture as sketched in C3**

See C3 above. Lock in: `FakeRpcClient` class + per-pool fixtures + a `LiveProvider._with_client()` test constructor.

The `FakeRpcClient` class belongs in `python/test/twin/_fake_rpc.py` (or `conftest.py` if it stays small). Not in `python/prod/twin/` — it's test-only. **The Phase 1 doc lists `_rpc.py` as a NEW file in `python/prod/twin/`. Resolution: there are two RPC-shaped files, not one.**

- `python/prod/twin/_rpc.py` (production) — thin wrapper around web3scout's `ConnectW3` + ABI loading + reads. Real code path.
- `python/test/twin/_fake_rpc.py` (test) — `FakeRpcClient` with `preload_call` API. Test-only.

The production `_rpc.py` should expose a small interface (`get_w3()`, `eth_call(to, data, block)`, `block_number()`, `chain_id()`) that the `FakeRpcClient` can mimic structurally. That's what makes the swap via `LiveProvider._with_client()` clean.

### D5 — Token decimal resolution: **read from contract, via `FetchToken`**

Phase 1 doc's recommendation is correct. `FetchToken.apply(addr)` returns an `ERC20` with `.decimals` populated. Use that.

R2 (token contract weirdness) is real — `FetchToken` itself may not handle every weird token, but for canonical mainnet pools (USDC, DAI, WETH, WBTC) it works. Document the limitation in the LiveProvider docstring: *"Tokens with non-standard `decimals()` ABIs may fail to read; LiveProvider does not currently fall back to a hardcoded table. For Phase 1 use, restrict to canonical ERC-20s."*

### D6 — Smoke-test pool selection (NEW; doc didn't enumerate)

Phase 1 doc names USDC/DAI V2 (`0xAE461cA67B15dc8dc81CE7615e0320dA1A9aB8D5`).

**Concern:** V2 has been bleeding TVL for years. A pool with marginal liquidity in 2026 produces marginal `AnalyzePosition` output. The smoke test should hit a pool where the primitives produce *interesting* output, not output-shaped-data-that-happens-to-not-NaN.

**Recommendation:** Use **WETH/USDC V2** (`0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc`) as the canonical smoke-test pool. It's been the most active V2 pool throughout the protocol's life — even in 2026, when most volume has migrated to V3, it's the V2 pool most likely to still have meaningful liquidity. AnalyzePosition output against it is meaningful: real reserves, real spot price, real LP supply.

Keep USDC/DAI as a secondary smoke test if both are easy to run. The acceptance criterion in the Phase 1 doc should be revised to name WETH/USDC as primary.

**Note for execution:** before declaring acceptance criterion 1 met, do a `getReserves()` read against the chosen pool and confirm both reserves are > some threshold (say, $1M each in token-equivalent). If they're not, V2 has finally rotted enough that a different pool is needed.

---

## Two more risks the doc doesn't flag

### R7 — `gmpy2` interaction with raw uint256 conversion

When `FetchToken` returns reserves and we divide by `10**18`, we're hitting Python ints. Fine. But once those floats land in `lp.add_liquidity()`, the underlying `uniswappy.UniswapExchange` uses `gmpy2.mpz` for some internal math. Mixing native-int wei values with mpz reserves is the kind of subtle precision bug that doesn't surface in unit tests but produces 1e-15 reserve mismatches in roundtrip checks.

**Mitigation:** Convert raw_reserve_wei to a Python int → divide by `10**decimals` → cast to native float before passing to `V2PoolSnapshot.reserve0`. Don't introduce `mpz` until the builder pulls them in. The MockProvider path already produces native floats; matching that contract avoids this risk entirely.

### R8 — `V2PoolSnapshot.pool_id` ambiguity

Phase 1 will produce snapshots where `pool_id` is the pool address (`"uniswap_v2:0xAE46..."` or just `"0xAE46..."` — TBD). MockProvider produces snapshots where `pool_id` is the recipe name (`"eth_dai_v2"`). `StateTwinBuilder._build_v2` uses `pool_id` for token address synthesis: `"0xtwin_{pool_id}_{token_name}"`.

For LiveProvider-built twins, the synthesized address `"0xtwin_uniswap_v2:0xAE46..._ETH"` is ugly but harmless — these are internal token identifiers, not real addresses. **Worth flagging:** if anyone downstream parses `pool_id` expecting either format, the LiveProvider format will surprise them.

**Mitigation:** Document `pool_id` semantics explicitly in `V2PoolSnapshot`'s docstring: *"For MockProvider snapshots, `pool_id` is the recipe name. For LiveProvider snapshots, `pool_id` is the on-chain pool address (40-char hex, with or without `0x` prefix). The format is provider-dependent."*

If this turns into a real problem (e.g. the demo script in Phase 3 needs to introspect provider source), add a `source` field to `PoolSnapshot` in Phase 2 alongside `block_number`.

---

## Concrete test surface for `test_live_provider_v2.py`

The Phase 1 doc says "~10-15 new tests" without enumeration. Below is the specific test list, organized by what each test proves.

### Snapshot construction (5 tests)

1. **`test_snapshot_returns_v2_pool_snapshot`** — `provider.snapshot("uniswap_v2:0xPOOL")` returns a `V2PoolSnapshot` (not a different subclass).

2. **`test_snapshot_reserves_decimal_adjusted`** — Mocked `getReserves()` returns `(1000 * 10**18, 100000 * 10**18, 0)` and decimals 18/18. Snapshot has `reserve0 == 1000.0`, `reserve1 == 100000.0`. **This is the C2 contract test.**

3. **`test_snapshot_handles_mixed_decimals`** — Mocked USDC (6 decimals) / WETH (18 decimals) pool. Reserves come out in human-readable units regardless of decimal mismatch.

4. **`test_snapshot_reads_token_symbols`** — Mocked `symbol()` returns `"USDC"`, `"DAI"`. Snapshot has `token0_name == "USDC"`, `token1_name == "DAI"`.

5. **`test_snapshot_pool_id_is_address`** — Snapshot's `pool_id` matches the address from the input pool_id string. Settles R8 explicitly.

### Block consistency (3 tests)

6. **`test_block_number_resolved_once`** — When `block_number='latest'` (default), `eth_blockNumber` is called exactly once at the start of `.snapshot()`. All subsequent `eth_call`s use the resolved concrete block_number. **R1 fix verification.** (Inspect `mocked_rpc.call_log` for the sequence.)

7. **`test_explicit_block_number_used_directly`** — `provider.snapshot("uniswap_v2:0xPOOL", block_number=18000000)` doesn't call `eth_blockNumber` and uses 18000000 for all reads.

8. **`test_block_number_consistency_across_reads`** — Every `eth_call` in a snapshot uses the same `block_identifier`. If the mocked client logs each call's block param, they should all match. Slightly redundant with #6/#7 but explicit.

### `MockProvider` parity (3 tests — the R6 fix)

9. **`test_live_twin_matches_mock_twin_reserves`** — Build a twin via LiveProvider with mocked reserves matching `eth_dai_v2` recipe (1000 ETH / 100000 DAI). Build a twin via MockProvider with the same recipe. `lp.get_reserve(eth)` and `lp.get_reserve(dai)` match.

10. **`test_live_twin_matches_mock_twin_total_supply`** — `lp.total_supply` matches between live-built and mock-built.

11. **`test_live_twin_token_from_exchange_populated`** — `lp.factory.token_from_exchange[lp.name]` is populated and structured identically. **The MCP server compatibility check.**

### Error paths (4 tests)

12. **`test_snapshot_unknown_protocol_raises`** — `provider.snapshot("uniswap_v4:0xPOOL")` raises `ValueError` with message naming v4 and listing supported protocols.

13. **`test_snapshot_malformed_pool_id_raises`** — Missing `:` separator, empty protocol, empty address — each raises `ValueError` with specific message.

14. **`test_snapshot_rpc_failure_propagates`** — Mocked RPC raises on `eth_call`. The exception isn't swallowed; it propagates with context (which call failed against which contract).

15. **`test_snapshot_v3_protocol_not_yet_supported`** — `provider.snapshot("uniswap_v3:0xPOOL")` raises `ValueError` with message naming Phase 2. **Forces explicit handling of the Phase 1 boundary.** Without this test, a future drift could silently start handling V3 with V2 logic.

### Construction and config (2 tests)

16. **`test_live_provider_init_stores_rpc_url`** — Existing v2.0 test, preserved.

17. **`test_live_provider_with_client_classmethod`** — `LiveProvider._with_client(fake_client)` returns a usable provider. Test-internal API, but worth a smoke test.

### Acceptance bridges to existing primitives (2 tests)

18. **`test_live_twin_runs_through_analyze_position`** — Build live twin (mocked), pass to `AnalyzePosition().apply(...)`, assert result has finite values (no NaN, no inf). Mirror of `test_v2_recipe_runs_analyze_position` from `test_twin_roundtrip.py`.

19. **`test_live_twin_runs_through_check_pool_health`** — Same shape, against `CheckPoolHealth`.

**Total: 19 tests.** Comfortably inside the doc's "10-15" estimate plus a small safety margin. Some can be parameterized to keep the file compact.

---

## File layout — final, concrete

After Phase 1, the relevant tree looks like:

```
python/prod/twin/
├── __init__.py                  # MODIFY — export updated LiveProvider
├── builder.py                   # unchanged
├── live_provider.py             # MODIFY — V2 implementation
├── mock_provider.py             # MODIFY — absorb **kwargs in .snapshot() (C1)
├── provider.py                  # MODIFY — widen ABC (C1)
├── snapshot.py                  # MODIFY (small) — pool_id docstring (R8)
└── _rpc.py                      # NEW — production RPC wrapper

python/test/twin/
├── __init__.py                  # unchanged
├── _fake_rpc.py                 # NEW — FakeRpcClient for mocked-RPC tests
├── conftest.py                  # MODIFY — add layer-1 + layer-2 RPC fixtures
├── test_builder.py              # unchanged
├── test_live_provider.py        # KEEP — existing 4 stub tests, still relevant
├── test_live_provider_v2.py     # NEW — the 19 tests above
├── test_mock_provider.py        # MODIFY (small) — verify kwargs absorbed silently
├── test_snapshot.py             # unchanged
└── test_twin_roundtrip.py       # unchanged

setup.py                          # MODIFY — add 'chain' extras_require slot

doc/source/twin/
├── live-provider.md             # MODIFY — replace stub with V2 examples
└── index.md                     # MODIFY (if needed) — V2 shipped notice
```

**Tests after Phase 1:** 629 (v2.0 baseline) + 19 (new) + 0 (no displaced or removed tests, since `test_live_provider.py`'s 4 stub tests still verify the ABC stub-mode behavior even with V2 implemented — the stub tests just need to be re-pointed at `LiveProvider("http://anything").snapshot("invalid_protocol:xxx")` instead of `.snapshot("x")`).

Actually — clarification needed there. Some of the existing `test_live_provider.py` tests assert `NotImplementedError`. After Phase 1, V2 is implemented, so those need updating. The right pattern: keep the test file but rewrite the tests to assert against unsupported protocols (v3, balancer, stableswap) raising `ValueError`/`NotImplementedError`. Two of the four stub tests probably stay as-is (rpc_url storage, web3 not auto-imported), the other two get rewritten.

**Net test count: 629 - 2 (stub tests rewritten in place) + 2 (rewritten as v3-not-yet tests) + 19 (new V2 tests) = ~648 after Phase 1.**

---

## Pre-execution checklist

Before any code is written:

- [ ] C1 settled: ABC widened to `**kwargs`. Acceptance criterion 7 in Phase 1 doc revised accordingly.
- [ ] C2 acknowledged: snapshot reserves are decimal-adjusted floats, not wei. Inline comment mandated.
- [ ] C3 sketched: two-layer fixture pattern + `FakeRpcClient` + `LiveProvider._with_client()`.
- [ ] D1 locked: web3scout, via `[chain]` extra mirroring `[book]`.
- [ ] D6 settled: smoke-test pool is WETH/USDC V2, not USDC/DAI V2.
- [ ] R7 mitigation: native floats end-to-end in the snapshot, no `mpz` until the builder.
- [ ] R8 mitigation: `pool_id` semantics documented in docstring.
- [ ] Existing `test_live_provider.py` plan: 2 of 4 tests rewritten in place, not deleted.

Once these are settled, the Phase 1 implementation session can run mostly mechanically. The longest remaining unknowns are the smoke test (depends on mainnet RPC access and current pool liquidity) and the clean-venv install (depends on `gmpy2` cooperation per R4).

---

## What this expansion does NOT do

- Does not change the Phase 1 scope. V2-only, no V3, no multicall, no demo. The boundaries from `STATE_TWIN_PHASE_1.md` hold.
- Does not pre-resolve Phase 2 work. D6-D11 in the Phase 2 doc are still Phase 2's to settle.
- Does not commit to specific Phase 1 timing. The "~1 week dedicated" estimate from the umbrella plan is unaffected by these clarifications — if anything, settling them up-front shortens the actual coding time.
- Does not change the commit strategy. Phase 1 still merges as a single feature branch with the suggested commit message from the doc.

---

*Once these are confirmed, Phase 1 can begin. The expansion exists so the implementation session is mostly typing, not deciding.*
