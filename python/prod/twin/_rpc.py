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

Phase 2 will extend this module with a multicall helper. The class
shape stays the same; multicall lives behind a `multicall(reads)`
method or similar.
"""


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
        """Chain id of the endpoint. Cached on the underlying web3
        instance after first read; safe to call repeatedly."""
        return int(self._w3.eth.chain_id)

    def is_connected(self) -> bool:
        """True if the underlying ConnectW3 reports a live connection.

        Used in tests and as a debugging hook; LiveProvider does not
        gate snapshots on this — a failing eth_call surfaces the same
        problem with more context.
        """
        return self._connector.is_connect()


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
