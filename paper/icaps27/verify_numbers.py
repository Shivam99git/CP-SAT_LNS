"""Recompute, from raw CSVs only, every number quoted in the ICAPS-27
manuscript (paper/icaps27/manuscript.tex), and write them to
paper/icaps27/verified_numbers.json.

Nothing here is copied from earlier write-ups: each figure is derived from
the per-instance result files under results/ using the project's own tested
statistics functions (phase0.analyze_icaps_results), so the manuscript can
be audited line-by-line against this script's output.

    .venv/bin/python paper/icaps27/verify_numbers.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from phase0.analyze_icaps_results import (  # noqa: E402
    bootstrap_ci_mean, holm_correction, sign_test, wilcoxon_p,
)

RUNS = ROOT / "results" / "icaps" / "runs"
KEY = ["experiment_family", "instance_size", "stream_seed", "budget_s",
       "workers", "severity", "bootstrap_policy", "stream_step"]


def paired(df: pd.DataFrame, a: str, b: str, key=KEY, metric="primal_integral",
           lower_is_better=True) -> dict:
    """Head-to-head of method `a` vs baseline `b` on `metric`, paired on key."""
    ok = df[df.status == "ok"] if "status" in df.columns else df
    A = ok[ok.method == a].set_index(key)
    B = ok[ok.method == b].set_index(key)
    common = A.index.intersection(B.index)
    x = A.loc[common, metric].to_numpy(float)
    y = B.loc[common, metric].to_numpy(float)
    better = (x < y) if lower_is_better else (x > y)
    worse = (x > y) if lower_is_better else (x < y)
    w, l = int(better.sum()), int(worse.sum())
    diff = (y - x) if lower_is_better else (x - y)  # positive = a better
    mean, lo, hi = bootstrap_ci_mean(diff)
    wp = wilcoxon_p(x, y)
    return {"n": int(len(common)), "win": w, "tie": int(len(common) - w - l), "loss": l,
            "win_rate": w / len(common) if len(common) else float("nan"),
            "sign_p": sign_test(w, l), "wilcoxon_p": wp,
            "mean_improvement": mean, "ci95": [lo, hi],
            "mean_a": float(np.mean(x)), "mean_b": float(np.mean(y))}


def final_obj(df, a, b, key=KEY, col="objective_value"):
    ok = df[df.status == "ok"] if "status" in df.columns else df
    A = ok[ok.method == a].set_index(key)[col]
    B = ok[ok.method == b].set_index(key)[col]
    c = A.index.intersection(B.index)
    x, y = A.loc[c].to_numpy(float), B.loc[c].to_numpy(float)
    loss_mask = x > y
    excess = (x[loss_mask] - y[loss_mask]) / y[loss_mask]
    return {"n": int(len(c)), "win": int((x < y).sum()), "tie": int((x == y).sum()),
            "loss": int(loss_mask.sum()),
            "loss_median_excess": float(np.median(excess)) if len(excess) else 0.0,
            "loss_max_excess": float(np.max(excess)) if len(excess) else 0.0}


def load(name):
    return pd.read_csv(RUNS / f"{name}.csv", low_memory=False)


out: dict = {}

# --- 1. Main campaign (paper_main): boot_cold and all baselines vs cpsat_cold
pm = load("paper_main")
methods = sorted(m for m in pm.method.unique() if m != "cpsat_cold")
agg = (pm.groupby("method")
         .agg(mean_pi=("primal_integral", "mean"),
              median_pi=("primal_integral", "median"),
              mean_final_gap=("final_gap", "mean"),
              n=("primal_integral", "size"))
         .reset_index())
out["paper_main_config"] = {
    "sizes": sorted(pm.instance_size.unique().tolist()),
    "stream_seeds": int(pm.stream_seed.nunique()),
    "budget_s": sorted(pm.budget_s.unique().tolist()),
    "workers": sorted(pm.workers.unique().tolist()),
    "stream_length": int(pm.stream_step.max()),
    "n_rows": int(len(pm)),
    "delta_kind_counts": pm[pm.method == "cpsat_cold"].delta_kind.value_counts().to_dict(),
}
out["paper_main_aggregate"] = agg.to_dict(orient="records")
pw = {m: paired(pm, m, "cpsat_cold") for m in methods}
holm = holm_correction({m: v["sign_p"] for m, v in pw.items()})
for m in pw:
    pw[m]["sign_p_holm"] = holm[m]
out["paper_main_vs_cpsat_cold"] = pw
out["paper_main_vs_boot_cold"] = {m: paired(pm, "boot_cold", m)
                                  for m in methods if m != "boot_cold"}
out["paper_main_final_obj_boot_vs_cold"] = final_obj(pm, "boot_cold", "cpsat_cold")

# per-size and per-delta-kind breakdown (boot_cold vs cpsat_cold)
out["paper_main_by_size"] = {s: paired(pm[pm.instance_size == s], "boot_cold", "cpsat_cold")
                             for s in sorted(pm.instance_size.unique())}
out["paper_main_by_delta"] = {k: paired(pm[pm.delta_kind == k], "boot_cold", "cpsat_cold")
                              for k in sorted(pm.delta_kind.unique())}

# stability: fraction of common operations whose start moved (lower = more stable)
stab = {}
for m in ["boot_cold", "boot_warm", "cpsat_cold", "cpsat_warm",
          "fix_and_optimize_50", "lns_prev_solution", "local_branching_prev"]:
    s = pm[(pm.method == m) & pm.fraction_moved_ops.notna()].fraction_moved_ops
    stab[m] = {"mean_fraction_moved": float(s.mean()), "n": int(len(s))}
out["paper_main_stability"] = stab
out["paper_main_stability_boot_vs_cold"] = paired(
    pm[pm.fraction_moved_ops.notna()], "boot_cold", "cpsat_cold",
    metric="fraction_moved_ops")

# --- 2. Worker scaling: floor (boot_cold) vs hint (boot_warm, cpsat_warm)
wk = load("workers")
out["workers"] = {
    int(w): {m: paired(wk[wk.workers == w], m, "cpsat_cold")
             for m in ["boot_cold", "boot_warm", "cpsat_warm"]}
    for w in sorted(wk.workers.unique())
}
# the same floor-vs-hint contrast on the large single-worker campaign
out["paper_main_hint_vs_floor"] = {
    "boot_warm_vs_cpsat_cold": pw["boot_warm"],
    "cpsat_warm_vs_cpsat_cold": pw["cpsat_warm"],
    "boot_cold_vs_boot_warm": paired(pm, "boot_cold", "boot_warm"),
}

# --- 2b. Per-campaign consistency: floor (boot_cold) vs hint-based reuse
# (cpsat_warm = previous solution as solver hint; boot_warm = repaired floor
# as hint AND kept as floor), each vs cpsat_cold, single-worker rows only.
campaigns = ["pilot", "arrivals", "workers", "paper_main", "real_benchmarks",
             "taillard_benchmarks", "dmu_benchmarks", "swv_benchmarks", "yn_benchmarks"]
consistency = {}
for name in campaigns:
    d = load(name)
    d = d[d.workers == 1]
    consistency[name] = {
        m: paired(d, m, "cpsat_cold")
        for m in ["boot_cold", "boot_warm", "cpsat_warm"] if m in set(d.method)
    }
    consistency[name]["_config"] = {
        "sizes": sorted(d.instance_size.unique().tolist()),
        "stream_seeds": sorted(int(s) for s in d.stream_seed.unique()),
        "budget_s": sorted(float(b) for b in d.budget_s.unique()),
        "stream_length": int(d.stream_step.max()),
        "delta_kinds": sorted(d.delta_kind.unique().tolist()),
        "bootstrap_policies": sorted(d.bootstrap_policy.unique().tolist()),
    }
out["consistency_by_campaign"] = consistency

# --- 3. Pooled ICAPS-preset campaigns (the n=1547 figure in BOOT_COLD_PAPER.md)
pool_names = ["smoke", "pilot", "workers", "arrivals", "paper_main", "real_benchmarks"]
pool = pd.concat([load(n) for n in pool_names], ignore_index=True)
out["pooled_6_campaigns"] = {"campaigns": pool_names,
                             "pi": paired(pool, "boot_cold", "cpsat_cold"),
                             "final_obj": final_obj(pool, "boot_cold", "cpsat_cold")}

# --- 4. Real published job-shop benchmarks
real = {}
for name, label in [("real_benchmarks", "OR-Library"), ("taillard_benchmarks", "Taillard"),
                    ("dmu_benchmarks", "DMU"), ("swv_benchmarks", "SWV"),
                    ("yn_benchmarks", "YN")]:
    d = load(name)
    r = paired(d, "boot_cold", "cpsat_cold")
    r["instances"] = sorted(d.benchmark_name.dropna().unique().tolist())
    r["n_instances"] = len(r["instances"])
    r["stream_seeds"] = int(d.stream_seed.nunique())
    r["stream_length"] = int(d.stream_step.max())
    r["budget_s"] = sorted(d.budget_s.unique().tolist())
    r["final_obj"] = final_obj(d, "boot_cold", "cpsat_cold")
    real[label] = r
out["real_jssp"] = real

# --- 5. RCPSP: synthetic real-scale campaign and PSPLIB instances
rk = ["seed", "instance"]
rs = pd.read_csv(ROOT / "results/icaps/rcpsp/rcpsp_seeds1_10_combined.csv")
rr = pd.read_csv(ROOT / "results/icaps/rcpsp/rcpsp_real_benchmarks.csv")
rr["family"] = rr.benchmark_name.str.extract(r"(j\d+)_")
out["rcpsp_synthetic"] = {
    "all": paired(rs, "boot_cold", "cpsat_cold", key=rk),
    "stream_only": paired(rs[rs.delta_kind != "base"], "boot_cold", "cpsat_cold", key=rk),
    "final_obj": final_obj(rs, "boot_cold", "cpsat_cold", key=rk, col="objective"),
    "n_seeds": int(rs.seed.nunique()),
}
rkey = ["benchmark_name", "seed", "instance"]
out["rcpsp_psplib"] = {
    "all": paired(rr, "boot_cold", "cpsat_cold", key=rkey),
    "final_obj": final_obj(rr, "boot_cold", "cpsat_cold", key=rkey, col="objective"),
    "by_family": {f: paired(rr[rr.family == f], "boot_cold", "cpsat_cold", key=rkey)
                  for f in sorted(rr.family.dropna().unique())},
    "n_instances": int(rr.benchmark_name.nunique()),
    "n_seeds": int(rr.seed.nunique()),
}
bks = json.loads((ROOT / "tests/fixtures/rcpsp_real/optalcp_bks_reference.json").read_text())
base = rr[rr.delta_kind == "base"].copy()
base["ext"] = base.benchmark_name.map(bks)
out["rcpsp_psplib_external_check"] = {
    "n_base_runs": int(len(base)),
    "match_external_optimum": int((base.objective == base.ext).sum()),
    "better_than_external_optimum": int((base.objective < base.ext).sum()),
    "worse_than_external_optimum": int((base.objective > base.ext).sum()),
}

# --- 6. Cross-solver (CP-SAT / Gurobi / CPLEX), license-capped instances
xs = {}
pv = {}
for dom, f, col, lib in [("jssp", "jssp_results.csv", "objective", True),
                         ("knapsack", "knapsack_results.csv", "value", False)]:
    d = pd.read_csv(ROOT / "results/multisolver" / f)
    for solver, cold, boot in [("CP-SAT", "cpsat_cold", "boot_cold"),
                               ("Gurobi", "gurobi_cold", "gurobi_boot_cold"),
                               ("CPLEX", "cplex_cold", "cplex_boot_cold")]:
        r = paired(d, boot, cold, key=["seed", "instance"])
        xs[f"{dom}/{solver}"] = r
        pv[f"{dom}/{solver}"] = r["sign_p"]
    # three independent formulations agreeing on the optimum?
    piv = d.pivot_table(index=["seed", "instance"], columns="method", values=col)
    colds = piv[["cpsat_cold", "gurobi_cold", "cplex_cold"]]
    xs[f"{dom}/n_instances"] = int(len(piv))
    xs[f"{dom}/cold_solvers_all_agree"] = int((colds.nunique(axis=1) == 1).sum())
    xs[f"{dom}/mean_pi_cold"] = {s: float(d[d.method == s].primal_integral.mean())
                                 for s in ["cpsat_cold", "gurobi_cold", "cplex_cold"]}
    xs[f"{dom}/n_seeds"] = int(d.seed.nunique())
h = holm_correction(pv)
for k in pv:
    xs[k]["sign_p_holm"] = h[k]
# final value of each floor variant vs. its own solver run from scratch
fv = {"better": 0, "tie": 0, "worse": 0}
for f, col, minimize in [("jssp_results.csv", "objective", True),
                         ("knapsack_results.csv", "value", False)]:
    d = pd.read_csv(ROOT / "results/multisolver" / f)
    for cold, boot in [("cpsat_cold", "boot_cold"), ("gurobi_cold", "gurobi_boot_cold"),
                       ("cplex_cold", "cplex_boot_cold")]:
        A = d[d.method == boot].set_index(["seed", "instance"])[col]
        B = d[d.method == cold].set_index(["seed", "instance"])[col]
        fv["better"] += int(((A < B) if minimize else (A > B)).sum())
        fv["worse"] += int(((A > B) if minimize else (A < B)).sum())
        fv["tie"] += int((A == B).sum())
xs["final_value_vs_cold"] = fv
out["cross_solver"] = xs


# --- 6b. Per-delta analysis (main campaign): quality of the repaired floor
# itself, and each reuse method's win rate vs cpsat_cold, Holm over 15 tests.
bfl = pm[(pm.method == "boot_cold") & pm.bootstrap_objective.notna()].copy()
bfl["floor_gap"] = (bfl.bootstrap_objective - bfl.best_known) / bfl.best_known
by_delta = {}
dp = {}
for k in ["arrival", "cancellation", "duration_jitter", "outage", "base"]:
    d = pm[pm.delta_kind == k]
    row = {m: paired(d, m, "cpsat_cold") for m in ["boot_cold", "boot_warm", "cpsat_warm"]}
    g = bfl[bfl.delta_kind == k].floor_gap
    row["floor_gap_median"] = float(g.median()) if len(g) else None
    by_delta[k] = row
    for m in ["boot_cold", "boot_warm", "cpsat_warm"]:
        dp[f"{k}/{m}"] = row[m]["sign_p"]
out["paper_main_delta_analysis"] = by_delta
out["paper_main_delta_holm"] = holm_correction(dp)

# --- 7. Extra facts quoted in the text
# floor construction time (boot_cold rows that had a previous solution)
bt = pm[(pm.method == "boot_cold") & (pm.has_previous_solution == True)]  # noqa: E712
out["floor_time_ms"] = {
    s: {"median": float(g.bootstrap_time_ms.median()), "max": float(g.bootstrap_time_ms.max()),
        "n": int(len(g))}
    for s, g in bt.groupby("instance_size")
}
# CP-SAT continuation: wall-clock time actually used by cpsat_cold (budget 8 s)
out["paper_main_cold_wall_s"] = {
    "median": float(pm[pm.method == "cpsat_cold"].total_wall_time_s.median()),
    "proven_optimal_rate": float(pm[pm.method == "cpsat_cold"].optimality_proved.astype(bool).mean()),
}
# PSPLIB misses vs external optimum: which instances, how far
miss = base[base.objective > base.ext]
out["rcpsp_psplib_external_misses"] = {
    "instances": sorted(miss.benchmark_name.unique().tolist()),
    "mean_excess": float(((miss.objective - miss.ext) / miss.ext).mean()) if len(miss) else 0.0,
    "max_excess": float(((miss.objective - miss.ext) / miss.ext).max()) if len(miss) else 0.0,
}
# Holm over every sign test in the consistency table
cons_p = {f"{c}/{m}": r["sign_p"] for c, d in consistency.items()
          for m, r in d.items() if not m.startswith("_")}
cons_h = holm_correction(cons_p)
out["consistency_holm"] = cons_h
# knapsack: spread of the three cold solvers' final values
dk = pd.read_csv(ROOT / "results/multisolver/knapsack_results.csv")
pk = dk.pivot_table(index=["seed", "instance"], columns="method", values="value")[
    ["cpsat_cold", "gurobi_cold", "cplex_cold"]]
out["knapsack_cold_spread_max_rel"] = float(((pk.max(axis=1) - pk.min(axis=1)) / pk.max(axis=1)).max())


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return o


dest = Path(__file__).with_name("verified_numbers.json")
dest.write_text(json.dumps(_clean(out), indent=2))
print(f"wrote {dest}")
