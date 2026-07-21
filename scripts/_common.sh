#!/usr/bin/env bash
# Shared setup for all scripts/run_icaps_*.sh. Not run directly.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python"
fi

mkdir -p logs results/icaps/runs results/icaps/tables results/icaps/figures

log_and_run() {
    # log_and_run <logfile> <description> -- <command...>
    local logfile="$1"; shift
    local desc="$1"; shift
    if [ "$1" = "--" ]; then shift; fi
    echo ">>> $desc"
    echo ">>> $*" | tee -a "logs/$logfile"
    "$@" 2>&1 | tee -a "logs/$logfile"
    return "${PIPESTATUS[0]}"
}
