"""Solver-portable anytime rescheduling methods (multisolver phase, Task 6.1).

All methods share one monotonic clock: t0 at the call, deadline t0 + B.
Everything (incumbent construction, model translation, subprocess start,
solving, validation) is charged to B. Every incumbent counted in the
trajectory is validated by the solver-independent validator.

  S0 cold      solver alone, no initial schedule.
  S1 warm      the historical-repair schedule (portfolio member "hist") is
               handed to the solver ONLY as a native warm start; it is not
               retained, so the method gets credit only for schedules the
               solver itself returns. Not defined for solvers without a
               warm-start API (NOT_SUPPORTED).
  S2 retain    the same historical-repair schedule is retained externally as
               the incumbent from the moment it is validated; the solver then
               runs cold for the remaining budget.
  S3 portfolio full incumbent portfolio (history repairs + dispatching rules,
               each improving member retained when built), then the solver for
               the remaining budget, warm-started from the best member where
               the solver supports it (else cold; recorded).
  S4 rounds    S3's portfolio, IAIP-SR's disruption-centred restricted stage,
               then repeated restricted rounds on crit_expand neighbourhoods
               (C_max <= U - 1, kept machine-order arcs, stop on the first
               non-improving round) until 0.6 B, then the solver unrestricted
               and warm-started until B: the confirmatory SR+Crit pipeline with
               the solver swapped. Restricted models are hinted only for CP
               solvers whose hint tolerates an infeasible point (the incumbent
               violates the cutoff); MIP starts would be rejected.
  S5 native    CP-SAT only: S3 with interleave_search (single-thread native
               LNS); other engines have no separate native-LNS mode, so S5 is
               not defined for them (their S0 already is their native search).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from .cobar_certificates import kept_arcs
from .critical_region_anytime import make_round_neighbourhood
from .incumbent_portfolio import PORTFOLIOS, build_portfolio
from .schedule_validator import ScheduleError, check_schedule
from .selective_reoptimization import disruption_set, make_neighbourhood
from .solver_adapters import ADAPTERS, SolveRequest, run_adapter
from .streams import Instance

Solution = dict[str, int]
METHODS = ("S0", "S1", "S2", "S3", "S4", "S5")
CONSTRUCTION_FRAC = 0.05
ALPHA = 0.6
EXPANSION = 0.25
MAX_ROUNDS = 9
HINT_IN_RESTRICTED = {"cpsat", "cpoptimizer"}


class NotSupported(Exception):
    pass


@dataclass
class MethodRun:
    method: str
    solver: str
    budget: float
    workers: int
    seed: int
    objective: int | None = None
    schedule: Solution | None = None
    events: list = field(default_factory=list)       # (t, obj, source)
    stages: list = field(default_factory=list)       # one dict per solver call
    construction_s: float = 0.0
    total_s: float = 0.0
    overrun_s: float = 0.0
    validated: bool = False
    notes: list = field(default_factory=list)


def supported(method: str, solver: str) -> bool:
    caps = ADAPTERS[solver].caps
    if method == "S1":
        return caps.warm_start != "none"
    if method == "S5":
        return solver == "cpsat"
    return True


def _stage_record(name, r, extra=None):
    d = {"stage": name, "status": r.status, "objective": r.objective, "validated": r.validated,
         "build_s": r.build_s, "solve_s": r.solve_s, "total_s": r.total_s, "lower_bound": r.lower_bound,
         "proven_optimal": r.proven_optimal, "vars": r.model_vars, "binary": r.model_binary,
         "constraints": r.model_constraints, "n_events": len(r.events), "error": r.error,
         "subprocess_cpu_s": r.subprocess_cpu_s,
         "notes": r.notes[:3]}
    if extra:
        d.update(extra)
    return d


def run_method(method: str, solver: str, inst: Instance, previous: Solution | None,
               prev_instance: Instance | None, budget: float, workers: int = 1, seed: int = 0) -> MethodRun:
    if not supported(method, solver):
        raise NotSupported(f"{method} not defined for {solver}")
    adapter = ADAPTERS[solver]
    t0 = time.monotonic()
    deadline = t0 + budget
    run = MethodRun(method=method, solver=solver, budget=budget, workers=workers, seed=seed)

    def el():
        return time.monotonic() - t0

    audit = []   # (event index, schedule) checked after the clock stops

    def accept(sol, obj, t, source):
        if run.objective is None or obj < run.objective:
            run.objective, run.schedule = obj, sol
            run.events.append((t, obj, source))
            audit.append((len(run.events) - 1, sol))

    def call(stage, end, warm=None, cutoff=None, arcs=None, params=None):
        req = SolveRequest(instance=inst, t0=t0, deadline=min(end, deadline), seed=seed, workers=workers,
                           warm_start=warm, cutoff=cutoff, kept_arcs=arcs, params=params or {})
        r = run_adapter(adapter, req, validate_intermediate=False)
        for t, obj, sched in r.events:
            if sched is not None:
                accept(sched, obj, t, stage)
        run.stages.append(_stage_record(stage, r))
        return r

    if method == "S0":
        call("solver", deadline)
    elif method in ("S1", "S2"):
        ts = el()
        pf = build_portfolio(inst, previous, PORTFOLIOS["hist"] if previous is not None else PORTFOLIOS["mwkr"],
                             construction_budget=CONSTRUCTION_FRAC * budget, deadline=deadline)
        run.construction_s = el() - ts
        if pf.solution is None:
            run.notes.append("historical repair produced no valid schedule")
        if method == "S1":
            call("solver", deadline, warm=pf.solution)
        else:
            if pf.solution is not None:
                accept(pf.solution, pf.objective, el(), f"retain:{pf.chosen}")
            call("solver", deadline)
    elif method in ("S3", "S4", "S5"):
        ts = el()
        pf = build_portfolio(inst, previous, PORTFOLIOS["full"], construction_budget=CONSTRUCTION_FRAC * budget,
                             deadline=deadline, on_improve=lambda s, o, n: accept(s, o, el(), f"portfolio:{n}"))
        run.construction_s = el() - ts
        warm_ok = adapter.caps.warm_start != "none"
        if method == "S4" and run.schedule is not None:
            local_end = t0 + ALPHA * budget
            D = disruption_set(prev_instance, inst, previous)
            N0 = make_neighbourhood("N5", inst, run.schedule, D, EXPANSION)
            plan = [("initial", N0, set())] if N0 else []
            k = 0
            while time.monotonic() < local_end - 0.05:
                if plan:
                    name, N, R = plan.pop(0)
                else:
                    if k >= MAX_ROUNDS:
                        break
                    N, R, _ = make_round_neighbourhood("crit_expand", inst, run.schedule, D, EXPANSION, k)
                    name = f"round{k}"
                    k += 1
                if not N and not R:
                    break
                arcs = kept_arcs(inst, run.schedule, N, R)
                before = run.objective
                r = call(name, local_end, warm=run.schedule if solver in HINT_IN_RESTRICTED else None,
                         cutoff=before - 1, arcs=arcs)
                run.stages[-1].update({"released_ops": len(N), "kept_arcs": len(arcs),
                                       "improved": run.objective < before})
                if run.objective >= before and name != "initial":
                    break
        params = {"interleave_search": True} if method == "S5" else None
        call("global", deadline, warm=run.schedule if warm_ok else None, params=params)
        if not warm_ok and method in ("S3", "S4"):
            run.notes.append("solver has no warm-start API: global stage ran cold beside the retained incumbent")
    else:
        raise ValueError(method)
    run.total_s = el()
    run.overrun_s = max(0.0, run.total_s - budget)
    # post-clock audit: every trajectory event must be backed by a valid schedule
    # with exactly that makespan; invalid events are removed and recorded
    bad = set()
    for i, sol in audit:
        try:
            if check_schedule(inst, sol) != run.events[i][1]:
                bad.add(i)
        except ScheduleError:
            bad.add(i)
    if bad:
        run.notes.append(f"{len(bad)} trajectory events failed the post-run audit and were removed")
        run.events = [e for i, e in enumerate(run.events) if i not in bad]
    run.notes.append(f"audited {len(audit)} trajectory events")
    if run.schedule is not None:
        try:
            v = check_schedule(inst, run.schedule)
            run.validated = v == run.objective
            if not run.validated:
                run.notes.append(f"objective {run.objective} != validated {v}")
        except ScheduleError as e:
            run.notes.append(f"final schedule invalid: {e}")
    return run


def run_to_record(run: MethodRun) -> dict:
    d = asdict(run)
    d["events"] = [list(e) for e in run.events]
    return d
