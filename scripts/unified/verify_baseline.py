"""Independent re-verification of archived campaigns (unified ICAPS study,
docs/unified_icaps/01_baseline_verification.md).

Shares no code with the run or analysis pipeline: its own instance reader,
feasibility checker, primal-integral integrator, sign test, Holm correction
and bootstrap. For each setting directory it checks
  1. solver invocations (from the run metadata),
  2. physical-instance identifiers and completeness of the method x seed grid,
  3. feasibility of every final schedule (own checker),
  4. objective == own makespan == last trajectory value,
  5. predecessor policy (prev_source, has_prev),
  6. budgets and deadline overruns per method,
  7. primal integrals recomputed from trajectories, compared with the archived
     stream-level analysis (means, relative differences, W/L, Holm p, CI),
  8. solver seed / stream separation,
  9. Holm adjustment recomputed,
 10. clustering of published-benchmark streams by base instance.

    .venv/bin/python scripts/unified/verify_baseline.py
"""
import collections
import glob
import hashlib
import json
import re
import sys
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------ independent pieces

def load_instances(d):
    out = {}
    for f in glob.glob(str(d / "instances" / "*.json")):
        out[Path(f).stem] = json.load(open(f))
    return out


def own_check(inst, sol):
    """Independent feasibility check; returns the makespan or raises ValueError."""
    ops, rel = {}, {}
    for j in inst["jobs"]:
        for k, (oid, m, p) in enumerate(j["ops"]):
            ops[oid] = (m, p, j["job_id"], k)
        rel[j["job_id"]] = j["release_date"]
    if set(sol) != set(ops):
        raise ValueError("operation set mismatch")
    for v, s in sol.items():
        if not isinstance(s, int) or s < 0:
            raise ValueError(f"bad start {v}")
    for j in inst["jobs"]:
        seq = j["ops"]
        if seq and sol[seq[0][0]] < j["release_date"]:
            raise ValueError("release")
        for a, b in zip(seq, seq[1:]):
            if sol[b[0]] < sol[a[0]] + a[2]:
                raise ValueError("precedence")
    for v, f in (inst.get("frozen_starts") or {}).items():
        if sol[v] != f:
            raise ValueError("commitment")
    by_m = collections.defaultdict(list)
    for v, (m, p, _, _) in ops.items():
        if p > 0:
            by_m[m].append((sol[v], sol[v] + p))
    for m, a, b in inst["outages"]:
        by_m[m].append((a, b))
    for m, iv in by_m.items():
        iv.sort()
        for (s1, e1), (s2, e2) in zip(iv, iv[1:]):
            if s2 < e1:
                raise ValueError(f"overlap on machine {m}")
    return max(sol[v] + p for v, (m, p, _, _) in ops.items())


def own_pi(events, z, B):
    area, t_prev, g = 0.0, 0.0, 1.0
    for t, obj, _ in sorted(events, key=lambda e: e[0]):
        t = min(max(t, 0.0), B)
        area += g * (t - t_prev)
        t_prev, g = t, (obj - z) / z
    area += g * (B - t_prev)
    return area / B


def own_sign_p(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = max(w, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def own_holm(ps):
    order = sorted(ps, key=ps.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * ps[k]))
        out[k] = run
    return out


def own_ci(d, seed=12345, n=10000):
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


# ------------------------------------------------------------ verification

def verify(d: Path, roles: dict, family: list[tuple[str, str]], archived: dict | None):
    insts = load_instances(d)
    recs = [json.loads(l) for f in sorted(glob.glob(str(d / "runs" / "*.jsonl"))) for l in open(f)]
    rep = {"setting": d.name, "records": len(recs)}
    # 1. solver invocations
    calls = 0
    for r in recs:
        mt = r.get("meta") or {}
        if r["method"].startswith(("iaip|", "cobar|")):
            calls += ("local" in mt) + len(mt.get("rounds", [])) + (r["solver_status"] not in ("CERTIFIED_OPTIMAL",)
                                                                     and "global" in mt or r["method"].startswith("iaip|"))
        else:
            calls += 1
    rep["solver_invocations"] = calls
    # 2. identifiers and grid
    grid = collections.defaultdict(set)
    for r in recs:
        grid[(r["stream"], r["step"])].add((r["method"], r["solver_seed"]))
    sizes = collections.Counter(len(v) for v in grid.values())
    rep["physical_instances"] = len(grid)
    rep["grid_complete"] = len(sizes) == 1
    rep["missing_instance_file"] = sum(1 for (s, _) in grid if s not in insts)
    # 3./4. feasibility and objectives
    bad, mism, lastmis = [], 0, 0
    for r in recs:
        inst = insts[r["stream"]][r["step"]]
        try:
            mk = own_check(inst, r["solution"])
        except ValueError as e:
            bad.append((r["stream"], r["step"], r["method"], str(e)))
            continue
        mism += mk != r["objective"]
        lastmis += r["events"][-1][1] != r["objective"]
    rep["infeasible_final_schedules"] = len(bad)
    rep["objective_vs_own_makespan_mismatch"] = mism
    rep["last_event_vs_objective_mismatch"] = lastmis
    # 5. predecessor policy
    rep["prev_source"] = dict(collections.Counter(r["prev_source"] for r in recs))
    rep["has_prev_ok"] = all(r["has_prev"] == (r["step"] >= 1) for r in recs)
    # 6. budgets
    rep["budgets"] = sorted({r["budget"] for r in recs})
    ov = collections.defaultdict(list)
    for r in recs:
        ov[r["method"]].append(r["overrun_s"])
    rep["overrun_by_method_ms"] = {m[:60]: [round(1000 * float(np.mean(v)), 2), round(1000 * float(np.max(v)), 1)]
                                   for m, v in ov.items()}
    rep["workers"] = sorted({r["workers"] for r in recs})
    # 8. seeds vs streams
    tasks = collections.Counter((r["stream"], r["solver_seed"], r["method"], r["step"]) for r in recs)
    rep["duplicate_run_keys"] = sum(1 for v in tasks.values() if v > 1)
    rep["solver_seeds"] = sorted({r["solver_seed"] for r in recs})
    rep["n_streams"] = len({r["stream"] for r in recs})
    # 7. PI
    z = {}
    late_best = 0
    for r in recs:
        k = (r["stream"], r["step"])
        z[k] = min(z.get(k, 10 ** 12), r["objective"])
    for k in z:
        inb = min((e[1] for r in recs if (r["stream"], r["step"]) == k for e in r["events"] if e[0] <= r["budget"]), default=None) \
            if False else None
    pis = collections.defaultdict(list)
    for r in recs:
        if r["step"] >= 1:
            pis[(r["stream"], r["method"])].append(own_pi(r["events"], z[(r["stream"], r["step"])], r["budget"]))
    tab = {k: float(np.mean(v)) for k, v in pis.items()}
    streams = sorted({s for s, _ in tab})
    unit_of = (lambda s: re.sub(r"_s\d+.*$", "", s)) if not all(re.match(r"^\d+x\d+_s\d+", s) for s in streams) else (lambda s: s)
    units = sorted({unit_of(s) for s in streams})
    rep["units"] = len(units)
    rep["unit_kind"] = "base instance" if units != streams else "stream"

    def unit_vec(m):
        return np.array([np.mean([tab[(s, m)] for s in streams if unit_of(s) == u]) for u in units])
    rep["means"] = {role: float(unit_vec(m).mean()) for role, m in roles.items() if any(k[1] == m for k in tab)}
    comps, ps = {}, {}
    for a, b in family:
        if a not in rep["means"] or b not in rep["means"]:
            continue
        va, vb = unit_vec(roles[a]), unit_vec(roles[b])
        dif = va - vb
        w, l = int((dif < 0).sum()), int((dif > 0).sum())
        comps[f"{a} vs {b}"] = {"rel_diff": float(dif.mean() / vb.mean()), "W": w, "L": l,
                                "sign_p": own_sign_p(w, l), "ci95": own_ci(dif), "mean_diff": float(dif.mean())}
        ps[f"{a} vs {b}"] = comps[f"{a} vs {b}"]["sign_p"]
    for k, p in own_holm(ps).items():
        comps[k]["holm"] = p
    rep["comparisons"] = comps
    # agreement with the archived analysis
    if archived:
        agree = {}
        for k, c in comps.items():
            a = archived["comparisons"].get(k, {}).get("pi") if "comparisons" in archived else None
            if a is None:
                continue
            agree[k] = {"rel_diff_abs_err": abs(a["rel_diff"] - c["rel_diff"]),
                        "WL_equal": (a["stream_wins"], a["stream_losses"]) == (c["W"], c["L"]),
                        "holm_equal": abs(a.get("sign_p_holm", -1) - c["holm"]) < 1e-12,
                        "ci_max_abs_err": max(abs(a["ci95"][0] - c["ci95"][0]), abs(a["ci95"][1] - c["ci95"][1]))}
        means_err = max(abs(archived["means"][r]["pi"] - v) for r, v in rep["means"].items() if r in archived["means"])
        rep["agreement_with_archived"] = {"max_mean_abs_err": means_err, "comparisons": agree}
    rep["infeasible_examples"] = bad[:5]
    return rep


def checksums(d):
    f = d / "RUNS.sha256"
    if not f.exists():
        return None
    bad = 0
    n = 0
    for line in open(f):
        h, p = line.split()
        n += 1
        bad += hashlib.sha256((d / p).read_bytes()).hexdigest() != h
    return {"files": n, "mismatch": bad}


def main():
    out = {}
    # COBAR confirmatory
    croot = ROOT / "results/cobar/confirmatory"
    raw = (croot / "FROZEN_CONFIG.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (croot / "FROZEN_CONFIG.sha256").read_text().split()[0]
    cfg = json.loads(raw)
    arch = json.loads((croot / "confirmatory_analysis.json").read_text())["settings"]
    for d in sorted(p for p in croot.iterdir() if p.is_dir()):
        fam = [tuple(x) for x in cfg["family_S1"]] if d.name.startswith("S1") else \
            [("candidate", "iaip_sr"), ("candidate", "portfolio_hinted")]
        rep = verify(d, cfg["roles"], fam, arch.get(d.name))
        rep["checksums"] = checksums(d)
        out[f"cobar/{d.name}"] = rep
        print(d.name, json.dumps({k: rep[k] for k in ("records", "solver_invocations", "physical_instances", "grid_complete",
                                                       "infeasible_final_schedules", "objective_vs_own_makespan_mismatch",
                                                       "duplicate_run_keys", "checksums")}))
        for k, c in rep["comparisons"].items():
            ag = rep.get("agreement_with_archived", {}).get("comparisons", {}).get(k, {})
            print(f"   {k:34s} {100 * c['rel_diff']:+6.1f}% {c['W']}/{c['L']} holm={c['holm']:.2g}  agree: {ag}")
    # IAIP-SR confirmatory
    iroot = ROOT / "results/research_extension/confirmatory"
    icfg = json.loads((iroot / "FROZEN_CONFIG.json").read_text())
    iarch = json.loads((iroot / "confirmatory_analysis.json").read_text())
    iarch_like = {"means": iarch["means"], "comparisons": {k: {"pi": v["pi"]} for k, v in iarch["family"].items()}}
    rep = verify(iroot, icfg["roles"], [tuple(x) for x in icfg["family"]], iarch_like)
    rep["checksums"] = checksums(iroot)
    out["iaip_sr/confirmatory"] = rep
    print("IAIP-SR confirmatory", json.dumps({k: rep[k] for k in ("records", "physical_instances", "grid_complete",
                                                               "infeasible_final_schedules", "objective_vs_own_makespan_mismatch",
                                                               "checksums")}))
    for k, c in rep["comparisons"].items():
        print(f"   {k:46s} {100 * c['rel_diff']:+6.1f}% {c['W']}/{c['L']} holm={c['holm']:.2g}")
    dest = ROOT / "results/unified_icaps/baseline_verification.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, default=float))
    print("wrote", dest)


if __name__ == "__main__":
    main()
