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

"""Internal RPC client for LiveProvider.

Phase 1 strategy (per STATE_TWIN_PHASE_1_EXPANDED.md D1):

  - Reuse web3scout's ConnectW3 + ABILoad + FetchToken rather than
    rebuilding ABI loading and token decimal logic. They're already
    battle-tested in the v1 ImpermanentLossAgent.
  - Keep the import lazy: `from defipy.twin._rpc import RpcClient` is
    cheap and dependency-free; only constructing an `RpcClient` (or
    calling `make_client`) pulls web3 / web3scout into the process.
  - Expose a small surface (`get_w3()`, `block_number()`,
    `chain_id()`) so a `FakeRpcClient` in tests can mimic it without
    network access.

Phase 2 extends this module with Multicall3 batching for V3 reads
(see MULTICALL3_ADDRESS, multicall_aggregate3, load_v3_pool_contract
below). V2 LiveProvider stays sequential — one extra
`eth_getBlockByNumber` for the timestamp retrofit, no multicall.
"""

from typing import Optional


# RPC client interface (informal protocol):
#
#   class RpcClient:
#       def get_w3(self): ...           # web3.Web3-like instance
#       def block_number(self) -> int: ...   # current block_number
#       def chain_id(self) -> int: ...       # endpoint's chain id
#
# The production RpcClient (below) wraps web3scout's ConnectW3.
# The test FakeRpcClient (in python/test/twin/_fake_rpc.py) provides
# the same surface against canned responses.


def make_client(rpc_url: str):
    """Construct a production RpcClient backed by web3scout.ConnectW3.

    Imported lazily so `from defipy.twin import LiveProvider` works
    in the bare install. Only callers that actually want to hit the
    chain pay the [chain]-extras import cost.
    """
    try:
        from web3scout.utils.connect import ConnectW3
    except ImportError as e:
        raise ImportError(
            "LiveProvider requires the [chain] extra. Install with "
            "`pip install defipy[chain]` (or `defipy[book]` / "
            "`defipy[anvil]`, which carry the same web3 dep)."
        ) from e

    # ConnectW3 accepts a chain enum or, via RPCEnum.get_rpc()'s
    # fallthrough, a literal RPC URL string. The v1
    # ImpermanentLossAgent uses this same path.
    connector = ConnectW3(rpc_url)
    connector.apply()
    return RpcClient(connector)


class RpcClient:
    """Thin wrapper around web3scout's ConnectW3.

    Held by LiveProvider for the duration of a single .snapshot()
    call. Stateless across calls — every .snapshot() makes a fresh
    client via make_client().
    """

    def __init__(self, connector):
        self._connector = connector
        self._w3 = connector.get_w3()
        # C9: chain_id cached lazily on first read. Avoids re-querying
        # the endpoint on every .snapshot() call. Reset across RpcClient
        # instances (per-call construction in production keeps the
        # provider stateless).
        self._chain_id: Optional[int] = None

    def get_w3(self):
        """Return the underlying web3.Web3 instance.

        Used by FetchToken (web3scout) and by direct contract calls
        (lp_contract.functions.X().call(block_identifier=N)) inside
        LiveProvider's V2 snapshot path.
        """
        return self._w3

    def block_number(self) -> int:
        """Current block_number from the endpoint."""
        return int(self._w3.eth.block_number)

    def chain_id(self) -> int:
        """Chain id of the endpoint. Cached on first access per C9.
        Safe to call repeatedly — the chain_id of a connected endpoint
        is a constant for the lifetime of the connection."""
        if self._chain_id is None:
            self._chain_id = int(self._w3.eth.chain_id)
        return self._chain_id

    def block_timestamp(self, block_number: int) -> int:
        """Block header timestamp for the given block_number.

        Used by V2 LiveProvider's enrichment retrofit (Phase 2). V3
        reads timestamp inside the multicall via Multicall3's
        `getCurrentBlockTimestamp()`, so this helper is V2-only in
        Phase 2; one extra round trip per V2 snapshot.
        """
        return int(self._w3.eth.get_block(block_number).timestamp)

    def is_connected(self) -> bool:
        """True if the underlying ConnectW3 reports a live connection.

        Used in tests and as a debugging hook; LiveProvider does not
        gate snapshots on this — a failing eth_call surfaces the same
        problem with more context.
        """
        return self._connector.is_connect()


# ─── Multicall3 (Phase 2 D6/D14) ───────────────────────────────────────────


# Canonical Multicall3 address — same on every major EVM chain per
# https://www.multicall3.com. Hardcoded per D6: if a target chain
# doesn't have Multicall3, the eth_call to this address fails with a
# clear error and that's a v2.2 problem (multi-chain support work).
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"


# Minimal Multicall3 ABI — only `aggregate3` (the Call3 struct
# accepting allowFailure per call) and `getCurrentBlockTimestamp`
# (folded into the same batch per C8 to save a round trip).
_MULTICALL3_ABI = [
    {
        "inputs": [{
            "components": [
                {"internalType": "address", "name": "target", "type": "address"},
                {"internalType": "bool", "name": "allowFailure", "type": "bool"},
                {"internalType": "bytes", "name": "callData", "type": "bytes"},
            ],
            "internalType": "struct Multicall3.Call3[]",
            "name": "calls",
            "type": "tuple[]",
        }],
        "name": "aggregate3",
        "outputs": [{
            "components": [
                {"internalType": "bool", "name": "success", "type": "bool"},
                {"internalType": "bytes", "name": "returnData", "type": "bytes"},
            ],
            "internalType": "struct Multicall3.Result[]",
            "name": "returnData",
            "type": "tuple[]",
        }],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getCurrentBlockTimestamp",
        "outputs": [
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def _fn_selector(fn_signature: str) -> bytes:
    """4-byte function selector for a no-arg view function signature
    like `"slot0()"` or `"token0()"`. We only batch no-arg reads in
    Phase 2; introducing args would require encoding calldata too."""
    from eth_utils import function_signature_to_4byte_selector
    return function_signature_to_4byte_selector(fn_signature)


def multicall_aggregate3(w3, calls, block_number: int):
    """Batch a set of no-arg view calls through Multicall3.aggregate3.

    Parameters
    ----------
    w3 : Web3
        web3 client. The Multicall3 contract proxy is built fresh on
        every invocation — cost is negligible.
    calls : list[tuple[str, str, list[str]]]
        Each entry is `(target_address, fn_signature, decode_types)`.
        `fn_signature` is the canonical `"name(args)"` form used to
        compute the selector (e.g. `"slot0()"`). `decode_types` is a
        list of eth_abi type strings (e.g. `["uint160", "int24", ...]`)
        describing the return shape.
    block_number : int
        Pin every sub-call to this block per R1 (block consistency).

    Returns
    -------
    list
        One decoded value per call. For single-return calls, the bare
        decoded value. For multi-return (e.g. slot0's 7 fields), a
        tuple. The order matches the input `calls` list.

    Raises
    ------
    RuntimeError
        If any sub-call reports `success=False`. With D7
        (`allowFailure=false` on every call), the whole multicall
        reverts before this branch — but defended anyway in case a
        future caller passes allowFailure=True.
    """
    from eth_abi import decode
    multicall = w3.eth.contract(
        address = w3.to_checksum_address(MULTICALL3_ADDRESS),
        abi = _MULTICALL3_ABI,
    )
    # D7: allowFailure=False on every call. Snapshot fails loudly.
    encoded = [
        (
            w3.to_checksum_address(target),
            False,
            _fn_selector(fn_sig),
        )
        for target, fn_sig, _ in calls
    ]
    results = multicall.functions.aggregate3(encoded).call(
        block_identifier = block_number,
    )
    decoded_results = []
    for (success, return_data), (_, fn_sig, decode_types) in zip(results, calls):
        if not success:
            raise RuntimeError(
                "multicall_aggregate3: sub-call {!r} reverted "
                "(allowFailure was off but success=False — should not happen)"
                .format(fn_sig)
            )
        out = decode(decode_types, return_data)
        # Convention: bare scalar for single-return, tuple for multi.
        decoded_results.append(out[0] if len(decode_types) == 1 else out)
    return decoded_results


def multicall_aggregate3_args(w3, calls, block_number, allow_failure = False):
    """Batch view calls (no-arg or argument-bearing) through Multicall3.

    Sibling to multicall_aggregate3. That helper only encodes a 4-byte
    selector (no-arg reads); this one also ABI-encodes calldata args,
    so it serves getPoolTokens(bytes32), coins(uint256),
    balances(uint256), and the no-arg getters in one path. The no-arg
    helper is left untouched so the V3 read path is unaffected.

    Parameters
    ----------
    w3 : Web3
        web3 client.
    calls : list[tuple]
        Each entry is (target, fn_signature, arg_types, args, decode_types):
          - fn_signature : canonical "name(types)" form, e.g.
            "coins(uint256)" or "getPoolId()".
          - arg_types    : eth_abi input types, e.g. ["uint256"]; []
            for a no-arg call.
          - args         : argument values, e.g. [0]; [] for no-arg.
          - decode_types : eth_abi return types, e.g. ["address"] or
            ["address[]", "uint256[]", "uint256"].
    block_number : int
        Pin every sub-call to this block per R1 (block consistency).
    allow_failure : bool
        False (default): any sub-call revert raises RuntimeError (the
        whole batch is allowFailure=False, so it reverts upstream first).
        True: failed sub-calls return None in their result slot, used
        by the Curve coin-count probe.

    Returns
    -------
    list
        One decoded value per call, in input order. Bare scalar for a
        single-return call, tuple for multi-return. None for a failed
        sub-call when allow_failure=True.
    """
    from eth_abi import encode, decode
    from eth_utils import function_signature_to_4byte_selector
    multicall = w3.eth.contract(
        address = w3.to_checksum_address(MULTICALL3_ADDRESS),
        abi = _MULTICALL3_ABI,
    )
    encoded = []
    for target, fn_sig, arg_types, args, _decode_types in calls:
        selector = function_signature_to_4byte_selector(fn_sig)
        call_data = selector + (encode(arg_types, args) if arg_types else b"")
        encoded.append((w3.to_checksum_address(target), allow_failure, call_data))
    results = multicall.functions.aggregate3(encoded).call(
        block_identifier = block_number,
    )
    decoded_results = []
    for (success, return_data), (_t, fn_sig, _at, _a, decode_types) in zip(results, calls):
        if not success:
            if allow_failure:
                decoded_results.append(None)
                continue
            raise RuntimeError(
                "multicall_aggregate3_args: sub-call {!r} reverted "
                "(allowFailure was off)".format(fn_sig)
            )
        out = decode(decode_types, return_data)
        decoded_results.append(out[0] if len(decode_types) == 1 else out)
    return decoded_results


# ─── V2 helpers ────────────────────────────────────────────────────────────


def load_v2_pair_contract(w3, address: str):
    """Load a Uniswap V2 pair contract proxy via web3scout's ABI bundle.

    Uses the AGNOSTIC platform's UniswapV2Pair ABI — protocol-neutral
    (works for Uniswap V2 and Sushi V2 since both implement the same
    interface). Returns a web3.contract.Contract suitable for
    `.functions.getReserves().call(block_identifier=N)` etc.
    """
    from web3scout.abi.abi_load import ABILoad
    from web3scout.enums.platforms_enum import PlatformsEnum
    abi = ABILoad(PlatformsEnum.AGNOSTIC, "UniswapV2Pair")
    return abi.apply(w3, address)


def load_v3_pool_contract(w3, address: str):
    """Load a Uniswap V3 pool contract proxy via web3scout's ABI bundle.

    Symmetric with `load_v2_pair_contract`. Phase 2's V3 LiveProvider
    doesn't strictly need the proxy (reads go through Multicall3 with
    raw selectors), but keeping the loader makes the V2/V3 surface
    parallel and gives future V3-specific direct calls a clean path.
    """
    from web3scout.abi.abi_load import ABILoad
    from web3scout.enums.platforms_enum import PlatformsEnum
    abi = ABILoad(PlatformsEnum.AGNOSTIC, "UniswapV3Pool")
    return abi.apply(w3, address)


def fetch_token(w3, address: str):
    """Fetch ERC20 metadata via web3scout's FetchToken.

    Returns a uniswappy.erc.ERC20 with .token_name (symbol),
    .token_addr, .token_decimal populated from on-chain reads.

    Note on block-pinning: FetchToken does NOT accept a
    block_identifier — symbol() and decimals() are read at "latest".
    For Phase 1 this is acceptable: token metadata is effectively
    immutable for production ERC20s, so reading at latest while
    reserves are pinned to block N produces consistent snapshots in
    practice. The v1 ImpermanentLossAgent's prime_mock_pool path uses
    this same pattern.
    """
    from web3scout.token.fetch.fetch_token import FetchToken
    return FetchToken(w3).apply(address)


def amt_to_decimal(token, amt_raw):
    """Convert a raw uint amount to a decimal-adjusted Python float.

    Mirror of FetchToken.amt_to_decimal. Native int / int division
    produces a float — matches MockProvider's reserve representation
    (whole-token units as floats), which is what StateTwinBuilder
    expects. Per R7 in the expanded brief, do NOT introduce mpz here
    — keep native floats end-to-end into the snapshot.
    """
    return amt_raw / (10 ** token.token_decimal)
