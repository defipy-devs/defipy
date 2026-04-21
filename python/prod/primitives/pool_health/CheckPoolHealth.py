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

from uniswappy.utils.data import UniswapExchangeData
from ...utils.data import PoolHealth


# V2 burns MINIMUM_LIQUIDITY LP tokens to address "0" at the first mint
# to prevent division-by-tiny issues. This sentinel is not a real LP and
# should be excluded from LP counting and concentration metrics.
_V2_SENTINEL_ADDRESS = "0"

# Default rolling window for recent fee accrual. Small enough to reflect
# recent pool activity, large enough to smooth single-swap noise.
_DEFAULT_RECENT_WINDOW = 20


class CheckPoolHealth:

    """ Snapshot of pool-level health metrics for deposit-fitness analysis.

        Answers "is this a pool I'd deposit into?" — TVL in numeraire,
        fee accrual activity, LP concentration, spot price. Pool-level
        only, not position-level; position analysis belongs in
        AnalyzePosition and friends.

        Answers: Q4.1 (pool health), Q4.2 (LP concentration),
        Q4.3 (fee accrual rate), Q7.1 (TVL) from
        DEFIMIND_TIER1_QUESTIONS.md.

        Follows the DeFiPy primitive contract: stateless construction,
        computation at .apply(), structured dataclass return.

        Notes
        -----
        V2 vs V3 coverage. V2 exposes per-swap fee history (fee0_arr,
        fee1_arr), letting us report num_swaps and a rolling-window
        fee accrual rate. V3 accumulates fee growth via
        feeGrowthGlobal0X128 / feeGrowthGlobal1X128 and derives
        collected_fee* at swap time — there's no per-swap history
        array. For V3, num_swaps and fee_accrual_rate_recent are both
        reported as None; total_fee0 / total_fee1 remain available.
        A future V3-specific primitive could derive fee-per-unit-L
        rates from feeGrowthGlobal, but that's a different metric
        and lives outside this primitive's scope.

        Reserve interpretation for V3. reserve0 / reserve1 report the
        pool's raw on-chain reserves (cumulative deposits minus
        withdrawals), not virtual reserves. Virtual-reserve analysis
        belongs in AssessLiquidityDepth. The intent here is "what does
        the pool hold?", not "what's concentrated at the active tick?"

        LP counting. V2 pools burn MINIMUM_LIQUIDITY to address "0" at
        first mint to guard against division-by-dust. This sentinel is
        excluded from num_lps and top_lp_share_pct; otherwise every V2
        pool would report an extra "LP" that isn't a real participant.

        Numeraire convention. tvl_in_token0 uses token0 as the numeraire,
        matching AnalyzePosition / SimulatePriceMove. Callers who want
        USD or another base can divide by their own price source.
    """

    def __init__(self):
        pass

    def apply(self, lp, recent_window = _DEFAULT_RECENT_WINDOW):

        """ apply

            Compute pool health snapshot.

            Parameters
            ----------
            lp : Exchange
                LP exchange at current state. V2 or V3.
            recent_window : int, optional
                Rolling window for fee_accrual_rate_recent, in swap
                counts. Default 20. V2-only; ignored for V3.

            Returns
            -------
            PoolHealth
                Structured snapshot of pool metrics.

            Raises
            ------
            ValueError
                If recent_window <= 0.
        """

        if recent_window <= 0:
            raise ValueError(
                "CheckPoolHealth: recent_window must be > 0; "
                "got {}".format(recent_window)
            )

        tokens = lp.factory.token_from_exchange[lp.name]
        x_tkn = tokens[lp.token0]
        y_tkn = tokens[lp.token1]

        # Spot price of token0 in token1 units.
        spot_price = lp.get_price(x_tkn)

        # Reserves in human units (via lp.get_reserve, which applies
        # precision conversion).
        reserve0 = lp.get_reserve(x_tkn)
        reserve1 = lp.get_reserve(y_tkn)

        # Total liquidity (LP token supply) in human units.
        total_liquidity = lp.get_liquidity()

        # TVL in token0 numeraire. Guard against zero spot_price (can
        # happen on uninitialized pools), in which case fall back to
        # reserve0 alone — token1 value is undefined without a price.
        if spot_price and spot_price > 0:
            tvl_in_token0 = reserve0 + reserve1 / spot_price
        else:
            tvl_in_token0 = reserve0

        # Accumulated fees. V2's collected_fee* is already in human
        # units via convert_to_human at write time; V3 stores in
        # machine units after _update_fees computes them. Normalize
        # both through convert_to_human for consistency.
        total_fee0 = lp.convert_to_human(lp.collected_fee0) \
                     if lp.version == UniswapExchangeData.VERSION_V3 \
                     else lp.collected_fee0
        total_fee1 = lp.convert_to_human(lp.collected_fee1) \
                     if lp.version == UniswapExchangeData.VERSION_V3 \
                     else lp.collected_fee1

        # Swap count and rolling fee accrual — V2 only.
        num_swaps, fee_accrual_rate_recent = self._swap_activity(
            lp, recent_window
        )

        # LP concentration metrics.
        num_lps, top_lp_share_pct = self._lp_concentration(lp)

        has_activity = num_swaps is not None and num_swaps > 0

        return PoolHealth(
            version = lp.version,
            token0_name = lp.token0,
            token1_name = lp.token1,
            spot_price = spot_price if spot_price is not None else 0.0,
            reserve0 = reserve0,
            reserve1 = reserve1,
            total_liquidity = total_liquidity,
            tvl_in_token0 = tvl_in_token0,
            total_fee0 = total_fee0,
            total_fee1 = total_fee1,
            num_swaps = num_swaps,
            fee_accrual_rate_recent = fee_accrual_rate_recent,
            num_lps = num_lps,
            top_lp_share_pct = top_lp_share_pct,
            has_activity = has_activity,
        )

    def _swap_activity(self, lp, recent_window):

        """ _swap_activity

            Extract swap count and rolling fee rate. V2 tracks per-swap
            history in fee0_arr; V3 does not, so both metrics are None.

            Returns
            -------
            (num_swaps, fee_accrual_rate_recent) : (Optional[int], Optional[float])
        """

        if lp.version != UniswapExchangeData.VERSION_V2:
            return None, None

        fee0_arr = getattr(lp, 'fee0_arr', None)
        if fee0_arr is None:
            return None, None

        num_swaps = len(fee0_arr)
        if num_swaps == 0:
            return 0, None

        # Rolling average over the last recent_window swaps (or all, if
        # fewer). fee0_arr stores token0-side fees in machine units
        # (raw integers from _tally_fees); normalize through
        # convert_to_human so the rate is in the same units as total_fee0.
        window = fee0_arr[-recent_window:]
        avg_raw = sum(window) / len(window)
        rate = lp.convert_to_human(avg_raw)

        return num_swaps, rate

    def _lp_concentration(self, lp):

        """ _lp_concentration

            Count distinct LPs and compute the largest LP's share of
            total_supply. Excludes the V2 MINIMUM_LIQUIDITY sentinel
            so metrics reflect real participants.

            Returns
            -------
            (num_lps, top_lp_share_pct) : (int, Optional[float])
        """

        providers = dict(lp.liquidity_providers)
        if lp.version == UniswapExchangeData.VERSION_V2:
            providers.pop(_V2_SENTINEL_ADDRESS, None)

        num_lps = len(providers)

        if num_lps == 0 or lp.total_supply == 0:
            return num_lps, None

        max_share = max(providers.values())
        # total_supply is in the same (machine) units as the dict values,
        # so the ratio is directly interpretable.
        top_share = max_share / lp.total_supply

        return num_lps, top_share
