"""Fast sanity tests for the phase-0 pipeline. Run from the project root:

    .venv/bin/python -m pytest tests/ -q
"""

import random

import pytest

from phase0.harness import (
    ARMS,
    lns_solve,
    select_destroy_set,
)
from phase0.metrics import primal_integral
from phase0.model_builder import build_model, solve, validate_solution
from phase0.policies import EpsilonGreedyPolicy, UniformRandomPolicy
from phase0.streams import StreamConfig, generate_stream


SMALL_CFG = StreamConfig(
    num_machines=3, initial_jobs=4, stream_length=4, seed=7
)


def test_stream_deterministic():
    s1 = generate_stream(SMALL_CFG)
    s2 = generate_stream(SMALL_CFG)
    assert s1 == s2
    assert len(s1) == SMALL_CFG.stream_length + 1


def test_stream_deltas_touch_ops():
    stream = generate_stream(SMALL_CFG)
    assert stream[0].delta_kind == "base"
    assert stream[0].touched_ops == frozenset()
    for inst in stream[1:]:
        assert inst.delta_kind in ("arrival", "cancellation", "duration_jitter", "outage")
        assert inst.touched_ops, f"delta {inst.delta_kind} touched nothing"
        # touched ops refer to ops that exist in the instance (cancellation
        # touches the victim's machine-neighbours, which all still exist)
        ids = {op.op_id for op in inst.all_ops}
        assert inst.touched_ops <= ids


def test_solve_and_validate():
    inst = generate_stream(SMALL_CFG)[0]
    built = build_model(inst)
    solution, objective, _ = solve(built, time_limit=5.0)
    assert solution is not None
    assert validate_solution(inst, solution) == objective


def test_outage_respected():
    cfg = StreamConfig(num_machines=2, initial_jobs=3, stream_length=8,
                       p_arrival=0, p_cancellation=0, p_duration_jitter=0,
                       p_outage=1.0, seed=3)
    stream = generate_stream(cfg)
    inst = stream[-1]
    assert inst.outages
    built = build_model(inst)
    solution, _, _ = solve(built, time_limit=5.0)
    assert solution is not None
    validate_solution(inst, solution)  # validator checks outage overlap too


def test_full_freeze_preserves_feasibility_and_never_worsens():
    # order-based freeze: freezing everything fixes all machine orders, so
    # the solve can only re-time (left-shift), never worsen
    inst = generate_stream(SMALL_CFG)[0]
    built = build_model(inst)
    solution, objective, _ = solve(built, time_limit=5.0)
    frozen = dict(solution)  # freeze everything
    rebuilt = build_model(inst, frozen=frozen)
    sol2, obj2, _ = solve(rebuilt, time_limit=5.0)
    assert sol2 is not None
    assert obj2 <= objective
    assert validate_solution(inst, sol2) == obj2
    # machine order of the incumbent is preserved
    for machine in range(inst.num_machines):
        ops = [op for job in inst.jobs for op in job.ops if op.machine == machine]
        order1 = sorted(ops, key=lambda o: solution[o.op_id])
        order2 = sorted(ops, key=lambda o: sol2[o.op_id])
        assert [o.op_id for o in order1] == [o.op_id for o in order2]


def test_destroy_set_sizes():
    inst = generate_stream(SMALL_CFG)[1]
    built = build_model(inst)
    solution, _, _ = solve(built, time_limit=5.0)
    rng = random.Random(0)
    n = len(inst.all_ops)
    for arm in ARMS:
        picked = select_destroy_set(arm, inst, solution, rng)
        assert len(picked) >= 2
        ids = {op.op_id for op in inst.all_ops}
        assert picked <= ids
        if arm.strategy in ("random", "critical", "delta"):
            import math
            assert len(picked) == min(max(2, math.ceil(n * arm.size)), n)


def test_lns_never_worsens_and_final_feasible():
    inst = generate_stream(SMALL_CFG)[0]
    result = lns_solve(
        inst, UniformRandomPolicy(seed=1),
        total_budget=3.0, slice_budget=0.5, seed=1,
    )
    assert result.objective is not None
    assert validate_solution(inst, result.solution) == result.objective
    for r in result.rounds:
        assert r.objective_after <= r.objective_before
    objs = [obj for _, obj in result.trajectory]
    assert objs == sorted(objs, reverse=True) or len(set(objs)) == 1


def test_epsilon_greedy_reset():
    p = EpsilonGreedyPolicy(seed=0, reset_per_instance=True)
    p.update(ARMS[0], 5.0, True)
    assert p.counts[ARMS[0].name] == 1
    p.reset_instance()
    assert p.counts[ARMS[0].name] == 0
    persistent = EpsilonGreedyPolicy(seed=0, reset_per_instance=False)
    persistent.update(ARMS[0], 5.0, True)
    persistent.reset_instance()
    assert persistent.counts[ARMS[0].name] == 1


def test_primal_integral():
    # instant best-known -> 0; never solved -> 1
    assert primal_integral([(0.0, 100)], best_known=100, budget=10.0) == pytest.approx(0.0)
    assert primal_integral([], best_known=100, budget=10.0) == pytest.approx(1.0)
    # gap 0.5 for the first half, 0 after
    pi = primal_integral([(0.0, 150), (5.0, 100)], best_known=100, budget=10.0)
    assert pi == pytest.approx(0.25)
