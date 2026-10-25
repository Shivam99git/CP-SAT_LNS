"""Certificate-guided neighbourhood construction (COBAR,
docs/cobar/04_neighborhood_construction.md).

When the certificate of a neighbourhood (N, R) is decisive through its path
bound (L_path = U), every chain of binding constraints that realizes U must
lose a constraint before the restricted problem can contain a better
schedule. `release_obstructions` finds a minimum-cost set of releasable
machine arcs that meets every such chain (an s-t minimum cut of the binding
subgraph, Ford-Fulkerson / Edmonds-Karp), releases it, recomputes the
certificate, and repeats until the certificate is no longer decisive, the
obstruction cannot be released, or an iteration cap is reached.

What this does and does not establish:
  * releasing the cut removes every chain that realized the old bound; the
    recomputed certificate is the only statement about the new neighbourhood
    (with outages a new chain of the same length can appear, hence the loop);
  * a non-decisive certificate does NOT mean an improving schedule exists in
    the new neighbourhood, nor that CP-SAT will find one within its budget.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .cobar_certificates import Arc, Certificate, certificate, heads, kept_arcs
from .event_localized_repair import index_instance
from .streams import Instance

INF = 10 ** 9
Solution = dict[str, int]


def max_flow_min_cut(n: int, edges: list[tuple[int, int, int]], s: int, t: int):
    """Edmonds-Karp on a graph with nodes 0..n-1 and directed edges (u, v, cap).
    Returns (flow value, indices of the edges in a minimum s-t cut: edges from
    the residual-reachable side of s to the other side)."""
    head = [[] for _ in range(n)]
    to, cap = [], []
    for u, v, c in edges:
        head[u].append(len(to)); to.append(v); cap.append(c)
        head[v].append(len(to)); to.append(u); cap.append(0)
    flow = 0
    while True:
        par = [-1] * n
        par[s] = -2
        q = deque([s])
        while q and par[t] == -1:
            u = q.popleft()
            for e in head[u]:
                if cap[e] > 0 and par[to[e]] == -1:
                    par[to[e]] = e
                    q.append(to[e])
        if par[t] == -1:
            break
        aug, v = INF * 4, t
        while v != s:
            e = par[v]
            aug = min(aug, cap[e])
            v = to[e ^ 1]
        v = t
        while v != s:
            e = par[v]
            cap[e] -= aug
            cap[e ^ 1] += aug
            v = to[e ^ 1]
        flow += aug
        if flow >= INF:
            break
    seen = [False] * n
    seen[s] = True
    q = deque([s])
    while q:
        u = q.popleft()
        for e in head[u]:
            if cap[e] > 0 and not seen[to[e]]:
                seen[to[e]] = True
                q.append(to[e])
    cut = [i for i, (u, v, _c) in enumerate(edges) if seen[u] and not seen[v]]
    return flow, cut


@dataclass
class Obstruction:
    """The binding subgraph behind a decisive path certificate."""
    sinks: list[str]                 # operations with h + p = U
    starts: list[str]                # chain starts: bound by release, commitment, outage or 0 (ties included)
    arcs: list[tuple[str, str, str]]  # binding arcs (u, v, "job"|"machine") on chains to a sink
    releasable: list[Arc]            # machine arcs among them that may be released


def obstruction(instance: Instance, incumbent: Solution, N: set[str], R: set[Arc],
                U: int) -> Obstruction:
    ix = index_instance(instance)
    arcs = kept_arcs(instance, incumbent, N, R, ix)
    h, _ready, binding, g, floor_bound = heads(instance, arcs, ix)
    kind = {(u, v): k for v in g.topo for u, k in g.preds[v]}
    sinks = [v for v in g.topo if h[v] + ix.op[v].duration >= U]
    # backward closure over binding arcs from the sinks
    on = set(sinks)
    stack = list(sinks)
    sub = []
    while stack:
        v = stack.pop()
        for u in binding[v]:
            sub.append((u, v, kind[(u, v)]))
            if u not in on:
                on.add(u)
                stack.append(u)
    starts = sorted(v for v in on if floor_bound[v])
    releasable = sorted({(u, v) for u, v, k in sub if k == "machine"})
    return Obstruction(sorted(sinks), starts, sorted(set(sub)), releasable)


def min_release_cut(ob: Obstruction, weight=None) -> tuple[set[Arc], int]:
    """Minimum-cost set of releasable machine arcs meeting every binding chain
    from a chain start to a sink. Cost INF means some chain has no releasable
    arc (job precedence, release dates, commitments or outages only)."""
    weight = weight or (lambda a: 1)
    nodes = sorted({x for u, v, _ in ob.arcs for x in (u, v)} | set(ob.sinks) | set(ob.starts))
    idx = {v: i + 2 for i, v in enumerate(nodes)}
    S, T = 0, 1
    edges, meta = [], []
    for v in ob.starts:
        edges.append((S, idx[v], INF)); meta.append(None)
    for v in ob.sinks:
        edges.append((idx[v], T, INF)); meta.append(None)
    for u, v, k in ob.arcs:
        c = int(weight((u, v))) if k == "machine" else INF
        edges.append((idx[u], idx[v], c)); meta.append((u, v) if k == "machine" else None)
    flow, cut = max_flow_min_cut(len(nodes) + 2, edges, S, T)
    if flow >= INF:
        return set(), INF
    released = {meta[i] for i in cut}
    assert None not in released, "a finite cut contains only releasable arcs"
    return released, flow


@dataclass
class ReleaseResult:
    status: str                     # not_needed | released | unreleasable | machine_obstructed | iteration_cap
    N: set[str]
    R: set[Arc]
    before: Certificate
    after: Certificate
    iterations: int = 0
    cut_cost: int = 0
    added_ops: set[str] = field(default_factory=set)
    time_s: float = 0.0


def release_obstructions(instance: Instance, incumbent: Solution, N: set[str],
                         R: set[Arc] | None = None, mode: str = "arcs", weight=None,
                         max_iter: int = 20) -> ReleaseResult:
    """Release obstructing machine arcs until the certificate of the
    neighbourhood is no longer decisive.

    mode "arcs": released arcs go into R (all other kept arcs stay);
    mode "ops":  the successor operation of each released arc joins N."""
    t0 = time.monotonic()
    N, R = set(N), set(R or set())
    before = cert = certificate(instance, incumbent, N, R)
    status, it, cost, added = "not_needed", 0, 0, set()
    while cert.decisive:
        if cert.L_path < cert.U:              # only the machine bound blocks
            status = "machine_obstructed"
            break
        if it >= max_iter:
            status = "iteration_cap"
            break
        ob = obstruction(instance, incumbent, N, R, cert.U)
        cut, c = min_release_cut(ob, weight)
        if c >= INF:
            status = "unreleasable"
            break
        it += 1
        cost += c
        if mode == "arcs":
            R |= cut
        elif mode == "ops":
            new = {v for _u, v in cut} - N
            added |= new
            N |= new
        else:
            raise ValueError(mode)
        cert = certificate(instance, incumbent, N, R)
        status = "released"
    if status == "released" and cert.decisive:
        status = "iteration_cap"
    return ReleaseResult(status, N, R, before, cert, it, cost, added, time.monotonic() - t0)
