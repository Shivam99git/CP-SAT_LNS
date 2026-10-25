"""Audit of intermediate CP-SAT incumbents (docs/cobar/01 §4, 06). The
campaigns record every improving solver solution from objective_value and
validate only the final schedule. This audit re-solves a sample of
development instances with a callback that extracts the full schedule of
every solution, validates each with the independent validator, and checks
that the validator's makespan equals the reported objective. Timing is
irrelevant here (efficiency cores).

    taskset -c 16-19 .venv/bin/python scripts/cobar/audit_intermediate.py
"""
import json
import sys
from pathlib import Path

from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from phase0.cobar import build_cobar_restricted_model  # noqa: E402
from phase0.model_builder import build_model, solve  # noqa: E402
from phase0.reuse_methods import build_research_model  # noqa: E402
from phase0.run_iaip_campaign import CampaignSpec  # noqa: E402
from phase0.schedule_validator import ScheduleError, check_schedule  # noqa: E402
from phase0.selective_reoptimization import disruption_set, make_neighbourhood  # noqa: E402

rows = []
for m, seed in ((15, 301), (20, 301), (15, 302), (20, 302)):
    stream = CampaignSpec(m, m, seed, 6).build()
    prev = solve(build_model(stream[0]), time_limit=1.0)[0]
    for k in range(1, len(stream)):
        inst = stream[k]
        inc = solve(build_model(inst), time_limit=0.5)[0]
        U = check_schedule(inst, inc)
        N = make_neighbourhood("N5", inst, inc, disruption_set(stream[k - 1], inst, prev), 0.25)
        for kind, built in (("global", build_research_model(inst, hint=inc)),
                            ("restricted", build_cobar_restricted_model(inst, inc, N, set(), True, U)[0])):
            sols = []

            class CB(cp_model.CpSolverSolutionCallback):
                def on_solution_callback(self):
                    sols.append((int(self.objective_value),
                                 {v: int(self.value(x)) for v, x in built.starts.items()}))
            s = cp_model.CpSolver()
            s.parameters.num_workers = 1
            s.parameters.max_time_in_seconds = 3.0
            s.solve(built.model, CB())
            for obj, sol in sols:
                try:
                    mk = check_schedule(inst, sol)
                    ok, err = mk == obj, None if mk == obj else f"makespan {mk} != reported {obj}"
                except ScheduleError as e:
                    ok, err = False, str(e)
                rows.append({"instance": f"{m}x{m}_s{seed}_t{k}", "model": kind, "objective": obj, "valid": ok, "error": err})
        prev = inc
out = Path("results/cobar/audit_intermediate.json")
out.parent.mkdir(parents=True, exist_ok=True)
summary = {"solutions_checked": len(rows), "invalid": sum(not r["valid"] for r in rows),
           "by_model": {k: sum(1 for r in rows if r["model"] == k) for k in ("global", "restricted")},
           "instances": len({r["instance"] for r in rows}), "rows": rows}
out.write_text(json.dumps(summary, indent=1))
print({k: v for k, v in summary.items() if k != "rows"})
