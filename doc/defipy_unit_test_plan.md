# DeFiPy Unit Test Suite — Full Plan for Claude Code

## Context

Three repos: `uniswappy`, `balancerpy`, `stableswappy`. All located at `~/repos/`.

Tier 1 precision fixes have already been applied on `main` (to be moved to branch before test work begins). Tests must be pure offline — no Web3, no live nodes.

---

## Prerequisites

### Branch setup (run before anything else)
```bash
cd ~/repos/uniswappy && git checkout -b feature/unit-tests
cd ~/repos/balancerpy && git checkout -b feature/unit-tests
cd ~/repos/stableswappy && git checkout -b feature/unit-tests
```

---

## Phase 0 — Test Infrastructure (all 3 repos)

### Create `conftest.py` at each repo root

Replaces the fragile `sys.path.append(os.getcwd().replace(TEST_PATH,""))` pattern in existing tests.

**Files:**
- `/Users/ian_moore/repos/uniswappy/conftest.py`
- `/Users/ian_moore/repos/balancerpy/conftest.py`
- `/Users/ian_moore/repos/stableswappy/conftest.py`

All three identical:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

### Create test directory trees

#### uniswappy — extend existing structure
```
python/test/
  conftest.py                        (same content as root conftest)
  v2/
    process/
      join/                          __init__.py  +  test_join.py
      deposit/                       __init__.py  +  test_swap_deposit.py
      withdraw/                      __init__.py  +  test_withdraw_swap.py
      liquidity/                     __init__.py  +  test_add_liquidity.py
      swap/                          (already exists — leave alone)
      drain_lp/                      (already exists — leave alone)
    cpt/
      index/                         __init__.py  +  test_rebase_index_token.py
                                                  +  test_settlement_lp_token.py
                                                  +  test_round_trip.py
      quote/                         (already exists — add test_lp_quote.py)
    analytics/                       __init__.py  +  test_impermanent_loss.py
  v3/
    process/                         __init__.py  +  test_v3_swap.py
```

#### balancerpy — build from scratch
```
python/test/
  __init__.py
  conftest.py
  process/
    __init__.py
    test_join.py
    test_swap.py
    test_liquidity.py
  quote/
    __init__.py
    test_cwp_quote.py
  math/
    __init__.py
    test_balancer_math.py
```

#### stableswappy — build from scratch
```
python/test/
  __init__.py
  conftest.py
  process/
    __init__.py
    test_join.py
    test_swap.py
    test_liquidity.py
  math/
    __init__.py
    test_stableswap_math.py
```

---

## Phase 1 — uniswappy Tests (~40 tests)

### Import pattern (use in every test file)
```python
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])
from python.prod.erc import ERC20
from python.prod.cpt.factory import UniswapFactory
from python.prod.utils.data import UniswapExchangeData
```

### Standard V2 pool fixture (reuse across all V2 tests)
```python
USER = 'user0'
ETH_AMT = 1000
DAI_AMT = 100000   # implied price = 100 DAI per ETH

def setup_v2_lp(eth_amt=ETH_AMT, dai_amt=DAI_AMT):
    eth = ERC20("ETH", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory("ETH pool factory", "0x2")
    exch_data = UniswapExchangeData(tkn0=eth, tkn1=dai, symbol="LP", address="0x011")
    lp = factory.deploy(exch_data)
    lp.add_liquidity(USER, eth_amt, dai_amt, eth_amt, dai_amt)
    return lp, eth, dai
```

---

### `python/test/v2/process/join/test_join.py`

Additional imports:
```python
from python.prod.process.join import Join
```

Tests:
- `test_join_initial_reserves` — after `add_liquidity`, `lp.get_reserve(eth) == ETH_AMT` and `lp.get_reserve(dai) == DAI_AMT`
- `test_join_lp_minted` — `lp.total_supply > 0` after join
- `test_join_proportional` — add liquidity again at same ratio, check reserves scale proportionally
- `test_join_lp_attribution` — `lp.liquidity_providers[USER] > 0`

---

### `python/test/v2/process/deposit/test_swap_deposit.py`

Additional imports:
```python
from python.prod.process.deposit import SwapDeposit
```

Tests:
- `test_swap_deposit_increases_liquidity` — `SwapDeposit().apply(lp, eth, USER, 10)` increases `lp.total_supply`
- `test_swap_deposit_returns_lp_amount` — return value `> 0`
- `test_swap_deposit_eth_reserve_change` — ETH reserve increases after ETH deposit
- `test_swap_deposit_dai_direction` — same but depositing DAI

---

### `python/test/v2/process/withdraw/test_withdraw_swap.py`

Additional imports:
```python
from python.prod.process.deposit import SwapDeposit
from python.prod.process.withdraw import WithdrawSwap
```

Tests:
- `test_withdraw_decreases_liquidity` — `total_supply` decreases after `WithdrawSwap`
- `test_withdraw_returns_token` — return value `> 0`
- `test_withdraw_eth_reserve_change` — ETH reserve decreases after ETH withdrawal
- `test_withdraw_roundtrip` — deposit X ETH, then withdraw the resulting LP amount, recover close to X ETH (within fee tolerance ~0.3%)

---

### `python/test/v2/process/liquidity/test_add_liquidity.py`

Additional imports:
```python
from python.prod.process.liquidity import AddLiquidity, RemoveLiquidity
```

Tests:
- `test_add_liquidity_single_token` — `AddLiquidity().apply(lp, eth, USER, 10)` increases `lp.total_supply`
- `test_add_liquidity_reserve_increases` — ETH reserve increases after ETH-only add
- `test_remove_liquidity_single_token` — `RemoveLiquidity().apply(lp, dai, USER, 1000)` decreases DAI reserve
- `test_add_then_remove_approx_neutral` — add then remove same amount, ending reserves within 1% of start

---

### `python/test/v2/cpt/quote/test_lp_quote.py`

Additional imports:
```python
from python.prod.cpt.quote import LPQuote
```

Tests:
- `test_get_price_eth` — `LPQuote().get_price(lp, eth)` ≈ `100.0` (DAI per ETH)
- `test_get_price_dai` — `LPQuote().get_price(lp, dai)` ≈ `0.01` (ETH per DAI)
- `test_get_reserve_eth` — `LPQuote().get_reserve(lp, eth) == ETH_AMT`
- `test_get_reserve_dai` — `LPQuote().get_reserve(lp, dai) == DAI_AMT`
- `test_get_amount_eth_to_dai` — `LPQuote().get_amount(lp, eth, 100)` ≈ `10000`
- `test_get_amount_from_lp` — `LPQuote(False).get_amount_from_lp(lp, eth, some_lp_amt) > 0`
- `test_get_lp_from_amount` — `LPQuote(False).get_lp_from_amount(lp, eth, 100) > 0`
- `test_round_trip_lp` — `get_lp_from_amount` then `get_amount_from_lp` recovers original within 0.1%

---

### `python/test/v2/cpt/index/test_rebase_index_token.py`

Additional imports:
```python
from python.prod.cpt.index import RebaseIndexToken
```

Tests:
- `test_rebase_positive` — `RebaseIndexToken().apply(lp, eth, some_lp_amount) > 0`
- `test_rebase_scales_with_input` — doubling `lp_amount` roughly doubles output (within 1%)
- `test_rebase_zero_input` — `apply(lp, eth, 0) == 0`
- `test_rebase_dai_direction` — `apply(lp, dai, some_lp_amount) > 0`

---

### `python/test/v2/cpt/index/test_settlement_lp_token.py`

Additional imports:
```python
from python.prod.cpt.index import SettlementLPToken
```

Tests:
- `test_settlement_positive` — `SettlementLPToken().apply(lp, eth, 100) > 0`
- `test_settlement_scales_with_input` — doubling token amount roughly doubles LP output (within 1%)
- `test_settlement_zero_input` — `apply(lp, eth, 0) == 0`
- `test_settlement_dai_direction` — `apply(lp, dai, 10000) > 0`

---

### `python/test/v2/cpt/index/test_round_trip.py`

**These are the mathematical identity tests — the crown jewels of the index module.**

Additional imports:
```python
from python.prod.cpt.index import RebaseIndexToken, SettlementLPToken
```

Tests:
- `test_lp_to_token_to_lp_eth` — start with `lp_amount` → `RebaseIndexToken` → `token_amount` → `SettlementLPToken` → `lp_amount2`; assert `abs(lp_amount - lp_amount2) / lp_amount < 0.001`
- `test_token_to_lp_to_token_eth` — start with `token_amount` → `SettlementLPToken` → `lp_amount` → `RebaseIndexToken` → `token_amount2`; assert `abs(token_amount - token_amount2) / token_amount < 0.001`
- `test_lp_to_token_to_lp_dai` — same round-trip in DAI direction
- `test_token_to_lp_to_token_dai` — same inverse round-trip in DAI direction

---

### `python/test/v2/analytics/test_impermanent_loss.py`

Additional imports:
```python
from python.prod.process.deposit import SwapDeposit
from python.prod.process.swap import Swap
from python.prod.analytics.risk import UniswapImpLoss
```

Tests:
- `test_il_zero_at_entry` — IL == 0 immediately after taking position (no price change yet)
- `test_il_negative_after_price_move` — swap large amount to move price, then `apply() < 0`
- `test_il_worse_with_larger_price_move` — bigger swap → more negative IL
- `test_hold_value_equals_position_at_entry` — `hold_value(eth) ≈ current_position_value(eth)` immediately after deposit
- `test_current_position_value_positive` — `current_position_value(eth) > 0`
- `test_fees_mode_returns_float` — `apply(fees=True)` returns a float without raising

---

### `python/test/v3/process/test_v3_swap.py`

Reuse existing utilities:
```python
from python.test.v3.utilities import (
    encodePriceSqrt, getMinTick, getMaxTick, FeeAmount, TICK_SPACINGS
)
from python.prod.cpt.factory import UniswapFactory
from python.prod.erc import ERC20
from python.prod.utils.data import UniswapExchangeData
from python.prod.cpt.quote import LPQuote
from python.prod.cpt.index import RebaseIndexToken, SettlementLPToken
```

Standard V3 fixture:
```python
def setup_v3_lp():
    fee = FeeAmount.MEDIUM
    tick_spacing = TICK_SPACINGS[FeeAmount.MEDIUM]
    usdc = ERC20("USDC", "0x09")
    dai = ERC20("DAI", "0x111")
    factory = UniswapFactory("TEST pool factory", "0x2")
    exch_data = UniswapExchangeData(
        tkn0=usdc, tkn1=dai, symbol="LP", address="0x011",
        version=UniswapExchangeData.VERSION_V3,
        precision=UniswapExchangeData.TYPE_GWEI,
        tick_spacing=tick_spacing, fee=fee
    )
    lp = factory.deploy(exch_data)
    lp.initialize(encodePriceSqrt(1, 1))
    lwr = getMinTick(tick_spacing)
    upr = getMaxTick(tick_spacing)
    lp.mint(USER, lwr, upr, 3161)
    return lp, usdc, dai, lwr, upr
```

Tests:
- `test_v3_mint_virtual_reserves_positive` — both virtual reserves `> 0` after mint
- `test_v3_swap_token0_in` — swap token0 in, token1 out, output `> 0`
- `test_v3_swap_token1_in` — swap token1 in, token0 out, output `> 0`
- `test_v3_lp_quote_get_amount` — `LPQuote().get_amount(lp, usdc, amt, lwr, upr) > 0`
- `test_v3_settlement_positive` — `SettlementLPToken().apply(lp, usdc, amt, lwr, upr) > 0`
- `test_v3_rebase_positive` — `RebaseIndexToken().apply(lp, usdc, lp_amt, lwr, upr) > 0`

---

## Phase 2 — balancerpy Tests (~25 tests)

### Import pattern (use in every test file)
```python
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])
from python.prod.erc import ERC20
from python.prod.vault import BalancerVault
from python.prod.cwpt.factory import BalancerFactory
from python.prod.utils.data import BalancerExchangeData
from python.prod.process.join import Join
from python.prod.process.swap import Swap
from python.prod.process.liquidity import AddLiquidity, RemoveLiquidity
from python.prod.quote import CWPQuote
```

### Standard Balancer pool fixture
```python
USER = 'user0'

def setup_balancer_lp():
    eth = ERC20("ETH", "0x01")
    eth.deposit(USER, 10)
    dai = ERC20("DAI", "0x02")
    dai.deposit(USER, 10000)

    vault = BalancerVault()
    vault.add_token(eth, 0.5)    # 50/50 pool
    vault.add_token(dai, 0.5)

    factory = BalancerFactory("Balancer factory", "0x3")
    exch_data = BalancerExchangeData(vault=vault, symbol="BPT", address="0x011")
    lp = factory.deploy(exch_data)
    Join().apply(lp, USER, 100)  # 100 initial pool shares
    return lp, eth, dai
```

---

### `python/test/process/test_join.py`

Tests:
- `test_join_sets_pool_shares` — `lp.pool_shares == 100`
- `test_join_sets_eth_reserve` — `lp.get_reserve(eth) == 10`
- `test_join_sets_dai_reserve` — `lp.get_reserve(dai) == 10000`
- `test_join_provider_credited` — `lp.pool_providers[USER] > 0`
- `test_join_already_joined_raises` — second `Join().apply` raises `AssertionError`

---

### `python/test/process/test_swap.py`

Tests:
- `test_swap_exact_in_eth_for_dai` — swap ETH in, `out['tkn_out_amt'] > 0`
- `test_swap_exact_in_eth_reserve_increases` — ETH reserve increases after ETH in
- `test_swap_exact_in_dai_reserve_decreases` — DAI reserve decreases after ETH→DAI swap
- `test_swap_exact_in_fee_positive` — `out['tkn_in_fee'] > 0`
- `test_swap_exact_out_dai_for_eth` — reverse direction works, returns `tkn_in_amt > 0`
- `test_swap_price_impact` — larger swap input → proportionally less output (worse price)
- `test_get_price` — `lp.get_price(eth, dai) > 0`

---

### `python/test/process/test_liquidity.py`

Tests:
- `test_add_liquidity_by_token_increases_shares` — `AddLiquidity().apply(lp, eth, USER, 1)` increases `lp.pool_shares`
- `test_add_liquidity_eth_reserve_increases` — ETH reserve increases after ETH deposit
- `test_add_liquidity_returns_fee` — returned dict contains `tkn_in_fee > 0`
- `test_add_liquidity_by_shares` — `AddLiquidity(kind=Proc.ADDSHARES).apply(lp, eth, USER, 5)` increases reserves
- `test_remove_liquidity_by_token` — `RemoveLiquidity().apply(lp, eth, USER, 1)` decreases reserves
- `test_remove_liquidity_by_shares` — `RemoveLiquidity(kind=Proc.REMOVESHARES).apply(lp, eth, USER, 5)` returns token amount
- `test_exit_pool_all_assets` — `lp.exit_pool(50, USER)` returns dict with amounts for both ETH and DAI

---

### `python/test/quote/test_cwp_quote.py`

Tests:
- `test_get_amount_from_shares_positive` — `CWPQuote().get_amount_from_shares(lp, eth, 10) > 0`
- `test_get_shares_from_amount_positive` — `CWPQuote().get_shares_from_amount(lp, eth, 1) > 0`
- `test_round_trip_shares_to_amount_to_shares` — `shares → amount → shares` within 0.1%
- `test_zero_shares_returns_zero` — `get_amount_from_shares(lp, eth, 0) == 0`
- `test_zero_amount_returns_zero` — `get_shares_from_amount(lp, eth, 0) == 0`

---

### `python/test/math/test_balancer_math.py`

Pure math tests — no pool setup needed.

```python
from decimal import Decimal
from python.prod.cwpt.exchg.BalancerMath import BalancerMath
```

Tests:
- `test_calc_out_given_in_positive` — known Decimal inputs produce positive output
- `test_calc_out_given_in_fee_positive` — fee field `> 0`
- `test_calc_in_given_out_positive` — inverse direction, positive result
- `test_calc_spot_price` — `spot = (bal_in/w_in) / (bal_out/w_out) * 1/(1-fee)`; verify against formula
- `test_pool_out_given_single_in_positive` — `calc_pool_out_given_single_in(...)` result `> 0`
- `test_single_in_given_pool_out_positive` — `calc_single_in_given_pool_out(...)` result `> 0`
- `test_single_out_given_pool_in_positive` — `calc_single_out_given_pool_in(...)` result `> 0`
- `test_pool_in_given_single_out_positive` — `calc_pool_in_given_single_out(...)` result `> 0`

---

## Phase 3 — stableswappy Tests (~20 tests)

### Import pattern (use in every test file)
```python
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)).split('/python/')[0])
from python.prod.erc import ERC20
from python.prod.vault import StableswapVault
from python.prod.cst.factory import StableswapFactory
from python.prod.utils.data import StableswapExchangeData
from python.prod.process.join import Join
from python.prod.process.swap import Swap
from python.prod.process.liquidity import AddLiquidity
```

### Standard Stableswap pool fixture

> **Note:** In `stableswappy`'s `Join.apply(lp, user_nm, shares)`, the `shares` parameter is passed through to `lp.join_pool(vault, ampl_coeff, to)` — so it is actually the amplification coefficient, not a share count. Pass `200` (standard Curve A value).

```python
USER = 'user0'
AMPL = 200

def setup_stableswap_lp():
    usdc = ERC20("USDC", "0x01", 6)     # 6 decimal stablecoin
    usdc.deposit(USER, 10000)
    dai  = ERC20("DAI",  "0x02", 18)    # 18 decimal stablecoin
    dai.deposit(USER, 10000)

    vault = StableswapVault()
    vault.add_token(usdc)
    vault.add_token(dai)

    factory = StableswapFactory("Stableswap factory", "0x3")
    exch_data = StableswapExchangeData(vault=vault, symbol="CST", address="0x011")
    lp = factory.deploy(exch_data)
    Join().apply(lp, USER, AMPL)
    return lp, usdc, dai
```

---

### `python/test/process/test_join.py`

Tests:
- `test_join_sets_liquidity` — `lp.total_supply > 0`
- `test_join_sets_usdc_reserve` — `lp.get_reserve(usdc) == 10000`
- `test_join_sets_dai_reserve` — `lp.get_reserve(dai) == 10000`
- `test_join_provider_credited` — `lp.liquidity_providers[USER] > 0`
- `test_join_already_joined_raises` — second `Join().apply` raises `AssertionError`

---

### `python/test/process/test_swap.py`

Tests:
- `test_swap_usdc_for_dai_positive` — `Swap().apply(lp, usdc, dai, USER, 100)['tkn_out_amt'] > 0`
- `test_swap_near_peg_low_slippage` — swap 100 USDC, get back within 1% of 100 DAI
- `test_swap_fee_charged` — `out['tkn_in_fee'] > 0`
- `test_swap_dai_for_usdc` — reverse direction works, output `> 0`
- `test_swap_large_amount_higher_slippage` — slippage on 5000 USDC swap > slippage on 100 USDC swap
- `test_swap_usdc_reserve_increases` — USDC reserve increases after USDC→DAI swap
- `test_swap_dai_reserve_decreases` — DAI reserve decreases after USDC→DAI swap

---

### `python/test/process/test_liquidity.py`

Tests:
- `test_add_liquidity_usdc_returns_positive` — `AddLiquidity().apply(lp, usdc, USER, 1000)['liquidity_amt_in'] > 0`
- `test_add_liquidity_increases_total_supply` — `total_supply` increases after add
- `test_add_liquidity_usdc_reserve_increases` — USDC reserve increases
- `test_remove_liquidity_returns_token` — `lp.remove_liquidity(liq_amt, usdc, USER)['tkn_out_amt'] > 0`
- `test_remove_liquidity_decreases_total_supply` — `total_supply` decreases after remove

---

### `python/test/math/test_stableswap_math.py`

```python
from python.prod.cst.exchg.StableswapPoolMath import StableswapPoolMath
```

Standard math pool fixture:
```python
def setup_math_pool():
    # 10000 USDC (6 dec) + 10000 DAI (18 dec), balanced
    rates = [10**30, 10**18]   # rate_multiplier(6), rate_multiplier(18)
    balances = [10000 * 10**6, 10000 * 10**18]
    return StableswapPoolMath(A=200, D=balances, n=2, rates=rates)
```

Tests:
- `test_D_invariant_positive` — `pool.D() > 0`
- `test_D_invariant_stable_after_small_swap` — D changes by less than 0.01% after small exchange
- `test_get_y_positive` — `pool.get_y(0, 1, x, xp) > 0`
- `test_exchange_output_positive` — `pool.exchange(0, 1, dx)[0] > 0`
- `test_exchange_fee_positive` — `pool.exchange(0, 1, dx)[1] > 0`
- `test_virtual_price_near_one` — `pool.get_virtual_price() ≈ 10**18` for balanced pool (within 0.1%)
- `test_dydx_near_one_at_peg` — `pool.dydx(0, 1) ≈ 1.0` for balanced equal pool (within 1%)
- `test_calc_token_amount_positive` — `pool.calc_token_amount([1000 * 10**6, 0]) > 0`

---

## Test Writing Rules for Claude Code

### 1. Run first, then hardcode
For every numeric assertion: run the test to capture the actual output, then hardcode that value as the expected with a comment. Do not guess values.

```python
# Actual value captured from run: 99.8501...
self.assertAlmostEqual(out['tkn_out_amt'], 99.8501, places=4)
```

### 2. Tolerance pattern

| Context | Method | Places |
|---------|--------|--------|
| V2 integer math (SaferMath) | `assertAlmostEqual` | `6` |
| V2 float paths, Balancer, Stableswap | `assertAlmostEqual` | `4` |
| V3 sqrt price math | `assertAlmostEqual` | `3` |
| Round-trip identity tests | Relative tolerance `< 0.001` | — |

Never use `assertEqual` on floats.

### 3. K invariant note
In any uniswappy V2 swap test, include this comment:
```python
# NOTE: UniswapV2 K invariant check is currently disabled in UniswapExchange.swap()
# These tests verify reserve changes and output amounts, not K conservation.
```

### 4. Test isolation
Every test method calls the fixture setup fresh. No shared mutable state between tests.

### 5. File header
Every new test file starts with the Apache 2.0 license block matching the existing repo files:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2025 Ian Moore
# Email: defipy.devs@gmail.com
# ...
```

### 6. Class structure
Follow the existing pattern:
```python
class TestJoin(unittest.TestCase):

    def setUp(self):
        self.lp, self.eth, self.dai = setup_v2_lp()

    def test_xxx(self):
        ...

if __name__ == '__main__':
    unittest.main()
```

### 7. Run command (from each repo root)
```bash
python -m pytest python/test/ -v
```

---

## Delivery Order for Claude Code

1. Root `conftest.py` files — all 3 repos
2. All directory trees + `__init__.py` files — all 3 repos
3. **uniswappy** Phase 1 tests — in order listed above
4. **balancerpy** Phase 2 tests — in order listed above
5. **stableswappy** Phase 3 tests — in order listed above
6. **Final step** — run `python -m pytest python/test/ -v` in each repo, fix any import or setup errors before declaring done

---

## Known Issues / Flags for Claude Code

| Repo | Issue | Action |
|------|-------|--------|
| uniswappy | K invariant disabled in `UniswapExchange.swap()` | Add comment in swap tests, do not attempt to fix |
| uniswappy V3 | Float sqrt price math (Tier 3) | Use `places=3` tolerances in V3 tests |
| stableswappy | `Join.apply` `shares` param is actually `ampl_coeff` | Use `200` as the value, add comment |
| balancerpy | No existing tests at all | Build full tree from scratch per plan |
| stableswappy | No existing tests at all | Build full tree from scratch per plan |
