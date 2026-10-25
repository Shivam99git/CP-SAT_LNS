#!/usr/bin/env bash
# COBAR pilot round 3 (docs/cobar/07_pilot_protocol.md). Development streams only; solver seed 2.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/cobar/pilot
A0="iaip|portfolio=full|global_mode=hinted"
A1="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
B="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10"
C2="$B|round_neighbourhood=critical+expand"; C3="$B|round_neighbourhood=random+expand"
P=(0 2 4 6 8 10 12 14); S5=(301 302 303 304 305)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --solver-seeds 2 --tag cobar_pilot3 "$@"; }
run --out $R/p10a_b8_seed2 --budget 8 --stream-seeds 301 302 303 304 305 306 307 308 309 310 --cpus "${P[@]}" --methods "$A0" "$A1" "$C2" "$C3"
run --out $R/p10b_b2  --budget 2  --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "$A0" "$A1" "$C2"
run --out $R/p10c_w4  --budget 8 --workers 4 --stream-seeds "${S5[@]}" --cpu-groups 0,2,4,6 8,10,12,14 --methods "$A0" "$A1" "$C2"
run --out $R/p10d_b30 --budget 30 --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "$A0" "$A1" "$C2"
run --out $R/p10e_outage --budget 8 --delta-mix outage --stream-seeds "${S5[@]}" --cpus "${P[@]}" --methods "$A0" "$A1" "$C2"
echo "COBAR pilot3 all done"
