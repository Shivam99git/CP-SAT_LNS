#!/usr/bin/env bash
# Unified confirmatory campaign (docs/unified_icaps/06_statistical_results.md); FROZEN_CONFIG sha a594a25f...
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/unified_icaps/confirmatory
(cd $R && sha256sum -c --quiet FROZEN_CONFIG.sha256)
B2="crgar|strategy=crit_expand"
B0="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
B6="iaip|portfolio=full|global_mode=hinted"
B1="crgar|strategy=random_matched"
B3="crgar|strategy=time_window"
B4="crgar|strategy=precedence"
B5="cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave"
M2="|stop_on_fail=0|round_time=0.4|max_rounds=6"
P=(0 2 4 6 8 10 12 14)
S40=(1101 1102 1103 1104 1105 1106 1107 1108 1109 1110 1111 1112 1113 1114 1115 1116 1117 1118 1119 1120)
S20=(1101 1102 1103 1104 1105 1106 1107 1108 1109 1110)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --tag unified_confirmatory "$@"; }

run --out $R/U1_primary --budget 8 --solver-seeds 0 1 2 3 4 --stream-seeds "${S40[@]}" --cpus "${P[@]}" \
    --methods "$B2" "$B0" "$B6" "$B1" "$B3" "$B4" "$B5"
run --out $R/U2_mechanism --budget 8 --solver-seeds 0 1 2 3 4 --stream-seeds "${S40[@]}" --cpus "${P[@]}" \
    --methods "$B2$M2" "$B1$M2" "$B3$M2" "$B4$M2"
run --out $R/U3_workers4 --budget 8 --workers 4 --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" \
    --cpu-groups 0,2,4,6 8,10,12,14 --methods "$B2" "$B0" "$B6" "$B3"
echo "core settings U1-U3 done"
run --out $R/U4_b2  --budget 2  --solver-seeds 0 1 2 3 4 --stream-seeds "${S40[@]}" --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3"
run --out $R/U5_b30 --budget 30 --solver-seeds 0 1 2     --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3"
run --out $R/U6_arrival --budget 8 --delta-mix arrival --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3"
run --out $R/U7_outage  --budget 8 --delta-mix outage  --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3"
run --out $R/U8_high    --budget 8 --severity high     --solver-seeds 0 1 2 3 4 --stream-seeds "${S20[@]}" --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3"
BD=tests/fixtures/benchmarks_real
run --out $R/U9_benchmarks --budget 8 --solver-seeds 0 1 2 3 4 --stream-seeds 1101 --cpus "${P[@]}" --methods "$B2" "$B0" "$B6" "$B3" \
    --benchmarks $BD/taillard/ta*.txt $BD/dmu/dmu0*.txt $BD/swv/swv0*.txt $BD/yn/yn*.txt
echo "unified confirmatory all done"
