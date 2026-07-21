"""Statistical analysis of the cross-solver validation campaigns
(results/multisolver/{jssp,knapsack}_results.csv), produced by
phase0.run_multisolver_test.

For each solver family (cpsat, gurobi, cplex) and each domain (jssp,
knapsack), compares that solver's boot_cold variant against its own cold
variant using the same statistical battery as analyze_icaps_results.py
(exact two-sided sign test, Wilcoxon signed-rank, percentile bootstrap CI on
the mean primal-integral improvement, Holm-Bonferroni correction across the
family of comparisons).

Usage:
    .venv/bin/python -m phase0.analyze_multisolver_results \\
        --jssp results/multisolver/jssp_results.csv \\
        --knapsack results/multisolver/knapsack_results.csv \\
        --out-dir results/multisolver/analysis
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .analyze_icaps_results import (
    bootstrap_ci_mean, holm_correction, sign_test, to_markdown, wilcoxon_p,
    write_latex_table,
)

SOLVER_PAIRS = [
    ("cpsat", "cpsat_cold", "boot_cold"),
    ("gurobi", "gurobi_cold", "gurobi_boot_cold"),
    ("cplex", "cplex_cold", "cplex_boot_cold"),
]


def _pairwise(df: pd.DataFrame, cold: str, boot: str, value_col: str,
             maximize: bool) -> dict:
    """value_col: 'objective' (jssp, minimize) or 'value' (knapsack, maximize).
    Returns dict of summary stats for boot vs cold on primal_integral, plus
    final-value win/tie/loss counts."""
    key_cols = ["seed", "instance"]
    a = df[df.method == cold].set_index(key_cols)
    b = df[df.method == boot].set_index(key_cols)
    common = a.index.intersection(b.index)
    a, b = a.loc[common], b.loc[common]

    pi_win = int((a.primal_integral.values > b.primal_integral.values).sum())
    pi_loss = int((a.primal_integral.values < b.primal_integral.values).sum())
    pi_tie = len(common) - pi_win - pi_loss

    if maximize:
        val_win = int((b[value_col].values > a[value_col].values).sum())
        val_loss = int((b[value_col].values < a[value_col].values).sum())
    else:
        val_win = int((b[value_col].values < a[value_col].values).sum())
        val_loss = int((b[value_col].values > a[value_col].values).sum())
    val_tie = len(common) - val_win - val_loss

    p_sign = sign_test(pi_win, pi_loss)
    mean_diff, ci_lo, ci_hi = bootstrap_ci_mean(
        a.primal_integral.values - b.primal_integral.values)
    p_wilcoxon = wilcoxon_p(a.primal_integral.values, b.primal_integral.values)

    return {
        "n": len(common),
        "cold_mean_pi": a.primal_integral.mean(),
        "boot_mean_pi": b.primal_integral.mean(),
        "pi_win": pi_win, "pi_tie": pi_tie, "pi_loss": pi_loss,
        "final_win": val_win, "final_tie": val_tie, "final_loss": val_loss,
        "sign_test_p": p_sign,
        "wilcoxon_p": p_wilcoxon if p_wilcoxon is not None else np.nan,
        "mean_pi_improvement": mean_diff, "ci95_lo": ci_lo, "ci95_hi": ci_hi,
    }


def analyze_domain(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    value_col = "value" if domain == "knapsack" else "objective"
    maximize = domain == "knapsack"
    rows = []
    raw_p = {}
    for solver, cold, boot in SOLVER_PAIRS:
        stats = _pairwise(df, cold, boot, value_col, maximize)
        raw_p[solver] = stats["sign_test_p"]
        rows.append({"domain": domain, "solver": solver, **stats})
    p_adj = holm_correction(raw_p)
    for r in rows:
        r["sign_test_p_holm"] = p_adj[r["solver"]]
    return pd.DataFrame(rows)


def cross_solver_speed_table(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """Raw cold-solve comparison: which solver's cold variant reaches best
    primal integral fastest on this instance size/license constraint."""
    value_col = "value" if domain == "knapsack" else "objective"
    cold_methods = ["cpsat_cold", "gurobi_cold", "cplex_cold"]
    agg = df[df.method.isin(cold_methods)].groupby("method").agg(
        mean_pi=("primal_integral", "mean"),
        median_pi=("primal_integral", "median"),
        mean_final_gap=("final_gap", "mean"),
        proven_optimal_rate=("proven_optimal", "mean"),
        n=("primal_integral", "size"),
    ).reset_index()
    agg["domain"] = domain
    return agg.sort_values("mean_pi")


def full_comparison_table(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """Full per-instance comparison: one row per (seed, instance), one
    column per method's primal_integral -- the granular table backing the
    aggregate summaries above."""
    value_col = "value" if domain == "knapsack" else "objective"
    piv_pi = df.pivot_table(index=["seed", "instance", "delta_kind"],
                            columns="method", values="primal_integral")
    piv_val = df.pivot_table(index=["seed", "instance", "delta_kind"],
                             columns="method", values=value_col)
    piv_val.columns = [f"{c}_{value_col}" for c in piv_val.columns]
    out = pd.concat([piv_val, piv_pi.add_suffix("_pi")], axis=1).reset_index()
    out.insert(0, "domain", domain)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jssp", required=True)
    ap.add_argument("--knapsack", required=True)
    ap.add_argument("--out-dir", default="results/multisolver/analysis")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    (out_dir / "tables").mkdir(parents=True, exist_ok=True)

    jssp_df = pd.read_csv(args.jssp)
    knap_df = pd.read_csv(args.knapsack)

    pairwise_jssp = analyze_domain(jssp_df, "jssp")
    pairwise_knap = analyze_domain(knap_df, "knapsack")
    pairwise = pd.concat([pairwise_jssp, pairwise_knap], ignore_index=True)

    speed_jssp = cross_solver_speed_table(jssp_df, "jssp")
    speed_knap = cross_solver_speed_table(knap_df, "knapsack")
    speed = pd.concat([speed_jssp, speed_knap], ignore_index=True)

    full_jssp = full_comparison_table(jssp_df, "jssp")
    full_knap = full_comparison_table(knap_df, "knapsack")

    pairwise.to_csv(out_dir / "tables" / "pairwise_boot_vs_cold.csv", index=False)
    speed.to_csv(out_dir / "tables" / "cold_solver_speed.csv", index=False)
    full_jssp.to_csv(out_dir / "tables" / "full_comparison_jssp.csv", index=False)
    full_knap.to_csv(out_dir / "tables" / "full_comparison_knapsack.csv", index=False)

    print("=== boot_cold vs cold, per solver, per domain ===")
    print(pairwise.to_string(index=False,
                             float_format=lambda x: f"{x:.5g}"))
    print("\n=== raw cold-solver comparison (which solver is fastest at this size) ===")
    print(speed.to_string(index=False, float_format=lambda x: f"{x:.5g}"))

    report_lines = [
        "# Cross-Solver Validation: Statistical Analysis\n",
        "Comparing boot_cold's floor/pocket mechanism against its own cold "
        "variant, independently for CP-SAT, Gurobi, and CPLEX, on both "
        "job-shop (disjunctive MIP) and knapsack domains.\n",
        "## Pairwise: boot_cold vs cold, per solver\n",
        to_markdown(pairwise.round(5)),
        "\n## Raw cold-solver comparison\n",
        to_markdown(speed.round(5)),
        "\n## Full per-instance comparison (job-shop)\n",
        to_markdown(full_jssp.round(5)),
        "\n## Full per-instance comparison (knapsack)\n",
        to_markdown(full_knap.round(5)),
    ]
    (out_dir / "report.md").write_text("\n".join(report_lines))

    # LaTeX artifact: aggregate tables + full per-instance comparison tables
    tex_dir = out_dir / "latex"
    tex_dir.mkdir(parents=True, exist_ok=True)
    write_latex_table(
        pairwise.round(5), tex_dir / "pairwise_boot_vs_cold.tex",
        caption="boot\\_cold vs its own cold variant, per solver and domain "
                "(sign test, Wilcoxon, and bootstrap 95\\% CI on mean primal-integral improvement)",
        label="tab:multisolver-pairwise",
        float_cols=["cold_mean_pi", "boot_mean_pi", "sign_test_p", "wilcoxon_p",
                   "mean_pi_improvement", "ci95_lo", "ci95_hi", "sign_test_p_holm"],
    )
    write_latex_table(
        speed.round(5), tex_dir / "cold_solver_speed.tex",
        caption="Raw cold-solve comparison across solvers: which solver reaches "
                "best primal integral at this license-capped instance size",
        label="tab:multisolver-speed",
        float_cols=["mean_pi", "median_pi", "mean_final_gap", "proven_optimal_rate"],
    )
    write_latex_table(
        full_jssp.round(5), tex_dir / "full_comparison_jssp.tex",
        caption="Full per-instance comparison, job-shop (disjunctive MIP), "
                "all 6 methods, objective and primal integral",
        label="tab:multisolver-full-jssp",
        float_cols=[c for c in full_jssp.columns if c not in
                   ("domain", "seed", "instance", "delta_kind")],
    )
    write_latex_table(
        full_knap.round(5), tex_dir / "full_comparison_knapsack.tex",
        caption="Full per-instance comparison, knapsack, all 6 methods, "
                "value and primal integral",
        label="tab:multisolver-full-knapsack",
        float_cols=[c for c in full_knap.columns if c not in
                   ("domain", "seed", "instance", "delta_kind")],
    )

    print(f"\nwrote {out_dir}/report.md, {out_dir}/tables/*.csv, {tex_dir}/*.tex")


if __name__ == "__main__":
    main()
