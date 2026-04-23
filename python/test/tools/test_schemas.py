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

import pytest

from defipy.tools import get_schemas, list_tool_names, TOOL_REGISTRY


# The V2_TOOL_SET.md Day 1 verification gate.
EXPECTED_NAMES = {
    "AnalyzePosition",
    "AnalyzeBalancerPosition",
    "AnalyzeStableswapPosition",
    "SimulatePriceMove",
    "SimulateBalancerPriceMove",
    "SimulateStableswapPriceMove",
    "CheckPoolHealth",
    "DetectRugSignals",
    "CalculateSlippage",
    "AssessDepegRisk",
}

# Description length cap: 2-4 sentences without being pedantic about
# counting. 500 chars is a generous ceiling that catches bloat while
# leaving room for the "names protocol + flags reachability" cases.
DESCRIPTION_MAX_CHARS = 500


# ─── V2_TOOL_SET.md gate tests ──────────────────────────────────────────────


def test_get_schemas_returns_ten():
    assert len(get_schemas("mcp")) == 10


def test_tool_names_match_curated_set():
    schemas = get_schemas("mcp")
    assert {s["name"] for s in schemas} == EXPECTED_NAMES


# ─── MCP format compliance ──────────────────────────────────────────────────


def test_each_schema_has_mcp_required_fields():
    for schema in get_schemas("mcp"):
        assert "name" in schema, schema
        assert "description" in schema, schema
        assert "inputSchema" in schema, schema


def test_descriptions_are_strings_under_length_cap():
    for schema in get_schemas("mcp"):
        desc = schema["description"]
        assert isinstance(desc, str)
        assert len(desc) > 0
        assert len(desc) <= DESCRIPTION_MAX_CHARS, (
            f"{schema['name']}: description is {len(desc)} chars "
            f"(cap {DESCRIPTION_MAX_CHARS})"
        )


def test_input_schemas_are_valid_json_schema():
    for schema in get_schemas("mcp"):
        input_schema = schema["inputSchema"]
        assert input_schema.get("type") == "object", schema["name"]
        assert isinstance(input_schema.get("properties"), dict), schema["name"]


def test_every_property_has_type_and_description():
    for schema in get_schemas("mcp"):
        for prop_name, prop in schema["inputSchema"]["properties"].items():
            assert "type" in prop, (
                f"{schema['name']}.{prop_name} missing 'type'"
            )
            assert "description" in prop, (
                f"{schema['name']}.{prop_name} missing 'description'"
            )


def test_required_fields_are_subset_of_properties():
    # Every entry in 'required' must appear as a key in 'properties';
    # otherwise the schema would demand a field it hasn't declared.
    for schema in get_schemas("mcp"):
        input_schema = schema["inputSchema"]
        required = input_schema.get("required", [])
        props = input_schema["properties"]
        for field in required:
            assert field in props, (
                f"{schema['name']}: required field {field!r} not in properties"
            )


# ─── Format selector ────────────────────────────────────────────────────────


def test_unsupported_format_raises_notimplementederror():
    with pytest.raises(NotImplementedError) as excinfo:
        get_schemas("openai")
    assert "v2.1" in str(excinfo.value)


def test_unsupported_format_raises_notimplementederror_anthropic():
    with pytest.raises(NotImplementedError) as excinfo:
        get_schemas("anthropic")
    assert "v2.1" in str(excinfo.value)


def test_default_format_is_mcp():
    # No-argument call should be equivalent to format="mcp".
    assert get_schemas() == get_schemas("mcp")


# ─── Registry/schema consistency ────────────────────────────────────────────


def test_tool_name_in_schema_matches_registry_key():
    for key, spec in TOOL_REGISTRY.items():
        assert spec.name == key, (
            f"Registry key {key!r} does not match spec.name {spec.name!r}"
        )


def test_list_tool_names_sorted():
    names = list_tool_names()
    assert names == sorted(TOOL_REGISTRY.keys())
    assert set(names) == EXPECTED_NAMES
