#!/usr/bin/env bash
# Unified dev pilot D3: 4 workers (native CP-SAT LNS active), dev streams 301-305, solver seed 3.
set -euo pipefail
cd "$(dirname "$0")/../.."
until grep -q "unified dev pilots done" logs/unified_dev.log; do sleep 30; done
.venv/bin/python -m phase0.run_iaip_campaign --out results/unified_icaps/dev/d3_w4 --tag unified_dev --budget 8 --workers 4 \
  --stream-length 10 --solver-seeds 3 --stream-seeds 301 302 303 304 305 --cpu-groups 0,2,4,6 8,10,12,14 \
  --methods "iaip|portfolio=full|global_mode=hinted" "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted" \
  "crgar|strategy=crit_expand" "crgar|strategy=time_window"
echo "unified dev D3 done"
