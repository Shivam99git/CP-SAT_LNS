"""Stream-level analysis of a run_iaip_campaign output directory.

Uses the same per-run metrics and stream-level statistics as
analyze_gate1.py (shared z* per physical instance, PI from saved
trajectories, streams as the unit of inference). Development campaigns are
exploratory: p-values are reported uncorrected and labelled as such.

    .venv/bin/python -m phase0.analyze_campaign results/research_extension/dev_e3e4 \\
        --baselines iaip|portfolio=fresh mwkr_cold floor cold
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .analyze_gate1 import METRICS, compare, per_run


def load(root: Path) -> pd.DataFrame:
    recs = [json.loads(l) for f in sorted(glob.glob(str(root / "runs" / "*.jsonl"))) for l in open(f)]
    df = pd.DataFrame(recs)
    df["inst_key"] = df["stream"] + "|" + df["step"].astype(str)
    zstar = df[df.objective.notna()].groupby("inst_key").objective.min()
    met = [per_run(r, zstar[r["inst_key"]]) if r["inst_key"] in zstar.index
           else {m: np.nan for m in METRICS} for r in df.to_dict("records")]
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(met)], axis=1)


def stream_tab(df, metric, steps_from=1, delta=None):
    d = df[df.step >= steps_from]
    if delta is not None:
        d = d[d.delta_kind == delta]
    return d.groupby(["stream", "method"])[metric].mean().unstack("method")


def summarize(df: pd.DataFrame, baselines: list[str]) -> dict:
    out = {"integrity": {"records": int(len(df)),
                         "not_validated": int((~df.validated.astype(bool)).sum()),
                         "no_solution": int(df.objective.isna().sum()),
                         "overrun_runs": int((df.overrun_s > 0).sum()),
                         "overrun_max_s": float(df.overrun_s.max())}}
    tab = stream_tab(df, "pi")
    out["methods"] = {}
    for m in tab.columns:
        row = {"mean_pi": float(tab[m].mean()), "median_pi": float(tab[m].median())}
        for metric in ("pi_early", "pi_late", "gap_B", "t_first", "pi_capped"):
            row[metric] = float(stream_tab(df, metric)[m].mean())
        sub = df[(df.method == m) & (df.step >= 1)]
        loc = [r.get("local") for r in sub.meta if isinstance(r, dict) and r.get("local")]
        if loc:
            row["local_improved_rate"] = float(np.mean([l["local_improved"] for l in loc]))
            row["local_status"] = pd.Series([l["local_status"] for l in loc]).value_counts().to_dict()
            row["neighbourhood_frac"] = float(np.mean([l["neighbourhood_size"] / l["n_ops"] for l in loc]))
            row["local_time_s"] = float(np.mean([l["local_time_s"] for l in loc]))
        pf = [r.get("portfolio", {}).get("chosen") for r in sub.meta if isinstance(r, dict) and r.get("portfolio")]
        if pf:
            row["portfolio_chosen"] = pd.Series(pf).value_counts().to_dict()
        row["vs"] = {b: compare(tab, m, b) for b in baselines if b in tab and b != m}
        out["methods"][m] = row
    out["by_delta"] = {}
    for k in sorted(df[df.step >= 1].delta_kind.unique()):
        t = stream_tab(df, "pi", delta=k)
        out["by_delta"][k] = {m: float(t[m].mean()) for m in t.columns}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--baselines", nargs="+", default=["iaip|portfolio=fresh", "mwkr_cold", "floor", "cold"])
    a = ap.parse_args()
    root = Path(a.root)
    df = load(root)
    out = summarize(df, a.baselines)
    (root / "analysis.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out["integrity"]))
    ref = a.baselines[0]
    print(f"\nstream mean PI (steps 1..T), n streams = {df.stream.nunique()}; vs {ref} "
          f"[exploratory, uncorrected]")
    rows = sorted(out["methods"].items(), key=lambda kv: kv[1]["mean_pi"])
    for m, r in rows:
        c = r["vs"].get(ref, {})
        extra = ""
        if "local_improved_rate" in r:
            extra = f" local_impr={r['local_improved_rate']:.2f} nbh={r['neighbourhood_frac']:.2f}"
        rel = f"{100 * c['rel_diff']:+6.1f}% W/L={c['stream_wins']}/{c['stream_losses']} p={c['sign_p']:.2g}" if c else ""
        print(f"  {m:58s} PI={r['mean_pi']:.4f} early={r['pi_early']:.3f} gapB={r['gap_B']:.4f} "
              f"t1={r['t_first']:.3f} {rel}{extra}")
    print("\nmean PI by delta kind:")
    bd = pd.DataFrame(out["by_delta"]).T
    keep = [m for m, _ in rows[:8]] + [b for b in a.baselines if b in bd.columns]
    print(bd[list(dict.fromkeys(keep))].round(4).to_string())


if __name__ == "__main__":
    main()
