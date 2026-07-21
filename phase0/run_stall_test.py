"""Head-to-head: stall-triggered interleaved LNS vs cpsat_cold / cpsat_warm.

Every method gets the same total wall-clock budget per instance. lns_stall
runs one continuous CP-SAT solve until it stalls (no improving solution for
stall_window seconds), then spends the stalled time on LNS repair rounds
rotating through the strongest arms, reheating globally when repair stops
paying. best_known per (seed, instance) is the best objective ANY method
found, so all methods are scored against one target.

Usage:
    .venv/bin/python -m phase0.run_stall_test --seeds 1 2 --total-budget 6 \\
        --machines 15 --initial-jobs 15 --stream-length 3 --full-shop
"""

from __future__ import annotations

import argparse
import time
from collections import Counter

import pandas as pd

from .harness import (
    SolveResult,
    cpsat_default_solve,
    stall_interleaved_solve,
    warm_bootstrap_solve,
)
from .metrics import final_gap, primal_integral
from .model_builder import Solution, validate_solution
from .streams import Instance, StreamConfig, generate_stream


def _build_stream(seed: int, args: argparse.Namespace) -> list[Instance]:
    cfg = StreamConfig(
        num_machines=args.machines,
        initial_jobs=args.initial_jobs,
        stream_length=args.stream_length,
        seed=seed,
    )
    if args.full_shop:
        cfg.ops_per_job = (args.machines, args.machines)
        cfg.duration_range = (5, 50)
    return generate_stream(cfg)


def _run_stream(method: str, stream: list[Instance], args) -> list[SolveResult]:
    out: list[SolveResult] = []
    prev: Solution | None = None
    for inst in stream:
        if method == "cpsat_cold":
            res = cpsat_default_solve(inst, args.total_budget, prev_solution=None,
                                      workers=args.workers, seed=args.run_seed,
                                      method_name=method)
        elif method == "cpsat_warm":
            res = cpsat_default_solve(inst, args.total_budget, prev_solution=prev,
                                      workers=args.workers, seed=args.run_seed,
                                      method_name=method)
        elif method == "lns_stall":
            res = stall_interleaved_solve(
                inst, args.total_budget, prev_solution=prev,
                workers=args.workers, seed=args.run_seed,
                stall_window=args.stall_window,
                round_slice_budget=args.round_slice,
                global_frac=args.global_frac,
            )
        elif method == "boot_warm":
            res = warm_bootstrap_solve(
                inst, args.total_budget, prev_solution=prev,
                workers=args.workers, seed=args.run_seed,
            )
        elif method == "boot_cold":
            res = warm_bootstrap_solve(
                inst, args.total_budget, prev_solution=prev,
                workers=args.workers, seed=args.run_seed,
                use_hint=False, method_name="boot_cold",
            )
        else:
            raise ValueError(method)
        if res.solution is not None:
            assert validate_solution(inst, res.solution) == res.objective
        out.append(res)
        prev = res.solution if res.solution is not None else prev
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--total-budget", type=float, default=6.0)
    ap.add_argument("--stall-window", type=float, default=None,
                    help="seconds without improvement before switching to LNS "
                         "(default: max(1.5, 0.25*total))")
    ap.add_argument("--round-slice", type=float, default=1.0)
    ap.add_argument("--global-frac", type=float, default=0.6,
                    help="hard cap on the global stint as a fraction of total")
    ap.add_argument("--machines", type=int, default=15)
    ap.add_argument("--initial-jobs", type=int, default=15)
    ap.add_argument("--stream-length", type=int, default=3)
    ap.add_argument("--full-shop", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--run-seed", type=int, default=0,
                    help="CP-SAT random seed (same for all methods)")
    ap.add_argument("--methods", nargs="+",
                    default=["cpsat_cold", "cpsat_warm", "lns_stall"])
    ap.add_argument("--out", default=None, help="optional CSV path")
    args = ap.parse_args()

    raw: list[dict] = []
    for seed in args.seeds:
        stream = _build_stream(seed, args)
        print(f"seed {seed}: {len(stream)} instances, "
              f"{len(stream[0].all_ops)} ops, "
              f"deltas={Counter(i.delta_kind for i in stream[1:])}")
        for method in args.methods:
            t0 = time.monotonic()
            results = _run_stream(method, stream, args)
            print(f"  {method:12s} {time.monotonic() - t0:6.1f}s wall")
            for idx, res in enumerate(results):
                raw.append({"seed": seed, "method": method, "instance": idx,
                            "delta_kind": stream[idx].delta_kind,
                            "result": res})

    # best_known per (seed, instance) across all methods
    best: dict[tuple[int, int], int] = {}
    for item in raw:
        res = item["result"]
        if res.objective is None:
            continue
        key = (item["seed"], item["instance"])
        if key not in best or res.objective < best[key]:
            best[key] = res.objective

    rows = []
    for item in raw:
        res = item["result"]
        bk = best[(item["seed"], item["instance"])]
        rows.append({
            "seed": item["seed"], "method": item["method"],
            "instance": item["instance"], "delta_kind": item["delta_kind"],
            "objective": res.objective, "best_known": bk,
            "final_gap": final_gap(res, bk),
            "primal_integral": primal_integral(res.trajectory, bk,
                                               args.total_budget),
            "rounds": len(res.rounds),
            "improving_rounds": res.improving_rounds,
            "initial_objective": res.initial_objective,
        })
    df = pd.DataFrame(rows)
    if args.out:
        df.to_csv(args.out, index=False)
        print(f"\nwrote {args.out}")

    fmt = lambda x: f"{x:.4f}"
    print("\n=== per-instance objectives ===")
    piv = df.pivot_table(index=["seed", "instance", "delta_kind"],
                         columns="method", values="objective")
    print(piv.to_string())

    print("\n=== summary ===")
    summary = df.groupby("method").agg(
        mean_pi=("primal_integral", "mean"),
        mean_final_gap=("final_gap", "mean"),
        wins=("final_gap", lambda g: int((g == 0).sum())),
        mean_improving_rounds=("improving_rounds", "mean"),
    ).sort_values("mean_pi")
    print(summary.to_string(float_format=fmt))

    if "cpsat_cold" in set(df.method.unique()):
        cold = df[df.method == "cpsat_cold"].set_index(["seed", "instance"])
        for m in df.method.unique():
            if m in ("cpsat_cold", "cpsat_warm"):
                continue
            ours = df[df.method == m].set_index(["seed", "instance"])
            obj_better = int((ours.objective < cold.objective).sum())
            obj_worse = int((ours.objective > cold.objective).sum())
            pi_better = int((ours.primal_integral < cold.primal_integral).sum())
            n = len(ours)
            print(f"\n{m} vs cpsat_cold head-to-head over {n} instances:")
            print(f"  final objective : better {obj_better}, worse {obj_worse}, "
                  f"tied {n - obj_better - obj_worse}")
            print(f"  primal integral : better {pi_better} / {n}")


if __name__ == "__main__":
    main()
