# State Twin Phase 1 — Happy-Path V2 LiveProvider

**Status:** Forward-looking brief, work not yet started
**Umbrella plan:** `STATE_TWIN_COMPLETION_PLAN.md`
**Predecessor:** v2.0 (`DEFIPY_V2_SHIPPED.md`) — `LiveProvider` ABC ships with stable `__init__(rpc_url)` signature, `.snapshot()` raises `NotImplementedError("LiveProvider lands in v2.1...")`
**Estimated dedicated time:** ~1 week
**Acceptance gate:** Real V2 pool (canonical: USDC/DAI on mainnet) constructs a twin via `LiveProvider().snapshot(...)` that runs through `AnalyzePosition` and `CheckPoolHealth` producing sensible output

---

## Goal

Replace the v2.0 `LiveProvider.snapshot()` `NotImplementedError` with a working V2 implementation. Read mainnet, construct a `V2PoolSnapshot`, build a `UniswapExchange` via the existing `StateTwinBuilder`, run primitives against it.

Phase 1 is the floor of what makes the live-state claim defensible. V3 is phase 2. Multi-protocol expansion (Balancer, Stableswap) is v2.2+. The discipline here is shipping V2 cleanly, not building a multi-protocol abstraction up-front.

---

## Scope — what's in

- `defipy.twin.live_provider.LiveProvider.snapshot()` working for `protocol="uniswap_v2"`
- V2 read pattern: factory address resolution → pool address discovery → `getReserves()` + `totalSupply()` + token addresses + token decimals
- `V2PoolSnapshot` populated from real chain state, structurally equivalent to what `MockProvider`'s `eth_dai_v2` recipe produces
- Mocked-RPC test infrastructure for V2 — fixtures that mirror `MockProvider`'s output bytes, so the same primitives that work against MockProvider work against LiveProvider's mocked output
- `[chain]` extras_require slot in `setup.py` populated with web3 / web3scout dependencies (whichever stack is chosen — see Design Decisions)
- Documentation update on the `LiveProvider` page (currently a stub) showing V2 usage
- Tests in `python/test/twin/test_live_provider_v2.py`

## Scope — what's out (deferred to phase 2 or later)

- V3 reads of any kind
- Multicall batching (V2's 4-6 reads are fine sequentially)
- `PoolSnapshot` field enrichment with `block_number`, `timestamp`, `chain_id` (phase 2)
- Anvil fork-based integration tests (mocked-RPC only for phase 1)
- Caching layer of any kind (LiveProvider is stateless per call)
- Reorg detection or invalidation semantics
- Balancer / Stableswap LiveProviders
- Custom RPC endpoint failover or multi-provider routing
- Rate limiting beyond what the underlying web3 client provides

---

## Deliverables

Files to create or modify:

```
python/prod/twin/live_provider.py          # MODIFY — replace NotImplementedError
                                            # with V2 .snapshot() impl

python/prod/twin/_rpc.py                   # NEW (probably) — RPC client wrapper,
                                            # decoupled from LiveProvider for testability

python/test/twin/test_live_provider_v2.py  # NEW — V2 LiveProvider tests
                                            # against mocked RPC responses

python/test/twin/conftest.py               # MODIFY — add mocked-RPC fixtures
                                            # alongside existing MockProvider fixtures

setup.py                                    # MODIFY — populate
                                            # extras_require['chain']

doc/source/twin/live-provider.md           # MODIFY — replace v2.1-coming stub
                                            # with V2 working examples

doc/source/twin/index.md                   # MODIFY (if needed) — promote
                                            # LiveProvider from "coming v2.1"
                                            # to "V2 shipped, V3 in flight"
```

`_rpc.py` is conditional — if web3.py's client is clean enough to use directly without a wrapper, skip the wrapper. Wrapping is justified only if mocking is awkward without it.

---

## Acceptance criteria

Phase 1 ships when all of these pass:

1. **Real-pool smoke test (manual, documented).** Run against mainnet:
   ```python
   from defipy.twin import LiveProvider

   provider = LiveProvider(rpc_url="https://...")
   snapshot = provider.snapshot(
       pool_address="0xAE461cA67B15dc8dc81CE7615e0320dA1A9aB8D5",  # USDC/DAI V2
       protocol="uniswap_v2",
   )
   lp = snapshot.build()
   # lp is a UniswapExchange compatible with all V2 primitives
   ```
   Reserves, total supply, token addresses, decimals all match what's on-chain at the read block.

2. **`AnalyzePosition` runs against the live twin.** A deposit of known size into the live USDC/DAI pool, analyzed via `AnalyzePosition().apply(lp, lp_init_amt, entry_usdc, entry_dai)`, produces a `PositionAnalysis` dataclass with sensible numeric values. Doesn't have to match a specific reference — just be free of NaN, inf, or obvious errors.

3. **`CheckPoolHealth` runs against the live twin.** Returns a `PoolHealthAnalysis` with TVL > 0, reserves matching what's on-chain, LP concentration computed correctly.

4. **Mocked-RPC test suite passes.** New tests in `test_live_provider_v2.py` cover: snapshot construction from canned RPC responses, snapshot field population matches expected values, error paths (RPC failure, invalid pool address, non-V2 contract at address) handled cleanly.

5. **Existing test suite unaffected.** All 629 v2.0 tests still pass. No regressions.

6. **Clean-venv install with `[chain]` extra works.** `pip install -e .[chain]` in a fresh venv pulls in web3 + web3scout, imports resolve, the smoke test from criterion 1 runs.

7. **Existing `LiveProvider` ABC contract preserved.** Constructor signature stays `LiveProvider(rpc_url: str)`. `.snapshot()` signature stays `(pool_address, protocol, block_number=None) -> PoolSnapshot`.

---

## Design decisions to make up-front

These should be settled before writing code, not discovered mid-flight.

### D1 — RPC client library

**Options:** web3.py directly | web3scout (sibling repo, used by v1's `defipy.agents`) | both

**Recommendation:** web3.py for raw `eth_call` and contract reads. web3scout if its existing helpers (used by v1's event-decoding agents) cover any of the V2 read pattern cleanly. Avoid pulling in web3scout for things web3.py handles directly — keep dependencies minimal.

Decide before phase 1 starts. Whichever is chosen goes into `extras_require['chain']`.

### D2 — Pool address vs. token-pair lookup

**Options:** Caller provides pool address directly | LiveProvider resolves token pair → pool address via factory

**Recommendation:** Caller provides pool address. Factory lookup is convenience surface that adds RPC reads and complexity. Document the V2 factory's `getPair()` pattern in the LiveProvider docs as a hint for callers, but don't bake it into LiveProvider itself.

### D3 — block_number behavior in phase 1

**Options:** Accept block_number param and use it | Accept block_number param but ignore it (always read latest) | Don't accept block_number until phase 2

**Recommendation:** Accept and use it. The `PoolSnapshot` doesn't carry `block_number` until phase 2 enriches it, but the `eth_call` should respect the block_identifier the caller passes. This means a caller can read at block N in phase 1, they just can't introspect what block the snapshot came from. Phase 2 fixes the introspection gap.

### D4 — Test infrastructure shape

**Options:** Hand-rolled mocks per test | shared fixture factories that mirror MockProvider's pattern | record-replay against canned JSON files

**Recommendation:** Shared fixture factories in `conftest.py`, mirroring MockProvider's fixture structure. Each fixture returns a mock RPC client preloaded with the responses needed for a specific pool snapshot. This generalizes cleanly to phase 2's V3 work; hand-rolled mocks per test would have to be refactored anyway.

### D5 — Token decimal resolution

**Options:** Hard-code common token decimals (USDC=6, DAI=18, WETH=18) | Read decimals from each token contract | Lazy: read on first access

**Recommendation:** Read decimals from each token contract as part of the snapshot. Adds 2 reads per snapshot (one per token) but is correct for any token, not just well-known ones. The cost is negligible at V2 scale.

---

## Risks and gotchas to watch

These have historically eaten time on similar work. Worth knowing in advance.

### R1 — `eth_call` block consistency
Every read in a single snapshot must use the same `block_identifier`, or you get a subtle race condition where reserves are read at block N and total supply is read at block N+1. The spread is rare and small, but it produces a `V2PoolSnapshot` that's internally inconsistent. **Plumb a single `block_identifier` value through every `eth_call` in `.snapshot()`.** Hardcode it to `"latest"` if no block_number was passed; resolve `"latest"` to a concrete block number once at the start of `.snapshot()` so subsequent calls all use the same block.

### R2 — Token contract weirdness
Some ERC-20s have non-standard `decimals()` returns (e.g., uint8 vs uint256), and some don't implement `decimals()` at all (legacy tokens). If the snapshot tests pass against USDC/DAI but fail against an obscure pair, this is the likely culprit. Phase 1 only needs to work for canonical test pools, but document the limitation explicitly so phase 2 / consumer-facing usage doesn't trip on it silently.

### R3 — Factory address per-chain
The Uniswap V2 factory address is `0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f` on mainnet. Different per chain, even though most clones use the same address. Phase 1 should accept the factory address as a constructor argument or constant, not hardcode it inside `.snapshot()`. Keeps phase 2 / multi-chain expansion clean.

### R4 — `gmpy2` install pain
The defipy install already trips on `gmpy2` compilation in some environments. Adding `[chain]` extras compounds this if web3 has its own native deps. Test the clean-venv install on at least macOS and Linux before claiming acceptance criterion 6 is met. If `gmpy2` is the long pole, that's a known issue separate from phase 1, but worth not surprising future-you with it.

### R5 — RPC rate limits during testing
Manual smoke tests against mainnet hit RPC providers. Free-tier Alchemy/Infura limits are generous but real. Cache the smoke test responses locally if you find yourself re-running them frequently — the snapshot at a specific block doesn't change, so a cached response from the first manual run is a perfectly good "this still works" signal for subsequent runs.

### R6 — `lp.factory.token_from_exchange` integration
The existing `MockProvider`-built exchanges populate `lp.factory.token_from_exchange[lp.name]` for V2/V3 token resolution. The MCP server depends on this for `_resolve_token`. Phase 1's `LiveProvider`-built exchanges must populate this the same way, or downstream code that works with MockProvider-built twins will fail silently against LiveProvider-built ones. Verify byte-for-byte parity between MockProvider's exchange object and LiveProvider's exchange object in at least one test.

---

## Verification steps before declaring phase 1 done

In order:

1. Run `pytest python/test/primitives/ python/test/tools/ python/test/twin/ python/test/mcp/ -v` — all 629 v2.0 tests pass.
2. Run `pytest python/test/twin/test_live_provider_v2.py -v` — all new V2 LiveProvider tests pass.
3. In a fresh venv: `pip install -e .[chain]`, then `python -c "from defipy.twin import LiveProvider; print('ok')"` — imports resolve.
4. Run the smoke test from acceptance criterion 1 against a real RPC endpoint.
5. Run `AnalyzePosition` and `CheckPoolHealth` against the smoke-test twin per criteria 2-3.
6. Confirm `LiveProvider`-built exchange object has `lp.factory.token_from_exchange[lp.name]` populated.
7. Update `doc/source/twin/live-provider.md` with V2 usage examples; remove the "coming v2.1" stub language.
8. Commit. Suggested message:

   ```
   feat(twin): LiveProvider V2 implementation (Phase 1 of State Twin Completion)

   Replaces v2.0's NotImplementedError with a working V2 snapshot
   implementation. LiveProvider().snapshot(pool_address, "uniswap_v2")
   reads mainnet and constructs a V2PoolSnapshot compatible with the
   existing primitive surface.

   - V2 reads via web3.py: getReserves, totalSupply, token addrs, decimals
   - block_identifier consistency across all reads in a snapshot
   - Mocked-RPC test infrastructure in test_live_provider_v2.py
   - extras_require['chain'] populated for opt-in chain dependencies
   - Existing 629 tests pass; ~10-15 new tests in V2 LiveProvider suite

   V3 is Phase 2. Balancer/Stableswap LiveProviders are v2.2+.

   Part of State Twin Completion per STATE_TWIN_COMPLETION_PLAN.md.
   ```

---

## What this phase does NOT do

Worth saying plainly so the next session doesn't drift:

- **No V3.** Phase 2's job. Don't even sketch V3 reads in phase 1's code.
- **No multicall.** V2 is fine sequentially. Phase 2 introduces multicall for V3.
- **No PoolSnapshot enrichment.** The snapshot stays at v2.0's field set in phase 1. Phase 2 adds `block_number`, `timestamp`, `chain_id`.
- **No fork tests.** Mocked-RPC only. Phase 2 may add Anvil fork as an optional integration tier.
- **No demo work.** Phase 3's job. Phase 1 ships LiveProvider V2 working; demonstrating multi-scenario simulation is a separate phase.

If during phase 1 something surfaces that looks like phase 2 or phase 3 work, note it in `V2_FOLLOWUPS.md` and don't bring it into phase 1. The phase boundaries are scope discipline, not artificial constraints.

---

## What actually shipped

*Populated after phase ships. Retrospective voice — what shipped vs. what the plan said, deviations, gotchas that surfaced, decisions made mid-flight, follow-ups identified for V2_FOLLOWUPS.md or phase 2.*

*[Reserved.]*
