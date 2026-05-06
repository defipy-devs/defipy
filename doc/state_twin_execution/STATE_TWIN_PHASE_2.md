# State Twin Phase 2 — V2+V3 Strategically-Tight LiveProvider

**Status:** Forward-looking brief, work not yet started
**Umbrella plan:** `STATE_TWIN_COMPLETION_PLAN.md`
**Predecessor:** Phase 1 (`STATE_TWIN_PHASE_1.md`) — V2 LiveProvider shipped, mocked-RPC test infrastructure in place
**Estimated dedicated time:** ~1-2 additional weeks (on top of phase 1)
**Acceptance gate:** Real V3 pool (canonical: USDC/WETH 3000bps on mainnet) constructs a twin via `LiveProvider().snapshot(...)` that runs through V3 primitives at the active price. `PoolSnapshot` carries `block_number`, `timestamp`, `chain_id`. Test infrastructure handles both protocols cleanly without per-protocol forking of the test patterns.

---

## Goal

Add V3 to LiveProvider, elevate the test infrastructure to handle two protocols cleanly, and enrich `PoolSnapshot` with the chain context fields that consumers will need for caching, reorg awareness, and multi-chain routing.

Phase 2 is the strategically-tight version of LiveProvider — V2+V3 cover the bulk of relevant DeFi liquidity, and the substrate after phase 2 is the version worth pitching from. Phase 3's demo lands hard on V3 specifically; phase 2 is what makes phase 3 worthwhile.

---

## Scope — what's in

- `defipy.twin.live_provider.LiveProvider.snapshot()` working for `protocol="uniswap_v3"` (active-liquidity reads only — full tick bitmap walking is out of scope, see Out of Scope)
- V3 read pattern: pool address → `slot0()` (current sqrtPriceX96, tick) + `liquidity()` (active liquidity) + `token0()` + `token1()` + token decimals + `fee()` + tick spacing
- `V3PoolSnapshot` populated from real chain state, structurally equivalent to `MockProvider`'s `eth_dai_v3` recipe at the active range only
- **Multicall3 batching** for V3 reads — the V3 read pattern is 6-8 reads, sequential calls are slow enough on free-tier RPCs to hurt the smoke-test experience
- `PoolSnapshot` field enrichment: `block_number`, `timestamp`, `chain_id` populated on every snapshot (V2 and V3)
- Test infrastructure elevation: shared mocked-RPC fixture patterns that handle both V2 and V3 cleanly, multicall response decoding helpers, fixture parity with MockProvider's V2/V3 outputs
- Tests in `python/test/twin/test_live_provider_v3.py` plus shared infrastructure refactor in `conftest.py`
- ReadTheDocs update: V3 examples on the LiveProvider page, multicall behavior documented

## Scope — what's out (deferred)

- **V3 full tick bitmap walking** — the active-liquidity-only V3 snapshot covers `AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth`, `DetectRugSignals`, `CalculateSlippage`. It does NOT cover analyses that require knowledge of liquidity at non-active ticks (e.g. `AssessLiquidityDepth`, `EvaluateTickRanges`). Tick-walking is a significant separate piece of work — defer to v2.1.x or pair with the `AssessLiquidityDepth` primitive when it's scheduled.
- Balancer + Stableswap LiveProviders (v2.2+, demand-driven)
- Anvil fork integration tests (still optional; mocked-RPC remains primary)
- Caching layer (LiveProvider remains stateless per call)
- Reorg detection / snapshot invalidation (consumer concern; `block_number` enrichment is enough for consumer-side handling)
- Fee growth tracking for V3 (irrelevant to the active-liquidity primitive set; needed only for fee-PnL primitives, which are V2.x territory)

---

## Deliverables

Files to create or modify:

```
python/prod/twin/live_provider.py          # MODIFY — add V3 snapshot construction
                                            # alongside existing V2 path

python/prod/twin/_rpc.py                   # MODIFY (if exists from phase 1) —
                                            # add multicall helper

python/prod/twin/_multicall.py             # NEW (probably) — Multicall3 wrapper
                                            # if _rpc.py gets too crowded

python/prod/twin/snapshot.py               # MODIFY — add block_number, timestamp,
                                            # chain_id to PoolSnapshot base class

python/test/twin/test_live_provider_v3.py  # NEW — V3 LiveProvider tests
                                            # against mocked RPC responses

python/test/twin/conftest.py               # MODIFY — generalize fixtures from
                                            # phase 1 to handle both V2 and V3,
                                            # add multicall response builders

python/test/twin/test_pool_snapshot.py     # MODIFY (if exists) or NEW —
                                            # tests for the enriched fields

doc/source/twin/live-provider.md           # MODIFY — V3 examples,
                                            # multicall behavior, the
                                            # active-liquidity-only caveat

doc/source/twin/snapshot.md                # MODIFY (if exists) — document
                                            # block_number/timestamp/chain_id
                                            # fields and their semantics
```

`_multicall.py` is conditional on `_rpc.py` getting unwieldy. If multicall fits cleanly inside `_rpc.py`, keep it there. Don't proliferate files unnecessarily.

---

## Acceptance criteria

Phase 2 ships when all of these pass:

1. **Real V3 pool smoke test (manual, documented).** Run against mainnet:
   ```python
   from defipy.twin import LiveProvider

   provider = LiveProvider(rpc_url="https://...")
   snapshot = provider.snapshot(
       pool_address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",  # USDC/WETH V3 3000bps
       protocol="uniswap_v3",
   )
   lp = snapshot.build()
   # lp is a UniswapV3Exchange compatible with V3 primitives at active liquidity
   ```
   `slot0` reading returns sane sqrtPriceX96 and tick; `liquidity()` returns positive value; `block_number`, `timestamp`, `chain_id` are populated on the snapshot.

2. **`AnalyzePosition` runs against the live V3 twin.** A deposit of known size into the live USDC/WETH V3 pool, analyzed via `AnalyzePosition().apply(lp, lp_init_amt, entry_usdc, entry_weth)`, produces a `PositionAnalysis` dataclass with sensible numeric values for the active range.

3. **`SimulatePriceMove` runs against the live V3 twin.** Price-move scenario at ±10% produces sensible new-value and IL outputs.

4. **`CheckPoolHealth` runs against the live V3 twin.** Returns a `PoolHealthAnalysis` with V3 fields populated correctly.

5. **Multicall batching is actually batching.** Inspecting RPC traffic during a V3 snapshot read shows ≤ 2 RPC round-trips total (one for `eth_blockNumber` to resolve `"latest"`, one for the multicall containing all V3 reads). NOT 6-8 separate `eth_call` round-trips.

6. **Mocked-RPC test suite passes for both V2 and V3.** New V3 tests in `test_live_provider_v3.py` cover snapshot construction, field population, multicall response decoding, error paths. V2 tests from phase 1 still pass against the elevated test infrastructure.

7. **`PoolSnapshot` enrichment works on V2 and V3.** Both `V2PoolSnapshot` and `V3PoolSnapshot` carry populated `block_number`, `timestamp`, `chain_id`. Existing primitives that work against MockProvider's twins (which have None or default values for these fields) are not broken.

8. **Existing test suite unaffected.** All 629 v2.0 tests + phase 1's V2 LiveProvider tests still pass. No regressions from the snapshot enrichment or test infrastructure refactor.

9. **Test infrastructure elevation is real.** A new test that needs a mocked-RPC V2 or V3 client uses the shared fixture factory (1-2 lines) rather than hand-rolling RPC mocks (10-20 lines). This is what "elevation" means in practice.

---

## Design decisions to make up-front

These should be settled before V3 implementation begins, ideally before phase 2 starts.

### D6 — Multicall3 contract address

**Recommendation:** Hardcode the canonical Multicall3 address (`0xcA11bde05977b3631167028862bE2a173976CA11`) as a constant in `_rpc.py` or `_multicall.py`. Same address on every major EVM chain; no per-chain configuration needed. If a chain is missing Multicall3, that's a v2.2 problem.

### D7 — V3 read pattern: aggregate3 vs. tryAggregate

**Options:** `aggregate3` (allows partial failure per call) | `tryAggregate` (also partial-failure but older API) | `aggregate` (atomic, fails entire batch on any single failure)

**Recommendation:** `aggregate3`. Lets a missing token decimals or unusual contract behavior surface as a per-call failure rather than tanking the whole snapshot. The test infrastructure can simulate per-call failures for error-path testing.

### D8 — V3 active-liquidity-only stance

**Decision:** Phase 2 ships V3 reads sufficient for active-liquidity primitives only. Tick bitmap walking is out of scope, documented as such, and slated for v2.1.x or pairing with `AssessLiquidityDepth`.

**Implication:** The V3 LiveProvider snapshot does NOT populate the tick bitmap. Primitives that try to walk ticks against a LiveProvider-built V3 twin will hit empty tick data. Document this clearly. The MockProvider V3 twin doesn't fully populate ticks either (just the active range), so this isn't a regression — it's matching the existing behavior pattern.

### D9 — `block_number` resolution for "latest"

**Decision:** Resolve `"latest"` to a concrete block number once at the start of `.snapshot()`, then use that concrete block_number for all subsequent reads (carried forward from phase 1's R1 fix). Populate the snapshot's `block_number` field with the resolved concrete value.

### D10 — `timestamp` source

**Options:** Read block header timestamp via `eth_getBlockByNumber` | derive from system time | leave unpopulated for live reads

**Recommendation:** Read block header timestamp via `eth_getBlockByNumber`. Adds one read per snapshot, but produces a `timestamp` that's actually consistent with the block_number. System time would drift; leaving it unpopulated breaks the field's contract. The block-header read can be folded into the multicall batch on chains where Multicall3 supports `getCurrentBlockTimestamp`.

### D11 — `chain_id` source

**Options:** Read via `eth_chainId` once on LiveProvider construction and cache | Read on every `.snapshot()` call | require caller to provide

**Recommendation:** Read once on LiveProvider construction and cache. The LiveProvider already takes an `rpc_url`; the chain_id of that endpoint is fixed for the LiveProvider's lifetime. Caching means zero per-snapshot cost and no caller-error surface area.

### D12 — Test fixture refactor scope

**Question:** Do the phase 1 V2 fixtures get rewritten to fit the elevated infrastructure, or just augmented?

**Recommendation:** Rewritten if the elevation produces a meaningfully cleaner pattern. Phase 1's hand-rolled-leaning fixtures are explicitly described as "phase 2 will elevate this." Don't preserve phase 1's fixture style for backward compatibility — the test suite isn't an external API. If the V2 tests need updating to use the new fixture factories, that's part of phase 2's deliverables.

---

## Risks and gotchas to watch

### R7 — V3 sqrtPriceX96 / tick translation
Going from `slot0`'s `sqrtPriceX96` to a usable price (and from a tick to the `UniswapV3Exchange` constructor's expected initialization) involves the standard V3 conversions. The math itself isn't novel — it's in the V3 whitepaper and uniswappy already handles it for MockProvider — but plumbing it through the LiveProvider path needs to use the same conversion functions, not reinvent them. If `lp` objects produced by LiveProvider behave subtly differently from MockProvider-built ones in V3 primitives, this is the most likely source of the discrepancy.

### R8 — Multicall response decoding
Multicall3's `aggregate3` returns `(success: bool, returnData: bytes)[]`. Decoding requires knowing the ABI of each call's return type ahead of time. Build a typed wrapper that takes a list of `(target_address, function_signature, decode_type)` tuples and returns decoded values. Don't hand-decode call by call in `.snapshot()` — that's how subtle decoding bugs creep in.

### R9 — V3 fee tier vs. fee on Pool contract
The V3 pool contract has a `fee()` method returning the fee in pips (e.g., `3000` for 0.3%). The `UniswapV3Exchange` constructor expects a fee tier value — verify the unit matches what `MockProvider`'s `eth_dai_v3` recipe passes in. If MockProvider passes `3000` and LiveProvider also reads `3000`, they're aligned. If MockProvider does any unit conversion under the hood, LiveProvider needs to match.

### R10 — Token decimals for V3 tokens
Same as phase 1's R2, but more relevant on V3 because the popular V3 pools (USDC/WETH, USDC/USDT, WBTC/WETH) involve tokens with varying decimals (USDC=6, WETH=18, USDT=6, WBTC=8). The decimals must be read correctly per token; `V3PoolSnapshot` and the resulting exchange object have to handle the asymmetric-decimals case correctly.

### R11 — `PoolSnapshot` enrichment back-compat
Adding fields to `PoolSnapshot` is a non-breaking change *if* the fields default to None or sensible values for non-LiveProvider snapshots. MockProvider's snapshots, if not updated, would have None for `block_number`/`timestamp`/`chain_id`. Decide whether MockProvider snapshots populate these synthetically (e.g., `block_number=0`, `chain_id=0`) or stay None. Document the choice. Either is fine; just be deliberate about it.

### R12 — Test infrastructure refactor blast radius
Generalizing phase 1's V2 fixtures to handle V3 might cascade into changes in the existing primitives test suite (504 tests) if they import from `python/test/twin/conftest.py` indirectly via the cross-test fixture re-exports phase 1 set up. Audit before refactoring; don't break primitives tests as a side-effect of test infrastructure work.

### R13 — Anvil fork as optional tier
Phase 2's scope says Anvil fork tests stay optional. But the temptation will be real: a V3 snapshot reading from a mainnet-fork Anvil instance gives much higher confidence than a mocked-RPC test. The right move is to add Anvil fork as a *separate* optional CI lane that runs nightly or on-demand, not block phase 2 acceptance on it. If you want the higher confidence, build the lane; just don't gate phase 2 ship on it.

---

## Verification steps before declaring phase 2 done

In order:

1. Run full test suite — all v2.0 + phase 1 + phase 2 tests pass.
2. Run V3 smoke test against a real RPC endpoint (USDC/WETH 3000bps on mainnet).
3. Run `AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth` against the V3 smoke-test twin.
4. Inspect RPC traffic during the V3 smoke test — confirm ≤ 2 round-trips (multicall is actually batching).
5. Re-run V2 smoke test from phase 1 — confirm `block_number`, `timestamp`, `chain_id` are now populated on V2 snapshots.
6. Verify a new test using a mocked V3 client uses the shared fixture factory (1-2 lines), not hand-rolled mocks.
7. Update `doc/source/twin/live-provider.md` with V3 examples and the active-liquidity-only caveat.
8. Update `doc/source/twin/snapshot.md` (or create) documenting the enriched fields.
9. Commit. Suggested message:

   ```
   feat(twin): LiveProvider V3 + PoolSnapshot enrichment (Phase 2 of State Twin Completion)

   Adds V3 active-liquidity reads to LiveProvider. PoolSnapshot now
   carries block_number, timestamp, chain_id on both V2 and V3 snapshots.
   Test infrastructure generalized to handle both protocols cleanly.

   - V3 reads via Multicall3 aggregate3: slot0, liquidity, tokens,
     decimals, fee, tickSpacing
   - PoolSnapshot enrichment: block_number resolved from "latest" once,
     timestamp from block header, chain_id cached on LiveProvider construction
   - Test fixtures refactored: shared mocked-RPC patterns handle V2+V3
     without per-protocol forking
   - Smoke test against USDC/WETH V3 3000bps on mainnet passes

   V3 tick bitmap walking explicitly out of scope — active-liquidity only.
   Tick walking pairs with AssessLiquidityDepth (v2.1.x or v2.2).
   Balancer/Stableswap LiveProviders are v2.2+.

   Part of State Twin Completion per STATE_TWIN_COMPLETION_PLAN.md.
   ```

---

## What this phase does NOT do

- **No V3 tick bitmap walking.** Active-liquidity only. Document the limitation; pair with AssessLiquidityDepth when scheduled.
- **No Balancer / Stableswap LiveProviders.** v2.2+, demand-driven.
- **No demo work.** Phase 3's job. Phase 2 ships substrate; phase 3 demonstrates the multi-scenario pattern on top of it.
- **No agent / orchestration code.** Strictly OSS substrate work per the umbrella plan.
- **No caching layer.** Stateless per call. If a consumer wants caching, that's their layer.

---

## What actually shipped

*Populated after phase ships. Retrospective voice — what shipped vs. what the plan said, deviations, gotchas that surfaced (especially around D7-D11 and R7-R13), decisions made mid-flight, follow-ups identified for V2_FOLLOWUPS.md or phase 3.*

*[Reserved.]*
