"""Arrival-specific bootstrap policy variants.

Arrivals are the weakest case for boot_cold's default floor (see
BOOT_COLD_PAPER.md §6, §8): `list_schedule_bootstrap` always APPENDS new
jobs' operations after everything else, even when a machine has an idle gap
a new operation would fit into. These variants test whether smarter,
still-solver-free (except `micro_cp`) insertion closes that gap.

Default policy `append` is EXACTLY `harness.list_schedule_bootstrap` --
byte-identical output, regression tested (`test_append_matches_list_schedule_bootstrap`).

All floor policies (append/gap_insert/regret_insert/beam_insert) share the
signature `(instance, prev_solution) -> Solution` and plug directly into
`harness.warm_bootstrap_solve(..., floor_fn=<policy>)`. `micro_cp` is
different in kind -- it spends real CP-SAT budget, so it is NOT a drop-in
floor_fn; it is exposed as its own SolveResult-producing baseline
(a thin alias over `baselines.micro_repair_cp`).
"""

from __future__ import annotations

import time

from .harness import list_schedule_bootstrap
from .model_builder import Solution
from .streams import Instance, Job, Operation

BOOTSTRAP_POLICIES = ("append", "gap_insert", "regret_insert", "beam_insert", "micro_cp")


def boot_cold_append(instance: Instance, prev_solution: Solution) -> Solution:
    """Alias for harness.list_schedule_bootstrap -- the default policy."""
    return list_schedule_bootstrap(instance, prev_solution)


# ---------------------------------------------------------------------------
# Shared machinery: schedule surviving ops first (leaving genuine idle gaps
# on machines wherever job precedence forced a wait), then insert new jobs'
# operations into those gaps instead of always appending.
# ---------------------------------------------------------------------------

def _old_ops_schedule(instance: Instance, prev_solution: Solution) -> Solution:
    """Same list-scheduling replay as list_schedule_bootstrap, restricted to
    operations that survived the delta (are in prev_solution). New jobs are
    NOT placed here -- callers insert them afterward. Produces a compact
    schedule for old ops with real idle gaps wherever job precedence, not
    machine contention, was the binding constraint."""
    pos_in_job: dict[str, int] = {}
    job_of: dict[str, str] = {}
    for job in instance.jobs:
        for k, op in enumerate(job.ops):
            pos_in_job[op.op_id] = k
            job_of[op.op_id] = job.job_id

    old_ops = [op for op in instance.all_ops if op.op_id in prev_solution]
    ordered = sorted(
        old_ops,
        key=lambda op: (prev_solution[op.op_id], pos_in_job[op.op_id], op.op_id),
    )
    outages_by_machine: dict[int, list] = {}
    for o in instance.outages:
        outages_by_machine.setdefault(o.machine, []).append(o)
    for lst in outages_by_machine.values():
        lst.sort(key=lambda o: o.start)

    machine_avail: dict[int, int] = {}
    job_end: dict[str, int] = {}
    out: Solution = {}
    for op in ordered:
        s = max(job_end.get(job_of[op.op_id], 0), machine_avail.get(op.machine, 0))
        for o in outages_by_machine.get(op.machine, ()):
            if s < o.end and s + op.duration > o.start:
                s = o.end
        out[op.op_id] = s
        machine_avail[op.machine] = s + op.duration
        job_end[job_of[op.op_id]] = s + op.duration
    return out


def _new_jobs(instance: Instance, prev_solution: Solution) -> list[Job]:
    """Jobs with at least one operation not present in prev_solution
    (arrivals), in their original instance order. Each such job's ops are
    ALL new by stream-generator construction (an arrival adds a whole job)."""
    return [
        job for job in instance.jobs
        if any(op.op_id not in prev_solution for op in job.ops)
    ]


def _busy_intervals(solution: Solution, instance: Instance, machine: int,
                    outages_by_machine: dict) -> list[tuple[int, int]]:
    ivs = [
        (solution[op.op_id], solution[op.op_id] + op.duration)
        for op in instance.all_ops
        if op.op_id in solution and op.machine == machine
    ]
    ivs += [(o.start, o.end) for o in outages_by_machine.get(machine, [])]
    return sorted(ivs)


def _gaps(intervals: list[tuple[int, int]], horizon: int) -> list[tuple[int, int]]:
    gaps = []
    cursor = 0
    for s, e in intervals:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    gaps.append((cursor, horizon))  # unbounded trailing gap
    return gaps


def _outages_by_machine(instance: Instance) -> dict[int, list]:
    out: dict[int, list] = {}
    for o in instance.outages:
        out.setdefault(o.machine, []).append(o)
    return out


def _fits(gap: tuple[int, int], earliest: int, duration: int) -> int | None:
    """Return the actual start time if `duration` fits in `gap` no earlier
    than `earliest`, else None."""
    gs, ge = gap
    s = max(gs, earliest)
    if s + duration <= ge:
        return s
    return None


def boot_cold_gap_insert(instance: Instance, prev_solution: Solution) -> Solution:
    """Insert new jobs' operations into the FIRST idle machine gap they fit,
    preserving job precedence within each new job. Falls back to appending
    at the end of the machine's timeline when no gap fits (identical to
    `append`'s behaviour in that case, so this never does structurally worse
    than the default)."""
    solution = dict(_old_ops_schedule(instance, prev_solution))
    outages_by_machine = _outages_by_machine(instance)
    horizon = instance.horizon

    for job in _new_jobs(instance, prev_solution):
        job_ready = 0
        for op in job.ops:
            busy = _busy_intervals(solution, instance, op.machine, outages_by_machine)
            gaps = _gaps(busy, horizon)
            start = None
            for gap in gaps:
                start = _fits(gap, job_ready, op.duration)
                if start is not None:
                    break
            if start is None:  # should not happen (trailing gap is unbounded)
                start = max(job_ready,
                           busy[-1][1] if busy else 0)
            solution[op.op_id] = start
            job_ready = start + op.duration
    return solution


def boot_cold_regret_insert(instance: Instance, prev_solution: Solution) -> Solution:
    """For each new job's operation, evaluate ALL candidate gaps on its
    machine and choose the one minimizing the operation's own finish time
    (a simple, deterministic "least regret" proxy: the insertion that adds
    the least delay to the current partial schedule), rather than gap_insert's
    first-fit."""
    solution = dict(_old_ops_schedule(instance, prev_solution))
    outages_by_machine = _outages_by_machine(instance)
    horizon = instance.horizon

    for job in _new_jobs(instance, prev_solution):
        job_ready = 0
        for op in job.ops:
            busy = _busy_intervals(solution, instance, op.machine, outages_by_machine)
            gaps = _gaps(busy, horizon)
            best_start = None
            for gap in gaps:
                start = _fits(gap, job_ready, op.duration)
                if start is not None and (best_start is None or start < best_start):
                    best_start = start
                    if start == job_ready:
                        break  # earliest possible -- can't do better
            if best_start is None:
                best_start = max(job_ready, busy[-1][1] if busy else 0)
            solution[op.op_id] = best_start
            job_ready = best_start + op.duration
    return solution


def boot_cold_beam_insert(
    instance: Instance, prev_solution: Solution,
    beam_width: int = 4, timeout_s: float = 0.5,
) -> Solution:
    """Bounded beam search over insertion choices for new jobs' operations.
    At each step, each beam node is expanded by up to 3 candidate placements
    (first-fit gap, least-finish-time gap, append-at-end), scored by the
    node's running makespan-so-far, and pruned to the best `beam_width`.
    Falls back to gap_insert's result if the timeout is hit before finishing
    (timeout protection, per spec) -- keeps this usable even on large
    instances where the beam could otherwise blow up."""
    t0 = time.monotonic()
    outages_by_machine = _outages_by_machine(instance)
    horizon = instance.horizon
    base = dict(_old_ops_schedule(instance, prev_solution))
    new_jobs = _new_jobs(instance, prev_solution)

    # each beam node: (solution dict, {job_id: ready_time})
    beam = [(base, {job.job_id: 0 for job in new_jobs})]

    for job in new_jobs:
        for op in job.ops:
            if time.monotonic() - t0 > timeout_s:
                return boot_cold_gap_insert(instance, prev_solution)
            expanded = []
            for sol, ready in beam:
                job_ready = ready[job.job_id]
                busy = _busy_intervals(sol, instance, op.machine, outages_by_machine)
                gaps = _gaps(busy, horizon)
                candidates = set()
                # first-fit
                for gap in gaps:
                    s = _fits(gap, job_ready, op.duration)
                    if s is not None:
                        candidates.add(s)
                        break
                # least-finish-time (best-fit)
                best = None
                for gap in gaps:
                    s = _fits(gap, job_ready, op.duration)
                    if s is not None and (best is None or s < best):
                        best = s
                if best is not None:
                    candidates.add(best)
                # append fallback
                candidates.add(max(job_ready, busy[-1][1] if busy else 0))

                for start in candidates:
                    new_sol = dict(sol)
                    new_sol[op.op_id] = start
                    new_ready = dict(ready)
                    new_ready[job.job_id] = start + op.duration
                    expanded.append((new_sol, new_ready))

            def _score(node):
                sol, _ = node
                return max(sol.values(), default=0)

            expanded.sort(key=_score)
            beam = expanded[:beam_width]

    best_sol, _ = min(beam, key=lambda node: max(node[0].values(), default=0))
    return best_sol


FLOOR_POLICIES = {
    "append": boot_cold_append,
    "gap_insert": boot_cold_gap_insert,
    "regret_insert": boot_cold_regret_insert,
    "beam_insert": boot_cold_beam_insert,
}


def boot_cold_micro_cp(instance, total_budget, prev_solution, workers: int = 1,
                       seed: int = 0, micro_budget: float = 0.1):
    """CP-assisted floor: NOT near-zero-cost (spends micro_budget of real
    CP-SAT time), so kept out of FLOOR_POLICIES / not usable as a floor_fn
    swap-in for boot_cold. Thin alias over baselines.micro_repair_cp so the
    logic lives in exactly one place."""
    from .baselines import micro_repair_cp
    return micro_repair_cp(instance, total_budget, prev_solution, workers, seed, micro_budget)
