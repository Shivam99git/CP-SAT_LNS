"""Unified ICAPS dynamic-job-shop experiment suite.

Wraps the existing runners/baselines/bootstrap policies behind one preset-
driven CLI with a single wide CSV schema (docs/icaps_experiment_plan.md
§14), resumability, and per-run failure isolation (one failing instance
does not abort the suite -- it is recorded with status="error" and the
suite continues).

Presets (exact grids from the task spec) are defined in PRESETS below.
`smoke` and `pilot` are sized to actually run in this session; `main`,
`ablation`, `severity`, `workers`, `budgets`, `arrivals` are fully wired and
validated via --dry-run, but are NOT executed here -- their compute cost
(e.g. `main`: 4 sizes x 30 seeds x 4 budgets x 2 worker counts x 10 methods
x 20-instance streams) is appropriately an unattended multi-day run, and the
task's own Execution Order (§17) places them "only after smoke/pilot are
correct."

Usage:
    .venv/bin/python -m phase0.run_icaps_jssp_suite --preset smoke
    .venv/bin/python -m phase0.run_icaps_jssp_suite --preset pilot --out-dir results/icaps/pilot
    .venv/bin/python -m phase0.run_icaps_jssp_suite --preset main --dry-run
"""

from __future__ import annotations

import argparse
import getpass
import json
import platform
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import baselines as bl
from . import bootstrap_policies as bp
from .harness import cpsat_default_solve, warm_bootstrap_solve
from .metrics import (
    bootstrap_gap,
    final_gap,
    fraction_moved_operations,
    machine_order_distance,
    max_abs_start_shift,
    mean_abs_start_shift,
    median_abs_start_shift,
    num_moved_operations,
    primal_integral,
    time_to_first_feasible,
    time_to_gap_threshold,
)
from .model_builder import Solution, validate_solution
from .streams import Instance, StreamConfig, generate_stream

try:
    import ortools

    ORTOOLS_VERSION = ortools.__version__
except Exception:
    ORTOOLS_VERSION = "unknown"


# ---------------------------------------------------------------------------
# CSV schema (docs/icaps_experiment_plan.md §14 / task spec §14)
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    # general
    "domain", "experiment_family", "benchmark_name", "instance_size",
    "base_seed", "stream_seed", "method", "bootstrap_policy", "objective",
    "budget_s", "workers", "stream_step", "delta_kind", "severity",
    "status", "error_message",
    # objective/quality
    "objective_value", "best_known", "final_gap", "primal_integral",
    "optimality_proved", "best_bound", "solver_status",
    # timing
    "total_wall_time_s", "bootstrap_time_ms", "solver_time_s",
    "time_to_first_feasible_s", "time_to_10pct_gap_s", "time_to_5pct_gap_s",
    "time_to_1pct_gap_s",
    # bootstrap
    "has_previous_solution", "bootstrap_objective", "bootstrap_gap",
    "bootstrap_feasible",
    # stability
    "num_common_ops", "num_moved_ops", "fraction_moved_ops",
    "mean_abs_start_shift", "median_abs_start_shift", "max_abs_start_shift",
    "machine_order_distance", "frozen_violation_count",
    # validation
    "solution_feasible", "validation_error",
    # metadata
    "ortools_version", "python_version", "git_commit", "hostname",
    "timestamp_utc",
]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent.parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "NA"


def _metadata_row_fields() -> dict:
    return {
        "ortools_version": ORTOOLS_VERSION,
        "python_version": platform.python_version(),
        "git_commit": _git_commit(),
        "hostname": socket.gethostname(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Method registry: name -> callable(instance, prev_solution, budget, workers,
# seed, bootstrap_policy) -> SolveResult-like object (duck-typed: needs
# .objective, .solution, .trajectory, .initial_objective, .bootstrap_time_s,
# .solver_time_s, .proven_optimal)
# ---------------------------------------------------------------------------

FIXED_ARM_LNS = ("random_25", "delta_25", "critical_25", "outage_window_25")


def _floor_fn_for_policy(policy: str):
    if policy in bp.FLOOR_POLICIES:
        return bp.FLOOR_POLICIES[policy]
    return None  # default (append)


def run_method(name: str, instance: Instance, prev_solution: Solution | None,
               budget: float, workers: int, seed: int, bootstrap_policy: str = "append"):
    if name == "cpsat_cold":
        return cpsat_default_solve(instance, budget, prev_solution=None,
                                   workers=workers, seed=seed, method_name=name)
    if name == "cpsat_warm":
        return cpsat_default_solve(instance, budget, prev_solution=prev_solution,
                                   workers=workers, seed=seed, method_name=name)
    if name == "boot_cold":
        return warm_bootstrap_solve(instance, budget, prev_solution=prev_solution,
                                    workers=workers, seed=seed, use_hint=False,
                                    method_name=name, floor_fn=_floor_fn_for_policy(bootstrap_policy))
    if name == "boot_warm":
        return warm_bootstrap_solve(instance, budget, prev_solution=prev_solution,
                                    workers=workers, seed=seed, use_hint=True,
                                    method_name=name, floor_fn=_floor_fn_for_policy(bootstrap_policy))
    if name == "repair_only":
        return bl.repair_only(instance, prev_solution, seed=seed)
    if name == "greedy_from_scratch":
        return bl.greedy_from_scratch(instance, seed=seed)
    if name in bl.DISPATCH_RULES:
        return bl.run_dispatch_baseline(name, instance, seed=seed)
    if name == "repair_plus_solver_no_floor":
        return bl.repair_plus_solver_no_floor(instance, budget, prev_solution,
                                              workers=workers, seed=seed)
    if name.startswith("fix_and_optimize_"):
        frac = int(name.rsplit("_", 1)[1]) / 100.0
        return bl.fix_and_optimize(instance, budget, prev_solution, freeze_frac=frac,
                                   workers=workers, seed=seed)
    if name == "lns_prev_solution":
        return bl.lns_prev_solution(instance, budget, prev_solution,
                                    workers=workers, seed=seed, arm_names=FIXED_ARM_LNS)
    if name == "local_branching_prev":
        return bl.local_branching_prev(instance, budget, prev_solution,
                                       workers=workers, seed=seed)
    if name == "micro_repair_cp":
        return bl.micro_repair_cp(instance, budget, prev_solution, workers=workers, seed=seed)
    if name == "prev_raw":
        result, feasible = bl.prev_raw(instance, prev_solution, seed=seed, on_infeasible="flag")
        return result
    raise ValueError(f"unknown method {name!r}")


ALL_METHODS = (
    "cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm",
    "repair_only", "greedy_from_scratch",
    "dispatch_spt", "dispatch_lpt", "dispatch_mwkr", "dispatch_fifo", "dispatch_random",
    "repair_plus_solver_no_floor",
    "fix_and_optimize_25", "fix_and_optimize_50", "fix_and_optimize_75",
    "lns_prev_solution", "local_branching_prev", "micro_repair_cp", "prev_raw",
)


# ---------------------------------------------------------------------------
# Presets (task spec §15, exact grids)
# ---------------------------------------------------------------------------

@dataclass
class Preset:
    sizes: list[tuple[int, int]]              # (machines, jobs) pairs
    seeds: list[int]
    stream_length: int
    budgets: list[float]
    workers_list: list[int]
    methods: list[str]
    delta_kinds: list[str] | None              # None = default weighted mix
    severities: list[str]
    bootstrap_policies: list[str] = field(default_factory=lambda: ["append"])


PRESETS: dict[str, Preset] = {
    "smoke": Preset(
        sizes=[(5, 5)], seeds=[1], stream_length=3, budgets=[0.2], workers_list=[1],
        methods=["cpsat_cold", "boot_cold", "repair_only", "greedy_from_scratch"],
        delta_kinds=["arrival", "cancellation", "duration_jitter", "outage"],
        severities=["low"],
    ),
    "pilot": Preset(
        sizes=[(10, 10), (15, 15)], seeds=[1, 2, 3], stream_length=5,
        budgets=[1, 5, 10], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm", "repair_only",
                 "dispatch_spt", "dispatch_mwkr"],
        delta_kinds=["arrival", "cancellation", "duration_jitter", "outage"],
        severities=["medium"],
    ),
    "main": Preset(
        sizes=[(10, 10), (15, 15), (20, 20), (30, 20)], seeds=list(range(21, 51)),
        stream_length=20, budgets=[0.5, 1, 5, 10], workers_list=[1, 8],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm", "repair_only",
                 "greedy_from_scratch", "dispatch_spt", "dispatch_mwkr",
                 "fix_and_optimize_50", "lns_prev_solution"],
        delta_kinds=None, severities=["low", "medium", "high"],
    ),
    "ablation": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(11, 21)), stream_length=10,
        budgets=[1, 5, 10], workers_list=[1],
        methods=["cpsat_cold", "prev_raw", "repair_only", "repair_plus_solver_no_floor",
                 "boot_cold", "boot_warm"],
        delta_kinds=["arrival", "cancellation", "duration_jitter", "outage"],
        severities=["medium"],
    ),
    "severity": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(11, 21)), stream_length=10,
        budgets=[5], workers_list=[1],
        methods=["cpsat_cold", "boot_cold", "repair_only"],
        delta_kinds=["arrival", "batch_arrival", "cancellation", "duration_jitter",
                    "outage", "machine_speed_degradation", "rush_job"],
        severities=["low", "medium", "high", "extreme"],
    ),
    "workers": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(11, 21)), stream_length=10,
        budgets=[1, 5, 10], workers_list=[1, 4, 8, 16],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm", "repair_only"],
        delta_kinds=None, severities=["medium"],
    ),
    "budgets": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(11, 21)), stream_length=10,
        budgets=[0.1, 0.5, 1, 2, 5, 10, 30], workers_list=[1, 8],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm", "repair_only"],
        delta_kinds=None, severities=["medium"],
    ),
    "arrivals": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(11, 21)), stream_length=10,
        budgets=[1, 5, 10], workers_list=[1],
        methods=["cpsat_cold", "boot_cold"],
        delta_kinds=["arrival", "batch_arrival", "rush_job"],
        severities=["low", "medium", "high", "extreme"],
        bootstrap_policies=["append", "gap_insert", "regret_insert", "beam_insert"],
    ),
    "heldout": Preset(
        sizes=[(15, 15), (20, 20)], seeds=list(range(21, 51)), stream_length=20,
        budgets=[1, 5, 10], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["low", "medium", "high"],
    ),
    # Redesigned "main comparison table" for the full ICAPS paper
    # (docs/icaps_full_paper_plan.md Phase C.1). NOT the original oversized
    # `main` preset (28,800 stream-runs, full factorial across every axis at
    # once) -- this holds budget/workers/severity at one representative value
    # and lets budget/worker/severity sensitivity be covered by the separate
    # `budgets`/`workers`/`severity` presets instead, which is both cheaper
    # and statistically cleaner than sweeping every axis simultaneously.
    "paper_main": Preset(
        sizes=[(10, 10), (15, 15), (20, 20)], seeds=list(range(101, 116)),  # 15 seeds
        stream_length=10, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm", "repair_only",
                 "dispatch_spt", "dispatch_mwkr", "fix_and_optimize_50",
                 "lns_prev_solution", "local_branching_prev"],
        delta_kinds=None, severities=["medium"],
    ),
    # Real OR-Library instances (docs/icaps_full_paper_plan.md Phase B). Used
    # only via --benchmark-dir/--benchmark-file, which replaces `sizes` with
    # the loaded instances -- `sizes` here is a placeholder and ignored.
    "real_benchmarks": Preset(
        sizes=[(0, 0)], seeds=list(range(1, 7)),  # 6 seeds
        stream_length=8, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["medium"],
    ),
    # Taillard (1993) real job-shop instances (docs/icaps_full_paper_plan.md
    # follow-up: petrvilim.github.io/optalcp-website benchmark set, via
    # ScheduleOpt/benchmarks). ta01-ta20: 15x15/20x15, meaningfully larger
    # than real_benchmarks' OR-Library set (max 20x10). Used only via
    # --benchmark-dir, which replaces `sizes` with the loaded instances.
    "taillard_benchmarks": Preset(
        sizes=[(0, 0)], seeds=list(range(1, 5)),  # 4 seeds
        stream_length=6, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["medium"],
    ),
    # Additional real job-shop families from ScheduleOpt/benchmarks, used via
    # --benchmark-dir tests/fixtures/benchmarks_real/{dmu,swv,yn}. Same shape
    # as taillard_benchmarks; separate preset names so each writes its own
    # {family}.csv instead of colliding on taillard_benchmarks.csv.
    "dmu_benchmarks": Preset(
        sizes=[(0, 0)], seeds=list(range(1, 5)),
        stream_length=6, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["medium"],
    ),
    "swv_benchmarks": Preset(
        sizes=[(0, 0)], seeds=list(range(1, 5)),
        stream_length=6, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["medium"],
    ),
    "yn_benchmarks": Preset(
        sizes=[(0, 0)], seeds=list(range(1, 5)),
        stream_length=6, budgets=[8], workers_list=[1],
        methods=["cpsat_cold", "cpsat_warm", "boot_cold", "boot_warm"],
        delta_kinds=None, severities=["medium"],
    ),
}


# ---------------------------------------------------------------------------
# Run key (for --resume / --skip-existing) and stream-level execution
# ---------------------------------------------------------------------------

def _run_key(family, size_label, seed, method, bootstrap_policy, budget, workers, severity):
    return (family, size_label, seed, method, bootstrap_policy, budget, workers, severity)


def _stability_fields(instance: Instance, prev_solution: Solution | None,
                      solution: Solution | None) -> dict:
    if prev_solution is None or solution is None:
        return {}
    common = sorted(set(prev_solution) & set(solution))
    if not common:
        return {"num_common_ops": 0}
    return {
        "num_common_ops": len(common),
        "num_moved_ops": num_moved_operations(prev_solution, solution, common),
        "fraction_moved_ops": fraction_moved_operations(prev_solution, solution, common),
        "mean_abs_start_shift": mean_abs_start_shift(prev_solution, solution, common),
        "median_abs_start_shift": median_abs_start_shift(prev_solution, solution, common),
        "max_abs_start_shift": max_abs_start_shift(prev_solution, solution, common),
        "machine_order_distance": machine_order_distance(instance, prev_solution, solution, common),
    }


def _run_stream_for_method(
    method: str, stream: list[Instance], budget: float, workers: int, seed: int,
    bootstrap_policy: str, family: str, size_label: str, base_seed: int,
    stream_seed: int, meta: dict, benchmark_name: str = "",
) -> list[dict]:
    rows = []
    prev: Solution | None = None
    for inst in stream:
        row = {
            "domain": "jssp", "experiment_family": family, "benchmark_name": benchmark_name,
            "instance_size": size_label, "base_seed": base_seed, "stream_seed": stream_seed,
            "method": method, "bootstrap_policy": bootstrap_policy, "objective": "makespan",
            "budget_s": budget, "workers": workers, "stream_step": inst.index,
            "delta_kind": inst.delta_kind, "severity": inst.severity,
            "status": "ok", "error_message": "",
            **meta,
        }
        t0 = time.monotonic()
        try:
            res = run_method(method, inst, prev, budget, workers, seed, bootstrap_policy)
            wall = time.monotonic() - t0
            feasible, verr = True, ""
            if res.solution is not None:
                try:
                    mk = validate_solution(inst, res.solution)
                    feasible = (mk == res.objective)
                    if not feasible:
                        verr = f"makespan mismatch: validator={mk} reported={res.objective}"
                except AssertionError as e:
                    feasible, verr = False, str(e)

            row.update({
                "objective_value": res.objective, "optimality_proved": bool(res.proven_optimal),
                "solver_status": "FEASIBLE" if res.objective is not None else "NO_SOLUTION",
                "total_wall_time_s": wall,
                "bootstrap_time_ms": (res.bootstrap_time_s or 0.0) * 1000.0,
                "solver_time_s": res.solver_time_s if res.solver_time_s is not None else "",
                "time_to_first_feasible_s": time_to_first_feasible(res.trajectory),
                "has_previous_solution": prev is not None,
                "bootstrap_objective": res.initial_objective,
                "solution_feasible": feasible, "validation_error": verr,
                "_traj": res.trajectory,
            })
            row.update(_stability_fields(inst, prev, res.solution))
            if res.solution is not None:
                prev = res.solution
        except Exception as e:  # noqa: BLE001 -- must never crash the suite
            row.update({"status": "error", "error_message": f"{type(e).__name__}: {e}",
                       "objective_value": None, "solution_feasible": False, "_traj": []})
        rows.append(row)

    # second pass: primal_integral/final_gap/thresholds need best_known, which
    # requires knowing other methods' results too -- filled in by the caller
    # after all methods for this stream have run (see main()).
    return rows


# ---------------------------------------------------------------------------
# Per-stream-config unit of work (self-contained: builds its own stream, runs
# every requested method, computes its own best_known, and returns fully
# finalized rows). This is the granularity at which the suite parallelizes --
# each config is independent because best_known is scoped to a single stream.
# ---------------------------------------------------------------------------

@dataclass
class _ConfigTask:
    family: str
    size_label: str
    machines: int
    jobs: int
    seed: int
    budget: float
    workers: int
    severity: str
    bpolicy: str
    methods: list[str]          # methods still to run (post skip-existing filter)
    stream_length: int
    delta_kinds: list[str] | None
    run_seed: int
    meta: dict
    base_instance: Instance | None = None  # if set, stream is built on top of
                                            # this real benchmark instance
                                            # instead of a random base
    benchmark_name: str = ""


def _process_stream_config(task: _ConfigTask) -> dict:
    """Run every requested method for one stream config and finalize its rows.

    Self-contained and side-effect-free (returns rows; writes nothing). Safe to
    call in a worker process. Identical output whether called sequentially or
    via a pool because best_known is computed only from this config's own runs.
    """
    if task.base_instance is not None:
        cfg = StreamConfig(num_machines=task.machines, initial_jobs=task.jobs,
                           stream_length=task.stream_length, seed=task.seed,
                           severity=task.severity)
        if task.delta_kinds is not None:
            for field_name in ("p_arrival", "p_cancellation", "p_duration_jitter", "p_outage",
                              "p_batch_arrival", "p_rush_job", "p_machine_speed_degradation",
                              "p_due_date_change", "p_priority_change", "p_partial_schedule_freeze"):
                setattr(cfg, field_name, 0.0)
            for kind in task.delta_kinds:
                setattr(cfg, f"p_{kind}", 1.0)
        stream = generate_stream(cfg, base_instance=task.base_instance)
    else:
        stream = _build_stream(task.family, task.machines, task.jobs, task.seed,
                               task.stream_length, task.severity, task.delta_kinds)

    stream_by_method: dict[str, list[dict]] = {}
    for method in task.methods:
        stream_by_method[method] = _run_stream_for_method(
            method, stream, task.budget, task.workers, task.run_seed, task.bpolicy,
            task.family, task.size_label, task.seed, task.seed, task.meta,
            benchmark_name=task.benchmark_name,
        )

    # best_known per stream_step across all methods run for THIS stream
    best_known: dict[int, float] = {}
    for rows in stream_by_method.values():
        for r in rows:
            if r["status"] == "ok" and r["objective_value"] is not None:
                step = r["stream_step"]
                if step not in best_known or r["objective_value"] < best_known[step]:
                    best_known[step] = r["objective_value"]

    finalized: list[dict] = []
    n_error = 0
    for rows in stream_by_method.values():
        for r in rows:
            if r["status"] == "error":
                n_error += 1
            bk = best_known.get(r["stream_step"])
            r["best_known"] = bk
            traj = r.pop("_traj", [])
            if r["status"] == "ok" and bk is not None and r["objective_value"] is not None and bk > 0:
                r["final_gap"] = max(0.0, (r["objective_value"] - bk) / bk)
                r["bootstrap_gap"] = bootstrap_gap(r.get("bootstrap_objective"), bk)
                r["primal_integral"] = primal_integral(traj, bk, r["budget_s"])
                r["time_to_10pct_gap_s"] = time_to_gap_threshold(traj, bk, 0.10)
                r["time_to_5pct_gap_s"] = time_to_gap_threshold(traj, bk, 0.05)
                r["time_to_1pct_gap_s"] = time_to_gap_threshold(traj, bk, 0.01)
            finalized.append(r)

    return {
        "rows": finalized,
        "n_methods": len(stream_by_method),
        "n_error": n_error,
        "label": (f"{task.size_label} seed={task.seed} budget={task.budget} "
                  f"workers={task.workers} severity={task.severity} bpolicy={task.bpolicy}"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_stream(family: str, machines: int, jobs: int, seed: int, stream_length: int,
                  severity: str, delta_kinds: list[str] | None) -> list[Instance]:
    cfg = StreamConfig(num_machines=machines, initial_jobs=jobs,
                       stream_length=stream_length, seed=seed, severity=severity)
    cfg.ops_per_job = (machines, machines)
    cfg.duration_range = (5, 50)
    if delta_kinds is not None:
        # zero out all weights, then set requested kinds to uniform weight
        for field_name in ("p_arrival", "p_cancellation", "p_duration_jitter", "p_outage",
                          "p_batch_arrival", "p_rush_job", "p_machine_speed_degradation",
                          "p_due_date_change", "p_priority_change", "p_partial_schedule_freeze"):
            setattr(cfg, field_name, 0.0)
        for kind in delta_kinds:
            setattr(cfg, f"p_{kind}", 1.0)
    return generate_stream(cfg)


def _resolve_config(args) -> Preset:
    if args.preset:
        base = PRESETS[args.preset]
    else:
        base = Preset(sizes=[(15, 15)], seeds=[1], stream_length=10, budgets=[5],
                     workers_list=[1], methods=list(ALL_METHODS), delta_kinds=None,
                     severities=["medium"])
    cfg = Preset(**{**base.__dict__})
    if args.sizes:
        cfg.sizes = [tuple(map(int, s.split("x"))) for s in args.sizes]
    if args.seeds:
        cfg.seeds = args.seeds
    if args.stream_length is not None:
        cfg.stream_length = args.stream_length
    if args.budgets:
        cfg.budgets = args.budgets
    if args.workers_list:
        cfg.workers_list = args.workers_list
    if args.methods:
        cfg.methods = args.methods
    if args.delta_kinds:
        cfg.delta_kinds = args.delta_kinds
    if args.severity_levels:
        cfg.severities = args.severity_levels
    if args.bootstrap_policy:
        cfg.bootstrap_policies = [args.bootstrap_policy]
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preset", choices=list(PRESETS), default=None)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--sizes", nargs="+", default=None, help='e.g. 15x15 20x20')
    ap.add_argument("--stream-length", type=int, default=None)
    ap.add_argument("--num-streams", type=int, default=None,
                    help="alias: caps len(seeds) if fewer streams desired")
    ap.add_argument("--budgets", type=float, nargs="+", default=None)
    ap.add_argument("--workers-list", type=int, nargs="+", default=None)
    ap.add_argument("--methods", nargs="+", default=None)
    ap.add_argument("--delta-kinds", nargs="+", default=None)
    ap.add_argument("--severity-levels", nargs="+", default=None)
    ap.add_argument("--benchmark-dir", default=None)
    ap.add_argument("--benchmark-file", default=None)
    ap.add_argument("--bootstrap-policy", default=None)
    ap.add_argument("--objective", default="makespan", choices=["makespan"],
                    help="only makespan is wired for the JSSP suite runner; "
                         "due-date fields exist on Job but tardiness objective "
                         "wiring is a documented TODO (see docs/icaps_experiment_plan.md)")
    ap.add_argument("--out-dir", default="results/icaps/runs")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--max-instances", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--run-seed", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=1,
                    help="number of worker processes across independent stream "
                         "configs (default 1 = sequential). Each config's methods "
                         "run sequentially within one worker. For workers>1 CP-SAT "
                         "jobs, keep parallel*workers <= physical cores to avoid "
                         "oversubscription biasing wall-clock budgets.")
    args = ap.parse_args()

    family = args.preset or "custom"
    cfg = _resolve_config(args)
    if args.num_streams:
        cfg.seeds = cfg.seeds[: args.num_streams]

    # Real benchmark instances (docs/icaps_full_paper_plan.md Phase B): each
    # loaded instance stands in for one "size" -- deltas are applied on top of
    # it (generate_stream(base_instance=...)) instead of a randomly-generated
    # base, so the rest of the pipeline (methods, resumability, CSV schema,
    # analysis) is unchanged.
    benchmark_instances: list[tuple[str, Instance]] = []
    if args.benchmark_file:
        from .benchmark_loaders import load_benchmark_file
        p = Path(args.benchmark_file)
        benchmark_instances.append((p.stem, load_benchmark_file(p)))
    if args.benchmark_dir:
        from .benchmark_loaders import _LOADERS, load_benchmark_file
        d = Path(args.benchmark_dir)
        for p in sorted(d.iterdir()):
            if p.suffix.lower() in _LOADERS:
                benchmark_instances.append((p.stem, load_benchmark_file(p)))
        if not benchmark_instances:
            raise ValueError(f"no loadable benchmark files found in {d}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{family}.csv"

    # plan enumeration
    plan = []
    if benchmark_instances:
        for (name, inst) in benchmark_instances:
            m, j = inst.num_machines, len(inst.jobs)
            size_label = f"{name}_{j}x{m}"
            for seed in cfg.seeds:
                for budget in cfg.budgets:
                    for workers in cfg.workers_list:
                        for severity in cfg.severities:
                            for bpolicy in cfg.bootstrap_policies:
                                plan.append((size_label, m, j, seed, budget, workers,
                                            severity, bpolicy, name, inst))
    else:
        for (m, j) in cfg.sizes:
            size_label = f"{m}x{j}"
            for seed in cfg.seeds:
                for budget in cfg.budgets:
                    for workers in cfg.workers_list:
                        for severity in cfg.severities:
                            for bpolicy in cfg.bootstrap_policies:
                                plan.append((size_label, m, j, seed, budget, workers,
                                            severity, bpolicy, "", None))
    if args.max_instances:
        plan = plan[: args.max_instances]

    print(f"family={family} planned stream configs: {len(plan)}, "
          f"methods={cfg.methods}, sizes={cfg.sizes}, budgets={cfg.budgets}, "
          f"workers={cfg.workers_list}, severities={cfg.severities}")

    if args.dry_run:
        for p in plan:
            print("  would run:", dict(zip(
                ("size", "machines", "jobs", "seed", "budget", "workers", "severity",
                 "bootstrap_policy", "benchmark_name"), p[:9])))
            for method in cfg.methods:
                print(f"    method={method}")
        print(f"\ntotal stream-runs: {len(plan) * len(cfg.methods)}")
        return

    existing_keys: set = set()
    existing_rows: list[dict] = []
    if args.resume and out_csv.exists():
        prior = pd.read_csv(out_csv)
        existing_rows = prior.to_dict("records")
        for _, r in prior.iterrows():
            existing_keys.add(_run_key(r.experiment_family, r.instance_size, r.stream_seed,
                                       r.method, r.bootstrap_policy, r.budget_s, r.workers,
                                       r.severity))
        print(f"resuming: {len(existing_keys)} stream-runs already in {out_csv}")

    # validate-only: cheap solvability check per stream, no methods run, no CSV.
    if args.validate_only:
        from .model_builder import build_model, solve
        for (size_label, m, j, seed, budget, workers, severity, bpolicy, bname, binst) in plan:
            if binst is not None:
                stream = generate_stream(
                    StreamConfig(num_machines=m, initial_jobs=j, stream_length=cfg.stream_length,
                                seed=seed, severity=severity),
                    base_instance=binst,
                )
            else:
                stream = _build_stream(family, m, j, seed, cfg.stream_length, severity, cfg.delta_kinds)
            for inst in stream:
                sol, obj, _status = solve(build_model(inst), time_limit=0.5)
                ok = sol is not None
                print(f"  validate-only {size_label} seed={seed} step={inst.index} "
                      f"({inst.delta_kind}): {'OK' if ok else 'NO SOLUTION IN 0.5s'}")
        print("\nvalidate-only run complete, no CSV written")
        return

    all_rows: list[dict] = list(existing_rows)
    meta = _metadata_row_fields()
    n_run = n_skip = n_error = 0

    # Build the task list, applying the skip-existing filter up front so each
    # task carries only the methods that still need to run.
    tasks: list[_ConfigTask] = []
    for (size_label, m, j, seed, budget, workers, severity, bpolicy, bname, binst) in plan:
        methods_to_run = []
        for method in cfg.methods:
            key = _run_key(family, size_label, seed, method, bpolicy, budget, workers, severity)
            if args.skip_existing and key in existing_keys:
                n_skip += 1
            else:
                methods_to_run.append(method)
        if not methods_to_run:
            continue
        tasks.append(_ConfigTask(
            family=family, size_label=size_label, machines=m, jobs=j, seed=seed,
            budget=budget, workers=workers, severity=severity, bpolicy=bpolicy,
            methods=methods_to_run, stream_length=cfg.stream_length,
            delta_kinds=cfg.delta_kinds, run_seed=args.run_seed, meta=meta,
            base_instance=binst, benchmark_name=bname,
        ))

    def _write_checkpoint() -> pd.DataFrame:
        df = pd.DataFrame(all_rows)
        for col in CSV_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[CSV_COLUMNS]
        # write-to-temp-then-rename: never leaves out_csv half-written if the
        # process is killed mid-write.
        tmp = out_csv.with_suffix(out_csv.suffix + ".tmp")
        df.to_csv(tmp, index=False)
        tmp.replace(out_csv)
        return df

    def _consume(result: dict) -> None:
        nonlocal n_run, n_error
        all_rows.extend(result["rows"])
        n_run += result["n_methods"]
        n_error += result["n_error"]
        print(f"  {result['label']}: {result['n_methods']} methods done"
              + (f" ({result['n_error']} error rows)" if result["n_error"] else ""))
        # Checkpoint after every completed stream config so a crash/kill
        # partway through a long (--parallel) campaign loses at most the
        # in-flight configs, not the whole run. --resume --skip-existing
        # picks up from here on restart.
        _write_checkpoint()

    if args.parallel and args.parallel > 1 and len(tasks) > 1:
        import multiprocessing as mp
        nproc = min(args.parallel, len(tasks))
        print(f"running {len(tasks)} stream configs across {nproc} worker processes")
        # 'spawn' would re-import cleanly but 'fork' (Linux default) inherits the
        # already-imported ortools/pandas state -- faster startup, and each task
        # is side-effect-free so there's no shared-state hazard.
        ctx = mp.get_context("fork")
        with ctx.Pool(processes=nproc) as pool:
            for result in pool.imap_unordered(_process_stream_config, tasks):
                _consume(result)
    else:
        for task in tasks:
            _consume(_process_stream_config(task))

    df = _write_checkpoint()

    meta_path = out_dir / f"{family}_metadata.json"
    meta_path.write_text(json.dumps({
        "command": " ".join(sys.argv), **meta, "preset": family,
        "n_stream_runs": n_run, "n_skipped": n_skip, "n_errors": n_error,
        "n_rows": len(df),
    }, indent=2))

    print(f"\nwrote {out_csv} ({len(df)} rows) and {meta_path}")
    print(f"stream-runs: {n_run} executed, {n_skip} skipped (resume), {n_error} rows with errors")
    if n_error:
        print("  (errors are recorded per-row with status='error'; suite did not abort)")


if __name__ == "__main__":
    main()
