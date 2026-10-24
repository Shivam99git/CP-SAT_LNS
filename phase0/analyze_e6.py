"""E6 robustness analysis (exploratory), methodology section 6.

For each E6 campaign directory: integrity, stream mean PI / gap_B per
method, and IAIP-SR vs each comparator (sign test over units, Holm within
the campaign, stream-clustered bootstrap CI). The unit is the stream; for
campaigns built on published instances (stream names "<base>_s<seed>") it is
the base instance, averaging its streams first.

    .venv/bin/python -m phase0.analyze_e6 results/research_extension/e6a_b2 ...
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .analyze_campaign import load, stream_tab
from .analyze_gate1 import compare, holm

IAIP = "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted"
ROLES = {IAIP: "iaip_sr", "iaip|portfolio=fresh": "fresh_portfolio_cold",
         "iaip|portfolio=full|global_mode=hinted": "portfolio_hinted", "floor": "floor", "cold": "cold",
         "lns_prev_solution": "lns_prev_solution", "fix_and_optimize_50": "fix_and_optimize_50"}
SYNTHETIC = re.compile(r"^\d+x\d+_s\d+")


def unit_tab(df, metric):
    t = stream_tab(df, metric)
    if all(SYNTHETIC.match(s) for s in t.index):
        return t, "stream"
    return t.groupby(t.index.str.replace(r"_s\d+.*$", "", regex=True)).mean(), "base instance"


def analyze(root: Path) -> dict:
    df = load(root)
    out = {"campaign": root.name, "budget": float(df.budget.iloc[0]), "workers": int(df.workers.iloc[0]),
           "integrity": {"records": int(len(df)),
                         "not_validated": int((~df.validated.astype(bool)).sum()),
                         "no_solution": int(df.objective.isna().sum()),
                         "overrun_max_s": float(df.overrun_s.max()),
                         "overrun_p99_s": float(df.overrun_s.quantile(0.99))}}
    tabs = {}
    for m in ("pi", "gap_B", "pi_late"):
        tabs[m], unit = unit_tab(df, m)
    out["unit"], out["n_units"] = unit, int(len(tabs["pi"]))
    out["means"] = {ROLES.get(c, c): {m: float(tabs[m][c].mean()) for m in tabs} for c in tabs["pi"].columns}
    comps = {f"iaip_sr vs {ROLES[b]}": {m: compare(tabs[m], IAIP, b) for m in tabs}
             for b in ROLES if b != IAIP and b in tabs["pi"].columns}
    h = holm({k: v["pi"]["sign_p"] for k, v in comps.items()})
    for k in comps:
        comps[k]["pi"]["sign_p_holm"] = h[k]
    out["comparisons"] = comps
    if unit == "base instance":
        fam = tabs["pi"].groupby(tabs["pi"].index.str.extract(r"^([a-z]+)", expand=False))
        out["by_family"] = {f: compare(g, IAIP, "iaip|portfolio=fresh") | {"n_bases": len(g)} for f, g in fam}
    return out


def main() -> None:
    res = [analyze(Path(p)) for p in sys.argv[1:]]
    for r in res:
        print(f"\n{r['campaign']}: B={r['budget']:g}s workers={r['workers']} {r['n_units']} {r['unit']}s",
              json.dumps(r["integrity"]))
        for role, mm in r["means"].items():
            print(f"  {role:22s} PI={mm['pi']:.4f} gapB={mm['gap_B']:.4f}")
        for k, v in r["comparisons"].items():
            c = v["pi"]
            print(f"  {k:34s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"W/L={c['stream_wins']}/{c['stream_losses']} p_holm={c['sign_p_holm']:.2g} "
                  f"| gapB {100 * v['gap_B']['rel_diff']:+6.1f}% W/L={v['gap_B']['stream_wins']}/{v['gap_B']['stream_losses']}")
        for f, c in r.get("by_family", {}).items():
            print(f"  family {f:8s} vs fresh: {100 * c['rel_diff']:+6.1f}% W/L={c['stream_wins']}/{c['stream_losses']} (n={c['n_bases']})")
    Path("results/research_extension/e6_analysis.json").write_text(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
