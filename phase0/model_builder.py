"""CP-SAT model construction for job-shop instances, plus an independent
solution validator used by the tests.

The model uses the standard interval encoding: one interval per operation,
precedence within each job, no_overlap per machine (with outages as fixed
dummy intervals), makespan objective.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .streams import Instance

Solution = dict[str, int]  # op_id -> start time


@dataclass
class BuiltModel:
    model: cp_model.CpModel
    starts: dict[str, cp_model.IntVar]
    makespan: cp_model.IntVar
    instance: Instance


def build_model(
    instance: Instance,
    hint: Solution | None = None,
    frozen: dict[str, int] | None = None,
) -> BuiltModel:
    """Build the CP-SAT model.

    hint:   op_id -> start used as a solver hint (warm start). Ops missing
            from the hint (e.g. newly arrived jobs) are simply not hinted.
    frozen: op_id -> incumbent start. The LNS freeze preserves the *machine
            order* implied by these starts (chain constraints between
            consecutive frozen ops on each machine) but lets all start times
            float, so repairs can left-shift the schedule. Destroyed ops are
            free to reorder anywhere. The incumbent itself always satisfies
            the chains, so feasibility is preserved.
    """
    model = cp_model.CpModel()
    horizon = instance.horizon

    starts: dict[str, cp_model.IntVar] = {}
    intervals_by_machine: dict[int, list[cp_model.IntervalVar]] = {
        m: [] for m in range(instance.num_machines)
    }
    job_ends = []

    for job in instance.jobs:
        prev_end = None
        for op in job.ops:
            start = model.new_int_var(0, horizon, f"s_{op.op_id}")
            end = model.new_int_var(0, horizon, f"e_{op.op_id}")
            interval = model.new_interval_var(start, op.duration, end, f"i_{op.op_id}")
            starts[op.op_id] = start
            intervals_by_machine[op.machine].append(interval)
            if prev_end is not None:
                model.add(start >= prev_end)
            prev_end = end
        job_ends.append(prev_end)

    for outage in instance.outages:
        interval = model.new_fixed_size_interval_var(
            outage.start, outage.end - outage.start, f"out_{outage.machine}_{outage.start}"
        )
        intervals_by_machine[outage.machine].append(interval)

    for machine, intervals in intervals_by_machine.items():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, job_ends)
    model.minimize(makespan)

    if frozen:
        frozen_by_machine: dict[int, list] = {}
        for job in instance.jobs:
            for op in job.ops:
                if op.op_id in frozen:
                    frozen_by_machine.setdefault(op.machine, []).append(op)
        for ops in frozen_by_machine.values():
            ops.sort(key=lambda op: frozen[op.op_id])
            for a, b in zip(ops, ops[1:]):
                model.add(starts[b.op_id] >= starts[a.op_id] + a.duration)

    if hint:
        for op_id, value in hint.items():
            if op_id in starts and 0 <= value <= horizon:
                model.add_hint(starts[op_id], value)

    return BuiltModel(model=model, starts=starts, makespan=makespan, instance=instance)


def solve(
    built: BuiltModel,
    time_limit: float,
    workers: int = 1,
    seed: int = 0,
    recorder: list[tuple[float, int]] | None = None,
    t_offset: float = 0.0,
) -> tuple[Solution | None, int | None, int]:
    """Solve and return (solution, objective, status). Solution is None if
    no feasible solution was found within the limit; status is a cp_model
    status constant (e.g. cp_model.OPTIMAL).

    recorder: if given, every intermediate solution is appended to it as
    (t_offset + seconds since this solve started, objective) so callers can
    build honest primal-integral trajectories."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    if recorder is None:
        status = solver.solve(built.model)
    else:
        t0 = time.monotonic()

        class _Recorder(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                recorder.append(
                    (t_offset + time.monotonic() - t0, int(self.objective_value))
                )

        status = solver.solve(built.model, _Recorder())
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {op_id: solver.value(var) for op_id, var in built.starts.items()}
        return solution, solver.value(built.makespan), status
    return None, None, status


def validate_solution(instance: Instance, solution: Solution) -> int:
    """Independently verify feasibility and return the makespan.

    Raises AssertionError on any violated constraint. Deliberately does not
    use CP-SAT so it can catch model-construction bugs.
    """
    # every op scheduled, non-negative start
    for job in instance.jobs:
        for op in job.ops:
            assert op.op_id in solution, f"missing op {op.op_id}"
            assert solution[op.op_id] >= 0, f"negative start for {op.op_id}"

    # precedence within jobs
    for job in instance.jobs:
        for a, b in zip(job.ops, job.ops[1:]):
            end_a = solution[a.op_id] + a.duration
            assert solution[b.op_id] >= end_a, (
                f"precedence violated: {a.op_id} ends {end_a}, "
                f"{b.op_id} starts {solution[b.op_id]}"
            )

    # no overlap per machine (ops and outages)
    by_machine: dict[int, list[tuple[int, int, str]]] = {}
    for job in instance.jobs:
        for op in job.ops:
            s = solution[op.op_id]
            by_machine.setdefault(op.machine, []).append((s, s + op.duration, op.op_id))
    for outage in instance.outages:
        by_machine.setdefault(outage.machine, []).append(
            (outage.start, outage.end, "outage")
        )
    for machine, spans in by_machine.items():
        spans.sort()
        for (s1, e1, id1), (s2, e2, id2) in zip(spans, spans[1:]):
            assert e1 <= s2, (
                f"overlap on machine {machine}: {id1} [{s1},{e1}) vs {id2} [{s2},{e2})"
            )

    return max(
        solution[job.ops[-1].op_id] + job.ops[-1].duration for job in instance.jobs
    )
