#!/usr/bin/env bash
# Taillard (1993) real job-shop benchmark instances, via ScheduleOpt/benchmarks
# (petrvilim.github.io/optalcp-website benchmark set). 80 configs x 4 methods
# = 320 stream-runs on ta01-ta20 (15x15/20x15) -- meaningfully larger than the
# OR-Library real_benchmarks set (max 20x10).
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PARALLEL="${PARALLEL:-8}"

echo ">>> Running Taillard real-benchmark suite (--parallel $PARALLEL) -- see logs/taillard.log"
"$PY" -m phase0.run_icaps_jssp_suite --preset taillard_benchmarks \
    --benchmark-dir tests/fixtures/benchmarks_real/taillard \
    --out-dir results/icaps/runs --parallel "$PARALLEL" \
    --resume --skip-existing >> logs/taillard.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_icaps_jssp_suite exited with status $status -- check logs/taillard.log" >&2
fi
echo ">>> taillard run finished (or was interrupted) -- results/icaps/runs/taillard_benchmarks.csv"
