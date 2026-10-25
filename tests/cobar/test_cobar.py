"""Integration tests for phase0/cobar.py and phase0/cobar_budget_policy.py."""

import random

import pytest
from ortools.sat.python import cp_model

from phase0.cobar import COBARConfig, build_cobar_restricted_model, run_cobar
from phase0.cobar_budget_policy import Features, PolicyConfig, decide
from phase0.cobar_certificates import kept_arcs
from phase0.model_builder import build_model, solve
from phase0.reuse_methods import Clock, RunResult, build_research_model, run_cpsat
from phase0.run_gate1 import StreamSpec
from phase0.run_iaip_campaign import parse_cobar
from phase0.schedule_validator import check_schedule
from phase0.selective_reoptimization import build_restricted_model, make_neighbourhood, disruption_set

ABLATIONS = {  # the method strings used in the experiments (docs/cobar/05, 07)
    "A2": "cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=fixed",
    "A3": "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=0|global_certificate=0|policy=fixed",
    "A4": "cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=budget",
    "A5": "cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=cert+budget",
    "A6": "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=cert+budget",
    "A8": "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=fixed",
    "A9": "cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave",
}


def _stream(m=6, seed=4, length=4):
    return StreamSpec(m, m, seed, length).build()


@pytest.mark.parametrize("name", sorted(ABLATIONS))
def test_every_configuration_returns_validated_schedules_within_the_deadline(name):
    cfg = parse_cobar(ABLATIONS[name])
    stream = _stream()
    prev = prev_inst = None
    for inst in stream:
        res, meta = run_cobar(inst, prev, prev_inst, 1.0, cfg, 1, 0, name)
        assert res.validated and check_schedule(inst, res.solution) == res.objective
        ts = [e[0] for e in res.events]
        objs = [e[1] for e in res.events]
        assert ts == sorted(ts) and all(a > b for a, b in zip(objs, objs[1:]))
        assert res.events[-1][1] == res.objective
        assert 0 < ts[0] and res.total_s <= 1.0 + 0.3
        assert res.construction_s > 0
        if "local" in meta:
            assert meta["decision"]["run_local"]
            assert meta["local"]["local_time_s"] <= meta["decision"]["alpha"] * 1.0 + 0.05
        prev, prev_inst = res.solution, inst


def test_budget_policy_skips_local_stage_with_four_workers_and_short_budgets():
    cfg = parse_cobar(ABLATIONS["A4"])
    stream = _stream()
    prev, _ = solve(build_model(stream[0]), time_limit=0.3)[:2]
    _, meta = run_cobar(stream[1], prev, stream[0], 1.0, cfg, 4, 0)
    assert "local" not in meta and "workers" in meta["decision"]["reason"]
    _, meta = run_cobar(stream[1], prev, stream[0], 1.0, cfg, 1, 0)   # B = 1 < min_budget_s = 4
    assert "local" not in meta and "budget" in meta["decision"]["reason"]


def test_decide_rules():
    base = dict(budget=8.0, workers=1, elapsed=0.05, U=100, L=50, certified_non_improving=False,
                neighbourhood_size=10, n_ops=40, new_ops=True)
    f = Features(**base)
    assert decide(f, PolicyConfig("fixed")).local_end == pytest.approx(4.8)
    assert not decide(Features(**{**base, "workers": 4}), PolicyConfig("budget")).run_local
    assert not decide(Features(**{**base, "budget": 2.0}), PolicyConfig("budget")).run_local
    assert decide(Features(**{**base, "workers": 4}), PolicyConfig("certificate")).run_local
    assert not decide(Features(**{**base, "certified_non_improving": True}), PolicyConfig("certificate")).run_local
    short = decide(Features(**{**base, "L": 99}), PolicyConfig("certificate", gap_threshold=0.02))
    assert short.run_local and short.alpha == 0.2
    assert not decide(Features(**{**base, "elapsed": 5.0}), PolicyConfig("fixed")).run_local
    assert not decide(Features(**{**base, "neighbourhood_size": 0}), PolicyConfig("fixed")).run_local
    with pytest.raises(ValueError):
        decide(f, PolicyConfig("bandit"))


def test_global_certificate_skips_solvers_only_for_optimal_incumbents():
    cfg = parse_cobar(ABLATIONS["A6"])
    rng = random.Random(0)
    n_cert = 0
    for seed in range(12):
        stream = StreamSpec(3, 3, seed, 2).build()
        prev = prev_inst = None
        for inst in stream:
            res, meta = run_cobar(inst, prev, prev_inst, 0.5, cfg, 1, rng.randint(0, 9))
            if meta.get("global_certificate", {}).get("decisive"):
                n_cert += 1
                assert res.solver_status == "CERTIFIED_OPTIMAL" and "global" not in meta
                b = build_research_model(inst)
                s = cp_model.CpSolver()
                s.parameters.max_time_in_seconds = 20
                assert s.solve(b.model) == cp_model.OPTIMAL
                assert int(s.objective_value) == res.objective
            prev, prev_inst = res.solution, inst
    assert n_cert >= 1


def test_restricted_model_contains_incumbent_and_matches_iaip_for_positive_durations():
    stream = _stream(m=8, seed=7, length=3)
    prev = solve(build_model(stream[0]), time_limit=0.3)[0]
    for inst, prev_inst in zip(stream[1:], stream):
        inc = solve(build_model(inst), time_limit=0.3)[0]
        U = check_schedule(inst, inc)
        D = disruption_set(prev_inst, inst, prev)
        N = make_neighbourhood("N5", inst, inc, D, 0.25)
        built, _ = build_cobar_restricted_model(inst, inc, N, set(), False, U)
        for v, s in inc.items():
            built.model.add(built.starts[v] == s)
        assert cp_model.CpSolver().solve(built.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # same kept arcs as IAIP-SR's builder (all durations are positive here)
        ref, n_ref = build_restricted_model(inst, inc, N, False, U)
        assert n_ref == len(kept_arcs(inst, inc, N))
        prev = inc


def test_stall_stop_ends_search_early_and_keeps_validated_incumbent():
    inst = StreamSpec(20, 20, 3, 1).build()[0]
    clock = Clock(5.0)
    res = RunResult(method="t", budget=5.0)
    run_cpsat(res, clock, inst, None, 1, 0, stall_s=0.2)
    assert res.objective is not None and check_schedule(inst, res.solution) == res.objective
    assert any("stopped after" in n for n in res.notes) or res.solver_status == "OPTIMAL"
    assert clock.elapsed() < 4.5


def test_interleave_parameter_reaches_the_solver():
    inst = StreamSpec(8, 8, 3, 1).build()[0]
    res = RunResult(method="t", budget=1.0)
    run_cpsat(res, Clock(1.0), inst, None, 1, 0, params={"interleave_search": True})
    assert res.validated is False and res.objective is not None  # _finish not called here
    with pytest.raises(Exception):
        run_cpsat(RunResult(method="t", budget=1.0), Clock(1.0), inst, None, 1, 0,
                  params={"no_such_parameter": True})


def test_multi_round_local_stage_stays_inside_the_local_window():
    cfg = parse_cobar("cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0"
                      "|policy=fixed|alpha=0.6|rounds=5")
    stream = StreamSpec(12, 12, 5, 3).build()
    prev = prev_inst = None
    n_rounds = 0
    for inst in stream:
        res, meta = run_cobar(inst, prev, prev_inst, 2.0, cfg, 1, 0)
        assert res.validated
        if "local" in meta:
            assert meta["stage_s"]["local_s"] <= 0.6 * 2.0 + 0.1
            n_rounds += len(meta["rounds"])
            for r in meta["rounds"]:
                assert r["size"] > 0
        prev, prev_inst = res.solution, inst
    print("extra rounds", n_rounds)
