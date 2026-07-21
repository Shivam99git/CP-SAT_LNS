"""ICAPS-extension tests: severity-scaled + new deltas, and the golden-stream
backward-compatibility regression for the original four deltas.

    .venv/bin/python -m pytest tests/test_icaps_streams.py -q
"""

from __future__ import annotations

import json

import pytest

from phase0.model_builder import build_model, solve, validate_solution
from phase0.streams import (
    SEVERITY_SCALE,
    Instance,
    StreamConfig,
    generate_stream,
)

GOLDEN_CFG = StreamConfig(num_machines=5, initial_jobs=8, stream_length=15, seed=42)

NEW_KINDS = (
    "batch_arrival", "rush_job", "machine_speed_degradation",
    "due_date_change", "priority_change", "partial_schedule_freeze",
)


def _fingerprint(stream: list[Instance]) -> list[dict]:
    return [
        {"idx": i.index, "delta": i.delta_kind, "njobs": len(i.jobs),
         "nops": len(i.all_ops), "outages": len(i.outages),
         "ops_hash": sorted((op.op_id, op.machine, op.duration) for op in i.all_ops)}
        for i in stream
    ]


def test_golden_stream_backward_compatible():
    """generate_stream with default severity ('medium') and the new p_* delta
    weights left at 0.0 must reproduce EXACTLY the pre-ICAPS-extension stream
    for a fixed seed -- verified against a fingerprint captured before the
    extension was written. A break here means the refactor changed the
    original four deltas' numeric behavior, which the task explicitly
    forbids."""
    stream = generate_stream(GOLDEN_CFG)
    fp = json.loads(json.dumps(_fingerprint(stream)))  # tuple->list normalize
    assert fp == _GOLDEN_FINGERPRINT


def test_severity_scale_covers_all_levels():
    assert set(SEVERITY_SCALE) == {"low", "medium", "high", "extreme"}
    assert SEVERITY_SCALE["low"] < SEVERITY_SCALE["medium"] < SEVERITY_SCALE["high"] < SEVERITY_SCALE["extreme"]


@pytest.mark.parametrize("kind", NEW_KINDS)
@pytest.mark.parametrize("severity", ["low", "medium", "high", "extreme"])
def test_new_delta_deterministic_and_valid(kind, severity):
    weight_field = f"p_{kind}"
    cfg = StreamConfig(
        num_machines=4, initial_jobs=6, stream_length=3, seed=11,
        severity=severity,
        p_arrival=0, p_cancellation=0, p_duration_jitter=0, p_outage=0,
        **{weight_field: 1.0},
    )

    prev_solutions = None
    if kind == "partial_schedule_freeze":
        # partial_schedule_freeze needs a previous SOLUTION to freeze against;
        # solve the base instance and feed it in for every stream index.
        base_stream = generate_stream(StreamConfig(
            num_machines=4, initial_jobs=6, stream_length=0, seed=11))
        sol, _, _ = solve(build_model(base_stream[0]), time_limit=3.0)
        prev_solutions = {i: sol for i in range(10)}

    s1 = generate_stream(cfg, prev_solutions=prev_solutions)
    s2 = generate_stream(cfg, prev_solutions=prev_solutions)
    assert s1 == s2, f"{kind}@{severity} not deterministic under seed"

    for inst in s1[1:]:
        assert inst.delta_kind == kind
        assert inst.severity == severity
        for op in inst.all_ops:
            assert op.duration > 0, f"non-positive duration for {op.op_id}"
        for job in inst.jobs:
            if job.due_date is not None:
                assert job.due_date > 0
            assert job.weight > 0


def test_new_delta_produces_feasible_schedule():
    """For each new delta kind, a feasible schedule can be constructed and
    passes the independent validator (except partial_schedule_freeze on the
    base instance, which has nothing to freeze and degrades to a no-op)."""
    for kind in NEW_KINDS:
        weight_field = f"p_{kind}"
        cfg = StreamConfig(
            num_machines=4, initial_jobs=6, stream_length=2, seed=3,
            severity="high",
            p_arrival=0, p_cancellation=0, p_duration_jitter=0, p_outage=0,
            **{weight_field: 1.0},
        )
        prev_solutions = None
        if kind == "partial_schedule_freeze":
            base = generate_stream(StreamConfig(
                num_machines=4, initial_jobs=6, stream_length=0, seed=3))
            sol, _, _ = solve(build_model(base[0]), time_limit=3.0)
            prev_solutions = {i: sol for i in range(10)}
        stream = generate_stream(cfg, prev_solutions=prev_solutions)
        for inst in stream:
            built = build_model(inst, exact_frozen=inst.frozen_starts or None)
            solution, objective, status = solve(built, time_limit=5.0)
            assert solution is not None, f"{kind}: no feasible solution found"
            makespan = validate_solution(inst, solution)
            assert makespan == objective


def test_partial_schedule_freeze_respects_previous_starts():
    from phase0.metrics import frozen_violation_count

    cfg = StreamConfig(num_machines=4, initial_jobs=6, stream_length=0, seed=5)
    base = generate_stream(cfg)[0]
    sol, _, _ = solve(build_model(base), time_limit=3.0)

    frozen_cfg = StreamConfig(
        num_machines=4, initial_jobs=6, stream_length=1, seed=5,
        severity="high",  # high -> 75% of ops frozen
        p_arrival=0, p_cancellation=0, p_duration_jitter=0, p_outage=0,
        p_partial_schedule_freeze=1.0,
    )
    stream = generate_stream(frozen_cfg, prev_solutions={0: sol})
    inst = stream[1]
    assert inst.frozen_ops, "expected a non-empty frozen prefix at high severity"
    # requested fraction ~= 0.75 of ops that existed in both instances
    assert len(inst.frozen_ops) / len(sol) == pytest.approx(0.75, abs=0.05)

    built = build_model(inst, exact_frozen=inst.frozen_starts)
    solution, objective, status = solve(built, time_limit=5.0)
    assert solution is not None
    validate_solution(inst, solution)
    assert frozen_violation_count(inst.frozen_starts, solution) == 0
    # and a solution that ignores the freeze would (in general) violate it --
    # sanity-check the checker itself catches a real violation
    tampered = dict(solution)
    an_op = next(iter(inst.frozen_ops))
    tampered[an_op] = tampered[an_op] + 5
    assert frozen_violation_count(inst.frozen_starts, tampered) >= 1


_GOLDEN_FINGERPRINT = [{"idx": 0, "delta": "base", "njobs": 8, "nops": 33, "outages": 0, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 19], ["j2_o1", 1, 23], ["j2_o2", 2, 13], ["j2_o3", 3, 30], ["j2_o4", 4, 5], ["j3_o0", 3, 9], ["j3_o1", 2, 11], ["j3_o2", 1, 29], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 1, "delta": "duration_jitter", "njobs": 8, "nops": 33, "outages": 0, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 18], ["j2_o1", 1, 19], ["j2_o2", 2, 11], ["j2_o3", 3, 46], ["j2_o4", 4, 6], ["j3_o0", 3, 9], ["j3_o1", 2, 11], ["j3_o2", 1, 29], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 2, "delta": "duration_jitter", "njobs": 8, "nops": 33, "outages": 0, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 9], ["j3_o1", 2, 11], ["j3_o2", 1, 29], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 3, "delta": "duration_jitter", "njobs": 8, "nops": 33, "outages": 0, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 4, "delta": "arrival", "njobs": 9, "nops": 36, "outages": 0, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23]]}, {"idx": 5, "delta": "outage", "njobs": 9, "nops": 36, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23]]}, {"idx": 6, "delta": "arrival", "njobs": 10, "nops": 41, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23], ["j9_o0", 3, 28], ["j9_o1", 1, 22], ["j9_o2", 4, 22], ["j9_o3", 0, 13], ["j9_o4", 2, 28]]}, {"idx": 7, "delta": "cancellation", "njobs": 9, "nops": 36, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23]]}, {"idx": 8, "delta": "arrival", "njobs": 10, "nops": 39, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23]]}, {"idx": 9, "delta": "arrival", "njobs": 11, "nops": 42, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25], ["j8_o0", 2, 7], ["j8_o1", 3, 11], ["j8_o2", 1, 23]]}, {"idx": 10, "delta": "cancellation", "njobs": 10, "nops": 39, "outages": 1, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 11, "delta": "outage", "njobs": 10, "nops": 39, "outages": 2, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 7], ["j5_o1", 0, 22], ["j5_o2", 1, 14], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 12, "delta": "duration_jitter", "njobs": 10, "nops": 39, "outages": 2, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 5], ["j5_o1", 0, 23], ["j5_o2", 1, 15], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 13, "delta": "outage", "njobs": 10, "nops": 39, "outages": 3, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j1_o0", 4, 5], ["j1_o1", 0, 7], ["j1_o2", 2, 11], ["j1_o3", 1, 12], ["j1_o4", 3, 21], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 5], ["j5_o1", 0, 23], ["j5_o2", 1, 15], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 14, "delta": "cancellation", "njobs": 9, "nops": 34, "outages": 3, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 5], ["j5_o1", 0, 23], ["j5_o2", 1, 15], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}, {"idx": 15, "delta": "outage", "njobs": 9, "nops": 34, "outages": 3, "ops_hash": [["j0_o0", 0, 12], ["j0_o1", 4, 9], ["j0_o2", 2, 28], ["j0_o3", 1, 8], ["j0_o4", 3, 26], ["j10_o0", 1, 29], ["j10_o1", 3, 6], ["j10_o2", 0, 8], ["j11_o0", 3, 17], ["j11_o1", 0, 24], ["j11_o2", 1, 19], ["j2_o0", 0, 20], ["j2_o1", 1, 16], ["j2_o2", 2, 12], ["j2_o3", 3, 40], ["j2_o4", 4, 9], ["j3_o0", 3, 12], ["j3_o1", 2, 16], ["j3_o2", 1, 40], ["j4_o0", 0, 16], ["j4_o1", 4, 16], ["j4_o2", 1, 24], ["j4_o3", 3, 13], ["j5_o0", 3, 5], ["j5_o1", 0, 23], ["j5_o2", 1, 15], ["j6_o0", 4, 6], ["j6_o1", 2, 26], ["j6_o2", 3, 12], ["j6_o3", 0, 29], ["j6_o4", 1, 14], ["j7_o0", 1, 13], ["j7_o1", 0, 19], ["j7_o2", 4, 25]]}]
