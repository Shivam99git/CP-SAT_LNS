#!/usr/bin/env bash
# Fast correctness checks before any analysis or experimental reproduction (Task A2, A11).
# Actually executes code; does not just print instructions.
#
#   bash reproducibility/run_smoke_tests.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Fast unit/integration test suite (.venv) =="
.venv/bin/python -m pytest -q --no-header -p no:cacheprovider

echo
echo "== Multisolver equivalence suite: every engine vs. the exhaustive oracle (.venv_ms) =="
.venv_ms/bin/python -m pytest -q --no-header -p no:cacheprovider tests/multisolver tests/unified/test_critical_region_anytime.py

echo
echo "== Solver discovery: a real smoke optimization on every installed engine =="
.venv_ms/bin/python scripts/multisolver/discover_solvers.py

echo
echo "== Multisolver method-level smoke run (every engine x every supported method) =="
.venv_ms/bin/python scripts/multisolver/run_smoke.py

echo
echo "RESULT: smoke tests complete. See results/multisolver/solver_inventory.json and"
echo "        results/multisolver/smoke/smoke_results.json for per-engine outcomes."
