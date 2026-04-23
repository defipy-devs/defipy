# DeFiPy v2.0 — Day 3 Completion Report

## Ready for Ian

All CC-side work complete. To verify the end-to-end agentic loop closes:

1. **Commit SHA:** TBD — filled in after commit lands on `main` (this report ships in the same commit; resolve via `git log -1`).

2. **Claude Desktop config.** Open `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

   ```json
   {
     "mcpServers": {
       "defipy": {
         "command": "/opt/homebrew/opt/python@3.11/bin/python3.11",
         "args": [
           "/Users/ian_moore/repos/defipy/python/mcp/defipy_mcp_server.py"
         ]
       }
     }
   }
   ```

   Restart Claude Desktop. The DeFiPy tools appear under the hammer icon.

3. **Suggested first question:**

   > "Check the health of the ETH/DAI V2 pool."

   Expected behavior: Claude picks `CheckPoolHealth` with `pool_id="eth_dai_v2"`, returns TVL, reserves, and LP concentration. A richer test:

   > "I have 10 LP tokens in the 50/50 ETH/DAI Balancer pool and I deposited 1000 ETH and 100000 DAI. If ETH drops 30%, what happens to my position?"

   Expected: Claude calls `SimulateBalancerPriceMove` with `pool_id="eth_dai_balancer_50_50"`, `price_change_pct=-0.30`, `lp_init_amt=10`, and reports IL, new value, and value-change percentage.

4. **Receipts location.** Every tool call writes one line of JSON to the server's stderr. Claude Desktop routes MCP stderr to its Developer Console — enable via Help → Developer → Toggle Developer Tools → Console tab. Claude Code writes to `~/.claude/mcp-logs/defipy.log` (verify against your Claude Code version).

5. **If the loop doesn't close**, paste the error back to CC (or a fresh session) — likely causes are path typos in the config JSON, Python-interpreter mismatch (the command in `args[0]` must match the Python where `pip install defipy[mcp]` ran), or an `mcp` SDK API shift between 1.27.0 (tested) and whatever's installed.

---

## Objective

Ship two Day 3 deliverables:

1. **Packaging fix.** `setup.py` was missing 6 primitive sub-packages (`comparison`, `execution`, `optimization`, `pool_health`, `portfolio`, `risk`) plus `defipy.analytics.*` — a fresh PyPI install would be broken on import.
2. **MCP server demo.** A stdio-transport server at `python/mcp/defipy_mcp_server.py` that exposes the curated 10 tools, dispatches to primitives running against MockProvider-built twins, and emits stderr receipts.

---

## Deliverables

### Packaging fix (`setup.py`)

- **`version`** → `2.0.0`
- **`description`** → `"Python SDK for Agentic DeFi"` (the new tagline)
- **`packages`** regenerated from an on-disk scan — 35 concrete packages now enumerated. Missing-from-v1.2.0 additions: the 6 primitive sub-packages above, plus `defipy.analytics.risk`, `defipy.analytics.simulate`, `defipy.agents.config`, and `defipy.agents.data` (which were implicit before)
- **`extras_require["mcp"]`** = `["mcp >= 1.27.0"]` — demo-only dependency; not in `install_requires`

### Packaging smoke tests (`python/test/test_packaging.py`)

3 tests that exercise every shipped sub-package via import. These fail in a broken install but pass in the (editable or clean) install that has all `packages=[...]` entries present.

### MCP server (`python/mcp/`)

- `defipy_mcp_server.py` — async stdio server built on `mcp.server.Server` + `mcp.server.stdio.stdio_server`. Uses `@server.list_tools()` and `@server.call_tool()` decorator pattern from MCP SDK 1.27.0 (matches the brief's sketch).
- `README.md` — install, Claude Desktop config, Claude Code config, example questions, tool inventory, recipes, receipts viewing, limitations, troubleshooting.

**No `__init__.py`** in `python/mcp/` — making it a package would shadow the installed `mcp` SDK when the directory ends up on `sys.path`. The dir ships as plain scripts.

### MCP server unit tests (`python/test/mcp/test_server.py`)

23 tests covering schema wrapping, ok/error dispatch paths, token resolution across all 4 protocols, summarizer coverage, receipt emission (ok + error), and fresh-twin-per-call semantics. Tests load the server module via `importlib` (not `sys.path`) to avoid the `mcp` shadowing trap — see §"Gotchas" below.

---

## Design decisions carried through

All 6 settled decisions from the brief held:

- **(A) Token resolution in server, not library.** `_resolve_token(lp, name)` walks V2/V3 path (`lp.factory.token_from_exchange[lp.name]`) then Balancer/Stableswap path (`lp.vault.get_token(name)`); raises with an enumeration of available tokens if nothing matches.
- **(B) `pool_id` wrapped at server, Day 1 schemas unchanged.** `_wrap_schemas_with_pool_id()` deep-copies the schemas and injects a required `pool_id` string field with an `enum` restricted to compatible recipes. The 556-test Day 1 baseline stays green.
- **(C) Single-line JSON receipts to stderr.** `_log_receipt` emits `ts / tool / pool_id / args / status / duration_ms / result_summary` (or `error_type / error_message`) via `print(..., file=sys.stderr, flush=True)`. One summarizer per tool — hand-curated, one line each.
- **(D) Fresh twin per call.** `call_tool` builds a new lp via `_PROVIDER.snapshot(pool_id) → _BUILDER.build(snapshot)` on every invocation. No cross-call state.
- **(E) Primitive×recipe compatibility validated at dispatch.** `_COMPATIBLE_RECIPES` hardcoded; incompatible calls return a structured error content block (not an exception), with the message enumerating valid pools so Claude can recover.
- **(F) `mcp` is extras-only.** `install_requires` unchanged; new `extras_require["mcp"]` added. Users running `pip install defipy` don't pay the MCP SDK dependency cost.

---

## Two gotchas worth remembering

### 1. `python/mcp/` can't be a Python package

If `python/mcp/__init__.py` exists and `python/mcp/` (or an ancestor) is on `sys.path`, Python's import resolver treats the local directory as the `mcp` top-level package — shadowing the installed MCP SDK. `from mcp.server import Server` then fails with `ModuleNotFoundError: No module named 'mcp.server'`.

Fix: `python/mcp/` has no `__init__.py` and isn't treated as a package. Test conftest loads `defipy_mcp_server.py` directly via `importlib.util.spec_from_file_location`.

### 2. `python/test/mcp/` can't be a package either

Same root cause: `python/test/mcp/__init__.py` combined with `python/test/` on sys.path (which the top-level test conftest does) shadows the installed MCP SDK. Fix: removed the `__init__.py`.

Both gotchas matter for Day 4 (and for anyone writing docs examples) — don't reintroduce `__init__.py` in either location.

---

## Clean-venv install verification

Attempted the brief's clean-venv install test. Results:

- **DeFiPy wheel build:** passed. 35 packages enumerated correctly; `defipy-2.0.0-py3-none-any.whl` produced at 177 KB.
- **DeFiPy sub-package imports:** all shipped modules resolve. Our packaging fix is verified.
- **Blocking upstream bug:** `uniswappy` 1.7.7 has an unconditional `import pytest` in `uniswappy/utils/tools/v3/UniV3Utils.py` line 28. Breaks import of `defipy` in any environment without pytest installed.
- **Blocking upstream bug 2:** `balancerpy` 1.0.6 and `stableswappy` 1.0.5 on PyPI are missing their `analytics` sub-packages. The v1.2.0 refactor added `balancerpy.analytics.risk.BalancerImpLoss` and `stableswappy.analytics.risk.StableswapImpLoss`, but the upstream `packages=[...]` wasn't updated — same bug defipy just fixed. DeFiPy primitives that import from `balancerpy.analytics.risk` or `stableswappy.analytics.risk` fail at runtime on a clean install.

**Implication:** v2.0 cannot ship to PyPI until upstream `balancerpy` / `stableswappy` / `uniswappy` release fresh wheels with correct packages. This is a Day 4 / pre-release gate, not a Day 3 defect. DeFiPy's own packaging is correct and complete. Adding to `V2_FOLLOWUPS.md` is recommended.

Editable install (`pip install -e .`) pointed at the worktree continues to work because it bypasses the installed siblings' `packages=[...]` lists and uses their source trees directly.

---

## Results

- **Tests:** 629 passing (504 primitives + 52 tools + 47 twin + 3 packaging + 23 MCP server)
- **New code:** `python/mcp/defipy_mcp_server.py` (~330 lines), `python/mcp/README.md`, `python/test/mcp/test_server.py` + conftest, `python/test/test_packaging.py`, `setup.py` rewrite
- **Commit:** filled in at push time (same commit as this report)

---

## Day 4 hand-off notes

- The `[mcp]` pin is `mcp >= 1.27.0` — revisit when the MCP Python SDK hits 1.0 per their announced stability goal. Add to `V2_FOLLOWUPS.md`.
- Richer observability (structured event sink, not one-liners) is v2.1. Day 4 CHANGELOG should call this out.
- CI job that runs the clean-venv install test on every PR is Day 5/6 or Phase 2 work.
- Upstream siblings (`balancerpy`, `stableswappy`, `uniswappy`) all need fresh PyPI releases before v2.0.0 can ship to PyPI. Track the coordination in `V2_FOLLOWUPS.md`.

---

## Environment note

MCP SDK installed globally in the homebrew Python 3.11 site-packages at `/opt/homebrew/lib/python3.11/site-packages/mcp/` at version 1.27.0. The editable install pointing at this worktree continues to work. Nothing to repoint.
