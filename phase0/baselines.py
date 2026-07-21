"""ICAPS baseline methods for dynamic job-shop reoptimization.

Every function here returns the existing `harness.SolveResult`, uses the
existing `model_builder.build_model`/`solve`/`validate_solution` primitives,
and follows the same fairness contract as `cpsat_cold`/`boot_cold`: one
total wall-clock budget, one solver seed, one worker count, no hidden
advantage. Feasibility validation of the returned solution is the CALLER's
responsibility (consistent with every existing runner in this repo), not
done inside these functions.

Method families implemented (see docs/icaps_experiment_plan.md §6 for the
mapping to the task spec):

  Floor-only / no-reuse:
    repair_only(...)             -- bootstrap floor, no CP-SAT after it
    greedy_from_scratch(...)     -- dispatch-rule construction, ignores history
    dispatch_*(...)              -- 5 priority-dispatch rules (spt/lpt/mwkr/fifo/random)

  Reuse-mechanism comparisons:
    prev_raw(...)                -- naive direct reuse (usually infeasible -- the point)
    repair_plus_solver_no_floor(...) -- floor built and discarded (isolates the pocket effect)
    fix_and_optimize(...)        -- exact-freeze a fraction of ops, reoptimize the rest
    lns_prev_solution(...)       -- destroy/repair rounds seeded from the floor
    local_branching_prev(...)    -- CP-SAT + an approximate "few ops may move" constraint
    micro_repair_cp(...)         -- tiny CP-SAT repair of only touched ops, used as floor
"""

from __future__ import annotations

import random
import time

from .harness import (
    ARMS,
    RoundLog,
    SolveResult,
    list_schedule_bootstrap,
    select_destroy_set,
)
from .model_builder import Solution, build_model, solve
from .streams import Instance

# ---------------------------------------------------------------------------
# Dispatch-rule scheduling (solver-free, feasible by construction)
# ---------------------------------------------------------------------------

def _dispatch_schedule(instance: Instance, priority_key) -> Solution:
    """Non-delay list-scheduling simulation. At each step, among all jobs
    whose next operation is ready, pick the one with the earliest feasible
    start; ties broken by `priority_key(op, job_index, remaining_work)`
    (smaller = scheduled first). Deterministic, ignores any previous
    solution -- this is "build a feasible schedule from nothing"."""
    job_index = {job.job_id: i for i, job in enumerate(instance.jobs)}
    next_idx = {job.job_id: 0 for job in instance.jobs}
    job_ready = {job.job_id: job.release_date for job in instance.jobs}
    remaining_work = {
        job.job_id: sum(op.duration for op in job.ops) for job in instance.jobs
    }
    machine_avail = {m: 0 for m in range(instance.num_machines)}
    outages_by_machine: dict[int, list] = {}
    for o in instance.outages:
        outages_by_machine.setdefault(o.machine, []).append(o)
    for lst in outages_by_machine.values():
        lst.sort(key=lambda o: o.start)

    solution: Solution = {}
    pending = {job.job_id for job in instance.jobs if job.ops}
    while pending:
        candidates = []
        for jid in pending:
            job = instance.jobs[job_index[jid]]
            op = job.ops[next_idx[jid]]
            earliest = max(job_ready[jid], machine_avail[op.machine])
            key = priority_key(op, job_index[jid], remaining_work[jid])
            candidates.append((earliest, key, jid, op))
        # Final tie-break on job_id keeps this fully deterministic: without it,
        # ties in (earliest, priority) fall back to `pending` set-iteration
        # order, which is PYTHONHASHSEED-dependent for string job_ids (breaks
        # run-to-run reproducibility -- notably for MWKR's equal-work ties).
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        earliest, _, jid, op = candidates[0]
        start = earliest
        for o in outages_by_machine.get(op.machine, ()):
            if start < o.end and start + op.duration > o.start:
                start = o.end
        solution[op.op_id] = start
        machine_avail[op.machine] = start + op.duration
        job_ready[jid] = start + op.duration
        remaining_work[jid] -= op.duration
        next_idx[jid] += 1
        if next_idx[jid] >= len(instance.jobs[job_index[jid]].ops):
            pending.discard(jid)
    return solution


def _makespan(instance: Instance, solution: Solution) -> int:
    return max(
        solution[job.ops[-1].op_id] + job.ops[-1].duration
        for job in instance.jobs if job.ops
    )


def dispatch_spt(instance: Instance, seed: int = 0) -> Solution:
    """Shortest processing time first."""
    return _dispatch_schedule(instance, lambda op, ji, rem: op.duration)


def dispatch_lpt(instance: Instance, seed: int = 0) -> Solution:
    """Longest processing time first."""
    return _dispatch_schedule(instance, lambda op, ji, rem: -op.duration)


def dispatch_mwkr(instance: Instance, seed: int = 0) -> Solution:
    """Most work remaining (in the op's job) first."""
    return _dispatch_schedule(instance, lambda op, ji, rem: -rem)


def dispatch_fifo(instance: Instance, seed: int = 0) -> Solution:
    """Original job order (arrival order) first."""
    return _dispatch_schedule(instance, lambda op, ji, rem: ji)


def dispatch_random(instance: Instance, seed: int = 0) -> Solution:
    """Seeded random priority, fixed once per call (deterministic)."""
    rng = random.Random(seed)
    priority = {op.op_id: rng.random() for op in instance.all_ops}
    return _dispatch_schedule(instance, lambda op, ji, rem: priority[op.op_id])


DISPATCH_RULES = {
    "dispatch_spt": dispatch_spt, "dispatch_lpt": dispatch_lpt,
    "dispatch_mwkr": dispatch_mwkr, "dispatch_fifo": dispatch_fifo,
    "dispatch_random": dispatch_random,
}


def run_dispatch_baseline(name: str, instance: Instance, seed: int = 0) -> SolveResult:
    t0 = time.monotonic()
    solution = DISPATCH_RULES[name](instance, seed=seed)
    dt = time.monotonic() - t0
    obj = _makespan(instance, solution)
    return SolveResult(name, obj, solution, [(dt, obj)],
                       bootstrap_time_s=dt, solver_time_s=0.0)


# ---------------------------------------------------------------------------
# Floor-only baselines
# ---------------------------------------------------------------------------

def repair_only(
    instance: Instance, prev_solution: Solution | None, seed: int = 0,
    method_name: str = "repair_only",
) -> SolveResult:
    """The bootstrap floor with NO CP-SAT afterward: measures how good the
    floor alone is. Falls back to SPT dispatch when there is no previous
    solution (first stream instance)."""
    t0 = time.monotonic()
    if prev_solution is None:
        solution = dispatch_spt(instance, seed=seed)
    else:
        solution = list_schedule_bootstrap(instance, prev_solution)
    dt = time.monotonic() - t0
    obj = _makespan(instance, solution)
    return SolveResult(method_name, obj, solution, [(dt, obj)],
                       bootstrap_time_s=dt, solver_time_s=0.0)


def greedy_from_scratch(instance: Instance, seed: int = 0) -> SolveResult:
    """Feasible construction via SPT dispatch, IGNORING any previous
    solution even if one exists -- isolates "generic feasibility" from
    "reuse of history"."""
    return run_dispatch_baseline("dispatch_spt", instance, seed=seed)


# ---------------------------------------------------------------------------
# prev_raw: naive direct reuse (usually infeasible -- demonstrates why
# repair is needed at all)
# ---------------------------------------------------------------------------

def prev_raw(
    instance: Instance, prev_solution: Solution | None, seed: int = 0,
    on_infeasible: str = "flag",
) -> tuple[SolveResult, bool]:
    """Reuse the previous solution's start times verbatim for surviving ops;
    place any brand-new ops (arrivals) at t=0 with no adjustment. This is
    almost always infeasible once anything has changed (violates no_overlap
    or precedence) -- that is the point. Returns (result, was_feasible).
    on_infeasible='repair' falls back to list_schedule_bootstrap so callers
    that need a usable solution can still get one; 'flag' returns the
    (likely infeasible) raw solution with objective=None so the caller's
    feasibility check is expected to fail and should be recorded as such."""
    t0 = time.monotonic()
    if prev_solution is None:
        dt = time.monotonic() - t0
        return SolveResult("prev_raw", None, None, [],
                           bootstrap_time_s=dt, solver_time_s=0.0), False

    from .model_builder import validate_solution

    raw: Solution = {}
    for op in instance.all_ops:
        raw[op.op_id] = prev_solution.get(op.op_id, 0)
    dt = time.monotonic() - t0
    try:
        obj = validate_solution(instance, raw)
        return SolveResult("prev_raw", obj, raw, [(dt, obj)],
                           bootstrap_time_s=dt, solver_time_s=0.0), True
    except AssertionError:
        if on_infeasible == "repair":
            repaired = list_schedule_bootstrap(instance, prev_solution)
            obj = _makespan(instance, repaired)
            return SolveResult("prev_raw", obj, repaired, [(dt, obj)],
                               bootstrap_time_s=dt, solver_time_s=0.0), False
        return SolveResult("prev_raw", None, None, [],
                           bootstrap_time_s=dt, solver_time_s=0.0), False


# ---------------------------------------------------------------------------
# repair_plus_solver_no_floor: build (and pay for) the floor, then discard
# it entirely -- isolates whether the POCKET (not just the hint) is what
# matters, vs. cpsat_cold's plain unhinted search.
# ---------------------------------------------------------------------------

def repair_plus_solver_no_floor(
    instance: Instance, total_budget: float, prev_solution: Solution | None,
    workers: int = 1, seed: int = 0,
) -> SolveResult:
    t0 = time.monotonic()
    if prev_solution is not None:
        list_schedule_bootstrap(instance, prev_solution)  # built, then discarded
    bootstrap_time = time.monotonic() - t0

    trajectory: list[tuple[float, int]] = []
    remaining = total_budget - bootstrap_time
    t_solve0 = time.monotonic()
    sol, obj, status = solve(
        build_model(instance, hint=None), time_limit=max(0.05, remaining),
        workers=workers, seed=seed, recorder=trajectory, t_offset=bootstrap_time,
    )
    solver_time = time.monotonic() - t_solve0
    from ortools.sat.python import cp_model
    return SolveResult("repair_plus_solver_no_floor", obj, sol, trajectory,
                       bootstrap_time_s=bootstrap_time, solver_time_s=solver_time,
                       proven_optimal=status == cp_model.OPTIMAL)


# ---------------------------------------------------------------------------
# fix_and_optimize: exact-freeze a fraction of ops (chosen by strategy),
# reoptimize the rest.
# ---------------------------------------------------------------------------

def fix_and_optimize(
    instance: Instance, total_budget: float, prev_solution: Solution | None,
    freeze_frac: float, freeze_strategy: str = "earliest",
    workers: int = 1, seed: int = 0,
) -> SolveResult:
    """freeze_strategy: 'unaffected' (ops NOT touched by the delta, per
    instance.touched_ops), 'earliest' (earliest-starting ops in the floor),
    or 'random' (seeded random subset)."""
    method_name = f"fix_and_optimize_{int(freeze_frac * 100)}"
    t0 = time.monotonic()
    if prev_solution is None:
        floor = dispatch_spt(instance, seed=seed)
    else:
        floor = list_schedule_bootstrap(instance, prev_solution)
    bootstrap_time = time.monotonic() - t0

    all_ids = [op.op_id for op in instance.all_ops if op.op_id in floor]
    n_freeze = round(freeze_frac * len(all_ids))
    if freeze_strategy == "unaffected":
        untouched = [oid for oid in all_ids if oid not in instance.touched_ops]
        touched = [oid for oid in all_ids if oid in instance.touched_ops]
        order = untouched + touched  # prefer freezing untouched ops first
    elif freeze_strategy == "random":
        order = list(all_ids)
        random.Random(seed).shuffle(order)
    else:  # earliest
        order = sorted(all_ids, key=lambda oid: floor[oid])
    exact_frozen = {oid: floor[oid] for oid in order[:n_freeze]}

    trajectory: list[tuple[float, int]] = []
    remaining = total_budget - bootstrap_time
    t_solve0 = time.monotonic()
    sol, obj, status = solve(
        build_model(instance, hint=floor, exact_frozen=exact_frozen),
        time_limit=max(0.05, remaining), workers=workers, seed=seed,
        recorder=trajectory, t_offset=bootstrap_time,
    )
    solver_time = time.monotonic() - t_solve0
    from ortools.sat.python import cp_model
    return SolveResult(method_name, obj, sol, trajectory,
                       initial_objective=_makespan(instance, floor),
                       bootstrap_time_s=bootstrap_time, solver_time_s=solver_time,
                       proven_optimal=status == cp_model.OPTIMAL)


# ---------------------------------------------------------------------------
# lns_prev_solution: destroy/repair rounds seeded from the bootstrap floor
# (not from a fresh CP-SAT solve, unlike the exploratory lns_solve in
# harness.py). Reuses harness.select_destroy_set / ARMS.
# ---------------------------------------------------------------------------

def lns_prev_solution(
    instance: Instance, total_budget: float, prev_solution: Solution | None,
    workers: int = 1, seed: int = 0, round_slice: float = 1.0,
    arm_names: tuple[str, ...] = ("random_25", "delta_25", "critical_25", "outage_window_25"),
) -> SolveResult:
    t0 = time.monotonic()
    if prev_solution is None:
        incumbent = dispatch_spt(instance, seed=seed)
    else:
        incumbent = list_schedule_bootstrap(instance, prev_solution)
    bootstrap_time = time.monotonic() - t0
    objective = _makespan(instance, incumbent)
    initial_objective = objective

    by_name = {a.name: a for a in ARMS}
    arms = [by_name[n] for n in arm_names if n in by_name]
    if not arms:
        arms = [by_name["random_25"]]

    rng = random.Random(seed)
    trajectory: list[tuple[float, int]] = [(bootstrap_time, objective)]
    rounds: list[RoundLog] = []
    round_index = 0
    while time.monotonic() - t0 < total_budget - 0.05:
        remaining = total_budget - (time.monotonic() - t0)
        arm = arms[round_index % len(arms)]
        round_start = time.monotonic()
        destroy = select_destroy_set(arm, instance, incumbent, rng)
        frozen = {
            op.op_id: incumbent[op.op_id]
            for op in instance.all_ops if op.op_id not in destroy
        }
        sub_sol, sub_obj, _ = solve(
            build_model(instance, hint=incumbent, frozen=frozen),
            time_limit=max(0.05, min(round_slice, remaining)),
            workers=workers, seed=seed + round_index + 1,
        )
        round_time = time.monotonic() - round_start
        obj_before = objective
        improved = sub_obj is not None and sub_obj < objective
        if improved:
            incumbent, objective = sub_sol, sub_obj
        reward = max(0, obj_before - objective) / max(round_time, 1e-6)
        elapsed = time.monotonic() - t0
        rounds.append(RoundLog(round_index, arm.name, obj_before, objective,
                               elapsed, round_time, reward))
        trajectory.append((elapsed, objective))
        round_index += 1

    return SolveResult("lns_prev_solution", objective, incumbent, trajectory,
                       rounds=rounds, initial_objective=initial_objective,
                       bootstrap_time_s=bootstrap_time,
                       solver_time_s=(time.monotonic() - t0) - bootstrap_time)


# ---------------------------------------------------------------------------
# local_branching_prev: CP-SAT + an APPROXIMATE local-branching constraint
# limiting how many previously-existing operations may move.
# ---------------------------------------------------------------------------

def local_branching_prev(
    instance: Instance, total_budget: float, prev_solution: Solution | None,
    workers: int = 1, seed: int = 0, k_frac: float = 0.3,
) -> SolveResult:
    """Approximate local branching: at most k_frac of the operations common
    to the previous and current instance may take a DIFFERENT start time
    than they had previously. Encoded via reified equality: a boolean
    `moved[op]` is true iff start != prev_value, and sum(moved) <= k.
    New (arrival) operations are unconstrained -- they have no previous
    position to deviate from. This is an approximation of true local
    branching (which is usually posed as a Hamming-distance cut on a MIP's
    binary variables); job-shop start times are integer-valued, not binary,
    so we approximate "distance" as "count of ops that moved at all" rather
    than a weighted L1 distance. Documented simplification, not exact."""
    t0 = time.monotonic()
    built = build_model(instance, hint=prev_solution)
    if prev_solution:
        common = [op.op_id for op in instance.all_ops if op.op_id in prev_solution]
        k = max(1, round(k_frac * len(common)))
        moved_vars = []
        for op_id in common:
            prev_val = prev_solution[op_id]
            mv = built.model.new_bool_var(f"moved_{op_id}")
            built.model.add(built.starts[op_id] != prev_val).only_enforce_if(mv)
            built.model.add(built.starts[op_id] == prev_val).only_enforce_if(mv.negated())
            moved_vars.append(mv)
        built.model.add(sum(moved_vars) <= k)

    trajectory: list[tuple[float, int]] = []
    setup_time = time.monotonic() - t0
    t_solve0 = time.monotonic()
    sol, obj, status = solve(
        built, time_limit=max(0.05, total_budget - setup_time),
        workers=workers, seed=seed, recorder=trajectory, t_offset=setup_time,
    )
    solver_time = time.monotonic() - t_solve0
    from ortools.sat.python import cp_model
    return SolveResult("local_branching_prev", obj, sol, trajectory,
                       bootstrap_time_s=setup_time, solver_time_s=solver_time,
                       proven_optimal=status == cp_model.OPTIMAL)


# ---------------------------------------------------------------------------
# micro_repair_cp: a tiny CP-SAT budget to repair only touched ops, then
# used as the floor under the SAME pocket mechanism as boot_cold. Kept
# strictly separate from boot_cold (which uses a pure greedy floor).
# ---------------------------------------------------------------------------

def micro_repair_cp(
    instance: Instance, total_budget: float, prev_solution: Solution | None,
    workers: int = 1, seed: int = 0, micro_budget: float = 0.1,
) -> SolveResult:
    t0 = time.monotonic()
    if prev_solution is None:
        floor = dispatch_spt(instance, seed=seed)
        floor_obj = _makespan(instance, floor)
        micro_time = time.monotonic() - t0
    else:
        greedy_floor = list_schedule_bootstrap(instance, prev_solution)
        untouched = {
            op.op_id: greedy_floor[op.op_id] for op in instance.all_ops
            if op.op_id not in instance.touched_ops and op.op_id in greedy_floor
        }
        micro_traj: list[tuple[float, int]] = []
        micro_sol, micro_obj, _ = solve(
            build_model(instance, hint=greedy_floor, exact_frozen=untouched),
            time_limit=micro_budget, workers=workers, seed=seed,
            recorder=micro_traj,
        )
        micro_time = time.monotonic() - t0
        if micro_sol is not None:
            floor, floor_obj = micro_sol, micro_obj
        else:
            floor, floor_obj = greedy_floor, _makespan(instance, greedy_floor)

    trajectory: list[tuple[float, int]] = [(micro_time, floor_obj)]
    remaining = total_budget - micro_time
    t_solve0 = time.monotonic()
    sol, obj, status = solve(
        build_model(instance, hint=None), time_limit=max(0.05, remaining),
        workers=workers, seed=seed, recorder=trajectory, t_offset=micro_time,
    )
    solver_time = time.monotonic() - t_solve0
    best_sol, best_obj = sol, obj
    if best_obj is None or floor_obj < best_obj:
        best_sol, best_obj = floor, floor_obj
    mono, best = [], None
    for t, o in sorted(trajectory):
        if best is None or o < best:
            best = o
            mono.append((t, o))
    from ortools.sat.python import cp_model
    return SolveResult("micro_repair_cp", best_obj, best_sol, mono,
                       initial_objective=floor_obj,
                       bootstrap_time_s=micro_time, solver_time_s=solver_time,
                       proven_optimal=status == cp_model.OPTIMAL)
