#!/usr/bin/env bash
# Single entry point: dependency check -> smoke tests -> Level 1 analysis
# reproduction -> manuscript rebuild. Does NOT run Level 2 (the full live
# solver campaign), which takes hours and has its own entry point
# (reproduce_all_experiments.sh / FULL=1 reproduce_all_experiments.sh),
# because this script is meant to finish in minutes on a fresh clone.
#
#   bash reproducibility/verify_everything.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STATUS=0
run() { echo; echo "##### $1"; shift; if ! "$@"; then STATUS=1; fi; }

run "check_dependencies.sh"     bash reproducibility/check_dependencies.sh
run "run_smoke_tests.sh"        bash reproducibility/run_smoke_tests.sh
run "reproduce_analysis.sh"     bash reproducibility/reproduce_analysis.sh
run "rebuild_manuscript.sh"     bash reproducibility/rebuild_manuscript.sh

echo
if [ "$STATUS" -eq 0 ]; then
  echo "VERDICT: ARCHIVED-DATA REPRODUCTION PASS (dependencies, smoke tests, Level 1"
  echo "         analysis reproduction, manuscript rebuild all succeeded)."
  echo "         Live solver reproduction (Level 2) was NOT run by this script;"
  echo "         run reproducibility/reproduce_all_experiments.sh separately."
else
  echo "VERDICT: FAIL -- one or more steps above failed. See their output."
fi
exit "$STATUS"
