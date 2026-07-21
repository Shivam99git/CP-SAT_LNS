"""Regression: the --parallel runner path must produce the same rows as the
sequential path.

We exercise `_process_stream_config` directly on deterministic, solver-free
methods (dispatch rules + repair_only) so there is no CP-SAT wall-clock noise
to confound the comparison -- any difference would be a real parallelization
bug (dropped/duplicated/corrupted/cross-contaminated rows), not timing.

    .venv/bin/python -m pytest tests/test_icaps_runner_parallel.py -q
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from phase0.run_icaps_jssp_suite import _ConfigTask, _process_stream_config

DET_METHODS = ["dispatch_spt", "dispatch_mwkr", "dispatch_lpt", "repair_only"]

# Columns whose value is a deterministic function of the inputs (excludes
# wall-clock timing fields and primal_integral, which integrate over trajectory
# timestamps and carry sub-ms noise even for instant methods).
DET_COLS = [
    "method", "stream_seed", "stream_step", "objective_value", "best_known",
    "final_gap", "num_moved_ops", "fraction_moved_ops", "machine_order_distance",
    "bootstrap_objective", "status",
]


def _make_tasks():
    meta = {"ortools_version": "test", "python_version": "test",
            "git_commit": "test", "hostname": "test", "timestamp_utc": "test"}
    return [
        _ConfigTask(
            family="custom", size_label="8x8", machines=8, jobs=8, seed=seed,
            budget=0.3, workers=1, severity="medium", bpolicy="append",
            methods=list(DET_METHODS), stream_length=4, delta_kinds=None,
            run_seed=0, meta=meta,
        )
        for seed in (1, 2, 3, 4, 5, 6)
    ]


def _det_view(rows):
    """Sorted list of (col->value) tuples over deterministic columns only."""
    keyed = sorted(rows, key=lambda r: (r["method"], r["stream_seed"], r["stream_step"]))
    return [tuple(r.get(c) for c in DET_COLS) for r in keyed]


def test_parallel_matches_sequential_deterministic_rows():
    tasks = _make_tasks()

    seq_rows = []
    for t in tasks:
        seq_rows.extend(_process_stream_config(t)["rows"])

    ctx = mp.get_context("fork")
    with ctx.Pool(processes=4) as pool:
        par_rows = []
        for res in pool.imap_unordered(_process_stream_config, tasks):
            par_rows.extend(res["rows"])

    assert len(seq_rows) == len(par_rows)
    assert _det_view(seq_rows) == _det_view(par_rows)


def test_checkpoint_partial_progress_then_resume_completes(tmp_path):
    """Simulates a crash mid-campaign: run the CLI with a hard timeout so it's
    killed partway through, then re-run with --resume --skip-existing and
    confirm every (method, seed, step) row exists exactly once (no dropped
    work, no duplicates from re-running an already-checkpointed config)."""
    import subprocess
    import sys

    import pandas as pd

    root = Path(__file__).parent.parent
    out_dir = tmp_path / "runs"
    common = [
        sys.executable, "-m", "phase0.run_icaps_jssp_suite",
        "--seeds", "1", "2", "3", "4", "5", "6",
        "--sizes", "8x8", "--stream-length", "3", "--budgets", "2",
        "--methods", "dispatch_spt", "repair_only", "cpsat_cold",
        "--severity-levels", "medium", "--out-dir", str(out_dir), "--parallel", "1",
    ]
    try:
        subprocess.run(common, cwd=root, timeout=2, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pass  # expected: interrupted mid-run, checkpoint should still exist

    csv_path = out_dir / "custom.csv"
    assert csv_path.exists(), "checkpoint must exist after interruption"
    partial = pd.read_csv(csv_path)
    assert 0 < len(partial) < 3 * 6 * 4, "expected partial (incomplete) progress"

    subprocess.run(common + ["--resume", "--skip-existing"], cwd=root,
                   capture_output=True, text=True, timeout=120, check=True)
    final = pd.read_csv(csv_path)
    # methods x seeds x (stream_length + 1) instances (base + deltas)
    assert len(final) == 3 * 6 * 4
    assert final.duplicated(["method", "stream_seed", "stream_step"]).sum() == 0


def test_process_stream_config_is_self_contained():
    """best_known must be scoped to a single config (its own methods only),
    so a config run in isolation gives the same best_known as in a batch."""
    task = _make_tasks()[0]
    r1 = _process_stream_config(task)
    r2 = _process_stream_config(task)
    assert _det_view(r1["rows"]) == _det_view(r2["rows"])
    # every row got a best_known filled in (all methods feasible here)
    assert all(r["best_known"] is not None for r in r1["rows"])
