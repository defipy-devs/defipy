# Changelog

All notable changes to DeFiPy are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Earlier releases are tracked in [git tags](https://github.com/defipy-devs/defipy/tags)
and the GitHub releases page.

---

## [2.1.0a2] — 2026-05-06 (UNRELEASED)

Second alpha of the v2.1 "State Twin Completion" cycle. Phase 2 ships V3
LiveProvider with Multicall3 batching and PoolSnapshot enrichment.

### Added

- **V3 LiveProvider** — `provider.snapshot("uniswap_v3:0xADDR")` returns a
  `V3PoolSnapshot` with reserves, ticks, fee, tickSpacing populated from
  on-chain reads. Active-liquidity only — tick bitmap walking is deferred to
  v2.1.x or pairing with `AssessLiquidityDepth`. Optional
  `lwr_tick` / `upr_tick` kwargs override the full-range default for callers
  who want a tight position.
- **Multicall3 batching** for V3 reads. Single round trip for token0,
  token1, slot0, liquidity, fee, tickSpacing, and block timestamp.
  Hardcoded canonical Multicall3 address
  (`0xcA11bde05977b3631167028862bE2a173976CA11`) — same on every major
  EVM chain.
- **PoolSnapshot enrichment** — `block_number`, `timestamp`, `chain_id`
  fields added to the base `PoolSnapshot` class. Optional, default `None`.
  LiveProvider populates from chain reads (V2 retrofit + V3 native);
  MockProvider snapshots stay `None` to honestly signal "synthetic, not a
  chain read."

### Changed

- **Phase 1 V2 LiveProvider retrofit** — V2 snapshots now carry the three
  enrichment fields. One extra `eth_getBlockByNumber` round trip per V2
  snapshot vs Phase 1; acceptable for V2 (no multicall).
- **Test infrastructure** — `_fake_rpc.py` extended with `V3PoolSpec`,
  `_V3PoolFunctions`, `_MulticallFunctions`. V2 fixture surface unchanged;
  all Phase 1 V2 tests pass without modification.

### Notes

- Tick bitmap walking explicitly out of scope. Primitives that need
  liquidity at non-active ticks (e.g., `AssessLiquidityDepth` when it
  ships) will need additional reads. Active-liquidity primitives
  (`AnalyzePosition`, `SimulatePriceMove`, `CheckPoolHealth`,
  `CalculateSlippage`, `DetectRugSignals`) work against V3 LiveProvider
  twins.
- `[chain]` extra still pins `web3 < 7.0` due to web3scout's reliance on
  `eth_utils.abi.get_abi_input_types` (web3 6 only). Tracking upstream as
  v2.2 work.

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

[2.0.0]: https://github.com/defipy-devs/defipy/compare/v1.2.0...v2.0.0
[1.2.0]: https://github.com/defipy-devs/defipy/releases/tag/v1.2.0
