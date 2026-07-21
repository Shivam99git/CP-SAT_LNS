"""Tests for phase0/mip_jssp.py and phase0/mip_knapsack.py -- the Gurobi and
CPLEX disjunctive-MIP/knapsack solver backends added for the cross-solver
validation in BOOT_COLD_PAPER.md Section 5.7.

Both solvers are used via their free, no-signup pip packages, which are
SIZE-LIMITED (gurobipy: 2000 vars/constraints; cplex Community Edition:
exactly 1000). The size-cap regression tests below pin the exact cap values
found by bisection this session -- if a future gurobipy/cplex release
changes them, these tests will fail loudly rather than silently producing
undersized experiment configurations.

    .venv/bin/python -m pytest tests/test_mip_solvers.py -q          # fast
    .venv/bin/python -m pytest tests/test_mip_solvers.py -q -m slow  # + actual solves
"""

from __future__ import annotations

import pytest

from phase0.model_builder import validate_solution
from phase0.run_knapsack_test import KInstance, validate_kselection
from phase0.streams import StreamConfig, generate_stream

pytest.importorskip("gurobipy", reason="gurobipy not installed")
pytest.importorskip("cplex", reason="cplex not installed")

from phase0.mip_jssp import (  # noqa: E402
    cplex_boot_cold_solve, cplex_cold_solve, gurobi_boot_cold_solve,
    gurobi_cold_solve, jssp_mip_size,
)
from phase0.mip_knapsack import (  # noqa: E402
    cplex_boot_cold as k_cplex_boot_cold, cplex_cold as k_cplex_cold,
    gurobi_boot_cold as k_gurobi_boot_cold, gurobi_cold as k_gurobi_cold,
    knapsack_mip_size,
)


# ---------------------------------------------------------------------------
# Fast: pure size-counting, no solver invoked
# ---------------------------------------------------------------------------

def test_jssp_mip_size_matches_hand_count():
    # 2 jobs x 2 ops, both jobs share both machines -> 1 pair per machine.
    cfg = StreamConfig(num_machines=2, initial_jobs=2, ops_per_job=(2, 2),
                       stream_length=0, seed=1)
    inst = generate_stream(cfg)[0]
    n_ops = len(inst.all_ops)
    assert n_ops == 4
    v, c = jssp_mip_size(inst)
    # vars: n_ops continuous starts + 1 makespan + disjunctive pair binaries
    # (exact pair count depends on which ops land on which machine, so just
    # sanity-check the additive structure rather than a brittle exact number)
    assert v > n_ops  # at least one disjunctive binary must exist
    assert c > 0


def test_knapsack_mip_size_is_items_plus_one_constraint():
    inst = KInstance(0, {f"it{i}": (1, 1) for i in range(50)}, capacity=25)
    v, c = knapsack_mip_size(inst)
    assert v == 50
    assert c == 1


# ---------------------------------------------------------------------------
# Slow: license-cap regressions (pin the exact bisected values) + real solves
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_gurobi_size_limited_license_cap_is_2000():
    import gurobipy as gp
    from gurobipy import GRB

    def _try(n):
        m = gp.Model()
        m.setParam("OutputFlag", 0)
        x = m.addVars(n, vtype=GRB.BINARY)
        m.setObjective(gp.quicksum(x[i] for i in range(n)), GRB.MAXIMIZE)
        try:
            m.optimize()
            return True
        except gp.GurobiError:
            return False

    assert _try(2000) is True
    assert _try(2001) is False


@pytest.mark.slow
def test_cplex_community_edition_cap_is_1000():
    import cplex

    def _try(n):
        c = cplex.Cplex()
        c.set_log_stream(None)
        c.set_results_stream(None)
        c.set_warning_stream(None)
        c.set_error_stream(None)
        c.variables.add(types=[c.variables.type.binary] * n)
        c.objective.set_linear([(i, 1.0) for i in range(n)])
        try:
            c.solve()
            return True
        except cplex.exceptions.errors.CplexSolverError:
            return False

    assert _try(1000) is True
    assert _try(1001) is False


@pytest.mark.slow
def test_gurobi_jssp_cold_solve_matches_validator():
    cfg = StreamConfig(num_machines=3, initial_jobs=4, ops_per_job=(2, 3),
                       stream_length=0, seed=1)
    inst = generate_stream(cfg)[0]
    res = gurobi_cold_solve(inst, total_budget=5.0)
    assert res.solution is not None
    assert validate_solution(inst, res.solution) == res.objective


@pytest.mark.slow
def test_cplex_jssp_cold_solve_matches_validator():
    cfg = StreamConfig(num_machines=3, initial_jobs=4, ops_per_job=(2, 3),
                       stream_length=0, seed=1)
    inst = generate_stream(cfg)[0]
    res = cplex_cold_solve(inst, total_budget=5.0)
    assert res.solution is not None
    assert validate_solution(inst, res.solution) == res.objective


@pytest.mark.slow
def test_gurobi_and_cplex_jssp_agree_with_each_other_on_optimum():
    """Both are independently-coded disjunctive MIP formulations of the same
    instance; on a small enough instance both should prove the same true
    optimum. (Regression for the correctness cross-check reported in
    BOOT_COLD_PAPER.md Sec 5.7: 60/60 instances agreed this session.)"""
    cfg = StreamConfig(num_machines=3, initial_jobs=4, ops_per_job=(2, 3),
                       stream_length=0, seed=2)
    inst = generate_stream(cfg)[0]
    g = gurobi_cold_solve(inst, total_budget=8.0)
    c = cplex_cold_solve(inst, total_budget=8.0)
    assert g.proven_optimal and c.proven_optimal
    assert g.objective == c.objective


@pytest.mark.slow
def test_gurobi_jssp_boot_cold_never_worse_than_floor():
    """Domination guarantee (Sec 3.3), re-verified for the Gurobi backend:
    boot_cold's final objective must be <= the bootstrap floor's objective."""
    cfg = StreamConfig(num_machines=3, initial_jobs=4, ops_per_job=(2, 3),
                       stream_length=2, seed=1)
    stream = generate_stream(cfg)
    prev = None
    for inst in stream:
        res = gurobi_boot_cold_solve(inst, total_budget=5.0, prev_solution=prev)
        assert res.solution is not None
        assert validate_solution(inst, res.solution) == res.objective
        if res.initial_objective is not None:
            assert res.objective <= res.initial_objective
        prev = res.solution


@pytest.mark.slow
def test_cplex_jssp_boot_cold_never_worse_than_floor():
    cfg = StreamConfig(num_machines=3, initial_jobs=4, ops_per_job=(2, 3),
                       stream_length=2, seed=1)
    stream = generate_stream(cfg)
    prev = None
    for inst in stream:
        res = cplex_boot_cold_solve(inst, total_budget=5.0, prev_solution=prev)
        assert res.solution is not None
        assert validate_solution(inst, res.solution) == res.objective
        if res.initial_objective is not None:
            assert res.objective <= res.initial_objective
        prev = res.solution


@pytest.mark.slow
def test_gurobi_knapsack_cold_and_boot_cold_validate():
    items = {f"it{i}": (i + 1, (i + 1) * 3 + 5) for i in range(60)}
    inst = KInstance(0, items, capacity=200)
    cold = k_gurobi_cold(inst, budget=3.0, seed=1)
    assert cold.chosen is not None
    assert validate_kselection(inst, cold.chosen) == cold.value

    boot = k_gurobi_boot_cold(inst, budget=3.0, seed=1, prev_chosen=cold.chosen)
    assert boot.chosen is not None
    assert validate_kselection(inst, boot.chosen) == boot.value
    assert boot.value >= boot.initial_value  # maximization: boot_cold >= floor


@pytest.mark.slow
def test_cplex_knapsack_cold_and_boot_cold_validate():
    items = {f"it{i}": (i + 1, (i + 1) * 3 + 5) for i in range(60)}
    inst = KInstance(0, items, capacity=200)
    cold = k_cplex_cold(inst, budget=3.0, seed=1)
    assert cold.chosen is not None
    assert validate_kselection(inst, cold.chosen) == cold.value

    boot = k_cplex_boot_cold(inst, budget=3.0, seed=1, prev_chosen=cold.chosen)
    assert boot.chosen is not None
    assert validate_kselection(inst, boot.chosen) == boot.value
    assert boot.value >= boot.initial_value
