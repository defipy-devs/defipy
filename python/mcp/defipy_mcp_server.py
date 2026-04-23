# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2026 Ian Moore
# Email: defipy.devs@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

"""DeFiPy MCP Server — exposes the v2.0 curated tool set to MCP clients.

Run standalone (stdio transport):
    python python/mcp/defipy_mcp_server.py

Claude Desktop / Claude Code wiring: see python/mcp/README.md.

Architecture:
- Day 1's 10 schemas come from defipy.tools unchanged.
- Each schema is wrapped with a required `pool_id` field at exposure
  time so the LLM picks both a tool and a pool in one call.
- Every call_tool invocation builds a fresh MockProvider twin — no
  cross-call state. Matches DeFiPy's stateless primitive contract.
- Token-name strings in the LLM's args (for CalculateSlippage and
  AssessDepegRisk) are resolved to ERC20 objects at dispatch time.
- One JSON receipt per invocation emitted to stderr.
"""

import asyncio
import copy
import json
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from defipy.tools import TOOL_REGISTRY, get_schemas
from defipy.twin import MockProvider, StateTwinBuilder


# ─── Compatibility + dispatch config ─────────────────────────────────────────

_PROVIDER = MockProvider()
_BUILDER = StateTwinBuilder()

# Which MockProvider recipes each primitive can run against. Primitives
# whose scope is V2/V3-only accept the two Uniswap recipes; Balancer-
# and Stableswap-specific primitives accept only their matched recipe.
_COMPATIBLE_RECIPES = {
    "AnalyzePosition":              ["eth_dai_v2", "eth_dai_v3"],
    "SimulatePriceMove":            ["eth_dai_v2", "eth_dai_v3"],
    "CheckPoolHealth":              ["eth_dai_v2", "eth_dai_v3"],
    "DetectRugSignals":             ["eth_dai_v2", "eth_dai_v3"],
    "CalculateSlippage":            ["eth_dai_v2", "eth_dai_v3"],
    "AnalyzeBalancerPosition":      ["eth_dai_balancer_50_50"],
    "SimulateBalancerPriceMove":    ["eth_dai_balancer_50_50"],
    "AnalyzeStableswapPosition":    ["usdc_dai_stableswap_A10"],
    "SimulateStableswapPriceMove":  ["usdc_dai_stableswap_A10"],
    "AssessDepegRisk":              ["usdc_dai_stableswap_A10"],
}

# Tools with an object-typed parameter (ERC20) the LLM specifies as a
# token-name string. Maps tool name → schema-arg-name that carries the
# token-name. Resolved to an ERC20 at dispatch time via _resolve_token.
_TOKEN_ARG_RENAMES = {
    "CalculateSlippage":  ("token_in_name", "token_in"),
    "AssessDepegRisk":    ("depeg_token_name", "depeg_token"),
}


# ─── Schema wrapping ─────────────────────────────────────────────────────────


def _wrap_schemas_with_pool_id() -> list[dict]:
    """Inject a required pool_id field (with enum of compatible recipes) and
    rename ERC20 args to string-name args on each Day 1 schema.
    """
    wrapped = []
    for s in get_schemas("mcp"):
        w = copy.deepcopy(s)
        tool_name = w["name"]
        props = w["inputSchema"].setdefault("properties", {})
        required = w["inputSchema"].setdefault("required", [])

        props["pool_id"] = {
            "type": "string",
            "description": (
                "Which pool to analyze. Required. Must match one of the "
                "available MockProvider recipes; pick the one matching "
                "the protocol the user's question implies."
            ),
            "enum": sorted(_COMPATIBLE_RECIPES.get(tool_name, _PROVIDER.list_recipes())),
        }
        if "pool_id" not in required:
            required.append("pool_id")

        if tool_name in _TOKEN_ARG_RENAMES:
            schema_name, _primitive_name = _TOKEN_ARG_RENAMES[tool_name]
            props[schema_name] = {
                "type": "string",
                "description": (
                    "Token symbol (e.g., 'DAI', 'USDC'). Must be one of "
                    "the tokens in the selected pool."
                ),
            }
            if tool_name == "CalculateSlippage":
                if schema_name not in required:
                    required.append(schema_name)

        wrapped.append(w)
    return wrapped


# ─── Token resolution ────────────────────────────────────────────────────────


def _resolve_token(lp, token_name: str):
    """Resolve a token-name string to the ERC20 object the primitive expects.

    V2/V3 exchanges expose tokens via `lp.factory.token_from_exchange[lp.name]`.
    Balancer and Stableswap expose them via `lp.vault.get_token(name)`.
    """
    # V2 / V3 path.
    factory = getattr(lp, "factory", None)
    if factory is not None and hasattr(factory, "token_from_exchange"):
        tokens = factory.token_from_exchange.get(lp.name, {})
        if token_name in tokens:
            return tokens[token_name]

    # Balancer / Stableswap path.
    vault = getattr(lp, "vault", None)
    if vault is not None and hasattr(vault, "get_token"):
        if token_name in vault.get_names():
            return vault.get_token(token_name)

    raise ValueError(
        "Token {!r} not found in pool. Available: {}".format(
            token_name, _list_pool_tokens(lp)
        )
    )


def _list_pool_tokens(lp) -> list[str]:
    """Enumerate the token names in a pool for error messages."""
    factory = getattr(lp, "factory", None)
    if factory is not None and hasattr(factory, "token_from_exchange"):
        return sorted(factory.token_from_exchange.get(lp.name, {}).keys())
    vault = getattr(lp, "vault", None)
    if vault is not None and hasattr(vault, "get_names"):
        return list(vault.get_names())
    return []


# ─── Receipt logging ─────────────────────────────────────────────────────────


def _log_receipt(tool_name: str, pool_id: str, args: dict,
                 status: str, duration_ms: float,
                 result_summary: str = "",
                 error_type: str = "", error_message: str = "") -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "pool_id": pool_id,
        "args": args,
        "status": status,
        "duration_ms": round(duration_ms, 2),
    }
    if status == "ok":
        event["result_summary"] = result_summary
    else:
        event["error_type"] = error_type
        event["error_message"] = error_message
    print(json.dumps(event, ensure_ascii=True, default=str),
          file=sys.stderr, flush=True)


# ─── Result summarization ────────────────────────────────────────────────────
# Each summarizer returns a single short line describing the result.
# Kept deliberately minimal — stderr is the v2.0 observability story;
# structured ingestion lives in v2.1.


def _fmt_opt(v, spec=".4f"):
    if v is None:
        return "None"
    try:
        return format(v, spec)
    except (TypeError, ValueError):
        return str(v)


_SUMMARIZERS = {
    "AnalyzePosition": lambda r: (
        "diagnosis={}, net_pnl={}".format(r.diagnosis, _fmt_opt(r.net_pnl))
    ),
    "AnalyzeBalancerPosition": lambda r: (
        "diagnosis={}, net_pnl={}, alpha={}".format(
            r.diagnosis, _fmt_opt(r.net_pnl), _fmt_opt(r.alpha)
        )
    ),
    "AnalyzeStableswapPosition": lambda r: (
        "diagnosis={}, il_pct={}, A={}".format(
            r.diagnosis, _fmt_opt(r.il_percentage), r.A
        )
    ),
    "SimulatePriceMove": lambda r: (
        "new_value={}, il={}, value_change_pct={}".format(
            _fmt_opt(r.new_value), _fmt_opt(r.il_at_new_price),
            _fmt_opt(r.value_change_pct)
        )
    ),
    "SimulateBalancerPriceMove": lambda r: (
        "new_value={}, il={}, alpha={}".format(
            _fmt_opt(r.new_value), _fmt_opt(r.il_at_new_price),
            _fmt_opt(r.new_price_ratio)
        )
    ),
    "SimulateStableswapPriceMove": lambda r: (
        "new_value={}, il={}, alpha={}".format(
            _fmt_opt(r.new_value), _fmt_opt(r.il_at_new_price),
            _fmt_opt(r.new_price_ratio)
        )
    ),
    "CheckPoolHealth": lambda r: (
        "tvl={}, num_lps={}, has_activity={}".format(
            _fmt_opt(r.tvl_in_token0, ".2f"), r.num_lps, r.has_activity
        )
    ),
    "DetectRugSignals": lambda r: (
        "risk={}, signals={}".format(r.risk_level, r.signals_detected)
    ),
    "CalculateSlippage": lambda r: (
        "slippage_pct={}, price_impact_pct={}, max_at_1pct={}".format(
            _fmt_opt(r.slippage_pct), _fmt_opt(r.price_impact_pct),
            _fmt_opt(r.max_size_at_1pct, ".2f")
        )
    ),
    "AssessDepegRisk": lambda r: (
        "n_scenarios={}, current_dev={}".format(
            len(r.scenarios), _fmt_opt(r.current_peg_deviation)
        )
    ),
}


def _summarize(tool_name: str, result) -> str:
    fn = _SUMMARIZERS.get(tool_name)
    if fn is None:
        return "<no summarizer for {}>".format(tool_name)
    try:
        return fn(result)
    except Exception as e:
        return "<summarizer error: {}>".format(e)


# ─── Result serialization ────────────────────────────────────────────────────


def _serialize_result(result) -> str:
    """Convert a dataclass result into a human+LLM-readable JSON block."""
    if is_dataclass(result):
        payload = asdict(result)
    else:
        payload = result
    return json.dumps(payload, indent=2, default=str)


# ─── Core dispatch ───────────────────────────────────────────────────────────


async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a single tool invocation. Separable from the stdio loop
    so tests can exercise it directly."""

    t0 = time.monotonic()
    arguments = dict(arguments or {})
    pool_id = arguments.get("pool_id", "")

    # Unknown tool.
    if name not in TOOL_REGISTRY or name not in _COMPATIBLE_RECIPES:
        err = "Unknown tool: {}".format(name)
        _log_receipt(name, pool_id, arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type="UnknownTool", error_message=err)
        return [TextContent(type="text", text="Error: {}".format(err))]

    # Incompatible pool.
    if pool_id not in _COMPATIBLE_RECIPES[name]:
        err = ("Tool {!r} is not compatible with pool {!r}. "
               "Compatible pools: {}".format(
                   name, pool_id, _COMPATIBLE_RECIPES[name]))
        _log_receipt(name, pool_id, arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type="IncompatiblePool", error_message=err)
        return [TextContent(type="text", text="Error: {}".format(err))]

    # Build fresh twin per call.
    try:
        snapshot = _PROVIDER.snapshot(pool_id)
        lp = _BUILDER.build(snapshot)
    except Exception as e:
        _log_receipt(name, pool_id, arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type=type(e).__name__, error_message=str(e))
        return [TextContent(type="text",
                            text="Error building twin: {}".format(e))]

    # Strip pool_id (and token-name fields) from LLM args before calling
    # the primitive; resolve ERC20 objects as needed.
    primitive_args = {k: v for k, v in arguments.items() if k != "pool_id"}

    if name in _TOKEN_ARG_RENAMES:
        schema_name, primitive_name = _TOKEN_ARG_RENAMES[name]
        token_name = primitive_args.pop(schema_name, None)
        if token_name is not None:
            try:
                primitive_args[primitive_name] = _resolve_token(lp, token_name)
            except Exception as e:
                _log_receipt(name, pool_id, arguments, "error",
                             (time.monotonic() - t0) * 1000,
                             error_type=type(e).__name__, error_message=str(e))
                return [TextContent(type="text",
                                    text="Error resolving token: {}".format(e))]

    # Invoke primitive.
    try:
        spec = TOOL_REGISTRY[name]
        result = spec.primitive_cls().apply(lp, **primitive_args)
    except Exception as e:
        _log_receipt(name, pool_id, arguments, "error",
                     (time.monotonic() - t0) * 1000,
                     error_type=type(e).__name__, error_message=str(e))
        return [TextContent(type="text", text="Error: {}".format(e))]

    duration_ms = (time.monotonic() - t0) * 1000
    _log_receipt(name, pool_id, arguments, "ok", duration_ms,
                 result_summary=_summarize(name, result))
    return [TextContent(type="text", text=_serialize_result(result))]


# ─── Server init ─────────────────────────────────────────────────────────────


def _build_server() -> Server:
    """Configure the MCP server with list_tools + call_tool handlers.
    Extracted so tests can inspect the handler registration without
    opening the stdio transport.
    """
    server = Server("defipy")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name = s["name"],
                description = s["description"],
                inputSchema = s["inputSchema"],
            )
            for s in _wrap_schemas_with_pool_id()
        ]

    @server.call_tool()
    async def handle_call(name: str, arguments: dict) -> list[TextContent]:
        return await call_tool(name, arguments)

    return server


async def main():
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
