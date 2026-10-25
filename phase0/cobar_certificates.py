"""Improvement-opportunity certificates for restricted CP-SAT neighbourhoods
(COBAR, docs/cobar/03_certificate_theory.md).

Neighbourhood. For a feasible incumbent S with machine orders pi_m, a set N of
free operations and a set R of released machine arcs, the restricted problem
P(S, N, R) is the full job-shop model (job precedence, machine no-overlap with
outages as fixed intervals, release dates on first operations, exact
commitments) plus

    s_v >= s_u + p_u   for every kept arc (u, v),

where the kept arcs are the pairs consecutive in pi_m restricted to the
operations of positive duration outside N, minus the released arcs R. For
positive durations these are exactly the arcs
`selective_reoptimization.build_restricted_model` (IAIP-SR) adds; IAIP-SR also
chains zero-length operations, which can exclude the incumbent (see
docs/cobar/03_certificate_theory.md, counterexample C3). With N = {} and
R = {} the kept arcs are the incumbent's own machine orders; with N = all
operations there are none.

Bound. L(N, R) = max(L_path, L_mach) where
  * L_path is the largest completion time of the earliest-start propagation
    over job arcs and kept arcs, with release dates, commitments (s_v = f_v)
    and outage-aware next-fit for operations of positive duration;
  * L_mach = max over machines m of  min head + sum of durations + min tail
    over the operations of m (tails: calendar-free longest job/kept-arc path
    after the operation).
Both are relaxations: every schedule of P(S, N, R) satisfies the constraints
used, so L(N, R) <= C*(N, R) (proof in the theory document). If S belongs to
P(S, N, R) (it always does by construction; it is checked), then
C*(N, R) <= U = Cmax(S), and L(N, R) >= U certifies that P(S, N, R) contains no
schedule better than S. It says nothing about the unrestricted problem,
except for N = all operations, where P is the full problem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .event_localized_repair import index_instance, next_fit, orders_from_schedule
from .schedule_validator import check_schedule
from .streams import Instance

Solution = dict[str, int]
Arc = tuple[str, str]


class CertificateError(ValueError):
    """Inputs violate the certificate's assumptions (cyclic constraints, or an
    incumbent that is infeasible for the instance or the restriction)."""


@dataclass
class Certificate:
    U: int                      # incumbent makespan (validated)
    L: int                      # max(L_path, L_mach)
    L_path: int
    L_mach: int
    decisive: bool              # L >= U: no improving schedule in P(S, N, R)
    kind: str                   # "path", "machine", "both" or "none"
    n_kept_arcs: int
    path: list[str] = field(default_factory=list)   # one chain realizing L_path
    time_s: float = 0.0


def kept_arcs(instance: Instance, incumbent: Solution, N: set[str],
              R: set[Arc] | None = None, ix=None) -> list[Arc]:
    """Kept machine arcs of P(S, N, R): consecutive pairs of the incumbent's
    machine orders restricted to operations outside N, minus R."""
    ix = ix or index_instance(instance)
    orders = orders_from_schedule(instance, incumbent, ix)
    R = R or set()
    arcs = []
    for seq in orders.values():
        # zero-length operations occupy no machine time (validator and CP-SAT
        # no-overlap), so they get no machine arc: a zero-length operation
        # inside or at the start of another operation's interval would
        # otherwise receive an arc the incumbent violates.
        kept = [v for v in seq if v not in N and ix.op[v].duration > 0]
        arcs.extend((u, v) for u, v in zip(kept, kept[1:]) if (u, v) not in R)
    return arcs


@dataclass
class _Graph:
    topo: list[str]
    preds: dict[str, list[tuple[str, str]]]   # v -> [(u, "job"|"machine")]
    succs: dict[str, list[str]]


def _graph(ix, arcs: list[Arc]) -> _Graph:
    ops = list(ix.op)
    preds: dict[str, list[tuple[str, str]]] = {v: [] for v in ops}
    succs: dict[str, list[str]] = {v: [] for v in ops}
    for jops in ix.job_ops.values():
        for a, b in zip(jops, jops[1:]):
            preds[b].append((a, "job"))
            succs[a].append(b)
    for u, v in arcs:
        if u not in preds or v not in preds:
            raise CertificateError(f"arc ({u}, {v}) refers to an unknown operation")
        preds[v].append((u, "machine"))
        succs[u].append(v)
    indeg = {v: len(preds[v]) for v in ops}
    stack = sorted((v for v in ops if indeg[v] == 0), reverse=True)
    topo = []
    while stack:
        u = stack.pop()
        topo.append(u)
        for w in succs[u]:
            indeg[w] -= 1
            if indeg[w] == 0:
                stack.append(w)
    if len(topo) != len(ops):
        raise CertificateError("cyclic fixed-precedence graph")
    return _Graph(topo, preds, succs)


def heads(instance: Instance, arcs: list[Arc], ix=None, calendar: bool = True):
    """Earliest-start lower bounds h(v) under job arcs, `arcs`, release dates,
    commitments and (if `calendar`) outage next-fit for p_v > 0. Returns
    (h, ready, binding, graph, floor_bound): ready(v) is the bound before the
    calendar and commitment; binding[v] lists the predecessors u with
    h(u)+p_u = ready(v), empty if v's bound comes from its release date, a
    commitment or an outage; floor_bound[v] is True if h(v) would not decrease
    even if every predecessor arc were removed (release date or 0 attains
    ready(v), or a commitment or outage fixes h(v)) -- such an operation starts
    a binding chain even when binding[v] is non-empty."""
    ix = ix or index_instance(instance)
    g = _graph(ix, arcs)
    h: dict[str, int] = {}
    ready: dict[str, int] = {}
    binding: dict[str, list[str]] = {}
    floor_bound: dict[str, bool] = {}
    for v in g.topo:
        op = ix.op[v]
        if op.duration < 0:
            raise CertificateError(f"{v}: negative duration")
        first = ix.pos[v] == 0
        r = ix.release[ix.job_of[v]] if first else 0
        if r < 0:
            raise CertificateError(f"{v}: negative release date")
        best = max(r, 0)
        for u, _ in g.preds[v]:
            best = max(best, h[u] + ix.op[u].duration)
        ready[v] = best
        s = best
        if calendar and op.duration > 0:
            s = next_fit(ix.calendar.get(op.machine, []), best, op.duration)
        bind = [u for u, _ in g.preds[v] if h[u] + ix.op[u].duration == best] if s == best else []
        fl = max(r, 0) >= best or s > best
        if v in ix.frozen:
            f = ix.frozen[v]
            if s > f:
                raise CertificateError(f"{v}: lower bound {s} exceeds its commitment {f}")
            s, bind, fl = f, [], True  # fixed by the commitment whatever its predecessors do
        h[v] = s
        binding[v] = bind
        floor_bound[v] = fl or not bind
    return h, ready, binding, g, floor_bound


def _tails(ix, g: _Graph) -> dict[str, int]:
    q: dict[str, int] = {}
    for v in reversed(g.topo):
        q[v] = max((ix.op[w].duration + q[w] for w in g.succs[v]), default=0)
    return q


def certificate(instance: Instance, incumbent: Solution, N: set[str],
                R: set[Arc] | None = None, calendar: bool = True,
                machine_bound: bool = True, check_membership: bool = True) -> Certificate:
    """Lower bound L(N, R) and the no-improvement certificate L >= U."""
    t0 = time.monotonic()
    ix = index_instance(instance)
    U = check_schedule(instance, incumbent)         # raises if S is infeasible
    arcs = kept_arcs(instance, incumbent, N, R, ix)
    if check_membership:
        for u, v in arcs:
            if incumbent[v] < incumbent[u] + ix.op[u].duration:
                raise CertificateError(f"incumbent violates kept arc ({u}, {v})")
    h, _ready, binding, g, _floor = heads(instance, arcs, ix, calendar)
    L_path, end = 0, None
    for v in g.topo:
        c = h[v] + ix.op[v].duration
        if c > L_path or end is None:
            L_path, end = c, v
    path = []
    v = end
    while v is not None:
        path.append(v)
        b = binding.get(v) or []
        v = b[0] if b else None
    path.reverse()
    L_mach = 0
    if machine_bound:
        q = _tails(ix, g)
        by_m: dict[int, list[str]] = {}
        for v, op in ix.op.items():
            by_m.setdefault(op.machine, []).append(v)
        for vs in by_m.values():
            busy = sum(ix.op[v].duration for v in vs)
            L_mach = max(L_mach, min(h[v] for v in vs) + busy + min(q[v] for v in vs))
    L = max(L_path, L_mach)
    if L > U:  # impossible when S belongs to P(S, N, R): a bug or a violated assumption
        raise CertificateError(f"lower bound {L} exceeds the incumbent makespan {U}")
    kind = "none"
    if L >= U:
        kind = "both" if L_path >= U and L_mach >= U else ("path" if L_path >= U else "machine")
    return Certificate(U=U, L=L, L_path=L_path, L_mach=L_mach, decisive=L >= U, kind=kind,
                       n_kept_arcs=len(arcs), path=path, time_s=time.monotonic() - t0)


def global_certificate(instance: Instance, incumbent: Solution) -> Certificate:
    """N = all operations: a lower bound on the unrestricted problem. If
    decisive, the incumbent is optimal for the instance."""
    return certificate(instance, incumbent, {o.op_id for o in instance.all_ops})
