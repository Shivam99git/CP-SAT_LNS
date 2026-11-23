"""Multisolver smoke test (Task 7.2): every available solver x every method it
supports, on tiny dynamic streams whose optimum is known exactly from the
exhaustive oracle. Covers the standard job shop, release dates, machine
outages, frozen (committed) starts produced by the stream generator's
partial_schedule_freeze delta, job arrival, job cancellation and duration
changes. Requires zero invalid schedules and the oracle optimum everywhere.

    .venv_ms/bin/python scripts/multisolver/run_smoke.py
"""
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/cobar"))

from phase0.multisolver_methods import METHODS, run_method, supported  # noqa: E402
from phase0.solver_adapters import ADAPTERS, cached_version  # noqa: E402
from phase0.solver_independent_model import exhaustive_optimum, instance_hash  # noqa: E402
from phase0.streams import StreamConfig, generate_stream  # noqa: E402
from test_certificates import random_instance  # noqa: E402


def dynamic_stream(seed, freeze):
    """Tiny stream generated step by step so partial_schedule_freeze can see the
    previous (oracle-optimal) schedule."""
    cfg = StreamConfig(num_machines=3, initial_jobs=2, ops_per_job=(2, 3), duration_range=(2, 8),
                       stream_length=4, seed=seed, p_partial_schedule_freeze=0.6 if freeze else 0.0)
    sols = {}
    for k in range(cfg.stream_length + 1):
        cur = generate_stream(cfg, prev_solutions=sols)[k]   # steps <= k depend only on sols[< k]
        try:
            _, sols[k] = exhaustive_optimum(cur)
        except ValueError:
            return None
    return generate_stream(cfg, prev_solutions=sols), sols


def main():
    for a in ADAPTERS.values():
        cached_version(a)
    cases = []
    rng = random.Random(2)
    for name, kw in [("standard", dict(outages=False, releases=False)), ("releases", dict(outages=False)),
                     ("outages", dict(releases=False))]:
        cases.append((name, random_instance(rng, n_jobs=3, n_mach=3, dur=(1, 5), **kw), None, None))
    kinds = Counter()
    for seed in range(40):
        for freeze in (False, True):
            got = dynamic_stream(seed, freeze)
            if got is None:
                continue
            stream, sols = got
            for k in range(1, len(stream)):
                inst = stream[k]
                per_m = Counter(o.machine for o in inst.all_ops)
                key = "frozen_starts" if inst.frozen_starts else inst.delta_kind
                if kinds[key] < 2 and max(per_m.values()) <= 4:
                    kinds[key] += 1
                    cases.append((f"{key}{kinds[key]}", inst, sols[k - 1], stream[k - 1]))
        if all(kinds[k] >= 2 for k in ("arrival", "cancellation", "duration_jitter", "outage", "frozen_starts")):
            break
    out = {"cases": [], "summary": {}}
    bad = 0
    for name, inst, prev, prev_inst in cases:
        opt, _ = exhaustive_optimum(inst)
        for solver in ADAPTERS:
            for method in METHODS:
                if not supported(method, solver):
                    continue
                t = time.monotonic()
                r = run_method(method, solver, inst, prev, prev_inst, budget=3.0)
                ok = r.validated and r.objective == opt
                bad += not ok
                out["cases"].append({"case": name, "hash": instance_hash(inst), "solver": solver, "method": method,
                                     "oracle": opt, "objective": r.objective, "validated": r.validated,
                                     "ok": ok, "total_s": round(time.monotonic() - t, 3), "notes": r.notes[:3]})
                if not ok:
                    print("FAIL", name, solver, method, r.objective, opt, r.notes[:2], flush=True)
    feats = sorted({c[0].rstrip("0123456789") for c in cases})
    out["summary"] = {"n_runs": len(out["cases"]), "n_fail": bad, "features": feats,
                      "solvers": list(ADAPTERS), "methods": list(METHODS)}
    p = ROOT / "results/multisolver/smoke/smoke_results.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["summary"]))


if __name__ == "__main__":
    main()
