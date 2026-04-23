# DeFiPy MCP Server

A Model Context Protocol (MCP) server that exposes DeFiPy's curated v2.0 tool set to any MCP client — Claude Desktop, Claude Code, or third-party agents.

Ships 10 tools covering position analysis, price-move simulation, pool health, slippage, and depeg risk across Uniswap V2, Uniswap V3, Balancer, and Curve-style Stableswap. Four canonical pools are pre-configured via MockProvider; every tool call builds a fresh synthetic twin, runs the primitive, and returns a typed dataclass result.

---

## Install

```bash
pip install defipy[mcp]
```

The `mcp` extra pulls in the MCP Python SDK. Core defipy (primitives, twin, tools) has no MCP dependency.

To run from source:

```bash
git clone https://github.com/defipy-devs/defipy
cd defipy
pip install -e .[mcp]
```

---

## Run standalone (stdio transport)

```bash
python python/mcp/defipy_mcp_server.py
```

The server reads MCP stdio frames on stdin and writes responses on stdout. Every tool invocation logs one line of structured JSON to **stderr** — this is the v2.0 observability surface.

Use this for smoke-testing; real use happens through an MCP client.

---

## Claude Desktop config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "defipy": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/defipy/python/mcp/defipy_mcp_server.py"
      ]
    }
  }
}
```

Restart Claude Desktop. The DeFiPy tools appear in the MCP tool tray (hammer icon).

On Linux the config path is `~/.config/Claude/claude_desktop_config.json`; on Windows `%APPDATA%\Claude\claude_desktop_config.json`.

---

## Claude Code config

```bash
claude mcp add defipy \
    /absolute/path/to/venv/bin/python \
    /absolute/path/to/defipy/python/mcp/defipy_mcp_server.py
```

Alternatively, commit a `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "defipy": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/defipy/python/mcp/defipy_mcp_server.py"]
    }
  }
}
```

---

## Example questions to try

1. **Position diagnostics.** "I have 10 LP tokens in a 50/50 ETH/DAI Balancer pool where I deposited 1000 ETH and 100000 DAI. What's my IL if ETH drops 30%?"
2. **Pool health.** "Is the ETH/DAI V2 pool healthy? Any rug signals?"
3. **Depeg risk.** "How exposed is a USDC/DAI stableswap position to a 5% USDC depeg versus just holding the tokens?"

Claude reads the tool descriptions, picks the appropriate tool + pool recipe, and returns a structured answer.

---

## Available tools

| Tool | Protocol | What it does |
|---|---|---|
| `AnalyzePosition` | V2 / V3 | PnL decomposition (IL, fees, net) |
| `AnalyzeBalancerPosition` | Balancer 2-asset | PnL with weight effects |
| `AnalyzeStableswapPosition` | Stableswap 2-asset | PnL with amplification effects |
| `SimulatePriceMove` | V2 / V3 | "What if price moves X%?" |
| `SimulateBalancerPriceMove` | Balancer 2-asset | Same, weighted-pool math |
| `SimulateStableswapPriceMove` | Stableswap 2-asset | Same, invariant expansion |
| `CheckPoolHealth` | V2 / V3 | TVL, reserves, LP concentration, activity |
| `DetectRugSignals` | V2 / V3 | Threshold-based rug flags |
| `CalculateSlippage` | V2 / V3 | Slippage, price impact, max trade size |
| `AssessDepegRisk` | Stableswap 2-asset | IL across depeg levels + V2 benchmark |

Full schemas: `python -c "from defipy.tools import get_schemas; import json; print(json.dumps(get_schemas('mcp'), indent=2))"`.

---

## Pool recipes available

| Recipe | Protocol | Reserves |
|---|---|---|
| `eth_dai_v2` | Uniswap V2 | 1000 ETH / 100000 DAI |
| `eth_dai_v3` | Uniswap V3 | 1000 ETH / 100000 DAI, full-range, fee=3000 |
| `eth_dai_balancer_50_50` | Balancer 2-asset | 1000 ETH / 100000 DAI, 50/50 |
| `usdc_dai_stableswap_A10` | Stableswap 2-asset | 100000 USDC / 100000 DAI, A=10 |

Each tool is restricted to the recipes it's compatible with (e.g., `AnalyzeBalancerPosition` only accepts `eth_dai_balancer_50_50`). Incompatible combinations return a structured error.

---

## Viewing receipts

Every tool invocation writes one line of JSON to the server's stderr:

```json
{"ts": "2026-04-23T22:31:14.479Z", "tool": "AnalyzePosition", "pool_id": "eth_dai_v2", "args": {...}, "status": "ok", "duration_ms": 0.26, "result_summary": "diagnosis=il_dominant, net_pnl=-1999.80"}
```

On error:

```json
{"ts": "...", "tool": "...", "status": "error", "error_type": "IncompatiblePool", "error_message": "..."}
```

Claude Desktop surfaces MCP stderr through its developer console — enable via Help → Developer → Toggle Developer Tools, then watch the Console tab while tools run.

Claude Code writes MCP stderr to `~/.claude/mcp-logs/defipy.log` (verify with your Claude Code version).

---

## Limitations (v2.0)

- **MockProvider only.** Synthetic pools only; no live chain reads. `LiveProvider` ships in v2.1.
- **User-supplied position numbers.** Entry amounts, holding periods, LP token counts come from the user's question — not from chain state.
- **Read-only.** No swaps, no plans, no signing. Pure analytics.
- **10 curated tools** out of 22 shipped primitives. See [doc/execution/V2_TOOL_SET.md](../../doc/execution/V2_TOOL_SET.md) for the curation rationale.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`** — install the extra: `pip install defipy[mcp]`.

**Claude Desktop doesn't show tools** — check the developer console for MCP errors; most commonly a path typo in `claude_desktop_config.json`. Restart the app after every config edit.

**Tool call returns "not compatible with pool"** — Claude picked an incompatible recipe. Either rephrase the question to make the protocol unambiguous, or tell Claude which pool recipe to use.

**`gmpy2` compilation fails on install** — `gmpy2` needs GMP/MPFR/MPC headers. On macOS: `brew install gmp mpfr mpc`. On Debian/Ubuntu: `apt install libgmp-dev libmpfr-dev libmpc-dev`.
