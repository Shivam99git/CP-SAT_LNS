"""Builds results/final_icaps/verified_metrics.json: one machine-readable
record per reported comparison across the unified study's confirmatory
settings (U1-U9), with the fields required by the final-phase task
(experiment id, method, comparator, instance population, n streams, n solver
seeds, n runs, budget, workers, metric, statistic, CI, adjusted p, raw
result location, verification status). Cross-references the independent
reproduction in results/final_icaps/unified_confirmatory_independent_verification.json
(scripts/final/verify_unified_confirmatory.py) to set verification_status.

    .venv/bin/python scripts/final/build_verified_metrics.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "results/unified_icaps/confirmatory"

arch = json.loads((CONF / "confirmatory_analysis.json").read_text())
indep = json.loads((ROOT / "results/final_icaps/unified_confirmatory_independent_verification.json").read_text())
cfg = json.loads((CONF / "FROZEN_CONFIG.json").read_text())
roles = cfg["roles"]

BUDGETS = {"U1_primary": 8, "U2_mechanism": 8, "U3_workers4": 8, "U4_b2": 2, "U5_b30": 30,
           "U6_arrival": 8, "U7_outage": 8, "U8_high": 8, "U9_benchmarks": 8}
WORKERS = {"U3_workers4": 4}

records = []
for setting, s in arch["settings"].items():
    indep_s = indep["settings"].get(setting, {})
    n_units = s["n_units"]
    n_seeds = len(s["solver_seeds"])
    n_runs = s["integrity"]["records"]
    budget = BUDGETS.get(setting, 8)
    workers = WORKERS.get(setting, 1)
    unit = s["unit"]
    for comp_key, comp in s["comparisons"].items():
        a_role, b_role = comp_key.split(" vs ")
        c = comp["pi"]
        indep_c = indep_s.get("agreement_with_archived", {}).get("comparisons", {}).get(comp_key)
        verified = bool(indep_c and indep_c.get("WL_equal") and indep_c.get("holm_equal")
                        and indep_c.get("rel_diff_abs_err", 1) < 1e-9)
        records.append({
            "experiment_id": f"{setting}::{comp_key}",
            "setting": setting,
            "method": a_role, "method_config": roles.get(a_role, a_role),
            "comparator": b_role, "comparator_config": roles.get(b_role, b_role),
            "instance_population": ("34 published job-shop benchmark bases (Taillard/DMU/SWV/YN)"
                                    if setting == "U9_benchmarks" else
                                    "synthetic full job-shop streams, m in {15,20}"),
            "unit_of_analysis": unit,
            "n_units": n_units,
            "n_solver_seeds": n_seeds,
            "n_runs": n_runs,
            "budget_s": budget,
            "workers": workers,
            "metric": "primal_integral (mean of stream means, steps 1-10, solver seeds averaged within unit)",
            "numerator": "mean(PI_method) - mean(PI_comparator)",
            "denominator": "mean(PI_comparator)",
            "statistic": "relative_difference_pct",
            "value_pct": round(100 * c["rel_diff"], 2),
            "stream_wins": c["stream_wins"], "stream_losses": c["stream_losses"],
            "ci95": c["ci95"],
            "adjusted_p_holm": c.get("sign_p_holm"),
            "significant_at_0.05": bool(c.get("sign_p_holm", 1) < 0.05),
            "raw_result_location": f"results/unified_icaps/confirmatory/{setting}/runs/*.jsonl",
            "archived_analysis_location": f"results/unified_icaps/confirmatory/confirmatory_analysis.json#settings.{setting}.comparisons.{comp_key}",
            "independent_verification_location": f"results/final_icaps/unified_confirmatory_independent_verification.json#settings.{setting}.comparisons.{comp_key}",
            "verification_status": "INDEPENDENTLY_VERIFIED" if verified else "NOT_INDEPENDENTLY_CROSS_CHECKED",
        })

out = {
    "frozen_config_sha256": cfg.get("git_revision"),
    "frozen_config_file_sha256": (CONF / "FROZEN_CONFIG.sha256").read_text().split()[0],
    "n_records": len(records),
    "n_verified": sum(r["verification_status"] == "INDEPENDENTLY_VERIFIED" for r in records),
    "records": records,
}
dest = ROOT / "results/final_icaps/verified_metrics.json"
dest.write_text(json.dumps(out, indent=1, default=float))
print(f"{out['n_records']} metric records written, {out['n_verified']} independently verified")
print("wrote", dest)
