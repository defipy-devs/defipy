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

# python/mcp/ ships the standalone server script but is deliberately
# NOT a Python package (no __init__.py) — otherwise its directory name
# would shadow the installed `mcp` SDK when on sys.path.
#
# Load defipy_mcp_server directly by file path via importlib and
# expose it under the name `defipy_mcp_server` for test modules to
# import normally.
import importlib.util
import os
import sys

_SERVER_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "mcp", "defipy_mcp_server.py"
    )
)

if "defipy_mcp_server" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "defipy_mcp_server", _SERVER_PATH
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["defipy_mcp_server"] = _module
    _spec.loader.exec_module(_module)
