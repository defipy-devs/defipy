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

"""Import smoke tests — exercise every shipped sub-package.

These tests would fail in a broken install (which the editable install
masks by pointing straight at the source tree). Kept in the normal
test suite as a continuous guard against setup.py packages=[] drift.
"""


def test_defipy_tools_importable():
    from defipy.tools import get_schemas, TOOL_REGISTRY, list_tool_names  # noqa: F401
    assert len(get_schemas("mcp")) == 10


def test_defipy_twin_importable():
    from defipy.twin import (  # noqa: F401
        MockProvider, StateTwinBuilder, StateTwinProvider,
        PoolSnapshot, V2PoolSnapshot, V3PoolSnapshot,
        BalancerPoolSnapshot, StableswapPoolSnapshot, LiveProvider,
    )
    assert MockProvider().list_recipes() == sorted([
        "eth_dai_v2", "eth_dai_v3",
        "eth_dai_balancer_50_50", "usdc_dai_stableswap_A10",
    ])


def test_each_primitive_subpackage_importable():
    from defipy.primitives.position import AnalyzePosition
    from defipy.primitives.pool_health import CheckPoolHealth
    from defipy.primitives.risk import AssessDepegRisk
    from defipy.primitives.execution import CalculateSlippage
    from defipy.primitives.optimization import EvaluateRebalance
    from defipy.primitives.comparison import CompareProtocols
    from defipy.primitives.portfolio import AggregatePortfolio

    for cls in (AnalyzePosition, CheckPoolHealth, AssessDepegRisk,
                CalculateSlippage, EvaluateRebalance,
                CompareProtocols, AggregatePortfolio):
        assert callable(cls)
