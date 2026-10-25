"""Exact-oracle tests for phase0/cobar_certificates.py.

Two oracles, neither sharing code with the module under test:
  * enumeration: every machine order consistent with the kept arcs, scheduled
    by an independent brute-force earliest-start routine (positive durations);
  * CP-SAT: the restricted research model (job precedence, no-overlap with
    outages, release dates, exact commitments) plus the kept arcs, solved to
    proven optimality (also covers zero-length operations).
A single case with L > C*(N, R), or a decisive certificate with C*(N, R) < U,
fails the test and prints the case.
"""

import itertools
import random

import pytest
from ortools.sat.python import cp_model

from phase0.cobar_certificates import (
    CertificateError, certificate, global_certificate, kept_arcs,
)
from phase0.reuse_methods import build_research_model
from phase0.schedule_validator import check_schedule
from phase0.streams import Instance, Job, Operation, Outage


# ---------------------------------------------------------------- instances

def random_instance(rng, n_jobs=3, n_mach=3, dur=(1, 4), allow_zero=False, outages=True, releases=True):
    jobs = []
    for j in range(n_jobs):
        k = rng.randint(1, n_mach)
        ms = rng.sample(range(n_mach), k)
        lo = 0 if allow_zero else dur[0]
        ops = tuple(Operation(f"j{j}_o{i}", m, rng.randint(lo, dur[1])) for i, m in enumerate(ms))
        jobs.append(Job(f"j{j}", ops, release_date=rng.randint(0, 3) if releases else 0))
    outs = []
    if outages:
        for m in range(n_mach):  # outages on one machine are disjoint (the model requires it)
            t = rng.randint(0, 6)
            for _ in range(rng.randint(0, 2)):
                length = rng.randint(1, 4)
                outs.append(Outage(m, t, t + length))
                t += length + rng.randint(0, 5)
    return Instance(index=1, num_machines=n_mach, jobs=tuple(jobs), outages=tuple(outs))


def _free_at(inst, m, s, p):
    """Independent outage check: [s, s+p) avoids every outage of machine m.
    A zero-length operation may not lie strictly inside an outage: CP-SAT's
    no-overlap forbids it (OR-Tools 9.15, checked in
    test_zero_length_semantics_cpsat_vs_validator), whereas the validator
    allows it; generated schedules satisfy the stricter rule."""
    if p == 0:
        return all(not (o.start < s < o.end) for o in inst.outages if o.machine == m)
    return all(not (s < o.end and s + p > o.start) for o in inst.outages if o.machine == m)


def _earliest(inst, m, t, p):
    while not _free_at(inst, m, t, p):
        t += 1
    return t


def random_feasible_schedule(rng, inst, slack=3):
    """A feasible (generally not semi-active) schedule: random machine orders,
    then each operation started after a random delay."""
    ops = {o.op_id: (j, i, o) for j in inst.jobs for i, o in enumerate(j.ops)}
    for _ in range(200):
        order = {}
        for m in range(inst.num_machines):
            vs = [v for v, (_, _, o) in ops.items() if o.machine == m]
            rng.shuffle(vs)
            order[m] = vs
        start, done, progress = {}, set(), True
        while progress:
            progress = False
            for j in inst.jobs:
                for i, o in enumerate(j.ops):
                    v = o.op_id
                    if v in done:
                        continue
                    if i > 0 and j.ops[i - 1].op_id not in done:
                        break
                    seq = order[o.machine]
                    k = seq.index(v)
                    if k > 0 and seq[k - 1] not in done:
                        break
                    t = j.release_date if i == 0 else start[j.ops[i - 1].op_id] + j.ops[i - 1].duration
                    if k > 0:
                        u = seq[k - 1]
                        t = max(t, start[u] + ops[u][2].duration)
                    t = _earliest(inst, o.machine, t + rng.randint(0, slack), o.duration)
                    start[v] = t
                    done.add(v)
                    progress = True
        if len(done) == len(ops):
            # the CP-SAT model bounds every end by inst.horizon, which release
            # dates and slack can exceed (counterexample C5): keep incumbents
            # the model can represent
            if max(start[v] + ops[v][2].duration for v in ops) <= inst.horizon:
                return start
    raise RuntimeError("no feasible schedule found")


def with_commitments(rng, inst, sched, frac=0.3):
    frozen = {v: s for v, s in sched.items() if rng.random() < frac}
    return Instance(index=inst.index, num_machines=inst.num_machines, jobs=inst.jobs,
                    outages=inst.outages, frozen_ops=frozenset(frozen), frozen_starts=frozen)


def independent_kept_arcs(inst, sched, N, R):
    pos = {o.op_id: i for j in inst.jobs for i, o in enumerate(j.ops)}
    arcs = []
    for m in range(inst.num_machines):
        seq = sorted((o.op_id for o in inst.all_ops if o.machine == m and o.duration > 0),
                     key=lambda v: (sched[v], pos[v], v))
        kept = [v for v in seq if v not in N]
        arcs += [(u, v) for u, v in zip(kept, kept[1:]) if (u, v) not in R]
    return arcs


# ------------------------------------------------------------------ oracles

def enumeration_optimum(inst, arcs):
    """min makespan over all schedules satisfying the instance and `arcs`
    (positive durations): enumerate machine orders, schedule earliest-start."""
    ops = {o.op_id: o for o in inst.all_ops}
    jpred, first_rel = {}, {}
    for j in inst.jobs:
        for i, o in enumerate(j.ops):
            jpred[o.op_id] = j.ops[i - 1].op_id if i else None
            first_rel[o.op_id] = j.release_date if i == 0 else 0
    by_m = {m: [v for v, o in ops.items() if o.machine == m] for m in range(inst.num_machines)}
    best = None
    for combo in itertools.product(*[itertools.permutations(vs) for vs in by_m.values()]):
        posm = {v: k for seq in combo for k, v in enumerate(seq)}
        if any(posm[u] > posm[v] for u, v in arcs):
            continue
        mpred = {seq[k]: (seq[k - 1] if k else None) for seq in combo for k in range(len(seq))}
        start, ok = {}, True
        pending = set(ops)
        while pending and ok:
            moved = False
            for v in sorted(pending):
                ps = [p for p in (jpred[v], mpred[v]) if p is not None]
                ps += [u for u, w in arcs if w == v]
                if any(p not in start for p in ps):
                    continue
                t = max([first_rel[v]] + [start[p] + ops[p].duration for p in ps])
                t = _earliest(inst, ops[v].machine, t, ops[v].duration)
                if v in inst.frozen_starts:
                    if t > inst.frozen_starts[v]:
                        ok = False
                        break
                    t = inst.frozen_starts[v]
                    if not _free_at(inst, ops[v].machine, t, ops[v].duration):
                        ok = False
                        break
                start[v] = t
                pending.discard(v)
                moved = True
            if not moved and pending:
                ok = False  # cyclic order
        if ok:
            # the order's machine arcs are satisfied by construction; check overlap once more
            mk = max(start[v] + ops[v].duration for v in ops)
            best = mk if best is None else min(best, mk)
    return best


def cpsat_optimum(inst, arcs):
    b = build_research_model(inst)
    dur = {o.op_id: o.duration for o in inst.all_ops}
    for u, v in arcs:
        b.model.add(b.starts[v] >= b.starts[u] + dur[u])
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.max_time_in_seconds = 30
    st = s.solve(b.model)
    assert st in (cp_model.OPTIMAL, cp_model.INFEASIBLE), s.status_name(st)
    return None if st == cp_model.INFEASIBLE else int(s.objective_value)


def _random_N_R(rng, inst, sched):
    ids = [o.op_id for o in inst.all_ops]
    N = {v for v in ids if rng.random() < rng.choice([0.0, 0.2, 0.5, 1.0])}
    full = independent_kept_arcs(inst, sched, N, set())
    R = {a for a in full if rng.random() < 0.3}
    return N, R


# -------------------------------------------------------------------- tests

def _check_case(inst, sched, N, R, oracle, stats):
    U = check_schedule(inst, sched)
    arcs = independent_kept_arcs(inst, sched, N, R)
    assert sorted(kept_arcs(inst, sched, N, R)) == sorted(arcs)
    cert = certificate(inst, sched, N, R)
    opt = oracle(inst, arcs)
    assert opt is not None, "incumbent should be feasible for its own restriction"
    assert opt <= U
    case = dict(inst=inst, sched=sched, N=N, R=R, cert=cert, opt=opt)
    assert cert.L <= opt, f"UNSOUND BOUND {case}"
    assert cert.U == U
    if cert.decisive:
        assert opt >= U, f"FALSE CERTIFICATE {case}"
        stats["decisive"] += 1
    stats["cases"] += 1
    stats["tight"] += cert.L == opt


def test_bound_sound_against_enumeration():
    rng = random.Random(11)
    stats = {"cases": 0, "decisive": 0, "tight": 0}
    while stats["cases"] < 400:
        inst = random_instance(rng, n_jobs=rng.choice([2, 3]), n_mach=3)
        sched = random_feasible_schedule(rng, inst, slack=rng.choice([0, 0, 2]))
        if rng.random() < 0.3:
            inst = with_commitments(rng, inst, sched)
        N, R = _random_N_R(rng, inst, sched)
        _check_case(inst, sched, N, R, enumeration_optimum, stats)
    print(stats)
    assert stats["decisive"] >= 50  # the test must exercise decisive certificates


def test_bound_sound_against_cpsat_with_zero_durations():
    rng = random.Random(23)
    stats = {"cases": 0, "decisive": 0, "tight": 0}
    while stats["cases"] < 200:
        inst = random_instance(rng, n_jobs=rng.choice([3, 4]), n_mach=3, allow_zero=True)
        sched = random_feasible_schedule(rng, inst, slack=rng.choice([0, 0, 2]))
        if rng.random() < 0.3:
            inst = with_commitments(rng, inst, sched)
        N, R = _random_N_R(rng, inst, sched)
        _check_case(inst, sched, N, R, cpsat_optimum, stats)
    print(stats)
    assert stats["decisive"] >= 20


def test_global_certificate_sound():
    rng = random.Random(5)
    n_dec = 0
    for _ in range(150):
        inst = random_instance(rng, n_jobs=3, n_mach=3)
        sched = random_feasible_schedule(rng, inst, slack=0)
        cert = global_certificate(inst, sched)
        opt = cpsat_optimum(inst, [])
        assert cert.L <= opt
        if cert.decisive:
            assert opt == cert.U
            n_dec += 1
    assert n_dec >= 5


def test_semi_active_incumbent_with_all_arcs_kept_is_certified():
    # N = R = {} on a semi-active incumbent: the kept arcs are its own orders,
    # whose earliest-start schedule is the incumbent itself, so L_path = U.
    rng = random.Random(3)
    for _ in range(50):
        inst = random_instance(rng)
        sched = random_feasible_schedule(rng, inst, slack=0)
        cert = certificate(inst, sched, set())
        assert cert.L_path == cert.U and cert.decisive


def test_machine_bound_decisive_where_path_bound_is_not():
    # one machine, three single-operation jobs: no arcs once N = all; the path
    # bound is max duration, the machine bound is the total load.
    jobs = tuple(Job(f"j{i}", (Operation(f"j{i}_o0", 0, 3),)) for i in range(3))
    inst = Instance(index=1, num_machines=1, jobs=jobs)
    sched = {"j0_o0": 0, "j1_o0": 3, "j2_o0": 6}
    cert = certificate(inst, sched, set(sched))
    assert (cert.L_path, cert.L_mach, cert.kind) == (3, 9, "machine")


def test_zero_length_operation_inside_outage_is_not_pushed():
    jobs = (Job("j0", (Operation("j0_o0", 0, 0), Operation("j0_o1", 1, 2))),)
    inst = Instance(index=1, num_machines=2, jobs=jobs, outages=(Outage(0, 0, 5),))
    sched = {"j0_o0": 1, "j0_o1": 1}
    assert check_schedule(inst, sched) == 3
    cert = certificate(inst, sched, set())
    assert cert.L == 2 and cert.L <= cpsat_optimum(inst, [])


def test_invalid_inputs_rejected():
    jobs = (Job("j0", (Operation("j0_o0", 0, 2),)), Job("j1", (Operation("j1_o0", 0, 2),)))
    inst = Instance(index=1, num_machines=1, jobs=jobs)
    with pytest.raises(Exception):  # overlapping incumbent: infeasible
        certificate(inst, {"j0_o0": 0, "j1_o0": 1}, set())
    sched = {"j0_o0": 0, "j1_o0": 2}
    with pytest.raises(CertificateError):  # released arcs cannot create a cycle, but given ones can
        from phase0.cobar_certificates import heads
        heads(inst, [("j0_o0", "j1_o0"), ("j1_o0", "j0_o0")])
    assert certificate(inst, sched, set()).decisive


def test_zero_length_semantics_cpsat_vs_validator():
    """Documents a semantic difference (counterexample C4 in 03_certificate_theory.md):
    the validator accepts a zero-length operation strictly inside an outage,
    CP-SAT's no-overlap does not. Bounds are checked against CP-SAT, the
    stricter model, so they stay valid for the model the methods solve."""
    jobs = (Job("j0", (Operation("j0_o0", 0, 0),)),)
    inst = Instance(index=1, num_machines=1, jobs=jobs, outages=(Outage(0, 6, 9),))
    assert check_schedule(inst, {"j0_o0": 7}) == 7
    b = build_research_model(inst)
    b.model.add(b.starts["j0_o0"] == 7)
    assert cp_model.CpSolver().solve(b.model) == cp_model.INFEASIBLE
