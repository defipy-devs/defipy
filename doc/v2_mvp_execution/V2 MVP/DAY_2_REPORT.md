# DeFiPy v2.0 — Day 2 Completion Report

## Objective

Ship `defipy.twin` — the State Twin abstraction. Three public surfaces: `StateTwinProvider` ABC, `MockProvider` with 4 canonical recipes, `LiveProvider` stub. Plus `PoolSnapshot` data and `StateTwinBuilder` glue.

## Deliverables

**Module:** `python/prod/twin/`
- `provider.py` — `StateTwinProvider` ABC (one abstract method: `snapshot(pool_id) → PoolSnapshot`)
- `snapshot.py` — `PoolSnapshot` ABC + 4 concrete kw-only dataclass subclasses (`V2PoolSnapshot`, `V3PoolSnapshot`, `BalancerPoolSnapshot`, `StableswapPoolSnapshot`); `__post_init__` sets the protocol discriminator and validates non-obvious constraints
- `builder.py` — `StateTwinBuilder.build(snapshot)` dispatches on snapshot type via `isinstance`; unknown types raise `TypeError`
- `mock_provider.py` — 4 canonical recipes as lambdas (fresh snapshot per call)
- `live_provider.py` — stub; constructor takes `rpc_url`, `snapshot()` raises `NotImplementedError` with v2.1 + MockProvider message; no web3/web3scout imports

**Tests:** `python/test/twin/` (47 new tests)
- `test_snapshot.py` — construction, protocol discriminator, validation (weight sum, tick ordering, stableswap N=2 + length match)
- `test_builder.py` — type-dispatch per protocol, unknown-type error, reserve/supply/weight/dydx byte-for-byte consistency with `v2_setup`/`v3_setup`/`balancer_setup`/`stableswap_setup` fixtures, spot-price consistency
- `test_mock_provider.py` — per-recipe content checks, sorted recipe list, unknown-recipe error with available list, fresh-snapshot semantics, end-to-end `CheckPoolHealth` calls
- `test_live_provider.py` — rpc_url storage, NotImplementedError with v2.1 + MockProvider mention, no web3 in module globals
- `test_twin_roundtrip.py` — one test per recipe pairing with the curated-10 primitive that applies (V2/V3 → AnalyzePosition + CheckPoolHealth; Balancer → AnalyzeBalancerPosition; Stableswap → AnalyzeStableswapPosition)
- `conftest.py` — re-exports the 4 fixture factories from `primitives.conftest` so builder-consistency tests can compare against the known-good reference without duplicating ~80 lines

**Packaging:** `setup.py` updated with `'defipy.twin'`

## The 4 canonical recipes

| Recipe | Protocol | State |
|---|---|---|
| `eth_dai_v2` | Uniswap V2 | 1000 ETH / 100000 DAI |
| `eth_dai_v3` | Uniswap V3 | 1000 ETH / 100000 DAI, full-range, tick_spacing=60, fee=3000 |
| `eth_dai_balancer_50_50` | Balancer 2-asset | 1000 ETH / 100000 DAI, weights 0.5/0.5 |
| `usdc_dai_stableswap_A10` | Stableswap 2-asset | 100000 USDC / 100000 DAI, A=10 |

## Results

- **End-to-end loop closes:** `MockProvider → builder → lp → primitive → dataclass` — verified in the 6 roundtrip tests
- **Byte-for-byte consistency with conftest:** V2/V3 reserves, total_supply, liquidity all match; Balancer `tkn_reserves`/`tkn_weights` match; Stableswap `tkn_reserves`/A/dydx match
- **Tests:** 603 passing (504 primitives + 52 tools + 47 twin)
- **Commit:** `0aca7c5` on `main`

## Design notes worth carrying forward

1. **`kw_only=True` on dataclasses** avoids the inheritance default-value trap. Base `PoolSnapshot` has `pool_id: str` (required) and `protocol: str = ""` (default); concrete subclasses add required fields without ordering issues.

2. **Protocol discriminator is computed in `__post_init__`**, not supplied by the caller. Prevents construction like `V2PoolSnapshot(..., protocol="balancer")` that would confuse the builder's dispatch.

3. **V3 full-range ticks are lazy**. The snapshot dataclass doesn't need uniswappy loaded at import time — `UniV3Utils.getMinTick/getMaxTick` are imported inside `__post_init__` only when defaults are needed.

4. **Internal `_TWIN_USER` sentinel** in the builder matches conftest's single-100%-owner pattern. Primitives take `lp_init_amt` as a scalar arg, so the user-string identity doesn't affect results; reserves and total_supply match the fixtures byte-for-byte regardless.

5. **Balancer `pool_shares_init` and Stableswap `decimals` on the snapshot** were judgment calls. Both are construction parameters needed by the respective libraries; defaulting them keeps the minimal surface clean (`V2PoolSnapshot(...)` with just reserves works), while still allowing custom pools. Brief-spec was ambiguous; defaulted to conftest values so roundtrip tests hold.

6. **Custom pools in v2.0 bypass MockProvider**. The docstring on `MockProvider` explicitly directs callers wanting non-canonical pools to construct a `PoolSnapshot` and pass to `StateTwinBuilder` directly. No `MockProvider.custom(...)` factory until there's demand.

7. **Fixture re-export via local conftest** (`python/test/twin/conftest.py`) — pytest fixtures are scoped to their directory, so `test_builder.py`'s "matches conftest" tests need a way to reach the primitives fixtures. Using `from primitives.conftest import v2_setup, v3_setup, ...` in a local conftest delegates without duplication and without mutating the existing primitives conftest (which the brief required be left untouched).

## Pause-and-ask surfaces that didn't surface

The brief flagged three "do pause and ask if" items; none triggered:
- Exchange constructors didn't need snapshot fields beyond what was specified — verified by smoke-testing each protocol's construction chain before authoring.
- Balancer and Stableswap construction paths worked on first try by mirroring conftest exactly (same factory names, same ExchangeData shapes, same Join call structure).
- Byte-for-byte consistency tests all pass — no silent divergence detected.

## Day 3 hand-off notes

Day 3 covers the `setup.py` packaging gap (sub-packages `optimization`, `comparison`, `pool_health`, `portfolio`, `risk`, `execution` are all missing from `packages=[...]` per DEFIPY_V2_AGENTIC_PLAN.md §Day 3 Morning) and the MCP server demo at `python/mcp/defipy_mcp_server.py`.

From Day 1: `DISPATCH_SUPPLIED_PARAMS = {"self", "lp", "token_in", "depeg_token"}` — the MCP server's `call_tool` handler will need to resolve `token_in`/`depeg_token` from tool arguments (likely token-name strings mapped to ERC20 instances retrieved from the twin-built lp's `factory.token_from_exchange[lp.name]` dict) alongside the `lp` context.

From Day 2: recipes expose tokens via the standard `lp.factory.token_from_exchange[lp.name]` pattern (V2/V3) and via `lp.tkn_reserves` keys (Balancer/Stableswap) — the MCP dispatch layer can resolve token names consistently across all 4 protocols this way.

## Environment note

The editable install at `/opt/homebrew/lib/python3.11/site-packages/__editable___DeFiPy_1_2_0_finder.py` continues to point at the worktree path so `defipy.twin` (and `defipy.tools` from Day 1) resolve during test runs. Run `pip install -e /Users/ian_moore/repos/defipy --no-deps` to repoint if switching back to main-repo work.

## Next

Day 3 brief — packaging fix + MCP server demo at `python/mcp/defipy_mcp_server.py` — to be written separately per the Agentic Plan.
