"""Analysis of the Gate 1 campaign (phase0/run_gate1.py). Endpoints and the
comparison family below were fixed before any Gate 1 result was inspected;
see docs/research_extension/04_experimental_methodology.md.

Unit of inference: the physical stream. Solver seeds and stream steps are
averaged within a stream first; they are never treated as independent.

Per run, from the saved trajectory and a shared reference z* (best objective
any run of any method, protocol or seed found on that physical instance):
  pi         archived primal integral: gap g = (z - z*)/z*, g = 1 before the
             first incumbent, uncapped, averaged over [0, B]
  pi_capped  same with g capped at 1 (sensitivity)
  pi_early   over [0, B/8];  pi_late over [B/8, B]
  gap_B      gap of the best incumbent found by time B (incumbents reported
             after the deadline because of solver overshoot are ignored)
  t_first    time of the first validated/solver incumbent
Primary endpoint: stream mean of `pi` over steps 1..T (instances with a
predecessor), Protocol B. Predeclared family (Holm within each protocol):
  floor-cold, floor-spt_cold, floor-mwkr_cold, hint-cold, floor_hint-floor,
  repaired_hint_only-floor, spt_cold-cold, mwkr_cold-cold
Each comparison reports the mean stream difference (negative = first method
better), its relative size, a stream-clustered bootstrap 95% CI, and an exact
sign test over streams.

    .venv/bin/python -m phase0.analyze_gate1 results/research_extension/gate1_historical_reuse
"""

from __future__ import annotations

import glob
import json
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

FAMILY = [("floor", "cold"), ("floor", "spt_cold"), ("floor", "mwkr_cold"), ("hint", "cold"),
          ("floor_hint", "floor"), ("repaired_hint_only", "floor"), ("spt_cold", "cold"),
          ("mwkr_cold", "cold")]
HISTORY_INDEPENDENT = ("cold", "spt_cold", "mwkr_cold")
METRICS = ["pi", "pi_capped", "pi_early", "pi_late", "gap_B", "t_first"]


def integrate_gap(events, zstar, budget, lo, hi, cap=False) -> float:
    """Mean of the step-function gap over [lo, hi]."""
    area, t_prev, g = 0.0, 0.0, 1.0
    for t, obj, _src in sorted(events):
        t = min(max(t, 0.0), budget)
        a, b = max(t_prev, lo), min(t, hi)
        if b > a:
            area += g * (b - a)
        t_prev = t
        g = (obj - zstar) / zstar
        g = min(g, 1.0) if cap else g
    a, b = max(t_prev, lo), hi
    if b > a:
        area += g * (b - a)
    return area / (hi - lo)


def per_run(r: dict, zstar: float) -> dict:
    B = r["budget"]
    ev = r["events"]
    in_budget = [e for e in ev if e[0] <= B]
    gap_B = (min(e[1] for e in in_budget) - zstar) / zstar if in_budget else np.nan
    return {"pi": integrate_gap(ev, zstar, B, 0, B),
            "pi_capped": integrate_gap(ev, zstar, B, 0, B, cap=True),
            "pi_early": integrate_gap(ev, zstar, B, 0, B / 8),
            "pi_late": integrate_gap(ev, zstar, B, B / 8, B),
            "gap_B": gap_B, "t_first": ev[0][0] if ev else np.nan}


def sign_test(w: int, l: int) -> float:
    n = w + l
    if n == 0:
        return 1.0
    k = max(w, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (len(items) - i) * p))
        out[k] = running
    return out


def cluster_bootstrap(diffs: np.ndarray, n_boot=10000, seed=0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diffs), size=(n_boot, len(diffs)))
    means = diffs[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def load(root: Path) -> pd.DataFrame:
    recs = [json.loads(l) for f in sorted(glob.glob(str(root / "runs" / "*.jsonl")))
            + sorted(glob.glob(str(root / "reference" / "*.jsonl"))) for l in open(f)]
    df = pd.DataFrame(recs)
    df["inst_key"] = df["stream"] + "|" + df["step"].astype(str)
    zstar = df[df.objective.notna()].groupby("inst_key").objective.min()
    metrics = [per_run(r, zstar[r["inst_key"]]) if r["inst_key"] in zstar.index else
               {m: np.nan for m in METRICS} for r in df.to_dict("records")]
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(metrics)], axis=1)


def stream_table(df: pd.DataFrame, protocol: str, metric: str, steps_from: int = 1,
                 delta: str | None = None) -> pd.DataFrame:
    """stream x method table of the metric's mean over seeds and steps."""
    d = df[(df.step >= steps_from)]
    if delta is not None:
        d = d[d.delta_kind == delta]
    hist = d[(d.protocol == protocol)]
    indep = d[(d.protocol == "B") & d.method.isin(HISTORY_INDEPENDENT)]
    d = pd.concat([hist[~hist.method.isin(HISTORY_INDEPENDENT)], indep]) if protocol == "A" else hist
    return d.groupby(["stream", "method"])[metric].mean().unstack("method")


def compare(tab: pd.DataFrame, a: str, b: str) -> dict:
    if a not in tab or b not in tab:
        return {}
    pair = tab[[a, b]].dropna()
    diff = (pair[a] - pair[b]).to_numpy()
    w, l = int((diff < 0).sum()), int((diff > 0).sum())
    lo, hi = cluster_bootstrap(diff) if len(diff) > 1 else (np.nan, np.nan)
    base = pair[b].mean()
    return {"n_streams": len(diff), "mean_a": float(pair[a].mean()), "mean_b": float(base),
            "mean_diff": float(diff.mean()), "rel_diff": float(diff.mean() / base) if base else np.nan,
            "ci95": [lo, hi], "stream_wins": w, "stream_losses": l, "stream_ties": len(diff) - w - l,
            "sign_p": sign_test(w, l)}


def analyze(root: Path) -> dict:
    df = load(root)
    runs = df[df.protocol != "REF"]
    out = {"n_records": int(len(runs)), "n_ref_records": int((df.protocol == "REF").sum()),
           "n_streams": int(runs.stream.nunique()),
           "solver_seeds": sorted(int(s) for s in runs.solver_seed.unique()),
           "integrity": {
               "not_validated": int((~runs.validated.astype(bool)).sum()),
               "no_solution": int(runs.objective.isna().sum()),
               "overrun_runs": int((runs.overrun_s > 0).sum()),
               "overrun_max_s": float(runs.overrun_s.max()),
               "overrun_p99_s": float(runs.overrun_s.quantile(0.99)),
               "notes": runs.notes.map(len).sum().item(),
               "solver_status": runs.solver_status.value_counts().to_dict()}}
    for proto in ("B", "A"):
        if not (runs.protocol == proto).any():
            continue
        res = {}
        for metric in METRICS:
            tab = stream_table(runs, proto, metric)
            res[metric] = {"means": tab.mean().to_dict(),
                           "comparisons": {f"{a}-{b}": compare(tab, a, b) for a, b in FAMILY}}
        prim = res["pi"]["comparisons"]
        h = holm({k: v["sign_p"] for k, v in prim.items() if v})
        for k in h:
            prim[k]["sign_p_holm"] = h[k]
        res["by_delta"] = {}
        for kind in sorted(runs[runs.step >= 1].delta_kind.unique()):
            tab = stream_table(runs, proto, "pi", delta=kind)
            res["by_delta"][kind] = {"means": tab.mean().to_dict(),
                                     "comparisons": {f"{a}-{b}": compare(tab, a, b) for a, b in FAMILY[:3]}}
        res["by_size"] = {}
        for size in sorted(runs["size"].unique()):
            tab = stream_table(runs[runs["size"] == size], proto, "pi")
            res["by_size"][size] = {"means": tab.mean().to_dict(),
                                    "comparisons": {f"{a}-{b}": compare(tab, a, b) for a, b in FAMILY[:3]}}
        out[f"protocol_{proto}"] = res
    # initial incumbent quality: repaired floor vs fresh schedules (Protocol B)
    b = runs[(runs.protocol == "B") & (runs.step >= 1)]
    zs = df[df.objective.notna()].groupby("inst_key").objective.min()
    init = b[b.construction_objective.notna()].copy()
    init["init_gap"] = (init.construction_objective - init.inst_key.map(zs)) / init.inst_key.map(zs)
    out["initial_incumbent_gap_median"] = init.groupby(["method", "delta_kind"]).init_gap.median().unstack().to_dict()
    return out


def main() -> None:
    root = Path(sys.argv[1])
    out = analyze(root)
    dest = root / "analysis.json"
    dest.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out["integrity"], indent=1))
    for proto in ("B", "A"):
        key = f"protocol_{proto}"
        if key not in out:
            continue
        print(f"\nProtocol {proto}: primary endpoint (stream mean PI, steps 1..T)")
        for name, c in out[key]["pi"]["comparisons"].items():
            if c:
                print(f"  {name:28s} n={c['n_streams']:2d} {c['mean_a']:.4f} vs {c['mean_b']:.4f} "
                      f"rel={100 * c['rel_diff']:+6.1f}% CI=[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] "
                      f"W/L={c['stream_wins']}/{c['stream_losses']} p={c['sign_p']:.2g} "
                      f"holm={c.get('sign_p_holm', float('nan')):.2g}")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
