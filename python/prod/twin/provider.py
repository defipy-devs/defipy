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

from abc import ABC, abstractmethod

from defipy.twin.snapshot import PoolSnapshot


class StateTwinProvider(ABC):
    """Source of pool snapshots for State Twin construction.

    Implementations decide where snapshots come from — synthetic
    recipes (MockProvider), live chain reads (LiveProvider, v2.1+),
    cached blocks, fork state, etc. The contract is protocol-agnostic:
    a provider returns a PoolSnapshot; StateTwinBuilder turns that
    into a concrete exchange object.

    The signature widened in v2.1 from `snapshot(pool_id)` to
    `snapshot(pool_id, **kwargs)`. MockProvider treats `pool_id` as a
    recipe name and ignores kwargs; LiveProvider treats `pool_id` as a
    "<protocol>:<address>" string and uses kwargs (e.g. `block_number`)
    to refine the read. Existing v2.0 single-arg callers continue to
    work unchanged.
    """

    @abstractmethod
    def snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot:
        """Return a PoolSnapshot for the given pool identifier.

        pool_id semantics are provider-specific. Refer to the concrete
        provider's docstring for its accepted formats.

        kwargs are provider-specific options (e.g. block_number for
        LiveProvider). Providers that don't recognize a given kwarg
        should silently ignore it rather than raise — keeps callers
        portable across providers.
        """
        ...
