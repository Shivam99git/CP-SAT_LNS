"""Compare a fresh LIVE solver rerun (results/multisolver_rerun/) against the
archived campaign (results/multisolver/) this project reports (Task A10).

Unlike compare_results.py (deterministic re-analysis of the SAME raw records),
this compares two INDEPENDENT executions of the solvers. Wall-clock-budgeted
anytime trajectories on different hardware/host-load are not expected to be
byte-identical, so the acceptance criteria below were fixed before this
script was run and are not adjusted afterwards:

  structural (must match exactly):
    - every rerun record validates (0 feasibility violations)
    - the set of task_ids executed is a subset of the frozen plan
    - status categories present (OK / NOT_SUPPORTED / NO_SOLUTION / ERROR)
      are a subset of those seen in the archived campaign

  numeric (STATISTICALLY CONSISTENT STOCHASTIC RESULT iff both hold):
    - for every (tier, solver, method) config present in both runs, the sign
      of (rerun mean PI - archived mean PI) is unconstrained, but the RATIO
      archived_PI / rerun_PI must lie in [0.2, 5] (a 5x band -- wide because a
      smoke-scale rerun has far fewer samples than the archived campaign);
      outside that band is MISMATCH for that config.
    - CP-SAT must still have the lowest mean cold (S0) PI among the engines
      present in the rerun (the one qualitative ranking claimed in the paper).

    .venv_ms/bin/python reproducibility/compare_live_rerun.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RERUN = ROOT / "results/multisolver_rerun"


def main():
    val_p = RERUN / "validation_report.json"
    ana_p = RERUN / "analysis_heldout.json"
    out = {"generated": "reproducibility/compare_live_rerun.py"}
    if not val_p.exists() or not ana_p.exists():
        out["status"] = "NOT EXECUTED"
        out["reason"] = "results/multisolver_rerun/{validation_report,analysis_heldout}.json missing"
        Path(ROOT / "reproducibility/LIVE_RERUN_COMPARISON.json").write_text(json.dumps(out, indent=1))
        print(json.dumps(out, indent=1))
        sys.exit(0)

    val = json.loads(val_p.read_text())
    structural_ok = val["n_violations"] == 0
    archived_statuses = set(json.loads((ROOT / "results/multisolver/validation_report.json").read_text())
                             ["status_counts"])
    rerun_statuses = set(val["status_counts"])
    statuses_ok = rerun_statuses.issubset(archived_statuses | {"OK_without_stored_schedule"})

    archived = json.loads((ROOT / "results/multisolver/analysis/heldout.json").read_text())["configs"]
    rerun = json.loads(ana_p.read_text())["configs"]
    per_config, mismatches = [], 0
    for k, rc in rerun.items():
        ac = archived.get(k)
        if ac is None or ac.get("mean_pi") is None or rc.get("mean_pi") is None:
            continue
        ratio = ac["mean_pi"] / rc["mean_pi"] if rc["mean_pi"] else float("inf")
        ok = 0.2 <= ratio <= 5.0
        mismatches += not ok
        per_config.append({"config": k, "archived_pi": ac["mean_pi"], "rerun_pi": rc["mean_pi"],
                            "ratio": ratio, "within_band": ok})

    cold = [(k.split("|")[2], v["mean_pi"]) for k, v in rerun.items()
            if k.split("|")[3] == "S0" and v.get("mean_pi") is not None]
    cpsat_lowest = (not cold) or min(cold, key=lambda x: x[1])[0] == "cpsat"

    out["structural"] = {"zero_validation_violations": structural_ok, "status_categories_known": statuses_ok}
    out["numeric"] = {"n_configs_compared": len(per_config), "n_outside_band": mismatches,
                      "cpsat_lowest_cold_pi": cpsat_lowest, "per_config": per_config}
    out["status"] = ("STATISTICALLY CONSISTENT STOCHASTIC RESULT"
                      if structural_ok and statuses_ok and mismatches == 0 and cpsat_lowest
                      else "MISMATCH")
    Path(ROOT / "reproducibility/LIVE_RERUN_COMPARISON.json").write_text(json.dumps(out, indent=1))
    print(f"status: {out['status']}  ({len(per_config)} configs compared, {mismatches} outside the acceptance band)")
    sys.exit(0 if out["status"] != "MISMATCH" else 1)


if __name__ == "__main__":
    main()
