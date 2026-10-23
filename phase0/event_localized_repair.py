"""Event-localized repair for dynamic job-shop scheduling.

A schedule is represented by its machine orders: for each machine m a
sequence pi_m of the operations it processes. Together with the job chains
these define a directed graph G = (V, E_J u E_M). For fixed orders, the
earliest-start ("semi-active") schedule is computed in one topological pass:

    ready(v) = max(release(job(v)) if v is first in its job,
                   c(job predecessor), c(machine predecessor))
    s(v)     = nextfit_m(ready(v), p_v)     earliest t >= ready(v) whose
                                            interval [t, t+p_v) avoids every
                                            outage on machine m
    c(v)     = s(v) + p_v
and committed operations are placed exactly at their committed start (an
error is raised if their earliest start is later). `evaluate` implements
this; it raises CycleError if the orders and job chains contain a cycle.

Repair (`event_localized_repair`):
  1. Take the previous schedule's machine orders, restricted to operations
     that still exist (surviving operations sorted by previous start).
  2. Remove the event's *core* operations from those orders:
       arrival / batch arrival / rush job : the new operations (not in the
                                             previous schedule)
       machine outage                     : operations whose earliest start
                                             under the previous orders is
                                             delayed by an outage
       others (cancellation, duration
       change, speed degradation, ...)    : none
  3. Re-insert core operations one at a time, jobs in decreasing order of
     total processing time and each job's operations in job order. Each
     operation goes to the cycle-free position on its machine that minimises
     max(current makespan, longest path through the operation); the path
     through the operation uses exact heads (with its machine calendar) and
     calendar-free tails, plus the remaining work of its own job.
  4. Evaluate the final orders exactly and validate the schedule
     independently. On a cycle, commitment conflict or validation failure,
     return the documented fallback (committed_dispatch: MWKR dispatching
     around committed operations) and record the cause.

Step 3 is a standard insertion heuristic for the job shop (cf. insertion
techniques for job-shop scheduling in the literature); the event-specific
choice of which operations to remove is the only design decision here.

`incremental_evaluate` recomputes only operations reachable in the NEW graph
from a dirty set; tests check it equals `evaluate` whenever the dirty set
contains every operation whose inputs changed (see
docs/research_extension/03_event_localized_repair.md for the statement,
proof and counterexamples).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .baselines import dispatch_mwkr
from .schedule_validator import ScheduleError, check_schedule
from .streams import Instance, Operation

Solution = dict[str, int]
Orders = dict[int, list[str]]
ARRIVAL_KINDS = {"arrival", "batch_arrival", "rush_job"}


class CycleError(ValueError):
    pass


class CommitmentError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

@dataclass
class _Index:
    op: dict[str, Operation]
    job_of: dict[str, str]
    pos: dict[str, int]
    job_ops: dict[str, list[str]]
    release: dict[str, int]
    calendar: dict[int, list[tuple[int, int]]]
    frozen: dict[str, int]


def index_instance(instance: Instance) -> _Index:
    op, job_of, pos, job_ops, release = {}, {}, {}, {}, {}
    for job in instance.jobs:
        job_ops[job.job_id] = [o.op_id for o in job.ops]
        release[job.job_id] = job.release_date
        for k, o in enumerate(job.ops):
            op[o.op_id], job_of[o.op_id], pos[o.op_id] = o, job.job_id, k
    cal: dict[int, list[tuple[int, int]]] = {}
    for o in instance.outages:
        cal.setdefault(o.machine, []).append((o.start, o.end))
    for m in cal:
        cal[m].sort()
    return _Index(op, job_of, pos, job_ops, release, cal, dict(instance.frozen_starts))


def next_fit(cal: list[tuple[int, int]], t: int, p: int) -> int:
    """Earliest start >= t such that [start, start+p) avoids all intervals of
    `cal` (sorted by start; merged outages are disjoint)."""
    for a, b in cal:
        if t < b and t + p > a:
            t = b
    return t


def _preds(ix: _Index, orders: Orders, present: set[str]) -> dict[str, list[str]]:
    preds: dict[str, list[str]] = {v: [] for v in present}
    for jid, ops in ix.job_ops.items():
        last = None
        for v in ops:
            if v in present:
                if last is not None:
                    preds[v].append(last)
                last = v
    for seq in orders.values():
        for a, b in zip(seq, seq[1:]):
            preds[b].append(a)
    return preds


def topological_order(ix: _Index, orders: Orders) -> list[str]:
    present = {v for seq in orders.values() for v in seq}
    preds = _preds(ix, orders, present)
    succs: dict[str, list[str]] = {v: [] for v in present}
    indeg = {v: len(ps) for v, ps in preds.items()}
    for v, ps in preds.items():
        for u in ps:
            succs[u].append(v)
    q = deque(sorted(v for v, d in indeg.items() if d == 0))
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for w in succs[u]:
            indeg[w] -= 1
            if indeg[w] == 0:
                q.append(w)
    if len(order) != len(present):
        raise CycleError(f"cycle among {len(present) - len(order)} operations")
    return order


def evaluate(instance: Instance, orders: Orders, ix: _Index | None = None,
             delayed: set[str] | None = None) -> Solution:
    """Exact earliest-start schedule for fixed machine orders (see module doc).
    If `delayed` is given, operations whose start the outage calendar pushed
    past their ready time are added to it."""
    ix = ix or index_instance(instance)
    topo = topological_order(ix, orders)
    present = set(topo)
    preds = _preds(ix, orders, present)
    start: Solution = {}
    for v in topo:
        o = ix.op[v]
        ready = 0
        if not any(u for u in preds[v] if ix.job_of[u] == ix.job_of[v]):
            ready = ix.release[ix.job_of[v]]
        for u in preds[v]:
            ready = max(ready, start[u] + ix.op[u].duration)
        s = next_fit(ix.calendar.get(o.machine, []), ready, o.duration)
        if delayed is not None and s > ready:
            delayed.add(v)
        if v in ix.frozen:
            if s > ix.frozen[v]:
                raise CommitmentError(f"{v}: earliest start {s} after commitment {ix.frozen[v]}")
            s = ix.frozen[v]
        start[v] = s
    return start


def incremental_evaluate(instance: Instance, orders: Orders, base: Solution,
                         dirty: set[str]) -> tuple[Solution, int]:
    """Recompute only operations reachable (in the graph of `orders`) from
    `dirty`; every other operation keeps its value in `base`. Exact iff
    `dirty` contains every operation whose own inputs (duration, release,
    commitment, calendar result or predecessor set) changed and `base` is the
    earliest-start schedule of the previous orders. Returns (schedule,
    number of recomputed operations)."""
    ix = index_instance(instance)
    topo = topological_order(ix, orders)
    present = set(topo)
    preds = _preds(ix, orders, present)
    start: Solution = {}
    changed: set[str] = set()
    recomputed = 0
    for v in topo:
        need = v in dirty or v not in base or any(u in changed for u in preds[v])
        if not need:
            start[v] = base[v]
            continue
        recomputed += 1
        o = ix.op[v]
        ready = 0
        if not any(u for u in preds[v] if ix.job_of[u] == ix.job_of[v]):
            ready = ix.release[ix.job_of[v]]
        for u in preds[v]:
            ready = max(ready, start[u] + ix.op[u].duration)
        s = next_fit(ix.calendar.get(o.machine, []), ready, o.duration)
        if v in ix.frozen:
            if s > ix.frozen[v]:
                raise CommitmentError(f"{v}: earliest start {s} after commitment {ix.frozen[v]}")
            s = ix.frozen[v]
        start[v] = s
        if base.get(v) != s or v in dirty:
            changed.add(v)
    return start, recomputed


def orders_from_schedule(instance: Instance, schedule: Solution, ix: _Index | None = None) -> Orders:
    """Machine orders of the operations of `instance` that appear in
    `schedule`, sorted by (start, position in job, op id)."""
    ix = ix or index_instance(instance)
    orders: Orders = {m: [] for m in range(instance.num_machines)}
    for v, o in ix.op.items():
        if v in schedule:
            orders.setdefault(o.machine, []).append(v)
    for m in orders:
        orders[m].sort(key=lambda v: (schedule[v], ix.pos[v], v))
    return orders


def _tails(ix: _Index, orders: Orders, topo: list[str]) -> dict[str, int]:
    """q(v) = p_v + max over successors of q (calendar-free)."""
    present = set(topo)
    succs: dict[str, list[str]] = {v: [] for v in present}
    for v, ps in _preds(ix, orders, present).items():
        for u in ps:
            succs[u].append(v)
    q: dict[str, int] = {}
    for v in reversed(topo):
        q[v] = ix.op[v].duration + max((q[w] for w in succs[v]), default=0)
    return q


def _reach(ix: _Index, orders: Orders, v: str, forward: bool) -> set[str]:
    """v together with all its descendants (forward) or ancestors."""
    present = {u for seq in orders.values() for u in seq}
    preds = _preds(ix, orders, present)
    nbrs: dict[str, list[str]] = preds
    if forward:
        nbrs = {u: [] for u in present}
        for w, ps in preds.items():
            for u in ps:
                nbrs[u].append(w)
    seen, stack = {v}, [v]
    while stack:
        for u in nbrs[stack.pop()]:
            if u not in seen:
                seen.add(u)
                stack.append(u)
    return seen


def insert_operation(instance: Instance, orders: Orders, v: str, ix: _Index) -> int:
    """Insert operation v into the sequence of its machine at the best
    cycle-free position (see module doc, step 3). Returns the position.

    With jp / js the nearest job predecessor / successor already in the graph,
    putting v between seq[i-1] and seq[i] closes a cycle iff seq[i] is jp or
    an ancestor of jp, or seq[i-1] is js or a descendant of js. Such positions
    are skipped. One always remains: the graph keeps the arc jp -> js while v
    is absent, so it is acyclic and every ancestor of jp precedes every
    descendant of js on the machine."""
    o = ix.op[v]
    m = o.machine
    seq = orders.setdefault(m, [])
    start = evaluate(instance, orders, ix)
    topo = topological_order(ix, orders)
    tails = _tails(ix, orders, topo)
    makespan = max((start[u] + ix.op[u].duration for u in start), default=0)
    jops = ix.job_ops[ix.job_of[v]]
    k = ix.pos[v]
    jp = next((u for u in reversed(jops[:k]) if u in start), None)
    js = next((u for u in jops[k + 1:] if u in start), None)
    no_before = _reach(ix, orders, jp, forward=False) if jp is not None else set()
    no_after = _reach(ix, orders, js, forward=True) if js is not None else set()
    head_job = start[jp] + ix.op[jp].duration if jp is not None else ix.release[ix.job_of[v]]
    tail_job = tails[js] if js is not None else sum(
        ix.op[u].duration for u in jops[k + 1:] if u not in start)
    cal = ix.calendar.get(m, [])
    # committed operations keep their exact start, so nothing may be inserted
    # ahead of one: only positions after the machine's last committed op
    first_free = max((k + 1 for k, u in enumerate(seq) if u in ix.frozen), default=0)
    best = None
    for i in range(first_free, len(seq) + 1):
        if i < len(seq) and seq[i] in no_before:
            continue
        if i > 0 and seq[i - 1] in no_after:
            continue
        head_m = start[seq[i - 1]] + ix.op[seq[i - 1]].duration if i > 0 else 0
        s_v = next_fit(cal, max(head_job, head_m), o.duration)
        tail = max(tails[seq[i]] if i < len(seq) else 0, tail_job)
        through = s_v + o.duration + tail
        key = (max(makespan, through), through, i)
        if best is None or key < best[0]:
            best = (key, i)
    if best is None:
        raise CycleError(f"no cycle-free position for {v}")
    seq.insert(best[1], v)
    return best[1]


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def committed_dispatch(instance: Instance) -> Solution:
    """MWKR dispatching that keeps committed operations at their committed
    starts: their intervals are blocked on their machines like outages, and a
    job's free operations start after its committed ones. Requires every
    committed operation's job predecessors to be committed too (true for the
    prefix commitments of partial_schedule_freeze); raises ScheduleError
    otherwise, since no dispatching order can then be guaranteed feasible."""
    if not instance.frozen_starts:
        return dispatch_mwkr(instance)
    ix = index_instance(instance)
    frozen = ix.frozen
    for jid, ops in ix.job_ops.items():
        seen_free = False
        for v in ops:
            if v in frozen and seen_free:
                raise ScheduleError(f"committed {v} follows an uncommitted operation of {jid}")
            seen_free |= v not in frozen
    blocked: dict[int, list[tuple[int, int]]] = {m: list(c) for m, c in ix.calendar.items()}
    for v, st in frozen.items():
        if v in ix.op:
            blocked.setdefault(ix.op[v].machine, []).append((st, st + ix.op[v].duration))
    for m in blocked:
        blocked[m].sort()
    sol: Solution = {v: st for v, st in frozen.items() if v in ix.op}
    nxt = {j: sum(v in sol for v in ops) for j, ops in ix.job_ops.items()}
    ready = {j: max([ix.release[j]] + [sol[v] + ix.op[v].duration for v in ops if v in sol])
             for j, ops in ix.job_ops.items()}
    rem = {j: sum(ix.op[v].duration for v in ops if v not in sol) for j, ops in ix.job_ops.items()}
    busy: dict[int, list[tuple[int, int]]] = {m: list(b) for m, b in blocked.items()}

    def earliest(m: int, t: int, p: int) -> int:
        for a, b in sorted(busy.get(m, [])):
            if t < b and t + p > a:
                t = b
        return t

    pending = {j for j, ops in ix.job_ops.items() if nxt[j] < len(ops)}
    while pending:
        cands = []
        for j in pending:
            v = ix.job_ops[j][nxt[j]]
            o = ix.op[v]
            cands.append((earliest(o.machine, ready[j], o.duration), -rem[j], j, v))
        t, _, j, v = min(cands)
        o = ix.op[v]
        sol[v] = t
        busy.setdefault(o.machine, []).append((t, t + o.duration))
        ready[j] = t + o.duration
        rem[j] -= o.duration
        nxt[j] += 1
        if nxt[j] >= len(ix.job_ops[j]):
            pending.discard(j)
    return sol


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

@dataclass
class RepairStats:
    delta_kind: str
    n_ops: int = 0
    core_removed: int = 0         # event core operations removed and re-inserted
    new_ops: int = 0
    cancelled_ops: int = 0        # in the previous schedule, absent now
    reused_order_pairs: int = 0   # consecutive machine pairs kept from the previous schedule
    total_order_pairs: int = 0
    changed_machine_arcs: int = 0
    frac_start_changed: float = 0.0
    makespan_before_insertion: int | None = None
    makespan: int | None = None
    wall_s: float = 0.0
    fallback: str | None = None
    notes: list[str] = field(default_factory=list)


def _machine_pairs(orders: Orders) -> set[tuple[str, str]]:
    return {(a, b) for seq in orders.values() for a, b in zip(seq, seq[1:])}


def event_localized_repair(instance: Instance, previous: Solution | None) -> tuple[Solution, RepairStats]:
    t0 = time.perf_counter()
    stats = RepairStats(delta_kind=instance.delta_kind, n_ops=len(instance.all_ops))
    ix = index_instance(instance)
    previous = previous or {}
    try:
        orders = orders_from_schedule(instance, previous, ix)
        prev_pairs = _machine_pairs(orders)
        stats.cancelled_ops = sum(1 for v in previous if v not in ix.op)
        new_ops = [v for v in ix.op if v not in previous]
        stats.new_ops = len(new_ops)
        core = set(new_ops)
        if instance.delta_kind == "outage" and instance.outages:
            # operations that the outage calendar delays under the previous orders
            delayed: set[str] = set()
            evaluate(instance, orders, ix, delayed=delayed)
            core |= delayed - set(ix.frozen)
        for m in orders:
            orders[m] = [v for v in orders[m] if v not in core]
        stats.core_removed = len(core) - len(new_ops)
        stats.makespan_before_insertion = (max((s + ix.op[v].duration for v, s in evaluate(instance, orders, ix).items()), default=0)
                                           if any(orders.values()) else 0)
        jobs = sorted({ix.job_of[v] for v in core},
                      key=lambda j: (-sum(ix.op[u].duration for u in ix.job_ops[j]), j))
        for jid in jobs:
            for v in ix.job_ops[jid]:
                if v in core:
                    insert_operation(instance, orders, v, ix)
        schedule = evaluate(instance, orders, ix)
        stats.makespan = check_schedule(instance, schedule)
    except (CycleError, CommitmentError, ScheduleError) as e:
        stats.fallback = f"{type(e).__name__}: {e}"
        schedule = committed_dispatch(instance)  # raises if no valid fallback exists
        stats.makespan = check_schedule(instance, schedule)
        stats.wall_s = time.perf_counter() - t0
        return schedule, stats
    pairs = _machine_pairs(orders)
    stats.total_order_pairs = len(pairs)
    stats.reused_order_pairs = len(pairs & prev_pairs)
    stats.changed_machine_arcs = len(pairs ^ prev_pairs)
    common = [v for v in schedule if v in previous]
    stats.frac_start_changed = (sum(schedule[v] != previous[v] for v in common) / len(common)) if common else 0.0
    stats.wall_s = time.perf_counter() - t0
    return schedule, stats
