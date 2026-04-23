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

from defipy.tools.registry import TOOL_REGISTRY, ToolSpec


def get_schemas(format: str = "mcp") -> list[dict]:
    """Return tool schemas for all registered primitives.

    Parameters
    ----------
    format : str
        Schema format. Only "mcp" is supported in v2.0. Anthropic
        tool-use and OpenAI function-calling are deferred to v2.1.

    Returns
    -------
    list[dict]
        One dict per registered tool, following the MCP tool-definition
        surface (name, description, inputSchema).

    Raises
    ------
    NotImplementedError
        If format is anything other than "mcp".
    """
    if format != "mcp":
        raise NotImplementedError(
            f"Format '{format}' deferred to v2.1. Use format='mcp'."
        )
    return [_to_mcp_schema(spec) for spec in TOOL_REGISTRY.values()]


def _to_mcp_schema(spec: ToolSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": spec.input_schema,
    }
