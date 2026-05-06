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

"""Module-level invariants for LiveProvider.

These tests cover always-true properties of the LiveProvider class
regardless of which protocol is implemented. The set is intentionally
tiny — V2-implementation coverage lives in test_live_provider_v2.py,
V3 in test_live_provider_v3.py, and live-RPC verification in the
*_live.py companions.

After Phase 2 (V3 LiveProvider lands), the only protocols that still
raise NotImplementedError are balancer + stableswap (v2.2+).
"""

import pytest

from defipy.twin import LiveProvider


# ─── Constructor (preserved from v2.0) ─────────────────────────────────────


def test_live_provider_stores_rpc_url():
    p = LiveProvider("http://localhost:8545")
    assert p.rpc_url == "http://localhost:8545"


# ─── Lazy import discipline (preserved from v2.0) ──────────────────────────


def test_live_provider_module_does_not_import_web3():
    """Core defipy promises chain-lib dependency-freedom at import time.

    web3 may already be present in sys.modules from other installs
    (web3scout via [book], or via the [chain] / [anvil] extras). This
    test guards that *this* module's own source doesn't contribute —
    no top-level `from web3 import ...` slipped into live_provider.py.
    The web3 import lives in `_rpc.make_client()`, called only on
    `.snapshot()`.
    """
    import defipy.twin.live_provider as lp_module
    assert "web3" not in dir(lp_module)
    assert "Web3" not in dir(lp_module)
    assert "web3scout" not in dir(lp_module)


# ─── Phase-boundary error messages ─────────────────────────────────────────


def test_balancer_and_stableswap_pool_ids_raise_not_implemented_v22():
    """Balancer + Stableswap LiveProviders are v2.2+ work."""
    for protocol in ("balancer", "stableswap"):
        with pytest.raises(NotImplementedError) as excinfo:
            LiveProvider("http://x").snapshot("{}:0xabc".format(protocol))
        msg = str(excinfo.value)
        assert "v2.2" in msg, (
            "Expected v2.2 reference for {} protocol; got {!r}"
            .format(protocol, msg)
        )
        assert "MockProvider" in msg
