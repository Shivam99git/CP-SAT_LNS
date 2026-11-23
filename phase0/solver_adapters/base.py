"""Common solver-adapter contract (multisolver phase, Task 5.1).

Every adapter solves the SAME physical problem (phase0/streams.Instance) and
returns an AdapterResult. The wrapper `run_adapter` -- not the adapter --
validates every returned schedule with the solver-independent validator, so
no backend's FEASIBLE/OPTIMAL status is trusted on its own.

Time accounting: the caller passes a time origin t0 and an absolute monotonic
deadline. Everything the adapter does after it is called (model translation,
subprocess start, MiniZinc compilation, presolve, search, solution
extraction) happens before the deadline check and is charged to the budget.
Event times are seconds since t0.

Trajectories: `events` holds (t, objective, schedule-or-None) for every
improving incumbent the backend actually reports through a callback or
streamed output; adapters that cannot observe intermediate solutions set
capability anytime="final_only" and report only the final solution. Nothing
is interpolated or invented.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..schedule_validator import ScheduleError, check_schedule
from ..streams import Instance

Solution = dict[str, int]


@dataclass(frozen=True)
class Capabilities:
    technology: str                 # "CP" | "MIP"
    anytime: str                    # "callback" | "stream" | "log" | "final_only"
    warm_start: str                 # API name, or "none"
    workers: bool
    seed_meaningful: bool
    cutoff: bool = True             # objective upper bound C <= U - 1
    restricted: bool = True         # extra precedence arcs (restricted neighbourhoods)
    size_limit: tuple[int, int] | None = None   # (max vars, max constraints) license cap


@dataclass
class SolveRequest:
    instance: Instance
    t0: float                       # time origin (monotonic)
    deadline: float                 # absolute monotonic deadline
    seed: int = 0
    workers: int = 1
    warm_start: Solution | None = None
    cutoff: int | None = None       # makespan <= cutoff
    kept_arcs: list[tuple[str, str]] | None = None
    params: dict = field(default_factory=dict)


@dataclass
class AdapterResult:
    solver: str
    version: str
    status: str = "NOT_RUN"         # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN | LICENSE_LIMIT | ERROR | NO_TIME
    schedule: Solution | None = None
    objective: int | None = None
    lower_bound: float | None = None
    proven_optimal: bool = False
    events: list = field(default_factory=list)     # (t, obj, schedule|None)
    build_s: float = 0.0
    solve_s: float = 0.0
    total_s: float = 0.0
    model_vars: int | None = None
    model_binary: int | None = None
    model_constraints: int | None = None
    threads: int = 1
    error: str | None = None
    notes: list = field(default_factory=list)
    validated: bool = False


def now(req: SolveRequest) -> float:
    return time.monotonic() - req.t0


def remaining(req: SolveRequest) -> float:
    return req.deadline - time.monotonic()


def run_adapter(adapter, req: SolveRequest) -> AdapterResult:
    """Call an adapter, then independently validate its final schedule and
    every intermediate schedule it reported. Invalid schedules are dropped
    and recorded; a solver never gets credit for an unvalidated schedule."""
    t_call = time.monotonic()
    try:
        res = adapter.solve(req)
    except Exception as e:  # recorded, never silently substituted
        res = AdapterResult(solver=adapter.name, version=adapter.version(), status="ERROR",
                            error=f"{type(e).__name__}: {e}")
    res.total_s = time.monotonic() - t_call
    inst = req.instance
    kept = []
    best = None
    for ev in sorted(res.events, key=lambda e: e[0]):
        t, obj, sched = ev
        if sched is not None:
            try:
                v = check_schedule(inst, sched)
            except ScheduleError as e:
                res.notes.append(f"intermediate rejected at t={t:.3f}: {e}")
                continue
            if req.cutoff is not None and v > req.cutoff:
                res.notes.append(f"intermediate violates cutoff at t={t:.3f}")
                continue
            if v != obj:
                res.notes.append(f"intermediate objective {obj} != validated {v}; using validated")
                obj = v
        if best is None or obj < best:
            best = obj
            kept.append((t, obj, sched is not None))
    res.events = kept
    if res.schedule is not None:
        try:
            v = check_schedule(inst, res.schedule)
            if req.cutoff is not None and v > req.cutoff:
                raise ScheduleError(f"cutoff violated: {v} > {req.cutoff}")
            res.objective, res.validated = v, True
            if not res.events or res.events[-1][1] > v:
                # final schedule better than any streamed one (e.g. final-only backends):
                # credit it at the moment the adapter returned it, never earlier.
                res.events.append((t_call - req.t0 + res.total_s, v, True))
        except ScheduleError as e:
            res.notes.append(f"final schedule rejected: {e}")
            res.schedule, res.objective, res.validated = None, None, False
            res.status = "INVALID"
    if res.proven_optimal and res.lower_bound is not None and res.objective is not None \
            and res.lower_bound > res.objective + 1e-6:
        res.notes.append("lower bound above objective: inconsistent backend report")
    return res


_VERSIONS: dict[str, str] = {}


def cached_version(adapter) -> str:
    """Solver version, queried once per process (callers warm it up before
    starting any clock, so version probing is never charged to a solve)."""
    if adapter.name not in _VERSIONS:
        _VERSIONS[adapter.name] = adapter.version()
    return _VERSIONS[adapter.name]
