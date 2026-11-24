#!/usr/bin/env bash
# LEVEL 2 -- Full experimental reproduction (Task A1, A2, A5, A11).
#
# Actually re-executes the optimization solvers (not just the analysis of
# archived records). Writes into results/multisolver_rerun/ -- a SEPARATE
# directory from results/multisolver/ -- so the already-verified archived
# campaign this project's manuscript reports is never overwritten; the two
# are compared afterwards (reproducibility/compare_live_rerun.py).
#
# Two modes:
#   bash reproducibility/reproduce_all_experiments.sh            # SMOKE scale (minutes):
#       one stream per tier, methods S0/S3/S4 only, budget 2s. Confirms the
#       pipeline runs end-to-end on a fresh machine with no hidden dependency
#       on prior state.
#   FULL=1 bash reproducibility/reproduce_all_experiments.sh     # the ENTIRE
#       frozen campaign (19,440 tasks; several hours; requires the same
#       licensed engines as the archived run -- see check_dependencies.sh).
#
# Before running: estimate resource needs with --dry-run on run_benchmark.py
# (this script prints that estimate first either way).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PLAN="results/multisolver/FROZEN_PLAN.json"
export MULTISOLVER_OUT="$ROOT/results/multisolver_rerun"
mkdir -p "$MULTISOLVER_OUT/runs"

# The frozen plan defines the held-out campaign; it must not have changed.
WANT=$(cut -d' ' -f1 results/multisolver/FROZEN_PLAN.sha256)
GOT=$(sha256sum "$PLAN" | cut -d' ' -f1)
if [ "$WANT" != "$GOT" ]; then
  echo "FROZEN_PLAN.json hash $GOT != committed $WANT; refusing to run (held-out configurations may not change after being examined)."
  exit 1
fi

if [ "${FULL:-0}" = "1" ]; then
  echo "== LEVEL 2 FULL reproduction: the entire frozen campaign (hours) =="
  echo "Resource estimate (dry run):"
  .venv_ms/bin/python scripts/multisolver/run_benchmark.py --plan "$PLAN" --dry-run
  for EXP in AB R2 W4 R30; do
    echo "=== $EXP $(date)"
    .venv_ms/bin/python scripts/multisolver/run_benchmark.py --plan "$PLAN" --experiments "$EXP"
  done
else
  echo "== LEVEL 2 SMOKE-scale reproduction (minutes). Set FULL=1 for the entire campaign. =="
  SMOKE_PLAN="$MULTISOLVER_OUT/SMOKE_PLAN.json"
  .venv_ms/bin/python - "$PLAN" "$SMOKE_PLAN" <<'EOF'
import json, sys
plan = json.load(open(sys.argv[1]))
for exp in plan["experiments"]:
    if exp["name"] != "AB":
        exp["blocks"] = []
        continue
    for b in exp["blocks"]:
        b["steps"] = b["steps"][:1]
        b["methods"] = [m for m in b["methods"] if m in ("S0", "S3", "S4")]
        # keep budget 8 (same as the archived AB family) so configs are comparable below
        b["seeds"] = {"default": [0]}
        b.pop("seeds_by_method", None)
json.dump(plan, open(sys.argv[2], "w"), indent=1)
EOF
  .venv_ms/bin/python scripts/multisolver/run_benchmark.py --plan "$SMOKE_PLAN" --experiments AB
fi

echo "== Validating the freshly executed schedules =="
.venv_ms/bin/python scripts/multisolver/validate_results.py --runs "$MULTISOLVER_OUT/runs" \
  --out "$MULTISOLVER_OUT/validation_report.json"

echo "== Analysing the fresh rerun =="
.venv_ms/bin/python scripts/multisolver/analyze_results.py --runs "$MULTISOLVER_OUT/runs" --phase heldout \
  --plan "$PLAN" --out "$MULTISOLVER_OUT/analysis_heldout.json"

echo "== Comparing the fresh rerun to the archived campaign (Task A10) =="
.venv_ms/bin/python reproducibility/compare_live_rerun.py

echo "RESULT: Level 2 reproduction finished. See reproducibility/LIVE_RERUN_COMPARISON.json"
