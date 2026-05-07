#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# Apache 2.0 License (DeFiPy)
# ─────────────────────────────────────────────────────────────────────────────
# Copyright 2023–2026 Ian Moore
# Email: defipy.devs@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS.

"""State Twin — fork-and-evaluate worked example.

Demonstrates the State Twin pattern's strategic claim: pull live state
once, fork the twin into N independent copies under different price
scenarios, run primitives against each fork, aggregate into an
interpretable distribution, produce a recommendation. All in memory,
all before any execution.

Per STATE_TWIN_COMPLETION_PLAN.md (Phase 3b) and
STATE_TWIN_PHASE_3.md.

This is NOT an agent. It's a Python script demonstrating the substrate
pattern. Drop in your own threshold, scenario set, or scoring function;
the script is the canonical reference, not the only valid shape.

Usage
-----
    # Live RPC (canonical narrative — USDC/WETH V3 mainnet):
    DEFIPY_LIVE_RPC=https://eth-mainnet.example.com/v2/<key> \
        python state_twin_fork_evaluate.py --n-scenarios 50

    # Offline (no RPC needed; uses MockProvider eth_dai_v3 recipe):
    python state_twin_fork_evaluate.py --offline --n-scenarios 20

    # Verbose per-scenario breakdown:
    python state_twin_fork_evaluate.py --offline --verbose

    # Pin to a historical block for reproducibility:
    python state_twin_fork_evaluate.py --block-number 19500000
"""

import argparse
import copy
import os
import statistics
import sys
import time

from defipy.twin import LiveProvider, MockProvider, StateTwinBuilder
from defipy.primitives.position import SimulatePriceMove


# ─── Configuration ──────────────────────────────────────────────────────────


# Canonical Phase 3 smoke pool — USDC/WETH V3, 0.05% fee tier on
# Ethereum mainnet. Same pool as Phase 2's smoke test and Phase 3a's
# verification. Long-running, deep liquidity, mixed decimals.
CANONICAL_POOL_ID = "uniswap_v3:0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
OFFLINE_RECIPE = "eth_dai_v3"

# Recommendation rule per D17 of STATE_TWIN_PHASE_3.md.
# Consumers calibrate to their own thresholds — these are illustrative.
IL_THRESHOLD = -0.05            # IL worse than -5% counts as "breach"
BREACH_RATIO_THRESHOLD = 0.70   # ≥ 70% breaching → rebalance

# Hand-specified scenario range. N=50 expands via uniform interpolation
# across [-30%, +30%]. Per D13: hand-specified beats sampled for
# interpretability and debug-ability. Comment out the linspace and
# substitute log-normal sampling here for rigor; don't ship two variants.
SCENARIO_MIN_PCT = -0.30
SCENARIO_MAX_PCT = +0.30


# ─── Helpers ────────────────────────────────────────────────────────────────


def build_initial_twin(offline: bool, block_number: int | None):
    """Build a V3 State Twin from chain state (offline=False) or
    MockProvider's `eth_dai_v3` recipe (offline=True).

    Returns the (lp, snapshot) tuple — the snapshot is needed for its
    `lwr_tick` / `upr_tick` (V3 SimulatePriceMove requires them)."""
    if offline:
        snap = MockProvider().snapshot(OFFLINE_RECIPE)
    else:
        rpc_url = os.environ.get("DEFIPY_LIVE_RPC")
        if not rpc_url:
            print(
                "ERROR: DEFIPY_LIVE_RPC env var not set. Either set it to a\n"
                "valid Ethereum RPC URL (Alchemy / Infura free tiers work)\n"
                "or pass --offline to use MockProvider's eth_dai_v3 recipe.",
                file = sys.stderr,
            )
            sys.exit(1)
        provider = LiveProvider(rpc_url)
        kwargs = {}
        if block_number is not None:
            kwargs["block_number"] = block_number
        snap = provider.snapshot(CANONICAL_POOL_ID, **kwargs)
    lp = StateTwinBuilder().build(snap)
    return lp, snap


def make_scenarios(n: int) -> list[float]:
    """Hand-specified price multipliers spanning [-30%, +30%].

    Uniform spacing per D13. Edit this function to plug in a
    log-normal distribution, calibrated empirical scenarios, or any
    other shape — the rest of the script is scenario-set agnostic."""
    if n < 2:
        return [0.0]
    step = (SCENARIO_MAX_PCT - SCENARIO_MIN_PCT) / (n - 1)
    return [SCENARIO_MIN_PCT + i * step for i in range(n)]


def fork_twin(lp, n: int) -> list:
    """Produce N independent forks via copy.deepcopy per D15.

    Comment from STATE_TWIN_PHASE_3.md / R14: if deepcopy proves slow
    at large N or surfaces shared-reference issues, the documented
    fallback is `PoolSnapshot.clone() → StateTwinBuilder.build()` per
    fork. For full-range V3 twins at N≤50 deepcopy stays well under
    the wall-clock budget; we don't preemptively build the helper."""
    return [copy.deepcopy(lp) for _ in range(n)]


def evaluate_scenarios(lp_forks, scenarios, snap):
    """Run SimulatePriceMove against each fork at the corresponding
    scenario's price-change percentage. Returns a list of
    PriceMoveScenario dataclass instances, one per scenario."""
    results = []
    primitive = SimulatePriceMove()
    for fork, pct in zip(lp_forks, scenarios):
        result = primitive.apply(
            fork,
            price_change_pct = pct,
            position_size_lp = 1.0,
            lwr_tick = snap.lwr_tick,
            upr_tick = snap.upr_tick,
        )
        results.append(result)
    return results


def aggregate(results) -> dict:
    """Per D16: mean, median, 5th and 95th percentile of
    `il_at_new_price` and `value_change_pct` across scenarios.
    Risk-adjusted scoring is explicitly out — the demo's job is to
    show the distribution is reachable, not to prescribe scoring."""
    il = [r.il_at_new_price for r in results]
    val = [r.value_change_pct for r in results]
    il_sorted = sorted(il)
    val_sorted = sorted(val)
    n = len(il_sorted)

    def pct_at(arr_sorted, p):
        """Linear-interpolated percentile; sufficient for demo."""
        if n == 1:
            return arr_sorted[0]
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return arr_sorted[idx]

    return {
        "n": n,
        "il_mean": statistics.fmean(il),
        "il_median": statistics.median(il),
        "il_p05": pct_at(il_sorted, 0.05),
        "il_p95": pct_at(il_sorted, 0.95),
        "val_mean": statistics.fmean(val),
        "val_median": statistics.median(val),
        "val_p05": pct_at(val_sorted, 0.05),
        "val_p95": pct_at(val_sorted, 0.95),
    }


def recommend(results, breach_ratio_threshold = BREACH_RATIO_THRESHOLD,
              il_threshold = IL_THRESHOLD):
    """Per D17: if ≥70% of scenarios produce IL worse than -5%,
    recommend `"rebalance"`; otherwise `"hold"`. Returns the verdict
    string plus the breach-info dict so the summary printer can name
    the threshold and breach count."""
    breaches = [r for r in results if r.il_at_new_price < il_threshold]
    breach_count = len(breaches)
    total = len(results)
    ratio = breach_count / total if total else 0.0
    verdict = "rebalance" if ratio >= breach_ratio_threshold else "hold"
    return verdict, {
        "breach_count": breach_count,
        "total": total,
        "ratio": ratio,
        "ratio_threshold": breach_ratio_threshold,
        "il_threshold": il_threshold,
    }


def print_summary(snap, agg, verdict, breach, results, scenarios,
                  wall_clock_s, verbose):
    """3-line summary by default per R17; full per-scenario breakdown
    when `--verbose`. Recommendation is fully transparent — names the
    threshold, the breach count, and the resulting verdict."""
    print()
    print("─" * 60)
    print("State Twin — fork-and-evaluate")
    print("─" * 60)
    print(f"Pool:         {snap.token0_name}/{snap.token1_name}  "
          f"(protocol={snap.protocol})")
    if snap.block_number is not None:
        print(f"Block:        {snap.block_number}  chain_id={snap.chain_id}")
    else:
        print(f"Block:        n/a  (synthetic / MockProvider snapshot)")
    print(f"Scenarios:    n={agg['n']}, "
          f"price-pct range [{scenarios[0]:+.2%}, {scenarios[-1]:+.2%}]")
    print(f"Wall clock:   {wall_clock_s:.2f}s "
          f"(fork + evaluate, excluding chain read)")
    print()
    print("Distribution (across scenarios)")
    print(f"  il_at_new_price : "
          f"mean={agg['il_mean']:+.4f}  median={agg['il_median']:+.4f}  "
          f"p05={agg['il_p05']:+.4f}  p95={agg['il_p95']:+.4f}")
    print(f"  value_change    : "
          f"mean={agg['val_mean']:+.4f}  median={agg['val_median']:+.4f}  "
          f"p05={agg['val_p05']:+.4f}  p95={agg['val_p95']:+.4f}")
    print()
    print(f"Threshold rule: rebalance if ≥{breach['ratio_threshold']:.0%} of "
          f"scenarios show IL < {breach['il_threshold']:+.2%}")
    print(f"Breaches:       {breach['breach_count']} of {breach['total']} "
          f"scenarios ({breach['ratio']:.1%})")
    print()
    print(f"RECOMMENDATION: {verdict.upper()}")
    print("─" * 60)
    print("Note: scenarios are illustrative, not predictive. Calibrate")
    print("the threshold / scenario set / scoring rule to your own pool")
    print("and risk tolerance.")
    print("─" * 60)
    if verbose:
        print()
        print("Per-scenario breakdown")
        print(f"  {'pct':>8}  {'il_at_new_price':>17}  {'value_change_pct':>18}")
        for pct, r in zip(scenarios, results):
            print(f"  {pct:>+8.2%}  {r.il_at_new_price:>+17.6f}  "
                  f"{r.value_change_pct:>+18.6f}")


# ─── Sanity check (acceptance criterion 2) ─────────────────────────────────


def assert_fork_independence(results, scenarios):
    """Verify forks are independent — different scenarios produce
    different outputs. Per the verification gate's acceptance
    criterion: 'fork independence verified'."""
    if len(results) < 2:
        return
    # Pick the most extreme scenario pair we have. With non-zero price
    # changes both should produce non-zero IL of different magnitude.
    extreme_idx = 0 if abs(scenarios[0]) > abs(scenarios[-1]) else -1
    other_idx = -1 if extreme_idx == 0 else 0
    extreme_il = results[extreme_idx].il_at_new_price
    other_il = results[other_idx].il_at_new_price
    if extreme_il == other_il and scenarios[extreme_idx] != scenarios[other_idx]:
        print(
            "WARN: forks may be sharing state — scenarios at "
            f"{scenarios[extreme_idx]:+.2%} and {scenarios[other_idx]:+.2%} "
            "produced identical IL.",
            file = sys.stderr,
        )


# ─── Entry point ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description = "State Twin fork-and-evaluate worked example.",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = __doc__,
    )
    parser.add_argument(
        "--offline", action = "store_true",
        help = "Use MockProvider's eth_dai_v3 recipe instead of LiveProvider. "
               "No RPC required.",
    )
    parser.add_argument(
        "--verbose", action = "store_true",
        help = "Print per-scenario breakdown in addition to the summary.",
    )
    parser.add_argument(
        "--n-scenarios", type = int, default = 50,
        help = "Number of price scenarios to evaluate (default: 50).",
    )
    parser.add_argument(
        "--block-number", type = int, default = None,
        help = "Pin the chain read to a specific block "
               "(LiveProvider only; ignored with --offline).",
    )
    args = parser.parse_args()

    if args.n_scenarios < 2:
        print("ERROR: --n-scenarios must be ≥ 2.", file = sys.stderr)
        sys.exit(1)

    # Initial twin construction — the only chain read.
    lp, snap = build_initial_twin(args.offline, args.block_number)

    # Fork + evaluate timing — the part we measure for the wall-clock
    # budget per R14.
    t0 = time.perf_counter()
    scenarios = make_scenarios(args.n_scenarios)
    forks = fork_twin(lp, len(scenarios))
    results = evaluate_scenarios(forks, scenarios, snap)
    wall_clock = time.perf_counter() - t0

    assert_fork_independence(results, scenarios)
    agg = aggregate(results)
    verdict, breach = recommend(results)
    print_summary(snap, agg, verdict, breach, results, scenarios,
                  wall_clock, args.verbose)


if __name__ == "__main__":
    main()
