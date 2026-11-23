"""One-command multisolver pipeline (Task 7): discover -> smoke -> held-out
benchmark (frozen plan) -> validate -> analyze (+ contention sensitivity,
stage attribution) -> figures/tables.

Only engines whose discovery smoke solve succeeded are ever run (the frozen
plan names them; run_task records a solver that fails at run time as ERROR /
LICENSE_LIMIT, never silently substitutes one). The frozen plan is NOT
regenerated here: it is verified against its committed SHA-256 so a re-run
cannot change held-out configurations. Completed tasks are skipped
(run_benchmark resumes from the run files), so the script is restartable.

    .venv_ms/bin/python scripts/multisolver/run_all_available.py              # everything
    .venv_ms/bin/python scripts/multisolver/run_all_available.py --skip-discover --skip-smoke
    .venv_ms/bin/python scripts/multisolver/run_all_available.py --only analyze,figures
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
S = ROOT / "scripts/multisolver"
PLAN = ROOT / "results/multisolver/FROZEN_PLAN.json"
ANA = ROOT / "results/multisolver/analysis"
FIG = ROOT / "paper/icaps27_multisolver_final/figures/ms"
STEPS = ["discover", "smoke", "benchmark", "validate", "analyze", "figures"]


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), cwd=ROOT, check=True)


def verify_plan():
    want = (ROOT / "results/multisolver/FROZEN_PLAN.sha256").read_text().split()[0]
    got = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    if got != want:
        sys.exit(f"FROZEN_PLAN.json hash {got} != committed {want}; refusing to run")
    print("frozen plan verified", got)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated subset of " + ",".join(STEPS))
    ap.add_argument("--skip-discover", action="store_true")
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--experiments", default="AB,R2,W4,R30")
    a = ap.parse_args()
    steps = a.only.split(",") if a.only else [s for s in STEPS if not (
        (s == "discover" and a.skip_discover) or (s == "smoke" and a.skip_smoke))]
    verify_plan()
    if "discover" in steps:
        run([PY, S / "discover_solvers.py"])
        inv = json.loads((ROOT / "results/multisolver/solver_inventory.json").read_text())
        print("inventory:", json.dumps({k: v.get("status") for k, v in inv.get("solvers", inv).items()
                                        if isinstance(v, dict)}))
    if "smoke" in steps:
        run([PY, S / "run_smoke.py"])
    if "benchmark" in steps:
        for e in a.experiments.split(","):
            run([PY, S / "run_benchmark.py", "--plan", PLAN, "--experiments", e])
    if "validate" in steps:
        run([PY, S / "validate_results.py", "--runs", ROOT / "results/multisolver/runs",
             "--out", ROOT / "results/multisolver/validation_report.json"])
    if "analyze" in steps:
        run([PY, S / "analyze_results.py", "--phase", "heldout", "--plan", PLAN, "--out", ANA / "heldout.json"])
        run([PY, S / "analyze_results.py", "--phase", "heldout", "--plan", PLAN, "--min-cpu-per-wall", "0.8",
             "--out", ANA / "heldout_cpu08.json"])
        run([PY, S / "attribute_stages.py", "--phase", "heldout", "--out", ANA / "stage_attribution.json"])
        run([PY, S / "posthoc_comparisons.py"])  # labelled post-hoc exploratory, not frozen
    if "figures" in steps:
        run([PY, S / "generate_figures.py", "--phase", "heldout", "--exp", "AB",
             "--analysis", ANA / "heldout.json", "--outdir", FIG])
    print("done:", ",".join(steps))


if __name__ == "__main__":
    main()
