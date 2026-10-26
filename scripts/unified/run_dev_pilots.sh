#!/usr/bin/env bash
# Unified study development pilots D1-D2 (docs/unified_icaps/03_lns_baseline_protocol.md). Dev streams, solver seed 3.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=.venv/bin/python
R=results/unified_icaps/dev
B6="iaip|portfolio=full|global_mode=hinted"
B0="iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
B5="cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave"
C="crgar|strategy"
M2="stop_on_fail=0|round_time=0.4|max_rounds=6"
P=(0 2 4 6 8 10 12 14)
S=(301 302 303 304 305 306 307 308 309 310)
run() { $PY -m phase0.run_iaip_campaign --stream-length 10 --solver-seeds 3 --tag unified_dev "$@"; }
run --out $R/d1_b8 --budget 8 --stream-seeds "${S[@]}" --cpus "${P[@]}" --methods "$B6" "$B0" "$B5" \
    "$C=crit_expand" "$C=crit_onechain_expand" "$C=crit_blocks_expand" "$C=crit_disr_expand" "$C=crit_onehop" "$C=crit_chain" \
    "$C=random_bfs" "$C=random_matched" "$C=time_window" "$C=precedence"
run --out $R/d2_b8_mech --budget 8 --stream-seeds "${S[@]}" --cpus "${P[@]}" --methods "$B0" "$C=crit_expand" \
    "$C=crit_expand|$M2" "$C=random_matched|$M2" "$C=time_window|$M2" "$C=precedence|$M2" \
    "$C=crit_expand|recompute=0" "$C=crit_expand|initial_stage=0" "$C=crit_expand|final_global=0"
echo "unified dev pilots done"
