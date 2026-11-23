"""Write and hash the frozen held-out multisolver plan (Task 7.3/7.4).

Everything that defines the held-out campaign is fixed here BEFORE any
held-out run: tiers, streams (size-only selection rule), solvers, methods,
budgets, workers, seeds, exclusion rules, primary metric, comparison families
(Holm correction within each family), and Experiment C's per-solver
configurations, which are chosen from DEVELOPMENT pilot results only.

    .venv_ms/bin/python scripts/multisolver/make_frozen_plan.py --pilot results/multisolver/analysis/pilot.json
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL = ["cpsat", "cpoptimizer", "gecode", "chuffed", "gurobi", "cplex", "scip", "highs", "cbc", "glpk"]
STOCH = ["cpsat", "cpoptimizer", "gurobi", "cplex", "scip", "highs"]
M_EXEC = ["cpsat", "gecode", "chuffed", "scip", "highs", "cbc", "glpk"]
LICENCE_CAPPED = ["cpoptimizer", "gurobi", "cplex"]
METHODS = ["S0", "S1", "S2", "S3", "S4", "S5"]
STEPS = list(range(1, 11))


def seeds(stoch):
    return {"default": [0], **{s: [0, 1, 2, 3, 4] for s in stoch}}


def key(exp, tier, solver, method, budget=8, workers=1):
    return [exp, tier, solver, method, budget, workers]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True)
    a = ap.parse_args()
    pilot = json.loads(Path(a.pilot).read_text())["configs"]

    # Experiment C: per solver and tier, the method with the lowest DEVELOPMENT mean PI
    # (ties -> simpler method); configurations that were never executable are skipped
    best = {}
    for tier in ("S", "M15"):
        for solver in ALL:
            cands = [(c["mean_pi"], METHODS.index(c["method"]), c["method"]) for c in pilot.values()
                     if c["tier"] == tier and c["solver"] == solver and c["budget"] == 8 and c["workers"] == 1
                     and c["mean_pi"] is not None and c["licence_limited_rate"] < 1.0]
            if cands:
                best[f"{tier}|{solver}"] = min(cands)[2]

    I = "results/multisolver/instances/heldout"
    plan = {
        "frozen_by": "scripts/multisolver/make_frozen_plan.py",
        "git_revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "shuffle_seed": 3101,
        "primary_metric": "primal integral (common best-known z* per physical instance over all held-out records), "
                          "stream as unit, steps 1-10 and seeds averaged within stream",
        "selection_rule": "tier S: first 10 streams from seed 3101 upward whose every step fits CPLEX CE (1000 vars/"
                          "1000 constraints) and CP Optimizer CE; tiers M15/M20: first 5 streams from seed 3201",
        "exclusion_rules": [
            "no run is excluded for performance; every NO_SOLUTION/INVALID/ERROR record stays (PI = 1)",
            "incumbents returned after the deadline get no credit (PI, final gap, feasible rate use the incumbent at B)",
            "licence refusals (LICENSE_LIMIT) are reported as NOT EXECUTED, not as performance",
            "a (method, solver) pair the solver cannot implement equivalently is NOT_SUPPORTED, recorded, not imputed",
        ],
        "contention_policy": "host shared with an unrelated CPU-bound workload; per-run CPU/wall and load average are "
                             "recorded and a sensitivity analysis on low-contention runs is pre-declared (cpu/wall >= 0.8)",
        "experiment_C_choice_from_dev": best,
        "experiments": [
            {"name": "AB", "blocks": [
                {"tier": "S", "instances": f"{I}/S", "steps": STEPS, "solvers": ALL, "methods": METHODS,
                 "budgets": [8], "workers": [1], "seeds": seeds(STOCH),
                 "seeds_by_method": {m: [0] for m in METHODS if m != "S0"}},
                {"tier": "M15", "instances": f"{I}/M15", "steps": STEPS, "solvers": M_EXEC, "methods": METHODS,
                 "budgets": [8], "workers": [1], "seeds": seeds(["cpsat", "scip", "highs"]),
                 "seeds_by_method": {m: [0] for m in METHODS if m != "S0"}},
                {"tier": "M20", "instances": f"{I}/M20", "steps": STEPS, "solvers": M_EXEC, "methods": METHODS,
                 "budgets": [8], "workers": [1], "seeds": seeds(["cpsat", "scip", "highs"]),
                 "seeds_by_method": {m: [0] for m in METHODS if m != "S0"}},
                {"tier": "M15", "instances": f"{I}/M15", "steps": [1], "solvers": LICENCE_CAPPED, "methods": ["S0"],
                 "budgets": [8], "workers": [1], "seeds": [0]},
                {"tier": "M20", "instances": f"{I}/M20", "steps": [1], "solvers": LICENCE_CAPPED, "methods": ["S0"],
                 "budgets": [8], "workers": [1], "seeds": [0]},
            ]},
            {"name": "R2", "blocks": [
                {"tier": "S", "instances": f"{I}/S", "steps": STEPS, "solvers": ALL, "methods": ["S0", "S3", "S4"],
                 "budgets": [2], "workers": [1], "seeds": [0]}]},
            {"name": "R30", "blocks": [
                {"tier": "S", "instances": f"{I}/S", "steps": STEPS, "max_streams": 5,
                 "solvers": ["cpsat", "cpoptimizer", "gurobi", "cplex", "scip", "highs", "gecode", "chuffed"],
                 "methods": ["S0", "S3", "S4"], "budgets": [30], "workers": [1], "seeds": [0]},
                {"tier": "M15", "instances": f"{I}/M15", "steps": STEPS, "max_streams": 3,
                 "solvers": ["cpsat", "scip", "gecode", "chuffed"], "methods": ["S0", "S4"], "budgets": [30],
                 "workers": [1], "seeds": [0]}]},
            {"name": "W4", "blocks": [
                {"tier": "S", "instances": f"{I}/S", "steps": STEPS, "max_streams": 5,
                 "solvers": ["cpsat", "cpoptimizer", "gurobi", "cplex", "gecode", "cbc"],
                 "methods": ["S0", "S3", "S4"], "budgets": [8], "workers": [4], "seeds": [0]},
                {"tier": "M15", "instances": f"{I}/M15", "steps": STEPS, "max_streams": 3,
                 "solvers": ["cpsat", "gecode", "cbc"], "methods": ["S0", "S3", "S4"], "budgets": [8],
                 "workers": [4], "seeds": [0]}]},
        ],
    }
    fam = {}
    # Experiment A: engines, cold (S0), vs CP-SAT, per tier
    fam["A_S"] = [[key("AB", "S", s, "S0"), key("AB", "S", "cpsat", "S0")] for s in ALL if s != "cpsat"]
    for t in ("M15", "M20"):
        fam[f"A_{t}"] = [[key("AB", t, s, "S0"), key("AB", t, "cpsat", "S0")] for s in M_EXEC if s != "cpsat"]
    # Experiment B: within-solver ablations (portability), per solver and tier
    for t, solvers in (("S", ALL), ("M15", M_EXEC), ("M20", M_EXEC)):
        for s in solvers:
            pairs = [("S2", "S0"), ("S3", "S2"), ("S4", "S3"), ("S4", "S0")]
            if s not in ("gecode", "chuffed", "glpk"):
                pairs += [("S1", "S0"), ("S2", "S1")]
            if s == "cpsat":
                pairs += [("S4", "S5"), ("S5", "S3")]
            fam[f"B_{t}_{s}"] = [[key("AB", t, s, x), key("AB", t, s, y)] for x, y in pairs]
    # Experiment C: each solver's dev-selected configuration vs CP-SAT's
    for t in ("S", "M15"):
        if f"{t}|cpsat" not in best:
            continue
        ref = key("AB", t, "cpsat", best[f"{t}|cpsat"])
        fam[f"C_{t}"] = [[key("AB", t, s, best[f"{t}|{s}"]), ref] for s in ALL
                         if s != "cpsat" and f"{t}|{s}" in best and (t == "S" or s in M_EXEC)]
    # robustness (exploratory): restricted rounds and portfolio at other budgets / worker counts
    for exp, t, b, w, solvers in (("R2", "S", 2, 1, ALL),
                                  ("R30", "S", 30, 1, ["cpsat", "cpoptimizer", "gurobi", "cplex", "scip", "highs", "gecode", "chuffed"]),
                                  ("W4", "S", 8, 4, ["cpsat", "cpoptimizer", "gurobi", "cplex", "gecode", "cbc"])):
        fam[f"{exp}_{t}"] = [[key(exp, t, s, x, b, w), key(exp, t, s, y, b, w)]
                             for s in solvers for x, y in (("S4", "S3"), ("S3", "S0"))]
    fam["R30_M15"] = [[key("R30", "M15", s, "S4", 30), key("R30", "M15", s, "S0", 30)] for s in ["cpsat", "scip", "gecode", "chuffed"]]
    fam["W4_M15"] = [[key("W4", "M15", s, x, 8, 4), key("W4", "M15", s, y, 8, 4)]
                     for s in ["cpsat", "gecode", "cbc"] for x, y in (("S4", "S3"), ("S3", "S0"))]
    plan["families"] = fam
    plan["confirmatory_families"] = ["A_S", "A_M15", "A_M20"] + [f for f in fam if f.startswith("B_")] + \
                                    [f for f in fam if f.startswith("C_")]
    plan["exploratory_families"] = [f for f in fam if f.startswith(("R2", "R30", "W4"))]
    txt = json.dumps(plan, indent=1, sort_keys=True)
    out = ROOT / "results/multisolver/FROZEN_PLAN.json"
    out.write_text(txt)
    h = hashlib.sha256(txt.encode()).hexdigest()
    (ROOT / "results/multisolver/FROZEN_PLAN.sha256").write_text(h + "  FROZEN_PLAN.json\n")
    print("frozen", out, h)
    print("Experiment C choices (dev):", best)


if __name__ == "__main__":
    main()
