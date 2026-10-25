"""Deadline-correct implementations of the solution-reuse methods compared in
the historical-reuse gate (docs/research_extension, Gate 1).

Every method runs under ONE monotonic deadline that starts before any work
(repair, dispatching, CP-SAT model construction, validation) and covers all of
it. An externally constructed incumbent enters the trajectory only at the
elapsed time at which it exists and has passed the independent validator
(schedule_validator.check_schedule), never at t = 0.

The archived implementations in harness.py (cpsat_default_solve,
warm_bootstrap_solve) are left unchanged as the behavioural baseline: the
mechanisms here are the same, but those start Cold's clock after model
construction and let the Floor continuation overrun by its build time.

Methods (P = previous schedule, None on the first instance of a stream):
  cold               unhinted CP-SAT
  hint               CP-SAT hinted with P
  floor              repair of P kept as external incumbent + unhinted CP-SAT
  floor_hint         repair of P kept as incumbent + CP-SAT hinted with it
  repaired_hint_only repair of P used only as a CP-SAT hint, not retained
  spt_cold           fresh SPT schedule kept as incumbent + unhinted CP-SAT
  mwkr_cold          fresh MWKR schedule kept as incumbent + unhinted CP-SAT
Without a previous schedule, the four history-based methods make exactly the
same solver call as `cold`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .baselines import dispatch_mwkr, dispatch_spt
from .harness import list_schedule_bootstrap
from .model_builder import BuiltModel, build_model
from .schedule_validator import ScheduleError, check_schedule
from .streams import Instance

Solution = dict[str, int]
MIN_SOLVE_S = 0.01

STATUS_NAME = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
               cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN",
               cp_model.MODEL_INVALID: "MODEL_INVALID"}


class Clock:
    def __init__(self, budget: float):
        self.budget = budget
        self.t0 = time.monotonic()
        self.deadline = self.t0 + budget

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def remaining(self) -> float:
        return self.deadline - time.monotonic()


@dataclass
class RunResult:
    method: str
    budget: float
    objective: int | None = None
    solution: Solution | None = None
    # (elapsed seconds, objective, source) for every improving incumbent
    events: list[tuple[float, int, str]] = field(default_factory=list)
    solver_status: str = "NOT_RUN"
    construction_s: float = 0.0
    construction_objective: int | None = None
    construction_source: str = ""
    build_s: float = 0.0
    solver_s: float = 0.0
    total_s: float = 0.0
    overrun_s: float = 0.0
    validated: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def t_first(self) -> float | None:
        return self.events[0][0] if self.events else None


def build_research_model(instance: Instance, hint: Solution | None = None) -> BuiltModel:
    """build_model plus the constraints it does not enforce by itself: job
    release dates and committed (frozen) start times."""
    built = build_model(instance, hint=hint,
                        exact_frozen=dict(instance.frozen_starts) or None)
    for job in instance.jobs:
        if job.release_date > 0 and job.ops:
            built.model.add(built.starts[job.ops[0].op_id] >= job.release_date)
    return built


def _accept(res: RunResult, sol: Solution, obj: int, t: float, source: str) -> None:
    """Record a validated incumbent if it improves on the current one."""
    if res.objective is None or obj < res.objective:
        res.objective, res.solution = obj, sol
        res.events.append((t, obj, source))


def _construct(res: RunResult, clock: Clock, instance: Instance, fn, source: str) -> Solution | None:
    """Build an external incumbent, validate it, and retain it at its real time."""
    t_start = clock.elapsed()
    try:
        sol = fn()
        obj = check_schedule(instance, sol)
    except ScheduleError as e:
        res.construction_s += clock.elapsed() - t_start
        res.notes.append(f"{source} rejected by validator: {e}")
        return None
    res.construction_s += clock.elapsed() - t_start
    res.construction_objective, res.construction_source = obj, source
    _accept(res, sol, obj, clock.elapsed(), source)
    return sol


def run_cpsat(res: RunResult, clock: Clock, instance: Instance, hint: Solution | None,
              workers: int, seed: int, source: str = "cpsat", built: BuiltModel | None = None,
              params: dict | None = None, stall_s: float | None = None) -> None:
    """Unrestricted (or caller-built) CP-SAT solve for the remaining budget.
    Model construction counts against the deadline; the returned solution is
    validated before it may replace the incumbent.

    params:  extra CP-SAT parameters (e.g. {"interleave_search": True});
    stall_s: stop the search once no improving solution has been reported for
             stall_s seconds (CpSolver.stop_search from a watchdog thread).
    With both None (the default) the behaviour is the archived one."""
    t_b = clock.elapsed()
    if built is None:
        built = build_research_model(instance, hint=hint)
    res.build_s += clock.elapsed() - t_b
    limit = clock.remaining()
    if limit < MIN_SOLVE_S:
        res.notes.append(f"{source}: no time left for the solver ({limit:.4f}s)")
        return
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    for k, v in (params or {}).items():
        setattr(solver.parameters, k, v)

    pending: list[tuple[float, int]] = []

    class _CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            pending.append((clock.elapsed(), int(self.objective_value)))

    t_s = clock.elapsed()
    watchdog = None
    if stall_s is not None:
        import threading
        done = threading.Event()

        def _watch():
            while not done.wait(0.005):
                last = pending[-1][0] if pending else t_s
                if clock.elapsed() - last > stall_s:
                    res.notes.append(f"{source}: stopped after {stall_s}s without improvement")
                    solver.stop_search()
                    return
        watchdog = threading.Thread(target=_watch, daemon=True)
        watchdog.start()
    status = solver.solve(built.model, _CB())
    if watchdog is not None:
        done.set()
        watchdog.join()
    res.solver_s += clock.elapsed() - t_s
    res.solver_status = STATUS_NAME.get(status, str(status))
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return
    sol = {op_id: int(solver.value(v)) for op_id, v in built.starts.items()}
    try:
        obj = check_schedule(instance, sol)
    except ScheduleError as e:
        res.notes.append(f"{source} final solution rejected by validator: {e}")
        return
    if obj != int(solver.value(built.makespan)):
        res.notes.append(f"{source}: validator makespan {obj} != solver {solver.value(built.makespan)}")
    # The trajectory records each solver incumbent that beats the best value
    # reported so far (solver objectives; only the final solution is checked).
    prior = res.objective
    for t, o in pending:
        if not res.events or o < res.events[-1][1]:
            res.events.append((t, o, source))
    # The retained solution changes only if the validated solver result is
    # strictly better than the externally retained incumbent.
    if prior is None or obj < prior:
        res.objective, res.solution = obj, sol
        if not res.events or res.events[-1][1] != obj:
            res.events.append((clock.elapsed(), obj, source))


def _finish(res: RunResult, clock: Clock, instance: Instance) -> RunResult:
    res.total_s = clock.elapsed()
    res.overrun_s = max(0.0, res.total_s - res.budget)
    if res.solution is not None:
        try:
            res.validated = check_schedule(instance, res.solution) == res.objective
        except ScheduleError as e:
            res.validated = False
            res.notes.append(f"final validation failed: {e}")
    return res


def run_method(method: str, instance: Instance, previous: Solution | None, budget: float,
               workers: int = 1, seed: int = 0) -> RunResult:
    clock = Clock(budget)
    res = RunResult(method=method, budget=budget)
    has_prev = previous is not None

    if method == "cold" or (method in ("hint", "floor", "floor_hint", "repaired_hint_only")
                            and not has_prev):
        run_cpsat(res, clock, instance, None, workers, seed)
    elif method == "hint":
        run_cpsat(res, clock, instance, previous, workers, seed)
    elif method in ("floor", "floor_hint"):
        floor = _construct(res, clock, instance,
                           lambda: list_schedule_bootstrap(instance, previous), "repair")
        run_cpsat(res, clock, instance, floor if method == "floor_hint" else None, workers, seed)
    elif method == "repaired_hint_only":
        t0 = clock.elapsed()
        rep = list_schedule_bootstrap(instance, previous)
        res.construction_s += clock.elapsed() - t0
        run_cpsat(res, clock, instance, rep, workers, seed)
    elif method == "spt_cold":
        _construct(res, clock, instance, lambda: dispatch_spt(instance), "spt")
        run_cpsat(res, clock, instance, None, workers, seed)
    elif method == "mwkr_cold":
        _construct(res, clock, instance, lambda: dispatch_mwkr(instance), "mwkr")
        run_cpsat(res, clock, instance, None, workers, seed)
    else:
        raise ValueError(f"unknown method {method!r}")
    return _finish(res, clock, instance)


GATE1_METHODS = ("cold", "hint", "floor", "floor_hint", "repaired_hint_only", "spt_cold", "mwkr_cold")
