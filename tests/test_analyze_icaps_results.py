"""Tests for phase0/analyze_icaps_results.py -- the statistics engine behind
every p-value/table/figure in results/icaps/report.md. No coverage existed
for this module before 2026-07-11, despite it having produced every
significance claim reported in BOOT_COLD_PAPER.md and this project's
analysis sessions.

    .venv/bin/python -m pytest tests/test_analyze_icaps_results.py -q
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from phase0.analyze_icaps_results import (
    bootstrap_ci_mean,
    breakdown_table,
    holm_correction,
    pairwise_vs_baseline,
    per_method_aggregate,
    sign_test,
    to_markdown,
    write_latex_table,
)

# ---------------------------------------------------------------------------
# sign_test
# ---------------------------------------------------------------------------

def test_sign_test_known_values():
    # 10 wins, 0 losses: exact two-sided value is 2 * 0.5**10 = 0.001953125
    assert sign_test(10, 0) == pytest.approx(2 * 0.5 ** 10)
    # perfectly balanced: p=1.0
    assert sign_test(5, 5) == pytest.approx(1.0)
    # 0 total comparisons: defined as 1.0 (no evidence)
    assert sign_test(0, 0) == 1.0
    # symmetric: sign_test(a,b) == sign_test(b,a)
    assert sign_test(7, 20) == pytest.approx(sign_test(20, 7))


def test_sign_test_matches_scipy_binomtest():
    scipy_stats = pytest.importorskip("scipy.stats")
    for wins, losses in [(3, 17), (41, 59), (0, 12), (100, 5)]:
        expected = scipy_stats.binomtest(min(wins, losses), wins + losses, 0.5,
                                         alternative="two-sided").pvalue
        assert sign_test(wins, losses) == pytest.approx(expected, rel=1e-9)


def test_sign_test_numpy_int64_regression():
    """Regression (found 2026-07-11): 2 ** n with a numpy.int64 n silently
    overflows numpy's fixed-width integer instead of raising or using
    Python's arbitrary-precision ints, corrupting the result. A caller
    passing raw numpy.int64 (e.g. straight from `.sum()` on a boolean
    array, without an explicit int() cast) must still get a correct,
    non-garbage p-value -- sign_test() now casts internally."""
    arr = np.array([True] * 27 + [False] * 136)
    w = (arr == True).sum()   # noqa: E712 -- deliberately numpy.bool_/int64 path
    l = (arr == False).sum()  # noqa: E712
    assert isinstance(w, np.integer)
    p = sign_test(w, l)
    assert p < 1e-10, f"expected a tiny p-value for a 27/136 split, got {p}"
    assert p == sign_test(int(w), int(l))


def test_sign_test_large_n_no_overflow():
    """Even for a near-balanced but large sample, must not silently return
    a degenerate 1.0 or 0.0 from float overflow in 2 ** n."""
    p = sign_test(240, 260)
    assert 0.0 < p <= 1.0
    p2 = sign_test(np.int64(240), np.int64(260))
    assert p2 == pytest.approx(p)


# ---------------------------------------------------------------------------
# bootstrap_ci_mean
# ---------------------------------------------------------------------------

def test_bootstrap_ci_mean_contains_true_mean_and_is_ordered():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 2.5, 3.5])
    mean, lo, hi = bootstrap_ci_mean(values, n_boot=500, seed=0)
    assert mean == pytest.approx(values.mean())
    assert lo <= mean <= hi

def test_bootstrap_ci_mean_empty_and_nan_handling():
    assert all(np.isnan(x) for x in bootstrap_ci_mean(np.array([])))
    # all-NaN input behaves like empty
    assert all(np.isnan(x) for x in bootstrap_ci_mean(np.array([np.nan, np.nan])))
    # partial NaNs are dropped, not propagated
    mean, lo, hi = bootstrap_ci_mean(np.array([1.0, np.nan, 3.0]), n_boot=200, seed=1)
    assert mean == pytest.approx(2.0)


def test_bootstrap_ci_mean_deterministic_given_seed():
    values = np.array([1.0, 5.0, 3.0, 9.0, 2.0])
    a = bootstrap_ci_mean(values, n_boot=300, seed=42)
    b = bootstrap_ci_mean(values, n_boot=300, seed=42)
    assert a == b


# ---------------------------------------------------------------------------
# holm_correction
# ---------------------------------------------------------------------------

def test_holm_correction_known_example():
    # classic textbook check: p-values 0.01, 0.02, 0.03, 0.04, 0.05 with m=5.
    # Holm step-down (0-indexed): raw_adj_i = (m-i) * p_i, then cumulative max
    # (i=0): 5*0.01=0.05  (i=1): 4*0.02=0.08  (i=2): 3*0.03=0.09
    # (i=3): 2*0.04=0.08 -> monotone floor keeps it at 0.09
    # (i=4): 1*0.05=0.05 -> monotone floor keeps it at 0.09
    raw = {"a": 0.01, "b": 0.02, "c": 0.03, "d": 0.04, "e": 0.05}
    adj = holm_correction(raw)
    assert adj["a"] == pytest.approx(0.05)
    assert adj["b"] == pytest.approx(0.08)
    assert adj["c"] == pytest.approx(0.09)
    assert adj["d"] == pytest.approx(0.09)
    assert adj["e"] == pytest.approx(0.09)


def test_holm_correction_is_monotone_nondecreasing_in_sorted_order():
    raw = {"a": 0.5, "b": 0.001, "c": 0.2, "d": 0.001, "e": 0.9}
    adj = holm_correction(raw)
    ordered = sorted(raw.items(), key=lambda kv: kv[1])
    adjusted_in_order = [adj[k] for k, _ in ordered]
    assert adjusted_in_order == sorted(adjusted_in_order)
    assert all(0.0 <= v <= 1.0 for v in adj.values())


def test_holm_correction_never_less_than_raw_p():
    raw = {"a": 0.01, "b": 0.2, "c": 0.5}
    adj = holm_correction(raw)
    for k in raw:
        assert adj[k] >= raw[k] - 1e-12


# ---------------------------------------------------------------------------
# to_markdown (dependency-free, no tabulate)
# ---------------------------------------------------------------------------

def test_to_markdown_empty():
    assert to_markdown(pd.DataFrame()) == "*(no rows)*"


def test_to_markdown_basic_shape():
    df = pd.DataFrame({"method": ["boot_cold", "cpsat_cold"], "mean_pi": [0.01, 0.05]})
    md = to_markdown(df)
    lines = md.splitlines()
    assert lines[0] == "| method | mean_pi |"
    assert lines[1] == "| --- | --- |"
    assert "boot_cold" in lines[2]
    assert "0.0100" in lines[2]  # float formatted to 4 decimals


# ---------------------------------------------------------------------------
# write_latex_table -- every row before \midrule/\bottomrule ends with \\
# ---------------------------------------------------------------------------

def test_write_latex_table_row_endings(tmp_path):
    df = pd.DataFrame({"method": ["boot_cold"], "mean_pi": [0.0123]})
    out = tmp_path / "t.tex"
    write_latex_table(df, out, "caption", "tab:x", float_cols=["mean_pi"])
    text = out.read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if ln in (r"\midrule", r"\bottomrule") and i > 0:
            assert lines[i - 1].rstrip().endswith(r"\\")


def test_write_latex_table_escapes_underscores_and_percent():
    import tempfile
    df = pd.DataFrame({"method": ["fix_and_optimize_50"], "note": ["50%"]})
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "t.tex"
        write_latex_table(df, out, "cap", "lab")
        text = out.read_text()
        assert r"fix\_and\_optimize\_50" in text
        assert r"50\%" in text


# ---------------------------------------------------------------------------
# pairwise_vs_baseline -- end-to-end on a small synthetic dataframe with a
# KNOWN win/loss pattern, so the reported counts/p-value are checkable by hand.
# ---------------------------------------------------------------------------

def _synthetic_df(n=20, seed=0):
    """boot_cold beats cpsat_cold on primal_integral in exactly 15/20 paired
    instances (5 losses), constructed so the expected win/loss/tie counts and
    sign-test p-value are known in advance."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        common = dict(experiment_family="test", instance_size="10x10", stream_seed=i,
                     budget_s=5.0, workers=1, severity="medium", bootstrap_policy="append",
                     stream_step=0, status="ok", final_gap=0.0, fraction_moved_ops=0.1)
        cpsat_pi = 0.10
        # boot_cold strictly better (lower PI) on first 15, strictly worse on last 5
        boot_pi = cpsat_pi - 0.02 if i < 15 else cpsat_pi + 0.02
        rows.append({**common, "method": "cpsat_cold", "primal_integral": cpsat_pi})
        rows.append({**common, "method": "boot_cold", "primal_integral": boot_pi})
    return pd.DataFrame(rows)


def test_pairwise_vs_baseline_known_win_loss_counts():
    df = _synthetic_df()
    out = pairwise_vs_baseline(df, baseline="cpsat_cold")
    row = out[out.method == "boot_cold"].iloc[0]
    assert row.n_common == 20
    assert row.pi_win == 15
    assert row.pi_loss == 5
    assert row.pi_tie == 0
    assert row.sign_test_p == pytest.approx(sign_test(15, 5))
    # mean_pi_improvement = mean(cpsat_pi - boot_pi) = (15*0.02 - 5*0.02)/20 = 0.01
    assert row.mean_pi_improvement == pytest.approx(0.01, abs=1e-9)


def test_pairwise_vs_baseline_all_ties_gives_p_one():
    df = _synthetic_df()
    df.loc[df.method == "boot_cold", "primal_integral"] = 0.10  # force exact ties
    out = pairwise_vs_baseline(df, baseline="cpsat_cold")
    row = out[out.method == "boot_cold"].iloc[0]
    assert row.pi_tie == 20
    assert row.pi_win == 0 and row.pi_loss == 0
    assert row.sign_test_p == 1.0


def test_pairwise_vs_baseline_holm_column_present_and_bounded():
    df = _synthetic_df()
    out = pairwise_vs_baseline(df, baseline="cpsat_cold")
    assert "sign_test_p_holm" in out.columns
    assert (out["sign_test_p_holm"] >= out["sign_test_p"] - 1e-12).all()


# ---------------------------------------------------------------------------
# per_method_aggregate / breakdown_table -- basic shape + status filtering
# ---------------------------------------------------------------------------

def test_per_method_aggregate_excludes_errors_from_pi_but_counts_n_errors():
    df = _synthetic_df(n=5)
    df["optimality_proved"] = True
    df["bootstrap_time_ms"] = 1.0
    df["solution_feasible"] = True
    err_row = df.iloc[0].copy()
    err_row["status"] = "error"
    err_row["method"] = "boot_cold"
    df = pd.concat([df, pd.DataFrame([err_row])], ignore_index=True)
    agg = per_method_aggregate(df)
    boot_row = agg[agg.method == "boot_cold"].iloc[0]
    assert boot_row.n_errors == 1
    # n counts only status=="ok" rows in the groupby(...).agg path
    assert boot_row.n == 5


def test_breakdown_table_missing_column_returns_empty():
    df = _synthetic_df(n=3)
    assert breakdown_table(df, "nonexistent_column").empty


def test_breakdown_table_basic():
    df = _synthetic_df(n=10)
    df["delta_kind"] = ["arrival", "outage"] * 10
    bt = breakdown_table(df, "delta_kind")
    assert set(bt.columns) >= {"method", "delta_kind", "mean_pi", "n"}
    assert bt.n.sum() == 20  # both methods, both delta kinds
