"""Phase 0 ceiling experiment.

Question: over a stream of related instances, how much headroom is there
between naive CP-SAT / non-adaptive LNS and an oracle that always picks the
best destroy arm in hindsight? If the oracle's advantage is large and its
arm choices are heterogeneous (vary by round/instance/delta kind), a learned
arm-selection policy has something to learn. If not, phase 0 kills the idea
cheaply.

Methods:
  a. cpsat_cold      one full-budget CP-SAT solve per instance, no warm start
  b. cpsat_warm      same, but hinted with the previous instance's solution
  c. lns_uniform     LNS harness, uniform-random arm choice
  d. lns_eps_reset   LNS + epsilon-greedy, stats reset per instance (BALANS-like)
  e. lns_eps_persist LNS + epsilon-greedy, stats carried across the stream
  f. oracle          LNS where every round evaluates ALL arms and keeps the
                     best; only the best arm's time is charged to a virtual
                     clock (best-arm-in-hindsight ceiling, ~12x wall clock)

Usage (from the project root):
    .venv/bin/python -m phase0.run_phase0 --quick
    .venv/bin/python -m phase0.run_phase0 --budget 10 --slice 2 --stream-length 20
"""

from __future__ import annotations

import argparse
import random
import time
from collections import Counter

import pandas as pd

from .harness import (
    ARMS,
    Policy,
    RoundLog,
    SolveResult,
    cpsat_default_solve,
    initial_incumbent,
    lns_solve,
    select_destroy_set,
)
from .metrics import final_gap, primal_integral
from .model_builder import Solution, build_model, solve, validate_solution
from .policies import EpsilonGreedyPolicy, UniformRandomPolicy
from .streams import Instance, StreamConfig, generate_stream


# ---------------------------------------------------------------------------
# Oracle: exhaustive per-round arm evaluation on a virtual clock
# ---------------------------------------------------------------------------

def oracle_solve(
    instance: Instance,
    total_budget: float,
    slice_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    max_rounds: int = 400,
) -> SolveResult:
    """Each round, run every arm from the same incumbent and keep the best
    (highest improvement/sec; among no-improvement arms, the cheapest). Only
    the kept arm's time is charged to the virtual clock, so the result is
    what a perfect arm selector could have achieved within total_budget.

    max_rounds bounds wall-clock blowup: because the virtual clock advances
    by the *chosen* (often fastest) arm's time while wall clock pays all 12,
    millisecond sub-solves would otherwise mean tens of thousands of rounds."""
    t0 = time.monotonic()
    initial_budget = max(0.1, total_budget - slice_budget)
    trajectory: list[tuple[float, int]] = []
    incumbent, objective, optimal = initial_incumbent(
        instance, prev_solution, time_limit=initial_budget, workers=workers,
        seed=seed, recorder=trajectory,
    )
    if incumbent is None:
        incumbent, objective, optimal = initial_incumbent(
            instance, prev_solution, total_budget, workers, seed,
            recorder=trajectory, t_offset=time.monotonic() - t0,
        )
        if incumbent is None:
            return SolveResult("oracle", None, None, [])
    virtual = time.monotonic() - t0  # initial solve is charged for real

    rounds: list[RoundLog] = []
    round_index = 0

    while not optimal and round_index < max_rounds and virtual < total_budget - 0.05:
        slice_now = min(slice_budget, max(0.1, total_budget - virtual))
        best = None  # (reward, -round_time, arm, sub_solution, sub_objective, round_time)
        for ai, arm in enumerate(ARMS):
            rng = random.Random(seed * 100_003 + round_index * 131 + ai)
            destroy = select_destroy_set(arm, instance, incumbent, rng)
            frozen = {
                op.op_id: incumbent[op.op_id]
                for op in instance.all_ops
                if op.op_id not in destroy
            }
            built = build_model(instance, hint=incumbent, frozen=frozen)
            arm_start = time.monotonic()
            sub_solution, sub_objective, _ = solve(
                built, time_limit=slice_now, workers=workers,
                seed=seed + round_index + 1,
            )
            round_time = time.monotonic() - arm_start
            improvement = (
                objective - sub_objective
                if sub_objective is not None and sub_objective < objective
                else 0
            )
            reward = improvement / max(round_time, 1e-6)
            key = (reward, -round_time)
            if best is None or key > best[0]:
                best = (key, arm, sub_solution, sub_objective, round_time, reward)

        _, arm, sub_solution, sub_objective, round_time, reward = best
        obj_before = objective
        if sub_objective is not None and sub_objective < objective:
            incumbent, objective = sub_solution, sub_objective
        virtual += round_time
        rounds.append(
            RoundLog(round_index, arm.name, obj_before, objective,
                     virtual, round_time, reward)
        )
        trajectory.append((virtual, objective))
        round_index += 1

    return SolveResult("oracle", objective, incumbent, trajectory, rounds)


# ---------------------------------------------------------------------------
# Stream runners
# ---------------------------------------------------------------------------

def run_method(
    name: str,
    stream: list[Instance],
    budget: float,
    slice_budget: float,
    seed: int,
    workers: int,
) -> list[SolveResult]:
    """Run one method over the whole stream, carrying its own solution
    forward as the warm start for the next instance."""
    policy: Policy | None = None
    warm = True
    if name == "cpsat_cold":
        warm = False
    elif name == "cpsat_warm":
        pass
    elif name == "lns_uniform":
        policy = UniformRandomPolicy(seed=seed)
    elif name == "lns_eps_reset":
        policy = EpsilonGreedyPolicy(seed=seed, reset_per_instance=True)
    elif name == "lns_eps_persist":
        policy = EpsilonGreedyPolicy(seed=seed, reset_per_instance=False)
    elif name == "oracle":
        pass
    else:
        raise ValueError(name)

    results: list[SolveResult] = []
    prev: Solution | None = None
    for inst in stream:
        if name in ("cpsat_cold", "cpsat_warm"):
            res = cpsat_default_solve(
                inst, budget, prev_solution=prev if warm else None,
                workers=workers, seed=seed, method_name=name,
            )
        elif name == "oracle":
            res = oracle_solve(
                inst, budget, slice_budget, prev_solution=prev,
                workers=workers, seed=seed,
            )
        else:
            policy.reset_instance()
            res = lns_solve(
                inst, policy, budget, slice_budget, prev_solution=prev,
                workers=workers, seed=seed, method_name=name,
            )
        if res.solution is not None:
            assert validate_solution(inst, res.solution) == res.objective
        results.append(res)
        prev = res.solution if res.solution is not None else prev
    return results


METHODS = (
    "cpsat_cold", "cpsat_warm",
    "lns_uniform", "lns_eps_reset", "lns_eps_persist",
    "oracle",
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget", type=float, default=10.0,
                    help="seconds of (virtual) solve budget per instance")
    ap.add_argument("--slice", dest="slice_budget", type=float, default=2.0,
                    help="seconds per LNS repair slice")
    ap.add_argument("--stream-length", type=int, default=20)
    ap.add_argument("--initial-jobs", type=int, default=10)
    ap.add_argument("--machines", type=int, default=5)
    ap.add_argument("--full-shop", action="store_true",
                    help="every job visits every machine (classic hard JSP); "
                         "sets ops_per_job=(machines, machines) and durations 5-50")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--methods", nargs="*", default=list(METHODS))
    ap.add_argument("--quick", action="store_true",
                    help="tiny settings for a smoke run")
    ap.add_argument("--out", default="phase0_results.csv")
    args = ap.parse_args()

    if args.quick:
        args.budget, args.slice_budget = 4.0, 1.0
        args.stream_length, args.initial_jobs = 4, 6

    cfg = StreamConfig(
        num_machines=args.machines,
        initial_jobs=args.initial_jobs,
        stream_length=args.stream_length,
        seed=args.seed,
    )
    if args.full_shop:
        cfg.ops_per_job = (args.machines, args.machines)
        cfg.duration_range = (5, 50)
    stream = generate_stream(cfg)
    print(f"stream: {len(stream)} instances, "
          f"{len(stream[0].all_ops)} ops initially, "
          f"deltas: {Counter(i.delta_kind for i in stream[1:])}")

    all_results: dict[str, list[SolveResult]] = {}
    for name in args.methods:
        t0 = time.monotonic()
        all_results[name] = run_method(
            name, stream, args.budget, args.slice_budget, args.seed, args.workers
        )
        print(f"{name:16s} done in {time.monotonic() - t0:6.1f}s wall")

    # best known per instance = best objective any method found
    best_known = [
        min(r[i].objective for r in all_results.values()
            if r[i].objective is not None)
        for i in range(len(stream))
    ]

    rows = []
    for name, results in all_results.items():
        for i, res in enumerate(results):
            rows.append({
                "method": name,
                "instance": i,
                "delta_kind": stream[i].delta_kind,
                "num_ops": len(stream[i].all_ops),
                "objective": res.objective,
                "best_known": best_known[i],
                "final_gap": final_gap(res, best_known[i]),
                "primal_integral": primal_integral(
                    res.trajectory, best_known[i], args.budget),
                "rounds": len(res.rounds),
            })
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}")

    summary = df.groupby("method").agg(
        mean_primal_integral=("primal_integral", "mean"),
        mean_final_gap=("final_gap", "mean"),
        total_pi=("primal_integral", "sum"),
        wins=("final_gap", lambda g: int((g == 0).sum())),
    ).sort_values("mean_primal_integral")
    print("\n=== summary (lower PI is better; wins = instances at best-known) ===")
    print(summary.to_string(float_format=lambda x: f"{x:.4f}"))

    if "oracle" in all_results:
        picks = Counter()
        improving_picks = Counter()
        for res in all_results["oracle"]:
            for r in res.rounds:
                picks[r.arm] += 1
                if r.objective_after < r.objective_before:
                    improving_picks[r.arm] += 1
        print("\n=== oracle arm choices (all / improving rounds) ===")
        for arm in ARMS:
            print(f"  {arm.name:14s} {picks[arm.name]:4d} / {improving_picks[arm.name]:4d}")
        n_arms_used = sum(1 for a in ARMS if improving_picks[a.name] > 0)
        total_improving = sum(improving_picks.values())
        print(f"\nimproving rounds: {total_improving}, "
              f"distinct improving arms: {n_arms_used}/{len(ARMS)}")
        if total_improving == 0:
            print("no LNS round improved anything — instances too easy or "
                  "budget too generous; increase --initial-jobs/--machines")
        elif n_arms_used >= 3:
            print("heterogeneous improving-arm usage => signal for a learned policy")
        else:
            print("improvements concentrated in few arms => a static arm "
                  "schedule may capture most of the gain")


if __name__ == "__main__":
    main()
