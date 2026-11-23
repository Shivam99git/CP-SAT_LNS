"""Third, code-disjoint recomputation of the CP-SAT confirmatory comparisons
(multisolver phase, Task 1.3). Reads only the raw run files and
FROZEN_CONFIG.json; imports nothing from phase0/analyze_* or
scripts/final/*. Manuscript numbers are NOT inputs: the script computes
everything from the raw events, and only afterwards diffs against the
archived analysis file to report agreement.

PI definition (as pre-registered): g(t) = 1 before the first incumbent,
(z(t) - z*)/z* afterwards, z* = best validated final objective for the
physical instance (stream, step) over every method and solver seed in the
setting; PI = (1/B) * integral_0^B g. Events after B are ignored. Unit of
inference = stream: PI is averaged over steps 1..10 and solver seeds first.

    .venv/bin/python scripts/multisolver/reproduce_cpsat_confirmatory.py
"""
import glob
import json
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "results/unified_icaps/confirmatory"
OUT = ROOT / "results/multisolver/audit/cpsat_reproduction.json"


def primal_integral(events, z_star, budget):
    t_prev, g_prev, area = 0.0, 1.0, 0.0
    for t, obj in sorted((e[0], e[1]) for e in events):
        if t >= budget:
            break
        area += g_prev * (t - t_prev)
        t_prev, g_prev = t, (obj - z_star) / z_star
    area += g_prev * (budget - t_prev)
    return area / budget


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(lo + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def bootstrap_ci(diffs, denom, reps=10000, seed=12345):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(reps))
    return [100 * means[int(0.025 * reps)] / denom, 100 * means[int(0.975 * reps) - 1] / denom]


def main():
    frozen = json.loads((CONF / "FROZEN_CONFIG.json").read_text())
    archived = json.loads((CONF / "confirmatory_analysis.json").read_text())
    roles = frozen["roles"]
    inv = {v: k for k, v in roles.items()}
    report = {"settings": {}, "record_counts": {}}
    total_records = 0
    for setting, scfg in frozen["settings"].items():
        budget = float(scfg["budget"])
        recs = []
        n_invalid = 0
        for f in glob.glob(str(CONF / setting / "runs" / "*.jsonl")):
            for line in open(f):
                r = json.loads(line)
                recs.append(r)
                if not r.get("validated") or r.get("objective") is None:
                    n_invalid += 1
        total_records += len(recs)
        unit_key = "stream"
        z_star = {}
        for r in recs:
            k = (r[unit_key], r["step"])
            if r.get("objective") is not None:
                z_star[k] = min(z_star.get(k, 10 ** 12), r["objective"])
        per_unit = defaultdict(lambda: defaultdict(list))
        for r in recs:
            if r["step"] == 0:
                continue
            role = inv.get(r["method"])
            if role is None:
                continue
            pi = primal_integral(r["events"], z_star[(r[unit_key], r["step"])], budget)
            per_unit[role][r[unit_key]].append(pi)
        unit_mean = {role: {u: sum(v) / len(v) for u, v in d.items()} for role, d in per_unit.items()}
        comps = {}
        for key in archived["settings"][setting]["comparisons"]:
            a, b = key.split(" vs ")
            units = sorted(set(unit_mean[a]) & set(unit_mean[b]))
            da = [unit_mean[a][u] for u in units]
            db = [unit_mean[b][u] for u in units]
            ma, mb = sum(da) / len(da), sum(db) / len(db)
            diffs = [x - y for x, y in zip(da, db)]
            w = sum(d < 0 for d in diffs)
            l = sum(d > 0 for d in diffs)
            comps[key] = {"n_units": len(units), "mean_a": ma, "mean_b": mb, "rel_diff_pct": 100 * (ma - mb) / mb,
                          "wins": w, "losses": l, "sign_p": binom_two_sided(w, w + l),
                          "ci95_rel_pct": bootstrap_ci(diffs, mb)}
        adj = holm([c["sign_p"] for c in comps.values()])
        for c, p in zip(comps.values(), adj):
            c["holm_p"] = p
        agree = []
        for key, c in comps.items():
            arc = archived["settings"][setting]["comparisons"][key]["pi"]
            agree.append({
                "comparison": key,
                "rel_diff_abs_err_pct": abs(c["rel_diff_pct"] - 100 * arc["rel_diff"]),
                "wl_match": (c["wins"], c["losses"]) == (arc["stream_wins"], arc["stream_losses"]),
                "holm_abs_err": abs(c["holm_p"] - arc["sign_p_holm"]),
            })
        report["settings"][setting] = {"n_records": len(recs), "n_invalid_or_unsolved": n_invalid,
                                       "comparisons": comps, "agreement_with_archived": agree}
    report["record_counts"]["top_level_run_records"] = total_records
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    worst = max(a["rel_diff_abs_err_pct"] for s in report["settings"].values() for a in s["agreement_with_archived"])
    wl_bad = sum(not a["wl_match"] for s in report["settings"].values() for a in s["agreement_with_archived"])
    holm_worst = max(a["holm_abs_err"] for s in report["settings"].values() for a in s["agreement_with_archived"])
    n_comp = sum(len(s["comparisons"]) for s in report["settings"].values())
    print(f"top-level run records: {total_records}; comparisons: {n_comp}")
    print(f"max |rel-diff error| vs archived: {worst:.2e} pct-points; W/L mismatches: {wl_bad}; max |Holm error|: {holm_worst:.2e}")
    for s, d in report["settings"].items():
        for k, c in d["comparisons"].items():
            print(f"  {s:14s} {k:28s} {c['rel_diff_pct']:+7.2f}%  {c['wins']}/{c['losses']}  holm={c['holm_p']:.2g}  "
                  f"CI=[{c['ci95_rel_pct'][0]:+.1f},{c['ci95_rel_pct'][1]:+.1f}]")


if __name__ == "__main__":
    main()
