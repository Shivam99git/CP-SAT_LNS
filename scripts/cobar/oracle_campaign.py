"""Exact-oracle campaign for the COBAR certificate and release cut (Task 7.2).
Larger than the unit tests; results saved to results/cobar/oracle_campaign.json.
Uses the independent oracles of tests/cobar/test_certificates.py.

    taskset -c 16-19 .venv/bin/python scripts/cobar/oracle_campaign.py
"""
import itertools
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/cobar"))
from phase0.cobar_certificates import certificate, global_certificate  # noqa: E402
from phase0.cobar_neighborhood import INF, min_release_cut, obstruction, release_obstructions  # noqa: E402
from test_certificates import (  # noqa: E402
    cpsat_optimum, enumeration_optimum, independent_kept_arcs, random_feasible_schedule, random_instance,
    with_commitments,
)
from test_neighborhood import _chains  # noqa: E402

t0 = time.time()
rng = random.Random(2026)
out = {"enumeration": {"cases": 0, "decisive": 0, "violations": 0, "tight": 0},
       "cpsat": {"cases": 0, "decisive": 0, "violations": 0, "tight": 0},
       "global": {"cases": 0, "decisive": 0, "violations": 0},
       "cut": {"cases": 0, "finite": 0, "miss_chain": 0, "not_minimum": 0},
       "release_loop": {"cases": 0, "violations": 0, "status": {}}}
failures = []


def case(oracle, key, n, allow_zero):
    while out[key]["cases"] < n:
        inst = random_instance(rng, n_jobs=rng.choice([2, 3, 4]) if key == "cpsat" else rng.choice([2, 3]),
                               n_mach=3, allow_zero=allow_zero, releases=rng.random() < 0.6)
        try:
            S = random_feasible_schedule(rng, inst, slack=rng.choice([0, 0, 1, 3]))
        except RuntimeError:
            continue
        if rng.random() < 0.3:
            inst = with_commitments(rng, inst, S, frac=rng.choice([0.1, 0.3]))
        ids = [o.op_id for o in inst.all_ops]
        N = {v for v in ids if rng.random() < rng.choice([0.0, 0.1, 0.3, 0.6, 1.0])}
        R = {a for a in independent_kept_arcs(inst, S, N, set()) if rng.random() < rng.choice([0.0, 0.2, 0.5])}
        cert = certificate(inst, S, N, R)
        opt = oracle(inst, independent_kept_arcs(inst, S, N, R))
        d = out[key]
        d["cases"] += 1
        d["tight"] += cert.L == opt
        if cert.L > opt or (cert.decisive and opt < cert.U):
            d["violations"] += 1
            failures.append({"oracle": key, "L": cert.L, "opt": opt, "U": cert.U})
        d["decisive"] += cert.decisive


case(enumeration_optimum, "enumeration", 2000, False)
case(cpsat_optimum, "cpsat", 1000, True)

while out["global"]["cases"] < 500:
    inst = random_instance(rng, n_jobs=rng.choice([3, 4]), n_mach=3)
    try:
        S = random_feasible_schedule(rng, inst, slack=0)
    except RuntimeError:
        continue
    g = global_certificate(inst, S)
    opt = cpsat_optimum(inst, [])
    out["global"]["cases"] += 1
    out["global"]["decisive"] += g.decisive
    if g.L > opt or (g.decisive and opt != g.U):
        out["global"]["violations"] += 1

while out["cut"]["cases"] < 1000:
    inst = random_instance(rng, n_jobs=rng.choice([3, 4]), n_mach=3, releases=rng.random() < 0.5)
    try:
        S = random_feasible_schedule(rng, inst, slack=0)
    except RuntimeError:
        continue
    if rng.random() < 0.2:
        inst = with_commitments(rng, inst, S, frac=0.2)
    N = {o.op_id for o in inst.all_ops if rng.random() < rng.choice([0.0, 0.2])}
    cert = certificate(inst, S, N)
    if not (cert.decisive and cert.L_path >= cert.U):
        continue
    out["cut"]["cases"] += 1
    ob = obstruction(inst, S, N, set(), cert.U)
    chains = _chains(ob)
    cut, cost = min_release_cut(ob)
    if cost < INF:
        out["cut"]["finite"] += 1
        if any(not any(a in cut for a, _ in ch) for ch in chains):
            out["cut"]["miss_chain"] += 1
        best = None
        for k in range(len(ob.releasable) + 1):
            if any(all(any(a in sub for a, _ in ch) for ch in chains)
                   for sub in itertools.combinations(ob.releasable, k)):
                best = k
                break
        if best != cost:
            out["cut"]["not_minimum"] += 1
    res = release_obstructions(inst, S, N)
    out["release_loop"]["cases"] += 1
    out["release_loop"]["status"][res.status] = out["release_loop"]["status"].get(res.status, 0) + 1
    opt = cpsat_optimum(inst, independent_kept_arcs(inst, S, res.N, res.R))
    if res.after.L > opt or (res.after.decisive and opt != res.after.U) or \
            (res.status == "released") == res.after.decisive:
        out["release_loop"]["violations"] += 1

out["failures"] = failures
out["seconds"] = round(time.time() - t0, 1)
Path(ROOT / "results/cobar/oracle_campaign.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "failures"}, indent=1))
