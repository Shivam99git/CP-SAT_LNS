#!/usr/bin/env bash
# COBAR pilot round 2 (docs/cobar/07_pilot_protocol.md). Development streams only; solver seed 1.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/cobar/pilot
A0="iaip|portfolio=full|global_mode=hinted"
A1="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
A6r="cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=cert+budget|rounds=10"
B="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10"
C1="$B|round_neighbourhood=release+expand"; C2="$B|round_neighbourhood=critical+expand"; C3="$B|round_neighbourhood=random+expand"
P=(0 2 4 6 8 10 12 14)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --solver-seeds 1 --tag cobar_pilot2 "$@"; }
run --out $R/p8_b8_seed1 --budget 8 --stream-seeds 301 302 303 304 305 306 307 308 309 310 --cpus "${P[@]}" \
    --methods "$A0" "$A1" "$A6r" "$C1" "$C2" "$C3"
run --out $R/p9a_b2  --budget 2  --stream-seeds 301 302 303 304 305 --cpus "${P[@]}" --methods "$A0" "$A1" "$C1"
run --out $R/p9b_w4  --budget 8 --workers 4 --stream-seeds 301 302 303 304 305 --cpu-groups 0,2,4,6 8,10,12,14 --methods "$A0" "$A1" "$C1"
run --out $R/p9c_b30 --budget 30 --stream-seeds 301 302 303 304 305 --cpus "${P[@]}" --methods "$A0" "$A1" "$C1"
echo "COBAR pilot2 all done"
