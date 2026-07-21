#!/usr/bin/env bash
# Generate every figure for the ICAPS paper (paper/boot_cold_icaps.tex).
#
# Two steps: (1) capture solver trajectories on a small held-out grid (the
# anytime curves need per-moment gap data the result CSVs don't store), then
# (2) render all figures (anytime curves + CSV-derived aggregate figures).
#
# Trajectory capture takes a few minutes; set PARALLEL to your core count.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PARALLEL="${PARALLEL:-12}"
TRAJ="results/icaps/figures/trajectories.pkl"

if [ ! -f "$TRAJ" ] || [ "${RECAPTURE:-0}" = "1" ]; then
    echo ">>> capturing trajectories (--parallel $PARALLEL) -- see logs/capture_traj.log"
    "$PY" -m phase0.make_paper_figures capture --out "$TRAJ" \
        --sizes 15x15 20x20 --seeds 201 202 203 204 205 206 \
        --budget 8 --stream-length 6 --parallel "$PARALLEL" >> logs/capture_traj.log 2>&1
else
    echo ">>> using existing $TRAJ (set RECAPTURE=1 to regenerate)"
fi

echo ">>> rendering figures"
"$PY" -m phase0.make_paper_figures plot --traj "$TRAJ" \
    --runs-dir results/icaps/runs \
    --rcpsp-csv results/icaps/rcpsp/rcpsp_seeds1_10_combined.csv \
    --out-dir results/icaps/figures

echo ">>> figures in results/icaps/figures/ (referenced by paper/boot_cold_icaps.tex)"
