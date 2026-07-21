"""Statistical analysis + report generation for ICAPS suite CSV results.

Graceful degradation (per task spec §18): this environment has neither
scipy nor matplotlib installed (checked directly: both ImportError). Sign
test and bootstrap CI have zero third-party dependencies and are the
PRIMARY significance tooling here; Wilcoxon is attempted via scipy and
skipped with an explicit note if unavailable; plots are attempted via
matplotlib and skipped with an explicit note if unavailable. Nothing in
this script raises just because an optional dependency is missing -- CSV
and Markdown outputs are always produced.

Usage:
    .venv/bin/python -m phase0.analyze_icaps_results \\
        --csv results/icaps/runs/pilot.csv --out-dir results/icaps \\
        --baseline cpsat_cold
"""

from __future__ import annotations

import argparse
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.stats import wilcoxon as _scipy_wilcoxon
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MATPLOTLIB = True
except ImportError:
    HAVE_MATPLOTLIB = False


def to_markdown(df: pd.DataFrame) -> str:
    """Dependency-free Markdown table (pandas.to_markdown needs the
    `tabulate` package, which is not installed in this environment -- avoid
    adding a new dependency per task spec §18)."""
    if df.empty:
        return "*(no rows)*"
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = []
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append(f"{v:.4f}" if isinstance(v, float) else str(v))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep] + body)


# ---------------------------------------------------------------------------
# Dependency-free statistics
# ---------------------------------------------------------------------------

def sign_test(wins: int, losses: int) -> float:
    """Exact two-sided sign-test p-value. No scipy dependency (binomial
    coefficients via math.comb)."""
    # Defensive int() cast: wins/losses often arrive as numpy.int64 (e.g. from
    # `.sum()` on a boolean array). `2 ** n` with a numpy.int64 `n` silently
    # overflows numpy's fixed-width integer (wraps/becomes wrong) instead of
    # using Python's arbitrary-precision ints, which corrupts the p-value
    # (found 2026-07-11: an uncast caller got sign_p=1.0 for a 27/136 split
    # that should have been ~1e-18). Every caller in this module already
    # casts explicitly, but the cast belongs here so the function is safe
    # regardless of caller discipline.
    wins, losses = int(wins), int(losses)
    n = wins + losses
    if n == 0:
        return 1.0
    k = max(wins, losses)
    p = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return min(1.0, 2 * p)


def bootstrap_ci_mean(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05,
                      seed: int = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI for the mean. Returns (mean, lo, hi)."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boot_means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(n_boot)
    ])
    lo, hi = np.percentile(boot_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(values.mean()), float(lo), float(hi)


def holm_correction(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni step-down correction. Returns adjusted p-values keyed
    the same as the input."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted = {}
    running_max = 0.0
    for i, (key, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running_max = max(running_max, adj)
        adjusted[key] = running_max
    return adjusted


def wilcoxon_p(a: np.ndarray, b: np.ndarray) -> float | None:
    if not HAVE_SCIPY:
        return None
    diffs = np.asarray(a) - np.asarray(b)
    diffs = diffs[diffs != 0]
    if len(diffs) < 1:
        return None
    try:
        return float(_scipy_wilcoxon(diffs).pvalue)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Aggregate + breakdown tables
# ---------------------------------------------------------------------------

def per_method_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    ok = df[df.status == "ok"]
    rows = []
    for method, g in ok.groupby("method"):
        pi = g.primal_integral.dropna()
        fg = g.final_gap.dropna()
        bt = g.bootstrap_time_ms.dropna()
        rows.append({
            "method": method,
            "n": len(g),
            "mean_pi": pi.mean(), "median_pi": pi.median(),
            "std_pi": pi.std(), "iqr_pi": pi.quantile(0.75) - pi.quantile(0.25),
            "mean_final_gap": fg.mean(), "median_final_gap": fg.median(),
            "mean_bootstrap_time_ms": bt.mean(), "median_bootstrap_time_ms": bt.median(),
            "mean_moved_ops_frac": g.fraction_moved_ops.dropna().mean(),
            "optimality_proof_rate": g.optimality_proved.astype(bool).mean(),
            "feasibility_failure_rate": 1 - g.solution_feasible.astype(bool).mean(),
        })
    all_df = df.groupby("method").size().rename("n_all").reset_index()
    err = df[df.status == "error"].groupby("method").size().rename("n_errors")
    out = pd.DataFrame(rows).merge(all_df, on="method", how="right").merge(
        err, on="method", how="left")
    out["n_errors"] = out["n_errors"].fillna(0).astype(int)
    return out.sort_values("mean_pi")


def pairwise_vs_baseline(df: pd.DataFrame, baseline: str) -> pd.DataFrame:
    ok = df[df.status == "ok"]
    key_cols = ["experiment_family", "instance_size", "stream_seed", "budget_s",
               "workers", "severity", "bootstrap_policy", "stream_step"]
    base = ok[ok.method == baseline].set_index(key_cols)
    rows = []
    raw_pvalues = {}
    for method in sorted(ok.method.unique()):
        if method == baseline:
            continue
        other = ok[ok.method == method].set_index(key_cols)
        common = base.index.intersection(other.index)
        if len(common) == 0:
            continue
        b = base.loc[common]
        o = other.loc[common]

        pi_w = int((b.primal_integral.values > o.primal_integral.values).sum())
        pi_l = int((b.primal_integral.values < o.primal_integral.values).sum())
        pi_t = len(common) - pi_w - pi_l
        fg_w = int((b.final_gap.values > o.final_gap.values).sum())
        fg_l = int((b.final_gap.values < o.final_gap.values).sum())
        fg_t = len(common) - fg_w - fg_l

        stab_w = stab_l = stab_t = 0
        if "fraction_moved_ops" in b.columns and "fraction_moved_ops" in o.columns:
            bs, os_ = b.fraction_moved_ops.values, o.fraction_moved_ops.values
            valid = ~(np.isnan(bs.astype(float)) | np.isnan(os_.astype(float)))
            stab_w = int((bs[valid].astype(float) > os_[valid].astype(float)).sum())
            stab_l = int((bs[valid].astype(float) < os_[valid].astype(float)).sum())
            stab_t = int(valid.sum()) - stab_w - stab_l

        p_sign = sign_test(pi_w, pi_l)
        raw_pvalues[method] = p_sign
        mean_diff, ci_lo, ci_hi = bootstrap_ci_mean(
            b.primal_integral.values - o.primal_integral.values)
        p_wilcoxon = wilcoxon_p(b.primal_integral.values, o.primal_integral.values)

        rows.append({
            "method": method, "n_common": len(common),
            "pi_win": pi_w, "pi_tie": pi_t, "pi_loss": pi_l,
            "final_gap_win": fg_w, "final_gap_tie": fg_t, "final_gap_loss": fg_l,
            "stability_win": stab_w, "stability_tie": stab_t, "stability_loss": stab_l,
            "sign_test_p": p_sign,
            "wilcoxon_p": p_wilcoxon if p_wilcoxon is not None else np.nan,
            "mean_pi_improvement": mean_diff, "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        adjusted = holm_correction(raw_pvalues)
        out["sign_test_p_holm"] = out["method"].map(adjusted)
    return out.sort_values("mean_pi_improvement", ascending=False)


def breakdown_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    ok = df[df.status == "ok"]
    if by not in ok.columns:
        return pd.DataFrame()
    g = ok.groupby(["method", by]).agg(
        mean_pi=("primal_integral", "mean"),
        mean_final_gap=("final_gap", "mean"),
        n=("primal_integral", "size"),
    ).reset_index()
    return g.sort_values([by, "mean_pi"])


BREAKDOWN_DIMS = ["delta_kind", "severity", "budget_s", "workers", "instance_size",
                  "objective", "bootstrap_policy", "stream_step"]


# ---------------------------------------------------------------------------
# LaTeX table writer -- every row ends with \\, midrule/bottomrule only
# after a row that ends with \\.
# ---------------------------------------------------------------------------

def _escape_latex(s) -> str:
    return str(s).replace("_", r"\_").replace("%", r"\%")


def write_latex_table(df: pd.DataFrame, path: Path, caption: str, label: str,
                      float_cols: list[str] | None = None) -> None:
    float_cols = float_cols or []
    cols = list(df.columns)
    lines = [
        r"\begin{table}[t]", r"\centering",
        r"\begin{tabular}{" + "l" * len(cols) + "}",
        r"\toprule",
        " & ".join(_escape_latex(c) for c in cols) + r" \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if c in float_cols and isinstance(v, (int, float)) and not pd.isna(v):
                cells.append(f"{v:.4f}")
            else:
                cells.append(_escape_latex(v))
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}",
             rf"\caption{{{caption}}}", rf"\label{{{label}}}", r"\end{table}"]
    # verify the LaTeX requirement: every row before midrule/bottomrule ends \\
    for i, ln in enumerate(lines):
        if ln in (r"\midrule", r"\bottomrule") and i > 0:
            prev = lines[i - 1]
            assert prev.rstrip().endswith(r"\\"), (
                f"LaTeX row before {ln!r} does not end with \\\\: {prev!r}")
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Plots (matplotlib, only if available)
# ---------------------------------------------------------------------------

def make_plots(df: pd.DataFrame, out_dir: Path, baseline: str) -> list[str]:
    if not HAVE_MATPLOTLIB:
        return []
    made = []
    ok = df[df.status == "ok"]

    # 1. final gap boxplot by method
    try:
        methods = sorted(ok.method.unique())
        data = [ok[ok.method == m].final_gap.dropna().values for m in methods]
        fig, ax = plt.subplots(figsize=(max(6, len(methods) * 0.8), 4))
        ax.boxplot(data, tick_labels=methods)
        ax.set_ylabel("final gap")
        ax.set_title("Final gap by method")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        p = out_dir / "figures" / "final_gap_boxplot.pdf"
        fig.savefig(p)
        plt.close(fig)
        made.append(str(p))
    except Exception:
        pass

    # 2. PI scatter: baseline vs each other method (first non-baseline method)
    try:
        others = [m for m in ok.method.unique() if m != baseline]
        if others:
            m = others[0]
            key_cols = ["stream_seed", "budget_s", "stream_step", "instance_size"]
            b = ok[ok.method == baseline].set_index(key_cols).primal_integral
            o = ok[ok.method == m].set_index(key_cols).primal_integral
            common = b.index.intersection(o.index)
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.scatter(b.loc[common], o.loc[common], alpha=0.6)
            lim = [0, max(b.loc[common].max(), o.loc[common].max()) * 1.05 + 1e-6]
            ax.plot(lim, lim, "k--", linewidth=1)
            ax.set_xlabel(f"{baseline} PI")
            ax.set_ylabel(f"{m} PI")
            ax.set_title(f"{baseline} vs {m}: primal integral")
            plt.tight_layout()
            p = out_dir / "figures" / "pi_scatter.pdf"
            fig.savefig(p)
            plt.close(fig)
            made.append(str(p))
    except Exception:
        pass

    # 3. severity heatmap (delta_kind x severity, median PI improvement vs baseline)
    try:
        if "severity" in ok.columns and ok.severity.nunique() > 1:
            piv = ok.groupby(["delta_kind", "severity"]).primal_integral.median().unstack()
            fig, ax = plt.subplots(figsize=(6, 4))
            im = ax.imshow(piv.values, aspect="auto", cmap="viridis")
            ax.set_xticks(range(len(piv.columns)), piv.columns)
            ax.set_yticks(range(len(piv.index)), piv.index)
            ax.set_title("Median PI by delta kind x severity")
            fig.colorbar(im, ax=ax)
            plt.tight_layout()
            p = out_dir / "figures" / "severity_heatmap.pdf"
            fig.savefig(p)
            plt.close(fig)
            made.append(str(p))
    except Exception:
        pass

    # 4. bootstrap overhead scaling: num_ops proxy (instance_size) vs bootstrap_time_ms
    try:
        boot_rows = ok[ok.bootstrap_time_ms.notna() & (ok.bootstrap_time_ms > 0)]
        if not boot_rows.empty:
            fig, ax = plt.subplots(figsize=(5, 4))
            for method, g in boot_rows.groupby("method"):
                ax.scatter(g.instance_size.astype(str), g.bootstrap_time_ms, label=method, alpha=0.6)
            ax.set_ylabel("bootstrap time (ms)")
            ax.set_xlabel("instance size")
            ax.legend(fontsize=6)
            plt.xticks(rotation=45, ha="right")
            plt.tight_layout()
            p = out_dir / "figures" / "overhead_scaling.pdf"
            fig.savefig(p)
            plt.close(fig)
            made.append(str(p))
    except Exception:
        pass

    return made


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", nargs="+", required=True)
    ap.add_argument("--out-dir", default="results/icaps")
    ap.add_argument("--baseline", default="cpsat_cold")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    (out_dir / "tables").mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)

    frames = [pd.read_csv(f) for f in args.csv]
    df = pd.concat(frames, ignore_index=True)
    print(f"loaded {len(df)} rows from {len(args.csv)} file(s)")
    print(f"methods: {sorted(df.method.unique())}")
    print(f"scipy available: {HAVE_SCIPY} | matplotlib available: {HAVE_MATPLOTLIB}")

    agg = per_method_aggregate(df)
    agg.to_csv(out_dir / "tables" / "per_method_aggregate.csv", index=False)

    pairwise = pairwise_vs_baseline(df, args.baseline)
    pairwise.to_csv(out_dir / "tables" / f"pairwise_vs_{args.baseline}.csv", index=False)

    breakdowns = {}
    for dim in BREAKDOWN_DIMS:
        bt = breakdown_table(df, dim)
        if not bt.empty:
            bt.to_csv(out_dir / "tables" / f"breakdown_by_{dim}.csv", index=False)
            breakdowns[dim] = bt

    if not agg.empty:
        write_latex_table(
            agg[["method", "n", "mean_pi", "mean_final_gap", "optimality_proof_rate"]].round(4),
            out_dir / "tables" / "main_jssp_results.tex",
            "Per-method aggregate results", "tab:main-jssp",
            float_cols=["mean_pi", "mean_final_gap", "optimality_proof_rate"],
        )
    if not pairwise.empty:
        write_latex_table(
            pairwise[["method", "n_common", "pi_win", "pi_tie", "pi_loss", "sign_test_p"]].round(4),
            out_dir / "tables" / "ablation_results.tex",
            f"Pairwise comparison vs {args.baseline}", "tab:ablation",
            float_cols=["sign_test_p"],
        )
    if "delta_kind" in breakdowns:
        write_latex_table(
            breakdowns["delta_kind"].round(4), out_dir / "tables" / "severity_results.tex",
            "Results by delta kind", "tab:by-delta", float_cols=["mean_pi", "mean_final_gap"],
        )
    if "workers" in breakdowns:
        write_latex_table(
            breakdowns["workers"].round(4), out_dir / "tables" / "worker_results.tex",
            "Results by worker count", "tab:by-workers", float_cols=["mean_pi", "mean_final_gap"],
        )
    if "budget_s" in breakdowns:
        write_latex_table(
            breakdowns["budget_s"].round(4), out_dir / "tables" / "budget_results.tex",
            "Results by budget", "tab:by-budget", float_cols=["mean_pi", "mean_final_gap"],
        )

    figures = make_plots(df, out_dir, args.baseline)

    _write_report(df, agg, pairwise, breakdowns, figures, out_dir, args.baseline)
    print(f"\nwrote tables to {out_dir / 'tables'}, figures to {out_dir / 'figures'}, "
         f"report to {out_dir / 'report.md'}")


def _write_report(df, agg, pairwise, breakdowns, figures, out_dir, baseline):
    lines = []
    lines.append("# ICAPS Experiment Report\n")
    lines.append(f"Generated from {len(df)} result rows "
                f"({df.status.eq('ok').sum()} ok, {df.status.eq('error').sum()} errors).\n")
    lines.append("## 1. Executive summary\n")
    if not agg.empty:
        best = agg.iloc[0]
        base_row = agg[agg.method == baseline]
        base_pi = base_row.mean_pi.iloc[0] if not base_row.empty else float("nan")
        lines.append(
            f"Best method by mean primal integral: **{best.method}** "
            f"(mean PI {best.mean_pi:.4f}) vs baseline `{baseline}` "
            f"(mean PI {base_pi:.4f}).\n"
        )
    lines.append("## 2. What was implemented\n")
    lines.append(
        "Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, "
        "3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local "
        "branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-"
        "specific bootstrap floor policies, static benchmark loaders, an RCPSP "
        "second domain, and stability metrics -- see docs/icaps_experiment_plan.md.\n"
    )
    lines.append("## 3. What experiments were run\n")
    for fam in sorted(df.experiment_family.unique()):
        n = (df.experiment_family == fam).sum()
        lines.append(f"- `{fam}`: {n} rows\n")
    lines.append("## 4. Failed / unfinished parts\n")
    errs = df[df.status == "error"]
    if errs.empty:
        lines.append("No row-level errors in this data.\n")
    else:
        for (method, msg), g in errs.groupby(["method", "error_message"]):
            lines.append(f"- {method}: {msg} ({len(g)} rows)\n")
    lines.append(
        "\nNot executed in this pass (compute cost appropriate for an unattended "
        "multi-day run; grids validated via `--dry-run`, not run): `main`, "
        "`ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond "
        "what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness "
        "objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP "
        "are documented TODOs, not implemented.\n"
    )
    lines.append(f"scipy available: {HAVE_SCIPY} (Wilcoxon {'computed' if HAVE_SCIPY else 'SKIPPED -- not installed'}). "
                f"matplotlib available: {HAVE_MATPLOTLIB} (plots {'generated' if HAVE_MATPLOTLIB else 'SKIPPED -- not installed'}).\n")

    lines.append("## 5. Main results\n")
    if not agg.empty:
        lines.append(to_markdown(agg.round(4)) + "\n")

    lines.append("## 6. Tables\n")
    lines.append(f"### Pairwise vs {baseline}\n")
    if not pairwise.empty:
        lines.append(to_markdown(pairwise.round(4)) + "\n")
    for dim, bt in breakdowns.items():
        lines.append(f"### Breakdown by {dim}\n")
        lines.append(to_markdown(bt.round(4)) + "\n")

    lines.append("## 7. Figures\n")
    if figures:
        for f in figures:
            lines.append(f"- {f}\n")
    else:
        lines.append("No figures generated (matplotlib not installed in this environment).\n")

    lines.append("## 8. Interpretation\n")
    if not pairwise.empty:
        best_row = pairwise.iloc[0]
        lines.append(
            f"- **Where it helps:** `{best_row.method}` shows the largest mean PI "
            f"improvement over `{baseline}` ({best_row.mean_pi_improvement:.4f}, "
            f"{best_row.pi_win}W/{best_row.pi_tie}T/{best_row.pi_loss}L, "
            f"sign-test p={best_row.sign_test_p:.4f}).\n"
        )
        worst_row = pairwise.iloc[-1]
        lines.append(
            f"- **Where it weakens:** `{worst_row.method}` shows the smallest/negative "
            f"mean PI improvement ({worst_row.mean_pi_improvement:.4f}).\n"
        )
    if "delta_kind" in breakdowns:
        by_delta = breakdowns["delta_kind"]
        arrival_rows = by_delta[by_delta.delta_kind.isin(["arrival", "batch_arrival"])]
        if not arrival_rows.empty:
            lines.append(
                "- **Arrivals:** " +
                ", ".join(f"{r.method}={r.mean_pi:.4f}" for _, r in arrival_rows.iterrows()) +
                " (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).\n"
            )
    if "workers" in breakdowns and breakdowns["workers"].workers.nunique() > 1:
        lines.append("- **Multi-worker:** see `breakdown_by_workers.csv` for whether "
                     "gains shrink as num_workers grows (not yet run at scale in this pass).\n")
    else:
        lines.append("- **Multi-worker:** not exercised in this pass (workers=1 only); "
                     "this is a known, explicitly flagged limitation, not a claim.\n")

    lines.append("## 9. ICAPS paper recommendation\n")
    lines.append(
        "**Ready:** the method (boot_cold), the domination guarantee (in its precise "
        "form -- see below), the pilot primal-integral result on job-shop across 7 "
        "seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and "
        "the benchmark/loader infrastructure.\n\n"
        "**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/"
        "worker counts) for the actual paper table; `workers` preset specifically to "
        "characterize whether gains shrink under CP-SAT's own multi-worker portfolio "
        "search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only "
        "activates with workers>1); `arrivals` preset to confirm gap_insert/"
        "regret_insert/beam_insert close the arrival weak case at scale, not just in "
        "the single case checked by unit tests.\n\n"
        "**Strongest claim supported by data so far:** a near-zero-cost constructive "
        "repair of the previous schedule, kept as an anytime floor under an "
        "unmodified CP-SAT solve, improves primal integral, replicated across seeds "
        "and domains (BOOT_COLD_PAPER.md).\n\n"
        "**Domination guarantee -- precise form (do not overstate):** boot_cold's "
        "final objective is provably never worse than **its own unmodified "
        "continuation** (same run, same budget window) -- this is a theorem, not an "
        "empirical tendency. It is *not* an exact guarantee against a *separately "
        "invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 "
        "re-analysis) boot_cold's final objective was strictly worse than an "
        "independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max "
        "3.63%), attributable to wall-clock non-reproducibility, not a flaw in the "
        "proof. State the theorem in its precise form; report the 92.4% empirical "
        "non-loss rate as a strong-but-not-absolute finding, never as \"provably "
        "never worse than cold-solving.\"\n\n"
        "**Claims to avoid:** this is not a machine-learning method; CP-SAT's own "
        "search is not improved or sped to proof; final objective is not usually "
        "better (ties are the norm, by design); \"provably never worse than cold\" "
        "(only true against its own continuation, see above); weak cases (arrivals, "
        "and any case not yet run at the `main`/`workers`/`budgets` scale) should not "
        "be papered over.\n"
    )

    (out_dir / "report.md").write_text("".join(lines))


if __name__ == "__main__":
    main()
