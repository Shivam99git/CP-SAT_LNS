#!/usr/bin/env bash
# ICAPS full-paper main comparison table (docs/icaps_full_paper_plan.md
# Phase C.1). 45 stream configs x 10 methods = 450 stream-runs, 11-instance
# streams. Runs across worker processes via --parallel (stream-config
# granularity); tune PARALLEL below to the machine's core count.
#
# Does NOT stop on individual failures -- the runner isolates per-row errors
# into the CSV's status/error_message columns and continues.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PARALLEL="${PARALLEL:-16}"

echo ">>> Running ICAPS paper_main preset (--parallel $PARALLEL) -- see logs/paper_main.log"
"$PY" -m phase0.run_icaps_jssp_suite --preset paper_main --out-dir results/icaps/runs \
    --parallel "$PARALLEL" --resume --skip-existing >> logs/paper_main.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_icaps_jssp_suite exited with status $status -- check logs/paper_main.log" >&2
fi
echo ">>> paper_main run finished (or was interrupted) -- results/icaps/runs/paper_main.csv"
