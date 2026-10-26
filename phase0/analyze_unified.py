"""Analysis for the unified critical-rounds study (docs/unified_icaps/).

Stream-level paired comparisons (exact sign test with Holm over the given
family, stream-clustered bootstrap 95% CI; published bases: base instance as
unit), means of PI / gap_B / time to first incumbent, the stream-level SD of
each difference (for power), and per-strategy round diagnostics from the run
metadata (neighbourhood size, critical coverage, improvement by round number,
timings).

    .venv/bin/python -m phase0.analyze_unified <dir> [--family a:b ...] [--out f]
Roles are short names derived from method strings (role()).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .analyze_campaign import load
from .analyze_cobar import unit_tab
from .analyze_gate1 import compare, holm

FIXED = {
    "iaip|portfolio=full|global_mode=hinted": "B6",
    "iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted": "B0",
    "cobar|neighbourhood=none|use_certificate=0|global_certificate=0|policy=fixed|global_params=interleave": "B5",
}


def role(m: str) -> str:
    if m in FIXED:
        return FIXED[m]
    if m.startswith("crgar|"):
        kv = dict(p.split("=") for p in m.split("|")[1:])
        name = kv.pop("strategy", "crit_expand")
        if kv.get("stop_on_fail") == "0" and "round_time" in kv:
            for k in ("stop_on_fail", "round_time", "max_rounds"):
                kv.pop(k, None)
            name += "@M2"
        return name + "".join(f"|{k}={v}" for k, v in sorted(kv.items()))
    if m.startswith("cobar|"):
        return "cobar:" + m[6:]
    return m


def round_diagnostics(df) -> dict:
    out = {}
    for m, g in df[df.step >= 1].groupby("method"):
        metas = [x for x in g["meta"] if isinstance(x, dict) and "rounds" in x and isinstance(x["rounds"], list)]
        if not metas or not m.startswith("crgar|"):
            continue
        rs = [r for x in metas for r in x["rounds"] if not r.get("empty")]
        by_k = defaultdict(list)
        for r in rs:
            by_k[r["round"]].append(r["improved"])
        out[role(m)] = {
            "instances": len(metas),
            "rounds_per_instance": len(rs) / len(metas),
            "improving_rounds_per_instance": sum(r["improved"] for r in rs) / len(metas),
            "round_improvement_rate": float(np.mean([r["improved"] for r in rs])) if rs else None,
            "improvement_rate_by_round": {int(k): [len(v), float(np.mean(v))] for k, v in sorted(by_k.items())},
            "released_ops_mean": float(np.mean([r["n_released_ops"] for r in rs])) if rs else None,
            "released_frac_mean": float(np.mean([r["released_frac"] for r in rs])) if rs else None,
            "machine_arcs_released_mean": float(np.mean([r["machine_arcs_released"] for r in rs])) if rs else None,
            "critical_in_N_mean": float(np.mean([r["critical_in_N"] for r in rs])) if rs else None,
            "chain_ops_mean": float(np.mean([r["chain_ops"] for r in rs])) if rs else None,
            "neighbourhood_ms_mean": 1000 * float(np.mean([r["neighbourhood_s"] for r in rs])) if rs else None,
            "build_ms_mean": 1000 * float(np.mean([r["build_s"] for r in rs])) if rs else None,
            "round_time_s_mean": float(np.mean([r["time_s"] for r in rs])) if rs else None,
            "local_window_s_mean": float(np.mean([x["local_window_s"] for x in metas])),
            "status": {s: sum(1 for r in rs if r["status"] == s) for s in {r["status"] for r in rs}},
            "initial_stage_improved": sum(1 for x in metas if x.get("initial_stage", {}).get("improved")),
        }
    return out


def analyze(root: Path, family: list[str]) -> dict:
    df = load(root)
    tabs = {}
    for m in ("pi", "gap_B", "pi_early", "pi_late", "t_first"):
        tabs[m], unit = unit_tab(df, m)
    by_role = {role(c): c for c in tabs["pi"].columns}
    out = {"campaign": root.name, "unit": unit, "n_units": int(len(tabs["pi"])),
           "solver_seeds": sorted(int(s) for s in df.solver_seed.unique()),
           "budget": float(df.budget.iloc[0]), "workers": int(df.workers.iloc[0]),
           "integrity": {"records": int(len(df)), "not_validated": int((~df.validated.astype(bool)).sum()),
                         "no_solution": int(df.objective.isna().sum()),
                         "overrun_max_s": float(df.overrun_s.max()), "overrun_p99_s": float(df.overrun_s.quantile(0.99))},
           "means": {r: {m: float(tabs[m][c].mean()) for m in tabs} | {"pi_median": float(tabs["pi"][c].median()),
                                                                       "pi_sd": float(tabs["pi"][c].std())}
                     for r, c in by_role.items()}}
    comps = {}
    for pair in family:
        a, b = pair.split(":")
        if a in by_role and b in by_role:
            comps[f"{a} vs {b}"] = {m: compare(tabs[m], by_role[a], by_role[b]) for m in tabs}
            d = (tabs["pi"][by_role[a]] - tabs["pi"][by_role[b]]).dropna()
            comps[f"{a} vs {b}"]["pi"]["diff_sd"] = float(d.std())
    if comps:
        h = holm({k: v["pi"]["sign_p"] for k, v in comps.items()})
        for k in comps:
            comps[k]["pi"]["sign_p_holm"] = h[k]
    out["comparisons"] = comps
    out["round_diagnostics"] = round_diagnostics(df)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--family", nargs="*", default=[])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = [analyze(Path(d), a.family) for d in a.dirs]
    for r in res:
        print(f"\n{r['campaign']}: B={r['budget']:g}s workers={r['workers']} {r['n_units']} {r['unit']}s seeds={r['solver_seeds']}",
              json.dumps(r["integrity"]))
        for k, mm in sorted(r["means"].items(), key=lambda x: x[1]["pi"]):
            print(f"  {k:40s} PI={mm['pi']:.4f} gapB={mm['gap_B']:.4f} t1={mm['t_first']:.3f}")
        for k, v in r["comparisons"].items():
            c = v["pi"]
            print(f"  {k:46s} {100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                  f"W/L={c['stream_wins']}/{c['stream_losses']} p={c['sign_p']:.2g} holm={c['sign_p_holm']:.2g} sd={c['diff_sd']:.4f}")
        for k, d in r["round_diagnostics"].items():
            print(f"  [rounds] {k:36s} r/inst={d['rounds_per_instance']:.2f} impr/inst={d['improving_rounds_per_instance']:.2f} "
                  f"rate={d['round_improvement_rate']} |N|={d['released_ops_mean']} arcs={d['machine_arcs_released_mean']} "
                  f"crit_in_N={d['critical_in_N_mean']} nb_ms={d['neighbourhood_ms_mean']}")
    out = Path(a.out) if a.out else Path(a.dirs[0]) / "analysis.json"
    out.write_text(json.dumps(res if len(res) > 1 else res[0], indent=2, default=float))
    print("wrote", out)


if __name__ == "__main__":
    main()
