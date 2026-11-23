"""Exact disjunctive MILP for the dynamic job shop, built ONCE in a
solver-neutral form and translated verbatim to every MIP backend
(phase0/solver_adapters/mip_backends.py), so Gurobi, CPLEX, SCIP, HiGHS, CBC
and GLPK provably receive the same variables, coefficients and big-M values.

Variables (all integer; durations are integer, so integer starts lose nothing):
  s_i in [lb_i, ub_i]          start of operation i (bounds from
                               solver_independent_model.op_bounds, horizon H =
                               Instance.horizon, the CP-SAT model's own domain)
  y_ij in {0,1}                for i < j sharing a machine, both duration > 0:
                               y_ij = 1  <=>  i before j
  z_io in {0,1}                for operation i and outage o on i's machine, only
                               if neither side of the disjunction is implied by
                               the bounds: z_io = 1 <=> i ends before o starts
  C in [LB, H] (or [LB, U-1])  makespan

Constraints:
  s_b - s_a >= p_a                                   job precedence
  s_j - s_i - M_ij y_ij >= p_i - M_ij                (y=1: i before j)
  s_i - s_j + M_ji y_ij >= p_j                       (y=0: j before i)
  s_i + M y_io  ... outage: s_i + p_i <= o.start + Ma (1 - z),  s_i >= o.end - Mb z
  C - s_last >= p_last                               per job
  optional: C <= U - 1 (strict-improvement cutoff), kept machine-order arcs
            s_v - s_u >= p_u (restricted neighbourhoods)
Big-M constants are the tightest values implied by the start-time bounds:
  M_ij = ub_i + p_i - lb_j  (makes the i-before-j row redundant when y = 0),
  Ma = ub_i + p_i - o.start,  Mb = o.end - lb_i.
A pair whose order is implied by the bounds (ub_i + p_i <= lb_j) needs no
binary: the disjunction always holds. These are derived, not arbitrary
constants, and test_jobshop_milp.py checks the optimum against CP-SAT and an
exhaustive oracle on every supported feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .solver_independent_model import op_bounds
from .streams import Instance


@dataclass
class LinearModel:
    names: list[str] = field(default_factory=list)
    lb: list[float] = field(default_factory=list)
    ub: list[float] = field(default_factory=list)
    vtype: list[str] = field(default_factory=list)        # "I" integer, "B" binary
    rows: list[tuple[dict[int, float], str, float]] = field(default_factory=list)  # (coefs, ">="|"<="|"==", rhs)
    obj_var: int = -1
    start_index: dict[str, int] = field(default_factory=dict)
    order_vars: dict[tuple[str, str], int] = field(default_factory=dict)   # (i, j) -> y index
    outage_vars: dict[tuple[str, int], int] = field(default_factory=dict)  # (i, outage#) -> z index
    stats: dict = field(default_factory=dict)

    def add_var(self, name, lb, ub, vt):
        self.names.append(name); self.lb.append(lb); self.ub.append(ub); self.vtype.append(vt)
        return len(self.names) - 1

    def add_row(self, coefs, sense, rhs):
        self.rows.append((coefs, sense, rhs))

    @property
    def n_vars(self):
        return len(self.names)

    @property
    def n_rows(self):
        return len(self.rows)

    @property
    def n_binary(self):
        return sum(1 for t in self.vtype if t == "B")

    def start_vector(self, schedule: dict[str, int]) -> list[float | None]:
        """Full variable assignment implied by a feasible schedule (for MIP
        starts): starts, orders, outage sides, makespan. Entries are None for
        operations the schedule does not cover (new jobs)."""
        x: list[float | None] = [None] * self.n_vars
        dur = self.stats["_dur"]
        for op, k in self.start_index.items():
            if op in schedule:
                x[k] = schedule[op]
        for (i, j), k in self.order_vars.items():
            if i in schedule and j in schedule:
                x[k] = 1.0 if schedule[i] < schedule[j] else 0.0
        for (i, oi), k in self.outage_vars.items():
            if i in schedule:
                o_start = self.stats["_outages"][oi][1]
                x[k] = 1.0 if schedule[i] + dur[i] <= o_start else 0.0
        if all(op in schedule for op in self.start_index):
            x[self.obj_var] = max(schedule[op] + dur[op] for op in self.start_index)
        return x


def build_milp(inst: Instance, cutoff: int | None = None, kept_arcs=None) -> LinearModel:
    bounds, H = op_bounds(inst)
    b = {x.op_id: x for x in bounds}
    lm = LinearModel()
    for x in bounds:
        lm.start_index[x.op_id] = lm.add_var(f"s_{x.op_id}", x.lb, x.ub, "I")
    s = lm.start_index
    dur = {x.op_id: x.duration for x in bounds}
    # job precedence + makespan
    lb_c = max((x.lb + x.duration for x in bounds), default=0)
    ub_c = H if cutoff is None else min(H, cutoff)
    lm.obj_var = C = lm.add_var("Cmax", lb_c, ub_c, "I")
    for job in inst.jobs:
        for a, c in zip(job.ops, job.ops[1:]):
            lm.add_row({s[c.op_id]: 1, s[a.op_id]: -1}, ">=", a.duration)
        if job.ops:
            last = job.ops[-1]
            lm.add_row({C: 1, s[last.op_id]: -1}, ">=", last.duration)
    # machine disjunctions
    by_m: dict[int, list[str]] = {}
    for x in bounds:
        if x.duration > 0:
            by_m.setdefault(x.machine, []).append(x.op_id)
    implied = 0
    for ids in by_m.values():
        for p in range(len(ids)):
            for q in range(p + 1, len(ids)):
                i, j = ids[p], ids[q]
                bi, bj = b[i], b[j]
                if bi.ub + bi.duration <= bj.lb or bj.ub + bj.duration <= bi.lb:
                    implied += 1
                    continue
                y = lm.add_var(f"y_{i}_{j}", 0, 1, "B")
                lm.order_vars[(i, j)] = y
                Mij = bi.ub + bi.duration - bj.lb
                Mji = bj.ub + bj.duration - bi.lb
                lm.add_row({s[j]: 1, s[i]: -1, y: -Mij}, ">=", bi.duration - Mij)
                lm.add_row({s[i]: 1, s[j]: -1, y: Mji}, ">=", bj.duration)
    # outages
    outages = [(o.machine, o.start, o.end) for o in inst.outages]
    for oi, (m, os_, oe) in enumerate(outages):
        if oe <= os_:
            continue
        for i in by_m.get(m, []):
            bi = b[i]
            before_always = bi.ub + bi.duration <= os_
            after_always = bi.lb >= oe
            if before_always or after_always:
                continue
            if bi.lb + bi.duration > os_:          # cannot finish before the outage: must start after it
                lm.add_row({s[i]: 1}, ">=", oe)
                continue
            if bi.ub < oe:                         # cannot start after the outage: must end before it
                lm.add_row({s[i]: 1}, "<=", os_ - bi.duration)
                continue
            z = lm.add_var(f"z_{i}_o{oi}", 0, 1, "B")
            lm.outage_vars[(i, oi)] = z
            Ma = bi.ub + bi.duration - os_
            Mb = oe - bi.lb
            lm.add_row({s[i]: 1, z: Ma}, "<=", os_ - bi.duration + Ma)   # z=1: s_i + p_i <= os
            lm.add_row({s[i]: 1, z: Mb}, ">=", oe)                       # z=0: s_i >= oe
    if kept_arcs:
        for u, v in kept_arcs:
            lm.add_row({s[v]: 1, s[u]: -1}, ">=", dur[u])
    lm.stats = {"n_ops": len(bounds), "n_vars": lm.n_vars, "n_binary": lm.n_binary, "n_rows": lm.n_rows,
                "implied_pairs": implied, "H": H, "_dur": dur, "_outages": outages,
                "bound_infeasible": any(l > u for l, u in zip(lm.lb, lm.ub))}
    return lm
