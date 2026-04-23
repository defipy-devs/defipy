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

from defipy.twin.provider import StateTwinProvider
from defipy.twin.snapshot import (
    PoolSnapshot,
    V2PoolSnapshot,
    V3PoolSnapshot,
    BalancerPoolSnapshot,
    StableswapPoolSnapshot,
)


class MockProvider(StateTwinProvider):
    """Synthetic pool snapshots for notebooks, tests, and demos.

    Ships four canonical recipes matching V2_TOOL_SET.md coverage:

      - "eth_dai_v2"                   Uniswap V2, 1000 ETH / 100000 DAI
      - "eth_dai_v3"                   Uniswap V3, same reserves, full-range
      - "eth_dai_balancer_50_50"       Balancer 2-asset, 50/50 weights
      - "usdc_dai_stableswap_A10"      Stableswap 2-asset, A=10

    Recipes are callables (not cached instances) so each call returns
    a fresh snapshot; this prevents shared-mutation bugs where one
    test alters a snapshot and another test inherits the alteration.

    Custom pools in v2.0 happen by constructing a PoolSnapshot
    directly and passing to StateTwinBuilder; MockProvider is
    intentionally recipe-only.
    """

    RECIPES = {
        "eth_dai_v2": lambda: V2PoolSnapshot(
            pool_id = "eth_dai_v2",
            token0_name = "ETH",
            token1_name = "DAI",
            reserve0 = 1000.0,
            reserve1 = 100000.0,
        ),
        "eth_dai_v3": lambda: V3PoolSnapshot(
            pool_id = "eth_dai_v3",
            token0_name = "ETH",
            token1_name = "DAI",
            reserve0 = 1000.0,
            reserve1 = 100000.0,
            fee = 3000,
            tick_spacing = 60,
            # lwr_tick / upr_tick default to full-range via __post_init__.
        ),
        "eth_dai_balancer_50_50": lambda: BalancerPoolSnapshot(
            pool_id = "eth_dai_balancer_50_50",
            token0_name = "ETH",
            token1_name = "DAI",
            reserve0 = 1000.0,
            reserve1 = 100000.0,
            weight0 = 0.5,
            weight1 = 0.5,
            pool_shares_init = 100.0,
        ),
        "usdc_dai_stableswap_A10": lambda: StableswapPoolSnapshot(
            pool_id = "usdc_dai_stableswap_A10",
            token_names = ["USDC", "DAI"],
            reserves = [100000.0, 100000.0],
            A = 10,
        ),
    }

    def snapshot(self, pool_id: str) -> PoolSnapshot:
        if pool_id not in self.RECIPES:
            raise ValueError(
                "MockProvider: unknown recipe {!r}. Available: {}"
                .format(pool_id, sorted(self.RECIPES.keys()))
            )
        return self.RECIPES[pool_id]()

    def list_recipes(self) -> list[str]:
        return sorted(self.RECIPES.keys())
