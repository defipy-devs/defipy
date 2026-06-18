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

"""Unit tests for multicall_aggregate3_args (DeFiPy v2.2 Phase 1).

Tests the argument-bearing Multicall3 helper added in
defipy.twin._rpc. The helper encodes calldata (selector + ABI-encoded
args), batches through Multicall3.aggregate3, pins to a block, and
decodes each sub-call's return.

Infrastructure: a LOCAL, minimal fake Multicall3 w3 (below). It tests
the encode/decode round trip of the helper itself — the full
_fake_rpc.py extension that wires Balancer/Curve pool specs comes in
Phases 2/3. The fake's aggregate3().call(block_identifier=N) splits
each sub-call's calldata into selector ([:4]) + arg bytes ([4:]),
looks up a canned return value keyed by (target, selector, arg bytes),
ABI-encodes it per the known return types, and honors allow_failure by
returning (False, b"") for unknown keys.

Per test discipline: the canned values are run first, the actual
decoded values captured, then hardcoded below with comments (notably:
eth_abi decodes `address` to a LOWERCASE hex string, not EIP-55).
"""

import pytest

from defipy.twin._rpc import (
    multicall_aggregate3_args,
    MULTICALL3_ADDRESS,
    _MULTICALL3_ABI,
)


# ─── Local minimal fake Multicall3 w3 ──────────────────────────────────────


def _key(target, fn_sig, arg_types, args):
    """Canned-response key: (lowercased target, selector, arg bytes).

    Mirrors exactly how multicall_aggregate3_args builds calldata —
    selector from the signature, eth_abi-encoded args (b"" for no-arg).
    Keying on the raw arg bytes is what proves the helper dispatched
    the argument into calldata rather than dropping it.
    """
    from eth_utils import function_signature_to_4byte_selector
    from eth_abi import encode
    selector = function_signature_to_4byte_selector(fn_sig)
    arg_bytes = encode(arg_types, args) if arg_types else b""
    return (target.lower(), selector, arg_bytes)


class _BoundAgg:
    """Stand-in for aggregate3(encoded) — decode happens on .call()."""

    def __init__(self, w3, encoded):
        self._w3 = w3
        self._encoded = encoded

    def call(self, block_identifier=None):
        from eth_abi import encode
        # Record the envelope's block so the test can assert R1 pinning.
        self._w3.recorded_blocks.append(block_identifier)
        results = []
        for target, _allow_failure, call_data in self._encoded:
            selector = bytes(call_data[:4])
            arg_bytes = bytes(call_data[4:])
            key = (target.lower(), selector, arg_bytes)
            if key not in self._w3.returns:
                # Unknown sub-call: report a revert. The helper turns
                # this into a None slot (allow_failure) or a raise.
                results.append((False, b""))
                continue
            return_types, value = self._w3.returns[key]
            if len(return_types) == 1:
                encoded_ret = encode(return_types, [value])
            else:
                encoded_ret = encode(return_types, list(value))
            results.append((True, encoded_ret))
        return results


class _FakeFunctions:
    def __init__(self, w3):
        self._w3 = w3

    def aggregate3(self, encoded):
        return _BoundAgg(self._w3, encoded)


class _FakeContract:
    def __init__(self, w3):
        self.functions = _FakeFunctions(w3)


class _FakeEth:
    def __init__(self, w3):
        self._w3 = w3

    def contract(self, address=None, abi=None):
        # The helper only ever builds the Multicall3 proxy.
        return _FakeContract(self._w3)


class FakeMulticallWeb3:
    """Minimal web3.Web3 stand-in for the multicall helper."""

    def __init__(self, returns):
        self.returns = returns
        self.recorded_blocks = []
        self.eth = _FakeEth(self)

    def to_checksum_address(self, address):
        # Real for valid input (MULTICALL3_ADDRESS); identity fallback
        # for the placeholder addresses ("0xPOOL" etc.) used in tests.
        from eth_utils import to_checksum_address as _to_cs
        try:
            return _to_cs(address)
        except (ValueError, TypeError):
            return address


# ─── Canonical placeholder addresses / canned values ───────────────────────

POOL = "0xPOOL"
VAULT = "0xVAULT"

# Real mainnet token addresses used as canned coins()/getPoolTokens()
# returns. eth_abi decodes the `address` type to a LOWERCASE hex string
# (not EIP-55 checksummed), so the expectations below are lowercase.
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
DAI_LOWER = "0x6b175474e89094c44da98b954eedeac495271d0f"   # captured from eth_abi
USDC_LOWER = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # captured from eth_abi

POOL_ID = b"\x11" * 32

BLOCK = 19_500_000


# ─── Tests ─────────────────────────────────────────────────────────────────


def test_no_arg_call_decodes():
    """A no-arg getter (arg_types=[]) produces selector-only calldata
    and decodes to its canned scalar — same path the V3 no-arg getters
    take through this helper."""
    w3 = FakeMulticallWeb3({
        _key(POOL, "A()", [], []): (["uint256"], 2000),
    })
    out = multicall_aggregate3_args(
        w3, [(POOL, "A()", [], [], ["uint256"])], BLOCK,
    )
    assert out == [2000]


def test_single_arg_call_dispatches_argument():
    """coins(0) and coins(1) carry different calldata args and must map
    to different canned addresses — proving the arg is encoded into
    calldata and dispatched, not ignored."""
    w3 = FakeMulticallWeb3({
        _key(POOL, "coins(uint256)", ["uint256"], [0]): (["address"], DAI),
        _key(POOL, "coins(uint256)", ["uint256"], [1]): (["address"], USDC),
    })
    out = multicall_aggregate3_args(
        w3,
        [
            (POOL, "coins(uint256)", ["uint256"], [0], ["address"]),
            (POOL, "coins(uint256)", ["uint256"], [1], ["address"]),
        ],
        BLOCK,
    )
    # eth_abi lowercases decoded addresses.
    assert out == [DAI_LOWER, USDC_LOWER]


def test_multi_return_call_keeps_dynamic_arrays():
    """getPoolTokens(bytes32) returns (address[], uint256[], uint256).
    The helper returns the whole decoded tuple (len(decode_types) > 1),
    with the dynamic arrays intact."""
    tokens = [DAI, USDC]
    balances = [1000 * 10**18, 1000 * 10**6]
    last_change_block = 19_000_000
    w3 = FakeMulticallWeb3({
        _key(VAULT, "getPoolTokens(bytes32)", ["bytes32"], [POOL_ID]): (
            ["address[]", "uint256[]", "uint256"],
            (tokens, balances, last_change_block),
        ),
    })
    out = multicall_aggregate3_args(
        w3,
        [(
            VAULT, "getPoolTokens(bytes32)", ["bytes32"], [POOL_ID],
            ["address[]", "uint256[]", "uint256"],
        )],
        BLOCK,
    )
    assert len(out) == 1
    decoded_tokens, decoded_balances, decoded_last = out[0]
    # eth_abi returns dynamic arrays as tuples; addresses lowercased.
    assert tuple(decoded_tokens) == (DAI_LOWER, USDC_LOWER)
    assert tuple(decoded_balances) == (1000 * 10**18, 1000 * 10**6)
    assert decoded_last == 19_000_000


def test_allow_failure_returns_none_slot():
    """With allow_failure=True an unknown sub-call yields None in its
    slot; the surrounding good calls still decode. This is the Curve
    coin-count probe's path."""
    w3 = FakeMulticallWeb3({
        _key(POOL, "coins(uint256)", ["uint256"], [0]): (["address"], DAI),
        _key(POOL, "coins(uint256)", ["uint256"], [1]): (["address"], USDC),
        # No entry for coins(2) — that sub-call "reverts".
    })
    out = multicall_aggregate3_args(
        w3,
        [
            (POOL, "coins(uint256)", ["uint256"], [0], ["address"]),
            (POOL, "coins(uint256)", ["uint256"], [1], ["address"]),
            (POOL, "coins(uint256)", ["uint256"], [2], ["address"]),
        ],
        BLOCK,
        allow_failure=True,
    )
    assert out == [DAI_LOWER, USDC_LOWER, None]


def test_allow_failure_false_raises_naming_signature():
    """With allow_failure=False (default) an unknown sub-call raises
    RuntimeError naming the offending signature."""
    w3 = FakeMulticallWeb3({})   # nothing registered → every call reverts
    with pytest.raises(RuntimeError) as excinfo:
        multicall_aggregate3_args(
            w3,
            [(POOL, "coins(uint256)", ["uint256"], [0], ["address"])],
            BLOCK,
        )
    assert "coins(uint256)" in str(excinfo.value)


def test_block_pinning_on_envelope():
    """Every batch pins to the passed block_number (R1)."""
    w3 = FakeMulticallWeb3({
        _key(POOL, "A()", [], []): (["uint256"], 2000),
    })
    multicall_aggregate3_args(
        w3, [(POOL, "A()", [], [], ["uint256"])], BLOCK,
    )
    assert w3.recorded_blocks == [BLOCK]


def test_no_arg_and_arg_bearing_mixed_in_one_batch():
    """The helper serves no-arg and arg-bearing calls in a single
    batch — the property Phases 2/3 rely on (getPoolId()/A() alongside
    coins(i)/getPoolTokens(poolId))."""
    w3 = FakeMulticallWeb3({
        _key(POOL, "A()", [], []): (["uint256"], 2000),
        _key(POOL, "coins(uint256)", ["uint256"], [0]): (["address"], DAI),
    })
    out = multicall_aggregate3_args(
        w3,
        [
            (POOL, "A()", [], [], ["uint256"]),
            (POOL, "coins(uint256)", ["uint256"], [0], ["address"]),
        ],
        BLOCK,
    )
    assert out == [2000, DAI_LOWER]
