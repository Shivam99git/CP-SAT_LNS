"""Confirmatory analysis for IAIP-SR, driven by FROZEN_CONFIG.json.

The method set, the predeclared comparison family and the GO criteria are
read from the frozen file, so this script cannot be pointed at a different
endpoint after the run. Unit of inference: the stream (40 held-out streams);
solver seeds and steps 1..T are averaged within a stream. Primary endpoint:
stream mean of the archived primal integral `pi`.

    .venv/bin/python -m phase0.analyze_confirmatory results/research_extension/confirmatory
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from .analyze_campaign import load, stream_tab
from .analyze_gate1 import compare, holm


def main() -> None:
    root = Path(sys.argv[1])
    raw = (root / "FROZEN_CONFIG.json").read_bytes()
    cfg = json.loads(raw)
    sha = (root / "FROZEN_CONFIG.sha256").read_text().split()[0]
    assert hashlib.sha256(raw).hexdigest() == sha, "FROZEN_CONFIG.json changed after freezing"
    roles = cfg["roles"]
    df = load(root)
    out = {"frozen_sha256": sha, "n_streams": int(df.stream.nunique()),
           "solver_seeds": sorted(int(s) for s in df.solver_seed.unique()),
           "integrity": {"records": int(len(df)),
                         "not_validated": int((~df.validated.astype(bool)).sum()),
                         "no_solution": int(df.objective.isna().sum()),
                         "overrun_runs": int((df.overrun_s > 0).sum()),
                         "overrun_max_s": float(df.overrun_s.max()),
                         "overrun_p99_s": float(df.overrun_s.quantile(0.99))}}
    tabs = {m: stream_tab(df, m) for m in ("pi", "pi_capped", "pi_early", "pi_late", "gap_B", "t_first")}
    name = {r: roles[r] for r in roles}
    out["means"] = {r: {m: float(tabs[m][name[r]].mean()) for m in tabs} for r in roles}

    fam = {}
    for a, b in cfg["family"]:
        fam[f"{a} vs {b}"] = {m: compare(tabs[m], name[a], name[b]) for m in tabs}
    h = holm({k: v["pi"]["sign_p"] for k, v in fam.items()})
    for k in fam:
        fam[k]["pi"]["sign_p_holm"] = h[k]
    out["family"] = fam

    # GO criteria on the primary comparison
    a, b = cfg["family"][0]
    prim = fam[f"{a} vs {b}"]["pi"]
    sel = fam[f"{cfg['selective_check'][0]} vs {cfg['selective_check'][1]}"]["pi"]
    gap = fam[f"{a} vs {b}"]["gap_B"]
    crit = {
        "pi_reduction_ge_15pct": -prim["rel_diff"] >= 0.15,
        "wins_ge_70pct_streams": prim["stream_wins"] >= 0.7 * prim["n_streams"],
        "ci_excludes_zero": prim["ci95"][1] < 0,
        "primary_holm_p_lt_0_05": prim["sign_p_holm"] < 0.05,
        "no_final_gap_regression": gap["ci95"][0] <= 0 or gap["mean_diff"] <= 0,
        "all_outputs_validated": out["integrity"]["not_validated"] == 0,
        "selective_stage_adds_value": sel["ci95"][1] < 0 and sel["sign_p_holm"] < 0.05,
    }
    out["go_criteria"] = crit
    by_delta = {}
    for k in sorted(df[df.step >= 1].delta_kind.unique()):
        t = stream_tab(df, "pi", delta=k)
        by_delta[k] = {r: float(t[name[r]].mean()) for r in roles if name[r] in t}
        by_delta[k]["primary"] = compare(t, name[a], name[b])
    out["by_delta"] = by_delta
    by_size = {}
    for s in sorted(df["size"].unique()):
        t = stream_tab(df[df["size"] == s], "pi")
        by_size[s] = compare(t, name[a], name[b])
    out["by_size"] = by_size
    (root / "confirmatory_analysis.json").write_text(json.dumps(out, indent=2, default=float))

    print(json.dumps(out["integrity"]))
    print(f"\n{out['n_streams']} streams, seeds {out['solver_seeds']}; stream mean PI (steps 1..T)")
    for r in roles:
        mm = out["means"][r]
        print(f"  {r:24s} PI={mm['pi']:.4f} late={mm['pi_late']:.4f} gapB={mm['gap_B']:.4f} t1={mm['t_first']:.3f}")
    print("\npredeclared family (Holm on sign test over streams):")
    for k, v in fam.items():
        c = v["pi"]
        print(f"  {k:46s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
              f"W/L={c['stream_wins']}/{c['stream_losses']} p_holm={c['sign_p_holm']:.2g}")
    print("\nGO criteria:", json.dumps(crit, indent=1))


if __name__ == "__main__":
    main()
