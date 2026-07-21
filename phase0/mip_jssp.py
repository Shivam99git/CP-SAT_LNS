"""Disjunctive big-M MIP formulation of job-shop scheduling for Gurobi and
CPLEX, added alongside CP-SAT's specialized interval/no_overlap model
(phase0/model_builder.py) to test whether boot_cold's floor/pocket mechanism
generalizes across solver families.

Both Gurobi and CPLEX are used via their free pip-installable tiers, which
are SIZE-LIMITED (not time-limited):
  * gurobipy's bundled "size-limited" license: 2000 variables / 2000 constraints.
  * cplex/docplex's "Community Edition": exactly 1000 variables / 1000
    constraints (verified empirically).
This is why the job-shop instances used with these solvers
(phase0/run_multisolver_test.py) are much smaller than the paper's main
CP-SAT experiments (15x15 full-shop / real Taillard instances) -- a hard
licensing ceiling, not a methodological choice, and disclosed as such
wherever these results are reported (BOOT_COLD_PAPER.md).

Unlike knapsack (where commercial solvers' cover cuts make even large
instances close in milliseconds -- see mip_knapsack.py's docstring), the
disjunctive big-M encoding of job-shop scheduling has a famously weak LP
relaxation, so even small instances stay genuinely hard for a generic MIP
solver -- this is the reason job-shop, not knapsack, is this module's real
cross-solver comparison.

Formulation, given operations grouped by job (precedence chain) and by
machine (mutual exclusion):
  start[op] >= 0                                    continuous, one per op
  start[b] >= start[a] + dur[a]                      job precedence (a before b in job)
  for every unordered pair (a, b) sharing a machine, binary y_ab:
      start[b] - start[a] - M*y_ab >= dur[a] - M      (a before b when y_ab=1)
      start[a] - start[b] + M*y_ab >= dur[b]          (b before a when y_ab=0)
  for every (op, outage) sharing a machine, binary z:
      outage.start - start[op] - M*z >= dur[op] - M - outage.start ... see code
      start[op] + M*z >= outage.end
  makespan >= start[last_op_of_job] + dur[last_op_of_job]   for every job
  minimize makespan
M = instance.horizon (a valid, if loose, upper bound on any start time).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .streams import Instance


@dataclass
class _OpInfo:
    op_id: str
    machine: int
    duration: int


def _ops_and_precedence(instance: Instance):
    """Returns (ops: list[_OpInfo], prec_pairs: list[(pred_id, succ_id)],
    job_last_op: list[op_id])."""
    ops: list[_OpInfo] = []
    prec_pairs: list[tuple[str, str]] = []
    job_last_op: list[str] = []
    for job in instance.jobs:
        prev_id = None
        for op in job.ops:
            ops.append(_OpInfo(op.op_id, op.machine, op.duration))
            if prev_id is not None:
                prec_pairs.append((prev_id, op.op_id))
            prev_id = op.op_id
        job_last_op.append(prev_id)
    return ops, prec_pairs, job_last_op


def _machine_groups(ops: list[_OpInfo]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    for op in ops:
        groups.setdefault(op.machine, []).append(op.op_id)
    return groups


def jssp_mip_size(instance: Instance) -> tuple[int, int]:
    """(n_vars, n_constraints) for the disjunctive big-M formulation, without
    building a solver model -- used as a pre-flight license-size check."""
    ops, prec_pairs, job_last_op = _ops_and_precedence(instance)
    groups = _machine_groups(ops)
    n_pairs = sum(len(g) * (len(g) - 1) // 2 for g in groups.values())
    n_outage_pairs = sum(len(groups.get(o.machine, [])) for o in instance.outages)
    n_vars = len(ops) + 1 + n_pairs + n_outage_pairs  # +1 makespan
    n_constraints = (
        len(prec_pairs)
        + 2 * n_pairs
        + 2 * n_outage_pairs
        + len(job_last_op)
    )
    return n_vars, n_constraints


# ---------------------------------------------------------------------------
# Gurobi
# ---------------------------------------------------------------------------

def _solve_jssp_gurobi(instance: Instance, time_limit: float, seed: int,
                       recorder: list[tuple[float, int]], t_offset: float,
                       workers: int = 1) -> tuple[dict[str, int] | None, int | None, bool]:
    import gurobipy as gp
    from gurobipy import GRB

    ops, prec_pairs, job_last_op = _ops_and_precedence(instance)
    op_by_id = {op.op_id: op for op in ops}
    groups = _machine_groups(ops)
    M = float(instance.horizon)

    m = gp.Model()
    m.setParam("OutputFlag", 0)
    m.setParam("Threads", workers)
    m.setParam("Seed", seed)
    m.setParam("TimeLimit", max(time_limit, 0.01))

    start = {op.op_id: m.addVar(lb=0.0, ub=M) for op in ops}

    for a, b in prec_pairs:
        m.addConstr(start[b] >= start[a] + op_by_id[a].duration)

    for machine, ids in groups.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                y = m.addVar(vtype=GRB.BINARY)
                da, db = op_by_id[a].duration, op_by_id[b].duration
                m.addConstr(start[b] >= start[a] + da - M * (1 - y))
                m.addConstr(start[a] >= start[b] + db - M * y)

    for outage in instance.outages:
        for op_id in groups.get(outage.machine, []):
            z = m.addVar(vtype=GRB.BINARY)
            d = op_by_id[op_id].duration
            m.addConstr(outage.start >= start[op_id] + d - M * (1 - z))
            m.addConstr(start[op_id] >= outage.end - M * z)

    makespan = m.addVar(lb=0.0, ub=M)
    for last_op in job_last_op:
        m.addConstr(makespan >= start[last_op] + op_by_id[last_op].duration)
    m.setObjective(makespan, GRB.MINIMIZE)

    t0 = time.monotonic()

    def cb(model, where):
        if where == GRB.Callback.MIPSOL:
            obj = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            recorder.append((t_offset + time.monotonic() - t0, int(round(obj))))

    m.optimize(cb)

    if m.SolCount == 0:
        return None, None, False
    solution = {op.op_id: int(round(start[op.op_id].X)) for op in ops}
    objective = int(round(makespan.X))
    proven_optimal = m.Status == GRB.OPTIMAL
    return solution, objective, proven_optimal


def gurobi_cold_solve(instance: Instance, total_budget: float, workers: int = 1,
                      seed: int = 0):
    from .harness import SolveResult
    traj: list[tuple[float, int]] = []
    solution, objective, proven = _solve_jssp_gurobi(instance, total_budget, seed, traj, 0.0, workers)
    if solution is None:
        return SolveResult("gurobi_cold", None, None, [])
    return SolveResult("gurobi_cold", objective, solution, traj, proven_optimal=proven)


def gurobi_boot_cold_solve(instance: Instance, total_budget: float,
                          prev_solution: dict[str, int] | None = None,
                          workers: int = 1, seed: int = 0):
    from .harness import SolveResult, list_schedule_bootstrap
    t0 = time.monotonic()
    traj: list[tuple[float, int]] = []
    floor_sol = None
    floor_obj = None
    if prev_solution is not None:
        floor_sol = list_schedule_bootstrap(instance, prev_solution)
        floor_obj = max(
            floor_sol[job.ops[-1].op_id] + job.ops[-1].duration for job in instance.jobs
        )
        traj.append((time.monotonic() - t0, floor_obj))
    initial_objective = floor_obj

    remaining = total_budget - (time.monotonic() - t0)
    incumbent, objective = floor_sol, floor_obj
    proven = False
    if remaining > 0.01:
        sol, obj, proven = _solve_jssp_gurobi(
            instance, remaining, seed, traj, time.monotonic() - t0, workers)
        if sol is not None and (objective is None or obj < objective):
            incumbent, objective = sol, obj

    if incumbent is None:
        return SolveResult("gurobi_boot_cold", None, None, [])

    monotone: list[tuple[float, int]] = []
    best = None
    for t, o in sorted(traj):
        if best is None or o < best:
            best = o
            monotone.append((t, o))
    return SolveResult("gurobi_boot_cold", objective, incumbent, monotone,
                       initial_objective=initial_objective, proven_optimal=proven)


# ---------------------------------------------------------------------------
# CPLEX (built via docplex's natural modeling syntax, solved through the raw
# cplex.Cplex engine docplex wraps so a real IncumbentCallback can be
# registered -- see mip_knapsack.py's docstring for why.)
# ---------------------------------------------------------------------------

def _solve_jssp_cplex(instance: Instance, time_limit: float, seed: int,
                      recorder: list[tuple[float, int]], t_offset: float,
                      workers: int = 1) -> tuple[dict[str, int] | None, int | None, bool]:
    from docplex.mp.model import Model
    from cplex.callbacks import IncumbentCallback

    ops, prec_pairs, job_last_op = _ops_and_precedence(instance)
    op_by_id = {op.op_id: op for op in ops}
    groups = _machine_groups(ops)
    M = float(instance.horizon)

    mdl = Model(name="jssp")
    start = {op.op_id: mdl.continuous_var(lb=0.0, ub=M, name=f"s_{op.op_id}") for op in ops}

    for a, b in prec_pairs:
        mdl.add_constraint(start[b] >= start[a] + op_by_id[a].duration)

    y_vars = {}
    for machine, ids in groups.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                y = mdl.binary_var(name=f"y_{a}_{b}")
                y_vars[(a, b)] = y
                da, db = op_by_id[a].duration, op_by_id[b].duration
                mdl.add_constraint(start[b] >= start[a] + da - M * (1 - y))
                mdl.add_constraint(start[a] >= start[b] + db - M * y)

    z_vars = {}
    for oi, outage in enumerate(instance.outages):
        for op_id in groups.get(outage.machine, []):
            z = mdl.binary_var(name=f"z_{op_id}_{oi}")
            z_vars[(op_id, oi)] = z
            d = op_by_id[op_id].duration
            mdl.add_constraint(outage.start >= start[op_id] + d - M * (1 - z))
            mdl.add_constraint(start[op_id] >= outage.end - M * z)

    makespan = mdl.continuous_var(lb=0.0, ub=M, name="makespan")
    for last_op in job_last_op:
        mdl.add_constraint(makespan >= start[last_op] + op_by_id[last_op].duration)
    mdl.minimize(makespan)

    cpx = mdl.get_cplex()
    cpx.set_log_stream(None)
    cpx.set_results_stream(None)
    cpx.set_warning_stream(None)
    cpx.set_error_stream(None)
    cpx.parameters.threads.set(workers)
    cpx.parameters.randomseed.set(seed)
    cpx.parameters.timelimit.set(max(time_limit, 0.01))

    t0 = time.monotonic()

    class _Recorder(IncumbentCallback):
        def __call__(self):
            recorder.append((t_offset + time.monotonic() - t0,
                             int(round(self.get_objective_value()))))

    cpx.register_callback(_Recorder)
    cpx.solve()

    try:
        values = cpx.solution.get_values([f"s_{op.op_id}" for op in ops])
        makespan_val = cpx.solution.get_values(["makespan"])[0]
    except Exception:
        return None, None, False
    solution = {op.op_id: int(round(v)) for op, v in zip(ops, values)}
    objective = int(round(makespan_val))
    proven_optimal = cpx.solution.get_status() in (
        cpx.solution.status.MIP_optimal,
        cpx.solution.status.optimal_tolerance,
    )
    return solution, objective, proven_optimal


def cplex_cold_solve(instance: Instance, total_budget: float, workers: int = 1,
                     seed: int = 0):
    from .harness import SolveResult
    traj: list[tuple[float, int]] = []
    solution, objective, proven = _solve_jssp_cplex(instance, total_budget, seed, traj, 0.0, workers)
    if solution is None:
        return SolveResult("cplex_cold", None, None, [])
    return SolveResult("cplex_cold", objective, solution, traj, proven_optimal=proven)


def cplex_boot_cold_solve(instance: Instance, total_budget: float,
                         prev_solution: dict[str, int] | None = None,
                         workers: int = 1, seed: int = 0):
    from .harness import SolveResult, list_schedule_bootstrap
    t0 = time.monotonic()
    traj: list[tuple[float, int]] = []
    floor_sol = None
    floor_obj = None
    if prev_solution is not None:
        floor_sol = list_schedule_bootstrap(instance, prev_solution)
        floor_obj = max(
            floor_sol[job.ops[-1].op_id] + job.ops[-1].duration for job in instance.jobs
        )
        traj.append((time.monotonic() - t0, floor_obj))
    initial_objective = floor_obj

    remaining = total_budget - (time.monotonic() - t0)
    incumbent, objective = floor_sol, floor_obj
    proven = False
    if remaining > 0.01:
        sol, obj, proven = _solve_jssp_cplex(
            instance, remaining, seed, traj, time.monotonic() - t0, workers)
        if sol is not None and (objective is None or obj < objective):
            incumbent, objective = sol, obj

    if incumbent is None:
        return SolveResult("cplex_boot_cold", None, None, [])

    monotone: list[tuple[float, int]] = []
    best = None
    for t, o in sorted(traj):
        if best is None or o < best:
            best = o
            monotone.append((t, o))
    return SolveResult("cplex_boot_cold", objective, incumbent, monotone,
                       initial_objective=initial_objective, proven_optimal=proven)
