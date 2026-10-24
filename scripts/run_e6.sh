#!/usr/bin/env bash
# E6 robustness campaigns (exploratory), as specified in
# docs/research_extension/04_experimental_methodology.md section 6.
# Frozen IAIP-SR configuration; resumable (finished task files are skipped).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
R=results/research_extension
M=("iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
   "iaip|portfolio=fresh" "iaip|portfolio=full|global_mode=hinted" floor cold)
P=(0 2 4 6 8 10 12 14)
S=(601 602 603 604 605 606 607 608 609 610)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --solver-seeds 0 --methods "${M[@]}" "$@"; }

run --out $R/e6a_b2  --tag e6a --budget 2  --stream-seeds "${S[@]}" --cpus "${P[@]}"
run --out $R/e6a_b30 --tag e6a --budget 30 --stream-seeds "${S[@]}" --cpus "${P[@]}"
run --out $R/e6b_w4  --tag e6b --budget 8 --workers 4 --stream-seeds "${S[@]}" --cpu-groups 0,2,4,6 8,10,12,14
run --out $R/e6c_arrival --tag e6c --budget 8 --delta-mix arrival --stream-seeds "${S[@]}" --cpus "${P[@]}"
run --out $R/e6c_outage  --tag e6c --budget 8 --delta-mix outage  --stream-seeds "${S[@]}" --cpus "${P[@]}"
run --out $R/e6c_high    --tag e6c --budget 8 --severity high     --stream-seeds "${S[@]}" --cpus "${P[@]}"
B=tests/fixtures/benchmarks_real
run --out $R/e6d_benchmarks --tag e6d --budget 8 --stream-seeds 601 602 --cpus "${P[@]}" \
    --benchmarks $B/taillard/ta*.txt $B/dmu/dmu0*.txt $B/swv/swv0*.txt $B/yn/yn*.txt
echo "E6 all done"
