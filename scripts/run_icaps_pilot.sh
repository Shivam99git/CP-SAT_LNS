#!/usr/bin/env bash
# Quick but meaningful comparison (~10-30 min depending on hardware).
# Stops on any error (pilot is meant to be debugged interactively).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

log_and_run "pilot.log" "Running ICAPS pilot preset" -- \
    "$PY" -m phase0.run_icaps_jssp_suite --preset pilot --out-dir results/icaps/runs --resume --skip-existing

echo ">>> pilot complete: results/icaps/runs/pilot.csv"
