#!/usr/bin/env bash
# Fast correctness check (~seconds). Stops on any error.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log_and_run "smoke.log" "Running pytest" -- "$PY" -m pytest tests/ -q
log_and_run "smoke.log" "Running ICAPS smoke preset" -- \
    "$PY" -m phase0.run_icaps_jssp_suite --preset smoke --out-dir results/icaps/runs

echo ">>> smoke complete: results/icaps/runs/smoke.csv"
