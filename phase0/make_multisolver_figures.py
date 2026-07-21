"""Figures for the cross-solver validation (CP-SAT vs Gurobi vs CPLEX).

Two figure types:
  1. Anytime curves: capture full trajectories on held-out seeds (not used in
     the main results/multisolver/*.csv campaign) for all 6 methods, per
     domain, and plot median gap-vs-time with an IQR band.
  2. PI bar chart: aggregate mean primal integral per method per domain,
     read directly from the already-run campaign CSVs (no recompute).

Usage:
    .venv/bin/python -m phase0.make_multisolver_figures \\
        --out-dir results/multisolver/analysis/figures
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .harness import cpsat_default_solve, warm_bootstrap_solve
from .mip_jssp import (
    cplex_boot_cold_solve, cplex_cold_solve, gurobi_boot_cold_solve, gurobi_cold_solve,
)
from .mip_knapsack import (
    cplex_boot_cold as k_cplex_boot_cold, cplex_cold as k_cplex_cold,
    gurobi_boot_cold as k_gurobi_boot_cold, gurobi_cold as k_gurobi_cold,
)
from .run_knapsack_test import KConfig, generate_kstream, kboot_cold, kcold
from .streams import StreamConfig, generate_stream

_METHOD_STYLE = {
    "cpsat_cold":       ("#9aa0a6", "cpsat_cold"),
    "boot_cold":        ("#1a73e8", "boot_cold (CP-SAT)"),
    "gurobi_cold":      ("#f9ab00", "gurobi_cold"),
    "gurobi_boot_cold": ("#d93025", "gurobi_boot_cold"),
    "cplex_cold":       ("#a142f4", "cplex_cold"),
    "cplex_boot_cold":  ("#188038", "cplex_boot_cold"),
}


def _capture_jssp(seeds: list[int], budget: float) -> list[dict]:
    rows = []
    for seed in seeds:
        cfg = StreamConfig(num_machines=6, initial_jobs=10, ops_per_job=(4, 6),
                           stream_length=4, seed=seed,
                           p_arrival=0.4, p_cancellation=0.2,
                           p_duration_jitter=0.25, p_outage=0.15)
        stream = generate_stream(cfg)
        prev = {m: None for m in _METHOD_STYLE}
        for inst in stream:
            results = {
                "cpsat_cold": cpsat_default_solve(inst, budget, method_name="cpsat_cold"),
                "boot_cold": warm_bootstrap_solve(
                    inst, budget, prev["boot_cold"], use_hint=False, method_name="boot_cold"),
                "gurobi_cold": gurobi_cold_solve(inst, budget),
                "gurobi_boot_cold": gurobi_boot_cold_solve(inst, budget, prev["gurobi_boot_cold"]),
                "cplex_cold": cplex_cold_solve(inst, budget),
                "cplex_boot_cold": cplex_boot_cold_solve(inst, budget, prev["cplex_boot_cold"]),
            }
            for name, res in results.items():
                rows.append({"seed": seed, "step": inst.index, "method": name,
                            "objective": res.objective, "trajectory": res.trajectory})
                if res.solution is not None:
                    prev[name] = res.solution
    return rows


def _capture_knapsack(seeds: list[int], budget: float, n_items: int, weight_max: int) -> list[dict]:
    rows = []
    for seed in seeds:
        cfg = KConfig(n_items=n_items, correlated=True, weight_range=(1, weight_max),
                     corr_k=weight_max // 2, stream_length=4, seed=seed)
        stream = generate_kstream(cfg)
        prev = {m: None for m in _METHOD_STYLE}
        for inst in stream:
            results = {
                "cpsat_cold": kcold(inst, budget, 0),
                "boot_cold": kboot_cold(inst, budget, 0, prev["boot_cold"]),
                "gurobi_cold": k_gurobi_cold(inst, budget, 0),
                "gurobi_boot_cold": k_gurobi_boot_cold(inst, budget, 0, prev["gurobi_boot_cold"]),
                "cplex_cold": k_cplex_cold(inst, budget, 0),
                "cplex_boot_cold": k_cplex_boot_cold(inst, budget, 0, prev["cplex_boot_cold"]),
            }
            for name, res in results.items():
                rows.append({"seed": seed, "step": inst.index, "method": name,
                            "value": res.value, "trajectory": res.trajectory})
                if res.chosen is not None:
                    prev[name] = res.chosen
    return rows


def _gap_on_grid(trajectory, best_known, grid, maximize=False):
    traj = sorted(trajectory)
    gaps = np.ones(len(grid))
    if not traj or best_known <= 0:
        return gaps
    ti = 0
    cur_gap = 1.0
    for gi, t in enumerate(grid):
        while ti < len(traj) and traj[ti][0] <= t:
            v = traj[ti][1]
            cur_gap = max(0.0, (best_known - v) / best_known if maximize
                         else (v - best_known) / best_known)
            ti += 1
        gaps[gi] = cur_gap
    return gaps


def _anytime_figure(rows: list[dict], value_col: str, budget: float, maximize: bool,
                    title: str, out_path: Path):
    df = pd.DataFrame(rows)
    bk = (df.groupby(["seed", "step"])[value_col]
         .agg("max" if maximize else "min"))
    sub = df[df.step >= 1]  # stream instances only (have a floor to use)
    grid = np.linspace(0, budget, 240)

    fig, ax = plt.subplots(figsize=(5.5, 4))
    medians = {}
    for method, (color, label) in _METHOD_STYLE.items():
        msub = sub[sub.method == method]
        curves = []
        for _, r in msub.iterrows():
            key = (r.seed, r.step)
            if key not in bk.index or pd.isna(bk.loc[key]):
                continue
            curves.append(_gap_on_grid(r.trajectory, bk.loc[key], grid, maximize))
        if not curves:
            continue
        arr = np.vstack(curves)
        med = np.median(arr, axis=0)
        q25 = np.percentile(arr, 25, axis=0)
        q75 = np.percentile(arr, 75, axis=0)
        medians[method] = med
        ax.plot(grid, med, color=color, label=label, linewidth=1.6)
        ax.fill_between(grid, q25, q75, color=color, alpha=0.08)

    if medians:
        after_spike = max(m[min(3, len(m) - 1)] for m in medians.values())
        ax.set_ylim(0, max(0.02, after_spike * 1.3))
        # zoom the x-axis to where methods are still separating: find the
        # last grid point at which any method's median gap is still above 1%
        # of the y-limit, plus a small margin, instead of showing the long
        # flat tail where every method has already converged to ~0.
        ylim = ax.get_ylim()[1]
        active_idx = [i for i, g in enumerate(grid)
                     if any(m[i] > 0.02 * ylim for m in medians.values())]
        x_end = grid[min(active_idx[-1] + 15, len(grid) - 1)] if active_idx else budget
        ax.set_xlim(0, max(x_end, budget * 0.05))
    ax.set_xlabel("wall-clock time (s)")
    ax.set_ylabel("relative gap to best found (any method)")
    ax.set_title(title)
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _pi_bar_chart(jssp_csv: str, knap_csv: str, out_path: Path):
    jdf = pd.read_csv(jssp_csv)
    kdf = pd.read_csv(knap_csv)
    j_agg = jdf.groupby("method").primal_integral.mean()
    k_agg = kdf.groupby("method").primal_integral.mean()

    methods = list(_METHOD_STYLE)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, agg, title in zip(axes, [j_agg, k_agg], ["job-shop (disjunctive MIP)", "knapsack"]):
        vals = [agg.get(m, 0) for m in methods]
        colors = [_METHOD_STYLE[m][0] for m in methods]
        labels = [_METHOD_STYLE[m][1] for m in methods]
        ax.bar(range(len(methods)), vals, color=colors)
        ax.set_xticks(range(len(methods)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("mean primal integral")
        ax.set_title(title)
        ax.grid(True, alpha=0.25, axis="y")
    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default="results/multisolver/analysis/figures")
    ap.add_argument("--jssp-csv", default="results/multisolver/jssp_results.csv")
    ap.add_argument("--knapsack-csv", default="results/multisolver/knapsack_results.csv")
    ap.add_argument("--capture-seeds", type=int, nargs="+", default=[7, 8],
                    help="held-out seeds (not used in the main campaign) for anytime curves")
    ap.add_argument("--jssp-budget", type=float, default=8.0)
    ap.add_argument("--knapsack-budget", type=float, default=5.0)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("capturing job-shop trajectories on held-out seeds", args.capture_seeds)
    jssp_rows = _capture_jssp(args.capture_seeds, args.jssp_budget)
    _anytime_figure(jssp_rows, "objective", args.jssp_budget, maximize=False,
                    title="Anytime quality — job-shop, cross-solver\n"
                         "(median over held-out stream instances, IQR band)",
                    out_path=out_dir / "anytime_curve_jssp_multisolver.pdf")

    print("capturing knapsack trajectories on held-out seeds", args.capture_seeds)
    knap_rows = _capture_knapsack(args.capture_seeds, args.knapsack_budget, 700, 1_000_000)
    _anytime_figure(knap_rows, "value", args.knapsack_budget, maximize=True,
                    title="Anytime quality — knapsack, cross-solver\n"
                         "(median over held-out stream instances, IQR band)",
                    out_path=out_dir / "anytime_curve_knapsack_multisolver.pdf")

    print("building PI bar chart from main campaign CSVs")
    _pi_bar_chart(args.jssp_csv, args.knapsack_csv, out_dir / "pi_barchart_multisolver.pdf")

    print(f"wrote figures to {out_dir}")


if __name__ == "__main__":
    main()
