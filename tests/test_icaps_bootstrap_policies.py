"""Tests for phase0/bootstrap_policies.py -- arrival-specific floor variants.

    .venv/bin/python -m pytest tests/test_icaps_bootstrap_policies.py -q
"""

from __future__ import annotations

import pytest

from phase0 import bootstrap_policies as bp
from phase0.harness import list_schedule_bootstrap, warm_bootstrap_solve
from phase0.model_builder import build_model, solve, validate_solution
from phase0.streams import StreamConfig, generate_stream


def _arrival_pair(seed: int):
    cfg = StreamConfig(num_machines=4, initial_jobs=6, stream_length=1, seed=seed,
                       p_arrival=1.0, p_cancellation=0, p_duration_jitter=0, p_outage=0)
    stream = generate_stream(cfg)
    sol0, _, _ = solve(build_model(stream[0]), time_limit=3.0)
    return stream[0], stream[1], sol0


def test_append_matches_list_schedule_bootstrap():
    inst0, inst1, sol0 = _arrival_pair(13)
    assert bp.boot_cold_append(inst1, sol0) == list_schedule_bootstrap(inst1, sol0)


@pytest.mark.parametrize("name", list(bp.FLOOR_POLICIES))
def test_floor_policy_feasible(name):
    inst0, inst1, sol0 = _arrival_pair(13)
    floor = bp.FLOOR_POLICIES[name](inst1, sol0)
    obj = max(floor[j.ops[-1].op_id] + j.ops[-1].duration for j in inst1.jobs)
    mk = validate_solution(inst1, floor)
    assert mk == obj


@pytest.mark.parametrize("name", list(bp.FLOOR_POLICIES))
def test_floor_policy_respects_job_precedence(name):
    inst0, inst1, sol0 = _arrival_pair(13)
    floor = bp.FLOOR_POLICIES[name](inst1, sol0)
    for job in inst1.jobs:
        for a, b in zip(job.ops, job.ops[1:]):
            assert floor[b.op_id] >= floor[a.op_id] + a.duration, (
                f"{name}: precedence violated {a.op_id}->{b.op_id}")


@pytest.mark.parametrize("name", list(bp.FLOOR_POLICIES))
def test_floor_policy_deterministic(name):
    inst0, inst1, sol0 = _arrival_pair(13)
    f1 = bp.FLOOR_POLICIES[name](inst1, sol0)
    f2 = bp.FLOOR_POLICIES[name](inst1, sol0)
    assert f1 == f2


def test_floor_policy_respects_outages():
    cfg = StreamConfig(num_machines=3, initial_jobs=5, stream_length=2, seed=21,
                       p_arrival=0.5, p_cancellation=0, p_duration_jitter=0, p_outage=0.5)
    stream = generate_stream(cfg)
    sol0, _, _ = solve(build_model(stream[0]), time_limit=3.0)
    inst1 = stream[1]
    for name, fn in bp.FLOOR_POLICIES.items():
        floor = fn(inst1, sol0)
        # independent validator checks outage overlap too
        validate_solution(inst1, floor)


def test_gap_insert_beats_append_on_arrival_delta():
    """The whole point of this module: on an arrival delta, at least one
    gap-aware policy should find a floor no worse than plain append, and
    typically strictly better (idle-gap insertion vs. always-append)."""
    inst0, inst1, sol0 = _arrival_pair(13)
    append_floor = bp.boot_cold_append(inst1, sol0)
    append_obj = max(append_floor[j.ops[-1].op_id] + j.ops[-1].duration for j in inst1.jobs)
    for name in ("gap_insert", "regret_insert", "beam_insert"):
        floor = bp.FLOOR_POLICIES[name](inst1, sol0)
        obj = max(floor[j.ops[-1].op_id] + j.ops[-1].duration for j in inst1.jobs)
        assert obj <= append_obj, f"{name} did worse than append ({obj} > {append_obj})"


def test_floor_fn_pluggable_into_warm_bootstrap_solve():
    inst0, inst1, sol0 = _arrival_pair(13)
    default_res = warm_bootstrap_solve(inst1, total_budget=0.2, prev_solution=sol0,
                                       use_hint=False)
    plugged_res = warm_bootstrap_solve(inst1, total_budget=0.2, prev_solution=sol0,
                                       use_hint=False, floor_fn=bp.boot_cold_gap_insert)
    assert plugged_res.initial_objective <= default_res.initial_objective
    validate_solution(inst1, plugged_res.solution)


def test_warm_bootstrap_solve_default_unaffected_by_floor_fn_param():
    """Regression: adding the floor_fn parameter must not change default
    (floor_fn=None) behaviour at all."""
    inst0, inst1, sol0 = _arrival_pair(13)
    r1 = warm_bootstrap_solve(inst1, total_budget=0.2, prev_solution=sol0, use_hint=False, seed=1)
    r2 = warm_bootstrap_solve(inst1, total_budget=0.2, prev_solution=sol0, use_hint=False,
                              seed=1, floor_fn=None)
    assert r1.initial_objective == r2.initial_objective


def test_micro_cp_returns_solve_result_not_bare_solution():
    inst0, inst1, sol0 = _arrival_pair(13)
    r = bp.boot_cold_micro_cp(inst1, total_budget=0.5, prev_solution=sol0, micro_budget=0.05)
    assert hasattr(r, "objective") and hasattr(r, "solution")
    validate_solution(inst1, r.solution)


def test_beam_insert_timeout_protection():
    """A pathologically tiny timeout must not crash -- it falls back to
    gap_insert's result."""
    inst0, inst1, sol0 = _arrival_pair(13)
    floor = bp.boot_cold_beam_insert(inst1, sol0, beam_width=4, timeout_s=0.0)
    obj = max(floor[j.ops[-1].op_id] + j.ops[-1].duration for j in inst1.jobs)
    mk = validate_solution(inst1, floor)
    assert mk == obj
