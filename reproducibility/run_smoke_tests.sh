#!/usr/bin/env bash
# Fast correctness checks before any analysis or experimental reproduction (Task A2, A11).
# Actually executes code; does not just print instructions.
#
#   bash reproducibility/run_smoke_tests.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Fast unit/integration test suite, including multisolver equivalence (.venv_ms) =="
# .venv_ms is used for the WHOLE suite, not .venv: it reuses .venv's site-packages
# (zz_base_venv.pth) plus pyscipopt/highspy/swiglpk/minizinc/psutil, so it is a strict
# superset and the only environment that can collect tests/multisolver (every engine
# vs. the exhaustive oracle) in the same run as everything else.
.venv_ms/bin/python -m pytest -q --no-header -p no:cacheprovider

echo
echo "== Solver discovery: a real smoke optimization on every installed engine =="
.venv_ms/bin/python scripts/multisolver/discover_solvers.py

echo
echo "== Multisolver method-level smoke run (every engine x every supported method) =="
.venv_ms/bin/python scripts/multisolver/run_smoke.py

echo
echo "RESULT: smoke tests complete. See results/multisolver/solver_inventory.json and"
echo "        results/multisolver/smoke/smoke_results.json for per-engine outcomes."
