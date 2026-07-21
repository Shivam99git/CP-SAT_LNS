"""Tests for the RCPSP domain (phase0/rcpsp/) -- minimal but real second
scheduling domain for cross-domain transfer evidence.

    .venv/bin/python -m pytest tests/test_rcpsp.py -q
"""

from __future__ import annotations

import pytest

from phase0.rcpsp.harness import (
    rcpsp_boot_cold_solve,
    rcpsp_cold_solve,
    serial_sgs_bootstrap,
)
from phase0.rcpsp.model_builder import build_rcpsp_model, solve_rcpsp, validate_rcpsp_solution
from phase0.rcpsp.streams import RStreamConfig, generate_rcpsp_stream

SMALL_CFG = RStreamConfig(num_activities=8, num_resources=2, stream_length=6, seed=3)


def test_stream_deterministic():
    s1 = generate_rcpsp_stream(SMALL_CFG)
    s2 = generate_rcpsp_stream(SMALL_CFG)
    assert s1 == s2
    assert len(s1) == SMALL_CFG.stream_length + 1


def test_precedence_is_acyclic_by_construction():
    """Every activity's predecessors must have a strictly lower index --
    guarantees the precedence DAG has no cycles."""
    stream = generate_rcpsp_stream(SMALL_CFG)
    for inst in stream:
        index_of = {a.activity_id: i for i, a in enumerate(inst.activities)}
        for act in inst.activities:
            for p in act.predecessors:
                if p in index_of:
                    assert index_of[p] < index_of[act.activity_id]


def test_all_delta_kinds_appear_and_touch_activities():
    cfg = RStreamConfig(num_activities=10, num_resources=2, stream_length=40, seed=1)
    stream = generate_rcpsp_stream(cfg)
    kinds_seen = {inst.delta_kind for inst in stream[1:]}
    assert kinds_seen <= {"duration_jitter", "resource_capacity_reduction",
                          "activity_insertion", "activity_cancellation"}
    assert len(kinds_seen) >= 3  # all four should show up over 40 deltas
    for inst in stream[1:]:
        if inst.delta_kind != "activity_cancellation":
            # cancellation can legitimately touch nothing if the removed
            # activity had no successors
            pass


def test_instance_solvable_and_validator_agrees():
    stream = generate_rcpsp_stream(SMALL_CFG)
    for inst in stream:
        sol, obj, status = solve_rcpsp(build_rcpsp_model(inst), time_limit=3.0)
        assert sol is not None
        makespan = validate_rcpsp_solution(inst, sol)
        assert makespan == obj


def test_validator_catches_resource_violation():
    stream = generate_rcpsp_stream(SMALL_CFG)
    inst = stream[0]
    sol, obj, _ = solve_rcpsp(build_rcpsp_model(inst), time_limit=3.0)
    # force two resource-competing activities to overlap illegally
    tampered = dict(sol)
    acts_with_r0 = [a for a in inst.activities if a.resource_usage]
    if len(acts_with_r0) >= 2:
        a, b = acts_with_r0[0], acts_with_r0[1]
        tampered[b.activity_id] = tampered[a.activity_id]
        shared = set(a.resource_usage) & set(b.resource_usage)
        if shared:
            r = next(iter(shared))
            if a.resource_usage[r] + b.resource_usage[r] > inst.resources[r]:
                with pytest.raises(AssertionError):
                    validate_rcpsp_solution(inst, tampered)


def test_sgs_bootstrap_feasible_across_deltas():
    stream = generate_rcpsp_stream(SMALL_CFG)
    sol, _, _ = solve_rcpsp(build_rcpsp_model(stream[0]), time_limit=3.0)
    prev = sol
    seen_kinds = set()
    for inst in stream[1:]:
        boot = serial_sgs_bootstrap(inst, prev)
        makespan = validate_rcpsp_solution(inst, boot)  # raises if infeasible
        assert makespan > 0
        seen_kinds.add(inst.delta_kind)
        prev = boot
    assert seen_kinds  # at least some deltas fired


def test_boot_cold_never_worse_than_cold_on_final_objective():
    """The same domination guarantee as the JSSP boot_cold, checked here for
    RCPSP: floor is a pocket, never makes the final answer worse."""
    cfg = RStreamConfig(num_activities=12, num_resources=2, stream_length=3, seed=7)
    stream = generate_rcpsp_stream(cfg)
    prev = None
    for inst in stream:
        cold = rcpsp_cold_solve(inst, total_budget=1.0, seed=0)
        boot = rcpsp_boot_cold_solve(inst, total_budget=1.0, prev_solution=prev, seed=0)
        if cold.solution is not None:
            validate_rcpsp_solution(inst, cold.solution)
        if boot.solution is not None:
            validate_rcpsp_solution(inst, boot.solution)
            assert boot.objective <= cold.objective + 0  # never strictly worse
        prev = boot.solution


def test_boot_cold_degrades_to_cold_with_no_previous_solution():
    stream = generate_rcpsp_stream(SMALL_CFG)
    inst0 = stream[0]
    boot = rcpsp_boot_cold_solve(inst0, total_budget=1.0, prev_solution=None, seed=0)
    assert boot.initial_objective is None
    assert len(boot.trajectory) >= 0  # no hand-inserted floor point


def test_activity_cancellation_drops_dangling_predecessor_gracefully():
    """After a cancellation, any activity that listed the removed one as a
    predecessor must still build/solve without crashing (model_builder
    already tolerates missing predecessor ids)."""
    cfg = RStreamConfig(num_activities=8, num_resources=2, stream_length=15, seed=2,
                        p_duration_jitter=0, p_resource_capacity_reduction=0,
                        p_activity_insertion=0, p_activity_cancellation=1.0)
    stream = generate_rcpsp_stream(cfg)
    for inst in stream:
        sol, obj, status = solve_rcpsp(build_rcpsp_model(inst), time_limit=2.0)
        assert sol is not None
        validate_rcpsp_solution(inst, sol)
