# DeFiPy Agent Layer — Deep Audit Report

**Date:** April 16, 2026  
**Scope:** Full line-by-line audit of `python/prod/agents/` and all dependency call paths  
**Files audited:** 4 agents, 4 configs, 1 data class, 3 `__init__.py` files, plus full dependency trace into uniswappy process/quote/analytics layers and defipy's own multi-protocol wrappers

---

## 1. Critical Bugs (Will Crash at Runtime)

### BUG-1: `tkn0` undefined in `withdraw_mock_position` — 3 agents affected

**Files:** `ImpermanentLossAgent.py`, `TVLBasedLiquidityExitAgent.py`, `VolumeSpikeNotifierAgent.py`

All three agents contain identical broken code in `withdraw_mock_position`:

```python
def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt=None):
    ...
    tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)   # ← tkn0 is UNDEFINED
    amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)    # ← tkn0 is UNDEFINED
```

The parameter is `tkn` but the body references `tkn0`. This will raise `NameError` on any call. The fix is to replace `tkn0` with `tkn` in both lines.

**Severity:** CRITICAL — any withdrawal path crashes immediately.

---

### BUG-2: `block_number` vs `block_num` in `PriceThresholdSwapAgent.execute_action`

**File:** `PriceThresholdSwapAgent.py`, `execute_action` method

```python
def execute_action(self, lp, tkn, price, block_num, tkn1_over_tkn0=True):
    ...
    except Exception as e:
        print(f"Block {block_number}: Swap failed: {e}")  # ← block_number is UNDEFINED
```

The parameter is `block_num` but the except block references `block_number`. This means if a swap fails, the error handler itself crashes with a `NameError`, masking the original exception.

**Severity:** CRITICAL — error handling is broken; original errors are swallowed.

---

### BUG-3: `tDel.delta()` missing `self.` in uniswappy `Swap.py`

**File:** `uniswappy/python/prod/process/swap/Swap.py`, `apply` method

```python
def apply(self, lp, token_in, user_nm, amount_in, sqrt_price_limit=None):
    amount_in = tDel.delta() if amount_in == None else amount_in  # ← should be self.tDel
```

If `amount_in` is `None`, this raises `NameError`. In normal agent usage `amount_in` is always provided, so this is latent — but it will crash any code path that relies on the default random amount generation.

**Severity:** MODERATE — latent crash, only triggered when amount_in is None.

---

## 2. Logic / Semantic Bugs

### BUG-4: `check_condition` mutates config in `PriceThresholdSwapAgent`

**File:** `PriceThresholdSwapAgent.py`

```python
def check_condition(self, threshold=None, tkn1_over_tkn0=True, block_num=None):
    self.config.threshold = self.config.threshold if threshold == None else threshold
```

When `threshold` is passed, this *permanently mutates* the config object. Pydantic configs are meant to be immutable configuration — mutating them during a predicate check is a side effect that makes behavior unpredictable across calls. If `check_condition(threshold=5000)` is called once, all future calls without a threshold argument will use 5000 instead of the original config value.

**Severity:** HIGH — silent state corruption that compounds over batch runs.

---

### BUG-5: `check_condition` calls `self.apply()` — hidden Web3 call in predicate

**File:** `PriceThresholdSwapAgent.py`

```python
def check_condition(self, threshold=None, tkn1_over_tkn0=True, block_num=None):
    self.config.threshold = ...
    self.apply()          # ← re-fetches reserves from chain every call
    price = self.get_token_price(tkn1_over_tkn0, block_num)
    return price > self.config.threshold
```

`self.apply()` calls `_init_lp_contract()`, fetches reserves, fetches token metadata — all live Web3 RPC calls. This means `check_condition()` is not a pure predicate. It's expensive (multiple RPC calls per invocation), it mutates `self.lp_contract` and `self.lp_data` as side effects, and if the Web3 provider is down, the "check" crashes rather than returning a boolean.

Additionally, `get_token_price` with a `block_num` argument makes a *second* `_init_lp_contract()` + `getReserves` call, meaning a single `check_condition` call makes at minimum 4 RPC calls.

**Severity:** HIGH — performance killer in batch mode, design violation.

---

### BUG-6: `run_batch` event format inconsistency

**File:** `PriceThresholdSwapAgent.py` vs all other agents

PriceThresholdSwapAgent:
```python
def run_batch(self, tkn, events):
    start_block = events[0]['blockNumber']    # ← treats events as a LIST
    ...
    for k in events:
        reserve0 = events[k]['args']['reserve0']  # ← then treats as DICT
```

This is contradictory — `events[0]` is list indexing but `for k in events: events[k]` is dict iteration. If `events` is a list, the `for k` loop iterates over dict elements directly (not indices), so `events[k]` would fail. If `events` is a dict, `events[0]` works only if `0` is a key.

The other three agents consistently treat events as a dict:
```python
for k in events:
    block_num = events[k]['blockNumber']
```

**Severity:** HIGH — `run_batch` in PriceThresholdSwapAgent is likely broken depending on input format.

---

### BUG-7: `update_mock_pool` return value inconsistency

**ImpermanentLossAgent:** `update_mock_pool` has no return statement (returns `None`)  
**TVLBasedLiquidityExitAgent:** `update_mock_pool` returns `lp`  
**VolumeSpikeNotifierAgent:** `update_mock_pool` returns `lp`

The ImpermanentLossAgent's `apply` method calls `self.update_mock_pool(lp, block_num)` without capturing the return. This works only because `lp` is mutated in place. But if anyone refactors to use the return value (as the other agents suggest is the pattern), the IL agent breaks silently.

**Severity:** MODERATE — works by accident, fragile under refactoring.

---

## 3. Import / Namespace Issues

### ISSUE-1: Agents bypass defipy's multi-protocol dispatch layer

All four agents import directly from uniswappy:
```python
from uniswappy import *
```

But defipy has its own `Swap`, `Join`, `AddLiquidity`, `RemoveLiquidity` wrappers in `python/prod/process/` that dispatch based on exchange type (Uniswap V2/V3, Balancer, Stableswap). The agents completely bypass this dispatch layer.

This means the agents are hardcoded to Uniswap V2 only. The `prime_mock_pool` methods explicitly create `UniswapFactory` and `UniswapExchangeData` — there's no path to use these agents with Balancer or Stableswap pools.

**Impact:** The agent layer cannot fulfill the multi-protocol promise without significant rework. If agents should be protocol-agnostic, they need to use defipy's dispatch wrappers, not uniswappy directly.

---

### ISSUE-2: Wildcard import `from uniswappy import *` namespace pollution

The uniswappy `__init__.py` chains 25+ wildcard imports covering: erc, cpt.exchg, cpt.factory, cpt.index, cpt.quote, cpt.vault, cpt.wallet, math.basic, math.interest, math.interest.ips, math.interest.ips.aggregate, math.model, math.risk, process (and sub-packages), analytics, utils (and sub-packages).

Every name exported by any of these modules enters the agent's namespace. If any two modules export the same name, the last import wins silently. This is especially dangerous because defipy also has classes named `Swap`, `Join`, etc. — the resolution depends entirely on import order.

**Impact:** Namespace collisions are currently avoided by luck. Any new class added to uniswappy that shares a name with something in the agent scope will cause silent breakage.

---

### ISSUE-3: Unused imports across agents

| Agent | Unused Import |
|-------|--------------|
| ImpermanentLossAgent | `BaseModel` from pydantic (configs use it, agent doesn't) |
| ImpermanentLossAgent | `RetrieveEvents` from web3scout |
| ImpermanentLossAgent | `Web3` from web3 |
| TVLBasedLiquidityExitAgent | `BaseModel` from pydantic |
| TVLBasedLiquidityExitAgent | `RetrieveEvents` from web3scout |
| TVLBasedLiquidityExitAgent | `Web3` from web3 |
| VolumeSpikeNotifierAgent | `BaseModel` from pydantic |
| VolumeSpikeNotifierAgent | `RetrieveEvents` from web3scout |
| VolumeSpikeNotifierAgent | `Web3` from web3 |
| PriceThresholdSwapAgent | `RetrieveEvents` (imported twice) |
| PriceThresholdSwapAgent | `EventTypeEnum` from web3scout |

**Impact:** Low — code hygiene, but signals copy-paste development.

---

## 4. Architectural Issues

### ARCH-1: No base class — massive code duplication

The following code blocks are copy-pasted nearly verbatim across 3 or 4 agents:

| Duplicated Pattern | Agents | ~Lines each |
|-------------------|--------|------------|
| `__init__` (connector/abi/contract setup) | All 4 | 12 |
| `init()` / pool initialization | IL, TVL, Volume | 14 |
| `prime_mock_pool()` | IL, TVL, Volume, Price (as `prime_pool_state`) | 22 |
| `update_mock_pool()` | IL, TVL, Volume | 16 |
| Getter methods (get_connector, get_abi, get_w3, etc.) | All 4 | 12 |
| `_init_lp_contract()` | All 4 | 5 |
| `withdraw_mock_position()` | IL, TVL, Volume | 5 |
| `take_mock_position()` | IL, TVL, Volume | 4 |
| `run_batch()` | All 4 (different signatures) | 6 |

**Estimated duplication:** ~400 lines of nearly identical code across the 4 agents, out of ~550 total lines. That's roughly 73% duplicated code.

A `BaseUniswapAgent` class could hold all shared infrastructure: connector setup, contract initialization, mock pool priming/updating, position management, getters, and batch processing. Each concrete agent would only implement its specific condition logic and action.

---

### ARCH-2: Web3 coupling in `__init__` prevents testability

Every agent's `__init__` immediately creates a `ConnectW3` and calls `.apply()`:
```python
self.connector = ConnectW3(self.config.provider_url)
self.connector.apply()
```

This means you cannot instantiate any agent without a live Web3 provider. The mock pool infrastructure (`prime_mock_pool`, `update_mock_pool`) is a good idea for offline simulation, but it also requires Web3 because it calls `_init_lp_contract()`, `FetchToken`, and contract function calls on a live node at a specific block.

**The mock pool pattern is not truly offline** — it fetches real blockchain state at historical blocks and copies it into a local simulation. This is useful for backtesting against real data, but it's not a unit-testable mock. True unit testing requires injecting fake reserve/token data without any RPC calls.

**Recommendation:** Separate construction from connection. Accept an optional pre-built connector or allow a "dry run" mode that works with injected data.

---

### ARCH-3: Lifecycle inconsistency — `init()` vs `apply()` semantics

| Agent | Setup method | Action method | Condition method |
|-------|-------------|---------------|-----------------|
| ImpermanentLossAgent | `init()` | `apply()` | `check_condition()` — pure (given state) |
| TVLBasedLiquidityExitAgent | `init()` | `apply()` | `check_condition()` — fetches block if None |
| VolumeSpikeNotifierAgent | `init()` | `apply()` | `check_condition()` — fetches block if None |
| PriceThresholdSwapAgent | `apply()` ← overloaded | ← no separate action | `check_condition()` — calls apply() + RPC |

PriceThresholdSwapAgent uses `apply()` for what the other agents call `init()`. It has no separate action method — `execute_action` is a standalone method that doesn't follow the lifecycle. And its `check_condition()` triggers the full `apply()` setup internally.

This makes it impossible to write a generic agent orchestrator that calls `agent.init()` → `agent.apply()` → `agent.check_condition()` uniformly across all agent types.

---

### ARCH-4: Config fields declared but never used

| Config | Unused Field | Agent |
|--------|-------------|-------|
| `ImpermanentLossConfig` | `user_position` | Stored in agent but never referenced in any method |
| `ImpermanentLossConfig` | `exit_percentage` | Stored in agent but never referenced in any method |
| `TVLExitConfig` | `exit_percentage` | Never referenced anywhere in TVLBasedLiquidityExitAgent |
| `TVLExitConfig` | `user_position` | Never referenced anywhere |
| `VolumeSpikeConfig` | `user_position` | Never referenced anywhere |

These fields are required in the Pydantic config (no defaults, so you must provide them), but the agents never use them. This means callers must invent values for fields that have no effect.

---

### ARCH-5: Dead code in `init()` methods

In `ImpermanentLossAgent.init()`, `TVLBasedLiquidityExitAgent.init()`, and `VolumeSpikeNotifierAgent.init()`:

```python
reserve0 = reserves[0]; reserve1 = reserves[1]
```

These local variables are assigned but never used — `reserves` is stored in `self.lp_data` as the raw list. The `reserve0`/`reserve1` decomposition serves no purpose.

---

## 5. Dependency Chain Analysis

### Call path: `withdraw_mock_position` → `LPQuote` → `RebaseIndexToken` → exchange internals

```
Agent.withdraw_mock_position(lp, tkn, user_nm)
  → LPQuote(False).get_amount_from_lp(lp, tkn, lp_amt)
    → RebaseIndexToken().apply(lp, tkn, amount_lp_in)
      → lp.reserve0 / lp.reserve1 / lp.total_supply (V2)
    → LPQuote.get_amount(lp, tkn, itkn_amt)  [only if quote_opposing=True, but it's False here]
    → lp.convert_to_human(amt_out) (V2)
  → WithdrawSwap().apply(lp, tkn, user_nm, tkn_amt)
    → WithdrawSwap._calc_univ2_withdraw_portion(lp, tkn, amt)
      → SettlementLPToken().apply(lp, tkn, amt)
      → FullMath.divRoundingUp(...)
    → RemoveLiquidity().apply(lp, tkn, user_nm, portion * amount)
    → Swap().apply(lp, trading_token, user_nm, remaining)
```

This call chain is mathematically sound — the `RebaseIndexToken ↔ SettlementLPToken` inverse relationship correctly converts between LP tokens and underlying reserves. The math in `WithdrawSwap` correctly calculates the withdrawal portion using the quadratic fee-adjusted formula.

**However:** The agents pass `tkn0` (undefined) instead of `tkn` to this chain, so it never actually executes (BUG-1).

---

### Call path: `take_mock_position` → `SwapDeposit` → exchange internals

```
Agent.take_mock_position(lp, tkn, user_nm, amt)
  → SwapDeposit().apply(lp, tkn, user_nm, amt)
    → SwapDeposit._calc_univ2_deposit_portion(lp, tkn, amt) [quadratic formula for optimal split]
    → Swap().apply(lp, tkn, user_nm, portion * amt)
    → lp.add_liquidity(user_nm, balance0, balance1, ...)
  → lp.get_last_liquidity_deposit() [captures LP tokens minted]
  → UniswapImpLoss(lp, lp_init_amt) [IL agent only — creates tracker]
```

This chain is correct. The `_calc_univ2_deposit_portion` uses the hand-derived quadratic formula to find the optimal swap fraction that minimizes leftover tokens after deposit — this is the kind of mathematical rigor that distinguishes the project.

---

### Call path: `prime_mock_pool` → `UniswapFactory` → exchange setup

```
Agent.prime_mock_pool(start_block, user_nm)
  → FetchToken(w3).apply(token_address)    [RPC: fetch name, symbol, decimals]
  → fetch_tkn.amt_to_decimal(tkn, raw_reserves)  [scale by decimals]
  → UniswapFactory("Pool factory", "0x2").deploy(exch_data)  [creates local exchange]
  → Join().apply(lp_state, user_nm, amt0, amt1)  [seeds initial liquidity]
  → lp_state.total_supply = total_supply  [overrides with on-chain value]
```

This is correct but note: the `Join()` here comes from `uniswappy import *`, so it's the uniswappy-specific Join, not defipy's multi-protocol wrapper. For V2 pools this works fine.

---

### UniswapImpLoss mathematical correctness

The IL calculation has two modes:

**Mode 1 (`fees=False`):** Classic IL formula: `IL = 2√α / (1+α) - 1` where `α = current_price / initial_price`. For V3, scaled by `√r / (√r - 1)` where `r` is the average of the price range bounds. This is mathematically correct.

**Mode 2 (`fees=True`):** Compares actual position value vs. hold value. `position_value = LPQuote(False).get_amount_from_lp(lp, tkn, lp_init)` and `hold_value = x_init * price + y_init`. This correctly captures fee-inclusive returns.

The agent uses `fees=True` in `get_impermanent_loss()`, which is the right choice for real-world monitoring since it accounts for accumulated swap fees.

---

## 6. Agent-by-Agent Summary

### ImpermanentLossAgent
- **Purpose:** Monitor IL on a position and trigger exit when position value drops below threshold
- **Bugs:** BUG-1 (tkn0 undefined in withdraw), BUG-7 (update_mock_pool no return)
- **Math correctness:** UniswapImpLoss integration is correct; fee-inclusive mode properly used
- **Design issues:** Unused config fields (user_position, exit_percentage), unused imports
- **Note:** `check_condition` compares position value to a threshold, not IL percentage — the naming is slightly misleading. `il_threshold` in config is used as a position *value* threshold, not an IL percentage threshold

### TVLBasedLiquidityExitAgent
- **Purpose:** Exit liquidity when pool TVL drops below threshold
- **Bugs:** BUG-1 (tkn0 undefined in withdraw)
- **Math correctness:** TVL calculation via `LPQuote` is correct
- **Design issues:** Unused config fields (exit_percentage, user_position), unused imports

### VolumeSpikeNotifierAgent
- **Purpose:** Alert when trading volume exceeds threshold
- **Bugs:** BUG-1 (tkn0 undefined in withdraw)
- **Math correctness:** Volume calculation is reasonable — measures reserve delta between blocks, converts to single-token denomination using `LPQuote`. However, this measures *net* reserve change, not actual trading volume (deposits/withdrawals also change reserves)
- **Design issues:** Unused config fields, unused imports
- **Note:** Volume calculation via reserve deltas is an approximation. True volume requires parsing Swap events, not Sync events. A large liquidity add/remove would register as a volume spike

### PriceThresholdSwapAgent
- **Purpose:** Execute swap when price crosses threshold
- **Bugs:** BUG-2 (block_number typo), BUG-4 (config mutation), BUG-5 (hidden RPC in predicate), BUG-6 (event format inconsistency)
- **Math correctness:** Price calculation is correct (cross-rate with decimal adjustment)
- **Design issues:** Most problematic agent — lifecycle violation, no `init()` method, `apply()` overloaded for setup, `check_condition` has massive side effects

---

## 7. Recommendations (Prioritized)

### P0 — Fix crashers before anything else
1. Fix `tkn0` → `tkn` in all three `withdraw_mock_position` methods
2. Fix `block_number` → `block_num` in PriceThresholdSwapAgent
3. Fix `tDel.delta()` → `self.tDel.delta()` in uniswappy Swap.py

### P1 — Extract BaseUniswapAgent
Create a base class containing:
- `__init__` with connector/ABI setup
- `init()` for pool data fetching
- `prime_mock_pool()` / `update_mock_pool()`
- `take_mock_position()` / `withdraw_mock_position()`
- `run_batch()`
- All getter methods
- `_init_lp_contract()`

Each concrete agent implements only:
- `check_condition()` — pure predicate, no side effects
- `execute_action()` or `apply()` — the agent's specific behavior
- Agent-specific analytics (IL calculation, volume tracking, etc.)

### P2 — Fix PriceThresholdSwapAgent lifecycle
- Add `init()` method matching the other agents
- Remove `self.apply()` call from `check_condition()` — pre-fetch data once, check against it
- Stop mutating `self.config.threshold` inside `check_condition()`
- Align `run_batch` signature with the other agents

### P3 — Decouple Web3 from construction
- Make `ConnectW3` injection optional in `__init__`
- Add a factory method or builder pattern: `Agent.from_config(config)` for live mode, `Agent.from_mock_data(tokens, reserves)` for test mode
- This enables true unit testing without any RPC mocking

### P4 — Clean up configs
- Remove unused fields or implement the features they imply
- If `exit_percentage` should control partial exits, implement it in `withdraw_mock_position`
- If `user_position` should set initial position size, wire it into `take_mock_position`
- Add defaults where appropriate so callers don't need to invent values

### P5 — Fix volume calculation accuracy
- `VolumeSpikeNotifierAgent` measures net reserve deltas, not actual trading volume
- Consider parsing Swap events directly for accurate volume, or document the approximation explicitly
- Add a flag to distinguish "volume from swaps" vs "reserve change from all sources"

### P6 — Import cleanup
- Replace `from uniswappy import *` with explicit imports of needed classes
- Remove unused imports (BaseModel, RetrieveEvents, Web3, EventTypeEnum)
- Decide whether agents should use defipy's multi-protocol wrappers or uniswappy directly, and be consistent

### P7 — Multi-protocol readiness
- If agents should support Balancer/Stableswap, refactor `prime_mock_pool` to accept an exchange type parameter and use defipy's dispatch layer
- If agents are intentionally Uniswap-only, document this constraint and rename to `UniswapILAgent`, etc.

---

## 8. Test Strategy Implications

Given the Web3 coupling, the agent test suite needs two layers:

**Layer 1 — Pure math/logic tests (no mocking needed):**
- Test `calc_price` with known reserve values
- Test `check_condition` logic with pre-set state (requires P3 refactor)
- Test UniswapImpLoss calculations with synthetic pools
- Test volume calculation with known reserve deltas

**Layer 2 — Integration tests (mock Web3):**
- Mock `ConnectW3`, `ABILoad`, `FetchToken` to return synthetic data
- Test `prime_mock_pool` → `update_mock_pool` → `check_condition` → `apply` flow
- Test `run_batch` with synthetic event dicts
- Test `take_mock_position` → `withdraw_mock_position` round-trip

The P3 refactor (decoupling Web3 from construction) would eliminate most of the need for Layer 2, letting the math be tested directly. Until then, every test requires mocking 3-4 web3scout classes just to instantiate an agent.

---

## 9. Files Audited (Complete List)

| File | Status |
|------|--------|
| `agents/__init__.py` | Read — clean, explicit imports |
| `agents/ImpermanentLossAgent.py` | Read — BUG-1, BUG-7, unused fields |
| `agents/PriceThresholdSwapAgent.py` | Read — BUG-2, BUG-4, BUG-5, BUG-6 |
| `agents/TVLBasedLiquidityExitAgent.py` | Read — BUG-1 |
| `agents/VolumeSpikeNotifierAgent.py` | Read — BUG-1, volume approximation concern |
| `agents/config/__init__.py` | Read — clean |
| `agents/config/ImpermanentLossConfig.py` | Read — unused fields |
| `agents/config/PriceThresholdConfig.py` | Read — clean |
| `agents/config/TVLExitConfig.py` | Read — unused fields |
| `agents/config/VolumeSpikeConfig.py` | Read — unused fields |
| `agents/data/__init__.py` | Read — clean |
| `agents/data/UniswapPoolData.py` | Read — clean dataclass |
| `uniswappy/.../LPQuote.py` | Read — correct, well-documented |
| `uniswappy/.../UniswapImpLoss.py` | Read — mathematically correct |
| `uniswappy/.../Swap.py` | Read — BUG-3 |
| `uniswappy/.../SwapDeposit.py` | Read — correct, sophisticated math |
| `uniswappy/.../WithdrawSwap.py` | Read — correct |
| `uniswappy/.../Join.py` | Read — correct |
| `uniswappy/.../ERC20.py` | Read — clean |
| `defipy/.../process/swap/Swap.py` | Read — multi-protocol dispatcher |
| `defipy/.../process/join/Join.py` | Read — multi-protocol dispatcher |
| `defipy/.../process/liquidity/AddLiquidity.py` | Read — multi-protocol dispatcher |
| `defipy/.../process/liquidity/RemoveLiquidity.py` | Read — multi-protocol dispatcher |
| `defipy/python/prod/__init__.py` | Read — full import chain mapped |

---

## 10. Bottom Line

The mathematical foundation beneath the agents is excellent — `LPQuote`, `UniswapImpLoss`, `SwapDeposit`, `WithdrawSwap` all demonstrate hand-derived, financially rigorous implementations. The bugs are concentrated in the agent orchestration layer, not the math. Three of the four agents share a nearly identical `withdraw_mock_position` bug that was likely introduced during copy-paste development.

The highest-impact fix is extracting a `BaseUniswapAgent` class (P1). This eliminates ~400 lines of duplication, makes the `tkn0` bug a one-line fix instead of three, and creates a clear contract for future agents. Combined with the Web3 decoupling (P3), the test suite becomes straightforward to write.

The PriceThresholdSwapAgent needs the most work — it has 4 bugs and the most significant architectural deviations. Consider whether to fix it incrementally or rewrite it to conform to the pattern established by the other three agents.
