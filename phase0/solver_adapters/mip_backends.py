"""MIP backends. Every backend receives the SAME phase0.jobshop_milp.LinearModel
(identical variables, bounds, coefficients and big-M values), translated
verbatim. Model building in Python and translation into the solver API are
both charged to the budget (build_s).

Backend          anytime                       warm start           licence
gurobi           MIPSOL callback (schedules)   Var.Start            pip size-limited (2000/2000)
cplex            incumbent callback            MIP_starts.add       Community Edition (1000/1000)
scip             BESTSOLFOUND event            addSol (partial)     Apache 2.0
highs            cbMipImprovingSolution        setSolution          MIT
cbc (OR-Tools)   final only                    SetHint              EPL (bundled in OR-Tools)
glpk (swiglpk)   final only                    none                 GPL
Licence size limits are checked by the backend itself; a refusal is
reported as LICENSE_LIMIT, never replaced by another solver's answer."""

from __future__ import annotations

import time

from ..jobshop_milp import LinearModel, build_milp
from .base import AdapterResult, Capabilities, SolveRequest, cached_version, now, remaining


def _schedule_from(lm: LinearModel, values) -> dict[str, int]:
    return {op: int(round(values[k])) for op, k in lm.start_index.items()}


def _build(req: SolveRequest, res: AdapterResult) -> LinearModel:
    lm = build_milp(req.instance, cutoff=req.cutoff, kept_arcs=req.kept_arcs)
    res.model_vars, res.model_binary, res.model_constraints = lm.n_vars, lm.n_binary, lm.n_rows
    return lm


class _MIPBase:
    name = "?"

    def version(self):
        return "?"


# ------------------------------------------------------------------ Gurobi

class GurobiAdapter(_MIPBase):
    name = "gurobi"
    caps = Capabilities(technology="MIP", anytime="callback", warm_start="Var.Start", workers=True,
                        seed_meaningful=True, size_limit=(2000, 2000))

    def version(self):
        import gurobipy as gp
        return ".".join(map(str, gp.gurobi.version())) + " (pip size-limited licence)"

    def solve(self, req):
        import gurobipy as gp
        from gurobipy import GRB
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        lm = _build(req, res)
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
        m = gp.Model(env=env)
        vt = {"I": GRB.INTEGER, "B": GRB.BINARY}
        x = m.addVars(lm.n_vars, lb=lm.lb, ub=lm.ub, vtype=[vt[v] for v in lm.vtype])
        for coefs, sense, rhs in lm.rows:
            e = gp.quicksum(c * x[k] for k, c in coefs.items())
            m.addLConstr(e, {">=": GRB.GREATER_EQUAL, "<=": GRB.LESS_EQUAL, "==": GRB.EQUAL}[sense], rhs)
        m.setObjective(x[lm.obj_var], GRB.MINIMIZE)
        if req.warm_start:
            for k, v in enumerate(lm.start_vector(req.warm_start)):
                if v is not None:
                    x[k].Start = v
        m.Params.Threads = req.workers
        m.Params.Seed = req.seed
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            return res
        m.Params.TimeLimit = lim
        starts = [x[k] for k in lm.start_index.values()]
        keys = list(lm.start_index)

        def cb(model, where):
            if where == GRB.Callback.MIPSOL:
                vals = model.cbGetSolution(starts)
                res.events.append((now(req), int(round(model.cbGet(GRB.Callback.MIPSOL_OBJ))),
                                   {k: int(round(v)) for k, v in zip(keys, vals)}))

        t = time.monotonic()
        try:
            m.optimize(cb)
        except gp.GurobiError as e:
            if e.errno == 10010 or "size-limited" in str(e):
                res.status, res.error = "LICENSE_LIMIT", str(e)[:200]
                return res
            raise
        res.solve_s = time.monotonic() - t
        st = m.Status
        res.status = {GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE"}.get(
            st, "FEASIBLE" if m.SolCount else "UNKNOWN")
        if m.SolCount:
            res.schedule = {k: int(round(v.X)) for k, v in zip(keys, starts)}
            res.objective = int(round(m.ObjVal))
            res.lower_bound = float(m.ObjBound)
            res.proven_optimal = st == GRB.OPTIMAL
        m.dispose(); env.dispose()
        return res


# ------------------------------------------------------------------ CPLEX

class CplexAdapter(_MIPBase):
    name = "cplex"
    caps = Capabilities(technology="MIP", anytime="callback", warm_start="MIP_starts", workers=True,
                        seed_meaningful=True, size_limit=(1000, 1000))

    def version(self):
        import cplex
        return cplex.Cplex().get_version() + " (Community Edition)"

    def solve(self, req):
        import cplex
        from cplex.callbacks import IncumbentCallback
        from cplex.exceptions import CplexSolverError
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        lm = _build(req, res)
        c = cplex.Cplex()
        for stream in (c.set_log_stream, c.set_results_stream, c.set_warning_stream, c.set_error_stream):
            stream(None)
        c.variables.add(lb=lm.lb, ub=lm.ub, types=["I" if v == "I" else "B" for v in lm.vtype])
        c.linear_constraints.add(
            lin_expr=[cplex.SparsePair(list(co), list(co.values())) for co, _, _ in lm.rows],
            senses=[{">=": "G", "<=": "L", "==": "E"}[s] for _, s, _ in lm.rows],
            rhs=[float(r) for _, _, r in lm.rows])
        c.objective.set_linear([(lm.obj_var, 1.0)])
        c.objective.set_sense(c.objective.sense.minimize)
        c.parameters.threads.set(req.workers)
        c.parameters.randomseed.set(req.seed)
        if req.warm_start:
            sv = lm.start_vector(req.warm_start)
            ind = [k for k, v in enumerate(sv) if v is not None]
            c.MIP_starts.add(cplex.SparsePair(ind, [sv[k] for k in ind]), c.MIP_starts.effort_level.repair)
        keys = list(lm.start_index)
        idx = [lm.start_index[k] for k in keys]
        events = res.events

        class CB(IncumbentCallback):
            def __call__(self):
                vals = self.get_values(idx)
                events.append((now(req), int(round(self.get_objective_value())),
                               {k: int(round(v)) for k, v in zip(keys, vals)}))

        c.register_callback(CB)
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            return res
        c.parameters.timelimit.set(lim)
        t = time.monotonic()
        try:
            c.solve()
        except CplexSolverError as e:
            if "ommunity" in str(e) or getattr(e, "args", (None, None, None))[2:3] == (1016,):
                res.status, res.error = "LICENSE_LIMIT", str(e)[:200]
                return res
            raise
        res.solve_s = time.monotonic() - t
        sol = c.solution
        st = sol.get_status_string()
        if sol.get_solution_type() != sol.type.none:
            vals = sol.get_values(idx)
            res.schedule = {k: int(round(v)) for k, v in zip(keys, vals)}
            res.objective = int(round(sol.get_objective_value()))
            res.lower_bound = float(sol.MIP.get_best_objective())
            res.proven_optimal = "optimal" in st and "tolerance" not in st
            res.status = "OPTIMAL" if res.proven_optimal else "FEASIBLE"
        else:
            res.status = "INFEASIBLE" if "infeasible" in st else "UNKNOWN"
        res.notes.append(f"cplex status: {st}")
        c.end()
        return res


# ------------------------------------------------------------------ SCIP

class SCIPAdapter(_MIPBase):
    name = "scip"
    caps = Capabilities(technology="MIP", anytime="callback", warm_start="addSol", workers=False,
                        seed_meaningful=True)

    def version(self):
        import pyscipopt
        return f"{pyscipopt.Model().version()} (PySCIPOpt {pyscipopt.__version__})"

    def solve(self, req):
        from pyscipopt import Eventhdlr, Model, SCIP_EVENTTYPE, quicksum
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=1)
        t = time.monotonic()
        lm = _build(req, res)
        m = Model()
        m.hideOutput()
        x = [m.addVar(lb=lm.lb[k], ub=lm.ub[k], vtype="I" if lm.vtype[k] == "I" else "B")
             for k in range(lm.n_vars)]
        for coefs, sense, rhs in lm.rows:
            e = quicksum(c * x[k] for k, c in coefs.items())
            m.addCons(e >= rhs if sense == ">=" else (e <= rhs if sense == "<=" else e == rhs))
        m.setObjective(x[lm.obj_var], "minimize")
        m.setIntParam("randomization/randomseedshift", req.seed)
        keys = list(lm.start_index)

        class H(Eventhdlr):
            def eventinit(self):
                self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

            def eventexit(self):
                self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

            def eventexec(self, event):
                sol = self.model.getBestSol()
                res.events.append((now(req), int(round(self.model.getSolObjVal(sol))),
                                   {k: int(round(self.model.getSolVal(sol, x[lm.start_index[k]]))) for k in keys}))

        m.includeEventhdlr(H(), "best", "record improving solutions")
        if req.warm_start:
            sv = lm.start_vector(req.warm_start)
            s = m.createPartialSol()
            for k, v in enumerate(sv):
                if v is not None:
                    m.setSolVal(s, x[k], v)
            m.addSol(s)
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            return res
        m.setRealParam("limits/time", lim)
        t = time.monotonic()
        m.optimize()
        res.solve_s = time.monotonic() - t
        st = m.getStatus()
        if m.getNSols() > 0:
            sol = m.getBestSol()
            res.schedule = {k: int(round(m.getSolVal(sol, x[lm.start_index[k]]))) for k in keys}
            res.objective = int(round(m.getSolObjVal(sol)))
            res.lower_bound = float(m.getDualbound())
            res.proven_optimal = st == "optimal"
            res.status = "OPTIMAL" if res.proven_optimal else "FEASIBLE"
        else:
            res.status = "INFEASIBLE" if st == "infeasible" else "UNKNOWN"
        return res


# ------------------------------------------------------------------ HiGHS

class HiGHSAdapter(_MIPBase):
    name = "highs"
    caps = Capabilities(technology="MIP", anytime="callback", warm_start="setSolution", workers=False,
                        seed_meaningful=True)

    def version(self):
        import highspy
        return highspy.Highs().version()

    def solve(self, req):
        import highspy
        import numpy as np
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=1)
        t = time.monotonic()
        lm = _build(req, res)
        h = highspy.Highs()
        h.setOptionValue("output_flag", False)
        h.setOptionValue("random_seed", int(req.seed))
        h.setOptionValue("threads", 1)
        n = lm.n_vars
        h.addVars(n, np.array(lm.lb, dtype=float), np.array(lm.ub, dtype=float))
        h.changeColsIntegrality(n, np.arange(n, dtype=np.int32),
                                np.array([highspy.HighsVarType.kInteger] * n))
        cost = np.zeros(n); cost[lm.obj_var] = 1.0
        h.changeColsCost(n, np.arange(n, dtype=np.int32), cost)
        inf = highspy.kHighsInf
        lo, up, starts, index, value = [], [], [], [], []
        for coefs, sense, rhs in lm.rows:
            lo.append(rhs if sense in (">=", "==") else -inf)
            up.append(rhs if sense in ("<=", "==") else inf)
            starts.append(len(index))
            index.extend(coefs); value.extend(coefs.values())
        h.addRows(len(lo), np.array(lo, dtype=float), np.array(up, dtype=float), len(index),
                  np.array(starts, dtype=np.int32), np.array(index, dtype=np.int32), np.array(value, dtype=float))
        keys = list(lm.start_index)
        cols = [lm.start_index[k] for k in keys]

        def cb(e):
            sol = e.data_out.mip_solution
            res.events.append((now(req), int(round(e.data_out.objective_function_value)),
                               {k: int(round(sol[c])) for k, c in zip(keys, cols)}))

        h.cbMipImprovingSolution.subscribe(cb)
        if req.warm_start:
            sv = lm.start_vector(req.warm_start)
            if all(v is not None for v in sv):
                hs = highspy.HighsSolution()
                hs.col_value = [float(v) for v in sv]
                h.setSolution(hs)
            else:
                res.notes.append("warm start incomplete (new operations): HiGHS needs a full vector, skipped")
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            return res
        h.setOptionValue("time_limit", float(lim))
        t = time.monotonic()
        h.run()
        res.solve_s = time.monotonic() - t
        ms = h.getModelStatus()
        info = h.getInfo()
        if info.primal_solution_status == 2:  # kSolutionStatusFeasible
            sol = h.getSolution().col_value
            res.schedule = {k: int(round(sol[c])) for k, c in zip(keys, cols)}
            res.objective = int(round(info.objective_function_value))
            res.lower_bound = float(info.mip_dual_bound)
            res.proven_optimal = ms == highspy.HighsModelStatus.kOptimal
            res.status = "OPTIMAL" if res.proven_optimal else "FEASIBLE"
        else:
            res.status = "INFEASIBLE" if ms == highspy.HighsModelStatus.kInfeasible else "UNKNOWN"
        return res


# ------------------------------------------------------------------ CBC (via OR-Tools pywraplp)

class CBCAdapter(_MIPBase):
    name = "cbc"
    caps = Capabilities(technology="MIP", anytime="final_only", warm_start="SetHint", workers=True,
                        seed_meaningful=False)

    def version(self):
        from ortools.linear_solver import pywraplp
        return pywraplp.Solver.CreateSolver("CBC").SolverVersion() + " (via OR-Tools pywraplp)"

    def solve(self, req):
        from ortools.linear_solver import pywraplp
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        lm = _build(req, res)
        s = pywraplp.Solver.CreateSolver("CBC")
        x = [s.IntVar(lm.lb[k], lm.ub[k], lm.names[k]) for k in range(lm.n_vars)]
        for coefs, sense, rhs in lm.rows:
            ct = s.Constraint(rhs if sense in (">=", "==") else -s.infinity(),
                              rhs if sense in ("<=", "==") else s.infinity())
            for k, c in coefs.items():
                ct.SetCoefficient(x[k], c)
        s.Minimize(x[lm.obj_var])
        if req.warm_start:
            sv = lm.start_vector(req.warm_start)
            ks = [k for k, v in enumerate(sv) if v is not None]
            s.SetHint([x[k] for k in ks], [sv[k] for k in ks])
        if req.workers > 1:
            s.SetNumThreads(req.workers)
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            return res
        s.SetTimeLimit(int(lim * 1000))
        t = time.monotonic()
        st = s.Solve()
        res.solve_s = time.monotonic() - t
        if st in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            res.schedule = {k: int(round(x[i].solution_value())) for k, i in lm.start_index.items()}
            res.objective = int(round(s.Objective().Value()))
            res.lower_bound = float(s.Objective().BestBound())
            res.proven_optimal = st == pywraplp.Solver.OPTIMAL
            res.status = "OPTIMAL" if res.proven_optimal else "FEASIBLE"
        else:
            res.status = "INFEASIBLE" if st == pywraplp.Solver.INFEASIBLE else "UNKNOWN"
        return res


# ------------------------------------------------------------------ GLPK

class GLPKAdapter(_MIPBase):
    name = "glpk"
    caps = Capabilities(technology="MIP", anytime="final_only", warm_start="none", workers=False,
                        seed_meaningful=False)

    def version(self):
        import swiglpk as g
        return g.glp_version()

    def solve(self, req):
        import swiglpk as g
        if req.warm_start is not None:
            raise NotImplementedError("GLPK has no MIP-start API")
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=1)
        t = time.monotonic()
        lm = _build(req, res)
        g.glp_term_out(g.GLP_OFF)
        p = g.glp_create_prob()
        g.glp_set_obj_dir(p, g.GLP_MIN)
        g.glp_add_cols(p, lm.n_vars)
        for k in range(lm.n_vars):
            j = k + 1
            if lm.lb[k] == lm.ub[k]:
                g.glp_set_col_bnds(p, j, g.GLP_FX, lm.lb[k], lm.ub[k])
            else:
                g.glp_set_col_bnds(p, j, g.GLP_DB, lm.lb[k], lm.ub[k])
            g.glp_set_col_kind(p, j, g.GLP_IV if lm.vtype[k] == "I" else g.GLP_BV)
        g.glp_set_obj_coef(p, lm.obj_var + 1, 1.0)
        g.glp_add_rows(p, lm.n_rows)
        for r, (coefs, sense, rhs) in enumerate(lm.rows, start=1):
            kind = {">=": g.GLP_LO, "<=": g.GLP_UP, "==": g.GLP_FX}[sense]
            g.glp_set_row_bnds(p, r, kind, rhs, rhs)
            n = len(coefs)
            ind, val = g.intArray(n + 1), g.doubleArray(n + 1)
            for q, (k, c) in enumerate(coefs.items(), start=1):
                ind[q], val[q] = k + 1, c
            g.glp_set_mat_row(p, r, n, ind, val)
        res.build_s = time.monotonic() - t
        lim = remaining(req)
        if lim <= 0.01:
            res.status = "NO_TIME"
            g.glp_delete_prob(p)
            return res
        parm = g.glp_iocp()
        g.glp_init_iocp(parm)
        parm.presolve = g.GLP_ON
        parm.tm_lim = max(1, int(lim * 1000))
        parm.msg_lev = g.GLP_MSG_OFF
        t = time.monotonic()
        ret = g.glp_intopt(p, parm)
        res.solve_s = time.monotonic() - t
        st = g.glp_mip_status(p)
        if ret == g.GLP_ENOPFS:      # presolver proved the LP relaxation (hence the MIP) infeasible
            st = g.GLP_NOFEAS
        elif ret == g.GLP_EBOUND and lm.stats["bound_infeasible"]:
            st = g.GLP_NOFEAS        # a column domain is empty (e.g. cutoff below the makespan lower bound)
        elif ret not in (0, g.GLP_ETMLIM):
            res.notes.append(f"glp_intopt returned {ret}")
        if st in (g.GLP_OPT, g.GLP_FEAS):
            res.schedule = {k: int(round(g.glp_mip_col_val(p, i + 1))) for k, i in lm.start_index.items()}
            res.objective = int(round(g.glp_mip_obj_val(p)))
            res.proven_optimal = st == g.GLP_OPT
            res.status = "OPTIMAL" if res.proven_optimal else "FEASIBLE"
        else:
            res.status = "INFEASIBLE" if st == g.GLP_NOFEAS else "UNKNOWN"
        g.glp_delete_prob(p)
        return res
