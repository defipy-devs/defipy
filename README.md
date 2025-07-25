# DeFiPy: Python SDK for DeFi Analytics and Agents

DeFiPy is the first unified Python SDK for DeFi analytics, simulation, and autonomous agents. Built with modularity in mind, DeFiPy lets you isolate and extend your analytics by protocol using:

* [UniswapPy](https://github.com/defipy-devs/uniswappy)
* [BalancerPy](https://github.com/defipy-devs/balancerpy)
* [StableSwapPy](https://github.com/defipy-devs/stableswappy)

For onchain event access and scripting, pair it with [Web3Scout](https://github.com/defipy-devs/web3scout) — a companion tool for [decoding pool events](https://defipy.readthedocs.io/en/latest/onchain/pool_events.html) and [interfacing with Solidity contracts](https://defipy.readthedocs.io/en/latest/onchain/testnet_sim_univ2.html). Whether you’re building dashboards, simulations, or agent-based trading systems, DeFiPy + Web3Scout deliver a uniquely powerful toolset — unlike anything else in the ecosystem.

## Docs
Visit [DeFiPy docs](https://defipy.org) for full documentation with walk-through tutorials

## Install
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

Uniswap V2 Example
--------------------------

To setup a liquidity pool, you must first create the tokens in the pair using the `ERC20` object. Next, create a liquidity pool (LP) factory using `IFactory` object. Once this is setup, an unlimited amount of LPs can be created; the procedures for such are as follows:


    from defipy import *
    
    # Step 1: Define tokens
    tkn = ERC20("TKN", "0x111")
    eth = ERC20("ETH", "0x999")
    
    # Step 2:  Initialize factory
    factory = UniswapFactory("ETH pool factory", "0x2")
    
    # Step 3: Set up exchange data for V2
    exch_data = UniswapExchangeData(tkn0=eth, tkn1=tkn, symbol="LP", address="0x3")
    
    # Step 4: Deploy pool
    lp = factory.deploy(exch_data)
    
    # Step 5: Add initial liquidity
    join = Join()
    join.apply(lp, "user", 1000, 10000)
    
    # Step 6: Perform swap
    swap = Swap()
    out = swap.apply(lp, tkn, "user", 10)
    
    # Check reserves and liquidity
    lp.summary()    

    # OUTPUT:
    Exchange ETH-TKN (LP)
    Reserves: ETH = 999.00399301896, TKN = 10010.0
    Liquidity: 3162.2776601683795 

Uniswap V3 Example
--------------------------

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
    
Balancer Example
--------------------------   

    from defipy import *
    
    # Step 1: Define tokens
    dai = ERC20("DAI", "0x111")
    usdc = ERC20("USDC", "0x999")
    
    # Step 2: Deposit token amounts
    dai.deposit(None, 10000)
    usdc.deposit(None, 20000)
    
    # Step 3: Setup vault
    vault = BalancerVault()
    vault.add_token(dai, 10)  # Denormalized weight for DAI
    vault.add_token(usdc, 40)  # Denormalized weight for WETH
    
    # Step 4: Set up exchange data for Balancer
    exch_data = BalancerExchangeData(vault=vault, symbol="BSP", address="0x3")
    
    # Step 5: Initialize factor for Balancer
    bfactory = BalancerFactory("WETH pool factory", "0x2")
    
    # Step 6: Deploy pool
    lp = bfactory.deploy(exch_data)
    
    # Step 7: Join pool with initial liquidity
    join = Join()
    join.apply(lp, "user", 100) # Issue 100 pool shares
    
    # Step 8: Perform swap
    swap = Swap(Proc.SWAPIN)
    out = swap.apply(lp, dai, usdc, "user", 10)
    
    # Check reserves and liquidity
    lp.summary()

    # OUTPUT:
    Balancer Exchange: DAI-USDC (BSP)
    Reserves: DAI = 9979.92478694547, USDC = 20010
    Weights: DAI = 0.2, USDC = 0.8
    Pool Shares: 100 
    
StableSwap Example
--------------------------   

    from defipy import *
    
    # Step 1: Define stablecoins and parameters
    dai = ERC20("DAI", "0x111", 18)
    usdc = ERC20("USDC", "0x222", 6)
    AMPL_COEFF = 2000
    
    # Step 2: Deposit token amounts
    dai.deposit(None, 10000)
    usdc.deposit(None, 20000)
    
    # Step 3: Setup Stableswap vault and add tokens
    sgrp = StableswapVault()
    sgrp.add_token(dai)
    sgrp.add_token(usdc)
    
    # Step 4: Set up exchange data for Stableswap
    exch_data = StableswapExchangeData(vault = sgrp, symbol="LP", address="0x011")
    
    # Step 5: Initialize factor for Balancer
    factory = StableswapFactory("Stableswap factory", "0x2")
    
    # Step 6: Deploy pool
    lp = factory.deploy(exch_data)
    
    # Step 7: Join pool with initial liquidity
    join = Join()
    join.apply(lp, "user", AMPL_COEFF)
    
    # Step 8: Perform swap
    swap = Swap()
    out = swap.apply(lp, dai, usdc, "user", 10)
    
    # Check reserves and liquidity
    lp.summary()

    # OUTPUT:
    Stableswap Exchange: DAI-USDC (LP)
    Reserves: DAI = 10010, USDC = 19989.996791
    Liquidity: 29999.063056285642 

## 0x Quant Terminal

This application utilizes the 0x API to produce a mock Uniswap pool which allows end-users to stress test
the limitations of a Uniswap pool setup using live price feeds from [0x API](https://0x.org); for backend setup, see 
[notebook](https://github.com/defipy-devs/defipy/blob/main/notebooks/quant_terminal.ipynb) 

Click [dashboard.defipy.org](https://dashboard.defipy.org/) for live link; for more detail see 
[README](https://github.com/defipy-devs/defipy/tree/main/python/application/quant_terminal#readme) 

![plot](./doc/quant_terminal/screenshot.png)

### Run application locally  

```
> bokeh serve --show python/application/quant_terminal/bokeh_server.py
```

## License
Licensed under the Apache License, Version 2.0.  
See [LICENSE](./LICENSE) and [NOTICE](./NOTICE) for details.  
Portions of this project may include code from third-party projects under compatible open-source licenses.