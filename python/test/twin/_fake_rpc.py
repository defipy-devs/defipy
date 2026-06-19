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
class V3PoolSpec:
    """Canned response set for a single Uniswap V3 pool address.

    Phase 2 — fields mirror what `slot0()`, `liquidity()`, `fee()`,
    `tickSpacing()`, `token0()`, `token1()` return on-chain. The fake's
    `_V3PoolFunctions` class dispatches each function read against
    these fields. Per C7 of STATE_TWIN_PHASE_2_EXPANDED.md the dispatch
    happens via Multicall3's aggregate3 → selector lookup, NOT direct
    contract calls.
    """
    address: str
    token0_address: str
    token1_address: str
    sqrt_price_x96: int   # slot0[0]
    tick: int             # slot0[1]
    liquidity: int        # active liquidity (uint128)
    fee: int = 3000       # 500 / 3000 / 10000
    tick_spacing: int = 60   # 10 / 60 / 200


@dataclass
class TokenSpec:
    """Canned response set for a single ERC20 address."""
    address: str
    symbol: str
    decimals: int


@dataclass
class BalancerPoolSpec:
    """Canned response set for a single Balancer V2 WeightedPool.

    v2.2 Phase 2 — fields mirror the 2-hop read: the pool answers
    `getPoolId()`/`getVault()`/`getNormalizedWeights()`; the Vault
    answers `getPoolTokens(poolId)` with (tokens[], balances[],
    lastChangeBlock). The fake registers this spec at BOTH the pool
    address and the vault address so the selector → spec dispatch
    resolves for both targets (the function name disambiguates).

    `balance{0,1}_raw` are RAW uint balances (what getPoolTokens
    returns on-chain); LiveProvider does the decimal scaling.
    `weight{0,1}_raw` are 1e18-scaled and must sum to 1e18.
    """
    address: str
    pool_id: bytes          # bytes32
    vault_address: str
    token0_address: str
    token1_address: str
    balance0_raw: int
    balance1_raw: int
    weight0_raw: int        # 1e18-scaled; weight0_raw + weight1_raw == 1e18
    weight1_raw: int
    last_change_block: int = 0
    # Test-only escape hatch for the >2-asset scope-guard test: extra
    # (address, raw balance) entries appended to the getPoolTokens
    # return so a 3-asset pool can be simulated. Empty for the normal
    # 2-asset case.
    extra_token_addresses: list = field(default_factory=list)
    extra_balances_raw: list = field(default_factory=list)

    @classmethod
    def from_human(
        cls,
        *,
        address,
        pool_id,
        vault_address,
        token0_address,
        token1_address,
        balance0,
        balance1,
        weight0,
        weight1,
        decimals0,
        decimals1,
        last_change_block=0,
    ):
        """Build a spec from human-readable weights/balances.

        Scales `balance{0,1}` by the token decimals to raw uints and
        `weight{0,1}` (e.g. 0.8 / 0.2) by 1e18. Mirrors how a real
        WeightedPool stores normalized weights summing to 1e18.

        Balance scaling goes through Decimal so a round human amount
        (e.g. 100000.0 at 18 decimals) yields the exact raw integer
        (10**23) and round-trips back to 100000.0 — float
        multiplication would drift (int(100000.0 * 10**18) loses the
        low digits). This keeps fixture-parity assertions exact.
        """
        from decimal import Decimal
        return cls(
            address = address,
            pool_id = pool_id,
            vault_address = vault_address,
            token0_address = token0_address,
            token1_address = token1_address,
            balance0_raw = int(Decimal(str(balance0)) * (10**decimals0)),
            balance1_raw = int(Decimal(str(balance1)) * (10**decimals1)),
            weight0_raw = int(round(weight0 * 1e18)),
            weight1_raw = int(round(weight1 * 1e18)),
            last_change_block = last_change_block,
        )


@dataclass
class CurvePoolSpec:
    """Canned response set for a single Curve plain Stableswap pool.

    v2.2 Phase 3 — the pool answers `A()` / `fee()` (no-arg) and
    `coins(i)` / `balances(i)` (index-arg). `N_COINS` has no universal
    getter on plain pools, so `coins(i)` for `i >= len(coin_addresses)`
    must revert (the fake returns (False, b"")), which is what lets the
    allow_failure coin-count probe stop at the right count.

    `balances_raw` are RAW uint balances (what balances(i) returns
    on-chain); LiveProvider does the decimal scaling.
    """
    address: str
    coin_addresses: list    # 2 or 3 token addresses, in coin-index order
    balances_raw: list      # raw uints, parallel to coin_addresses
    A: int = 10
    fee: int = 4_000_000    # Curve fee is 1e10-scaled; opaque to the read

    @classmethod
    def from_human(cls, *, address, coin_addresses, balances, decimals, A=10,
                   fee=4_000_000):
        """Build a spec from human balances + per-token decimals.

        `balances` and `decimals` are lists parallel to
        `coin_addresses`. Scaling goes through Decimal so a round human
        amount round-trips exactly (see BalancerPoolSpec.from_human).
        """
        from decimal import Decimal
        balances_raw = [
            int(Decimal(str(bal)) * (10**dec))
            for bal, dec in zip(balances, decimals)
        ]
        return cls(
            address = address,
            coin_addresses = list(coin_addresses),
            balances_raw = balances_raw,
            A = A,
            fee = fee,
        )


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


class _V3PoolFunctions:
    """Functions surface for a V3 pool: slot0/liquidity/fee/tickSpacing/token0/token1.

    Phase 2 — V3 LiveProvider reads these via Multicall3 in production,
    so the V3 functions are reached via `_MulticallFunctions.aggregate3`
    in the test fake too. Direct `.functions.X().call()` patterns work
    against this class for symmetry with V2, but production V3 doesn't
    use them.
    """

    def __init__(self, pool: "V3PoolSpec", recorder, address: str):
        self._pool = pool
        self._recorder = recorder
        self._address = address

    def token0(self):
        return _BoundCall(self._recorder, self._address, "token0",
                          lambda: self._pool.token0_address)

    def token1(self):
        return _BoundCall(self._recorder, self._address, "token1",
                          lambda: self._pool.token1_address)

    def slot0(self):
        # slot0 returns (sqrtPriceX96, tick, observationIndex,
        # observationCardinality, observationCardinalityNext,
        # feeProtocol, unlocked). LiveProvider only uses sqrtPriceX96
        # and tick; the rest are zero-padded for ABI compliance.
        return _BoundCall(
            self._recorder, self._address, "slot0",
            lambda: (
                self._pool.sqrt_price_x96,
                self._pool.tick,
                0, 1, 1, 0, True,
            ),
        )

    def liquidity(self):
        return _BoundCall(self._recorder, self._address, "liquidity",
                          lambda: self._pool.liquidity)

    def fee(self):
        return _BoundCall(self._recorder, self._address, "fee",
                          lambda: self._pool.fee)

    def tickSpacing(self):
        return _BoundCall(self._recorder, self._address, "tickSpacing",
                          lambda: self._pool.tick_spacing)


class _BalancerPoolFunctions:
    """Functions surface for a Balancer V2 WeightedPool + its Vault.

    v2.2 Phase 2 — the pool reads (getPoolId/getVault/
    getNormalizedWeights) and the Vault read (getPoolTokens) both
    dispatch against the same BalancerPoolSpec (registered at both
    addresses). Production reads these via Multicall3, so they're
    reached through `_BoundAggregate3` in the fake, exactly like V3.
    """

    def __init__(self, pool: "BalancerPoolSpec", recorder, address: str):
        self._pool = pool
        self._recorder = recorder
        self._address = address

    def getPoolId(self):
        return _BoundCall(self._recorder, self._address, "getPoolId",
                          lambda: self._pool.pool_id)

    def getVault(self):
        return _BoundCall(self._recorder, self._address, "getVault",
                          lambda: self._pool.vault_address)

    def getNormalizedWeights(self):
        return _BoundCall(
            self._recorder, self._address, "getNormalizedWeights",
            lambda: [self._pool.weight0_raw, self._pool.weight1_raw],
        )

    def getPoolTokens(self):
        # Vault read: (tokens[], balances[], lastChangeBlock). A
        # single-pool fake ignores the poolId arg in call_data[4:].
        # extra_* lists let a test simulate a >2-asset pool.
        return _BoundCall(
            self._recorder, self._address, "getPoolTokens",
            lambda: (
                [self._pool.token0_address, self._pool.token1_address]
                + list(self._pool.extra_token_addresses),
                [self._pool.balance0_raw, self._pool.balance1_raw]
                + list(self._pool.extra_balances_raw),
                self._pool.last_change_block,
            ),
        )


class _CurvePoolFunctions:
    """No-arg functions surface for a Curve plain pool: A() / fee().

    The index-arg reads coins(i)/balances(i) are NOT here — they share
    one selector across all indices, so _BoundAggregate3 decodes the
    index from calldata and dispatches them directly against the spec.
    """

    def __init__(self, pool: "CurvePoolSpec", recorder, address: str):
        self._pool = pool
        self._recorder = recorder
        self._address = address

    def A(self):
        return _BoundCall(self._recorder, self._address, "A",
                          lambda: self._pool.A)

    def fee(self):
        return _BoundCall(self._recorder, self._address, "fee",
                          lambda: self._pool.fee)


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


# Multicall3 canonical address — must match _rpc.MULTICALL3_ADDRESS.
# Duplicated rather than imported to keep this test helper free of any
# production-code import that pulls web3 at top level.
_MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"


def _selector(fn_signature: str) -> bytes:
    from eth_utils import function_signature_to_4byte_selector
    return function_signature_to_4byte_selector(fn_signature)


# Selector → (function_name, eth_abi return-type list) for V3 pool reads
# and ERC20 metadata reads. Constructed lazily so importing this module
# doesn't require eth_utils to be installed (it always is via the
# [chain] extra, but keep the import pattern hygienic).
_DISPATCH: dict = {}
_MULTICALL3_TIMESTAMP_SELECTOR: bytes = b""


def _ensure_dispatch():
    global _MULTICALL3_TIMESTAMP_SELECTOR
    if _DISPATCH:
        return
    _DISPATCH.update({
        _selector("token0()"): ("token0", ["address"]),
        _selector("token1()"): ("token1", ["address"]),
        _selector("slot0()"): (
            "slot0",
            ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
        ),
        _selector("liquidity()"): ("liquidity", ["uint128"]),
        _selector("fee()"): ("fee", ["uint24"]),
        _selector("tickSpacing()"): ("tickSpacing", ["int24"]),
        _selector("getReserves()"): (
            "getReserves",
            ["uint112", "uint112", "uint32"],
        ),
        _selector("totalSupply()"): ("totalSupply", ["uint256"]),
        _selector("symbol()"): ("symbol", ["string"]),
        _selector("decimals()"): ("decimals", ["uint8"]),
        # Balancer V2 (v2.2 Phase 2). getPoolId/getVault/
        # getNormalizedWeights dispatch against the pool address;
        # getPoolTokens(bytes32) dispatches against the vault address.
        _selector("getPoolId()"): ("getPoolId", ["bytes32"]),
        _selector("getVault()"): ("getVault", ["address"]),
        _selector("getNormalizedWeights()"): (
            "getNormalizedWeights", ["uint256[]"],
        ),
        _selector("getPoolTokens(bytes32)"): (
            "getPoolTokens", ["address[]", "uint256[]", "uint256"],
        ),
        # Curve plain Stableswap (v2.2 Phase 3). A()/fee() are no-arg;
        # coins(uint256)/balances(uint256) are index-arg — _BoundAggregate3
        # decodes the index from calldata and dispatches per-index.
        _selector("A()"): ("A", ["uint256"]),
        _selector("coins(uint256)"): ("coins", ["address"]),
        _selector("balances(uint256)"): ("balances", ["uint256"]),
    })
    _MULTICALL3_TIMESTAMP_SELECTOR = _selector("getCurrentBlockTimestamp()")


class _MulticallFunctions:
    """Multicall3 contract surface in the fake: aggregate3 +
    getCurrentBlockTimestamp. Per C7, aggregate3 dispatches each
    sub-call by `(target, selector)`, fetches the raw value from the
    target's pool/token spec, and ABI-encodes per the return type."""

    def __init__(self, fake_w3, recorder):
        self._fake_w3 = fake_w3
        self._recorder = recorder
        self._address = _MULTICALL3_ADDRESS

    def aggregate3(self, calls):
        return _BoundAggregate3(
            self._fake_w3, self._recorder, self._address, calls,
        )

    def getCurrentBlockTimestamp(self):
        return _BoundCall(
            self._recorder, self._address, "getCurrentBlockTimestamp",
            lambda: self._fake_w3._block_timestamp,
        )


class _BoundAggregate3:
    """Stand-in for the aggregate3-prepared call. Decoding the
    sub-call selectors and ABI-encoding the canned values happen on
    `.call(block_identifier=N)`."""

    def __init__(self, fake_w3, recorder, address, calls):
        self._fake_w3 = fake_w3
        self._recorder = recorder
        self._address = address
        self._calls = calls

    def call(self, block_identifier=None):
        from eth_abi import encode
        _ensure_dispatch()
        # Record one entry for the multicall envelope itself + one for
        # each sub-call. Tests can verify R1 (block consistency) by
        # checking every sub-record has the same block_identifier.
        self._recorder.append(CallRecord(
            address = self._address,
            function = "aggregate3",
            block_identifier = block_identifier,
        ))
        results = []
        for target, allow_failure, call_data in self._calls:
            selector = bytes(call_data[:4])

            # Multicall3.getCurrentBlockTimestamp() — special target.
            if (target.lower() == _MULTICALL3_ADDRESS.lower()
                    and selector == _MULTICALL3_TIMESTAMP_SELECTOR):
                self._recorder.append(CallRecord(
                    address = target,
                    function = "getCurrentBlockTimestamp",
                    block_identifier = block_identifier,
                ))
                encoded = encode(["uint256"], [self._fake_w3._block_timestamp])
                results.append((True, encoded))
                continue

            # Regular V2/V3 pool / ERC20 read.
            if selector not in _DISPATCH:
                if not allow_failure:
                    raise RuntimeError(
                        "FakeMulticall: unknown selector {} for target {} "
                        "(allowFailure=False)".format(selector.hex(), target)
                    )
                results.append((False, b""))
                continue

            fn_name, return_types = _DISPATCH[selector]

            # Index-arg Curve reads: coins(i)/balances(i) share one
            # selector across all indices, so decode the index from
            # call_data[4:] and return the i-th element. An out-of-range
            # index is a genuine revert ((False, b"")) — this is what
            # lets the allow_failure coin-count probe stop at N.
            if fn_name in ("coins", "balances"):
                from eth_abi import decode as _decode
                index = _decode(["uint256"], bytes(call_data[4:]))[0]
                value = self._dispatch_curve_indexed(target, fn_name, index)
                if value is None:
                    results.append((False, b""))
                    continue
                self._recorder.append(CallRecord(
                    address = target,
                    function = fn_name,
                    block_identifier = block_identifier,
                ))
                results.append((True, encode(return_types, [value])))
                continue

            value = self._dispatch_to_spec(target, fn_name)
            self._recorder.append(CallRecord(
                address = target,
                function = fn_name,
                block_identifier = block_identifier,
            ))

            # ABI-encode per the function's return shape. Multi-return
            # functions get encoded as their tuple-of-types list (each
            # type a separate top-level argument), matching how
            # eth_abi.decode sees them on the production side.
            if len(return_types) == 1:
                encoded = encode(return_types, [value])
            else:
                # `value` is already a tuple of the right arity from
                # the slot0/getReserves _BoundCall lambdas.
                encoded = encode(return_types, list(value))
            results.append((True, encoded))
        return results

    def _dispatch_to_spec(self, target: str, fn_name: str):
        """Look up the canned value for `fn_name` against the spec
        registered at `target`. Mirror of the direct-call path so the
        same V2PoolSpec / V3PoolSpec / TokenSpec serves both."""
        # Pool spec match — V2 or V3.
        if target in self._fake_w3._pool_specs:
            spec = self._fake_w3._pool_specs[target]
            if isinstance(spec, V2PoolSpec):
                return _PairFunctions(
                    spec, [], target,
                ).__getattribute__(fn_name)()._value_fn()
            if isinstance(spec, V3PoolSpec):
                return _V3PoolFunctions(
                    spec, [], target,
                ).__getattribute__(fn_name)()._value_fn()
            if isinstance(spec, BalancerPoolSpec):
                return _BalancerPoolFunctions(
                    spec, [], target,
                ).__getattribute__(fn_name)()._value_fn()
            if isinstance(spec, CurvePoolSpec):
                # No-arg Curve reads only (A/fee); coins/balances are
                # handled per-index in call() before reaching here.
                return _CurvePoolFunctions(
                    spec, [], target,
                ).__getattribute__(fn_name)()._value_fn()
        # Token spec match — ERC20.
        if target in self._fake_w3._token_specs:
            return _ERC20Functions(
                self._fake_w3._token_specs[target], [], target,
            ).__getattribute__(fn_name)()._value_fn()
        raise KeyError(
            "FakeMulticall: no spec registered for target {!r}; "
            "registered pools={}, tokens={}"
            .format(
                target,
                list(self._fake_w3._pool_specs.keys()),
                list(self._fake_w3._token_specs.keys()),
            )
        )

    def _dispatch_curve_indexed(self, target, fn_name, index):
        """coins(i)/balances(i) against a CurvePoolSpec at `target`.
        Returns None for an out-of-range index — a genuine on-chain
        revert, which the coin-count probe relies on to stop at N."""
        spec = self._fake_w3._pool_specs.get(target)
        if not isinstance(spec, CurvePoolSpec):
            raise KeyError(
                "FakeMulticall: coins/balances against non-Curve target "
                "{!r}".format(target)
            )
        if index >= len(spec.coin_addresses):
            return None
        if fn_name == "coins":
            return spec.coin_addresses[index]
        return spec.balances_raw[index]


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


class _FakeBlock:
    """web3.types.BlockData stand-in — only `.timestamp` is used."""

    def __init__(self, timestamp: int):
        self.timestamp = timestamp


class _FakeEth:
    """web3.eth stand-in. Dispatches contract() to a per-address spec
    map; provides block_number / chain_id properties for RpcClient."""

    def __init__(self, fake_w3):
        self._fake_w3 = fake_w3
        self._chain_id_reads = 0

    @property
    def block_number(self) -> int:
        return self._fake_w3._latest_block

    @property
    def chain_id(self) -> int:
        self._chain_id_reads += 1
        return self._fake_w3._chain_id

    def get_block(self, block_identifier):
        # Production uses w3.eth.get_block(N).timestamp via
        # RpcClient.block_timestamp(N). One canned timestamp per
        # FakeWeb3 — matches live behavior closely enough since
        # tests pin to a specific block.
        self._fake_w3._call_log.append(CallRecord(
            address = "0x_block",
            function = "get_block",
            block_identifier = block_identifier,
        ))
        return _FakeBlock(self._fake_w3._block_timestamp)

    def contract(self, address=None, abi=None):
        # Address arrives in checksum form (LiveProvider normalizes
        # via to_checksum_address before reaching here). Look it up
        # in the V2-pool / V3-pool / token / multicall registries.
        addr = address
        # Multicall3 mount — V3 LiveProvider builds a Multicall3 proxy
        # at the canonical address and calls aggregate3 on it.
        if addr.lower() == _MULTICALL3_ADDRESS.lower():
            return _FakeContract(
                addr, abi,
                _MulticallFunctions(self._fake_w3, self._fake_w3._call_log),
            )
        if addr in self._fake_w3._pool_specs:
            pool = self._fake_w3._pool_specs[addr]
            if isinstance(pool, V2PoolSpec):
                return _FakeContract(
                    addr, abi,
                    _PairFunctions(pool, self._fake_w3._call_log, addr),
                )
            if isinstance(pool, V3PoolSpec):
                return _FakeContract(
                    addr, abi,
                    _V3PoolFunctions(pool, self._fake_w3._call_log, addr),
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

    def __init__(self, latest_block: int, chain_id: int,
                 block_timestamp: int = 1_710_000_000):
        self._latest_block = latest_block
        self._chain_id = chain_id
        self._block_timestamp = block_timestamp
        self._pool_specs: dict = {}
        self._token_specs: dict = {}
        self._call_log: list = []
        self.eth = _FakeEth(self)

    def to_checksum_address(self, address: str) -> str:
        # Phase 2 — V3 reads addresses back from eth_abi decode in
        # lowercase. Normalize here so callers pass-through to
        # FakeEth.contract() find the registered specs.
        # Fall back to identity for Phase 1's placeholder-style addrs
        # (e.g. "0xPOOL", "0xT0") which are not valid EIP-55 input but
        # work as identity keys in the V2 fakes.
        from eth_utils import to_checksum_address as _to_cs
        try:
            return _to_cs(address)
        except (ValueError, TypeError):
            return address


# ─── FakeRpcClient ─────────────────────────────────────────────────────────


class FakeRpcClient:
    """Test-only RpcClient stand-in.

    Duck-types defipy.twin._rpc.RpcClient: same get_w3() / block_number()
    surface. LiveProvider._with_client(fake) accepts it for unit tests.
    """

    def __init__(self, fake_w3: FakeWeb3):
        self._w3 = fake_w3
        self._chain_id_cache = None

    def get_w3(self):
        return self._w3

    def block_number(self) -> int:
        return self._w3.eth.block_number

    def chain_id(self) -> int:
        # Mirror production C9 — cache on first access. Tests for
        # cross-snapshot caching introspect _w3.eth._chain_id_reads.
        if self._chain_id_cache is None:
            self._chain_id_cache = self._w3.eth.chain_id
        return self._chain_id_cache

    def block_timestamp(self, block_number: int) -> int:
        return self._w3.eth.get_block(block_number).timestamp

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
    pool,
    tokens: list,
    latest_block: int = 19_500_000,
    chain_id: int = 1,
    block_timestamp: int = 1_710_000_000,
) -> FakeRpcClient:
    """Construct a FakeRpcClient pre-loaded with a pool + tokens.

    Single entry point for tests. Returns a FakeRpcClient ready for
    `LiveProvider._with_client(client)`. Dispatches on pool spec type:
    `V2PoolSpec` → V2 pair fake; `V3PoolSpec` → V3 pool fake +
    Multicall3 fake auto-mounted at the canonical Multicall3 address.

    Parameters
    ----------
    pool : V2PoolSpec | V3PoolSpec
        Pool metadata. V2: address, token addrs, raw reserves.
        V3: address, token addrs, sqrtPriceX96, liquidity, fee,
        tickSpacing, tick.
    tokens : list[TokenSpec]
        Token metadata (symbol, decimals) for token0 and token1.
        Must include specs for both addresses referenced by `pool`.
    latest_block : int
        Block number returned by `eth_blockNumber`. Defaults to a
        canonical mid-2024 block (19_500_000) for stability across
        tests.
    chain_id : int
        Chain id returned by `eth_chainId`. Defaults to 1 (mainnet).
    block_timestamp : int
        Timestamp returned by `eth_getBlockByNumber(N).timestamp`
        AND by Multicall3.getCurrentBlockTimestamp(). Defaults to a
        canonical 2024-03 timestamp.
    """
    fake = FakeWeb3(
        latest_block = latest_block,
        chain_id = chain_id,
        block_timestamp = block_timestamp,
    )
    if isinstance(pool, V2PoolSpec):
        fake._pool_specs[pool.address] = pool
    elif isinstance(pool, V3PoolSpec):
        fake._pool_specs[pool.address] = pool
        # V3 reads go through Multicall3. Mount a fake at the canonical
        # Multicall3 address so LiveProvider's
        # `w3.eth.contract(address=MULTICALL3_ADDRESS, abi=...)` resolves.
        fake._multicall_mounted = True
    elif isinstance(pool, BalancerPoolSpec):
        # Balancer reads go through Multicall3 over two round trips.
        # Register the spec at BOTH the pool address (getPoolId/getVault/
        # getNormalizedWeights) and the vault address (getPoolTokens) so
        # the selector → spec dispatch resolves for both targets.
        fake._pool_specs[pool.address] = pool
        fake._pool_specs[pool.vault_address] = pool
        fake._multicall_mounted = True
    elif isinstance(pool, CurvePoolSpec):
        # Curve reads go through Multicall3 (A/coins(i)/balances(i) +
        # timestamp, plus the optional coin-count probe). Register at the
        # pool address; coins/balances dispatch per-index against it.
        fake._pool_specs[pool.address] = pool
        fake._multicall_mounted = True
    else:
        raise TypeError(
            "build_fake_client: pool must be V2PoolSpec, V3PoolSpec, "
            "BalancerPoolSpec, or CurvePoolSpec; got {}"
            .format(type(pool).__name__)
        )
    for token in tokens:
        fake._token_specs[token.address] = token
    # Sanity check: the pool's referenced token addrs must have specs.
    if isinstance(pool, CurvePoolSpec):
        referenced = set(pool.coin_addresses)
    else:
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


# ─── Canonical V3 pool fixture: USDC/WETH 0.05% mainnet ────────────────────
#
# Per STATE_TWIN_PHASE_2_EXPANDED.md: USDC/WETH V3 is the canonical
# Phase 2 smoke pool — long-running, deep liquidity, mixed decimals.
# The brief listed this pool as "3000bps" but the address actually
# resolves to the 0.05% (500bps) tier on mainnet. Constants renamed
# for accuracy. Same token addresses as the V2 fixture
# (token0 = USDC 6dec, token1 = WETH 18dec).

USDC_WETH_V3_POOL = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"


def canonical_usdc_weth_v3_spec(
    *,
    sqrt_price_x96: int = 1_366_488_517_146_854_400_000_000_000_000,  # ~ETH/USDC at $3300
    liquidity: int = 10_000_000_000_000_000_000_000,                   # ~1e22, realistic
    tick: int = 200_000,
    fee: int = 3000,
    tick_spacing: int = 60,
) -> V3PoolSpec:
    """Build a V3PoolSpec at canonical USDC/WETH addresses.

    Defaults capture a representative mainnet state for the 0.3% pool
    (sqrtPriceX96 corresponds roughly to $3300/ETH). Tests can override
    individual fields for boundary cases. Token addresses match the V2
    fixture so test_live_twin_token_from_exchange_populated style
    assertions reuse the same constants.
    """
    return V3PoolSpec(
        address = USDC_WETH_V3_POOL,
        token0_address = USDC_ADDRESS,
        token1_address = WETH_ADDRESS,
        sqrt_price_x96 = sqrt_price_x96,
        tick = tick,
        liquidity = liquidity,
        fee = fee,
        tick_spacing = tick_spacing,
    )


def canonical_usdc_weth_v3_token_specs() -> list:
    # Same tokens as V2 — re-export under a V3-namespaced helper for
    # cross-test readability ("V3 tests use the V3 helper").
    return canonical_weth_usdc_token_specs()


# ─── Canonical Balancer pool fixture: BAL/WETH 80/20 mainnet ───────────────
#
# Per the Phase 2 handoff: BAL/WETH 80/20 is the canonical Balancer V2
# smoke pool — long-running, the archetypal weighted (non-50/50) pool.
# token0 = BAL (lower address), token1 = WETH; both 18 decimals.
# The Vault is the single canonical Balancer V2 Vault.

BAL_WETH_BALANCER_POOL = "0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56"
BALANCER_VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
BAL_ADDRESS = "0xba100000625a3754423978a60c9317c58a424e3D"   # token0 (lower addr)
# Real mainnet poolId for 0x5c6Ee3...; opaque to the read path (only
# used as the getPoolTokens(bytes32) argument, ignored by the fake).
BAL_WETH_POOL_ID = bytes.fromhex(
    "5c6ee304399dbdb9c8ef030ab642b10820db8f56000200000000000000000014"
)


def canonical_bal_weth_balancer_spec(
    *,
    bal_amount: float = 500_000.0,   # 500k BAL
    weth_amount: float = 1_500.0,    # 1.5k WETH (~80/20 by value)
    weight_bal: float = 0.8,
    weight_weth: float = 0.2,
) -> BalancerPoolSpec:
    """Build a BalancerPoolSpec at canonical BAL/WETH 80/20 addresses.

    Human balances/weights are scaled to raw uints / 1e18-weights by
    BalancerPoolSpec.from_human. Tests can override weights for the
    weight-sum / parity cases.
    """
    return BalancerPoolSpec.from_human(
        address = BAL_WETH_BALANCER_POOL,
        pool_id = BAL_WETH_POOL_ID,
        vault_address = BALANCER_VAULT,
        token0_address = BAL_ADDRESS,
        token1_address = WETH_ADDRESS,
        balance0 = bal_amount,
        balance1 = weth_amount,
        weight0 = weight_bal,
        weight1 = weight_weth,
        decimals0 = 18,
        decimals1 = 18,
    )


def canonical_bal_weth_token_specs() -> list:
    return [
        TokenSpec(address=BAL_ADDRESS, symbol="BAL", decimals=18),
        TokenSpec(address=WETH_ADDRESS, symbol="WETH", decimals=18),
    ]


# ─── Canonical Curve pool fixtures: USDC/DAI 2-coin + DAI/USDC/USDT 3pool ──
#
# Per the Phase 3 handoff: the DAI/USDC/USDT 3pool is the canonical
# plain Stableswap pool. A 2-coin USDC/DAI spec mirrors stableswap_setup
# for exact builder parity. Native decimals (DAI 18, USDC/USDT 6) so the
# read path's decimal adjustment is exercised.

CURVE_3POOL = "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"
DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"     # 18 dec
USDT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"    # 6 dec
# USDC_ADDRESS (6 dec) is defined in the V2 fixture section above.


def canonical_usdc_dai_curve_spec(
    *,
    usdc_amount: float = 100_000.0,
    dai_amount: float = 100_000.0,
    A: int = 10,
) -> CurvePoolSpec:
    """2-coin USDC/DAI plain pool. coin0 = USDC (6dec), coin1 = DAI
    (18dec) — matches stableswap_setup's token insertion order for
    builder parity."""
    return CurvePoolSpec.from_human(
        address = CURVE_3POOL,   # reuse the pool address as an opaque id
        coin_addresses = [USDC_ADDRESS, DAI_ADDRESS],
        balances = [usdc_amount, dai_amount],
        decimals = [6, 18],
        A = A,
    )


def canonical_3pool_curve_spec(
    *,
    dai_amount: float = 200_000_000.0,
    usdc_amount: float = 200_000_000.0,
    usdt_amount: float = 200_000_000.0,
    A: int = 2000,
) -> CurvePoolSpec:
    """3-coin DAI/USDC/USDT plain pool (the canonical Curve 3pool).
    coin0 = DAI (18dec), coin1 = USDC (6dec), coin2 = USDT (6dec)."""
    return CurvePoolSpec.from_human(
        address = CURVE_3POOL,
        coin_addresses = [DAI_ADDRESS, USDC_ADDRESS, USDT_ADDRESS],
        balances = [dai_amount, usdc_amount, usdt_amount],
        decimals = [18, 6, 6],
        A = A,
    )


def canonical_usdc_dai_curve_token_specs() -> list:
    return [
        TokenSpec(address=USDC_ADDRESS, symbol="USDC", decimals=6),
        TokenSpec(address=DAI_ADDRESS, symbol="DAI", decimals=18),
    ]


def canonical_3pool_curve_token_specs() -> list:
    return [
        TokenSpec(address=DAI_ADDRESS, symbol="DAI", decimals=18),
        TokenSpec(address=USDC_ADDRESS, symbol="USDC", decimals=6),
        TokenSpec(address=USDT_ADDRESS, symbol="USDT", decimals=6),
    ]
