"""Gurobi and CPLEX solvers for the 0-1 knapsack domain (phase0/run_knapsack_test.py),
added to test whether the boot_cold floor/pocket mechanism (a bootstrap
solution kept as an anytime floor beside an otherwise-unmodified solver
continuation) generalizes across solver families, not just within CP-SAT.

Both are free pip-installable but SIZE-LIMITED:
  * gurobipy's bundled "size-limited" license: 2000 variables / 2000 constraints.
  * cplex/docplex's "Community Edition": exactly 1000 variables / 1000 constraints
    (verified empirically -- see tests/test_mip_solvers_license_caps.py).
This is why experiments using these solvers (phase0/run_multisolver_test.py)
use much smaller instances than the paper's main CP-SAT experiments -- a hard
licensing ceiling, not a methodological choice, and disclosed as such
wherever these results are reported (BOOT_COLD_PAPER.md).

The knapsack model itself is trivial (one capacity constraint, n binary
variables) so it fits comfortably under both caps for n up to ~900 items
even after stream deltas grow the item count -- see run_multisolver_test.py's
size choice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .run_knapsack_test import KInstance, knapsack_bootstrap, validate_kselection


@dataclass
class MSKResult:
    """Mirrors phase0.run_knapsack_test.KResult; kept separate so this module
    has no import-time dependency on gurobipy/cplex being installed unless
    the caller actually invokes a solve function."""
    method: str
    value: int | None
    chosen: set[str] | None
    trajectory: list[tuple[float, int]]
    initial_value: int | None = None
    proven_optimal: bool = False


def knapsack_mip_size(inst: KInstance) -> tuple[int, int]:
    """(n_vars, n_constraints) -- one binary var per item, one capacity row."""
    return len(inst.items), 1


# ---------------------------------------------------------------------------
# Gurobi
# ---------------------------------------------------------------------------

def _solve_knapsack_gurobi(inst: KInstance, time_limit: float, seed: int,
                           recorder: list[tuple[float, int]], t_offset: float,
                           workers: int = 1) -> tuple[set[str] | None, int | None, bool]:
    import gurobipy as gp
    from gurobipy import GRB

    item_ids = list(inst.items)
    m = gp.Model()
    m.setParam("OutputFlag", 0)
    m.setParam("Threads", workers)
    m.setParam("Seed", seed)
    m.setParam("TimeLimit", max(time_limit, 0.01))

    x = {iid: m.addVar(vtype=GRB.BINARY) for iid in item_ids}
    m.addConstr(gp.quicksum(inst.items[i][0] * x[i] for i in item_ids) <= inst.capacity)
    m.setObjective(gp.quicksum(inst.items[i][1] * x[i] for i in item_ids), GRB.MAXIMIZE)

    t0 = time.monotonic()

    def cb(model, where):
        if where == GRB.Callback.MIPSOL:
            obj = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            recorder.append((t_offset + time.monotonic() - t0, int(round(obj))))

    m.optimize(cb)

    if m.SolCount == 0:
        return None, None, False
    chosen = {iid for iid in item_ids if x[iid].X > 0.5}
    objective = int(round(m.ObjVal))
    proven_optimal = m.Status == GRB.OPTIMAL
    return chosen, objective, proven_optimal


def gurobi_cold(inst: KInstance, budget: float, seed: int, workers: int = 1) -> MSKResult:
    traj: list[tuple[float, int]] = []
    chosen, val, opt = _solve_knapsack_gurobi(inst, budget, seed, traj, 0.0, workers)
    return MSKResult("gurobi_cold", val, chosen, traj, proven_optimal=opt)


def gurobi_boot_cold(inst: KInstance, budget: float, seed: int,
                     prev_chosen: set[str] | None, workers: int = 1) -> MSKResult:
    t0 = time.monotonic()
    traj: list[tuple[float, int]] = []
    floor_val = None
    floor_sel = None
    if prev_chosen is not None:
        floor_sel = knapsack_bootstrap(inst, prev_chosen)
        floor_val = validate_kselection(inst, floor_sel)
        traj.append((time.monotonic() - t0, floor_val))
    chosen, val, opt = _solve_knapsack_gurobi(
        inst, budget - (time.monotonic() - t0), seed, traj,
        time.monotonic() - t0, workers)
    if val is None or (floor_val is not None and floor_val >= val):
        chosen, val = floor_sel, floor_val
    mono, best = [], None
    for t, v in sorted(traj):
        if best is None or v > best:
            best = v
            mono.append((t, v))
    return MSKResult("gurobi_boot_cold", val, chosen, mono,
                     initial_value=floor_val, proven_optimal=opt)


# ---------------------------------------------------------------------------
# CPLEX (built via docplex's natural modeling syntax to avoid hand-derived
# big-M coefficient arrays, then solved through the raw cplex.Cplex engine
# docplex wraps -- so a real IncumbentCallback can be registered for the
# anytime trajectory, which docplex's own progress-listener API does not
# reliably fire for fast-solving MIPs. Both paths hit the same underlying
# CPLEX Community Edition size cap.)
# ---------------------------------------------------------------------------

def _solve_knapsack_cplex(inst: KInstance, time_limit: float, seed: int,
                          recorder: list[tuple[float, int]], t_offset: float,
                          workers: int = 1) -> tuple[set[str] | None, int | None, bool]:
    from docplex.mp.model import Model
    from cplex.callbacks import IncumbentCallback

    item_ids = list(inst.items)
    mdl = Model(name="knapsack")
    x = {iid: mdl.binary_var(name=f"x_{iid}") for iid in item_ids}
    mdl.add_constraint(mdl.sum(inst.items[i][0] * x[i] for i in item_ids) <= inst.capacity)
    mdl.maximize(mdl.sum(inst.items[i][1] * x[i] for i in item_ids))

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
        values = cpx.solution.get_values()
    except Exception:
        return None, None, False
    if not values:
        return None, None, False
    chosen = {iid for iid, v in zip(item_ids, values) if v > 0.5}
    objective = int(round(cpx.solution.get_objective_value()))
    proven_optimal = cpx.solution.get_status() in (
        cpx.solution.status.MIP_optimal,
        cpx.solution.status.optimal_tolerance,
    )
    return chosen, objective, proven_optimal


def cplex_cold(inst: KInstance, budget: float, seed: int, workers: int = 1) -> MSKResult:
    traj: list[tuple[float, int]] = []
    chosen, val, opt = _solve_knapsack_cplex(inst, budget, seed, traj, 0.0, workers)
    return MSKResult("cplex_cold", val, chosen, traj, proven_optimal=opt)


def cplex_boot_cold(inst: KInstance, budget: float, seed: int,
                    prev_chosen: set[str] | None, workers: int = 1) -> MSKResult:
    t0 = time.monotonic()
    traj: list[tuple[float, int]] = []
    floor_val = None
    floor_sel = None
    if prev_chosen is not None:
        floor_sel = knapsack_bootstrap(inst, prev_chosen)
        floor_val = validate_kselection(inst, floor_sel)
        traj.append((time.monotonic() - t0, floor_val))
    chosen, val, opt = _solve_knapsack_cplex(
        inst, budget - (time.monotonic() - t0), seed, traj,
        time.monotonic() - t0, workers)
    if val is None or (floor_val is not None and floor_val >= val):
        chosen, val = floor_sel, floor_val
    mono, best = [], None
    for t, v in sorted(traj):
        if best is None or v > best:
            best = v
            mono.append((t, v))
    return MSKResult("cplex_boot_cold", val, chosen, mono,
                     initial_value=floor_val, proven_optimal=opt)
