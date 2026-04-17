# DeFiPy Agent Layer — Deep Audit Report

**Date:** April 16, 2026  
**Scope:** Full line-by-line audit of `python/prod/agents/` and all dependency call paths  
**Files audited:** 4 agents, 4 configs, 1 data class, 3 `__init__.py` files, plus full dependency trace into uniswappy process/quote/analytics layers and defipy's own multi-protocol wrappers

---

## 9. Errata Patch — 5 One-Line Fixes for Immediate Release

These are the crashers that should be patched immediately. No architectural changes, no restructuring — just fix what blows up at runtime.

**(Full audit in sections 1-8 above — this section added for quick reference)**

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

**Changes:** `tkn0` → `tkn` (2 occurrences). Also fix assert message — incorrectly says `TVLBasedLiquidityExitAgent`.

---

### FIX 2 of 5 — `TVLBasedLiquidityExitAgent.py` → `withdraw_mock_position`

**Before:**
```python
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn0, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn0, user_nm, tkn_amt)
```

**After:**
```python
        tkn_amt = LPQuote(False).get_amount_from_lp(lp, tkn, lp_amt)
        amount_out = WithdrawSwap().apply(lp, tkn, user_nm, tkn_amt)
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

**Changes:** `tkn0` → `tkn` (2 occurrences). Also fix assert message — incorrectly says `TVLBasedLiquidityExitAgent`.

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
