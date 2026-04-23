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

# Re-export the 4 canonical fixture builders from the primitives
# conftest so the twin builder-consistency tests can compare built
# lp objects against the known-good reference construction without
# duplicating ~80 lines of fixture code. python/test is on sys.path
# via python/test/conftest.py.
from primitives.conftest import (  # noqa: F401
    v2_setup,
    v3_setup,
    balancer_setup,
    stableswap_setup,
)
