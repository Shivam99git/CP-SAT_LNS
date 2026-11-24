#!/usr/bin/env bash
# LEVEL 1 -- Analysis reproduction (Task A1, A2).
#
# Regenerates every numerical result, statistic, table and figure from the
# ARCHIVED raw experimental records already in results/. No optimization solver
# is invoked here (that is Level 2: reproduce_all_experiments.sh). This uses the
# project's existing, tested analysis scripts -- nothing here duplicates an
# algorithm that already has a verified implementation.
#
#   bash reproducibility/reproduce_analysis.sh
#
# Writes reproducibility/LEVEL1_REPRODUCTION_LOG.txt and leaves every regenerated
# JSON/figure in its documented location (same paths the archived ones already have).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="reproducibility/LEVEL1_REPRODUCTION_LOG.txt"
: > "$LOG"
STATUS=0
step() {
  echo "== $1" | tee -a "$LOG"
  shift
  if "$@" >>"$LOG" 2>&1; then
    echo "   OK" | tee -a "$LOG"
  else
    echo "   FAILED (see $LOG)" | tee -a "$LOG"
    STATUS=1
  fi
}

echo "LEVEL 1 analysis reproduction -- $(date -Is)" | tee -a "$LOG"

echo "--- 1. IAIP-SR (phase0/analyze_confirmatory.py) ---" | tee -a "$LOG"
step "IAIP-SR confirmatory analysis" .venv/bin/python -m phase0.analyze_confirmatory results/research_extension/confirmatory

echo "--- 2. COBAR certificate study (phase0/analyze_cobar_confirmatory.py) ---" | tee -a "$LOG"
step "COBAR confirmatory analysis" .venv/bin/python -m phase0.analyze_cobar_confirmatory results/cobar/confirmatory

echo "--- 3. Unified critical-region / matched-round study (phase0/analyze_unified_confirmatory.py) ---" | tee -a "$LOG"
step "Unified confirmatory analysis" .venv/bin/python -m phase0.analyze_unified_confirmatory results/unified_icaps/confirmatory

echo "--- 4. Final CP-SAT study: third, code-disjoint recomputation from raw events ---" | tee -a "$LOG"
step "CP-SAT confirmatory re-derivation" .venv_ms/bin/python scripts/multisolver/reproduce_cpsat_confirmatory.py
step "Mechanism (M1/M2) re-derivation" .venv_ms/bin/python scripts/multisolver/reproduce_mechanism.py

echo "--- 5. Multi-solver held-out campaign ---" | tee -a "$LOG"
step "Re-validate every stored schedule" .venv_ms/bin/python scripts/multisolver/validate_results.py
step "Recompute held-out statistics" .venv_ms/bin/python scripts/multisolver/analyze_results.py --phase heldout \
  --plan results/multisolver/FROZEN_PLAN.json --out results/multisolver/analysis/heldout.json
step "Contention sensitivity (CPU/wall >= 0.8)" .venv_ms/bin/python scripts/multisolver/analyze_results.py --phase heldout \
  --plan results/multisolver/FROZEN_PLAN.json --min-cpu-per-wall 0.8 --out results/multisolver/analysis/heldout_cpu08.json
step "Post-hoc stage attribution (descriptive)" .venv_ms/bin/python scripts/multisolver/attribute_stages.py --phase heldout \
  --out results/multisolver/analysis/stage_attribution.json
step "Post-hoc 20x20 comparisons (exploratory)" .venv_ms/bin/python scripts/multisolver/posthoc_comparisons.py

echo "--- 6. Figures and tables ---" | tee -a "$LOG"
step "CP-SAT confirmatory figures" .venv/bin/python paper/icaps27_multisolver_final/figures/make_figure4_forest.py
step "Mechanism figure" .venv/bin/python paper/icaps27_multisolver_final/figures/make_figure5_mechanism.py
step "Robustness heatmap" .venv/bin/python paper/icaps27_multisolver_final/figures/make_figure6_heatmap.py
step "Multisolver figures and tables" .venv_ms/bin/python scripts/multisolver/generate_figures.py --phase heldout \
  --exp AB --analysis results/multisolver/analysis/heldout.json --outdir paper/icaps27_multisolver_final/figures/ms

echo "--- 7. Comparison against archived reference values (Task A10) ---" | tee -a "$LOG"
step "Reproduction-vs-archive comparison report" .venv_ms/bin/python reproducibility/compare_results.py

echo | tee -a "$LOG"
if [ "$STATUS" -eq 0 ]; then
  echo "RESULT: Level 1 analysis reproduction completed; see $LOG and reproducibility/REPRODUCTION_COMPARISON.json" | tee -a "$LOG"
else
  echo "RESULT: one or more Level 1 steps FAILED; see $LOG" | tee -a "$LOG"
fi
exit "$STATUS"
