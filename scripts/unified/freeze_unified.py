"""Freeze the unified confirmatory protocol (docs/unified_icaps/06_statistical_results.md §1).
Writes results/unified_icaps/confirmatory/FROZEN_CONFIG.json and its SHA-256; refuses
to overwrite or to run with uncommitted changes under phase0/."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

out = Path("results/unified_icaps/confirmatory")
out.mkdir(parents=True, exist_ok=True)
dest = out / "FROZEN_CONFIG.json"
if dest.exists():
    raise SystemExit("frozen already")
if subprocess.call(["git", "diff", "--quiet", "HEAD", "--", "phase0"]) != 0:
    raise SystemExit("phase0/ has uncommitted changes")
M2 = "|stop_on_fail=0|round_time=0.4|max_rounds=6"
roles = {
    "B2_crit": "crgar|strategy=crit_expand",
    "B0_iaip": "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted",
    "B6_port_hint": "iaip|portfolio=full|global_mode=hinted",
    "B1_random": "crgar|strategy=random_matched",
    "B3_timewin": "crgar|strategy=time_window",
    "B4_prec": "crgar|strategy=precedence",
    "B5_native1w": "cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave",
    "M2_crit": "crgar|strategy=crit_expand" + M2,
    "M2_random": "crgar|strategy=random_matched" + M2,
    "M2_timewin": "crgar|strategy=time_window" + M2,
    "M2_prec": "crgar|strategy=precedence" + M2,
}
core4 = ["B2_crit", "B0_iaip", "B6_port_hint", "B3_timewin"]
S40 = list(range(1101, 1121))
S20 = list(range(1101, 1111))
settings = {
    "U1_primary": {"budget": 8, "workers": 1, "stream_seeds": S40, "solver_seeds": [0, 1, 2, 3, 4],
                   "methods": ["B2_crit", "B0_iaip", "B6_port_hint", "B1_random", "B3_timewin", "B4_prec", "B5_native1w"]},
    "U2_mechanism": {"budget": 8, "workers": 1, "stream_seeds": S40, "solver_seeds": [0, 1, 2, 3, 4],
                     "methods": ["M2_crit", "M2_random", "M2_timewin", "M2_prec"]},
    "U3_workers4": {"budget": 8, "workers": 4, "stream_seeds": S20, "solver_seeds": [0, 1, 2, 3, 4], "methods": core4,
                    "note": "B6 with 4 workers is CP-SAT's native multi-worker LNS (scheduling LNS subsolvers confirmed in logs)"},
    "U4_b2": {"budget": 2, "workers": 1, "stream_seeds": S40, "solver_seeds": [0, 1, 2, 3, 4], "methods": core4},
    "U5_b30": {"budget": 30, "workers": 1, "stream_seeds": S20, "solver_seeds": [0, 1, 2], "methods": core4},
    "U6_arrival": {"budget": 8, "workers": 1, "delta_mix": "arrival", "stream_seeds": S20, "solver_seeds": [0, 1, 2, 3, 4], "methods": core4},
    "U7_outage": {"budget": 8, "workers": 1, "delta_mix": "outage", "stream_seeds": S20, "solver_seeds": [0, 1, 2, 3, 4], "methods": core4},
    "U8_high": {"budget": 8, "workers": 1, "severity": "high", "stream_seeds": S20, "solver_seeds": [0, 1, 2, 3, 4], "methods": core4},
    "U9_benchmarks": {"budget": 8, "workers": 1, "benchmarks": "ta01-ta20, dmu01-05, swv01-05, yn1-4 (34 bases)", "stream_seeds": [1101],
                      "solver_seeds": [0, 1, 2, 3, 4], "methods": core4, "unit": "base instance"},
}
cfg = {
    "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "ortools": "9.15.6755",
    "selection_basis": "development pilots D1-D3 on streams 301-310 (docs/unified_icaps/03_lns_baseline_protocol.md); "
                       "candidate and control set fixed by rules written before the pilots",
    "roles": roles, "settings": settings, "run_order": list(settings),
    "streams": "full m x m job shops, m in {15,20}, durations U[5,50], 10 deltas, generator defaults unless stated; "
               "stream seeds 1101-1120 never used before (checked)",
    "primary_metric": "stream mean of PI over steps 1..10 and solver seeds; shared z* per physical instance within a setting",
    "family_U1": [["B2_crit", "B0_iaip"], ["B2_crit", "B1_random"], ["B2_crit", "B3_timewin"], ["B2_crit", "B4_prec"],
                  ["B2_crit", "B5_native1w"], ["B2_crit", "B6_port_hint"], ["B3_timewin", "B0_iaip"], ["B1_random", "B0_iaip"]],
    "family_U2": [["M2_crit", "M2_random"], ["M2_crit", "M2_timewin"], ["M2_crit", "M2_prec"], ["M2_timewin", "M2_random"]],
    "family_other": [["B2_crit", "B0_iaip"], ["B2_crit", "B6_port_hint"], ["B2_crit", "B3_timewin"]],
    "equivalence_margin": 0.10,
    "criteria": {
        "C1_replication": "U1 B2 vs B0: reduction >= 5%, CI upper < 0, Holm p < 0.05",
        "C2_vs_random": "U1 B2 vs B1: CI upper < 0, Holm p < 0.05",
        "C3_vs_timewin": "U1 B2 vs B3: superior if CI upper < 0 and Holm p < 0.05; inferior if CI lower > 0 and Holm p < 0.05; "
                         "practically equivalent if the 95% CI lies within +-10% of B3's mean PI; otherwise inconclusive",
        "C4_vs_prec": "U1 B2 vs B4: CI upper < 0",
        "C5_vs_native1w": "U1 B2 vs B5: CI upper < 0",
        "C6_vs_native4w": "U3 B2 vs B6 (4 workers): CI upper < 0",
        "validity": "all outputs validated",
    },
    "classification": {
        "STRONG_GO": "C1, C2, C3 superior, C4, C5, C6 and validity hold",
        "CONDITIONAL_GO": "C1 and validity hold, but C3 is not superior (equivalent or inconclusive) or C6 fails: "
                          "no claim of superior critical-region search; empirical framing",
        "NO_GO_novelty": "C1 fails, or C3 inferior (time-window LNS significantly better)",
    },
    "cpus": {"single_worker": [0, 2, 4, 6, 8, 10, 12, 14], "four_workers": ["0,2,4,6", "8,10,12,14"]},
}
raw = json.dumps(cfg, indent=2).encode()
dest.write_bytes(raw)
(out / "FROZEN_CONFIG.sha256").write_text(hashlib.sha256(raw).hexdigest() + "  FROZEN_CONFIG.json\n")
print(hashlib.sha256(raw).hexdigest())
