"""Tests for selective reoptimization and the integrated method, including an
exact enumeration oracle on tiny instances.

    .venv/bin/python -m pytest tests/test_selective_reoptimization.py -q
"""

import itertools
import random
from dataclasses import replace

import pytest

from phase0.event_localized_repair import CycleError, evaluate
from phase0.impact_aware_reoptimization import IAIPConfig, run_iaip
from phase0.model_builder import build_model, solve
from phase0.reuse_methods import Clock, RunResult, build_research_model, run_cpsat
from phase0.schedule_validator import check_schedule
from phase0.selective_reoptimization import (
    build_restricted_model, disruption_set, make_neighbourhood, selective_solve,
)
from phase0.streams import Instance, Job, Operation, Outage, StreamConfig, generate_stream


def _tiny(rng, j=3, m=2, outage=True):
    jobs = tuple(Job(f"j{k}", tuple(Operation(f"j{k}_o{i}", ms, rng.randint(1, 6))
                                    for i, ms in enumerate(rng.sample(range(m), m))))
                 for k in range(j))
    outs = (Outage(rng.randrange(m), rng.randint(0, 8), rng.randint(9, 12)),) if outage else ()
    return Instance(0, m, jobs, outs)


def _enumerate_optimum(inst):
    """Exact optimum by enumerating every machine order (independent of CP-SAT)."""
    by_m = {}
    for o in inst.all_ops:
        by_m.setdefault(o.machine, []).append(o.op_id)
    machines = sorted(by_m)
    best = None
    for perms in itertools.product(*(itertools.permutations(by_m[m]) for m in machines)):
        try:
            s = evaluate(inst, {m: list(p) for m, p in zip(machines, perms)})
        except CycleError:
            continue
        mk = check_schedule(inst, s)
        best = mk if best is None else min(best, mk)
    return best


def test_cpsat_model_optimum_matches_enumeration():
    rng = random.Random(0)
    for _ in range(40):
        inst = _tiny(rng)
        sol, obj, status = solve(build_research_model(inst), time_limit=10)
        assert check_schedule(inst, sol) == obj
        assert obj == _enumerate_optimum(inst)


def _stream(seed=2, m=6, kinds=None, length=5):
    cfg = StreamConfig(num_machines=m, initial_jobs=m, stream_length=length, seed=seed)
    cfg.ops_per_job, cfg.duration_range = (m, m), (5, 50)
    if kinds:
        for f in ("p_arrival", "p_cancellation", "p_duration_jitter", "p_outage"):
            setattr(cfg, f, 0.0)
        for k in kinds:
            setattr(cfg, f"p_{k}", 1.0)
    return generate_stream(cfg)


def _restricted_opt(inst, inc, N, improve):
    built, _ = build_restricted_model(inst, inc, N, improve, check_schedule(inst, inc))
    sol, obj, status = solve(built, time_limit=5)
    return sol, obj, status


def test_restriction_contains_incumbent_and_empty_neighbourhood_is_fixed_orders():
    stream = _stream()
    inc, _, _ = solve(build_model(stream[1]), time_limit=0.2)
    inst = stream[1]
    sol, obj, _ = _restricted_opt(inst, inc, set(), improve=False)
    assert obj <= check_schedule(inst, inc)
    from phase0.event_localized_repair import orders_from_schedule
    assert obj == check_schedule(inst, evaluate(inst, orders_from_schedule(inst, inc)))


def test_full_neighbourhood_equals_unrestricted_optimum():
    rng = random.Random(4)
    for _ in range(15):
        inst = _tiny(rng, j=3, m=3, outage=False)
        inc, _, _ = solve(build_model(inst), time_limit=0.01)
        _, obj, _ = _restricted_opt(inst, inc, {o.op_id for o in inst.all_ops}, improve=False)
        assert obj == _enumerate_optimum(inst)


def test_require_improvement_on_optimal_incumbent_is_infeasible():
    rng = random.Random(7)
    inst = _tiny(rng, j=3, m=3)
    opt, _, _ = solve(build_research_model(inst), time_limit=10)
    _, obj, status = _restricted_opt(inst, opt, {o.op_id for o in inst.all_ops}, improve=True)
    from ortools.sat.python import cp_model
    assert obj is None and status == cp_model.INFEASIBLE


def test_selective_solve_never_worsens_and_validates():
    stream = _stream(length=4)
    for inst in stream[1:]:
        for N in (set(), {o.op_id for o in inst.all_ops[:5]}, {o.op_id for o in inst.all_ops}):
            clock = Clock(1.0)
            res = RunResult(method="t", budget=1.0)
            inc, _, _ = solve(build_model(inst), time_limit=0.05)
            res.objective, res.solution = check_schedule(inst, inc), inc
            res.events.append((clock.elapsed(), res.objective, "inc"))
            before = res.objective
            meta = selective_solve(res, clock, inst, N, clock.t0 + 0.5, 1, 0)
            assert res.objective <= before
            assert check_schedule(inst, res.solution) == res.objective
            assert meta["local_time_s"] <= 0.5 + 0.2


def test_disruption_set_per_delta():
    for kind in ("arrival", "cancellation", "duration_jitter", "outage"):
        stream = _stream(seed=3, kinds=[kind], length=3)
        prev, _, _ = solve(build_model(stream[0]), time_limit=0.2)
        D = disruption_set(stream[0], stream[1], prev)
        new_ids = {o.op_id for o in stream[1].all_ops}
        old = {o.op_id: o for o in stream[0].all_ops}
        assert D <= new_ids
        if kind == "arrival":
            assert D == new_ids - set(old)
        if kind == "duration_jitter":
            assert D == {o.op_id for o in stream[1].all_ops if old[o.op_id].duration != o.duration}
        if kind == "cancellation":
            assert D and not (D & (set(old) - new_ids))


@pytest.mark.parametrize("cfg", [
    IAIPConfig(), IAIPConfig(portfolio="fresh"), IAIPConfig(portfolio="elr", alpha=0.2),
    IAIPConfig(alpha=0.2, neighbourhood="N1"), IAIPConfig(alpha=0.2, neighbourhood="N3"),
    IAIPConfig(alpha=0.4, neighbourhood="N4", global_mode="cutoff"),
    IAIPConfig(alpha=0.1, neighbourhood="random", global_mode="hinted"),
])
def test_integrated_runs_are_valid_monotone_and_on_deadline(cfg):
    stream = _stream(length=4)
    prev, prev_inst = None, None
    for inst in stream:
        res, meta = run_iaip(inst, prev, prev_inst, 0.6, cfg)
        assert res.validated and check_schedule(inst, res.solution) == res.objective
        objs = [e[1] for e in res.events]
        ts = [e[0] for e in res.events]
        assert ts == sorted(ts) and all(a > b for a, b in zip(objs, objs[1:]))
        assert res.events[0][0] > 0.0  # never attributed to t = 0
        assert res.total_s <= 0.6 + 0.3
        if "local" in meta:
            assert meta["local"]["local_time_s"] <= cfg.alpha * 0.6 + 0.2
        prev, prev_inst = res.solution, inst


def test_integrated_respects_commitments_and_release_dates():
    stream = _stream(seed=9, kinds=["arrival"], length=2)
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.2)
    inst = stream[1]
    surv = sorted((v for v in prev if v in {o.op_id for o in inst.all_ops}), key=prev.get)
    frozen = {v: prev[v] for v in surv[: len(surv) // 3]}
    jobs = inst.jobs[:-1] + (replace(inst.jobs[-1], release_date=40),)
    inst2 = replace(inst, jobs=jobs, frozen_ops=frozenset(frozen), frozen_starts=frozen)
    for cfg in (IAIPConfig(), IAIPConfig(alpha=0.3, neighbourhood="N4")):
        res, _ = run_iaip(inst2, prev, stream[0], 0.8, cfg)
        assert check_schedule(inst2, res.solution) == res.objective
        assert all(res.solution[v] == s for v, s in frozen.items())


def test_alpha_rule_new_ops_skips_local_phase_without_arrivals():
    for kind, expect_local in (("cancellation", False), ("arrival", True)):
        stream = _stream(seed=5, kinds=[kind], length=2)
        prev, _, _ = solve(build_model(stream[0]), time_limit=0.2)
        res, meta = run_iaip(stream[1], prev, stream[0], 0.6,
                             IAIPConfig(alpha=0.2, neighbourhood="N1", alpha_rule="new_ops"))
        assert ("local" in meta) == expect_local
        assert res.validated


def test_portfolio_incumbent_published_before_all_members_built():
    stream = _stream(length=2)
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.2)
    res, meta = run_iaip(stream[1], prev, stream[0], 0.6, IAIPConfig(portfolio="full"))
    first = res.events[0]
    assert first[2].startswith("portfolio:")
    assert first[0] < res.construction_s + 1e-9  # available before construction finished
