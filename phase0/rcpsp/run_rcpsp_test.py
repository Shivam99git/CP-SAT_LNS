"""Domain-transfer test: cpsat_cold vs boot_cold on RCPSP streams.

Third data point (after job-shop and knapsack) for the "reuse-floor idea
transfers across domains" claim in BOOT_COLD_PAPER.md. Same experimental
contract: shared budget/seed/worker count, best_known per (name, seed,
instance) = best objective any method found, every solution independently
validated.

Small default instances solve trivially (see BOOT_COLD_PAPER.md's lesson
that job-shop needed --full-shop and knapsack needed large+correlated
instances to be non-trivial) -- use --num-activities 60+ with a tight
--resource-capacity range for a genuinely hard configuration, OR point
--benchmark-dir at real PSPLIB/.rcp instances (see
phase0/rcpsp/benchmark_loaders.py, tests/fixtures/rcpsp_real/).

Usage (synthetic):
    .venv/bin/python -m phase0.rcpsp.run_rcpsp_test --seeds 1 2 \\
        --num-activities 60 --num-resources 3 --resource-capacity 4 6 \\
        --total-budget 10 --stream-length 4

Usage (real benchmark instances as stream bases):
    .venv/bin/python -m phase0.rcpsp.run_rcpsp_test \\
        --benchmark-dir tests/fixtures/rcpsp_real --seeds 1 2 3 \\
        --total-budget 10 --stream-length 4 --parallel 8
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .benchmark_loaders import load_rcp_dir
from .harness import rcpsp_boot_cold_solve, rcpsp_cold_solve
from .instances import RInstance
from .model_builder import RSolution, validate_rcpsp_solution
from .streams import RStreamConfig, generate_rcpsp_stream


def _primal_integral(traj, best_known, budget):
    area, prev_t, prev_gap = 0.0, 0.0, 1.0
    for t, obj in sorted(traj):
        t = min(t, budget)
        area += prev_gap * (t - prev_t)
        prev_t, prev_gap = t, max(0.0, (obj - best_known) / best_known)
    area += prev_gap * (budget - prev_t)
    return area / budget


@dataclass
class _Task:
    name: str                        # "" for synthetic, else benchmark instance name
    seed: int
    total_budget: float
    stream_length: int
    workers: int
    run_seed: int
    num_activities: int
    num_resources: int
    resource_capacity: tuple[int, int]
    base_instance: RInstance | None = None


def _run_one(task: _Task) -> list[dict]:
    """Run cpsat_cold + boot_cold over one stream. Module-level for
    multiprocessing-fork; returns rows without best_known (filled by caller,
    since best_known needs both methods' results for this stream)."""
    if task.base_instance is not None:
        cfg = RStreamConfig(stream_length=task.stream_length, seed=task.seed)
        stream = generate_rcpsp_stream(cfg, base_instance=task.base_instance)
    else:
        cfg = RStreamConfig(
            num_activities=task.num_activities, num_resources=task.num_resources,
            resource_capacity=task.resource_capacity,
            stream_length=task.stream_length, seed=task.seed,
        )
        stream = generate_rcpsp_stream(cfg)

    rows = []
    for method in ("cpsat_cold", "boot_cold"):
        prev: RSolution | None = None
        for inst in stream:
            if method == "cpsat_cold":
                res = rcpsp_cold_solve(inst, task.total_budget, task.workers, task.run_seed)
            else:
                res = rcpsp_boot_cold_solve(inst, task.total_budget, prev,
                                           task.workers, task.run_seed)
            if res.solution is not None:
                assert validate_rcpsp_solution(inst, res.solution) == res.objective
            rows.append({
                "benchmark_name": task.name, "seed": task.seed, "method": method,
                "instance": inst.index, "num_activities": len(inst.activities),
                "delta_kind": inst.delta_kind, "objective": res.objective,
                "initial_objective": res.initial_objective,
                "proven_optimal": res.proven_optimal, "_traj": res.trajectory,
            })
            prev = res.solution if res.solution is not None else prev
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--num-activities", type=int, default=15)
    ap.add_argument("--num-resources", type=int, default=2)
    ap.add_argument("--resource-capacity", type=int, nargs=2, default=[4, 8])
    ap.add_argument("--total-budget", type=float, default=10.0)
    ap.add_argument("--stream-length", type=int, default=4)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--run-seed", type=int, default=0)
    ap.add_argument("--benchmark-dir", default=None,
                    help="directory of .rcp files to use as stream bases "
                         "instead of synthetic generation")
    ap.add_argument("--max-instances", type=int, default=None,
                    help="cap the number of benchmark files loaded from --benchmark-dir")
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tasks: list[_Task] = []
    if args.benchmark_dir:
        loaded = load_rcp_dir(args.benchmark_dir, max_files=args.max_instances)
        print(f"loaded {len(loaded)} real instances from {args.benchmark_dir}: "
              f"{[n for n, _ in loaded]}")
        for name, inst in loaded:
            for seed in args.seeds:
                tasks.append(_Task(
                    name=name, seed=seed, total_budget=args.total_budget,
                    stream_length=args.stream_length, workers=args.workers,
                    run_seed=args.run_seed, num_activities=0, num_resources=0,
                    resource_capacity=(0, 0), base_instance=inst,
                ))
    else:
        for seed in args.seeds:
            tasks.append(_Task(
                name="", seed=seed, total_budget=args.total_budget,
                stream_length=args.stream_length, workers=args.workers,
                run_seed=args.run_seed, num_activities=args.num_activities,
                num_resources=args.num_resources,
                resource_capacity=tuple(args.resource_capacity),
            ))

    print(f"running {len(tasks)} (name,seed) stream configs "
          f"(--parallel {args.parallel})")

    all_rows: list[dict] = []
    t_start = time.monotonic()
    if args.parallel > 1 and len(tasks) > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=min(args.parallel, len(tasks))) as pool:
            for i, rows in enumerate(pool.imap_unordered(_run_one, tasks), 1):
                all_rows.extend(rows)
                print(f"  {i}/{len(tasks)} configs done ({time.monotonic()-t_start:.0f}s elapsed)")
    else:
        for i, task in enumerate(tasks, 1):
            all_rows.extend(_run_one(task))
            print(f"  {i}/{len(tasks)} configs done ({time.monotonic()-t_start:.0f}s elapsed)")

    df = pd.DataFrame(all_rows)
    best = df.groupby(["benchmark_name", "seed", "instance"])["objective"].transform("min")
    df["best_known"] = best
    df["final_gap"] = (df.objective - df.best_known) / df.best_known
    df["primal_integral"] = [
        _primal_integral(t, bk, args.total_budget) for t, bk in zip(df._traj, df.best_known)
    ]
    out_df = df.drop(columns="_traj")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(args.out, index=False)
        print(f"\nwrote {args.out}")

    fmt = lambda x: f"{x:.5f}"
    print("\n=== summary ===")
    print(out_df.groupby("method").agg(
        mean_pi=("primal_integral", "mean"), mean_final_gap=("final_gap", "mean"),
        wins=("final_gap", lambda g: int((g == 0).sum())),
        proven_optimal=("proven_optimal", "sum"),
    ).sort_values("mean_pi").to_string(float_format=fmt))

    cold = out_df[out_df.method == "cpsat_cold"].set_index(["benchmark_name", "seed", "instance"])
    boot = out_df[out_df.method == "boot_cold"].set_index(["benchmark_name", "seed", "instance"])
    n = len(boot)
    ob = int((boot.objective < cold.objective).sum())
    ow = int((boot.objective > cold.objective).sum())
    pb = int((boot.primal_integral < cold.primal_integral).sum())
    print(f"\nboot_cold vs cpsat_cold over {n} instances:")
    print(f"  final objective : better {ob}, worse {ow}, tied {n - ob - ow}")
    print(f"  primal integral : better {pb} / {n}")


if __name__ == "__main__":
    main()
