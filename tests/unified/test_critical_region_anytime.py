"""Tests for phase0/critical_region_anytime.py (docs/unified_icaps/05_verification.md)."""

import random
import sys
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from phase0.cobar import COBARConfig, _neighbourhood, build_cobar_restricted_model
from phase0.cobar_certificates import kept_arcs
from phase0.critical_region_anytime import (
    STRATEGIES, CRGARConfig, critical_structure, make_round_neighbourhood, run_crgar,
)
from phase0.model_builder import build_model, solve
from phase0.reuse_methods import build_research_model
from phase0.run_gate1 import StreamSpec
from phase0.run_iaip_campaign import CampaignSpec, parse_crgar
from phase0.schedule_validator import check_schedule
from phase0.selective_reoptimization import disruption_set

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cobar"))
from test_certificates import random_feasible_schedule, random_instance, with_commitments  # noqa: E402


def _incumbent(inst, t=0.3):
    return solve(build_model(inst), time_limit=t)[0]


def _check_run(res, B):
    assert res.validated and check_schedule  # validated by _finish with the validator
    ts = [e[0] for e in res.events]
    objs = [e[1] for e in res.events]
    assert ts == sorted(ts) and ts[0] > 0
    assert all(a > b for a, b in zip(objs, objs[1:])), "retained objective must strictly improve per event"
    assert objs[-1] == res.objective
    assert res.total_s <= B + 0.3


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_strategy_runs_valid_and_within_the_deadline(strategy):
    cfg = parse_crgar(f"crgar|strategy={strategy}")
    stream = StreamSpec(8, 8, 11, 3).build()
    prev = prev_inst = None
    for inst in stream:
        res, meta = run_crgar(inst, prev, prev_inst, 1.2, cfg, 1, 0)
        _check_run(res, 1.2)
        assert check_schedule(inst, res.solution) == res.objective
        for r in meta["rounds"]:
            if r.get("empty"):
                continue
            assert r["objective_after"] <= r["objective_before"]
            assert r["time_s"] <= 0.6 * 1.2 + 0.1
        prev, prev_inst = res.solution, inst


def test_crit_expand_equals_cobar_critical_expand():
    stream = StreamSpec(12, 12, 3, 4).build()
    prev = _incumbent(stream[0])
    for inst, pi in zip(stream[1:], stream):
        S = _incumbent(inst)
        D = disruption_set(pi, inst, prev)
        a, _, _ = make_round_neighbourhood("crit_expand", inst, S, D, 0.25, 0)
        b, _, _ = _neighbourhood(COBARConfig(neighbourhood="critical+expand"), inst, S, D, {})
        assert a == b
        prev = S


def test_size_matching_of_controls():
    stream = StreamSpec(15, 15, 5, 3).build()
    for inst in stream[1:]:
        S = _incumbent(inst)
        Nc, _, ic = make_round_neighbourhood("crit_expand", inst, S, set(), 0.25, 0)
        for strat in ("random_matched", "time_window"):
            N, R, info = make_round_neighbourhood(strat, inst, S, set(), 0.25, 0)
            assert len(N) == len(Nc) == info["matched_target_ops"] and not R
        N, R, info = make_round_neighbourhood("precedence", inst, S, set(), 0.25, 0)
        assert not N and info["machine_arcs_released"] == ic["machine_arcs_released"] == len(R)


def test_round_neighbourhoods_are_deterministic_and_round_dependent():
    inst = StreamSpec(10, 10, 2, 1).build()[1]
    S = _incumbent(inst)
    for strat in ("random_matched", "time_window", "precedence", "random_bfs"):
        a = make_round_neighbourhood(strat, inst, S, set(), 0.25, 0)[:2]
        assert a == make_round_neighbourhood(strat, inst, S, set(), 0.25, 0)[:2]
        assert a != make_round_neighbourhood(strat, inst, S, set(), 0.25, 1)[:2]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_restricted_models_contain_incumbent_and_are_not_relaxations(strategy):
    """Tiny instances with outages, releases and commitments: the incumbent is
    feasible for the restricted model, and the restricted optimum is >= the
    full optimum and its schedule satisfies the instance."""
    rng = random.Random(hash(strategy) % 1000)
    done = 0
    while done < 25:
        inst = random_instance(rng, n_jobs=3, n_mach=3)
        try:
            S = random_feasible_schedule(rng, inst, slack=rng.choice([0, 2]))
        except RuntimeError:
            continue
        if rng.random() < 0.3:
            inst = with_commitments(rng, inst, S)
        U = check_schedule(inst, S)
        N, R, _ = make_round_neighbourhood(strategy, inst, S, set(), 0.5, 0)
        built, _ = build_cobar_restricted_model(inst, S, N, R, False, U)
        fix = build_cobar_restricted_model(inst, S, N, R, False, U)[0]
        for v, s in S.items():
            fix.model.add(fix.starts[v] == s)
        assert cp_model.CpSolver().solve(fix.model) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        sv = cp_model.CpSolver()
        assert sv.solve(built.model) == cp_model.OPTIMAL
        sol = {v: int(sv.value(x)) for v, x in built.starts.items()}
        restricted_opt = check_schedule(inst, sol)
        full = build_research_model(inst)
        sf = cp_model.CpSolver()
        assert sf.solve(full.model) == cp_model.OPTIMAL
        assert int(sf.objective_value) <= restricted_opt <= U
        for u, v in kept_arcs(inst, S, N, R):          # the kept order is really enforced
            assert sol[v] >= sol[u] + next(o.duration for o in inst.all_ops if o.op_id == u)
        done += 1


def test_stop_on_fail_and_fixed_round_protocol():
    stream = StreamSpec(12, 12, 8, 2).build()
    m1 = CRGARConfig(strategy="crit_expand")
    m2 = CRGARConfig(strategy="crit_expand", stop_on_fail=False, round_time=0.15, max_rounds=4)
    prev = prev_inst = None
    for inst in stream:
        r1, meta1 = run_crgar(inst, prev, prev_inst, 2.0, m1, 1, 0)
        r2, meta2 = run_crgar(inst, prev, prev_inst, 2.0, m2, 1, 0)
        for r in meta1["rounds"][:-1]:
            assert r.get("improved"), "M1 continues only after an improving round"
        for r in meta2["rounds"]:
            if not r.get("empty"):
                assert r["time_s"] <= 0.15 + 0.08
        _check_run(r1, 2.0)
        _check_run(r2, 2.0)
        prev, prev_inst = r1.solution, inst


def test_frozen_neighbourhood_is_reused_when_recompute_is_off():
    stream = StreamSpec(12, 12, 9, 2).build()
    cfg = CRGARConfig(strategy="crit_expand", recompute=False, stop_on_fail=False, round_time=0.1, max_rounds=4)
    prev = _incumbent(stream[0])
    res, meta = run_crgar(stream[1], prev, stream[0], 2.0, cfg, 1, 0)
    rs = [r for r in meta["rounds"] if not r.get("empty")]
    assert len({r["n_released_ops"] for r in rs}) <= 1 and len({r["U"] for r in rs}) <= 1
    _check_run(res, 2.0)


def test_no_initial_stage_and_no_final_global_variants():
    stream = StreamSpec(10, 10, 4, 2).build()
    prev = _incumbent(stream[0])
    r, meta = run_crgar(stream[1], prev, stream[0], 1.5, CRGARConfig(initial_stage=False), 1, 0)
    assert "initial_stage" not in meta
    _check_run(r, 1.5)
    r, meta = run_crgar(stream[1], prev, stream[0], 1.5, CRGARConfig(final_global=False, stop_on_fail=False), 1, 0)
    assert "global" not in meta
    _check_run(r, 1.5)


def test_no_initial_incumbent_skips_rounds_and_global_still_solves():
    inst = StreamSpec(6, 6, 1, 1).build()[0]
    r, meta = run_crgar(inst, None, None, 1.0, CRGARConfig(portfolio="hist"), 1, 0)
    assert meta["portfolio"]["objective"] is None and not meta["rounds"] and "initial_stage" not in meta
    assert r.validated and r.objective is not None


def test_time_exhaustion_and_multiworker_execution():
    inst = StreamSpec(15, 15, 6, 1).build()[1]
    prev = _incumbent(StreamSpec(15, 15, 6, 1).build()[0])
    r, meta = run_crgar(inst, prev, StreamSpec(15, 15, 6, 1).build()[0], 0.2, CRGARConfig(), 1, 0)
    assert r.validated and r.total_s <= 0.2 + 0.3
    r, meta = run_crgar(inst, prev, StreamSpec(15, 15, 6, 1).build()[0], 1.0, CRGARConfig(), 4, 0)
    _check_run(r, 1.0)


def test_empty_critical_region_is_handled():
    from phase0.streams import Instance, Job, Operation
    inst = Instance(index=1, num_machines=1, jobs=(Job("j0", (Operation("j0_o0", 0, 3),)),))
    S = {"j0_o0": 0}
    cs = critical_structure(inst, S)
    assert cs["chain_ops"] == {"j0_o0"}
    r, meta = run_crgar(inst, S, inst, 0.5, CRGARConfig(), 1, 0)
    assert r.validated and r.objective == 3


def test_benchmark_stream_runs_valid():
    spec = CampaignSpec(15, 15, 3, 2, base_path="tests/fixtures/benchmarks_real/taillard/ta01.txt")
    stream = spec.build()
    prev = prev_inst = None
    for inst in stream:
        r, _ = run_crgar(inst, prev, prev_inst, 1.0, CRGARConfig(strategy="time_window"), 1, 0)
        _check_run(r, 1.0)
        prev, prev_inst = r.solution, inst


def test_campaign_resume_skips_finished_tasks_and_keeps_files(tmp_path):
    import hashlib
    import subprocess
    cmd = [sys.executable, "-m", "phase0.run_iaip_campaign", "--out", str(tmp_path), "--tag", "t", "--sizes", "6",
           "--stream-seeds", "1", "--stream-length", "2", "--budget", "0.3", "--cpus", "0",
           "--methods", "crgar|strategy=crit_expand", "crgar|strategy=random_matched"]
    subprocess.run(cmd, check=True, capture_output=True)
    f = next((tmp_path / "runs").glob("*.jsonl"))
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    assert "1 done, 0 to run" in out
    assert hashlib.sha256(f.read_bytes()).hexdigest() == h


def test_trajectory_reconstruction_matches_independent_integrator():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/unified"))
    from verify_baseline import own_pi
    from phase0.analyze_gate1 import per_run
    stream = StreamSpec(10, 10, 12, 2).build()
    prev = prev_inst = None
    for inst in stream:
        r, _ = run_crgar(inst, prev, prev_inst, 1.0, CRGARConfig(), 1, 0)
        rec = {"budget": r.budget, "events": [list(e) for e in r.events]}
        z = r.objective - 3
        assert abs(per_run(rec, z)["pi"] - own_pi(rec["events"], z, r.budget)) < 1e-12
        prev, prev_inst = r.solution, inst
