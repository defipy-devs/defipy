# DeFiPy: Python SDK for DeFi Analytics and Agents

DeFiPy is the first unified Python SDK for DeFi analytics, simulation, and autonomous agents. Built with modularity in mind, DeFiPy lets you isolate and extend your analytics by protocol using:

* [UniswapPy](https://github.com/defipy-devs/uniswappy)
* [BalancerPy](https://github.com/defipy-devs/balancerpy)
* [StableSwapPy](https://github.com/defipy-devs/stableswappy)

For onchain event access and scripting, pair it with [Web3Scout](https://github.com/defipy-devs/web3scout) — a companion tool for [decoding pool events](https://defipy.readthedocs.io/en/latest/onchain/pool_events.html) and [interfacing with Solidity contracts](https://defipy.readthedocs.io/en/latest/onchain/testnet_sim_univ2.html). Whether you’re building dashboards, simulations, or agent-based trading systems, DeFiPy + Web3Scout deliver a uniquely powerful toolset — unlike anything else in the ecosystem.

SPDX-Anchor: https://anchorregistry.ai/AR-2026-Pvdp0W5

## 📝 Docs
Visit [**DeFiPy docs**](https://defipy.org) for full documentation 

## 🔍 Install
Must first install gmpy2 python package to handle the precision within the StableSwap protocol (requires CPython 3.7 or above). To install the latest release with pip:
```
> pip install gmpy2
```
Also, in many cases will need to have required libraries (GMP, MPFR and MPC) already installed on your system, see [gmpy2 installation docs](https://gmpy2.readthedocs.io/en/latest/install.html) for more info. Once setup, install the latest release of DeFiPy with pip:
```
> git clone https://github.com/defipy-devs/defipy
> pip install .
```
or
```
> pip install defipy
```

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

## 🚀 Quick Example (Uniswap V3)
--------------------------

To setup a liquidity pool, you must first create the tokens in the pair using the `ERC20` object. Next, create a liquidity pool (LP) factory using `IFactory` object. Once this is setup, an unlimited amount of LPs can be created; the procedures for such are as follows:

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

## License
Licensed under the Apache License, Version 2.0.  
See [LICENSE](./LICENSE) and [NOTICE](./NOTICE) for details.  
Portions of this project may include code from third-party projects under compatible open-source licenses.
