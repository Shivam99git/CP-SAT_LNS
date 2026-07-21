"""CP-SAT model construction for RCPSP instances, plus an independent
solution validator.

One interval variable per activity, precedence constraints (general DAG,
not just per-job chains), one `AddCumulative` per renewable resource,
minimize makespan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .instances import RInstance

RSolution = dict[str, int]  # activity_id -> start time


@dataclass
class RBuiltModel:
    model: cp_model.CpModel
    starts: dict[str, cp_model.IntVar]
    makespan: cp_model.IntVar
    instance: RInstance


def build_rcpsp_model(
    instance: RInstance,
    hint: RSolution | None = None,
    exact_frozen: dict[str, int] | None = None,
) -> RBuiltModel:
    model = cp_model.CpModel()
    horizon = instance.horizon
    by_id = instance.activity_by_id

    starts: dict[str, cp_model.IntVar] = {}
    intervals: dict[str, cp_model.IntervalVar] = {}
    for act in instance.activities:
        s = model.new_int_var(0, horizon, f"s_{act.activity_id}")
        e = model.new_int_var(0, horizon, f"e_{act.activity_id}")
        iv = model.new_interval_var(s, act.duration, e, f"i_{act.activity_id}")
        starts[act.activity_id] = s
        intervals[act.activity_id] = iv

    for act in instance.activities:
        for pred_id in act.predecessors:
            if pred_id in by_id:
                pred = by_id[pred_id]
                model.add(starts[act.activity_id] >= starts[pred_id] + pred.duration)

    for resource_id, capacity in instance.resources.items():
        ivs, demands = [], []
        for act in instance.activities:
            amt = act.resource_usage.get(resource_id, 0)
            if amt > 0:
                ivs.append(intervals[act.activity_id])
                demands.append(amt)
        if ivs:
            model.add_cumulative(ivs, demands, capacity)

    makespan = model.new_int_var(0, horizon, "makespan")
    ends = [starts[a.activity_id] + a.duration for a in instance.activities]
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)

    if exact_frozen:
        for act_id, value in exact_frozen.items():
            if act_id in starts:
                model.add(starts[act_id] == value)

    if hint:
        for act_id, value in hint.items():
            if act_id in starts and 0 <= value <= horizon:
                model.add_hint(starts[act_id], value)

    return RBuiltModel(model=model, starts=starts, makespan=makespan, instance=instance)


def solve_rcpsp(
    built: RBuiltModel, time_limit: float, workers: int = 1, seed: int = 0,
    recorder: list[tuple[float, int]] | None = None, t_offset: float = 0.0,
) -> tuple[RSolution | None, int | None, int]:
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
                recorder.append((t_offset + time.monotonic() - t0, int(self.objective_value)))

        status = solver.solve(built.model, _Recorder())
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {aid: solver.value(var) for aid, var in built.starts.items()}
        return solution, solver.value(built.makespan), status
    return None, None, status


def validate_rcpsp_solution(instance: RInstance, solution: RSolution) -> int:
    """Independent feasibility check (no CP-SAT): precedence + resource
    capacity at every relevant time point. Raises AssertionError on any
    violation; returns the makespan."""
    by_id = instance.activity_by_id
    for act in instance.activities:
        assert act.activity_id in solution, f"missing activity {act.activity_id}"
        assert solution[act.activity_id] >= 0

    for act in instance.activities:
        for pred_id in act.predecessors:
            if pred_id in by_id:
                pred = by_id[pred_id]
                end_pred = solution[pred_id] + pred.duration
                assert solution[act.activity_id] >= end_pred, (
                    f"precedence violated: {pred_id} ends {end_pred}, "
                    f"{act.activity_id} starts {solution[act.activity_id]}"
                )

    for resource_id, capacity in instance.resources.items():
        events = sorted({solution[a.activity_id] for a in instance.activities
                         if a.resource_usage.get(resource_id, 0) > 0})
        for t in events:
            usage = sum(
                a.resource_usage.get(resource_id, 0)
                for a in instance.activities
                if solution[a.activity_id] <= t < solution[a.activity_id] + a.duration
            )
            assert usage <= capacity, (
                f"resource {resource_id} over capacity at t={t}: {usage} > {capacity}"
            )

    return max(solution[a.activity_id] + a.duration for a in instance.activities)
