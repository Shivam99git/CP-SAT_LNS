"""Write results/research_extension/confirmatory/FROZEN_CONFIG.json and its
SHA-256. Run once, before the confirmatory campaign; refuses to overwrite.

    .venv/bin/python scripts/freeze_confirmatory.py --alpha 0.4
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--alpha", type=float, required=True)
ap.add_argument("--neighbourhood", default="N5")
a = ap.parse_args()

out = Path("results/research_extension/confirmatory")
out.mkdir(parents=True, exist_ok=True)
dest = out / "FROZEN_CONFIG.json"
if dest.exists():
    raise SystemExit(f"{dest} already exists; the confirmatory configuration is frozen")

iaip = f"iaip|portfolio=full|alpha={a.alpha}|neighbourhood={a.neighbourhood}|global_mode=hinted"
roles = {
    "iaip_sr": iaip,
    "portfolio_hinted": "iaip|portfolio=full|global_mode=hinted",
    "portfolio_cold": "iaip|portfolio=full",
    "fresh_portfolio_cold": "iaip|portfolio=fresh",
    "fresh_portfolio_hinted": "iaip|portfolio=fresh|global_mode=hinted",
    "mwkr_cold": "mwkr_cold",
    "floor": "floor",
    "cold": "cold",
    "elr_cold": "iaip|portfolio=elr",
    "random_nbh_control": f"iaip|portfolio=full|alpha={a.alpha}|neighbourhood=random|global_mode=hinted",
}
cfg = {
    "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "selection_basis": "development streams 301-310 only (dev_e3e4, dev_e5, dev_e5b, dev_e5c)",
    "roles": roles,
    "methods": list(roles.values()),
    "family": [
        ["iaip_sr", "fresh_portfolio_cold"],    # predeclared primary comparison
        ["iaip_sr", "fresh_portfolio_hinted"],
        ["iaip_sr", "mwkr_cold"],
        ["iaip_sr", "floor"],
        ["iaip_sr", "cold"],
        ["iaip_sr", "portfolio_hinted"],        # does the selective stage add value?
        ["iaip_sr", "random_nbh_control"],      # does impact-awareness matter?
        ["portfolio_cold", "fresh_portfolio_cold"],  # does history help the portfolio?
    ],
    "selective_check": ["iaip_sr", "portfolio_hinted"],
    "streams": {"sizes": [15, 20], "stream_seeds": list(range(501, 521)), "stream_length": 10,
                "generator": "full job shop, durations U[5,50], default delta weights, severity medium"},
    "solver_seeds": [0, 1, 2, 3, 4],
    "budget_s": 8.0,
    "workers": 1,
    "cpus": [0, 2, 4, 6, 8, 10, 12, 14],
    "primary_endpoint": "stream mean of archived primal integral (pi) over steps 1..10, shared z* per instance",
    "go_criteria": "docs/research_extension/04_experimental_methodology.md section 5",
}
raw = json.dumps(cfg, indent=2).encode()
dest.write_bytes(raw)
(out / "FROZEN_CONFIG.sha256").write_text(hashlib.sha256(raw).hexdigest() + "  FROZEN_CONFIG.json\n")
print(hashlib.sha256(raw).hexdigest())
