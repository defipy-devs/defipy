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

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProtocolMetrics:
    """ Per-pool metrics produced by CompareProtocols.

        One ProtocolMetrics per input pool, representing the pool's
        behavior at the shared `price_shock` and `amount` values that
        the CompareProtocols run was configured with.

        Attributes
        ----------
        pool_label : str
            Human-readable label, caller-supplied or protocol-derived
            default.
        protocol : str
            One of "uniswap_v2" | "uniswap_v3" | "balancer" | "stableswap".
            Drives how downstream readers interpret the other fields
            (e.g. "slippage = None for balancer is expected, not a
            bug").
        il_at_shock : Optional[float]
            Absolute |IL| at the configured symmetric price_shock,
            averaged over +shock and -shock. Fractional, non-negative.
            None when the shock is unreachable — currently only occurs
            for high-A stableswap pools where small shocks lie outside
            the physically achievable |ε| < 0.95 regime. A
            clarifying note is appended to ProtocolComparison.notes
            when this happens.
        slippage_at_amount : Optional[float]
            Fractional slippage for a trade of `amount` tokens on this
            pool. V2 and V3 only in v1; None for Balancer and
            Stableswap with an explanatory note. None is not a failure
            — it's a documented scope boundary. A future version will
            extend CalculateSlippage to cover weighted and stableswap
            pools.
        tvl_in_token_in : float
            Current pool TVL denominated in the input token. Reported
            for reference and for the caller's own relative sizing.
    """
    pool_label: str
    protocol: str
    il_at_shock: Optional[float]
    slippage_at_amount: Optional[float]
    tvl_in_token_in: float


@dataclass
class ProtocolComparison:
    """ Result of CompareProtocols.

        Cross-protocol IL + slippage comparison for the same capital
        on the same input token across two pools that may live on
        different AMM designs (V2, V3, Balancer, Stableswap).

        Independent advantage labels rather than a single "winner"
        verdict — matches the signal-surfacer convention established
        by CompareFeeTiers, DetectRugSignals, AggregatePortfolio,
        AssessDepegRisk. Different protocols are genuinely better on
        different axes; collapsing to one number would hide the
        tradeoff.

        Attributes
        ----------
        price_shock : float
            Symmetric alpha shock magnitude used for IL comparison.
            Echo from the constructor.
        amount : float
            Trade size used for slippage comparison. Echo from
            .apply(amount=...).
        token_in_name : str
            Symbol of the token treated as the numeraire / trade
            input. Echo from the argument or from lp_a.token0 when
            defaulted.
        pool_a, pool_b : ProtocolMetrics
            Per-pool metrics. Pool a is the first positional argument
            to .apply().
        il_advantage : Optional[str]
            One of "pool_a" | "pool_b" | "tied" | None. "tied" when
            the two IL values agree to 1e-9. None when either
            `il_at_shock` is None (unreachable regime), in which case
            the comparison is undefined and a note explains why.
        slippage_advantage : Optional[str]
            Same semantics as il_advantage, applied to
            slippage_at_amount. None when either slippage is None
            (Balancer / Stableswap in v1). A caller building a
            best-of-both-worlds summary reads both advantages
            independently.
        notes : List[str]
            Scope caveats, unreachable flags, or any condition a
            caller reading the result might otherwise miss. Appended
            by the primitive in input-pool order.
    """
    price_shock: float
    amount: float
    token_in_name: str
    pool_a: ProtocolMetrics
    pool_b: ProtocolMetrics
    il_advantage: Optional[str]
    slippage_advantage: Optional[str]
    notes: List[str]
