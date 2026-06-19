# Changelog

All notable changes to DeFiPy are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Earlier releases are tracked in [git tags](https://github.com/defipy-devs/defipy/tags)
and the GitHub releases page.

---

## [2.2.0] — 2026-06-18

The "Balancer & Stableswap LiveProvider" cycle. v2.2 extends the
LiveProvider read path from V2/V3 to Balancer V2 weighted pools and
Curve plain Stableswap pools — the same `provider.snapshot(...)` →
`StateTwinBuilder().build(...)` flow, now across all four protocol
families. Read path only: the snapshots, builders, and math were
already in place.

### Added

- **`multicall_aggregate3_args`** (`twin/_rpc.py`) — an argument-bearing
  sibling to `multicall_aggregate3`. ABI-encodes calldata args, so it
  serves `getPoolTokens(bytes32)`, `coins(uint256)`, `balances(uint256)`
  and the no-arg getters through one block-pinned `Multicall3.aggregate3`
  path. Optional `allow_failure` returns `None` in a sub-call's slot
  instead of reverting the batch (used by the Curve coin-count probe).
  The no-arg helper and the V3 read path are untouched.
- **Balancer LiveProvider** — `provider.snapshot("balancer:0xADDR")`
  builds a `BalancerPoolSnapshot` from a real Balancer V2 weighted pool.
  Two block-pinned round trips: pool `getPoolId`/`getVault`/
  `getNormalizedWeights` + timestamp, then the Vault's
  `getPoolTokens(poolId)` (balances live on the Vault, keyed by poolId).
  Normalized weights read honestly; reserves decimal-adjusted.
  2-asset weighted pools only — 3-asset raises `NotImplementedError`.
- **Stableswap LiveProvider** — `provider.snapshot("stableswap:0xADDR")`
  builds an N-coin `StableswapPoolSnapshot` (N ∈ {2, 3}) from a real
  Curve plain pool. Reads `A()` + `coins(i)`/`balances(i)` + timestamp
  in one pinned batch. Coin count comes from an optional `n_coins`
  kwarg (fast path) or an `allow_failure` `coins(0..K)` probe that
  counts the leading non-reverting run. Plain pools only (stored_rate
  = 1); `A()` not `A_precise()`.
- **N-coin `StableswapPoolSnapshot`** — the schema guard widened from
  exactly-2 to at-least-2 tokens. `_build_stableswap` was already
  N-safe. `decimals` stays scalar 18 (decimals-invariant for plain
  pools). 1-token snapshots still raise.
- **Balancer / Curve contract loaders** (`twin/_rpc.py`) —
  `load_balancer_pool_contract`, `load_balancer_vault_contract`,
  `load_curve_pool_contract` over web3scout's ABI bundle, for symmetry
  / direct calls / live debugging.

### Changed

- **web3scout pinned to `>= 1.0.0`** in the `chain` / `book` / `agentic`
  extras (1.0.0 carries the Balancer/Curve read ABIs and platform
  enums). Was `>= 0.2.0`.
- Both Balancer and Stableswap `NotImplementedError` stubs in
  `LiveProvider.snapshot()` are gone. All four protocol prefixes
  (`uniswap_v2`, `uniswap_v3`, `balancer`, `stableswap`) are
  implemented; only an unknown prefix raises `ValueError`.

### Notes

- Out of scope for v2.2 (v2.3): N-asset Balancer, rate-bearing Curve
  pools (metapools, LSD), per-token native decimals on the snapshot,
  and extending the position/risk primitives (`AnalyzeStableswapPosition`,
  `AnalyzeBalancerPosition`, `AssessDepegRisk`) beyond 2-asset.

---

## [2.1.0] — 2026-05-07

The "State Twin Completion" cycle. v2.1 makes the State Twin substrate
real — chain reads compose with every primitive in the library, the
same way `MockProvider` recipes do. The "what would happen if?" loop is
now local: pull state once, simulate forever, decide before executing.

### Added

- **V2 LiveProvider** — `provider.snapshot("uniswap_v2:0xADDR")` builds
  a `V2PoolSnapshot` from real on-chain state. Block-pinned reads,
  decimal-adjusted reserves, ERC20 metadata via web3scout's `FetchToken`.
- **V3 LiveProvider** — `provider.snapshot("uniswap_v3:0xADDR")` builds
  a `V3PoolSnapshot` with reserves, ticks, fee, tickSpacing populated
  from on-chain reads via Multicall3 (single round trip for token0,
  token1, slot0, liquidity, fee, tickSpacing, block timestamp).
  Active-liquidity only — tick bitmap walking is deferred to v2.2 or
  pairing with `AssessLiquidityDepth`. Optional `lwr_tick` / `upr_tick`
  kwargs override the full-range default for callers who want a tight
  position.
- **Multicall3 batching** for V3 reads. Hardcoded canonical Multicall3
  address (`0xcA11bde05977b3631167028862bE2a173976CA11`) — same on
  every major EVM chain. `allowFailure=False` on every sub-call: a
  failed read fails the snapshot loudly rather than producing partial
  data.
- **PoolSnapshot enrichment** — `block_number`, `timestamp`, `chain_id`
  fields added to the base `PoolSnapshot` class. Optional, default
  `None`. LiveProvider populates from chain reads; MockProvider
  snapshots stay `None` to honestly signal "synthetic, not chain
  state."
- **`LiveProvider.get_w3()`** — public method exposing the underlying
  `web3.Web3` instance. DeFiPy stays read-only by design; consumers
  needing to sign transactions reach the substrate underneath via
  `get_w3()` rather than monkey-patching internals or rebuilding their
  own `ConnectW3`. Lazy client caching: first `get_w3()` or
  `.snapshot()` call constructs the `RpcClient`; both methods share
  one connection per `LiveProvider` instance.
- **`PoolHealth` ergonomics for V3** — three additive fields populated
  by `CheckPoolHealth.apply()`: `fee_pips` (V3 fee tier in pips,
  `None` for V2), `tvl_in_token1` (symmetric to existing
  `tvl_in_token0`), `tick_current` (V3 current tick from
  `lp.slot0.tick`, `None` for V2). `RugSignalReport` gets the new
  fields transitively via its embedded `PoolHealth`.
- **`[chain]` install extra** — `pip install defipy[chain]` adds
  `web3scout` and `web3.py` for users who want LiveProvider. Core
  install (no extras) remains free of any chain or LLM dependencies.
- **`[agentic]` install extra** — composes `[chain]` and `[mcp]` for
  the canonical "Python SDK for Agentic DeFi" install. The capability
  extras keep their single-purpose semantics; `[agentic]` is a
  persona-named bundle for the full-stack install.
- **Fork-and-evaluate worked example** —
  [`python/examples/state_twin_fork_evaluate.py`](./python/examples/state_twin_fork_evaluate.py)
  demonstrates the State Twin's multi-scenario reasoning pattern.
  Pulls a V3 pool snapshot once, forks the twin N ways under price
  scenarios, runs primitives against each fork, aggregates into a
  recommendation. Walks through the pattern at
  [defipy.org/fork-evaluate/](https://defipy.org/fork-evaluate/).

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
- `[chain]` extra pins `web3 < 7.0` due to `web3scout 0.2.0`'s
  reliance on `eth_utils.abi.get_abi_input_types` (web3 6 only).
  Tracking upstream as v2.2 work.
- "Result dataclasses should be complete against the notebook user's
  first attempt to read them" — the principle the `PoolHealth`
  ergonomics fix establishes for future result dataclass design.

#### Pre-release alphas

`2.1.0a1`, `2.1.0a2`, `2.1.0a3` shipped during the State Twin
Completion cycle for internal testing of Phases 1, 2, and 3a
respectively. They were not published to PyPI and are superseded by
this `2.1.0` entry.

---

## [2.0.0] — 2026-04-23

The v2.0 release makes DeFiPy's primitives **agent-ready** without coupling the
library to any specific LLM framework. Three new modules (`defipy.tools`,
`defipy.twin`, and an MCP server demo) ship on top of the 22 primitives already
present in v1.2.0. The library itself remains pure analytics — zero LLM
dependencies, zero network calls at core. See
[`doc/execution/DEFIPY_V2_SHIPPED.md`](./doc/execution/DEFIPY_V2_SHIPPED.md) for
the full retrospective.

### Added

- **`defipy.tools`** — self-describing schemas for a curated set of 10 leaf
  primitives in [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
  format. `get_schemas("mcp")` returns the schema list; `TOOL_REGISTRY` exposes
  the underlying `ToolSpec` entries for programmatic use. Anthropic tool-use and
  OpenAI function-calling formats raise `NotImplementedError` with a v2.1
  message — both formats are derivable from MCP schemas with small wrappers.
- **`defipy.twin`** — the State Twin abstraction:
  - `StateTwinProvider` ABC defines the `snapshot(pool_id) → PoolSnapshot`
    contract
  - `PoolSnapshot` hierarchy (`V2PoolSnapshot`, `V3PoolSnapshot`,
    `BalancerPoolSnapshot`, `StableswapPoolSnapshot`) — protocol-discriminated
    dataclasses
  - `StateTwinBuilder` dispatches on snapshot type to construct the protocol's
    exchange object
  - `MockProvider` ships four canonical synthetic recipes: `eth_dai_v2`,
    `eth_dai_v3`, `eth_dai_balancer_50_50`, `usdc_dai_stableswap_A10`
  - `LiveProvider` stub ships with a stable constructor signature taking
    `rpc_url`; `snapshot()` raises `NotImplementedError` with a v2.1 message
- **MCP server demo** at `python/mcp/defipy_mcp_server.py` — a stdio-transport
  server exposing DeFiPy's tools to Claude Desktop, Claude Code, or any MCP
  client. Dispatches tool calls to primitives running against MockProvider-built
  twins. Per-call receipts log as single-line JSON to stderr. See
  [`python/mcp/README.md`](./python/mcp/README.md) for setup.
- **`[mcp]` install extra** — `pip install defipy[mcp]` adds the `mcp` Python
  SDK for running the MCP server demo. Not needed for library usage.
- **Test coverage** — 125 new tests (52 for `defipy.tools`, 47 for
  `defipy.twin`, 3 packaging smoke tests, 23 MCP server dispatch tests).

### Changed

- **Tagline** — `"Python SDK for DeFi Analytics and Agents"` →
  `"Python SDK for Agentic DeFi"`.
- **`setup.py` `packages=[...]`** fully enumerated. v1.2.0 was missing six
  primitive sub-packages (`comparison`, `execution`, `optimization`,
  `pool_health`, `portfolio`, `risk`) plus two `analytics.*` sub-packages; fresh
  PyPI installs of v1.2.0 were broken on import for several primitives. v2.0.0
  fixes all of it and adds a `test_packaging.py` smoke test as a continuous
  guard against future drift.
- **`install_requires`** pins bumped to match fixed sibling releases:
  - `uniswappy >= 1.7.9` (was unpinned; 1.7.9 removes an erroneous
    `import pytest` that broke non-dev installs)
  - `balancerpy >= 1.1.0` (was unpinned; 1.1.0 fixes missing
    `balancerpy.analytics.risk` sub-package)
  - `stableswappy >= 1.1.0` (was unpinned; 1.1.0 fixes missing
    `stableswappy.analytics.risk` sub-package)

### Deferred to v2.1+

Explicitly noted so expectations stay honest:

- `LiveProvider` implementation (ABC + stub ship in v2.0; on-chain snapshot
  construction is v2.1)
- `defipy.observability` module (stderr receipts are the v2.0 observability
  story; structured event sink with opt-in tracing is v2.1)
- Anthropic tool-use and OpenAI function-calling schema formats
- Planning primitives category (`PlanRebalance`, `PlanZapIn`, `PlanExit`)
- Balancer + Stableswap extensions to `FindBreakEvenPrice`, `FindBreakEvenTime`,
  `CalculateSlippage`
- `AssessLiquidityDepth` (V3 tick-walking) and `DiscoverPools`

### Unchanged from v1.2.0

- All 22 primitives ship with identical behavior. No breaking changes to
  primitive signatures, return dataclasses, or composition patterns.
- Core install (`pip install defipy`) remains dependency-free of chain libraries
  and LLM libraries. `[book]` and `[anvil]` extras unchanged.
- Legacy event-driven agents in `python/prod/agents/` preserved for *Hands-On
  AMMs with Python* chapter 9 readers. Not the go-forward architecture.

---

## [1.2.0] — 2026-04-18

Previous PyPI release. Established the primitives layer as the go-forward
architecture for agentic use. 22 primitives across 7 categories covering
position analysis, pool health, risk, execution, optimization, comparison, and
portfolio aggregation. Cross-protocol siblings (`AnalyzeBalancerPosition`,
`AnalyzeStableswapPosition`, `SimulateBalancerPriceMove`,
`SimulateStableswapPriceMove`) extend core questions across Uniswap V2/V3,
Balancer 2-asset weighted, and Curve-style Stableswap 2-asset pools.

504 tests. Full primitive catalog with LP-question mappings in
`doc/execution/DEFIMIND_TIER1_QUESTIONS.md`.

See the [v1.2.0 git tag](https://github.com/defipy-devs/defipy/releases/tag/v1.2.0)
and GitHub release notes for earlier release history.

---

[2.1.0]: https://github.com/defipy-devs/defipy/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/defipy-devs/defipy/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/defipy-devs/defipy/releases/tag/v1.2.0
