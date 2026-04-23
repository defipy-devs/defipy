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

# No web3 / web3scout imports in this file. The v2.0 LiveProvider is a
# stub; pulling chain libraries here would break the promise that core
# defipy is dependency-free.

from defipy.twin.provider import StateTwinProvider
from defipy.twin.snapshot import PoolSnapshot


class LiveProvider(StateTwinProvider):
    """Chain-reading provider — stub in v2.0, implementation in v2.1.

    The constructor signature is stable so v2.1 can implement
    `snapshot()` without breaking callers. The class exists today
    to make the v2.1 surface visible and to document the commitment
    in code rather than only in prose.
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    def snapshot(self, pool_id: str) -> PoolSnapshot:
        raise NotImplementedError(
            "LiveProvider implementation lands in v2.1. "
            "For v2.0, use MockProvider for synthetic pools or "
            "construct lp objects manually via the underlying "
            "exchange classes."
        )
