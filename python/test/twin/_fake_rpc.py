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

"""Test-only FakeRpcClient + supporting fakes for LiveProvider unit tests.

Strategy: duck-type web3.Web3 closely enough that LiveProvider's
production reads (via web3scout's ABILoad + FetchToken) work against
the fake without modification. No real web3, no network.

The fake satisfies the surface used by:
  - RpcClient (defipy.twin._rpc): get_w3(), block_number()
  - load_v2_pair_contract -> ABILoad.apply(w3, address)
    which calls w3.eth.contract(address=..., abi=...)
  - fetch_token -> FetchToken(w3).apply(token_address)
    which calls w3.to_checksum_address, w3.eth.contract,
    contract.functions.symbol().call(),
    contract.functions.decimals().call()
  - LiveProvider._snapshot_v2 directly:
    pair.functions.token0().call(block_identifier=N),
    pair.functions.token1().call(block_identifier=N),
    pair.functions.getReserves().call(block_identifier=N),
    pair.functions.totalSupply().call(block_identifier=N)

Phase 2 (per STATE_TWIN_PHASE_2.md) will lift this into shared
fixture machinery generalized over V2 and V3. For Phase 1 it stays
focused on V2.

Each test composes a `FakeRpcClient` with a small spec describing the
pool: pool address, token addresses, reserves (raw uint), token
metadata (symbol, decimals). The fake hands out FakeContract objects
keyed by address; each FakeContract dispatches function calls against
that pool/token's spec.
"""

from dataclasses import dataclass, field
from typing import Optional


# ─── Per-call recording ────────────────────────────────────────────────────


@dataclass
class CallRecord:
    """One observed contract function call. Tests inspect a list of
    these to verify block consistency, call ordering, etc."""
    address: str
    function: str
    block_identifier: object   # int, None, "latest", etc.


# ─── Pool / token specs ────────────────────────────────────────────────────


@dataclass
class V2PoolSpec:
    """Canned response set for a single Uniswap V2 pair address.

    Reserves are provided in RAW uint form (what getReserves() actually
    returns on-chain), per the C2 contract — LiveProvider does the
    decimal scaling. The spec is what the chain looks like; LiveProvider
    is what we're testing.
    """
    address: str
    token0_address: str
    token1_address: str
    reserve0_raw: int
    reserve1_raw: int
    total_supply_raw: int = 10_000 * 10**18


@dataclass
class TokenSpec:
    """Canned response set for a single ERC20 address."""
    address: str
    symbol: str
    decimals: int


# ─── FakeContract / FakeFunctions ──────────────────────────────────────────


class _PairFunctions:
    """Functions surface for a V2 pair: token0/token1/getReserves/totalSupply."""

    def __init__(self, pool: V2PoolSpec, recorder, address: str):
        self._pool = pool
        self._recorder = recorder
        self._address = address

    def token0(self):
        return _BoundCall(self._recorder, self._address, "token0",
                          lambda: self._pool.token0_address)

    def token1(self):
        return _BoundCall(self._recorder, self._address, "token1",
                          lambda: self._pool.token1_address)

    def getReserves(self):
        # Real getReserves returns (uint112, uint112, uint32). The
        # third element is blockTimestampLast; LiveProvider doesn't
        # use it but returning a realistic shape catches accidental
        # production-code changes that try to consume it.
        return _BoundCall(
            self._recorder, self._address, "getReserves",
            lambda: (self._pool.reserve0_raw, self._pool.reserve1_raw, 0),
        )

    def totalSupply(self):
        return _BoundCall(self._recorder, self._address, "totalSupply",
                          lambda: self._pool.total_supply_raw)


class _ERC20Functions:
    """Functions surface for an ERC20: symbol/decimals/name/totalSupply."""

    def __init__(self, token: TokenSpec, recorder, address: str):
        self._token = token
        self._recorder = recorder
        self._address = address

    def symbol(self):
        return _BoundCall(self._recorder, self._address, "symbol",
                          lambda: self._token.symbol)

    def decimals(self):
        return _BoundCall(self._recorder, self._address, "decimals",
                          lambda: self._token.decimals)

    def name(self):
        return _BoundCall(self._recorder, self._address, "name",
                          lambda: self._token.symbol)

    def totalSupply(self):
        # Not used by LiveProvider but satisfies FetchToken.get_token_supply
        # if anyone calls it. Return a placeholder.
        return _BoundCall(self._recorder, self._address, "totalSupply",
                          lambda: 0)


class _BoundCall:
    """Stands in for a web3 ContractFunction prepared call. Records
    the `block_identifier` arg so tests can verify R1 (block
    consistency) holds."""

    def __init__(self, recorder, address: str, fn_name: str, value_fn):
        self._recorder = recorder
        self._address = address
        self._fn_name = fn_name
        self._value_fn = value_fn

    def call(self, block_identifier=None):
        self._recorder.append(CallRecord(
            address = self._address,
            function = self._fn_name,
            block_identifier = block_identifier,
        ))
        return self._value_fn()


class _FakeContract:
    """A web3.contract.Contract stand-in. Holds a `.functions`
    attribute exposing the right surface for the contract type."""

    def __init__(self, address: str, abi, functions):
        self.address = address
        self.abi = abi
        self.functions = functions


# ─── FakeEth / FakeWeb3 ────────────────────────────────────────────────────


class _FakeEth:
    """web3.eth stand-in. Dispatches contract() to a per-address spec
    map; provides block_number / chain_id properties for RpcClient."""

    def __init__(self, fake_w3):
        self._fake_w3 = fake_w3

    @property
    def block_number(self) -> int:
        return self._fake_w3._latest_block

    @property
    def chain_id(self) -> int:
        return self._fake_w3._chain_id

    def contract(self, address=None, abi=None):
        # Address arrives in checksum form (LiveProvider normalizes
        # via to_checksum_address before reaching here). Look it up
        # in the V2-pool / token registries.
        addr = address
        if addr in self._fake_w3._pool_specs:
            pool = self._fake_w3._pool_specs[addr]
            return _FakeContract(
                addr, abi, _PairFunctions(pool, self._fake_w3._call_log, addr),
            )
        if addr in self._fake_w3._token_specs:
            token = self._fake_w3._token_specs[addr]
            return _FakeContract(
                addr, abi, _ERC20Functions(token, self._fake_w3._call_log, addr),
            )
        raise KeyError(
            "FakeWeb3: no spec registered for address {!r}. "
            "Registered pools: {}; registered tokens: {}"
            .format(addr,
                    list(self._fake_w3._pool_specs.keys()),
                    list(self._fake_w3._token_specs.keys()))
        )


class FakeWeb3:
    """web3.Web3 stand-in for LiveProvider unit tests.

    Built via FakeRpcClientBuilder (see below); not constructed
    directly by tests. The FakeWeb3 is reachable via
    `fake_client.get_w3()` and behaves enough like the real Web3 to
    satisfy ABILoad, FetchToken, and direct `.functions.X().call()`
    patterns.
    """

    def __init__(self, latest_block: int, chain_id: int):
        self._latest_block = latest_block
        self._chain_id = chain_id
        self._pool_specs: dict = {}
        self._token_specs: dict = {}
        self._call_log: list = []
        self.eth = _FakeEth(self)

    def to_checksum_address(self, address: str) -> str:
        # Tests pass already-checksummed or otherwise canonical addrs
        # so we can use the value verbatim. Real web3 would normalize
        # casing per EIP-55. The identity behavior here is sufficient
        # because the tests register addresses under exactly the keys
        # they pass through. If a test mixes casing, this is the
        # place to add normalization.
        return address


# ─── FakeRpcClient ─────────────────────────────────────────────────────────


class FakeRpcClient:
    """Test-only RpcClient stand-in.

    Duck-types defipy.twin._rpc.RpcClient: same get_w3() / block_number()
    surface. LiveProvider._with_client(fake) accepts it for unit tests.
    """

    def __init__(self, fake_w3: FakeWeb3):
        self._w3 = fake_w3

    def get_w3(self):
        return self._w3

    def block_number(self) -> int:
        return self._w3.eth.block_number

    def chain_id(self) -> int:
        return self._w3.eth.chain_id

    def is_connected(self) -> bool:
        return True

    # ─── Test inspection ───────────────────────────────────────────────────

    @property
    def call_log(self) -> list:
        """Ordered list of CallRecord — every recorded contract call.

        Tests use this for R1 verification (every call pins to the
        same block_identifier) and for ordering / count checks.
        """
        return list(self._w3._call_log)


# ─── Builder API ───────────────────────────────────────────────────────────


def build_fake_client(
    *,
    pool: V2PoolSpec,
    tokens: list,
    latest_block: int = 19_500_000,
    chain_id: int = 1,
) -> FakeRpcClient:
    """Construct a FakeRpcClient pre-loaded with a V2 pool + tokens.

    Single entry point for tests. Returns a FakeRpcClient ready for
    `LiveProvider._with_client(client)`.

    Parameters
    ----------
    pool : V2PoolSpec
        Pool metadata (address, token addrs, raw reserves).
    tokens : list[TokenSpec]
        Token metadata (symbol, decimals) for token0 and token1.
        Must include specs for both addresses referenced by `pool`.
    latest_block : int
        Block number returned by `eth_blockNumber`. Defaults to a
        canonical mid-2024 block (19_500_000) for stability across
        tests.
    chain_id : int
        Chain id returned by `eth_chainId`. Defaults to 1 (mainnet).
    """
    fake = FakeWeb3(latest_block=latest_block, chain_id=chain_id)
    fake._pool_specs[pool.address] = pool
    for token in tokens:
        fake._token_specs[token.address] = token
    # Sanity check: pool's token addrs must have matching specs.
    referenced = {pool.token0_address, pool.token1_address}
    provided = {t.address for t in tokens}
    missing = referenced - provided
    if missing:
        raise ValueError(
            "build_fake_client: pool references token addresses "
            "without TokenSpecs: {}".format(missing)
        )
    return FakeRpcClient(fake)


# ─── Canonical V2 pool fixture: WETH/USDC mainnet ──────────────────────────
#
# Per D6 in STATE_TWIN_PHASE_1_EXPANDED.md: WETH/USDC V2 is the
# canonical smoke-test pool because it's been the most active V2 pool
# throughout the protocol's life. Used by the live_rpc tests; mocked
# tests use these same addresses for cross-test consistency.

WETH_USDC_V2_POOL = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"   # token0 (lower addr)
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"   # token1


def canonical_weth_usdc_v2_spec(
    *,
    usdc_amount: float = 50_000_000.0,   # 50M USDC
    weth_amount: float = 15_000.0,       # 15k WETH (~$50M at $3300/ETH)
) -> V2PoolSpec:
    """Build a V2PoolSpec with realistic WETH/USDC reserves.

    The float `_amount` parameters are in whole-token units; this
    helper converts to raw uint by scaling at the correct decimals.
    Lets tests express "50M USDC and 15k WETH" without manually
    multiplying by 10**6 and 10**18.
    """
    return V2PoolSpec(
        address = WETH_USDC_V2_POOL,
        token0_address = USDC_ADDRESS,
        token1_address = WETH_ADDRESS,
        reserve0_raw = int(usdc_amount * 10**6),
        reserve1_raw = int(weth_amount * 10**18),
    )


def canonical_weth_usdc_token_specs() -> list:
    return [
        TokenSpec(address=USDC_ADDRESS, symbol="USDC", decimals=6),
        TokenSpec(address=WETH_ADDRESS, symbol="WETH", decimals=18),
    ]
