"""RCPSP bootstrap (serial schedule-generation-scheme repair) and the
boot_cold / cpsat_cold solve functions -- the RCPSP analogue of
phase0/harness.py's list_schedule_bootstrap / warm_bootstrap_solve /
cpsat_default_solve, for cross-domain transfer evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .instances import Activity, RInstance
from .model_builder import RSolution, build_rcpsp_model, solve_rcpsp


@dataclass
class RSolveResult:
    method: str
    objective: int | None
    solution: RSolution | None
    trajectory: list[tuple[float, int]] = field(default_factory=list)
    initial_objective: int | None = None
    proven_optimal: bool = False


def _topo_order_by_prev_start(instance: RInstance, prev_solution: RSolution) -> list[Activity]:
    """Order activities respecting precedence, ties broken by previous start
    time (old activities) or insertion order (new activities, appended
    last). Since predecessors always have a lower activity index by
    construction (see streams.py), sorting by (has_prev_solution, prev
    start-or-index) already respects precedence."""
    by_id = instance.activity_by_id
    index_of = {a.activity_id: i for i, a in enumerate(instance.activities)}
    return sorted(
        instance.activities,
        key=lambda a: (a.activity_id not in prev_solution,
                       prev_solution.get(a.activity_id, index_of[a.activity_id]),
                       index_of[a.activity_id]),
    )


def serial_sgs_bootstrap(instance: RInstance, prev_solution: RSolution) -> RSolution:
    """Serial schedule-generation scheme: process activities in an order
    derived from the previous solution (old activities keep their relative
    order; new activities are appended), placing each as early as precedence
    and resource capacity allow. Feasible by construction (bounded search:
    each retry strictly increases the candidate start time, so it always
    terminates). ~1ms-scale, no CP-SAT."""
    order = _topo_order_by_prev_start(instance, prev_solution)
    by_id = instance.activity_by_id
    finish: dict[str, int] = {}
    solution: RSolution = {}
    # resource_profile[r] = list of (start, end, amount) already placed
    resource_profile: dict[str, list[tuple[int, int, int]]] = {
        r: [] for r in instance.resources
    }

    for act in order:
        est = max((finish[p] for p in act.predecessors if p in finish), default=0)
        t = est
        for _ in range(len(instance.activities) * 4 + 10):  # bounded, always terminates
            conflict_end = None
            for r, amt in act.resource_usage.items():
                cap = instance.resources.get(r, 0)
                window_end = t + act.duration
                breakpoints = {t} | {
                    s for s, e, _ in resource_profile[r] if t <= s < window_end
                }
                for p in sorted(breakpoints):
                    usage = amt + sum(
                        a2 for s, e, a2 in resource_profile[r] if s <= p < e
                    )
                    if usage > cap:
                        ends_here = [e for s, e, _ in resource_profile[r] if s <= p < e]
                        candidate = min(ends_here) if ends_here else t + 1
                        conflict_end = candidate if conflict_end is None else min(conflict_end, candidate)
            if conflict_end is None:
                break
            t = max(t + 1, conflict_end)
        solution[act.activity_id] = t
        finish[act.activity_id] = t + act.duration
        for r, amt in act.resource_usage.items():
            resource_profile[r].append((t, t + act.duration, amt))
    return solution


def _makespan(instance: RInstance, solution: RSolution) -> int:
    return max(solution[a.activity_id] + a.duration for a in instance.activities)


def rcpsp_cold_solve(
    instance: RInstance, total_budget: float, workers: int = 1, seed: int = 0,
    method_name: str = "cpsat_cold",
) -> RSolveResult:
    from ortools.sat.python import cp_model
    trajectory: list[tuple[float, int]] = []
    sol, obj, status = solve_rcpsp(
        build_rcpsp_model(instance), time_limit=total_budget, workers=workers,
        seed=seed, recorder=trajectory,
    )
    return RSolveResult(method_name, obj, sol, trajectory,
                        proven_optimal=status == cp_model.OPTIMAL)


def rcpsp_boot_cold_solve(
    instance: RInstance, total_budget: float, prev_solution: RSolution | None = None,
    workers: int = 1, seed: int = 0, use_hint: bool = False,
    method_name: str = "boot_cold",
) -> RSolveResult:
    """Direct RCPSP analogue of phase0.harness.warm_bootstrap_solve: build
    the SGS floor (~1ms), keep it as an anytime pocket under an otherwise
    unmodified (use_hint=False, "boot_cold") or hinted (use_hint=True,
    "boot_warm") continuation solve for the remaining budget."""
    from ortools.sat.python import cp_model
    t0 = time.monotonic()
    trajectory: list[tuple[float, int]] = []
    incumbent: RSolution | None = None
    objective: int | None = None

    if prev_solution is not None:
        boot = serial_sgs_bootstrap(instance, prev_solution)
        boot_obj = _makespan(instance, boot)
        incumbent, objective = boot, boot_obj
        trajectory.append((time.monotonic() - t0, boot_obj))
    initial_objective = objective

    remaining = total_budget - (time.monotonic() - t0)
    status = None
    if remaining > 0.05:
        sol, obj, status = solve_rcpsp(
            build_rcpsp_model(instance, hint=incumbent if use_hint else None),
            time_limit=remaining, workers=workers, seed=seed,
            recorder=trajectory, t_offset=time.monotonic() - t0,
        )
        if sol is not None and (objective is None or obj < objective):
            incumbent, objective = sol, obj

    if incumbent is None:
        return RSolveResult(method_name, None, None, [])

    mono, best = [], None
    for t, o in sorted(trajectory):
        if best is None or o < best:
            best = o
            mono.append((t, o))
    return RSolveResult(
        method_name, objective, incumbent, mono, initial_objective=initial_objective,
        proven_optimal=(status == cp_model.OPTIMAL) if status is not None else False,
    )
