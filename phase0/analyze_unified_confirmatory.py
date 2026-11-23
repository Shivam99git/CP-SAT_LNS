"""Confirmatory analysis for the unified critical-rounds study, driven by
results/unified_icaps/confirmatory/FROZEN_CONFIG.json (refuses to run if the
file changed after freezing).

    .venv/bin/python -m phase0.analyze_unified_confirmatory results/unified_icaps/confirmatory
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .analyze_campaign import load
from .analyze_cobar import unit_tab
from .analyze_gate1 import compare, holm


def main() -> None:
    root = Path(sys.argv[1])
    raw = (root / "FROZEN_CONFIG.json").read_bytes()
    cfg = json.loads(raw)
    sha = (root / "FROZEN_CONFIG.sha256").read_text().split()[0]
    assert hashlib.sha256(raw).hexdigest() == sha, "FROZEN_CONFIG.json changed after freezing"
    roles = cfg["roles"]
    margin = cfg["equivalence_margin"]
    out = {"frozen_sha256": sha, "settings": {}}

    for name in cfg["run_order"]:
        d = root / name
        if not (d / "runs").exists():
            continue
        df = load(d)
        tabs = {}
        for m in ("pi", "gap_B", "pi_late", "t_first"):
            tabs[m], unit = unit_tab(df, m)
        present = {r: c for r, c in roles.items() if c in tabs["pi"].columns}
        s = {"unit": unit, "n_units": int(len(tabs["pi"])),
             "solver_seeds": sorted(int(x) for x in df.solver_seed.unique()),
             "integrity": {"records": int(len(df)), "not_validated": int((~df.validated.astype(bool)).sum()),
                           "no_solution": int(df.objective.isna().sum()),
                           "overrun_max_s": float(df.overrun_s.max()),
                           "overrun_p99_s": float(df.overrun_s.quantile(0.99))},
             "means": {r: {m: float(tabs[m][c].mean()) for m in tabs} for r, c in present.items()}}
        if name == "U1_primary":
            pairs = cfg["family_U1"]
        elif name == "U2_mechanism":
            pairs = cfg["family_U2"]
        else:
            pairs = cfg["family_other"]
        comps = {f"{a} vs {b}": {m: compare(tabs[m], present[a], present[b]) for m in tabs}
                 for a, b in pairs if a in present and b in present}
        h = holm({k: v["pi"]["sign_p"] for k, v in comps.items()})
        for k in comps:
            comps[k]["pi"]["sign_p_holm"] = h[k]
        s["comparisons"] = comps
        out["settings"][name] = s

    U1 = out["settings"].get("U1_primary")
    verdict = {}
    if U1:
        c1 = U1["comparisons"]["B2_crit vs B0_iaip"]["pi"]
        c2 = U1["comparisons"]["B2_crit vs B1_random"]["pi"]
        c3 = U1["comparisons"]["B2_crit vs B3_timewin"]["pi"]
        c4 = U1["comparisons"]["B2_crit vs B4_prec"]["pi"]
        c5 = U1["comparisons"]["B2_crit vs B5_native1w"]["pi"]
        C1 = (-c1["rel_diff"] >= 0.05) and (c1["ci95"][1] < 0) and (c1["sign_p_holm"] < 0.05)
        C2 = (c2["ci95"][1] < 0) and (c2["sign_p_holm"] < 0.05)
        mean_b3 = c3["mean_b"]
        if c3["ci95"][1] < 0 and c3["sign_p_holm"] < 0.05:
            c3_verdict = "superior"
        elif c3["ci95"][0] > 0 and c3["sign_p_holm"] < 0.05:
            c3_verdict = "inferior"
        elif abs(c3["ci95"][0]) <= margin * mean_b3 and abs(c3["ci95"][1]) <= margin * mean_b3:
            c3_verdict = "equivalent"
        else:
            c3_verdict = "inconclusive"
        C4 = (c4["ci95"][1] < 0) and (c4["sign_p_holm"] < 0.05)
        C5 = (c5["ci95"][1] < 0) and (c5["sign_p_holm"] < 0.05)
        verdict = {"C1_replication": C1, "C2_vs_random": C2, "C3_vs_timewin": c3_verdict,
                   "C4_vs_prec": C4, "C5_vs_native1w": C5}
    U3 = out["settings"].get("U3_workers4")
    if U3 and "B2_crit vs B6_port_hint" in U3["comparisons"]:
        c6 = U3["comparisons"]["B2_crit vs B6_port_hint"]["pi"]
        verdict["C6_vs_native4w"] = (c6["ci95"][1] < 0) and (c6["sign_p_holm"] < 0.05)
    verdict["validity"] = all(s["integrity"]["not_validated"] == 0 for s in out["settings"].values())

    if verdict.get("C1_replication") and verdict.get("C2_vs_random") and verdict.get("C3_vs_timewin") == "superior" \
            and verdict.get("C4_vs_prec") and verdict.get("C5_vs_native1w") and verdict.get("C6_vs_native4w") and verdict.get("validity"):
        classification = "STRONG_GO"
    elif verdict.get("C1_replication") and verdict.get("validity"):
        classification = "CONDITIONAL_GO"
    else:
        classification = "NO_GO_novelty"
    out["criteria"] = verdict
    out["classification"] = classification

    (root / "confirmatory_analysis.json").write_text(json.dumps(out, indent=2, default=float))
    for name, s in out["settings"].items():
        print(f"\n{name}: {s['n_units']} {s['unit']}s, seeds {s['solver_seeds']}", json.dumps(s["integrity"]))
        for r, mm in sorted(s["means"].items(), key=lambda x: x[1]["pi"]):
            print(f"  {r:16s} PI={mm['pi']:.4f} gapB={mm['gap_B']:.4f}")
        for k, v in s["comparisons"].items():
            c = v["pi"]
            print(f"  {k:36s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"W/L={c['stream_wins']}/{c['stream_losses']} holm={c['sign_p_holm']:.2g}")
    print("\ncriteria:", json.dumps(verdict, indent=1))
    print("CLASSIFICATION:", classification)


if __name__ == "__main__":
    main()
