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

from uniswappy.erc import ERC20
from uniswappy.cpt.factory import UniswapFactory
from uniswappy.utils.data import UniswapExchangeData
from uniswappy.process.join import Join as UniJoin

from balancerpy.erc import ERC20 as BERC20
from balancerpy.vault import BalancerVault
from balancerpy.cwpt.factory import BalancerFactory
from balancerpy.utils.data import BalancerExchangeData
from balancerpy.process.join import Join as BJoin

from stableswappy.erc import ERC20 as SERC20
from stableswappy.vault import StableswapVault
from stableswappy.cst.factory import StableswapFactory
from stableswappy.utils.data import StableswapExchangeData
from stableswappy.process.join import Join as SJoin

from defipy.twin.snapshot import (
    PoolSnapshot,
    V2PoolSnapshot,
    V3PoolSnapshot,
    BalancerPoolSnapshot,
    StableswapPoolSnapshot,
)


# Internal sentinel for the LP holder inside a built twin. Not
# surfaced to callers — primitives take lp_init_amt as a scalar and
# never look up by user. Matches the conftest convention of a single
# 100%-owner.
_TWIN_USER = "twin_user"


class StateTwinBuilder:
    """Construct a protocol-specific exchange object from a PoolSnapshot.

    Dispatches on snapshot type. The resulting exchange object is
    functionally identical to what the conftest fixtures produce for
    the same reserves — same get_reserve outputs, same spot prices,
    same total_supply.
    """

    def build(self, snapshot: PoolSnapshot):
        if isinstance(snapshot, V2PoolSnapshot):
            return self._build_v2(snapshot)
        if isinstance(snapshot, V3PoolSnapshot):
            return self._build_v3(snapshot)
        if isinstance(snapshot, BalancerPoolSnapshot):
            return self._build_balancer(snapshot)
        if isinstance(snapshot, StableswapPoolSnapshot):
            return self._build_stableswap(snapshot)
        raise TypeError(
            "StateTwinBuilder: unknown snapshot type {}"
            .format(type(snapshot).__name__)
        )

    # ─── Provenance tagging ─────────────────────────────────────────────────

    def _tag_provenance(self, lp, s: PoolSnapshot):
        """Stamp live-vs-synthetic provenance onto a built twin.

        Every twin is reconstructed from a single state read — reserves
        (plus, for live reads, a block number) — with no swap/event
        replay and no recovered LP-holder distribution. The twin's LP
        set is therefore a single synthetic provider and its swap
        history is empty *by construction*, regardless of the real pool.

        The discriminator for "is this a chain snapshot?" is
        `s.block_number is not None`: LiveProvider populates block_number
        from on-chain reads; MockProvider leaves it None by design (see
        the PoolSnapshot docstring in snapshot.py). When `live_snapshot`
        is True, downstream consumers MUST treat per-LP concentration and
        swap-history metrics as unknown rather than reading the synthetic
        single-provider / empty-history state as ground truth — see
        CheckPoolHealth, which reports those fields as None for live
        twins. Mock twins keep `live_snapshot = False` and continue to
        report concrete values so existing notebook/test behavior is
        unaffected.

        `snapshot_block_number` carries the block the snapshot was read
        at (None for mock) so consumers can surface provenance.
        """
        lp.live_snapshot = s.block_number is not None
        lp.snapshot_block_number = s.block_number
        return lp

    # ─── Uniswap V2 ─────────────────────────────────────────────────────────

    def _build_v2(self, s: V2PoolSnapshot):
        tkn0 = ERC20(s.token0_name, "0xtwin_{}_{}".format(s.pool_id, s.token0_name))
        tkn1 = ERC20(s.token1_name, "0xtwin_{}_{}".format(s.pool_id, s.token1_name))
        factory = UniswapFactory(
            "twin_{}_factory".format(s.pool_id),
            "0xtwin_{}_factory".format(s.pool_id),
        )
        exch_data = UniswapExchangeData(
            tkn0 = tkn0, tkn1 = tkn1,
            symbol = "LP", address = "0xtwin_{}_lp".format(s.pool_id),
        )
        lp = factory.deploy(exch_data)
        lp.add_liquidity(_TWIN_USER, s.reserve0, s.reserve1, s.reserve0, s.reserve1)

        # v2.2.2 — stamp the REAL LP totalSupply when the snapshot carries
        # it (LiveProvider does; MockProvider / old wire forms leave it
        # None and keep the synthetic √(r0·r1) supply set by add_liquidity).
        # add_liquidity sets total_supply = √(reserve0·reserve1), which
        # drifts from the real on-chain supply as fees grow reserves —
        # mis-scaling AnalyzePosition's absolute outputs (they read
        # lp_init_amt as a scalar against total_supply).
        if s.total_supply is not None:
            self._set_v2_total_supply(lp, s.total_supply)

        return self._tag_provenance(lp, s)

    @staticmethod
    def _set_v2_total_supply(lp, real_supply: float) -> None:
        """Overwrite a built V2 twin's LP supply with the real on-chain
        totalSupply, keeping the single synthetic provider (_TWIN_USER) in
        lockstep so get_liquidity() and the holder's balance both report
        the real value.

        The uniswappy V2 exchange stores `total_supply` and the
        `liquidity_providers` ledger in MACHINE units (get_liquidity() /
        get_liquidity_from_provider() apply convert_to_human), while the
        snapshot carries `real_supply` in human (18-dec-adjusted) units —
        so route through the exchange's own `convert_to_machine` to match
        whatever precision mode the twin uses (NOT a raw assignment)."""
        machine_supply = lp.convert_to_machine(real_supply)
        lp.total_supply = machine_supply
        lp.liquidity_providers[_TWIN_USER] = machine_supply

    # ─── Uniswap V3 ─────────────────────────────────────────────────────────

    def _build_v3(self, s: V3PoolSnapshot):
        tkn0 = ERC20(s.token0_name, "0xtwin_{}_{}".format(s.pool_id, s.token0_name))
        tkn1 = ERC20(s.token1_name, "0xtwin_{}_{}".format(s.pool_id, s.token1_name))
        factory = UniswapFactory(
            "twin_{}_factory".format(s.pool_id),
            "0xtwin_{}_factory".format(s.pool_id),
        )
        exch_data = UniswapExchangeData(
            tkn0 = tkn0, tkn1 = tkn1,
            symbol = "LP", address = "0xtwin_{}_lp".format(s.pool_id),
            version = "V3",
            tick_spacing = s.tick_spacing,
            fee = s.fee,
        )
        lp = factory.deploy(exch_data)
        UniJoin().apply(
            lp, _TWIN_USER, s.reserve0, s.reserve1, s.lwr_tick, s.upr_tick,
        )
        return self._tag_provenance(lp, s)

    # ─── Balancer 2-asset ───────────────────────────────────────────────────

    def _build_balancer(self, s: BalancerPoolSnapshot):
        base = BERC20(s.token0_name, "0xtwin_{}_{}".format(s.pool_id, s.token0_name))
        base.deposit(_TWIN_USER, s.reserve0)
        opp = BERC20(s.token1_name, "0xtwin_{}_{}".format(s.pool_id, s.token1_name))
        opp.deposit(_TWIN_USER, s.reserve1)

        vault = BalancerVault()
        vault.add_token(base, s.weight0)
        vault.add_token(opp, s.weight1)

        factory = BalancerFactory(
            "twin_{}_factory".format(s.pool_id),
            "0xtwin_{}_factory".format(s.pool_id),
        )
        exch_data = BalancerExchangeData(
            vault = vault,
            symbol = "BPT",
            address = "0xtwin_{}_lp".format(s.pool_id),
        )
        lp = factory.deploy(exch_data)
        BJoin().apply(lp, _TWIN_USER, s.pool_shares_init)
        return self._tag_provenance(lp, s)

    # ─── Stableswap 2-asset ─────────────────────────────────────────────────

    def _build_stableswap(self, s: StableswapPoolSnapshot):
        vault = StableswapVault()
        for name, amt in zip(s.token_names, s.reserves):
            tkn = SERC20(name, "0xtwin_{}_{}".format(s.pool_id, name), s.decimals)
            tkn.deposit(_TWIN_USER, amt)
            vault.add_token(tkn)

        factory = StableswapFactory(
            "twin_{}_factory".format(s.pool_id),
            "0xtwin_{}_factory".format(s.pool_id),
        )
        exch_data = StableswapExchangeData(
            vault = vault,
            symbol = "CST",
            address = "0xtwin_{}_lp".format(s.pool_id),
        )
        lp = factory.deploy(exch_data)
        SJoin().apply(lp, _TWIN_USER, s.A)
        return self._tag_provenance(lp, s)
