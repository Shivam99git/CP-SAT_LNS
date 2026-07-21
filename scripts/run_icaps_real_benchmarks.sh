#!/usr/bin/env bash
# Real OR-Library benchmark instances (docs/icaps_full_paper_plan.md Phase B)
# run through the full ICAPS suite: each of the 10 real instances in
# tests/fixtures/benchmarks_real/ becomes the base of a dynamic stream via
# generate_stream(base_instance=...), with the same delta/severity machinery
# as the synthetic-stream presets. Matches paper_main's budget (8s) for
# direct comparability.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PARALLEL="${PARALLEL:-8}"

echo ">>> Running ICAPS real-benchmarks suite (--parallel $PARALLEL) -- see logs/real_benchmarks.log"
"$PY" -m phase0.run_icaps_jssp_suite --preset real_benchmarks \
    --benchmark-dir tests/fixtures/benchmarks_real \
    --out-dir results/icaps/runs --parallel "$PARALLEL" \
    --resume --skip-existing >> logs/real_benchmarks.log 2>&1
status=$?
if [ $status -ne 0 ]; then
    echo ">>> WARNING: run_icaps_jssp_suite exited with status $status -- check logs/real_benchmarks.log" >&2
fi
echo ">>> real_benchmarks run finished (or was interrupted) -- results/icaps/runs/real_benchmarks.csv"
