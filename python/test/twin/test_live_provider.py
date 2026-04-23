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

import sys

import pytest

from defipy.twin import LiveProvider


def test_live_provider_stores_rpc_url():
    p = LiveProvider("http://localhost:8545")
    assert p.rpc_url == "http://localhost:8545"


def test_live_provider_snapshot_raises_notimplemented():
    with pytest.raises(NotImplementedError):
        LiveProvider("http://anything").snapshot("x")


def test_live_provider_error_message_mentions_v21_and_mockprovider():
    with pytest.raises(NotImplementedError) as excinfo:
        LiveProvider("http://anything").snapshot("x")
    msg = str(excinfo.value)
    assert "v2.1" in msg
    assert "MockProvider" in msg


def test_live_provider_module_does_not_import_web3():
    # Core defipy promises to be dependency-free of chain libs. The
    # v2.0 LiveProvider stub must not pull web3 or web3scout into
    # sys.modules when its module is loaded. web3 might already be
    # present in the test process from other installed packages; the
    # test checks that *this* module's import graph doesn't contribute
    # to it by walking live_provider's own imports.
    import defipy.twin.live_provider as lp_module

    # Direct imports declared at module level shouldn't mention web3.
    module_source_globals = dir(lp_module)
    assert "web3" not in module_source_globals
    assert "web3scout" not in module_source_globals
