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

When `threshold` is passed, this *permanently mutates* the config object. Pydantic configs are meant to be immutable configuration — mutating them during a predicate check is a side effect that makes behavior unpredictable across calls.

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

`self.apply()` calls `_init_lp_contract()`, fetches reserves, fetches token metadata — all live Web3 RPC calls. A single `check_condition` call makes at minimum 4 RPC calls.

**Severity:** HIGH — performance killer in batch mode, design violation.

---

### BUG-6: `run_batch` event format inconsistency

**File:** `PriceThresholdSwapAgent.py` vs all other agents

PriceThresholdSwapAgent treats events as both list (`events[0]`) and dict (`for k in events: events[k]`). The other three agents consistently treat events as a dict.

**Severity:** HIGH — `run_batch` in PriceThresholdSwapAgent is likely broken depending on input format.

---

### BUG-7: `update_mock_pool` return value inconsistency

- ImpermanentLossAgent: no return (returns None)
- TVLBasedLiquidityExitAgent: returns lp
- VolumeSpikeNotifierAgent: returns lp

**Severity:** MODERATE — works by accident via in-place mutation, fragile under refactoring.

---

## 3. Import / Namespace Issues

### ISSUE-1: Agents bypass defipy's multi-protocol dispatch layer

All four agents import `from uniswappy import *` directly, bypassing defipy's own `Swap`, `Join`, `AddLiquidity`, `RemoveLiquidity` wrappers that dispatch based on exchange type. Agents are hardcoded to Uniswap V2 only.

### ISSUE-2: Wildcard import namespace pollution

The uniswappy `__init__.py` chains 25+ wildcard imports. Any name collision is resolved silently by import order.

### ISSUE-3: Unused imports across agents

`BaseModel`, `RetrieveEvents`, `Web3`, `EventTypeEnum` imported but never used in agent bodies. Signals copy-paste development.

---

## 4. Architectural Issues

### ARCH-1: No base class — ~73% code duplication

~400 lines of nearly identical code duplicated across 4 agents (out of ~550 total). `__init__`, `init()`, `prime_mock_pool()`, `update_mock_pool()`, getters, `_init_lp_contract()`, `withdraw_mock_position()`, `take_mock_position()`, `run_batch()` are all copy-pasted.

### ARCH-2: Web3 coupling in `__init__` prevents testability

Cannot instantiate any agent without a live Web3 provider. Mock pool infrastructure also requires RPC calls. True unit testing requires injecting fake data without any RPC.

### ARCH-3: Lifecycle inconsistency

IL/TVL/Volume agents: `init()` → `apply()` → `check_condition()`
PriceThresholdSwapAgent: `apply()` for setup, `check_condition()` calls `apply()` internally, `execute_action()` is standalone.

### ARCH-4: Config fields declared but never used

`user_position` and `exit_percentage` are required in configs but never referenced in agent code. Callers must invent values for fields that have no effect.

### ARCH-5: Dead code

`reserve0 = reserves[0]; reserve1 = reserves[1]` assigned in `init()` but never used (3 agents).

---

## 5. Dependency Chain — Mathematical Verification

### LPQuote / RebaseIndexToken / SettlementLPToken
Mathematically correct. The inverse relationship properly converts between LP tokens and underlying reserves for both V2 and V3.

### SwapDeposit quadratic formula
Correct. Hand-derived optimal swap fraction minimizes leftover tokens after single-sided deposit. V3 version uses scipy optimization which is appropriate for the non-closed-form case.

### WithdrawSwap withdrawal portion
Correct. Uses SettlementLPToken and FullMath for precise portion calculation with fee integration.

### UniswapImpLoss
Two modes both correct:
- `fees=False`: Classic `2√α/(1+α) - 1` with V3 price-range scaling
- `fees=True`: Actual position value vs hold value comparison

### Volume calculation (VolumeSpikeNotifierAgent)
**Approximation concern:** Measures net reserve delta between blocks, not actual swap volume. Liquidity adds/removes also change reserves and would register as "volume spikes." Document this limitation or switch to Swap event parsing.

---

## 6. Recommendations (Prioritized)

### P0 — Fix crashers
1. `tkn0` → `tkn` in three `withdraw_mock_position` methods
2. `block_number` → `block_num` in PriceThresholdSwapAgent
3. `tDel.delta()` → `self.tDel.delta()` in uniswappy Swap.py

### P1 — Extract BaseUniswapAgent
Eliminate ~400 lines of duplication. Shared infrastructure in base class, concrete agents implement only condition + action.

### P2 — Fix PriceThresholdSwapAgent lifecycle
Add `init()`, remove `self.apply()` from `check_condition()`, stop mutating config, align `run_batch` signature.

### P3 — Decouple Web3 from construction
Optional connector injection. Factory methods for live vs test mode. Enables true unit testing.

### P4 — Clean up configs
Remove unused fields or implement the features they imply. Add defaults where appropriate.

### P5 — Fix volume calculation accuracy
Document approximation or parse Swap events for true volume.

### P6 — Import cleanup
Explicit imports, remove unused, decide on defipy wrappers vs direct uniswappy.

### P7 — Multi-protocol readiness
Either refactor for protocol-agnostic agents or document as Uniswap-only.

---

## 7. Test Strategy Implications

**Layer 1 — Pure math/logic (no mocking):**
- `calc_price`, `check_condition` logic, IL calculations, volume deltas with synthetic pools

**Layer 2 — Integration (mock Web3):**
- Mock `ConnectW3`, `ABILoad`, `FetchToken`
- Test full `prime → update → check → apply` flow
- Test batch processing with synthetic events

P3 refactor eliminates most Layer 2 need, letting math be tested directly.

---

## 8. Bottom Line

The mathematical foundation is excellent. The bugs are in the orchestration layer, not the math. Three agents share an identical `tkn0` bug from copy-paste. PriceThresholdSwapAgent has the most issues (4 bugs + lifecycle violations). Extracting a base class (P1) is the highest-impact improvement — it fixes the duplication, makes bugs single-fix, and establishes a clear contract for the agentic layer expansion.

---

## 9. Errata Patch — 5 One-Line Fixes for Immediate Release

These are the crashers that should be patched immediately. No architectural changes, no restructuring — just fix what blows up at runtime.

---

### FIX 1 of 5 — `ImpermanentLossAgent.py` → `withdraw_mock_position`

**Before:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'TVLBasedLiquidityExitAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)
        return amount_out
```

**After:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'ImpermanentLossAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn, user_nm, tkn_amt)
        return amount_out
```

**Changes:** `tkn0` → `tkn` (2 occurrences). Also fix the assert message — it incorrectly says `TVLBasedLiquidityExitAgent`.

---

### FIX 2 of 5 — `TVLBasedLiquidityExitAgent.py` → `withdraw_mock_position`

**Before:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'TVLBasedLiquidityExitAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)
        return amount_out
```

**After:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'TVLBasedLiquidityExitAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn, user_nm, tkn_amt)
        return amount_out
```

**Changes:** `tkn0` → `tkn` (2 occurrences).

---

### FIX 3 of 5 — `VolumeSpikeNotifierAgent.py` → `withdraw_mock_position`

**Before:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'TVLBasedLiquidityExitAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)
        return amount_out
```

**After:**
```python
    def withdraw_mock_position(self, lp, tkn, user_nm, lp_amt = None):
        assert self.mock_lp_pos_amt != None, 'VolumeSpikeNotifierAgent: MOCK_POSITION_UNAVAILABLE' 
        lp_amt = self.mock_lp_pos_amt if lp_amt == None else lp_amt
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn, user_nm, tkn_amt)
        return amount_out
```

**Changes:** `tkn0` → `tkn` (2 occurrences). Also fix the assert message — it incorrectly says `TVLBasedLiquidityExitAgent`.

---

### FIX 4 of 5 — `PriceThresholdSwapAgent.py` → `execute_action`

**Before:**
```python
            except Exception as e:
                print(f"Block {block_number}: Swap failed: {e}")
```

**After:**
```python
            except Exception as e:
                print(f"Block {block_num}: Swap failed: {e}")
```

**Changes:** `block_number` → `block_num`.

---

### FIX 5 of 5 — `uniswappy/python/prod/process/swap/Swap.py` → `apply`

**Before:**
```python
        amount_in = tDel.delta() if amount_in == None else amount_in
```

**After:**
```python
        amount_in = self.tDel.delta() if amount_in == None else amount_in
```

**Changes:** `tDel` → `self.tDel`.

---

### Bonus: Copy-paste assert message errors

Fixes 1 and 3 also correct assert messages that were copied from `TVLBasedLiquidityExitAgent` without updating the class name. Not crashers, but confusing when they fire.

---

### Verification

After applying all 5 fixes, from each repo root:
```bash
python -c "from defipy.agents import *; print('defipy agents import OK')"
python -c "from uniswappy.process.swap import Swap; print('uniswappy Swap import OK')"
```

Full runtime verification requires a Web3 provider, but these import checks confirm no syntax errors were introduced.
