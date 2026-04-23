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

from dataclasses import dataclass
from typing import Any

from defipy.primitives.position import (
    AnalyzePosition,
    AnalyzeBalancerPosition,
    AnalyzeStableswapPosition,
    SimulatePriceMove,
    SimulateBalancerPriceMove,
    SimulateStableswapPriceMove,
)
from defipy.primitives.pool_health import CheckPoolHealth, DetectRugSignals
from defipy.primitives.risk import AssessDepegRisk
from defipy.primitives.execution import CalculateSlippage


# Parameter names that are supplied by the dispatch layer (e.g. the Day 3
# MCP server), not by the LLM. These are filtered out of drift-test
# comparisons and never appear in a tool's input_schema. `lp` is the
# pool/exchange object; `token_in` and `depeg_token` are ERC20 objects
# resolved from context by the dispatch layer.
DISPATCH_SUPPLIED_PARAMS = frozenset({"self", "lp", "token_in", "depeg_token"})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    primitive_cls: type
    input_schema: dict
    signature_params: tuple


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "AnalyzePosition": ToolSpec(
        name="AnalyzePosition",
        description=(
            "Analyze why a Uniswap V2 or V3 LP position is gaining or losing "
            "money. Decomposes PnL into impermanent loss, accumulated fees, "
            "and net result, with optional real APR if a holding period is "
            "supplied. Returns current value, hold value, IL percentage, fee "
            "income, net PnL, real APR, and a diagnosis label."
        ),
        primitive_cls=AnalyzePosition,
        signature_params=(
            "lp_init_amt",
            "entry_x_amt",
            "entry_y_amt",
            "lwr_tick",
            "upr_tick",
            "holding_period_days",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "lp_init_amt": {
                    "type": "number",
                    "description": "LP token amount held by the position (position size in human units).",
                },
                "entry_x_amt": {
                    "type": "number",
                    "description": "Amount of token0 originally deposited at position entry.",
                },
                "entry_y_amt": {
                    "type": "number",
                    "description": "Amount of token1 originally deposited at position entry.",
                },
                "lwr_tick": {
                    "type": ["integer", "null"],
                    "description": "Lower tick of the position (V3 positions only; null for V2).",
                },
                "upr_tick": {
                    "type": ["integer", "null"],
                    "description": "Upper tick of the position (V3 positions only; null for V2).",
                },
                "holding_period_days": {
                    "type": ["number", "null"],
                    "description": "Optional holding period in days. If supplied, real_apr is annualized from net_pnl.",
                },
            },
            "required": ["lp_init_amt", "entry_x_amt", "entry_y_amt"],
        },
    ),
    "AnalyzeBalancerPosition": ToolSpec(
        name="AnalyzeBalancerPosition",
        description=(
            "Analyze a 2-asset Balancer weighted-pool LP position's PnL. "
            "Decomposes impermanent loss using the weighted-pool formula "
            "where the base token's weight affects IL magnitude. Values "
            "are denominated in opp-token units per BalancerImpLoss's "
            "convention; fee income is not attributed in v1 because "
            "Balancer pools only expose vault-level fees with no per-LP "
            "attribution."
        ),
        primitive_cls=AnalyzeBalancerPosition,
        signature_params=(
            "lp_init_amt",
            "entry_base_amt",
            "entry_opp_amt",
            "holding_period_days",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "lp_init_amt": {
                    "type": "number",
                    "description": "Pool shares held by this position, in human units.",
                },
                "entry_base_amt": {
                    "type": "number",
                    "description": "Amount of base (first) token originally deposited.",
                },
                "entry_opp_amt": {
                    "type": "number",
                    "description": "Amount of opp (second) token originally deposited.",
                },
                "holding_period_days": {
                    "type": ["number", "null"],
                    "description": "Optional holding period in days. If supplied, real_apr is annualized from net_pnl.",
                },
            },
            "required": ["lp_init_amt", "entry_base_amt", "entry_opp_amt"],
        },
    ),
    "AnalyzeStableswapPosition": ToolSpec(
        name="AnalyzeStableswapPosition",
        description=(
            "Analyze a 2-asset Curve-style Stableswap LP position's PnL "
            "using the amplified-invariant IL formula where small depegs "
            "can produce surprisingly large IL at high A. Values are in "
            "peg-numeraire (tokens valued 1:1); fee income is not attributed "
            "in v1 (pool-global only); positions whose implied alpha is in "
            "the unreachable regime return None on il_percentage, net_pnl, "
            "and real_apr."
        ),
        primitive_cls=AnalyzeStableswapPosition,
        signature_params=(
            "lp_init_amt",
            "entry_amounts",
            "holding_period_days",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "lp_init_amt": {
                    "type": "number",
                    "description": "LP tokens held by this position, in human units.",
                },
                "entry_amounts": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Per-token entry amounts in pool insertion order. Exactly 2 entries (2-asset pools only in v1).",
                },
                "holding_period_days": {
                    "type": ["number", "null"],
                    "description": "Optional holding period in days. If supplied, real_apr is annualized from net_pnl.",
                },
            },
            "required": ["lp_init_amt", "entry_amounts"],
        },
    ),
    "SimulatePriceMove": ToolSpec(
        name="SimulatePriceMove",
        description=(
            "Project a Uniswap V2 or V3 LP position's value at a hypothetical "
            "price change from the CURRENT pool state (not from entry). A "
            "price_change_pct of -0.30 asks 'what if price drops 30% from "
            "here'. Returns new value, IL at the simulated price, and "
            "percentage change in position value. Fee projection is not "
            "modeled (always null)."
        ),
        primitive_cls=SimulatePriceMove,
        signature_params=(
            "price_change_pct",
            "position_size_lp",
            "lwr_tick",
            "upr_tick",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "price_change_pct": {
                    "type": "number",
                    "description": "Fractional price change from current price. Must be > -1.0. Example: -0.30 models a 30% drop.",
                },
                "position_size_lp": {
                    "type": "number",
                    "description": "LP tokens held by the position, in human units. Must be > 0.",
                },
                "lwr_tick": {
                    "type": ["integer", "null"],
                    "description": "Lower tick of the position (V3 only; null for V2).",
                },
                "upr_tick": {
                    "type": ["integer", "null"],
                    "description": "Upper tick of the position (V3 only; null for V2).",
                },
            },
            "required": ["price_change_pct", "position_size_lp"],
        },
    ),
    "SimulateBalancerPriceMove": ToolSpec(
        name="SimulateBalancerPriceMove",
        description=(
            "Project a 2-asset Balancer weighted-pool LP position's value at "
            "a hypothetical price change from the CURRENT pool state. The "
            "shock is applied to the base-token price in opp units; IL "
            "depends on both the shock magnitude and the pool's weights. "
            "Returns new value in opp-numeraire, IL at the simulated price, "
            "and percentage change."
        ),
        primitive_cls=SimulateBalancerPriceMove,
        signature_params=("price_change_pct", "lp_init_amt"),
        input_schema={
            "type": "object",
            "properties": {
                "price_change_pct": {
                    "type": "number",
                    "description": "Fractional price change from current spot. Must be > -1.0. Example: -0.30 models a 30% drop in base-in-opp terms.",
                },
                "lp_init_amt": {
                    "type": "number",
                    "description": "Pool shares held by this position, in human units. Must be > 0.",
                },
            },
            "required": ["price_change_pct", "lp_init_amt"],
        },
    ),
    "SimulateStableswapPriceMove": ToolSpec(
        name="SimulateStableswapPriceMove",
        description=(
            "Project a 2-asset Curve-style Stableswap LP position's value at "
            "a hypothetical depeg from the CURRENT pool state. The shock "
            "multiplies the pool's current alpha by (1 + price_change_pct); "
            "at high A, large shocks may be physically unreachable and in "
            "that case new_value, il_at_new_price, and value_change_pct are "
            "returned as null. Values are in peg-numeraire."
        ),
        primitive_cls=SimulateStableswapPriceMove,
        signature_params=("price_change_pct", "lp_init_amt"),
        input_schema={
            "type": "object",
            "properties": {
                "price_change_pct": {
                    "type": "number",
                    "description": "Fractional shock applied to current alpha. Must be > -1.0. Simulated alpha = current_alpha * (1 + price_change_pct).",
                },
                "lp_init_amt": {
                    "type": "number",
                    "description": "LP tokens held by this position, in human units. Must be > 0.",
                },
            },
            "required": ["price_change_pct", "lp_init_amt"],
        },
    ),
    "CheckPoolHealth": ToolSpec(
        name="CheckPoolHealth",
        description=(
            "Snapshot pool-level health metrics for a Uniswap V2 or V3 pool: "
            "TVL in token0 numeraire, reserves, accumulated fees, LP "
            "concentration, and swap activity. Answers 'is this a pool I "
            "would deposit into?' at the pool level (not position level). "
            "num_swaps and fee_accrual_rate_recent are V2-only; V3 returns "
            "null for these because V3 has no per-swap history array."
        ),
        primitive_cls=CheckPoolHealth,
        signature_params=("recent_window",),
        input_schema={
            "type": "object",
            "properties": {
                "recent_window": {
                    "type": ["integer", "null"],
                    "description": "Rolling window size for fee_accrual_rate_recent, in swap counts. Default 20. V2-only; ignored for V3.",
                },
            },
            "required": [],
        },
    ),
    "DetectRugSignals": ToolSpec(
        name="DetectRugSignals",
        description=(
            "Detect rug-pull signals on a Uniswap V2 or V3 pool via three "
            "threshold checks: suspiciously low TVL, top-LP concentration "
            "above a limit, and inactive-pool-with-liquidity. Composes over "
            "CheckPoolHealth and returns per-signal booleans plus a "
            "count-based risk level (low/medium/high/critical). The "
            "inactive-with-liquidity signal is V2-only; V3 pools report "
            "False for it with a note in details."
        ),
        primitive_cls=DetectRugSignals,
        signature_params=("lp_concentration_threshold", "tvl_floor"),
        input_schema={
            "type": "object",
            "properties": {
                "lp_concentration_threshold": {
                    "type": ["number", "null"],
                    "description": "Top-LP share (strict-greater-than) that triggers the concentration signal. In (0, 1]; default 0.90; pass 1.0 to disable.",
                },
                "tvl_floor": {
                    "type": ["number", "null"],
                    "description": "Minimum acceptable TVL in token0 numeraire. Values at or below fire the tvl_suspiciously_low signal. Default 10.0 is nominal; override for your pair.",
                },
            },
            "required": [],
        },
    ),
    "CalculateSlippage": ToolSpec(
        name="CalculateSlippage",
        description=(
            "Calculate slippage and price-impact decomposition for a proposed "
            "swap on a Uniswap V2 or V3 pool. Returns spot vs execution price, "
            "slippage percentage, slippage cost in output-token units, and "
            "price impact. Also returns the maximum trade size that stays "
            "within 1% slippage for V2 pools; V3 returns null for that field "
            "because tick-crossing math has not yet been inverted."
        ),
        primitive_cls=CalculateSlippage,
        signature_params=("amount_in", "lwr_tick", "upr_tick"),
        input_schema={
            "type": "object",
            "properties": {
                "amount_in": {
                    "type": "number",
                    "description": "Amount of token_in to trade, in human units. Must be > 0.",
                },
                "lwr_tick": {
                    "type": ["integer", "null"],
                    "description": "Lower tick of the position (V3 only; null for V2).",
                },
                "upr_tick": {
                    "type": ["integer", "null"],
                    "description": "Upper tick of the position (V3 only; null for V2).",
                },
            },
            "required": ["amount_in"],
        },
    ),
    "AssessDepegRisk": ToolSpec(
        name="AssessDepegRisk",
        description=(
            "Quantify a 2-asset Curve-style Stableswap LP position's exposure "
            "to a stablecoin depeg. Computes IL at multiple depeg levels "
            "(default 2%, 5%, 10%, 20%, 50%) via the closed-form "
            "stableswap-invariant expansion, with an optional V2 "
            "constant-product benchmark at each level. Some depeg levels "
            "are physically unreachable at high A — unreachable scenarios "
            "return null on il_pct, lp_value_at_depeg, and "
            "hold_value_at_depeg; the V2 benchmark stays populated."
        ),
        primitive_cls=AssessDepegRisk,
        signature_params=("lp_init_amt", "depeg_levels", "compare_v2"),
        input_schema={
            "type": "object",
            "properties": {
                "lp_init_amt": {
                    "type": "number",
                    "description": "LP tokens held, in human units. Must be > 0.",
                },
                "depeg_levels": {
                    "type": ["array", "null"],
                    "items": {"type": "number"},
                    "description": "Depeg magnitudes as fractions in (0, 1). Default [0.02, 0.05, 0.10, 0.20, 0.50].",
                },
                "compare_v2": {
                    "type": ["boolean", "null"],
                    "description": "If true (default), each scenario reports the equivalent V2 constant-product IL at the same price deviation.",
                },
            },
            "required": ["lp_init_amt"],
        },
    ),
}


def list_tool_names() -> list[str]:
    """Return the sorted list of tool names currently in the registry."""
    return sorted(TOOL_REGISTRY.keys())
