"""Cross-solver validation: does boot_cold's floor/pocket mechanism (a cheap
constructive repair kept as an anytime floor beside an otherwise-unmodified
solver continuation) generalize beyond CP-SAT to Gurobi and IBM CPLEX?

Both Gurobi and CPLEX are used via their free pip-installable tiers, which
are SIZE-LIMITED, not time-limited or feature-limited:
  * gurobipy's bundled "size-limited" license: 2000 variables / 2000 constraints.
  * cplex/docplex's "Community Edition": exactly 1000 variables / 1000
    constraints (verified empirically, see phase0/mip_jssp.py's docstring).
This is a hard licensing ceiling that forces much smaller instances than the
paper's main CP-SAT experiments (15x15 full-shop / real Taillard instances).
It is disclosed prominently everywhere these results are reported.

Job-shop uses the disjunctive big-M MIP formulation (phase0/mip_jssp.py),
which -- unlike knapsack -- has a famously weak LP relaxation and stays
genuinely hard for a generic MIP solver even at these small, license-capped
sizes (empirically verified: Gurobi ~3-10s, CPLEX >10s-not-proven, on an
instance CP-SAT itself proves in ~30ms -- see the module docstring and
session notes; this speed gap is itself a reported finding, not an artifact).

Knapsack (phase0/mip_knapsack.py) is included for completeness/mechanism
validation, but is reported honestly as a near-null domain for this
particular comparison: 0-1 knapsack has extremely strong cover-cut theory in
commercial MIP solvers, so even adversarial (subset-sum-style) instances up
to the license cap solve in <50ms for both Gurobi and CPLEX -- there is no
meaningful anytime curve for a floor to improve on.

Usage:
    .venv/bin/python -m phase0.run_multisolver_test --domain jssp \\
        --seeds 1 2 3 4 5 6 --budget 8 --out results/multisolver/jssp.csv
    .venv/bin/python -m phase0.run_multisolver_test --domain knapsack \\
        --seeds 1 2 3 --budget 5 --out results/multisolver/knapsack.csv
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from .harness import cpsat_default_solve, warm_bootstrap_solve
from .metrics import primal_integral as jssp_primal_integral
from .model_builder import validate_solution
from .mip_jssp import (
    cplex_boot_cold_solve, cplex_cold_solve, gurobi_boot_cold_solve,
    gurobi_cold_solve, jssp_mip_size,
)
from .mip_knapsack import (
    cplex_boot_cold as k_cplex_boot_cold, cplex_cold as k_cplex_cold,
    gurobi_boot_cold as k_gurobi_boot_cold, gurobi_cold as k_gurobi_cold,
    knapsack_mip_size,
)
from .run_knapsack_test import (
    KConfig, generate_kstream, k_primal_integral, kboot_cold, kcold,
    validate_kselection,
)
from .streams import StreamConfig, generate_stream

CPLEX_VAR_CAP = 1000
CPLEX_CONS_CAP = 1000


def run_jssp(seeds: list[int], budget: float, stream_length: int,
            num_machines: int, initial_jobs: int) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        cfg = StreamConfig(
            num_machines=num_machines, initial_jobs=initial_jobs,
            ops_per_job=(4, 6), stream_length=stream_length, seed=seed,
            p_arrival=0.4, p_cancellation=0.2, p_duration_jitter=0.25, p_outage=0.15,
        )
        stream = generate_stream(cfg)
        for inst in stream:
            v, c = jssp_mip_size(inst)
            if v > CPLEX_VAR_CAP or c > CPLEX_CONS_CAP:
                raise RuntimeError(
                    f"seed={seed} step={inst.index}: MIP size {v}v/{c}c exceeds "
                    f"the CPLEX Community Edition cap ({CPLEX_VAR_CAP}v/{CPLEX_CONS_CAP}c) "
                    f"-- pick a smaller base/stream_length."
                )
        print(f"seed {seed}: {len(stream)} instances, "
              f"deltas={[i.delta_kind for i in stream[1:]]}, "
              f"max mip size={max(jssp_mip_size(i) for i in stream)}")

        prev_by_method: dict[str, dict | None] = {
            m: None for m in ("cpsat_cold", "boot_cold", "gurobi_cold",
                             "gurobi_boot_cold", "cplex_cold", "cplex_boot_cold")
        }
        for inst in stream:
            t0 = time.monotonic()
            results = {
                "cpsat_cold": cpsat_default_solve(inst, budget, method_name="cpsat_cold"),
                "boot_cold": warm_bootstrap_solve(
                    inst, budget, prev_by_method["boot_cold"], use_hint=False,
                    method_name="boot_cold"),
                "gurobi_cold": gurobi_cold_solve(inst, budget),
                "gurobi_boot_cold": gurobi_boot_cold_solve(
                    inst, budget, prev_by_method["gurobi_boot_cold"]),
                "cplex_cold": cplex_cold_solve(inst, budget),
                "cplex_boot_cold": cplex_boot_cold_solve(
                    inst, budget, prev_by_method["cplex_boot_cold"]),
            }
            wall = time.monotonic() - t0
            print(f"  seed={seed} step={inst.index} delta={inst.delta_kind} "
                  f"({wall:.1f}s for 6 methods)")
            for name, res in results.items():
                if res.solution is not None:
                    check = validate_solution(inst, res.solution)
                    assert check == res.objective, (
                        f"{name} seed={seed} step={inst.index}: reported "
                        f"objective {res.objective} != validated {check}"
                    )
                rows.append({
                    "seed": seed, "instance": inst.index, "delta_kind": inst.delta_kind,
                    "method": name, "objective": res.objective,
                    "initial_objective": res.initial_objective,
                    "proven_optimal": res.proven_optimal,
                    "_traj": res.trajectory,
                })
                if res.solution is not None:
                    prev_by_method[name] = res.solution

    df = pd.DataFrame(rows)
    df["best_known"] = df.groupby(["seed", "instance"])["objective"].transform("min")
    df["final_gap"] = (df.objective - df.best_known) / df.best_known
    df["primal_integral"] = [
        jssp_primal_integral(t, bk, budget) for t, bk in zip(df._traj, df.best_known)
    ]
    return df.drop(columns="_traj")


def run_knapsack(seeds: list[int], budget: float, stream_length: int,
                 n_items: int, weight_max: int) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        cfg = KConfig(n_items=n_items, correlated=True,
                     weight_range=(1, weight_max), corr_k=weight_max // 2,
                     stream_length=stream_length, seed=seed)
        stream = generate_kstream(cfg)
        for inst in stream:
            v, c = knapsack_mip_size(inst)
            if v > CPLEX_VAR_CAP or c > CPLEX_CONS_CAP:
                raise RuntimeError(
                    f"seed={seed} step={inst.index}: MIP size {v}v/{c}c exceeds "
                    f"the CPLEX Community Edition cap -- reduce n_items."
                )
        print(f"seed {seed}: {len(stream)} instances, "
              f"deltas={[i.delta_kind for i in stream[1:]]}")

        prev_by_method: dict[str, set | None] = {
            m: None for m in ("cpsat_cold", "boot_cold", "gurobi_cold",
                             "gurobi_boot_cold", "cplex_cold", "cplex_boot_cold")
        }
        for inst in stream:
            t0 = time.monotonic()
            results = {
                "cpsat_cold": kcold(inst, budget, 0),
                "boot_cold": kboot_cold(inst, budget, 0, prev_by_method["boot_cold"]),
                "gurobi_cold": k_gurobi_cold(inst, budget, 0),
                "gurobi_boot_cold": k_gurobi_boot_cold(
                    inst, budget, 0, prev_by_method["gurobi_boot_cold"]),
                "cplex_cold": k_cplex_cold(inst, budget, 0),
                "cplex_boot_cold": k_cplex_boot_cold(
                    inst, budget, 0, prev_by_method["cplex_boot_cold"]),
            }
            wall = time.monotonic() - t0
            print(f"  seed={seed} step={inst.index} delta={inst.delta_kind} "
                  f"({wall:.1f}s for 6 methods)")
            for name, res in results.items():
                if res.chosen is not None:
                    check = validate_kselection(inst, res.chosen)
                    assert check == res.value, (
                        f"{name} seed={seed} step={inst.index}: reported "
                        f"value {res.value} != validated {check}"
                    )
                rows.append({
                    "seed": seed, "instance": inst.index, "delta_kind": inst.delta_kind,
                    "method": name, "value": res.value,
                    "initial_value": res.initial_value,
                    "proven_optimal": res.proven_optimal,
                    "_traj": res.trajectory,
                })
                if res.chosen is not None:
                    prev_by_method[name] = res.chosen

    df = pd.DataFrame(rows)
    df["best_known"] = df.groupby(["seed", "instance"])["value"].transform("max")
    df["final_gap"] = (df.best_known - df.value) / df.best_known
    df["primal_integral"] = [
        k_primal_integral(t, bk, budget) for t, bk in zip(df._traj, df.best_known)
    ]
    return df.drop(columns="_traj")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--domain", choices=["jssp", "knapsack"], required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    ap.add_argument("--budget", type=float, default=8.0)
    ap.add_argument("--stream-length", type=int, default=4)
    # jssp-specific
    ap.add_argument("--num-machines", type=int, default=6)
    ap.add_argument("--initial-jobs", type=int, default=10)
    # knapsack-specific
    ap.add_argument("--items", type=int, default=700)
    ap.add_argument("--weight-max", type=int, default=1_000_000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.monotonic()
    if args.domain == "jssp":
        df = run_jssp(args.seeds, args.budget, args.stream_length,
                      args.num_machines, args.initial_jobs)
    else:
        df = run_knapsack(args.seeds, args.budget, args.stream_length,
                          args.items, args.weight_max)
    print(f"\ntotal wall time: {time.monotonic() - t0:.1f}s")

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"wrote {args.out} ({len(df)} rows)")

    fmt = lambda x: f"{x:.5f}"
    print("\n=== summary ===")
    print(df.groupby("method").agg(
        mean_pi=("primal_integral", "mean"),
        mean_final_gap=("final_gap", "mean"),
        proven_optimal_rate=("proven_optimal", "mean"),
        n=("primal_integral", "size"),
    ).sort_values("mean_pi").to_string(float_format=fmt))


if __name__ == "__main__":
    main()
