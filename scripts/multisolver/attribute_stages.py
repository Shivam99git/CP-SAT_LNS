"""Post-hoc DESCRIPTIVE stage attribution for S3/S4 (not a frozen comparison family).

Every S3/S4 trajectory event carries its source tag (portfolio:*, initial,
roundN, global). Replaying a run's trajectory with only a prefix of its
stages gives the PI the run would have scored had later stages produced no
improvement (they would still have consumed their time, so this is an exact
counterfactual for "no further incumbent", not for "stage removed and its
time given to the next stage"):

  pi_portfolio  only portfolio events            (engine-independent part)
  pi_pre_global portfolio + initial + rounds     (S4 only)
  pi_full       all events (= the analysed PI)

Reported per (experiment, tier, solver, method, budget, workers), averaged
over runs within stream, then over streams, with the same common z* and
deadline rule as analyze_results.py. Also: share of runs whose final
incumbent came from each stage.

    .venv_ms/bin/python scripts/multisolver/attribute_stages.py --phase heldout \
        --out results/multisolver/analysis/stage_attribution.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_results import ROOT, load, pi_of, summarize  # noqa: E402


def stage_of(tag: str) -> str:
    head = tag.split(":")[0]
    return "round" if head.startswith("round") else head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results/multisolver/runs"))
    ap.add_argument("--phase", choices=["dev", "heldout"], required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    phase_streams = {p.stem for p in (ROOT / "results/multisolver/instances" / a.phase).rglob("*.json")}
    recs = load(Path(a.runs), phase_streams)
    _, z = summarize(recs)
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    final_src = defaultdict(lambda: defaultdict(int))
    for r in recs:
        if r.get("method") not in ("S3", "S4") or r.get("status") != "OK" or r["instance_hash"] not in z:
            continue
        key = "|".join(map(str, (r["experiment"], r["tier"], r["solver"], r["method"], r["budget"], r["workers"])))
        B, zh = r["budget"], z[r["instance_hash"]]
        ev = [e for e in r["events"] if e[0] <= B]
        port = [e for e in ev if stage_of(e[2]) == "portfolio"]
        pre = [e for e in ev if stage_of(e[2]) in ("portfolio", "initial", "round")]
        cell = acc[key][r["stream"]]
        cell["pi_portfolio"].append(pi_of(port, zh, B))
        cell["pi_pre_global"].append(pi_of(pre, zh, B))
        cell["pi_full"].append(pi_of(ev, zh, B))
        if ev:
            best = min(e[1] for e in ev)
            first_best = min((e for e in ev if e[1] == best), key=lambda e: e[0])
            final_src[key][stage_of(first_best[2])] += 1
    out = {}
    for key, streams in sorted(acc.items()):
        row = {"n_streams": len(streams)}
        for m in ("pi_portfolio", "pi_pre_global", "pi_full"):
            per = [sum(v[m]) / len(v[m]) for v in streams.values()]
            row[m] = sum(per) / len(per)
        tot = sum(final_src[key].values())
        row["final_incumbent_source"] = {k: v / tot for k, v in sorted(final_src[key].items())}
        row["engine_share_of_pi_reduction"] = None if row["pi_portfolio"] == 0 else \
            (row["pi_portfolio"] - row["pi_full"]) / row["pi_portfolio"]
        out[key] = row
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"phase": a.phase, "post_hoc_descriptive": True, "configs": out}, indent=1))
    print(f"{len(out)} configurations -> {a.out}")


if __name__ == "__main__":
    main()
