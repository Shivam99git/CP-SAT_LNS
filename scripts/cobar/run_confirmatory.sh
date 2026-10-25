#!/usr/bin/env bash
# COBAR confirmatory campaign (docs/cobar/08_confirmatory_protocol.md); FROZEN_CONFIG sha 7d3dec95...
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/cobar/confirmatory
(cd $R && sha256sum -c --quiet FROZEN_CONFIG.sha256)
CAND="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=critical+expand"
RND="cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=random+expand"
IAIP="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
PH="iaip|portfolio=full|global_mode=hinted"
P=(0 2 4 6 8 10 12 14)
S40=(901 902 903 904 905 906 907 908 909 910 911 912 913 914 915 916 917 918 919 920)
S20=(901 902 903 904 905 906 907 908 909 910)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --tag cobar_confirmatory "$@"; }
run --out $R/S1_primary --budget 8 --solver-seeds 0 1 2 3 4 --stream-seeds "${S40[@]}" --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH" "$RND"
run --out $R/S2_short   --budget 2 --solver-seeds 0 1 2 3 4 --stream-seeds "${S40[@]}" --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH"
run --out $R/S3_workers4 --budget 8 --workers 4 --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpu-groups 0,2,4,6 8,10,12,14 --methods "$CAND" "$IAIP" "$PH"
echo "core settings done"
run --out $R/S4_arrival --budget 8 --delta-mix arrival --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH"
run --out $R/S5_outage  --budget 8 --delta-mix outage  --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH"
run --out $R/S6_b30     --budget 30 --solver-seeds 0 1 2 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH"
B=tests/fixtures/benchmarks_real
run --out $R/S7_benchmarks --budget 8 --solver-seeds 0 1 2 3 4 --stream-seeds 901 --cpus "${P[@]}" --methods "$CAND" "$IAIP" "$PH" \
    --benchmarks $B/taillard/ta*.txt $B/dmu/dmu0*.txt $B/swv/swv0*.txt $B/yn/yn*.txt
echo "COBAR confirmatory all done"
