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

import asyncio
import json

import pytest

import defipy_mcp_server as srv  # noqa: E402 — resolved via local conftest
from defipy.tools import TOOL_REGISTRY


def _run(coro):
    return asyncio.run(coro)


# ─── Schema wrapping ────────────────────────────────────────────────────────


def test_schema_wrapping_returns_ten_tools():
    wrapped = srv._wrap_schemas_with_pool_id()
    assert len(wrapped) == 10


def test_schema_wrapping_adds_pool_id_property_and_required():
    for w in srv._wrap_schemas_with_pool_id():
        props = w["inputSchema"]["properties"]
        required = w["inputSchema"]["required"]
        assert "pool_id" in props, w["name"]
        assert "pool_id" in required, w["name"]
        assert props["pool_id"]["type"] == "string"
        assert "enum" in props["pool_id"]


def test_schema_wrapping_pool_id_enum_matches_compatibility():
    wrapped = {w["name"]: w for w in srv._wrap_schemas_with_pool_id()}
    assert wrapped["AnalyzeBalancerPosition"]["inputSchema"]["properties"][
        "pool_id"]["enum"] == ["eth_dai_balancer_50_50"]
    assert set(wrapped["AnalyzePosition"]["inputSchema"]["properties"][
        "pool_id"]["enum"]) == {"eth_dai_v2", "eth_dai_v3"}


def test_schema_wrapping_adds_token_name_string_args():
    wrapped = {w["name"]: w for w in srv._wrap_schemas_with_pool_id()}
    slip_props = wrapped["CalculateSlippage"]["inputSchema"]["properties"]
    assert "token_in_name" in slip_props
    assert slip_props["token_in_name"]["type"] == "string"
    assert "token_in_name" in wrapped["CalculateSlippage"][
        "inputSchema"]["required"]

    depeg_props = wrapped["AssessDepegRisk"]["inputSchema"]["properties"]
    assert "depeg_token_name" in depeg_props


# ─── call_tool: ok paths ───────────────────────────────────────────────────


def test_call_tool_ok_returns_textcontent_with_dataclass_json():
    result = _run(srv.call_tool("AnalyzePosition", {
        "pool_id": "eth_dai_v2",
        "lp_init_amt": 1.0,
        "entry_x_amt": 1000,
        "entry_y_amt": 100000,
    }))
    assert len(result) == 1
    assert result[0].type == "text"
    payload = json.loads(result[0].text)
    assert "diagnosis" in payload
    assert "net_pnl" in payload


def test_call_tool_check_pool_health_v3():
    result = _run(srv.call_tool("CheckPoolHealth", {
        "pool_id": "eth_dai_v3",
    }))
    payload = json.loads(result[0].text)
    assert payload["version"] == "V3"


def test_call_tool_stableswap_depeg_risk_resolves_token_name():
    result = _run(srv.call_tool("AssessDepegRisk", {
        "pool_id": "usdc_dai_stableswap_A10",
        "lp_init_amt": 100.0,
        "depeg_token_name": "USDC",
    }))
    payload = json.loads(result[0].text)
    assert payload["depeg_token"] == "USDC"
    assert len(payload["scenarios"]) == 5


def test_call_tool_slippage_resolves_token_in_name():
    result = _run(srv.call_tool("CalculateSlippage", {
        "pool_id": "eth_dai_v2",
        "token_in_name": "DAI",
        "amount_in": 100.0,
    }))
    payload = json.loads(result[0].text)
    assert "slippage_pct" in payload
    assert payload["slippage_pct"] > 0


# ─── call_tool: error paths ────────────────────────────────────────────────


def test_call_tool_unknown_tool_returns_error():
    result = _run(srv.call_tool("BogusTool", {"pool_id": "eth_dai_v2"}))
    assert len(result) == 1
    assert "Error" in result[0].text
    assert "Unknown tool" in result[0].text


def test_call_tool_incompatible_pool_returns_error():
    result = _run(srv.call_tool("AnalyzeBalancerPosition", {
        "pool_id": "eth_dai_v2",
        "lp_init_amt": 100.0,
        "entry_base_amt": 1000,
        "entry_opp_amt": 100000,
    }))
    assert "not compatible" in result[0].text
    assert "eth_dai_balancer_50_50" in result[0].text


def test_call_tool_bad_primitive_args_returns_error():
    result = _run(srv.call_tool("SimulatePriceMove", {
        "pool_id": "eth_dai_v2",
        "price_change_pct": -5.0,   # must be > -1.0
        "position_size_lp": 1.0,
    }))
    assert "Error" in result[0].text


def test_call_tool_unknown_token_returns_error():
    result = _run(srv.call_tool("CalculateSlippage", {
        "pool_id": "eth_dai_v2",
        "token_in_name": "NOTATOKEN",
        "amount_in": 100.0,
    }))
    assert "Error" in result[0].text
    assert "NOTATOKEN" in result[0].text


def test_call_tool_strips_pool_id_from_primitive_args():
    # Implicit check: if pool_id were forwarded, AnalyzePosition would
    # raise because 'pool_id' isn't a .apply() parameter.
    result = _run(srv.call_tool("AnalyzePosition", {
        "pool_id": "eth_dai_v2",
        "lp_init_amt": 1.0,
        "entry_x_amt": 1000,
        "entry_y_amt": 100000,
    }))
    payload = json.loads(result[0].text)
    assert "diagnosis" in payload
    assert "pool_id" not in payload


# ─── Token resolution ─────────────────────────────────────────────────────


def test_resolve_token_v2_path():
    from defipy.twin import MockProvider, StateTwinBuilder
    lp = StateTwinBuilder().build(MockProvider().snapshot("eth_dai_v2"))
    tkn = srv._resolve_token(lp, "DAI")
    assert tkn is not None
    assert tkn.token_name == "DAI"


def test_resolve_token_v3_path():
    from defipy.twin import MockProvider, StateTwinBuilder
    lp = StateTwinBuilder().build(MockProvider().snapshot("eth_dai_v3"))
    tkn = srv._resolve_token(lp, "ETH")
    assert tkn.token_name == "ETH"


def test_resolve_token_balancer_path():
    from defipy.twin import MockProvider, StateTwinBuilder
    lp = StateTwinBuilder().build(
        MockProvider().snapshot("eth_dai_balancer_50_50"))
    tkn = srv._resolve_token(lp, "ETH")
    assert tkn.token_name == "ETH"


def test_resolve_token_stableswap_path():
    from defipy.twin import MockProvider, StateTwinBuilder
    lp = StateTwinBuilder().build(
        MockProvider().snapshot("usdc_dai_stableswap_A10"))
    tkn = srv._resolve_token(lp, "USDC")
    assert tkn.token_name == "USDC"


def test_resolve_token_unknown_raises():
    from defipy.twin import MockProvider, StateTwinBuilder
    lp = StateTwinBuilder().build(MockProvider().snapshot("eth_dai_v2"))
    with pytest.raises(ValueError) as excinfo:
        srv._resolve_token(lp, "NOPE")
    assert "NOPE" in str(excinfo.value)


# ─── Summarizer coverage ──────────────────────────────────────────────────


def test_summarizer_exists_for_every_registered_tool():
    # Every tool in the registry must have a one-line summarizer so
    # stderr receipts are readable for all 10 tools.
    missing = set(TOOL_REGISTRY.keys()) - set(srv._SUMMARIZERS.keys())
    assert not missing, "Missing summarizers for: {}".format(missing)


# ─── Receipt logging ──────────────────────────────────────────────────────


def test_receipt_emitted_on_ok(capsys):
    _run(srv.call_tool("CheckPoolHealth", {"pool_id": "eth_dai_v2"}))
    captured = capsys.readouterr()
    lines = [ln for ln in captured.err.strip().splitlines() if ln]
    assert lines, "expected at least one stderr line"
    event = json.loads(lines[-1])
    assert event["status"] == "ok"
    assert event["tool"] == "CheckPoolHealth"
    assert event["pool_id"] == "eth_dai_v2"
    assert "duration_ms" in event
    assert "result_summary" in event


def test_receipt_emitted_on_error(capsys):
    _run(srv.call_tool("AnalyzeBalancerPosition", {
        "pool_id": "eth_dai_v2",
        "lp_init_amt": 100.0,
        "entry_base_amt": 1000,
        "entry_opp_amt": 100000,
    }))
    captured = capsys.readouterr()
    lines = [ln for ln in captured.err.strip().splitlines() if ln]
    event = json.loads(lines[-1])
    assert event["status"] == "error"
    assert event["error_type"] == "IncompatiblePool"
    assert "eth_dai_balancer_50_50" in event["error_message"]


# ─── Fresh twin per call ──────────────────────────────────────────────────


def test_call_tool_builds_fresh_twin_per_call():
    # Invoke twice; the two internal lp objects must be distinct.
    # We spy via MockProvider.snapshot returning distinct snapshot
    # instances per call (Day 2 guarantee); separate build calls then
    # yield separate lp instances.
    from defipy.twin import MockProvider
    p = MockProvider()
    s1 = p.snapshot("eth_dai_v2")
    s2 = p.snapshot("eth_dai_v2")
    assert s1 is not s2
    # Dispatch once to verify end-to-end freshness with builder
    _run(srv.call_tool("CheckPoolHealth", {"pool_id": "eth_dai_v2"}))
    _run(srv.call_tool("CheckPoolHealth", {"pool_id": "eth_dai_v2"}))


# ─── Server wiring ────────────────────────────────────────────────────────


def test_build_server_returns_server_instance():
    from mcp.server import Server
    server = srv._build_server()
    assert isinstance(server, Server)
