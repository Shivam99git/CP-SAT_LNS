#!/usr/bin/env bash
# Real PSPLIB RCPSP instances (.rcp/Patterson format), via ScheduleOpt/benchmarks
# (petrvilim.github.io/optalcp-website benchmark set). 40 instances (j30/j60/
# j90/j120, 10 each) x seeds x 2 methods -- the first real-instance validation
# for the RCPSP domain (previously synthetic streams only).
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PARALLEL="${PARALLEL:-8}"

echo ">>> Running RCPSP real-benchmark suite (--parallel $PARALLEL) -- see logs/rcpsp_real.log"
"$PY" -m phase0.rcpsp.run_rcpsp_test \
    --benchmark-dir tests/fixtures/rcpsp_real --seeds 1 2 3 \
    --total-budget 8 --stream-length 6 --parallel "$PARALLEL" \
    --out results/icaps/rcpsp/rcpsp_real_benchmarks.csv >> logs/rcpsp_real.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_rcpsp_test exited with status $status -- check logs/rcpsp_real.log" >&2
fi
echo ">>> rcpsp real-benchmark run finished (or was interrupted) -- results/icaps/rcpsp/rcpsp_real_benchmarks.csv"
