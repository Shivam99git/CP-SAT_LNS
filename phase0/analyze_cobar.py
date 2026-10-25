"""Analysis of COBAR pilot / confirmatory campaigns.

For a campaign directory: integrity, stream-mean metrics per method, paired
stream-level comparisons (exact sign test, Holm within the given family,
stream-clustered bootstrap CI; published bases: base instance as unit), and
certificate statistics from the run metadata (docs/cobar/07, Task 8.3).

    .venv/bin/python -m phase0.analyze_cobar results/cobar/pilot/p1_b8 [--family A1:A0 A6:A1 ...]
Method roles are recognised from their method strings (ROLE_OF below).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .analyze_campaign import load, stream_tab
from .analyze_gate1 import compare, holm

ROLE_OF = {
    "iaip|portfolio=full|global_mode=hinted": "A0",
    "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted": "A1",
    "cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=fixed": "A2",
    "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=0|global_certificate=0|policy=fixed": "A3",
    "cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=budget": "A4",
    "cobar|neighbourhood=iaip|use_certificate=1|skip_certified=1|global_certificate=0|policy=cert+budget": "A5",
    "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=cert+budget": "A6",
    "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=fixed": "A8",
    "cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave": "A9",
    "cobar|neighbourhood=iaip+release|use_certificate=1|skip_certified=1|global_certificate=1|policy=cert+budget|rounds=10": "A6r",
    "cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=iaip": "A10",
    "cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10|round_neighbourhood=critical": "A12",
}
DEFAULT_FAMILY = ["A1:A0", "A2:A1", "A3:A1", "A4:A1", "A5:A4", "A6:A4", "A6:A1", "A8:A1", "A9:A0",
                  "A6r:A1", "A6r:A10", "A6r:A12", "A6r:A9", "A10:A1", "A12:A1"]
SYNTHETIC = re.compile(r"^\d+x\d+_s\d+")


def role(m: str) -> str:
    return ROLE_OF.get(m, m)


def unit_tab(df, metric):
    t = stream_tab(df, metric)
    if all(SYNTHETIC.match(s) for s in t.index):
        return t, "stream"
    return t.groupby(t.index.str.replace(r"_s\d+.*$", "", regex=True)).mean(), "base instance"


def certificate_stats(df) -> dict:
    out = {}
    for m, g in df[df.step >= 1].groupby("method"):
        metas = [x for x in g["meta"] if isinstance(x, dict)]
        if not any("decision" in x or "certificate" in x or "global_certificate" in x for x in metas):
            continue
        n = len(metas)
        certs = [x["certificate"] for x in metas if "certificate" in x]
        rel = [x["release"] for x in metas if "release" in x]
        dec = [x["decision"] for x in metas if "decision" in x]
        loc = [x["local"] for x in metas if "local" in x]
        rounds = [r for x in metas for r in x.get("rounds", [])]
        gaps = [(c["U"] - c["L"]) / c["U"] for c in certs if c["U"] > 0]
        reasons = Counter(d["reason"].split(" ")[0] + (" " + d["reason"].split(" ")[1] if " " in d["reason"] else "")
                          for d in dec)
        out[role(m)] = {
            "steps": n,
            "global_certified_optimal": sum(1 for x in metas if x.get("global_certificate", {}).get("decisive")),
            "certificate_computed": len(certs),
            "certified_non_improving": sum(c["decisive"] for c in certs),
            "certified_kind": dict(Counter(c["kind"] for c in certs if c["decisive"])),
            "opportunity_gap_median": float(np.median(gaps)) if gaps else None,
            "opportunity_gap_p10": float(np.quantile(gaps, 0.1)) if gaps else None,
            "certificate_time_ms_mean": 1000 * float(np.mean([c["time_s"] for c in certs])) if certs else None,
            "release_status": dict(Counter(r["status"] for r in rel)),
            "released_arcs_mean_when_released": float(np.mean([r["n_released_arcs"] for r in rel if r["status"] == "released"]))
            if any(r["status"] == "released" for r in rel) else 0.0,
            "release_time_ms_mean": 1000 * float(np.mean([r["time_s"] for r in rel])) if rel else None,
            "decision_reasons": dict(reasons),
            "local_run": len(loc),
            "local_improved": sum(bool(x["local_improved"]) for x in loc),
            "local_status": dict(Counter(x["local_status"] for x in loc)),
            "local_time_s_mean": float(np.mean([x["local_time_s"] for x in loc])) if loc else 0.0,
            "neighbourhood_size_mean": float(np.mean([x.get("neighbourhood_size", 0) for x in metas])),
            "extra_rounds": len(rounds), "extra_rounds_improved": sum(r["improved"] for r in rounds),
            "global_s_mean": float(np.mean([x["stage_s"].get("global_s", 0.0) for x in metas if "stage_s" in x])),
            "fallbacks": sum(len(x.get("fallbacks", [])) for x in metas),
        }
    return out


def analyze(root: Path, family: list[str]) -> dict:
    df = load(root)
    out = {"campaign": root.name, "budget": float(df.budget.iloc[0]), "workers": int(df.workers.iloc[0]),
           "integrity": {"records": int(len(df)),
                         "not_validated": int((~df.validated.astype(bool)).sum()),
                         "no_solution": int(df.objective.isna().sum()),
                         "overrun_max_s": float(df.overrun_s.max()),
                         "overrun_p99_s": float(df.overrun_s.quantile(0.99))}}
    tabs = {}
    for m in ("pi", "gap_B", "pi_early", "pi_late", "t_first"):
        tabs[m], unit = unit_tab(df, m)
    out["unit"], out["n_units"] = unit, int(len(tabs["pi"]))
    by_role = {role(c): c for c in tabs["pi"].columns}
    out["means"] = {r: {m: float(tabs[m][c].mean()) for m in tabs} for r, c in by_role.items()}
    comps = {}
    for pair in family:
        a, b = pair.split(":")
        if a in by_role and b in by_role:
            comps[f"{a} vs {b}"] = {m: compare(tabs[m], by_role[a], by_role[b]) for m in tabs}
    if comps:
        h = holm({k: v["pi"]["sign_p"] for k, v in comps.items()})
        for k in comps:
            comps[k]["pi"]["sign_p_holm"] = h[k]
    out["comparisons"] = comps
    by_delta = {}
    for k in sorted(df[df.step >= 1].delta_kind.unique()):
        t = stream_tab(df, "pi", delta=k)
        by_delta[k] = {role(c): float(t[c].mean()) for c in t.columns}
    out["by_delta"] = by_delta
    out["certificate_stats"] = certificate_stats(df)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--family", nargs="*", default=DEFAULT_FAMILY)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = [analyze(Path(d), a.family) for d in a.dirs]
    for r in res:
        print(f"\n{r['campaign']}: B={r['budget']:g}s workers={r['workers']} {r['n_units']} {r['unit']}s", json.dumps(r["integrity"]))
        for k, mm in sorted(r["means"].items(), key=lambda x: x[1]["pi"]):
            print(f"  {k:6s} PI={mm['pi']:.4f} gapB={mm['gap_B']:.4f} t1={mm['t_first']:.3f}")
        for k, v in r["comparisons"].items():
            c = v["pi"]
            print(f"  {k:12s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"W/L={c['stream_wins']}/{c['stream_losses']} p={c['sign_p']:.2g} p_holm={c['sign_p_holm']:.2g}")
    out = Path(a.out) if a.out else Path(a.dirs[0]) / "analysis.json"
    out.write_text(json.dumps(res if len(res) > 1 else res[0], indent=2, default=float))
    print("wrote", out)


if __name__ == "__main__":
    main()
