"""OR-Tools CP-SAT adapter: the project's verified research model
(reuse_methods.build_research_model: intervals, no_overlap with outage
intervals, releases, exact commitments), plus optional cutoff / kept arcs.
Warm start = CP-SAT solution hints (a search hint, not a retained incumbent)."""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from ..reuse_methods import build_research_model
from .base import AdapterResult, Capabilities, SolveRequest, cached_version, now, remaining

STATUS = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE", cp_model.INFEASIBLE: "INFEASIBLE",
          cp_model.UNKNOWN: "UNKNOWN", cp_model.MODEL_INVALID: "ERROR"}


class CPSATAdapter:
    name = "cpsat"
    caps = Capabilities(technology="CP", anytime="callback", warm_start="AddHint", workers=True,
                        seed_meaningful=True)

    @staticmethod
    def version():
        import ortools
        return ortools.__version__

    def solve(self, req: SolveRequest) -> AdapterResult:
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        built = build_research_model(req.instance, hint=req.warm_start)
        if req.cutoff is not None:
            built.model.add(built.makespan <= req.cutoff)
        if req.kept_arcs:
            dur = {o.op_id: o.duration for o in req.instance.all_ops}
            for u, v in req.kept_arcs:
                built.model.add(built.starts[v] >= built.starts[u] + dur[u])
        proto = built.model.proto
        res.model_vars, res.model_constraints = len(proto.variables), len(proto.constraints)
        res.model_binary = 0
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.005:
            res.status = "NO_TIME"
            return res
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = lim
        solver.parameters.num_workers = req.workers
        solver.parameters.random_seed = req.seed
        for k, v in req.params.items():
            setattr(solver.parameters, k, v)
        starts = built.starts
        events = res.events

        class CB(cp_model.CpSolverSolutionCallback):
            def on_solution_callback(self):
                events.append((now(req), int(self.objective_value),
                               {k: int(self.value(x)) for k, x in starts.items()}))

        t = time.monotonic()
        st = solver.solve(built.model, CB())
        res.solve_s = time.monotonic() - t
        res.status = STATUS.get(st, str(st))
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            res.schedule = {k: int(solver.value(x)) for k, x in starts.items()}
            res.objective = int(solver.objective_value)
            res.lower_bound = float(solver.best_objective_bound)
            res.proven_optimal = st == cp_model.OPTIMAL
        return res
