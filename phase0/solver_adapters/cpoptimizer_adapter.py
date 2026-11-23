"""IBM ILOG CP Optimizer adapter (docplex.cp + the pip-bundled Community
Edition `cpoptimizer` binary; CE is size-limited, so oversized models return
LICENSE_LIMIT rather than a substituted result).

Native scheduling model: one interval variable per positive-duration
operation (fixed start for commitments, start >= release), end_before_start
for job precedence, no_overlap per machine including fixed outage intervals,
makespan = max end. Zero-duration operations are plain integer start
variables outside no_overlap (they occupy no machine time, matching the
validator). Warm start = CpoModel.set_starting_point.

Intermediate solutions are streamed with CpoSolver.search_next(); in
optimization mode CPO keeps enumerating equal-objective solutions after
proving optimality, so the loop stops on the Optimal status or the deadline
and calls end_search()."""

from __future__ import annotations

import time
from pathlib import Path

from .base import AdapterResult, Capabilities, SolveRequest, cached_version, now, remaining

CPO_EXEC = str(Path(__file__).resolve().parents[2] / ".venv/bin/cpoptimizer")


class CPOptimizerAdapter:
    name = "cpoptimizer"
    caps = Capabilities(technology="CP", anytime="stream", warm_start="set_starting_point", workers=True,
                        seed_meaningful=True, size_limit=(1000, 1000))

    @staticmethod
    def version():
        import docplex
        return f"CE (docplex {docplex.__version__})"

    def solve(self, req: SolveRequest) -> AdapterResult:
        from docplex.cp.model import CpoModel
        from docplex.cp.solution import CpoModelSolution
        from docplex.cp.solver.solver import CpoSolver
        inst = req.instance
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        m = CpoModel()
        H = inst.horizon
        itv, intv_by_m, last = {}, {}, []
        frozen = inst.frozen_starts
        for job in inst.jobs:
            prev = None
            for op in job.ops:
                lo = max(job.release_date, 0)
                if op.op_id in frozen:
                    st = (frozen[op.op_id], frozen[op.op_id])
                else:
                    st = (lo, H)
                x = m.interval_var(size=op.duration, start=st, end=(0, H), name=op.op_id)
                itv[op.op_id] = x
                if op.duration > 0:
                    intv_by_m.setdefault(op.machine, []).append(x)
                if prev is not None:
                    m.add(m.end_before_start(prev, x))
                prev = x
            if prev is not None:
                last.append(prev)
        for k, o in enumerate(inst.outages):
            if o.end > o.start:
                intv_by_m.setdefault(o.machine, []).append(
                    m.interval_var(start=(o.start, o.start), end=(o.end, o.end), size=o.end - o.start,
                                   name=f"out{k}"))
        for xs in intv_by_m.values():
            if len(xs) > 1:
                m.add(m.no_overlap(xs))
        mk = m.max([m.end_of(x) for x in last])
        if req.cutoff is not None:
            m.add(mk <= req.cutoff)
        if req.kept_arcs:
            for u, v in req.kept_arcs:
                m.add(m.end_before_start(itv[u], itv[v]))
        m.add(m.minimize(mk))
        if req.warm_start:
            sp = CpoModelSolution()
            dur = {o.op_id: o.duration for o in inst.all_ops}
            for op_id, s in req.warm_start.items():
                if op_id in itv:
                    sp.add_interval_var_solution(itv[op_id], presence=True, start=s, end=s + dur[op_id],
                                                 size=dur[op_id])
            m.set_starting_point(sp)
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.02:
            res.status = "NO_TIME"
            return res
        t = time.monotonic()
        solver = CpoSolver(m, TimeLimit=max(0.01, lim - 0.01), Workers=req.workers, RandomSeed=req.seed,
                           LogVerbosity="Quiet", execfile=CPO_EXEC, **req.params)
        last_sol, status = None, "UNKNOWN"
        try:
            while remaining(req) > 0:
                sol = solver.search_next()
                if not sol.is_solution():
                    ss = sol.get_solve_status()
                    if ss == "Infeasible":
                        status = "INFEASIBLE"
                    elif last_sol is not None and ss == "Optimal":
                        status = "OPTIMAL"
                    break
                last_sol = sol
                sched = {k: int(sol.get_var_solution(x).get_start()) for k, x in itv.items()}
                res.events.append((now(req), int(sol.get_objective_values()[0]), sched))
                status = "FEASIBLE"
                if sol.get_solve_status() == "Optimal":
                    status = "OPTIMAL"
                    break
        except Exception as e:
            msg = str(e)
            if "ommunity" in msg or "limit" in msg.lower() and "size" in msg.lower():
                res.status, res.error = "LICENSE_LIMIT", msg[:300]
                return res
            raise
        finally:
            try:
                solver.end_search()
            except Exception:
                pass
        res.solve_s = time.monotonic() - t
        res.status = status
        if last_sol is not None:
            info = last_sol.get_solver_infos()
            res.model_vars, res.model_constraints = info.get("NumberOfVariables"), info.get("NumberOfConstraints")
            res.model_binary = 0
            res.schedule = res.events[-1][2]
            res.objective = res.events[-1][1]
            b = last_sol.get_objective_bounds()
            res.lower_bound = float(b[0]) if b else None
            res.proven_optimal = status == "OPTIMAL"
        return res
