# DeFiPy: Python SDK for Agentic DeFi

DeFiPy is the Python SDK for agentic DeFi — a substrate of composable, typed primitives built on hand-derived AMM math across four families (Uniswap V2, Uniswap V3, Balancer, and Curve-style Stableswap). Most DeFi tools wrap APIs; DeFiPy ships the math. Whether you're building dashboards, simulations, notebook research, or agent-based systems, the primitives compose the same way: stateless construction, exact computation at `.apply()`, structured dataclass results.

Underneath, DeFiPy is modular by protocol:

* [UniswapPy](https://github.com/defipy-devs/uniswappy)
* [BalancerPy](https://github.com/defipy-devs/balancerpy)
* [StableSwapPy](https://github.com/defipy-devs/stableswappy)

For onchain event access and scripting, use [LiveProvider](https://defipy.org/live-provider/) as of v2.1 — it pulls live pool state into the same primitive surface that runs against synthetic recipes. Under the hood it's powered by [Web3Scout](https://github.com/defipy-devs/web3scout); install via the `[chain]` extra (see below).

🔗 SPDX-Anchor: [anchorregistry.ai/AR-2026-YdPXB5g](https://anchorregistry.ai/AR-2026-YdPXB5g)

## 🆕 What's new in v2.1

v2.1 makes the [State Twin](https://defipy.org/twin-concept/) **real**. `LiveProvider` ships for Uniswap V2 and V3 — chain reads compose with every primitive in the library, the same way `MockProvider` recipes do. The "what would happen if?" loop is now local: pull state once, simulate forever, decide before executing.

* **`LiveProvider`** — `provider.snapshot("uniswap_v2:0xADDR")` and `provider.snapshot("uniswap_v3:0xADDR")` build `V2PoolSnapshot` and `V3PoolSnapshot` from real on-chain state. Block pinning is automatic — `"latest"` resolves once at the top of `.snapshot()` and every read inside that snapshot pins to the same block. Pass `block_number=N` for historical reads.
* **Multicall3 batching for V3** — V3 snapshots batch `slot0`, `liquidity`, `fee`, `tickSpacing`, `token0`, `token1`, and block timestamp into one [Multicall3](https://github.com/mds1/multicall) `aggregate3` round trip. Hardcoded canonical Multicall3 address; works on every major EVM chain.
* **`PoolSnapshot` enrichment** — every snapshot now carries `block_number`, `timestamp`, `chain_id` as optional fields. `LiveProvider` populates them from chain reads; `MockProvider` leaves them `None` to honestly signal "synthetic, not chain state."
* **`PoolHealth` ergonomics for V3** — `CheckPoolHealth` now reports `fee_pips` (V3 fee tier in pips, `None` for V2), `tvl_in_token1` (symmetric to existing `tvl_in_token0`), and `tick_current` (V3 current tick, `None` for V2). All additive; no API breakage. `RugSignalReport` gets the new fields transitively.
* **`provider.get_w3()`** — the underlying `web3.Web3` instance is now public, for callers who want to sign transactions or wire LiveProvider into their own broader chain tooling. DeFiPy stays read-only by design; bring your own signing opinion.
* **Fork-and-evaluate worked example** — [`python/examples/state_twin_fork_evaluate.py`](./python/examples/state_twin_fork_evaluate.py) demonstrates the State Twin's multi-scenario reasoning pattern against live mainnet state. Pull a V3 pool snapshot once, fork the twin N ways under price scenarios, run primitives against each fork, aggregate into a recommendation. Walks through the pattern at [defipy.org/fork-evaluate/](https://defipy.org/fork-evaluate/).
* **`[chain]` install extra** — `pip install defipy[chain]` adds `web3scout` and `web3.py` for users who want LiveProvider. Core install (no extras) remains free of any chain or LLM dependencies.
* **`[agentic]` install extra** — `pip install defipy[agentic]` composes `[chain]` and `[mcp]` for the canonical *Python SDK for Agentic DeFi* full-stack install. Equivalent to `pip install defipy[chain,mcp]` but spelled with intent.

V2.1 is a strict superset of v2.0 — every v2.0 primitive, MockProvider recipe, and MCP server pattern works identically. What changes is that the same primitives now run against live chain state without changing call shape.

**What's deferred to v2.2:** Balancer and Stableswap LiveProvider implementations raise `NotImplementedError` pointing at the planned version. V3 tick bitmap walking is also v2.2 work; in v2.1, V3 LiveProvider snapshots cover active-liquidity only — primitives that depend on non-active-tick liquidity (e.g., `AssessLiquidityDepth`) ship in v2.2.

## v2.0 foundations

The State Twin abstraction, agentic primitives, and MCP server pattern shipped in v2.0. v2.1 builds on that surface without changing it:

* **`defipy.tools`** — self-describing schemas for a curated set of 10 leaf primitives, in [Model Context Protocol](https://modelcontextprotocol.io) (MCP) format. Any MCP-compatible client can discover and invoke DeFiPy primitives as tools.
* **`defipy.twin`** — the **State Twin** abstraction. `MockProvider` ships four canonical synthetic pools (V2, V3, Balancer, Stableswap) for notebooks and tests; `LiveProvider` ships chain reads for V2 and V3 in v2.1.
* **MCP server demo** at [`python/mcp/`](./python/mcp/) — a stdio-transport server exposing DeFiPy's tools to Claude Desktop, Claude Code, or any MCP client. Install with `pip install defipy[mcp]` and see the [MCP server README](./python/mcp/README.md) for setup.

### What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard for giving LLMs access to tools and data. With DeFiPy's MCP server running, Claude can answer natural-language LP questions backed by exact math:

> *"Is this V2 pool healthy? Any rug signals?"*

Claude reads the tool descriptions, picks `CheckPoolHealth`, calls it against a twin (synthetic via MockProvider, or live via LiveProvider), receives the typed dataclass result, and synthesizes a response — one that correctly interprets TVL, LP concentration, and activity signals, because the primitives encode the domain, not the LLM.

**Substrate, not agent.** DeFiPy itself has zero LLM dependencies and zero network calls at core. The library is a substrate that agent runtimes (including forthcoming DeFiMind and any third-party project) build on top of.

## 🧩 What DeFiPy offers

**7 [Core primitives](https://defipy.org/core-primitives/)** for cross-protocol pool execution — `Join`, `Swap`, `AddLiquidity`, `RemoveLiquidity`, `SwapDeposit`, `WithdrawSwap`, `LPQuote`. State-mutating operations that work across Uniswap V2/V3, Balancer, and Stableswap through a single abstract interface.

**21 [Agentic primitives](https://defipy.org/agentic-primitives/)** across 7 categories. Each answers a specific LP question with exact math and returns a typed dataclass result:

* **Position analysis** — "Why is my position losing money? What if price moves X%?" PnL decomposition (IL, fees, net result) and price-move scenarios across Uniswap V2/V3, Balancer, and Stableswap. Includes break-even pricing and time-to-breakeven analysis.
* **Pool health** — "Is this pool healthy? Any rug signals?" TVL, LP concentration, activity, threshold-based rug detection, fee-anomaly checks (V2/V3).
* **Risk** — "How exposed am I to a stablecoin depeg? Is my V3 range safe?" Stableswap IL at multiple depeg levels with V2 comparison baseline; V3 tick-range status.
* **Execution** — "What's my actual slippage? Maximum trade size before it exceeds X%? Did a swap get MEV'd?" (V2/V3).
* **Optimization** — Zap-in optimal swap fractions, V3 tick range evaluation, rebalance cost analysis.
* **Comparison** — Side-by-side same-capital analysis across protocols or V3 fee tiers.
* **Portfolio** — Multi-position aggregation with cross-protocol dispatch.

Full primitive catalog with LP-question mappings lives in the [v2 docs](https://defipy.org).

*Legacy event-driven agents (`python/prod/agents/`) are preserved for chapter 9 of* Hands-On AMMs with Python *but are not the go-forward architecture — new agentic behavior composes from primitives running against State Twin twins.*

## 📝 Docs
Visit [**DeFiPy docs**](https://defipy.org) for full documentation. The [LiveProvider page](https://defipy.org/live-provider/) covers the v2.1 chain-reading surface in detail.

## 🔍 Install

DeFiPy requires **Python 3.10 or later**. Install via pip:

```
> pip install defipy
```

The core install is the pure analytics engine — AMM math, primitives, State Twin, and all 21 typed analytics functions. It has **zero web3 dependencies and zero LLM dependencies**. No chain reads, no RPC calls, no MCP. Chain reads come from [Web3Scout](https://github.com/defipy-devs/web3scout) (via the `[chain]` or `[book]` extras); MCP tool serving comes from the `[mcp]` extra. All optional.

> **Note for zsh users (default on macOS):** wrap any install spec with extras in single quotes — `pip install 'defipy[agentic]'` — so zsh doesn't try to glob the brackets. Without the quotes, you'll see `zsh: no matches found`. Bash users can use either form.

### Chain install (LiveProvider — v2.1+)

To use `LiveProvider` for on-chain pool snapshots, install the `[chain]` extra:

```
> pip install 'defipy[chain]'
```

This pulls in `web3scout` (which `LiveProvider` uses internally for ABI loading, contract reads, and token-fetching) plus `web3.py`. With `[chain]` installed, you can construct twins from real chain state:

```python
from defipy.twin import LiveProvider, StateTwinBuilder

provider = LiveProvider("https://eth-mainnet.g.alchemy.com/v2/<key>")
snapshot = provider.snapshot("uniswap_v2:0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc")
lp = StateTwinBuilder().build(snapshot)
```

> **Note:** the `[chain]` extra pins `web3 < 7.0` because `web3scout 0.2.0` depends on `eth_utils.abi.get_abi_input_types`, which was removed in web3 7. If you have web3 7.x installed for other reasons, `pip install 'defipy[chain]'` will downgrade it. Tracking upstream as v2.2 work.

### Agentic install (full LLM + chain stack)

For users building LLM-driven systems against live chain state — the canonical *Python SDK for Agentic DeFi* use case — install the `[agentic]` extra:

```
> pip install 'defipy[agentic]'
```

This composes `[chain]` and `[mcp]` in one step: `web3scout` and `web3.py` for `LiveProvider` chain reads, plus the `mcp` Python SDK for serving DeFiPy's primitives as tools to Claude Desktop, Claude Code, or any MCP-compatible client. Equivalent to `pip install defipy[chain,mcp]` but spelled with intent.

The same `web3 < 7.0` pin from the `[chain]` extra applies.

### MCP install (Claude Desktop / Claude Code demo)

To run the MCP server that exposes DeFiPy's primitives as tools to Claude Desktop, Claude Code, or any MCP-compatible client, install the `[mcp]` extra:

```
> pip install 'defipy[mcp]'
```

This adds the [`mcp`](https://github.com/modelcontextprotocol/python-sdk) Python SDK on top of the core install. The MCP server itself lives at [`python/mcp/defipy_mcp_server.py`](./python/mcp/defipy_mcp_server.py); see [`python/mcp/README.md`](./python/mcp/README.md) for Claude Desktop and Claude Code configuration snippets.

### Book install (chapter 9 agents)

Chapter 9 of *Hands-On AMMs with Python* — *Building Autonomous DeFi Agents* — uses live chain integration via `web3scout`. To run those examples, install the `[book]` extra:

```
> pip install 'defipy[book]'
```

The `[book]` extra carries the same package set as `[chain]` (`web3scout` + `web3`). The split is intent-based — `[chain]` signals production live-state reads via LiveProvider; `[book]` signals textbook chapter 9 use. Either works for either purpose.

### Anvil install (local Foundry workflows)

If you're using `ExecuteScript` or `UniswapScriptHelper` against a local [Anvil](https://book.getfoundry.sh/anvil/) node and don't need the full `web3scout` event-monitoring stack, the lighter `[anvil]` extra just adds `web3.py`:

```
> pip install 'defipy[anvil]'
```

`[book]` and `[chain]` already include everything in `[anvil]`, so users on either of those don't need it separately.

### Source install

To install from source:

```
> git clone https://github.com/defipy-devs/defipy
> cd defipy
> pip install .
```

### System libraries for gmpy2

DeFiPy depends on `gmpy2` for high-precision arithmetic in StableSwap math. On most platforms, `pip` will install `gmpy2` from a prebuilt wheel and no further setup is needed. If the install fails, you may need the GMP, MPFR, and MPC system libraries installed *before* `pip install`:

**macOS (Homebrew):**
```
> brew install gmp mpfr libmpc
```

**Linux (Debian / Ubuntu):**
```
> sudo apt install libgmp-dev libmpfr-dev libmpc-dev
```

See the [gmpy2 installation docs](https://gmpy2.readthedocs.io/en/latest/install.html) for other platforms.

## 🔍 Learning Resources

DeFiPy is accompanied by educational resources for developers and researchers
interested in on-chain analytics and DeFi modeling.

### 📘 Textbook
**_DeFiPy: Python SDK for On-Chain Analytics_**

A comprehensive guide to DeFi analytics, AMM modeling, and simulation.

🔗 **Buy on Amazon:** https://www.amazon.com/dp/B0G3RV5QRB

### 🎓 Course
**On-Chain Analytics Foundations**

A practical course on transforming raw blockchain data into structured
analytics pipelines using Python.

Topics include:

- retrieving blockchain data via Ethereum RPC
- decoding event logs
- analyzing AMM swap events
- building DeFi analytics pipelines

🔗 **Course Page:** https://defipy.thinkific.com/products/courses/foundations

## 🚀 Quick Example (LiveProvider: real chain state + primitives)
--------------------------

The fastest way to see DeFiPy at work — pull a real Uniswap V2 pool's state from mainnet and run a primitive against it. Requires the `[chain]` install extra.

    from defipy import CheckPoolHealth
    from defipy.twin import LiveProvider, StateTwinBuilder
    
    # Pull live state from a real Uniswap V3 pool — USDC/WETH 500bps mainnet
    provider = LiveProvider("https://mainnet.infura.io/v3/d2d6569915ec402b82c9379d033f8b9b")
    snapshot = provider.snapshot(
        "uniswap_v3:0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
    )
    lp = StateTwinBuilder().build(snapshot)
    lp.summary()
    
    # Snapshot carries chain context — block_number, timestamp, chain_id
    print(f"Block: {snapshot.block_number}")
    
    # Run any primitive against the live twin — same call shape as MockProvider
    health = CheckPoolHealth().apply(lp)
    print(f"Fee tier:        {health.fee_pips} pips")
    print(f"TVL (USDC):      {health.tvl_in_token0:,.2f}")
    print(f"TVL (WETH):      {health.tvl_in_token1:,.4f}")
    print(f"Current tick:    {health.tick_current}")
    print(f"Spot price:      {health.spot_price:.6f} WETH/USDC")

The same shape works for V3 — swap `uniswap_v2:` for `uniswap_v3:` and the appropriate pool address (e.g. `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640` for USDC/WETH 500bps). V3 snapshots default to full-range ticks; pass `lwr_tick=N, upr_tick=N` to override. See the [LiveProvider docs](https://defipy.org/live-provider/) for block pinning, the V3 tick-range surface, and the active-liquidity-only caveat.

**No chain access?** Substitute `MockProvider` for `LiveProvider` and pass a recipe name (`"eth_dai_v2"`, `"eth_dai_v3"`, `"eth_dai_balancer_50_50"`, `"usdc_dai_stableswap_A10"`). Same primitive call, same result shape, no network needed:

    from defipy.twin import MockProvider, StateTwinBuilder

    provider = MockProvider()
    lp = StateTwinBuilder().build(provider.snapshot("eth_dai_v2"))
    # ... AnalyzePosition().apply(lp, ...) works identically

The State Twin abstraction is what makes this work: providers know about *sources*, primitives know about *math*, the twin is the canonical handoff between them. Same `lp` shape from a synthetic recipe, a live chain read, or a custom CSV-backed provider — every primitive consumes them identically.

For LLM-driven interaction with these primitives, see the [MCP server README](./python/mcp/README.md).

## 🧱 Quick Example (low-level: Uniswap V3 pool construction)
--------------------------

To construct a Uniswap V3 pool directly (outside MockProvider's canonical recipes and outside LiveProvider's chain reads), you must first create the tokens in the pair using the `ERC20` object. Next, create a liquidity pool (LP) factory using `IFactory` object. Once this is setup, an unlimited amount of LPs can be created; the procedures for such are as follows:

    from defipy import *
    
    # Step 1: Define tokens and parameters
    eth = ERC20("ETH", "0x93")
    tkn = ERC20("TKN", "0x111")
    tick_spacing = 60
    fee = 3000  # 0.3% fee tier
    
    # Step 2: Set up exchange data for V3
    exch_data = UniswapExchangeData(tkn0=eth, tkn1=tkn, symbol="LP", address="0x811", version='V3', tick_spacing=tick_spacing, fee=fee)
    
    # Step 3: Initialize factory
    factory = UniswapFactory("ETH pool factory", "0x2")
    
    # Step 4: Deploy pool
    lp = factory.deploy(exch_data)
    
    # Step 5: Add initial liquidity within tick range
    lwr_tick = UniV3Utils.getMinTick(tick_spacing)
    upr_tick = UniV3Utils.getMaxTick(tick_spacing)
    join = Join()
    join.apply(lp, "user", 1000, 10000, lwr_tick, upr_tick)
    
    # Step 6: Perform swap
    swap = Swap()
    out = swap.apply(lp, tkn, "user", 10)
    
    # Check reserves and liquidity
    lp.summary()

    # OUTPUT:
    Exchange ETH-TKN (LP)
    Real Reserves:   ETH = 999.0039930189599, TKN = 10010.0
    Gross Liquidity: 3162.277660168379  

## 🧪 Tests

DeFiPy ships ~686 tests across primitives, tools, twin, packaging, and the MCP server dispatch layer. Run the full suite:

    pytest python/test/ -v

Expect ~686 passed and 11 skipped — the skipped tests are the live-RPC suites, gated by the `DEFIPY_LIVE_RPC` environment variable. They run against real mainnet pools and aren't part of the default suite to keep CI deterministic.

Run just the primitive suite (no MCP or twin dependencies):

    pytest python/test/primitives/ -v

To run the opt-in live-RPC tests, set `DEFIPY_LIVE_RPC` to a mainnet RPC URL:

    DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key> pytest -m live_rpc -v

## License
Licensed under the Apache License, Version 2.0.  
See [LICENSE](./LICENSE) and [NOTICE](./NOTICE) for details.  
Portions of this project may include code from third-party projects under compatible open-source licenses.
