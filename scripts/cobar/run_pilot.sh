#!/usr/bin/env bash
# COBAR pilot (docs/cobar/07_pilot_protocol.md). Development streams 301-310 only.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/cobar/pilot
A0="iaip|portfolio=full|global_mode=hinted"
A1="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
A2="cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=fixed"
A3="cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=0|global_certificate=0|policy=fixed"
A4="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=budget"
A5="cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=cert+budget"
A6="cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=cert+budget"
A8="cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=fixed"
A9="cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave"
A6r="$A6|rounds=10"
A10="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=iaip"
A12="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=critical"
P=(0 2 4 6 8 10 12 14)
S10=(301 302 303 304 305 306 307 308 309 310)
S5=(301 302 303 304 305)
SMALL=("$A0" "$A1" "$A4" "$A6" "$A6r" "$A9")
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --solver-seeds 0 --tag cobar_pilot "$@"; }

run --out $R/p1_b8 --budget 8 --stream-seeds "${S10[@]}" --cpus "${P[@]}" \
    --methods "$A0" "$A1" "$A2" "$A3" "$A4" "$A5" "$A6" "$A8" "$A9" "$A6r" "$A10" "$A12"
run --out $R/p2_b2  --budget 2  --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "${SMALL[@]}"
run --out $R/p3_b30 --budget 30 --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "${SMALL[@]}"
run --out $R/p4_w4  --budget 8 --workers 4 --stream-seeds "${S5[@]}" --cpu-groups 0,2,4,6 8,10,12,14 --methods "${SMALL[@]}"
run --out $R/p5_arrival --budget 8 --delta-mix arrival --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "${SMALL[@]}"
run --out $R/p6_outage  --budget 8 --delta-mix outage  --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "${SMALL[@]}"
run --out $R/p7_high    --budget 8 --severity high     --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "${SMALL[@]}"
echo "COBAR pilot all done"
