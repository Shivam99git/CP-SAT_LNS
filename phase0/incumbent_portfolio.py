"""Feasible incumbent portfolio.

Builds a set of candidate schedules for the CURRENT instance, validates each
independently, and selects the one with the smallest makespan:

    S0 = argmin_{S in P, S valid} Cmax(S)

Selection property (immediate): if every member is valid and selection uses
the same objective, S0 is no worse than any member. This says nothing about
how a solver run started from S0 compares with an independently executed
solver run under the same wall-clock budget.

Members (cheapest first; history-dependent members need a previous schedule):
  history-dependent: hist (archived Floor repair: append new operations),
                     elr (event-localized repair), insert (archived regret
                     insertion floor policy)
  fresh:             spt, mwkr, lpt, fifo dispatching rules
Construction is sequential in a fixed order, shares one construction budget
(and the caller's overall deadline), and records provenance, time, validity
and duplicates for every member. It is anytime: `on_improve(solution,
objective, name)` is called as soon as a member is validated and improves on
the members built so far, so the caller can retain it immediately instead of
waiting for the whole portfolio (development data showed that waiting costs
more primal integral than the extra members recover).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .baselines import dispatch_fifo, dispatch_lpt, dispatch_mwkr, dispatch_spt
from .bootstrap_policies import FLOOR_POLICIES
from .event_localized_repair import event_localized_repair
from .schedule_validator import ScheduleError, check_schedule
from .streams import Instance

Solution = dict[str, int]

HISTORY_MEMBERS = ("hist", "elr", "insert")
FRESH_MEMBERS = ("spt", "mwkr", "lpt", "fifo")
# cheapest strong members first: with anytime publication, order sets when
# each incumbent becomes available (and breaks objective ties)
ORDER = ("hist", "elr", "mwkr", "spt", "insert", "lpt", "fifo")

PORTFOLIOS = {  # ablation configurations (Task 5)
    "hist": ("hist",),
    "spt": ("spt",),
    "mwkr": ("mwkr",),
    "elr": ("elr",),
    "hist+fresh": ("hist", "spt", "mwkr", "lpt", "fifo"),
    "hist+elr": ("hist", "elr"),
    "full": ORDER,
    "fresh": FRESH_MEMBERS,          # full portfolio without any history-dependent member
}


@dataclass
class Candidate:
    name: str
    objective: int | None
    time_s: float
    valid: bool
    duplicate_of: str | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class PortfolioResult:
    solution: Solution | None
    objective: int | None
    chosen: str | None
    candidates: list[Candidate]
    total_time_s: float
    skipped_for_budget: list[str] = field(default_factory=list)


def _builders(instance: Instance, previous: Solution | None):
    elr_extra: dict = {}

    def elr():
        sol, st = event_localized_repair(instance, previous)
        elr_extra.update({"fallback": st.fallback, "core_removed": st.core_removed,
                          "new_ops": st.new_ops, "frac_start_changed": st.frac_start_changed})
        return sol

    return {
        "hist": lambda: FLOOR_POLICIES["append"](instance, previous),
        "elr": elr,
        "insert": lambda: FLOOR_POLICIES["regret_insert"](instance, previous),
        "spt": lambda: dispatch_spt(instance),
        "mwkr": lambda: dispatch_mwkr(instance),
        "lpt": lambda: dispatch_lpt(instance),
        "fifo": lambda: dispatch_fifo(instance),
    }, elr_extra


def build_portfolio(instance: Instance, previous: Solution | None, members: tuple[str, ...],
                    construction_budget: float, deadline: float | None = None,
                    on_improve=None) -> PortfolioResult:
    """Construct `members` (in canonical ORDER) until the construction budget
    or the caller's absolute monotonic `deadline` is exhausted."""
    t0 = time.monotonic()
    builders, elr_extra = _builders(instance, previous)
    cands: list[Candidate] = []
    skipped: list[str] = []
    seen: dict[tuple, str] = {}
    best: tuple[int, int, str, Solution] | None = None
    for rank, name in enumerate(n for n in ORDER if n in members):
        now = time.monotonic()
        if now - t0 >= construction_budget or (deadline is not None and now >= deadline):
            skipped.append(name)
            continue
        if name in HISTORY_MEMBERS and previous is None:
            continue
        ts = time.monotonic()
        try:
            sol = builders[name]()
            obj = check_schedule(instance, sol)
            cand = Candidate(name, obj, time.monotonic() - ts, True)
        except ScheduleError as e:
            cands.append(Candidate(name, None, time.monotonic() - ts, False, error=str(e)))
            continue
        if name == "elr":
            cand.extra = dict(elr_extra)
        key = tuple(sorted(sol.items()))
        if key in seen:
            cand.duplicate_of = seen[key]
        else:
            seen[key] = name
        cands.append(cand)
        if best is None or (obj, rank) < (best[0], best[1]):
            best = (obj, rank, name, sol)
            if on_improve is not None:
                on_improve(sol, obj, name)
    return PortfolioResult(solution=best[3] if best else None, objective=best[0] if best else None,
                           chosen=best[2] if best else None, candidates=cands,
                           total_time_s=time.monotonic() - t0, skipped_for_budget=skipped)
