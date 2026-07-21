"""Publication figures for the boot_cold ICAPS paper.

Two kinds of figure:

  1. Anytime curves (the flagship figure): median relative-gap-vs-time with
     an inter-quartile band, per method. This needs the FULL solver
     trajectory (gap at every wall-clock moment), which the ICAPS suite CSVs
     do NOT store (they keep only summary stats like primal_integral). So
     this script re-runs a small, representative grid capturing trajectories
     (`capture` subcommand -> a pickle), then plots from that pickle.

  2. Aggregate figures derived purely from the existing result CSVs (no new
     compute): PI-improvement-vs-instance-size, worker-scaling, budget-
     sensitivity, and the RCPSP cross-domain summary.

Usage:
    # step 1: capture trajectories (a few minutes, parallelized)
    .venv/bin/python -m phase0.make_paper_figures capture \\
        --out results/icaps/figures/trajectories.pkl --parallel 12

    # step 2: build every figure
    .venv/bin/python -m phase0.make_paper_figures plot \\
        --traj results/icaps/figures/trajectories.pkl \\
        --out-dir results/icaps/figures
"""

from __future__ import annotations

import argparse
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .harness import cpsat_default_solve, warm_bootstrap_solve  # noqa: E402
from .streams import StreamConfig, generate_stream  # noqa: E402

# Methods shown on the anytime curve, with fixed colors/labels for consistency.
_METHOD_STYLE = {
    "cpsat_cold": ("#d62728", "cpsat_cold (baseline)"),
    "cpsat_warm": ("#ff7f0e", "cpsat_warm (hinted)"),
    "boot_cold": ("#1f77b4", "boot_cold (ours)"),
    "boot_warm": ("#2ca02c", "boot_warm (ours, hinted)"),
}


# ---------------------------------------------------------------------------
# Step 1: capture trajectories (needs compute)
# ---------------------------------------------------------------------------

@dataclass
class _CaptureTask:
    machines: int
    jobs: int
    seed: int
    budget: float
    stream_length: int


def _capture_one(task: _CaptureTask) -> list[dict]:
    """Run all 4 methods over one stream, returning per-(method,step) rows
    carrying the full trajectory. Module-level for multiprocessing-fork."""
    cfg = StreamConfig(num_machines=task.machines, initial_jobs=task.jobs,
                       stream_length=task.stream_length, seed=task.seed, severity="medium")
    cfg.ops_per_job = (task.machines, task.machines)
    cfg.duration_range = (5, 50)
    stream = generate_stream(cfg)

    rows = []
    per_method_prev = {m: None for m in _METHOD_STYLE}
    for inst in stream:
        for method in _METHOD_STYLE:
            prev = per_method_prev[method]
            if method == "cpsat_cold":
                res = cpsat_default_solve(inst, task.budget, prev_solution=None,
                                          workers=1, seed=0, method_name=method)
            elif method == "cpsat_warm":
                res = cpsat_default_solve(inst, task.budget, prev_solution=prev,
                                          workers=1, seed=0, method_name=method)
            elif method == "boot_cold":
                res = warm_bootstrap_solve(inst, task.budget, prev_solution=prev,
                                           workers=1, seed=0, use_hint=False, method_name=method)
            else:  # boot_warm
                res = warm_bootstrap_solve(inst, task.budget, prev_solution=prev,
                                           workers=1, seed=0, use_hint=True, method_name=method)
            rows.append({
                "size": f"{task.machines}x{task.jobs}", "seed": task.seed,
                "stream_step": inst.index, "method": method,
                "objective": res.objective, "trajectory": list(res.trajectory),
                "budget": task.budget,
            })
            if res.solution is not None:
                per_method_prev[method] = res.solution
    return rows


def capture(args) -> None:
    sizes = [tuple(map(int, s.split("x"))) for s in args.sizes]
    tasks = [
        _CaptureTask(m, j, seed, args.budget, args.stream_length)
        for (m, j) in sizes for seed in args.seeds
    ]
    print(f"capturing trajectories: {len(tasks)} (size,seed) configs x 4 methods "
          f"x {args.stream_length + 1} instances @ {args.budget}s")

    all_rows: list[dict] = []
    if args.parallel > 1 and len(tasks) > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=min(args.parallel, len(tasks))) as pool:
            for i, rows in enumerate(pool.imap_unordered(_capture_one, tasks), 1):
                all_rows.extend(rows)
                print(f"  {i}/{len(tasks)} configs done")
    else:
        for i, task in enumerate(tasks, 1):
            all_rows.extend(_capture_one(task))
            print(f"  {i}/{len(tasks)} configs done")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(all_rows, f)
    print(f"wrote {len(all_rows)} rows to {out}")


# ---------------------------------------------------------------------------
# gap-vs-time helpers
# ---------------------------------------------------------------------------

def _gap_on_grid(trajectory, best_known, grid):
    """Step-function gap at each grid time. gap=1 before the first solution;
    otherwise (obj - best_known)/best_known held until the next improvement."""
    traj = sorted(trajectory)
    gaps = np.ones(len(grid))
    if not traj or best_known <= 0:
        return gaps
    ti = 0
    cur_gap = 1.0
    for gi, t in enumerate(grid):
        while ti < len(traj) and traj[ti][0] <= t:
            cur_gap = max(0.0, (traj[ti][1] - best_known) / best_known)
            ti += 1
        gaps[gi] = cur_gap
    return gaps


def fig_anytime_curves(rows, out_dir: Path) -> str | None:
    df = pd.DataFrame(rows)
    # best_known per (size, seed, stream_step): best final objective any method got
    df["objective"] = pd.to_numeric(df["objective"], errors="coerce")
    bk = df[df.objective.notna()].groupby(["size", "seed", "stream_step"]).objective.min()

    made = []
    for size in sorted(df["size"].unique()):
        sub = df[(df["size"] == size) & (df.stream_step >= 1)]  # stream instances only
        if sub.empty:
            continue
        budget = sub.budget.iloc[0]
        grid = np.linspace(0, budget, 240)
        fig, ax = plt.subplots(figsize=(5.5, 4))
        medians = {}
        for method, (color, label) in _METHOD_STYLE.items():
            msub = sub[sub.method == method]
            curves = []
            for _, r in msub.iterrows():
                key = (r["size"], r.seed, r.stream_step)
                if key not in bk.index:
                    continue
                curves.append(_gap_on_grid(r.trajectory, bk.loc[key], grid))
            if not curves:
                continue
            arr = np.vstack(curves)
            med = np.median(arr, axis=0)
            q25 = np.percentile(arr, 25, axis=0)
            q75 = np.percentile(arr, 75, axis=0)
            medians[method] = med
            ax.plot(grid, med, color=color, label=label, linewidth=1.8)
            ax.fill_between(grid, q25, q75, color=color, alpha=0.10)
        # Zoom the y-axis to the informative region: every method starts at
        # gap=1 and plunges within a fraction of a second, so a [0,1] axis
        # hides all the actual separation. Cap at ~1.3x the largest median gap
        # measured just after the initial plunge (t just past the first grid
        # step), and annotate that curves begin at 1.0.
        if medians:
            after_spike = max(m[3] for m in medians.values())  # ~t = 3*budget/240
            ax.set_ylim(0, max(0.05, after_spike * 1.3))
        ax.set_xlabel("wall-clock time (s)")
        ax.set_ylabel("relative gap to best known")
        ax.set_title(f"Anytime solution quality — job-shop {size}\n"
                     f"(median over held-out stream instances, IQR band)")
        ax.text(0.98, 0.02, "all methods start at gap $=1.0$ at $t{=}0$",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
                style="italic", color="0.4")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.25)
        plt.tight_layout()
        p = out_dir / f"anytime_curve_{size}.pdf"
        fig.savefig(p)
        plt.close(fig)
        made.append(str(p))
    return made


# ---------------------------------------------------------------------------
# Aggregate figures from existing CSVs (no compute)
# ---------------------------------------------------------------------------

def _pairwise_pi_improvement(df, method, base="cpsat_cold", by=None):
    """Return per-group (mean_pi_improvement, n) of base_PI - method_PI."""
    df = df[df.status == "ok"].copy()
    df["primal_integral"] = pd.to_numeric(df["primal_integral"], errors="coerce")
    keys = ["experiment_family", "instance_size", "stream_seed", "budget_s",
            "workers", "severity", "bootstrap_policy", "stream_step", "benchmark_name"]
    keys = [k for k in keys if k in df.columns]
    m = df[df.method == method].set_index(keys).primal_integral
    b = df[df.method == base].set_index(keys).primal_integral
    common = m.index.intersection(b.index)
    imp = (b.loc[common] - m.loc[common]).reset_index()
    imp.columns = list(imp.columns[:-1]) + ["pi_improvement"]
    return imp.dropna(subset=["pi_improvement"])


def fig_pi_vs_size(paper_main_csv, out_dir: Path) -> str | None:
    df = pd.read_csv(paper_main_csv)
    imp = _pairwise_pi_improvement(df, "boot_cold")
    if imp.empty:
        return None
    order = sorted(imp.instance_size.unique(),
                   key=lambda s: int(s.split("x")[0]) * int(s.split("x")[1]))
    means = [imp[imp.instance_size == s].pi_improvement.mean() for s in order]
    # bootstrap 95% CI per size
    los, his = [], []
    rng = np.random.default_rng(0)
    for s in order:
        vals = imp[imp.instance_size == s].pi_improvement.values
        boots = [rng.choice(vals, len(vals), replace=True).mean() for _ in range(2000)]
        los.append(np.percentile(boots, 2.5)); his.append(np.percentile(boots, 97.5))
    fig, ax = plt.subplots(figsize=(5, 4))
    x = range(len(order))
    ax.bar(x, means, color="#1f77b4", alpha=0.85,
           yerr=[np.array(means) - np.array(los), np.array(his) - np.array(means)],
           capsize=4)
    ax.axhline(0, color="k", linewidth=0.8)
    ax.set_xticks(list(x)); ax.set_xticklabels(order)
    ax.set_xlabel("instance size (machines x jobs)")
    ax.set_ylabel("mean PI improvement over cpsat_cold\n(higher = boot_cold better)")
    ax.set_title("boot_cold advantage vs. instance size (paper_main)")
    ax.grid(True, axis="y", alpha=0.25)
    plt.tight_layout()
    p = out_dir / "pi_vs_size.pdf"
    fig.savefig(p); plt.close(fig)
    return str(p)


def fig_worker_scaling(workers_csv, out_dir: Path) -> str | None:
    df = pd.read_csv(workers_csv)
    made_any = False
    fig, ax = plt.subplots(figsize=(5, 4))
    for method, (color, label) in _METHOD_STYLE.items():
        if method == "cpsat_cold":
            continue
        imp = _pairwise_pi_improvement(df, method)
        if imp.empty or "workers" not in imp.columns:
            continue
        wvals = sorted(imp.workers.unique())
        means = [imp[imp.workers == w].pi_improvement.mean() for w in wvals]
        ax.plot(wvals, means, "o-", color=color, label=label)
        made_any = True
    if not made_any:
        plt.close(fig); return None
    ax.axhline(0, color="k", linewidth=0.8)
    ax.set_xlabel("CP-SAT workers (parallel search threads)")
    ax.set_ylabel("mean PI improvement over cpsat_cold")
    ax.set_title("Does the advantage survive multi-worker search?")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    p = out_dir / "worker_scaling.pdf"
    fig.savefig(p); plt.close(fig)
    return str(p)


def fig_budget_sensitivity(workers_csv, out_dir: Path) -> str | None:
    df = pd.read_csv(workers_csv)
    df = df[df.workers == 1] if "workers" in df.columns else df
    imp = _pairwise_pi_improvement(df, "boot_cold")
    if imp.empty or "budget_s" not in imp.columns:
        return None
    bvals = sorted(imp.budget_s.unique())
    means = [imp[imp.budget_s == b].pi_improvement.mean() for b in bvals]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(bvals, means, "o-", color="#1f77b4")
    ax.axhline(0, color="k", linewidth=0.8)
    ax.set_xlabel("wall-clock budget (s)")
    ax.set_ylabel("mean PI improvement over cpsat_cold")
    ax.set_title("boot_cold advantage vs. budget (workers=1)")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    p = out_dir / "budget_sensitivity.pdf"
    fig.savefig(p); plt.close(fig)
    return str(p)


def fig_rcpsp_summary(rcpsp_csv, out_dir: Path) -> str | None:
    if not Path(rcpsp_csv).exists():
        return None
    df = pd.read_csv(rcpsp_csv)
    cold = df[df.method == "cpsat_cold"].set_index(["seed", "instance"])
    boot = df[df.method == "boot_cold"].set_index(["seed", "instance"])
    common = cold.index.intersection(boot.index)
    common = [k for k in common if k[1] >= 1]  # stream instances
    c = cold.loc[common].primal_integral.values
    b = boot.loc[common].primal_integral.values
    fig, ax = plt.subplots(figsize=(5, 5))
    lim = max(c.max(), b.max()) * 1.05
    ax.scatter(c, b, alpha=0.5, color="#9467bd")
    ax.plot([0, lim], [0, lim], "k--", linewidth=1)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("cpsat_cold primal integral")
    ax.set_ylabel("boot_cold primal integral")
    ax.set_title(f"RCPSP cross-domain (n={len(common)} stream instances)\n"
                 "points below diagonal = boot_cold better")
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    p = out_dir / "rcpsp_summary.pdf"
    fig.savefig(p); plt.close(fig)
    return str(p)


def plot(args) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []

    if args.traj and Path(args.traj).exists():
        with open(args.traj, "rb") as f:
            rows = pickle.load(f)
        made += fig_anytime_curves(rows, out_dir) or []
    else:
        print("(no trajectory pickle -> skipping anytime curves; run `capture` first)")

    runs = Path(args.runs_dir)
    for fn, csv in [
        (fig_pi_vs_size, runs / "paper_main.csv"),
        (fig_worker_scaling, runs / "workers.csv"),
        (fig_budget_sensitivity, runs / "workers.csv"),
    ]:
        if csv.exists():
            r = fn(csv, out_dir)
            if r:
                made.append(r)
    r = fig_rcpsp_summary(args.rcpsp_csv, out_dir)
    if r:
        made.append(r)

    print(f"wrote {len(made)} figures:")
    for m in made:
        print(f"  {m}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture")
    cap.add_argument("--out", default="results/icaps/figures/trajectories.pkl")
    cap.add_argument("--sizes", nargs="+", default=["15x15", "20x20"])
    cap.add_argument("--seeds", type=int, nargs="+", default=[201, 202, 203, 204, 205, 206])
    cap.add_argument("--budget", type=float, default=8.0)
    cap.add_argument("--stream-length", type=int, default=6)
    cap.add_argument("--parallel", type=int, default=12)
    cap.set_defaults(func=capture)

    pl = sub.add_parser("plot")
    pl.add_argument("--traj", default="results/icaps/figures/trajectories.pkl")
    pl.add_argument("--runs-dir", default="results/icaps/runs")
    pl.add_argument("--rcpsp-csv", default="results/icaps/rcpsp/rcpsp_seeds1_10_combined.csv")
    pl.add_argument("--out-dir", default="results/icaps/figures")
    pl.set_defaults(func=plot)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
