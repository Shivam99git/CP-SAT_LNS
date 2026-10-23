"""Impact-selective CP-SAT: optimize a neighbourhood of a validated incumbent
while preserving the incumbent's machine-order structure outside it.

Restricted problem. For incumbent S with machine orders pi_m and a
neighbourhood N, keep every job-shop constraint and add, for each machine m
and each pair (u, v) of operations NOT in N that are consecutive in pi_m
restricted to V \\ N:
        s_v >= s_u + p_u.
S satisfies all added constraints (on one machine, u before v in S implies
s_u + p_u <= s_v), so the restricted problem is a restriction of the original
problem containing S. Operations in N may move and be reordered freely.
With require_improvement, the constraint Cmax <= Cmax(S) - 1 is added: the
solver then searches only strictly better schedules, and INFEASIBLE means no
better schedule exists in the restricted problem.

Neighbourhoods (all computed on the incumbent's machine-order graph):
  N1 disruption   D: operations whose inputs changed (disruption_set)
  N2 closure      A = D + everything reachable from D
  N3 critical     operations on a longest path (calendar-free tails)
  N4 combined     A + critical
  N5 bounded      breadth-first expansion of D over job/machine adjacency,
                  capped at `frac` of all operations
  random          a uniformly random subset of the same size as N5 (control)
"""

from __future__ import annotations

import random
from collections import deque

from .event_localized_repair import (
    _preds, _tails, evaluate, index_instance, orders_from_schedule, topological_order,
)
from .reuse_methods import Clock, RunResult, build_research_model, run_cpsat
from .streams import Instance

Solution = dict[str, int]


# ---------------------------------------------------------------------------
# Disruption set
# ---------------------------------------------------------------------------

def disruption_set(prev_inst: Instance | None, inst: Instance, prev: Solution | None) -> set[str]:
    """Operations of `inst` whose own inputs differ from the previous
    instance: new operations; operations with a changed duration, machine,
    release date or commitment; surviving machine successors (in the previous
    schedule's order) of cancelled operations; and operations whose previous
    interval intersects a new outage."""
    new = {o.op_id: o for o in inst.all_ops}
    if prev_inst is None or prev is None:
        return set(new)
    old = {o.op_id: o for o in prev_inst.all_ops}
    rel_new = {o.op_id: j.release_date for j in inst.jobs for o in j.ops}
    rel_old = {o.op_id: j.release_date for j in prev_inst.jobs for o in j.ops}
    D = {v for v, o in new.items()
         if v not in old or old[v].duration != o.duration or old[v].machine != o.machine
         or rel_old.get(v) != rel_new[v]
         or prev_inst.frozen_starts.get(v) != inst.frozen_starts.get(v)}
    gone = set(old) - set(new)
    if gone:
        orders = orders_from_schedule(prev_inst, {v: s for v, s in prev.items() if v in old})
        for seq in orders.values():
            for a, b in zip(seq, seq[1:]):
                if a in gone and b in new:
                    D.add(b)
            # a removed op may be followed by more removed ops; take the next survivor
            for k, a in enumerate(seq):
                if a in gone:
                    nxt = next((b for b in seq[k + 1:] if b not in gone), None)
                    if nxt is not None:
                        D.add(nxt)
    old_out = {(o.machine, o.start, o.end) for o in prev_inst.outages}
    for o in inst.outages:
        if (o.machine, o.start, o.end) in old_out:
            continue
        for v, op in new.items():
            if op.machine == o.machine and v in prev and prev[v] < o.end and prev[v] + op.duration > o.start:
                D.add(v)
    return D


# ---------------------------------------------------------------------------
# Neighbourhoods
# ---------------------------------------------------------------------------

def forward_closure(inst: Instance, incumbent: Solution, D: set[str]) -> set[str]:
    ix = index_instance(inst)
    orders = orders_from_schedule(inst, incumbent, ix)
    present = {v for seq in orders.values() for v in seq}
    succs: dict[str, list[str]] = {v: [] for v in present}
    for v, ps in _preds(ix, orders, present).items():
        for u in ps:
            succs[u].append(v)
    seen = set(v for v in D if v in present)
    stack = list(seen)
    while stack:
        for w in succs[stack.pop()]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return seen


def critical_ops(inst: Instance, incumbent: Solution) -> set[str]:
    """Operations on at least one longest path of the incumbent's orders
    (heads from the exact evaluation, tails calendar-free). Critical paths
    need not be unique; all critical operations are returned."""
    ix = index_instance(inst)
    orders = orders_from_schedule(inst, incumbent, ix)
    heads = evaluate(inst, orders, ix)
    tails = _tails(ix, orders, topological_order(ix, orders))
    mk = max((heads[v] + ix.op[v].duration for v in heads), default=0)
    return {v for v in heads if heads[v] + tails[v] >= mk}


def bounded_expansion(inst: Instance, incumbent: Solution, D: set[str], frac: float) -> set[str]:
    ix = index_instance(inst)
    orders = orders_from_schedule(inst, incumbent, ix)
    cap = max(1, round(frac * len(ix.op)))
    adj: dict[str, list[str]] = {v: [] for v in ix.op}
    for ops in ix.job_ops.values():
        for a, b in zip(ops, ops[1:]):
            adj[a].append(b)
            adj[b].append(a)
    for seq in orders.values():
        for a, b in zip(seq, seq[1:]):
            adj[a].append(b)
            adj[b].append(a)
    seeds = sorted(v for v in D if v in ix.op)
    seen, q = set(), deque()
    for v in seeds:
        if len(seen) >= cap:
            break
        seen.add(v)
        q.append(v)
    while q and len(seen) < cap:
        for w in sorted(adj[q.popleft()]):
            if w not in seen:
                seen.add(w)
                q.append(w)
                if len(seen) >= cap:
                    break
    return seen


def make_neighbourhood(kind: str, inst: Instance, incumbent: Solution, D: set[str],
                       frac: float = 0.25, rng: random.Random | None = None) -> set[str]:
    if kind == "N1":
        return set(D) & {o.op_id for o in inst.all_ops}
    if kind == "N2":
        return forward_closure(inst, incumbent, D)
    if kind == "N3":
        return critical_ops(inst, incumbent)
    if kind == "N4":
        return forward_closure(inst, incumbent, D) | critical_ops(inst, incumbent)
    if kind == "N5":
        return bounded_expansion(inst, incumbent, D, frac)
    if kind == "random":
        ids = sorted(o.op_id for o in inst.all_ops)
        k = len(bounded_expansion(inst, incumbent, D, frac))
        return set((rng or random.Random(0)).sample(ids, min(k, len(ids))))
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# Restricted solve
# ---------------------------------------------------------------------------

def build_restricted_model(inst: Instance, incumbent: Solution, N: set[str],
                           require_improvement: bool, incumbent_obj: int):
    built = build_research_model(inst, hint=incumbent)
    ix = index_instance(inst)
    orders = orders_from_schedule(inst, incumbent, ix)
    n_arcs = 0
    for seq in orders.values():
        kept = [v for v in seq if v not in N]
        for u, v in zip(kept, kept[1:]):
            built.model.add(built.starts[v] >= built.starts[u] + ix.op[u].duration)
            n_arcs += 1
    if require_improvement:
        built.model.add(built.makespan <= incumbent_obj - 1)
    return built, n_arcs


def selective_solve(res: RunResult, clock: Clock, inst: Instance, N: set[str], local_end: float,
                    workers: int, seed: int, require_improvement: bool = True) -> dict:
    """Run the restricted model until the absolute monotonic time `local_end`
    (never past the overall deadline). The retained incumbent in `res` is
    replaced only by a validated, strictly better schedule."""
    meta = {"neighbourhood_size": len(N), "n_ops": len(inst.all_ops), "fixed_order_arcs": 0,
            "local_status": "NOT_RUN", "local_improved": False, "local_time_s": 0.0}
    if res.solution is None:
        meta["local_status"] = "NO_INCUMBENT"
        return meta
    before = res.objective
    t0 = clock.elapsed()
    built, meta["fixed_order_arcs"] = build_restricted_model(inst, res.solution, N, require_improvement,
                                                             res.objective)
    meta["local_build_s"] = clock.elapsed() - t0
    res.build_s += meta["local_build_s"]
    solver_s_before = res.solver_s
    sub = Clock(max(0.0, min(local_end, clock.deadline) - clock.t0 - clock.elapsed()))
    sub.t0 = clock.t0  # share the caller's time origin so events use one axis
    sub.deadline = min(local_end, clock.deadline)
    status_before = res.solver_status
    run_cpsat(res, sub, inst, None, workers, seed, source="local", built=built)
    meta["local_status"] = res.solver_status
    res.solver_status = status_before
    meta["local_improved"] = res.objective is not None and before is not None and res.objective < before
    meta["local_time_s"] = clock.elapsed() - t0
    meta["local_solver_s"] = res.solver_s - solver_s_before
    return meta
