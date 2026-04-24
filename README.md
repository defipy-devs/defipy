# DeFiPy: Python SDK for Agentic DeFi

DeFiPy is the Python SDK for agentic DeFi — a substrate of composable, typed primitives built on hand-derived AMM math across four families (Uniswap V2, Uniswap V3, Balancer, and Curve-style Stableswap). Most DeFi tools wrap APIs; DeFiPy ships the math. Whether you're building dashboards, simulations, notebook research, or agent-based systems, the primitives compose the same way: stateless construction, exact computation at `.apply()`, structured dataclass results.

Underneath, DeFiPy is modular by protocol:

* [UniswapPy](https://github.com/defipy-devs/uniswappy)
* [BalancerPy](https://github.com/defipy-devs/balancerpy)
* [StableSwapPy](https://github.com/defipy-devs/stableswappy)

For onchain event access and scripting, pair it with [Web3Scout](https://github.com/defipy-devs/web3scout) — a companion tool for [decoding pool events](https://defipy.readthedocs.io/en/latest/onchain/pool_events.html) and [interfacing with Solidity contracts](https://defipy.readthedocs.io/en/latest/onchain/testnet_sim_univ2.html).

🔗 SPDX-Anchor: [anchorregistry.ai/AR-2026-YdPXB5g](https://anchorregistry.ai/AR-2026-YdPXB5g)

## 🆕 What's new in v2.0

v2.0 makes DeFiPy's primitives **agent-ready** without coupling the library to any specific LLM framework. Three new modules land alongside the existing 22 primitives:

* **`defipy.tools`** — self-describing schemas for a curated set of 10 leaf primitives, in [Model Context Protocol](https://modelcontextprotocol.io) (MCP) format. Any MCP-compatible client can discover and invoke DeFiPy primitives as tools.
* **`defipy.twin`** — the **State Twin** abstraction. `MockProvider` ships four canonical synthetic pools (V2, V3, Balancer, Stableswap) for notebooks and tests; `LiveProvider` (chain reads) lands in v2.1.
* **MCP server demo** at [`python/mcp/`](./python/mcp/) — a stdio-transport server exposing DeFiPy's tools to Claude Desktop, Claude Code, or any MCP client. Install with `pip install defipy[mcp]` and see the [MCP server README](./python/mcp/README.md) for setup.

### What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard for giving LLMs access to tools and data. With DeFiPy's MCP server running, Claude can answer natural-language LP questions backed by exact math:

> *"Is the ETH/DAI V2 pool healthy? Any rug signals?"*

Claude reads the tool descriptions, picks `CheckPoolHealth`, calls it against a MockProvider twin, receives the typed dataclass result, and synthesizes a response — one that correctly interprets TVL, LP concentration, and activity signals, because the primitives encode the domain, not the LLM.

**Substrate, not agent.** DeFiPy itself has zero LLM dependencies and zero network calls at core. The library is a substrate that agent runtimes (including forthcoming DeFiMind and any third-party project) build on top of.

## 🧩 What DeFiPy offers

22 primitives across 7 categories. Each answers a specific LP question with exact math and returns a typed dataclass result:

* **Position analysis** — "Why is my position losing money? What if price moves X%?" PnL decomposition (IL, fees, net result) and price-move scenarios across Uniswap V2/V3, Balancer, and Stableswap. Includes break-even pricing and time-to-breakeven analysis.
* **Pool health** — "Is this pool healthy? Any rug signals?" TVL, LP concentration, activity, threshold-based rug detection, fee-anomaly checks (V2/V3).
* **Risk** — "How exposed am I to a stablecoin depeg? Is my V3 range safe?" Stableswap IL at multiple depeg levels with V2 comparison baseline; V3 tick-range status.
* **Execution** — "What's my actual slippage? Maximum trade size before it exceeds X%? Did a swap get MEV'd?" (V2/V3).
* **Optimization** — Zap-in optimal swap fractions, V3 tick range evaluation, rebalance cost analysis.
* **Comparison** — Side-by-side same-capital analysis across protocols or V3 fee tiers.
* **Portfolio** — Multi-position aggregation with cross-protocol dispatch.

Full primitive catalog with LP-question mappings lives in the [v2 docs](https://defipy.org).

*Legacy event-driven agents (`python/prod/agents/`) are preserved for chapter 9 of* Hands-On AMMs with Python *but are not the go-forward architecture — new agentic behavior composes from primitives.*

## 📝 Docs
Visit [**DeFiPy docs**](https://defipy.org) for full documentation 

## 🔍 Install

DeFiPy requires **Python 3.10 or later**. Install via pip:

```
> pip install defipy
```

### MCP install (Claude Desktop / Claude Code demo)

To run the MCP server that exposes DeFiPy's primitives as tools to Claude Desktop, Claude Code, or any MCP-compatible client, install the `[mcp]` extra:

```
> pip install defipy[mcp]
```

This adds the [`mcp`](https://github.com/modelcontextprotocol/python-sdk) Python SDK on top of the core install. The MCP server itself lives at [`python/mcp/defipy_mcp_server.py`](./python/mcp/defipy_mcp_server.py); see [`python/mcp/README.md`](./python/mcp/README.md) for Claude Desktop and Claude Code configuration snippets.

### Book install (chapter 9 agents)

Chapter 9 of *Hands-On AMMs with Python* — *Building Autonomous DeFi Agents* — uses live chain integration via `web3scout`. To run those examples, install the `[book]` extra:

```
> pip install defipy[book]
```

This pulls in `web3scout` on top of the core install, enabling the chain event monitoring, ABI loading, and token-fetching utilities that chapter 9's agents require. Other chapters work with the core install alone.

### Anvil install (local Foundry workflows)

If you're using `ExecuteScript` or `UniswapScriptHelper` against a local [Anvil](https://book.getfoundry.sh/anvil/) node and don't need the full `web3scout` event-monitoring stack, the lighter `[anvil]` extra just adds `web3.py`:

```
> pip install defipy[anvil]
```

`[book]` already includes everything in `[anvil]`, so book readers only need `[book]`.

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

## 🚀 Quick Example (high-level: primitives + State Twin)
--------------------------

The fastest way to see DeFiPy at work. `MockProvider` ships canonical synthetic pools; `StateTwinBuilder` turns a snapshot into a usable exchange object; any primitive runs against it.

    from defipy import AnalyzePosition
    from defipy.twin import MockProvider, StateTwinBuilder

    # Build a synthetic ETH/DAI Uniswap V2 pool
    provider = MockProvider()
    builder = StateTwinBuilder()
    lp = builder.build(provider.snapshot("eth_dai_v2"))

    # Ask the primitive: why is this LP position gaining or losing money?
    result = AnalyzePosition().apply(
        lp,
        lp_init_amt=1.0,
        entry_x_amt=1000,
        entry_y_amt=100000,
    )

    print(f"Diagnosis:   {result.diagnosis}")
    print(f"Net PnL:     {result.net_pnl:.4f}")
    print(f"IL %:        {result.il_percentage:.4f}")
    print(f"Current val: {result.current_value:.4f}")

At-entry state with 100% pool ownership yields `diagnosis=il_dominant` with zero IL and fees. Other recipes (`eth_dai_v3`, `eth_dai_balancer_50_50`, `usdc_dai_stableswap_A10`) exercise the other three AMM families; every curated primitive works against them.

For LLM-driven interaction with these primitives, see the [MCP server README](./python/mcp/README.md).

## 🧱 Quick Example (low-level: Uniswap V3 pool construction)
--------------------------

To construct a Uniswap V3 pool directly (outside MockProvider's canonical recipes), you must first create the tokens in the pair using the `ERC20` object. Next, create a liquidity pool (LP) factory using `IFactory` object. Once this is setup, an unlimited amount of LPs can be created; the procedures for such are as follows:

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

DeFiPy ships 629 tests across primitives, tools, twin, packaging, and the MCP server dispatch layer. Run the full suite:

    pytest python/test/ -v

Run just the primitive suite (504 tests, no MCP or twin dependencies):

    pytest python/test/primitives/ -v

## License
Licensed under the Apache License, Version 2.0.  
See [LICENSE](./LICENSE) and [NOTICE](./NOTICE) for details.  
Portions of this project may include code from third-party projects under compatible open-source licenses.
