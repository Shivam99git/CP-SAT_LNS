#!/usr/bin/env bash
# ICAPS budgets preset. Does NOT stop on individual instance failures --
# the runner isolates per-row errors into the CSV and continues; run
# --dry-run first to see the planned grid size before committing compute.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo ">>> Running ICAPS budgets preset -- see logs/budgets.log"
"$PY" -m phase0.run_icaps_jssp_suite --preset budgets --out-dir results/icaps/runs \
    --resume --skip-existing >> logs/budgets.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_icaps_jssp_suite exited with status $status -- check logs/budgets.log" >&2
fi
echo ">>> budgets run finished (or was interrupted) -- results/icaps/runs/budgets.csv"
