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

"""
Smoke test for conftest.py fixtures.

Confirms v2_setup and v3_setup construct valid LP state without exercising
any primitive logic. If these tests fail, the problem is in conftest.py
itself — not in any primitive under test. This isolates scaffolding
failures from primitive-logic failures.

Keep these tests minimal; they're infrastructure, not primitive coverage.
"""


class TestV2SetupFixture:

    def test_v2_setup_lp_exists(self, v2_setup):
        assert v2_setup.lp is not None

    def test_v2_setup_tokens_named_correctly(self, v2_setup):
        assert v2_setup.eth.token_name == "ETH"
        assert v2_setup.dai.token_name == "DAI"

    def test_v2_setup_lp_init_amt_positive(self, v2_setup):
        assert v2_setup.lp_init_amt > 0

    def test_v2_setup_entry_amounts_match_constants(self, v2_setup):
        assert v2_setup.entry_x_amt == 1000.0
        assert v2_setup.entry_y_amt == 100000.0


class TestV3SetupFixture:

    def test_v3_setup_lp_exists(self, v3_setup):
        assert v3_setup.lp is not None

    def test_v3_setup_tokens_named_correctly(self, v3_setup):
        assert v3_setup.eth.token_name == "ETH"
        assert v3_setup.dai.token_name == "DAI"

    def test_v3_setup_lp_init_amt_positive(self, v3_setup):
        assert v3_setup.lp_init_amt > 0

    def test_v3_setup_tick_range_valid(self, v3_setup):
        assert v3_setup.lwr_tick < v3_setup.upr_tick
