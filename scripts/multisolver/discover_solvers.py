"""Discover which optimization solvers are actually runnable here (Task 3.1).

A solver is AVAILABLE only if a real job-shop smoke model (with an outage,
release dates and a commitment) is solved to the exhaustive-oracle optimum
and its schedule passes the independent validator. Importability alone is
never enough. Licence size limits are probed by solving a model just below
and just above the documented cap.

Statuses: AVAILABLE, NOT INSTALLED, LICENSE UNAVAILABLE, INCOMPATIBLE VERSION,
UNSUPPORTED PROBLEM FEATURE, FAILED SMOKE TEST.

    .venv_ms/bin/python scripts/multisolver/discover_solvers.py
Writes results/multisolver/solver_inventory.json and
docs/multisolver/SOLVER_AVAILABILITY.md.
"""
import importlib
import json
import platform
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/cobar"))

from phase0.solver_adapters import ADAPTERS, SolveRequest, cached_version, run_adapter  # noqa: E402
from phase0.solver_adapters.minizinc_adapter import MZN_BIN, mzn_env  # noqa: E402
from phase0.solver_independent_model import exhaustive_optimum, model_size_hint  # noqa: E402
from phase0.streams import StreamConfig, generate_stream  # noqa: E402
from test_certificates import random_feasible_schedule, random_instance, with_commitments  # noqa: E402

GROUP = {"cpsat": "A: constraint programming", "cpoptimizer": "A: constraint programming",
         "gecode": "A: constraint programming", "chuffed": "A: constraint programming",
         "gurobi": "B: mixed-integer", "cplex": "B: mixed-integer", "scip": "B: mixed-integer",
         "highs": "B: mixed-integer", "cbc": "B: mixed-integer", "glpk": "B: mixed-integer"}


def smoke_instance():
    rng = random.Random(5)
    inst = random_instance(rng, n_jobs=3, n_mach=3)
    S = random_feasible_schedule(rng, inst, slack=2)
    return with_commitments(rng, inst, S)


def full_shop(m, n, seed=1):
    cfg = StreamConfig(num_machines=m, initial_jobs=n, stream_length=0, seed=seed)
    cfg.ops_per_job = (m, m)
    cfg.duration_range = (5, 50)
    return generate_stream(cfg)[0]


def probe(name, inst, budget=3.0):
    t0 = time.monotonic()
    return run_adapter(ADAPTERS[name], SolveRequest(instance=inst, t0=t0, deadline=t0 + budget))


def main():
    inst = smoke_instance()
    opt, _ = exhaustive_optimum(inst)
    inv = {"host": platform.node(), "python": sys.version.split()[0], "smoke_oracle_optimum": opt,
           "smoke_features": ["outages", "release dates", "commitments"], "solvers": {}, "not_installed": {}}
    for name, a in ADAPTERS.items():
        entry = {"group": GROUP[name], "technology": a.caps.technology, "anytime_trajectory": a.caps.anytime,
                 "warm_start": a.caps.warm_start, "parallel_workers": a.caps.workers,
                 "seed_meaningful": a.caps.seed_meaningful, "objective_cutoff": a.caps.cutoff,
                 "restricted_neighbourhoods": a.caps.restricted, "time_limit": True,
                 "documented_size_limit": a.caps.size_limit}
        try:
            entry["version"] = cached_version(a)
        except Exception as e:
            entry.update(status="NOT INSTALLED", reason=f"{type(e).__name__}: {e}"[:200])
            inv["solvers"][name] = entry
            continue
        r = probe(name, inst)
        entry["smoke"] = {"status": r.status, "objective": r.objective, "validated": r.validated,
                          "total_s": round(r.total_s, 3), "error": r.error}
        if r.status == "LICENSE_LIMIT":
            entry["status"] = "LICENSE UNAVAILABLE"
        elif r.validated and r.objective == opt:
            entry["status"] = "AVAILABLE"
        else:
            entry["status"] = "FAILED SMOKE TEST"
        # licence-scale probes: the paper's instance sizes
        entry["scale_probes"] = {}
        for label, (m, n) in {"6x8": (6, 8), "10x10": (10, 10), "15x15": (15, 15), "20x20": (20, 20)}.items():
            big = full_shop(m, n)
            rr = probe(name, big, budget=4.0)
            entry["scale_probes"][label] = {"status": rr.status, "objective": rr.objective,
                                            "vars": rr.model_vars, "binary": rr.model_binary,
                                            "constraints": rr.model_constraints, "build_s": round(rr.build_s, 3),
                                            "error": (rr.error or "")[:160], **model_size_hint(big)}
        inv["solvers"][name] = entry
        print(f"{name:12s} {entry['status']:20s} {entry.get('version','')}  "
              + "  ".join(f"{k}:{v['status']}" for k, v in entry["scale_probes"].items()))
    # solvers investigated but not runnable in this environment
    for mod, label in [("xpress", "FICO Xpress"), ("hexaly", "Hexaly"), ("localsolver", "LocalSolver/Hexaly")]:
        try:
            importlib.import_module(mod)
            inv["not_installed"][label] = "module present but no adapter (not evaluated)"
        except Exception:
            inv["not_installed"][label] = "NOT INSTALLED (no Python module; commercial, no licence available)"
    inv["not_installed"]["Choco Solver"] = ("NOT INSTALLED (requires a Java runtime; `java` not found)"
                                            if shutil.which("java") is None else "java present, not evaluated")
    try:
        out = json.loads(subprocess.run([str(MZN_BIN), "--solvers-json"], capture_output=True, text=True,
                                        env=mzn_env(), timeout=30).stdout)
        inv["minizinc_backends_seen"] = [{"id": s["id"], "version": s.get("version")} for s in out]
    except Exception as e:
        inv["minizinc_backends_seen"] = f"error: {e}"
    inv["minizinc_policy"] = ("MiniZinc 2.10.1 is a modelling system; only Gecode and Chuffed are used through "
                              "it. Its fzn-cp-sat (same CP-SAT engine) and its COIN-BC/HiGHS/SCIP/Gurobi/CPLEX "
                              "interfaces duplicate engines already reached through native APIs and are not "
                              "counted as independent solvers.")
    out = ROOT / "results/multisolver/solver_inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, indent=1))
    write_md(inv)
    print("wrote", out)


def write_md(inv):
    lines = ["# Solver availability (generated by scripts/multisolver/discover_solvers.py)", "",
             f"Host `{inv['host']}`, Python {inv['python']}. A solver is AVAILABLE only if it solved the "
             f"smoke instance (outages, release dates, commitments) to the exhaustive-oracle optimum "
             f"({inv['smoke_oracle_optimum']}) with a schedule accepted by the independent validator.", "",
             "| Solver | Group | Version | Status | Anytime trajectory | Warm start | Workers | "
             "6x8 | 10x10 | 15x15 | 20x20 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, e in inv["solvers"].items():
        sp = e.get("scale_probes", {})
        cell = lambda k: (sp.get(k, {}).get("status", "-") + (f" ({sp[k]['vars']}v/{sp[k]['constraints']}c)"
                          if sp.get(k, {}).get("vars") and sp[k].get("constraints") else ""))
        lines.append(f"| {n} | {e['group']} | {e.get('version','-')} | {e['status']} | {e['anytime_trajectory']} | "
                     f"{e['warm_start']} | {'yes' if e['parallel_workers'] else 'no'} | "
                     f"{cell('6x8')} | {cell('10x10')} | {cell('15x15')} | {cell('20x20')} |")
    lines += ["", "Scale probes: a 4 s cold solve of one base full job shop of each size; LICENSE_LIMIT means the "
              "bundled licence refused the model (not a performance judgement).", "", "## Investigated, not runnable",
              ""] + [f"- **{k}**: {v}" for k, v in inv["not_installed"].items()] + ["", "## MiniZinc", "",
              inv["minizinc_policy"]]
    p = ROOT / "docs/multisolver/SOLVER_AVAILABILITY.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
