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

"""LiveProvider — chain-reading State Twin provider.

v2.1 Phase 1 ships Uniswap V2 reads. V3 is Phase 2; Balancer and
Stableswap are v2.2+. Calls for those protocols raise
NotImplementedError pointing at the relevant phase / version.

Importing this module does NOT pull web3 or web3scout. Both come in
through the lazy `_rpc.make_client()` path inside `.snapshot()`. This
preserves the v2.0 invariant that `from defipy.twin import LiveProvider`
works in any install — including a bare `pip install defipy` with no
extras.

Per STATE_TWIN_PHASE_1_EXPANDED.md:

  - C1: ABC widened to `snapshot(pool_id, **kwargs)`. pool_id format
    here is "<protocol>:<address>", parsed by `_parse_pool_id`.
  - C2: Reserves come back as decimal-adjusted floats (raw / 10**dec)
    so `StateTwinBuilder._build_v2` works without modification.
  - D1: web3scout's ConnectW3 + ABILoad + FetchToken under the hood,
    via the `_rpc` module.
  - D5: Token decimals + symbols read via FetchToken (which doesn't
    block-pin metadata reads — see _rpc.fetch_token docstring).
  - C3: `_with_client(client)` test-only classmethod for injection.
  - R1: "latest" resolved to a concrete block once at the top of
    `.snapshot()`, then all subsequent reads pin to that block.
"""

from typing import Any, Optional

from defipy.twin.provider import StateTwinProvider
from defipy.twin.snapshot import (
    PoolSnapshot,
    V2PoolSnapshot,
    V3PoolSnapshot,
)


# Supported protocol identifiers for the pool_id string format.
_PROTO_V2 = "uniswap_v2"
_PROTO_V3 = "uniswap_v3"
_PROTO_BALANCER = "balancer"
_PROTO_STABLESWAP = "stableswap"

_KNOWN_PROTOCOLS = (_PROTO_V2, _PROTO_V3, _PROTO_BALANCER, _PROTO_STABLESWAP)


class LiveProvider(StateTwinProvider):
    """Chain-reading State Twin provider.

    v2.1 Phase 1: Uniswap V2 only.

    Construction
    ------------
    Public: `LiveProvider(rpc_url)` — pass an Ethereum mainnet (or
    testnet) RPC URL. The first `.snapshot()` call constructs the
    web3 client lazily.

    Test-only: `LiveProvider._with_client(client)` — inject a
    duck-typed RpcClient (real `defipy.twin._rpc.RpcClient` or a
    test fake). Used by mocked-RPC unit tests; not part of the
    public surface.

    pool_id format
    --------------
    `pool_id` is a string of the form `"<protocol>:<address>"`:

        "uniswap_v2:0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"

    Address casing is normalized internally — lowercase, uppercase,
    or checksum-mixed all work. The protocol prefix selects the read
    path; v2.1 Phase 1 supports `uniswap_v2`. Other protocols raise
    NotImplementedError pointing at the relevant phase/version.

    Block pinning
    -------------
    Pass `block_number=N` to read at a specific block. Without it,
    `"latest"` resolves to a concrete block_number once at the top of
    `.snapshot()`, then every subsequent `eth_call` pins to that
    block. State drift across reads inside one snapshot can't happen.

    Stateless snapshots, reused connection
    --------------------------------------
    Each `.snapshot()` produces a fresh PoolSnapshot from a fresh chain
    read — no caching of pool state, block data, or snapshot results.
    The underlying web3 connection IS reused: the first `.snapshot()`
    or `.get_w3()` call constructs an RpcClient via `make_client()`
    and caches it on the instance for the rest of its lifetime. For
    long-running processes that may see the connection go stale,
    construct a fresh LiveProvider periodically. Snapshot caching,
    connection pooling, and reorg-detection are consumer concerns
    (see DeFiMind for an opinionated take).

    Examples
    --------
        # Latest block
        provider = LiveProvider("https://eth-mainnet.g.alchemy.com/v2/<key>")
        snap = provider.snapshot("uniswap_v2:0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc")
        lp = StateTwinBuilder().build(snap)

        # Specific historical block
        snap = provider.snapshot(
            "uniswap_v2:0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
            block_number=19_500_000,
        )
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        # Client is constructed lazily on the first .snapshot() or
        # .get_w3() call so the constructor works without web3 installed.
        # Cached for the life of the LiveProvider instance per D20 —
        # snapshots are stateless (no caching of pool state, block data,
        # or snapshot results) but the connection is reused across calls.
        # Tests inject a client via _with_client(), which sets this
        # attribute directly to bypass the production make_client() path.
        self._cached_client = None

    # ─── Test-only constructor ─────────────────────────────────────────────

    @classmethod
    def _with_client(cls, client) -> "LiveProvider":
        """Inject a duck-typed RpcClient. Test-only.

        The argument must duck-type defipy.twin._rpc.RpcClient:

            client.get_w3() -> web3.Web3-like
            client.block_number() -> int

        See python/test/twin/_fake_rpc.py for the test implementation.
        Production callers should always use `LiveProvider(rpc_url)`.
        """
        provider = cls.__new__(cls)
        provider.rpc_url = "<injected>"
        provider._cached_client = client
        return provider

    # ─── Public API: web3 access ───────────────────────────────────────────

    def get_w3(self):
        """Return the underlying web3.Web3 instance.

        DeFiPy is read-only by design; LiveProvider does not sign or
        send transactions. Consumers needing to act on-chain pull the
        web3 instance via this method and bring their own signing
        infrastructure (private key management, hardware wallet, MPC
        vault, signing service — DeFiPy stays out of that opinion).

        Lazy construction. The underlying RpcClient is constructed on
        first call to get_w3() or .snapshot() (whichever comes first)
        and cached for the life of the LiveProvider instance. Both
        methods share one connection. For long-running processes that
        may see the connection go stale, construct a fresh
        LiveProvider periodically or build your own
        connection-management layer around get_w3().

        Returns
        -------
        web3.Web3
            The underlying web3 instance, ready for direct use.

        Raises
        ------
        ImportError
            If [chain] extra is not installed; surfaced from
            _rpc.make_client() with the install instructions.
        """
        return self._get_client().get_w3()

    # ─── Public API ────────────────────────────────────────────────────────

    def snapshot(self, pool_id: str, **kwargs) -> PoolSnapshot:
        """Construct a PoolSnapshot from on-chain state.

        Parameters
        ----------
        pool_id : str
            "<protocol>:<address>" format. Protocol must be one of:
            "uniswap_v2" (Phase 1), "uniswap_v3" (Phase 2),
            "balancer" / "stableswap" (v2.2+).
        **kwargs
            block_number : int | None
                Specific block to read. Default: resolves "latest" to
                a concrete block once at the start of the snapshot.

        Returns
        -------
        PoolSnapshot
            For uniswap_v2: a `V2PoolSnapshot` with `reserve0` /
            `reserve1` as decimal-adjusted floats (raw / 10**decimals)
            and `token0_name` / `token1_name` populated from on-chain
            symbol() reads.

        Raises
        ------
        ValueError
            If pool_id is malformed or names an unknown protocol.
        NotImplementedError
            If pool_id names a known-but-not-yet-implemented protocol
            (uniswap_v3, balancer, stableswap in Phase 1).
        """
        protocol, address = self._parse_pool_id(pool_id)
        block_number = kwargs.get("block_number", None)

        if protocol == _PROTO_V2:
            return self._snapshot_v2(address, block_number)
        if protocol == _PROTO_V3:
            return self._snapshot_v3(
                address,
                block_number,
                kwargs.get("lwr_tick", None),
                kwargs.get("upr_tick", None),
            )
        if protocol == _PROTO_BALANCER:
            return self._snapshot_balancer(address, block_number)
        if protocol == _PROTO_STABLESWAP:
            raise NotImplementedError(
                "LiveProvider Stableswap reads are v2.2+ work. For now, "
                "use MockProvider.snapshot('usdc_dai_stableswap_A10')."
            )
        # _parse_pool_id guards above; unreachable if reached.
        raise ValueError(
            "LiveProvider: unhandled protocol {!r}".format(protocol)
        )

    # ─── pool_id parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_pool_id(pool_id: str) -> tuple:
        """Split "<protocol>:<address>" into (protocol, address).

        Raises ValueError on malformed input. Empty protocol, empty
        address, missing colon, or unknown protocol all surface here
        with a message that names the offending input and lists the
        valid protocols. Phase 1 user feedback comes from this surface
        — make it informative.
        """
        if not isinstance(pool_id, str) or ":" not in pool_id:
            raise ValueError(
                "LiveProvider: pool_id must be '<protocol>:<address>'; "
                "got {!r}. Valid protocols: {}"
                .format(pool_id, list(_KNOWN_PROTOCOLS))
            )
        protocol, _, address = pool_id.partition(":")
        if not protocol:
            raise ValueError(
                "LiveProvider: pool_id has empty protocol prefix; "
                "got {!r}. Format: '<protocol>:<address>'."
                .format(pool_id)
            )
        if not address:
            raise ValueError(
                "LiveProvider: pool_id has empty address; got {!r}. "
                "Format: '<protocol>:<address>'."
                .format(pool_id)
            )
        if protocol not in _KNOWN_PROTOCOLS:
            raise ValueError(
                "LiveProvider: unknown protocol {!r} in pool_id. "
                "Valid protocols: {}"
                .format(protocol, list(_KNOWN_PROTOCOLS))
            )
        return protocol, address

    # ─── Client management ─────────────────────────────────────────────────

    def _get_client(self):
        """Return the cached client (constructing it on first call).

        Phase 3a — caching changed from "construct per snapshot" to
        "construct once, reuse." Snapshots remain stateless (no caching
        of pool state, block data, or snapshot results); only the
        connection is reused. Test injection via _with_client() sets
        _cached_client directly so the production make_client() path
        is bypassed."""
        if self._cached_client is not None:
            return self._cached_client
        # Lazy import — keep `from defipy.twin import LiveProvider`
        # working without web3 installed.
        from defipy.twin import _rpc
        self._cached_client = _rpc.make_client(self.rpc_url)
        return self._cached_client

    # ─── V2 snapshot ───────────────────────────────────────────────────────

    def _snapshot_v2(
        self,
        pool_address: str,
        block_number: Optional[int],
    ) -> V2PoolSnapshot:
        from defipy.twin import _rpc

        client = self._get_client()
        w3 = client.get_w3()

        # R1 — block consistency. Resolve "latest" once at the top so
        # every subsequent eth_call pins to the same concrete block.
        # If a new block lands mid-snapshot, reserves and total_supply
        # could otherwise come from different blocks.
        if block_number is None:
            block_number = client.block_number()

        # Address normalization: web3 rejects addresses with mixed
        # casing that don't match EIP-55 checksum. Normalize via the
        # underlying w3 to accept lowercase / uppercase / checksum
        # input uniformly.
        addr = w3.to_checksum_address(pool_address)

        pair = _rpc.load_v2_pair_contract(w3, addr)

        # All three reserve-side reads pin to the same block. Token
        # address reads also pin (token0/token1 don't change, but
        # pinning is cheap and keeps the consistency story simple).
        token0_addr = pair.functions.token0().call(block_identifier=block_number)
        token1_addr = pair.functions.token1().call(block_identifier=block_number)
        reserves = pair.functions.getReserves().call(block_identifier=block_number)
        # totalSupply is read but not stored on the V2PoolSnapshot in
        # Phase 1 — StateTwinBuilder reconstructs supply via the V2
        # invariant during add_liquidity. Read it anyway so a future
        # snapshot.total_supply field can be added without changing
        # the read pattern.
        _ = pair.functions.totalSupply().call(block_identifier=block_number)

        # FetchToken returns a uniswappy.erc.ERC20 with .token_name
        # (symbol), .token_addr, .token_decimal. metadata reads happen
        # at "latest" — see _rpc.fetch_token docstring for why that's
        # OK in practice.
        tkn0 = _rpc.fetch_token(w3, token0_addr)
        tkn1 = _rpc.fetch_token(w3, token1_addr)

        # C2 — decimal adjustment. raw_reserve / 10**decimals produces
        # a Python float in whole-token units, matching MockProvider's
        # contract. StateTwinBuilder._build_v2 expects this format and
        # passes the values directly to lp.add_liquidity().
        reserve0 = _rpc.amt_to_decimal(tkn0, int(reserves[0]))
        reserve1 = _rpc.amt_to_decimal(tkn1, int(reserves[1]))

        # Phase 2 C5 enrichment: populate chain context. V2 keeps
        # sequential reads — one extra eth_getBlockByNumber for
        # timestamp. Multicall optimization is V3-only.
        timestamp = client.block_timestamp(block_number)
        chain_id = client.chain_id()

        return V2PoolSnapshot(
            pool_id = pool_address,
            token0_name = tkn0.token_name,
            token1_name = tkn1.token_name,
            reserve0 = reserve0,
            reserve1 = reserve1,
            block_number = block_number,
            timestamp = timestamp,
            chain_id = chain_id,
        )

    # ─── V3 snapshot ───────────────────────────────────────────────────────

    def _snapshot_v3(
        self,
        pool_address: str,
        block_number: Optional[int],
        lwr_tick: Optional[int],
        upr_tick: Optional[int],
    ) -> V3PoolSnapshot:
        from defipy.twin import _rpc

        client = self._get_client()
        w3 = client.get_w3()

        # R1 — block consistency. Same discipline as V2.
        if block_number is None:
            block_number = client.block_number()

        addr = w3.to_checksum_address(pool_address)
        chain_id = client.chain_id()

        # All V3-specific reads + getCurrentBlockTimestamp folded into
        # one Multicall3.aggregate3 round trip per D6/C8. Token
        # metadata (symbol/decimals) is read separately via FetchToken
        # — its API doesn't accept block_identifier or fold cleanly into
        # the multicall format.
        calls = [
            (addr, "token0()", ["address"]),
            (addr, "token1()", ["address"]),
            (addr, "slot0()",
                ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"]),
            (addr, "liquidity()", ["uint128"]),
            (addr, "fee()", ["uint24"]),
            (addr, "tickSpacing()", ["int24"]),
            (_rpc.MULTICALL3_ADDRESS, "getCurrentBlockTimestamp()", ["uint256"]),
        ]
        results = _rpc.multicall_aggregate3(w3, calls, block_number)
        token0_addr = results[0]
        token1_addr = results[1]
        slot0_tuple = results[2]
        sqrt_price_x96 = int(slot0_tuple[0])
        current_tick = int(slot0_tuple[1])
        liquidity = int(results[3])
        fee = int(results[4])
        tick_spacing = int(results[5])
        timestamp = int(results[6])

        # Tick range default per D13 — full range from getMinTick /
        # getMaxTick at the pool's tick_spacing. Caller can override
        # either bound via kwargs.
        from uniswappy.utils.tools.v3 import UniV3Utils, TickMath, SqrtPriceMath
        if lwr_tick is None:
            lwr_tick = UniV3Utils.getMinTick(tick_spacing)
        if upr_tick is None:
            upr_tick = UniV3Utils.getMaxTick(tick_spacing)
        if lwr_tick >= upr_tick:
            raise ValueError(
                "LiveProvider V3: lwr_tick ({}) must be < upr_tick ({})"
                .format(lwr_tick, upr_tick)
            )

        # C4 + R14 — derive (amount0, amount1) for a position spanning
        # [lwr_tick, upr_tick] with active liquidity L at sqrt_current.
        # Three regimes:
        #   sqrt_current < sqrt_lower  → all in token0 (single-sided)
        #   sqrt_current > sqrt_upper  → all in token1 (single-sided)
        #   in-range                   → both nonzero
        sqrt_lower = int(TickMath.getSqrtRatioAtTick(lwr_tick))
        sqrt_upper = int(TickMath.getSqrtRatioAtTick(upr_tick))
        if sqrt_price_x96 <= sqrt_lower:
            amount0_raw = int(SqrtPriceMath.getAmount0Delta(
                sqrt_lower, sqrt_upper, liquidity, False,
            ))
            amount1_raw = 0
        elif sqrt_price_x96 >= sqrt_upper:
            amount0_raw = 0
            amount1_raw = int(SqrtPriceMath.getAmount1Delta(
                sqrt_lower, sqrt_upper, liquidity, False,
            ))
        else:
            amount0_raw = int(SqrtPriceMath.getAmount0Delta(
                sqrt_price_x96, sqrt_upper, liquidity, False,
            ))
            amount1_raw = int(SqrtPriceMath.getAmount1Delta(
                sqrt_lower, sqrt_price_x96, liquidity, False,
            ))

        # Token metadata reads happen at "latest" — same caveat as V2
        # path, FetchToken doesn't accept block_identifier.
        # eth_abi decodes addresses as lowercase; normalize to checksum
        # form before handing to FetchToken since real web3 rejects
        # non-checksummed mixed-case input.
        tkn0 = _rpc.fetch_token(w3, w3.to_checksum_address(token0_addr))
        tkn1 = _rpc.fetch_token(w3, w3.to_checksum_address(token1_addr))

        # D15 — decimal-adjusted floats matching V2 contract.
        reserve0 = amount0_raw / (10 ** tkn0.token_decimal)
        reserve1 = amount1_raw / (10 ** tkn1.token_decimal)

        return V3PoolSnapshot(
            pool_id = pool_address,
            token0_name = tkn0.token_name,
            token1_name = tkn1.token_name,
            reserve0 = reserve0,
            reserve1 = reserve1,
            fee = fee,
            tick_spacing = tick_spacing,
            lwr_tick = lwr_tick,
            upr_tick = upr_tick,
            block_number = block_number,
            timestamp = timestamp,
            chain_id = chain_id,
        )

    # ─── Balancer snapshot ───────────────────────────────────────────────────

    def _snapshot_balancer(self, pool_address, block_number):
        from defipy.twin import _rpc
        from defipy.twin.snapshot import BalancerPoolSnapshot

        client = self._get_client()
        w3 = client.get_w3()

        # R1 — block consistency. Same discipline as V2/V3. Both round
        # trips below pin to this block.
        if block_number is None:
            block_number = client.block_number()

        addr = w3.to_checksum_address(pool_address)
        chain_id = client.chain_id()

        # RT1 — no-arg pool reads + block timestamp, one pinned batch.
        # Balancer token balances live on the Vault keyed by poolId, so
        # they need a second round trip (poolId isn't known until RT1
        # returns — can't fold into one batch).
        rt1_calls = [
            (addr, "getPoolId()", [], [], ["bytes32"]),
            (addr, "getVault()", [], [], ["address"]),
            (addr, "getNormalizedWeights()", [], [], ["uint256[]"]),
            (_rpc.MULTICALL3_ADDRESS, "getCurrentBlockTimestamp()", [], [], ["uint256"]),
        ]
        pool_id, vault_addr, norm_weights, timestamp = _rpc.multicall_aggregate3_args(
            w3, rt1_calls, block_number,
        )
        timestamp = int(timestamp)

        # RT2 — balances live on the Vault, keyed by poolId. Single
        # arg-bearing call; the one-element list unpacks via trailing
        # comma to the (tokens, balances, lastChangeBlock) 3-tuple.
        (tokens, balances, _last_change), = _rpc.multicall_aggregate3_args(
            w3,
            [(w3.to_checksum_address(vault_addr), "getPoolTokens(bytes32)",
              ["bytes32"], [pool_id],
              ["address[]", "uint256[]", "uint256"])],
            block_number,
        )

        # v2.2 scope: 2-asset weighted pools only (matches the snapshot
        # and balancerpy's BalancerImpLoss scope).
        if len(tokens) != 2:
            raise NotImplementedError(
                "LiveProvider Balancer: v2.2 supports 2-asset weighted "
                "pools only; pool {} has {} tokens."
                .format(pool_address, len(tokens))
            )

        # On-chain normalized weights are 1e18-scaled and sum to exactly
        # 1e18. Read both honestly (don't derive weight1 = 1 - weight0);
        # the float sum lands within BalancerPoolSnapshot's 1e-9 tol.
        weight0 = int(norm_weights[0]) / 1e18
        weight1 = int(norm_weights[1]) / 1e18

        # Token metadata at "latest" — same caveat as V2/V3. eth_abi
        # decodes addresses lowercased; re-checksum before FetchToken.
        tkn0 = _rpc.fetch_token(w3, w3.to_checksum_address(tokens[0]))
        tkn1 = _rpc.fetch_token(w3, w3.to_checksum_address(tokens[1]))

        # C2 — decimal-adjusted floats in whole-token units.
        reserve0 = _rpc.amt_to_decimal(tkn0, int(balances[0]))
        reserve1 = _rpc.amt_to_decimal(tkn1, int(balances[1]))

        return BalancerPoolSnapshot(
            pool_id = pool_address,
            token0_name = tkn0.token_name,
            token1_name = tkn1.token_name,
            reserve0 = reserve0,
            reserve1 = reserve1,
            weight0 = weight0,
            weight1 = weight1,
            block_number = block_number,
            timestamp = timestamp,
            chain_id = chain_id,
        )
