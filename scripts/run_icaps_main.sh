#!/usr/bin/env bash
# ICAPS main result grid. LARGE: 4 sizes x 30 seeds x 4 budgets x 2 worker
# counts x 10 methods x 20-instance streams = 28,800 stream-runs. This is an
# unattended multi-day run on typical hardware -- run in the background
# (e.g. nohup, tmux, screen) and monitor logs/main.log.
#
# Does NOT stop on individual failures (large-experiment policy): the
# runner itself isolates per-row errors into the CSV's status/error_message
# columns and continues; this script only guards against a crash in the
# python process itself, which it still reports via a non-zero exit.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo ">>> Running ICAPS main preset (LARGE, may take days) -- see logs/main.log"
"$PY" -m phase0.run_icaps_jssp_suite --preset main --out-dir results/icaps/runs \
    --resume --skip-existing >> logs/main.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_icaps_jssp_suite exited with status $status -- check logs/main.log" >&2
    echo ">>> Re-run this script with --resume already set to continue from where it stopped."
fi
echo ">>> main run finished (or was interrupted) -- results/icaps/runs/main.csv"
