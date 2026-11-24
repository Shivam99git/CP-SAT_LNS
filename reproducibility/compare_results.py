"""Reproduction-vs-archive comparison (Task A10).

Compares every freshly regenerated analysis JSON (written by
reproduce_analysis.sh into its normal, already-tracked path) against the
version committed at HEAD -- i.e. the archived reference this project has
reported results from. All of these recomputations are DETERMINISTIC
(the same raw run records in results/, re-analysed by the same code), so a
real discrepancy here is a reproducibility bug, not solver randomness.

Classification per file (and, for JSON, per numeric leaf):
  EXACT MATCH                      byte-identical, or numeric diff == 0
  MATCH WITHIN NUMERICAL TOLERANCE numeric diff <= 1e-6 relative (float rounding)
  MISMATCH                         numeric diff above tolerance, or structural diff
  NOT EXECUTED                     the file does not exist in the working tree
                                    (its reproduction step did not run or did not write it)
  BLOCKED                          the committed reference itself is missing (new in this
                                    revision; nothing to compare against yet)

Stochastic live solver reruns (Level 2) are NOT compared here; see
reproducibility/compare_live_rerun.py for the STATISTICALLY CONSISTENT
STOCHASTIC RESULT category used there.

    .venv_ms/bin/python reproducibility/compare_results.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-6

# Deterministic analysis files this project reports numbers from.
FILES = [
    "results/research_extension/confirmatory/confirmatory_analysis.json",
    "results/cobar/confirmatory/confirmatory_analysis.json",
    "results/unified_icaps/confirmatory/confirmatory_analysis.json",
    "results/multisolver/audit/cpsat_reproduction.json",
    "results/multisolver/audit/mechanism_reproduction.json",
    "results/multisolver/validation_report.json",
    "results/multisolver/analysis/heldout.json",
    "results/multisolver/analysis/heldout_cpu08.json",
    "results/multisolver/analysis/stage_attribution.json",
    "results/multisolver/analysis/posthoc.json",
]


def archived(path: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def numeric_diff(a, b, path=""):
    """Yield (path, rel_diff) for every pair of numeric leaves that differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in a and k in b:
                yield from numeric_diff(a[k], b[k], f"{path}.{k}")
            else:
                # a key present on only one side (e.g. a reproduction step silently
                # produced fewer/more entries than the archive) is a real mismatch,
                # not something to skip
                yield (f"{path}.{k}", float("inf"))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from numeric_diff(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        denom = max(abs(a), abs(b), 1e-12)
        d = abs(a - b) / denom
        if d > 0:
            yield (path, d)
    elif a != b:
        yield (path, float("inf"))  # non-numeric structural mismatch


def classify(rel_path: str) -> dict:
    cur = ROOT / rel_path
    ref_bytes = archived(rel_path)
    if ref_bytes is None:
        return {"file": rel_path, "status": "BLOCKED", "reason": "no committed reference at HEAD"}
    if not cur.exists():
        return {"file": rel_path, "status": "NOT EXECUTED", "reason": "reproduction did not write this file"}
    cur_bytes = cur.read_bytes()
    if cur_bytes == ref_bytes:
        return {"file": rel_path, "status": "EXACT MATCH", "max_rel_diff": 0.0}
    try:
        ref, cur_j = json.loads(ref_bytes), json.loads(cur_bytes)
    except json.JSONDecodeError:
        return {"file": rel_path, "status": "MISMATCH", "reason": "not valid JSON for a structural diff"}
    diffs = list(numeric_diff(ref, cur_j))
    if not diffs:
        return {"file": rel_path, "status": "EXACT MATCH", "max_rel_diff": 0.0,
                "note": "differs only in key order / formatting"}
    worst = max(d for _, d in diffs)
    status = "MATCH WITHIN NUMERICAL TOLERANCE" if worst <= TOL else "MISMATCH"
    return {"file": rel_path, "status": status, "max_rel_diff": worst,
            "n_differing_leaves": len(diffs), "worst_path": max(diffs, key=lambda x: x[1])[0]}


def main():
    results = [classify(f) for f in FILES]
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = {"generated": "reproducibility/compare_results.py", "tolerance": TOL,
           "summary": counts, "files": results}
    (ROOT / "reproducibility/REPRODUCTION_COMPARISON.json").write_text(json.dumps(out, indent=1))
    for r in results:
        print(f"{r['status']:32s} {r['file']}" + (f"  (max_rel_diff={r['max_rel_diff']:.2e})" if "max_rel_diff" in r else ""))
    print("\nsummary:", counts)
    sys.exit(1 if counts.get("MISMATCH") else 0)


if __name__ == "__main__":
    main()
