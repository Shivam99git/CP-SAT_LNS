"""MiniZinc adapter. MiniZinc is a modelling system, not an algorithm: each
adapter instance is bound to ONE backend (gecode, chuffed, ...) and results
are reported under that backend's name. One fixed model
(mzn/jobshop.mzn, `disjunctive` global with outage blocks as fixed tasks);
per-instance JSON data with the same start bounds as every other backend.

Run as a subprocess with intermediate solutions streamed as JSON lines.
Everything after the call -- writing the data file, starting the process,
flattening, solving -- counts against the deadline; the process is killed at
the deadline if it has not stopped. Warm starts are not used (not verified
for these backends), so warm_start requests raise NotImplementedError and the
runner records NOT_SUPPORTED."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from ..solver_independent_model import op_bounds
from .base import AdapterResult, Capabilities, SolveRequest, cached_version, now, remaining

ROOT = Path(__file__).resolve().parents[2]
MZN_HOME = ROOT / ".solvers/MiniZincIDE-2.10.1-x86_64-linux-gnu"
MZN_BIN = MZN_HOME / "bin/minizinc"
MODEL = Path(__file__).with_name("mzn") / "jobshop.mzn"


def mzn_env():
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = f"{MZN_HOME / 'lib'}:{env.get('LD_LIBRARY_PATH', '')}"
    env["PATH"] = f"{MZN_HOME / 'bin'}:{env['PATH']}"
    return env


def instance_data(req: SolveRequest) -> tuple[dict, list[str]]:
    inst = req.instance
    bounds, H = op_bounds(inst)
    ids = [b.op_id for b in bounds]
    idx = {v: k + 1 for k, v in enumerate(ids)}
    pa, pb, last = [], [], []
    for job in inst.jobs:
        for a, b in zip(job.ops, job.ops[1:]):
            pa.append(idx[a.op_id]); pb.append(idx[b.op_id])
        if job.ops:
            last.append(idx[job.ops[-1].op_id])
    arcs = req.kept_arcs or []
    d = {"n": len(ids), "n_mach": inst.num_machines, "H": H,
         "mach": [b.machine + 1 for b in bounds], "dur": [b.duration for b in bounds],
         "lb": [b.lb for b in bounds], "ub": [b.ub for b in bounds],
         "n_prec": len(pa), "pa": pa, "pb": pb, "n_last": len(last), "last": last,
         "n_out": len(inst.outages), "om": [o.machine + 1 for o in inst.outages],
         "os": [o.start for o in inst.outages], "oe": [o.end for o in inst.outages],
         "n_arc": len(arcs), "au": [idx[u] for u, _ in arcs], "av": [idx[v] for _, v in arcs],
         "cutoff": H if req.cutoff is None else min(H, req.cutoff)}
    return d, ids


class MiniZincAdapter:
    def __init__(self, backend: str, workers_flag: bool, seed_meaningful: bool):
        self.backend = backend
        self.name = backend
        self.caps = Capabilities(technology="CP", anytime="stream", warm_start="none", workers=workers_flag,
                                 seed_meaningful=seed_meaningful)

    def version(self):
        if getattr(self, "_version", None) is None:
            self._version = self._query_version()
        return self._version

    def _query_version(self):
        try:
            out = subprocess.run([str(MZN_BIN), "--solvers-json"], capture_output=True, text=True,
                                 env=mzn_env(), timeout=20).stdout
            for s in json.loads(out):
                if self.backend in s.get("tags", []) or s.get("id", "").endswith(self.backend):
                    return f"{s.get('version')} (MiniZinc 2.10.1)"
        except Exception:
            pass
        return "unknown"

    def solve(self, req: SolveRequest) -> AdapterResult:
        if req.warm_start is not None:
            raise NotImplementedError("warm start not supported for MiniZinc backends in this study")
        res = AdapterResult(solver=self.name, version=cached_version(self), threads=req.workers)
        t = time.monotonic()
        data, ids = instance_data(req)
        with tempfile.TemporaryDirectory(prefix="mzn_") as td:
            dpath = Path(td) / "data.json"
            dpath.write_text(json.dumps(data))
            res.build_s = time.monotonic() - t
            lim = remaining(req)
            if lim <= 0.05:
                res.status = "NO_TIME"
                return res
            cmd = [str(MZN_BIN), "--solver", self.backend, str(MODEL), str(dpath), "-i", "--json-stream",
                   "--output-time", "--time-limit", str(int(lim * 1000))]
            if self.caps.workers and req.workers > 1:
                cmd += ["-p", str(req.workers)]
            if self.caps.seed_meaningful:
                cmd += ["-r", str(req.seed)]
            t = time.monotonic()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=mzn_env())
            status, best = "UNKNOWN", None
            try:
                for line in proc.stdout:
                    if remaining(req) < -0.5:
                        break
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "solution":
                        out = json.loads(msg["output"]["default"]) if "default" in msg.get("output", {}) \
                            else json.loads(msg["output"]["raw"])
                        sched = {v: int(x) for v, x in zip(ids, out["s"])}
                        res.events.append((now(req), int(out["cmax"]), sched))
                        best = (int(out["cmax"]), sched)
                        status = "FEASIBLE"
                    elif msg.get("type") == "status":
                        st = msg.get("status")
                        if st == "OPTIMAL_SOLUTION":
                            status = "OPTIMAL"
                        elif st == "UNSATISFIABLE":
                            status = "INFEASIBLE"
                        elif st == "ERROR":
                            status = "ERROR"
                    elif msg.get("type") == "error":
                        res.error = str(msg.get("message"))[:300]
                        status = "ERROR"
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            res.solve_s = time.monotonic() - t
        res.status = status
        if best is not None:
            res.objective, res.schedule = best
            res.proven_optimal = status == "OPTIMAL"
        res.model_vars, res.model_constraints, res.model_binary = len(ids) + 1, None, 0
        return res


GECODE = MiniZincAdapter("gecode", workers_flag=True, seed_meaningful=False)
CHUFFED = MiniZincAdapter("chuffed", workers_flag=False, seed_meaningful=False)
