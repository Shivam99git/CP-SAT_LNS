"""Statistical analysis of multisolver runs (Task 9).

    .venv_ms/bin/python scripts/multisolver/analyze_results.py --runs results/multisolver/runs \
        --phase heldout --out results/multisolver/analysis/heldout.json

Metric definitions
  z*(I)   best validated makespan for physical instance I (keyed by instance
          hash) over EVERY record of the phase -- all solvers, methods,
          budgets, worker counts. A best-known value, not a proven optimum.
  PI      (1/B) * integral_0^B g(t) dt, g = 1 before the first validated
          incumbent, (z(t) - z*)/z* afterwards; events after B ignored. For
          final-only backends (CBC, GLPK) the trajectory is the one the
          pipeline can OBSERVE (the incumbent becomes usable when the call
          returns); this is stated wherever such numbers are shown.
  unit    stream: PI etc. are averaged over steps and solver seeds within a
          stream before any comparison (steps and seeds are not independent).
Every failure (NO_SOLUTION, INVALID, ERROR, LICENSE_LIMIT inside a stage)
stays in the data: a run without any validated incumbent has PI = 1.
"""
import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def pi_of(events, z, budget, bounded=True):
    """bounded=True: Berthold's primal gap (z(t) - z*)/z(t) in [0, 1) -- the multisolver
    primary metric (fixed on development data: with cold starts of some engines the first
    incumbent can exceed 2 z*, and the uncapped gap (z(t) - z*)/z* then scores a poor
    feasible schedule WORSE than no schedule, g = 1). bounded=False: the uncapped gap of
    the CP-SAT confirmatory study, reported as secondary for continuity."""
    t_prev, g_prev, area = 0.0, 1.0, 0.0
    for t, obj, *_ in sorted(events, key=lambda e: e[0]):
        if t >= budget:
            break
        area += g_prev * (t - t_prev)
        t_prev, g_prev = t, ((obj - z) / obj if bounded else (obj - z) / z)
    return (area + g_prev * (budget - t_prev)) / budget


def sign_p(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def boot_ci(diffs, denom, reps=10000, seed=7):
    if not diffs or denom == 0:
        return [None, None]
    rng = random.Random(seed)
    n = len(diffs)
    ms = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(reps))
    return [100 * ms[int(0.025 * reps)] / denom, 100 * ms[int(0.975 * reps) - 1] / denom]


def load(runs_dir: Path, phase_streams: set | None):
    recs = []
    for f in runs_dir.rglob("*.jsonl"):
        for line in open(f):
            r = json.loads(line)
            if phase_streams is not None and r.get("stream") not in phase_streams:
                continue
            recs.append(r)
    return recs


def config_key(r):
    return (r["experiment"], r["tier"], r["solver"], r["method"], r["budget"], r["workers"])


def summarize(recs):
    """Per-record metrics with the common z*; per-config aggregate tables."""
    z = {}
    for r in recs:
        if r.get("status") == "OK" and r.get("objective") is not None:
            h = r["instance_hash"]
            z[h] = min(z.get(h, 10 ** 12), r["objective"])
    rows = []
    for r in recs:
        if r.get("status") == "NOT_SUPPORTED":
            continue
        h = r.get("instance_hash")
        if h not in z:
            continue
        ok = r.get("status") == "OK"
        # only incumbents available by the deadline count (late returns of solvers that
        # overshoot their own time limit get no credit, exactly as in the PI definition)
        ev = [e for e in r.get("events", []) if e[0] <= r["budget"]] if ok else []
        pi = pi_of(ev, z[h], r["budget"])
        pi_unc = pi_of(ev, z[h], r["budget"], bounded=False)
        obj_at_b = ev[-1][1] if ev else None
        stages = r.get("stages", [])
        licence = any(s.get("status") == "LICENSE_LIMIT" for s in stages)
        last = stages[-1] if stages else {}
        # CPU = this process + waited children; for solver subprocesses that were killed (MiniZinc
        # backends) or still alive at measurement (cpoptimizer) the sampled tree CPU is used instead
        sub = sum(s_.get("subprocess_cpu_s") or 0 for s_ in stages)
        cpu = (r.get("cpu_self_s") or 0) + max(r.get("cpu_children_s") or 0, sub)
        rows.append({
            "key": config_key(r), "stream": r["stream"], "step": r["step"], "seed": r["seed"],
            "delta_kind": r.get("delta_kind"), "n_ops": r.get("n_ops"), "pi": pi, "pi_uncapped": pi_unc,
            "feasible": obj_at_b is not None, "late_only": ok and obj_at_b is None,
            "licence_limited": licence, "error": r.get("status") == "ERROR",
            "final_gap": (obj_at_b - z[h]) / z[h] if obj_at_b is not None else None,
            "t_first": ev[0][0] if ev else None,
            "proven_optimal": bool(last.get("proven_optimal")) and obj_at_b == z[h]
                              and (r.get("overrun_s") or 0) <= 0.05,
            "build_s": sum(s.get("build_s") or 0 for s in stages),
            "solve_s": sum(s.get("solve_s") or 0 for s in stages),
            "construction_s": r.get("construction_s") or 0, "total_s": r.get("total_s") or r.get("wall_s"),
            "overrun_s": r.get("overrun_s") or 0, "cpu_s": cpu, "wall_s": r.get("wall_s"),
            "cpu_per_wall": cpu / r["wall_s"] if r.get("wall_s") else None,
            "rss_mb": max(r.get("peak_rss_mb_self") or 0, r.get("peak_rss_mb_children") or 0),
            "vars": max([s.get("vars") or 0 for s in stages] or [0]),
            "binary": max([s.get("binary") or 0 for s in stages] or [0]),
            "constraints": max([s.get("constraints") or 0 for s in stages] or [0]),
            "loadavg": r.get("loadavg_1m"),
        })
    return rows, z


def _units(rs, field):
    u = defaultdict(list)
    for r in rs:
        u[r["stream"]].append(r[field])
    return u


def agg(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["key"]].append(r)
    table = {}
    for k, rs in by.items():
        unit = defaultdict(list)
        for r in rs:
            unit[r["stream"]].append(r["pi"])
        unit_means = [sum(v) / len(v) for v in unit.values()]
        fin = [r["final_gap"] for r in rs if r["final_gap"] is not None]
        tf = [r["t_first"] for r in rs if r["t_first"] is not None]
        mean = lambda xs: sum(xs) / len(xs) if xs else None
        table["|".join(map(str, k))] = {
            "experiment": k[0], "tier": k[1], "solver": k[2], "method": k[3], "budget": k[4], "workers": k[5],
            "n_runs": len(rs), "n_streams": len(unit), "mean_pi": mean(unit_means),
            "mean_pi_uncapped": mean([sum(v) / len(v) for v in _units(rs, "pi_uncapped").values()]),
            "median_pi": statistics.median([r["pi"] for r in rs]),
            "mean_final_gap": mean(fin), "feasible_rate": sum(r["feasible"] for r in rs) / len(rs),
            "late_only_rate": sum(r["late_only"] for r in rs) / len(rs),
            "licence_limited_rate": sum(r["licence_limited"] for r in rs) / len(rs),
            "error_rate": sum(r["error"] for r in rs) / len(rs),
            "proven_optimal_rate": sum(r["proven_optimal"] for r in rs) / len(rs),
            "mean_t_first": mean(tf), "mean_build_s": mean([r["build_s"] for r in rs]),
            "mean_solve_s": mean([r["solve_s"] for r in rs]), "mean_total_s": mean([r["total_s"] or 0 for r in rs]),
            "max_overrun_s": max(r["overrun_s"] for r in rs), "overrun_rate_50ms": sum(r["overrun_s"] > 0.05 for r in rs) / len(rs),
            "mean_cpu_s": mean([r["cpu_s"] for r in rs]),
            "mean_cpu_per_wall": mean([r["cpu_per_wall"] for r in rs if r["cpu_per_wall"] is not None]),
            "max_rss_mb": max(r["rss_mb"] for r in rs), "mean_vars": mean([r["vars"] for r in rs]),
            "mean_binary": mean([r["binary"] for r in rs]), "mean_constraints": mean([r["constraints"] for r in rs]),
            "mean_loadavg": mean([r["loadavg"] for r in rs if r["loadavg"] is not None]),
        }
    return table


def compare(rows, key_a, key_b):
    """Paired over streams (each stream's mean over common (step, seed) pairs)."""
    a = {(r["stream"], r["step"], r["seed"]): r["pi"] for r in rows if r["key"] == key_a}
    b = {(r["stream"], r["step"], r["seed"]): r["pi"] for r in rows if r["key"] == key_b}
    # seeds may differ between configs (deterministic engines run seed 0 only): pair on (stream, step)
    # after averaging seeds within each config
    def by_step(d):
        acc = defaultdict(list)
        for (s, st, _), v in d.items():
            acc[(s, st)].append(v)
        return {k: sum(v) / len(v) for k, v in acc.items()}
    a, b = by_step(a), by_step(b)
    common = sorted(set(a) & set(b))
    if not common:
        return None
    ua, ub = defaultdict(list), defaultdict(list)
    for k in common:
        ua[k[0]].append(a[k]); ub[k[0]].append(b[k])
    units = sorted(ua)
    da = [sum(ua[u]) / len(ua[u]) for u in units]
    db = [sum(ub[u]) / len(ub[u]) for u in units]
    ma, mb = sum(da) / len(da), sum(db) / len(db)
    diffs = [x - y for x, y in zip(da, db)]
    w, l = sum(d < -1e-12 for d in diffs), sum(d > 1e-12 for d in diffs)
    return {"a": "|".join(map(str, key_a)), "b": "|".join(map(str, key_b)), "n_streams": len(units),
            "n_paired_steps": len(common), "mean_a": ma, "mean_b": mb,
            "rel_diff_pct": 100 * (ma - mb) / mb if mb else None, "wins_a": w, "losses_a": l,
            "ties": len(units) - w - l, "sign_p": sign_p(w, l), "ci95_rel_pct": boot_ci(diffs, mb)}


def run_families(rows, families):
    out = {}
    for fam, pairs in families.items():
        res = [c for c in (compare(rows, a, b) for a, b in pairs) if c is not None]
        for c, p in zip(res, holm([c["sign_p"] for c in res])):
            c["holm_p"] = p
            c["significant"] = p < 0.05 and c["ci95_rel_pct"][0] is not None and \
                (c["ci95_rel_pct"][1] < 0 or c["ci95_rel_pct"][0] > 0)
        out[fam] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results/multisolver/runs"))
    ap.add_argument("--phase", choices=["dev", "heldout"], required=True)
    ap.add_argument("--plan", default=None, help="frozen plan with comparison families")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    phase_streams = {p.stem for p in (ROOT / "results/multisolver/instances" / a.phase).rglob("*.json")}
    recs = load(Path(a.runs), phase_streams)
    rows, z = summarize(recs)
    table = agg(rows)
    fams = {}
    if a.plan:
        plan = json.loads(Path(a.plan).read_text())
        for fam, pairs in plan.get("families", {}).items():
            fams[fam] = [(tuple(p[0]), tuple(p[1])) for p in pairs]
    comps = run_families(rows, fams)
    status = defaultdict(int)
    for r in recs:
        status[(r["experiment"], r["tier"], r["solver"], r.get("status"))] += 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({
        "phase": a.phase, "n_records": len(recs), "n_instances_with_zstar": len(z),
        "status_counts": {"|".join(map(str, k)): v for k, v in sorted(status.items())},
        "configs": table, "comparisons": comps}, indent=1))
    print(f"{len(recs)} records, {len(z)} physical instances, {len(table)} configurations -> {a.out}")


if __name__ == "__main__":
    main()
