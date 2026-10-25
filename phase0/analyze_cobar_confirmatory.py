"""Confirmatory analysis for COBAR, driven by results/cobar/confirmatory/
FROZEN_CONFIG.json (refuses to run if the file changed after freezing).

    .venv/bin/python -m phase0.analyze_cobar_confirmatory results/cobar/confirmatory
Setting directories are <root>/S1_primary, <root>/S2_short, ... .
    --only S1_primary [S2_short ...]   analyse only these (finished) settings
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .analyze_cobar import unit_tab
from .analyze_campaign import load
from .analyze_gate1 import compare, holm


def main() -> None:
    root = Path(sys.argv[1])
    only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None  # restrict to finished settings
    raw = (root / "FROZEN_CONFIG.json").read_bytes()
    cfg = json.loads(raw)
    sha = (root / "FROZEN_CONFIG.sha256").read_text().split()[0]
    assert hashlib.sha256(raw).hexdigest() == sha, "FROZEN_CONFIG.json changed after freezing"
    roles = cfg["roles"]
    crit = cfg["criteria"]
    out = {"frozen_sha256": sha, "settings": {}}
    for name in sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "runs").exists()):
        if only and name not in only:
            continue
        df = load(root / name)
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
        pairs = cfg["family_S1"] if name.startswith("S1") else [["candidate", "iaip_sr"], ["candidate", "portfolio_hinted"]]
        comps = {f"{a} vs {b}": {m: compare(tabs[m], present[a], present[b]) for m in tabs}
                 for a, b in pairs if a in present and b in present}
        h = holm({k: v["pi"]["sign_p"] for k, v in comps.items()})
        for k in comps:
            comps[k]["pi"]["sign_p_holm"] = h[k]
        s["comparisons"] = comps
        c = comps.get("candidate vs iaip_sr", {}).get("pi")
        if c:
            s["non_inferiority_vs_iaip_sr"] = bool(c["ci95"][1] < crit["non_inferiority_margin"] * c["mean_b"])
        out["settings"][name] = s
    S1 = out["settings"].get("S1_primary")
    verdict = {}
    if S1:
        p = S1["comparisons"]["candidate vs iaip_sr"]["pi"]
        q = S1["comparisons"]["candidate vs portfolio_hinted"]["pi"]
        r = S1["comparisons"]["candidate vs random_rounds"]["pi"]
        g = S1["comparisons"]["candidate vs iaip_sr"]["gap_B"]
        verdict = {
            "primary_target": -p["rel_diff"] >= 0.05 and p["ci95"][1] < 0 and p["sign_p_holm"] < 0.05,
            "stronger_target": -q["rel_diff"] >= 0.10 and q["ci95"][1] < 0,
            "location_matters": r["ci95"][1] < 0,
            "no_final_gap_regression": g["ci95"][0] <= 0 or g["mean_diff"] <= 0,
            "all_outputs_validated": all(s["integrity"]["not_validated"] == 0 for s in out["settings"].values()),
        }
        for k in ("S2_short", "S3_workers4"):
            if k in out["settings"]:
                verdict[f"non_inferiority_{k}"] = out["settings"][k]["non_inferiority_vs_iaip_sr"]
    out["criteria"] = verdict
    (root / ("confirmatory_analysis.json" if not only else f"confirmatory_analysis_{'_'.join(only)}.json")).write_text(json.dumps(out, indent=2, default=float))
    for name, s in out["settings"].items():
        print(f"\n{name}: {s['n_units']} {s['unit']}s, seeds {s['solver_seeds']}", json.dumps(s["integrity"]))
        for r, mm in sorted(s["means"].items(), key=lambda x: x[1]["pi"]):
            print(f"  {r:18s} PI={mm['pi']:.4f} gapB={mm['gap_B']:.4f}")
        for k, v in s["comparisons"].items():
            c = v["pi"]
            print(f"  {k:34s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"W/L={c['stream_wins']}/{c['stream_losses']} p_holm={c['sign_p_holm']:.2g}")
        if "non_inferiority_vs_iaip_sr" in s:
            print("  non-inferior to IAIP-SR (5% margin):", s["non_inferiority_vs_iaip_sr"])
    print("\ncriteria:", json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
