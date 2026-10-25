"""Tests for phase0/cobar_neighborhood.py: max-flow/min-cut against brute
force, the path-hitting and minimality properties of the release cut against
subset enumeration, and the release loop's guarantees."""

import itertools
import random
import sys
from pathlib import Path

from phase0.cobar_certificates import certificate, kept_arcs
from phase0.cobar_neighborhood import (
    INF, max_flow_min_cut, min_release_cut, obstruction, release_obstructions,
)

sys.path.insert(0, str(Path(__file__).parent))
from test_certificates import (  # noqa: E402
    cpsat_optimum, independent_kept_arcs, random_feasible_schedule, random_instance, with_commitments,
)


def _disconnects(n, edges, removed, s, t):
    adj = {i: [] for i in range(n)}
    for i, (u, v, _c) in enumerate(edges):
        if i not in removed:
            adj[u].append(v)
    seen, stack = {s}, [s]
    while stack:
        for w in adj[stack.pop()]:
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return t not in seen


def test_max_flow_equals_brute_force_min_cut():
    rng = random.Random(1)
    for _ in range(300):
        n = rng.randint(3, 7)
        edges = [(u, v, rng.choice([1, 2, 3, INF])) for u in range(n) for v in range(n)
                 if u != v and rng.random() < 0.35]
        if len(edges) > 13:
            edges = edges[:13]
        s, t = 0, n - 1
        flow, cut = max_flow_min_cut(n, edges, s, t)
        best = INF
        for k in range(len(edges) + 1):
            for sub in itertools.combinations(range(len(edges)), k):
                if _disconnects(n, edges, set(sub), s, t):
                    best = min(best, sum(min(edges[i][2], INF) for i in sub))
        if best >= INF:
            assert flow >= INF
        else:
            assert flow == best
            assert _disconnects(n, edges, set(cut), s, t)
            assert sum(edges[i][2] for i in cut) == flow


def _chains(ob):
    succ = {}
    for u, v, k in ob.arcs:
        succ.setdefault(u, []).append((v, (u, v), k))
    sinks = set(ob.sinks)
    out = []

    def walk(v, path):
        if v in sinks:
            out.append(list(path))
        for w, a, k in succ.get(v, []):
            walk(w, path + [(a, k)])
    for s in ob.starts:
        walk(s, [])
    return out


def _decisive_cases(rng, n, outages):
    got = 0
    while got < n:
        inst = random_instance(rng, n_jobs=rng.choice([3, 4]), n_mach=3, outages=outages,
                               releases=rng.random() < 0.5)
        try:
            sched = random_feasible_schedule(rng, inst, slack=0)
        except RuntimeError:  # no schedule within the model's horizon (C5)
            continue
        if rng.random() < 0.2:
            inst = with_commitments(rng, inst, sched, frac=0.2)
        ids = [o.op_id for o in inst.all_ops]
        N = {v for v in ids if rng.random() < rng.choice([0.0, 0.2])}
        cert = certificate(inst, sched, N)
        if cert.decisive and cert.L_path >= cert.U:
            got += 1
            yield inst, sched, N, cert


def test_cut_hits_every_obstructing_chain_and_is_minimum():
    rng = random.Random(7)
    n_finite = 0
    for inst, sched, N, cert in _decisive_cases(rng, 300, outages=True):
        ob = obstruction(inst, sched, N, set(), cert.U)
        chains = _chains(ob)
        assert chains, "a decisive path certificate has at least one obstructing chain"
        cut, cost = min_release_cut(ob)
        if cost >= INF:
            # some chain contains no releasable arc
            assert any(all(k != "machine" for _a, k in ch) for ch in chains)
            continue
        n_finite += 1
        for ch in chains:
            assert any(a in cut for a, _k in ch), "cut misses an obstructing chain"
        best = None
        for k in range(len(ob.releasable) + 1):
            for sub in itertools.combinations(ob.releasable, k):
                if all(any(a in sub for a, _ in ch) for ch in chains):
                    best = k
                    break
            if best is not None:
                break
        assert cost == len(cut) == best
    assert n_finite >= 100


def test_without_outages_one_cut_removes_the_path_obstruction():
    rng = random.Random(9)
    for inst, sched, N, cert in _decisive_cases(rng, 200, outages=False):
        if inst.frozen_starts:
            continue
        ob = obstruction(inst, sched, N, set(), cert.U)
        cut, cost = min_release_cut(ob)
        if cost >= INF:
            continue
        after = certificate(inst, sched, N, cut)
        assert after.L_path < cert.U


def test_release_loop_outcomes_are_consistent_and_sound():
    rng = random.Random(13)
    seen = set()
    for inst, sched, N, cert in _decisive_cases(rng, 250, outages=True):
        for mode in ("arcs", "ops"):
            res = release_obstructions(inst, sched, N, mode=mode)
            seen.add(res.status)
            assert res.before.decisive
            if res.status == "released":
                assert not res.after.decisive
            else:
                assert res.after.decisive
            # the incumbent belongs to the final neighbourhood (certificate checks
            # membership) and the final bound is sound against the exact oracle
            arcs = independent_kept_arcs(inst, sched, res.N, res.R)
            assert sorted(arcs) == sorted(kept_arcs(inst, sched, res.N, res.R))
            opt = cpsat_optimum(inst, arcs)
            assert res.after.L <= opt <= res.after.U
            if res.after.decisive:
                assert opt == res.after.U
            if mode == "ops":
                assert res.R == set() and res.N >= N
            else:
                assert res.N == N
    assert {"released", "unreleasable"} <= seen


def test_single_long_job_is_unreleasable():
    from phase0.streams import Instance, Job, Operation
    jobs = (Job("j0", (Operation("j0_o0", 0, 5), Operation("j0_o1", 1, 5))),
            Job("j1", (Operation("j1_o0", 1, 1),)))
    inst = Instance(index=1, num_machines=2, jobs=jobs)
    sched = {"j0_o0": 0, "j0_o1": 5, "j1_o0": 0}
    res = release_obstructions(inst, sched, set())
    assert res.status == "unreleasable" and res.after.U == 10
