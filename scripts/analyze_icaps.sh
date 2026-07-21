#!/usr/bin/env bash
# Run the analysis + report generation over whichever result CSVs exist in
# results/icaps/runs/. Safe to run repeatedly (overwrites tables/figures/
# report.md, never touches the raw run CSVs).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

shopt -s nullglob
csvs=(results/icaps/runs/*.csv)
if [ ${#csvs[@]} -eq 0 ]; then
    echo "no CSVs found in results/icaps/runs/ -- run a preset first (e.g. scripts/run_icaps_smoke.sh)" >&2
    exit 1
fi

log_and_run "analyze.log" "Analyzing ${#csvs[@]} result file(s)" -- \
    "$PY" -m phase0.analyze_icaps_results --csv "${csvs[@]}" --out-dir results/icaps --baseline cpsat_cold

echo ">>> analysis complete: results/icaps/report.md"
