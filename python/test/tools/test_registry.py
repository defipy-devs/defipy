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

import inspect

import pytest

from defipy.tools.registry import TOOL_REGISTRY, DISPATCH_SUPPLIED_PARAMS


# ─── Drift detection ────────────────────────────────────────────────────────
# Verifies that each primitive's .apply() parameter list (minus
# dispatch-supplied params like `lp`, `token_in`, `depeg_token`) matches
# both the registry's declared signature_params and the schema's
# properties keys. If a primitive's signature changes without the schema
# being updated, this test fires.


@pytest.mark.parametrize("tool_name", sorted(TOOL_REGISTRY.keys()))
def test_schema_matches_apply_signature(tool_name):
    spec = TOOL_REGISTRY[tool_name]

    sig = inspect.signature(spec.primitive_cls.apply)
    actual_params = tuple(
        p for p in sig.parameters if p not in DISPATCH_SUPPLIED_PARAMS
    )

    expected_params = spec.signature_params
    schema_props = tuple(spec.input_schema["properties"].keys())

    assert actual_params == expected_params, (
        f"{tool_name}: .apply() params {actual_params} "
        f"differ from declared signature_params {expected_params}"
    )
    assert schema_props == expected_params, (
        f"{tool_name}: input_schema properties {schema_props} "
        f"differ from declared signature_params {expected_params}"
    )


# ─── Registry sanity ────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool_name", sorted(TOOL_REGISTRY.keys()))
def test_primitive_cls_is_actually_a_class(tool_name):
    spec = TOOL_REGISTRY[tool_name]
    assert inspect.isclass(spec.primitive_cls), (
        f"{tool_name}: primitive_cls is not a class (got {spec.primitive_cls!r})"
    )


@pytest.mark.parametrize("tool_name", sorted(TOOL_REGISTRY.keys()))
def test_primitive_cls_has_apply_method(tool_name):
    spec = TOOL_REGISTRY[tool_name]
    apply = getattr(spec.primitive_cls, "apply", None)
    assert callable(apply), (
        f"{tool_name}: primitive class has no callable .apply"
    )


@pytest.mark.parametrize("tool_name", sorted(TOOL_REGISTRY.keys()))
def test_tool_class_name_matches_primitive_class_name(tool_name):
    # The tool name exposed to LLMs must match the primitive class name
    # verbatim (PascalCase). This is the curation rule from
    # V2_TOOL_SET.md — names are not remapped between library and MCP
    # surfaces.
    spec = TOOL_REGISTRY[tool_name]
    assert spec.primitive_cls.__name__ == tool_name
