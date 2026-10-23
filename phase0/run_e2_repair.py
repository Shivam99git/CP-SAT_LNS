"""Stage E2 (development streams only): initial-incumbent quality of repair
strategies and fresh constructive schedules, before any solver improvement.

For every stream step t >= 1 the predecessor is a CP-SAT solution of step
t-1 (unhinted, --pred-budget seconds, seed 0), and the reference value is
the best of a CP-SAT solution of step t (same budget) and every candidate.
Candidates are built once each, timed, and checked by the independent
validator:
  append        archived Floor repair (harness.list_schedule_bootstrap)
  gap_insert, regret_insert, beam_insert   archived insertion floor policies
  elr           event-localized repair (phase0/event_localized_repair.py)
  spt, mwkr     fresh dispatching, no history

    .venv/bin/python -m phase0.run_e2_repair --out results/research_extension/e2_repair/dev.jsonl
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

from .baselines import dispatch_mwkr, dispatch_spt
from .bootstrap_policies import FLOOR_POLICIES
from .event_localized_repair import event_localized_repair
from .model_builder import build_model, solve
from .run_gate1 import StreamSpec
from .schedule_validator import ScheduleError, check_schedule
from .streams import StreamConfig, generate_stream


def _candidates(inst, prev):
    out = {}
    fns = {"append": lambda: FLOOR_POLICIES["append"](inst, prev),
           "gap_insert": lambda: FLOOR_POLICIES["gap_insert"](inst, prev),
           "regret_insert": lambda: FLOOR_POLICIES["regret_insert"](inst, prev),
           "beam_insert": lambda: FLOOR_POLICIES["beam_insert"](inst, prev),
           "elr": lambda: event_localized_repair(inst, prev),
           "spt": lambda: dispatch_spt(inst), "mwkr": lambda: dispatch_mwkr(inst)}
    for name, fn in fns.items():
        t = time.perf_counter()
        r = fn()
        dt = time.perf_counter() - t
        sol, stats = (r if name == "elr" else (r, None))
        try:
            obj, err = check_schedule(inst, sol), None
        except ScheduleError as e:
            obj, err = None, str(e)
        rec = {"objective": obj, "time_s": dt, "error": err}
        if stats is not None:
            rec.update({"fallback": stats.fallback, "core_removed": stats.core_removed,
                        "new_ops": stats.new_ops, "reused_order_pairs": stats.reused_order_pairs,
                        "total_order_pairs": stats.total_order_pairs,
                        "changed_machine_arcs": stats.changed_machine_arcs,
                        "frac_start_changed": stats.frac_start_changed})
        out[name] = rec
    return out


def _run_stream(args):
    machines, seed, length, pred_budget, kinds = args
    os.sched_setaffinity(0, os.sched_getaffinity(0))
    spec = StreamSpec(machines, machines, seed, length)
    cfg = StreamConfig(num_machines=machines, initial_jobs=machines, stream_length=length,
                       seed=seed, severity="medium")
    cfg.ops_per_job, cfg.duration_range = (machines, machines), (5, 50)
    if kinds:
        for f in ("p_arrival", "p_cancellation", "p_duration_jitter", "p_outage"):
            setattr(cfg, f, 0.0)
        for k in kinds:
            setattr(cfg, f"p_{k}", 1.0)
    stream = generate_stream(cfg)
    recs = []
    prev, _, _ = solve(build_model(stream[0]), time_limit=pred_budget, seed=0)
    for inst in stream[1:]:
        cands = _candidates(inst, prev)
        ref_sol, ref_obj, _ = solve(build_model(inst), time_limit=pred_budget, seed=0)
        recs.append({"stream": spec.name + ("_" + "+".join(kinds) if kinds else ""),
                     "size": f"{machines}x{machines}", "seed": seed, "step": inst.index,
                     "delta_kind": inst.delta_kind, "cpsat_ref": ref_obj, "candidates": cands})
        prev = ref_sol
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 15, 20])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(301, 311)))
    ap.add_argument("--length", type=int, default=10)
    ap.add_argument("--pred-budget", type=float, default=2.0)
    ap.add_argument("--kinds", nargs="*", default=None)
    ap.add_argument("--processes", type=int, default=4)
    a = ap.parse_args()
    tasks = [(m, s, a.length, a.pred_budget, a.kinds) for m in a.sizes for s in a.seeds]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with mp.get_context("fork").Pool(a.processes) as pool, open(a.out, "w") as f:
        for recs in pool.imap_unordered(_run_stream, tasks):
            for r in recs:
                f.write(json.dumps(r) + "\n")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
