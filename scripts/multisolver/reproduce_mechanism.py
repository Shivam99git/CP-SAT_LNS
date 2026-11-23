"""Recompute, from raw U1/U2 records, the M1-vs-M2 mechanism quantities the
manuscript previously transcribed from docs/final_icaps/03_critical_vs_timewindow.md
(Task 2.3): per-disruption-type M2 critical-vs-time-window comparisons WITH
stream-clustered bootstrap CIs, completed-round counts under M1 and M2, and
the restricted-round solver time and status mix under M2 -- i.e. what the M2
protocol actually equalizes and what it does not. Exploratory (not in the
pre-registered family); reported with uncorrected sign tests.

    .venv/bin/python scripts/multisolver/reproduce_mechanism.py
"""
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_cpsat_confirmatory import binom_two_sided, bootstrap_ci, primal_integral  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "results/unified_icaps/confirmatory"
OUT = ROOT / "results/multisolver/audit/mechanism_reproduction.json"


def load(setting):
    recs = []
    for f in glob.glob(str(CONF / setting / "runs" / "*.jsonl")):
        recs += [json.loads(l) for l in open(f)]
    return recs


def main():
    roles = json.loads((CONF / "FROZEN_CONFIG.json").read_text())["roles"]
    inv = {v: k for k, v in roles.items()}
    out = {}
    # ---- M2 by delta kind (U2) ----
    u2 = load("U2_mechanism")
    zs = {}
    for r in u2:
        k = (r["stream"], r["step"])
        zs[k] = min(zs.get(k, 1e12), r["objective"])
    per = defaultdict(lambda: defaultdict(list))   # (role, kind) -> stream -> [pi]
    for r in u2:
        if r["step"] == 0:
            continue
        role = inv[r["method"]]
        pi = primal_integral(r["events"], zs[(r["stream"], r["step"])], 8.0)
        per[(role, r["delta_kind"])][r["stream"]].append(pi)
        per[(role, "all")][r["stream"]].append(pi)
    comp = {}
    for kind in ("all", "arrival", "cancellation", "duration_jitter", "outage"):
        a = {s: sum(v) / len(v) for s, v in per[("M2_crit", kind)].items()}
        b = {s: sum(v) / len(v) for s, v in per[("M2_timewin", kind)].items()}
        units = sorted(set(a) & set(b))
        da, db = [a[u] for u in units], [b[u] for u in units]
        ma, mb = sum(da) / len(da), sum(db) / len(db)
        diffs = [x - y for x, y in zip(da, db)]
        w, l = sum(d < 0 for d in diffs), sum(d > 0 for d in diffs)
        comp[kind] = {"n_streams": len(units), "rel_diff_pct": 100 * (ma - mb) / mb, "crit_wins": w, "crit_losses": l,
                      "sign_p_uncorrected": binom_two_sided(w, w + l), "ci95_rel_pct": bootstrap_ci(diffs, mb)}
    out["M2_crit_vs_timewin_by_delta"] = comp
    # ---- what M2 equalizes: completed rounds, round solver time, status mix ----
    def round_stats(recs, role_names):
        st = defaultdict(lambda: {"instances": 0, "rounds": 0, "round_solver_s": 0.0, "status": defaultdict(int),
                                  "by_kind_rounds": defaultdict(lambda: [0, 0]), "improved": 0,
                                  "global_time_s": 0.0, "local_window_s": 0.0,
                                  "released": 0, "crit_in_N": 0})
        for r in recs:
            role = inv.get(r["method"])
            if role not in role_names or r["step"] == 0:
                continue
            m = r["meta"]
            rounds = [x for x in m.get("rounds", []) if not x.get("empty")]
            s = st[role]
            s["instances"] += 1
            s["rounds"] += len(rounds)
            s["improved"] += sum(1 for x in rounds if x.get("improved"))
            s["round_solver_s"] += sum(x.get("solver_s", 0.0) for x in rounds)
            s["global_time_s"] += m.get("global", {}).get("time_s", 0.0)
            s["local_window_s"] += m.get("local_window_s", 0.0)
            for x in rounds:
                s["status"][x.get("status")] += 1
                s["released"] += x.get("n_released_ops", 0)
                s["crit_in_N"] += x.get("critical_in_N", 0)
            bk = s["by_kind_rounds"][r["delta_kind"]]
            bk[0] += 1; bk[1] += len(rounds)
        res = {}
        for role, s in st.items():
            n = s["instances"]
            res[role] = {"mean_completed_rounds": s["rounds"] / n,
                         "round_improvement_rate": s["improved"] / max(1, s["rounds"]),
                         "mean_round_solver_s": s["round_solver_s"] / max(1, s["rounds"]),
                         "mean_restricted_solver_s_per_instance": s["round_solver_s"] / n,
                         "mean_global_time_s": s["global_time_s"] / n,
                         "mean_local_window_s": s["local_window_s"] / n,
                         "round_status": dict(s["status"]),
                         "mean_released_ops": s["released"] / max(1, s["rounds"]),
                         "mean_critical_in_N": s["crit_in_N"] / max(1, s["rounds"]),
                         "n_rounds": s["rounds"],
                         "mean_rounds_by_delta": {k: v[1] / v[0] for k, v in s["by_kind_rounds"].items()}}
        return res
    out["M1_round_stats_U1"] = round_stats(load("U1_primary"), {"B2_crit", "B3_timewin", "B1_random", "B4_prec"})
    out["M2_round_stats_U2"] = round_stats(u2, {"M2_crit", "M2_timewin", "M2_random", "M2_prec"})
    # restricted-solve status semantics across ALL confirmatory settings (initial stage + rounds)
    st = defaultdict(int)
    for f in glob.glob(str(CONF / "*" / "runs" / "*.jsonl")):
        for line in open(f):
            m = json.loads(line).get("meta") or {}
            stages = ([m["initial_stage"]] if "initial_stage" in m else []) + \
                     [x for x in m.get("rounds", []) if not x.get("empty")]
            for x in stages:
                st[str(x.get("status")).lower()] += 1
    st["total"] = sum(st.values())
    (OUT.parent / "restricted_status_counts.json").write_text(json.dumps(dict(st), indent=1))
    out["restricted_status_counts"] = dict(st)
    OUT.write_text(json.dumps(out, indent=1))
    for k, c in comp.items():
        print(f"M2 crit vs tw [{k:16s}] {c['rel_diff_pct']:+6.1f}%  {c['crit_wins']}/{c['crit_losses']}  "
              f"p={c['sign_p_uncorrected']:.3g}  CI=[{c['ci95_rel_pct'][0]:+.1f},{c['ci95_rel_pct'][1]:+.1f}]  n={c['n_streams']}")
    for prot in ("M1_round_stats_U1", "M2_round_stats_U2"):
        for role, s in sorted(out[prot].items()):
            print(f"{prot} {role:11s} rounds={s['mean_completed_rounds']:.2f} impr={s['round_improvement_rate']:.3f} "
                  f"round_solver={s['mean_round_solver_s']:.3f}s restricted/inst={s['mean_restricted_solver_s_per_instance']:.2f}s "
                  f"global={s['mean_global_time_s']:.2f}s by_delta={ {k: round(v, 2) for k, v in s['mean_rounds_by_delta'].items()} }")


if __name__ == "__main__":
    main()
