"""Closed-loop (Protocol B) campaigns for the IAIP-SR stages E3-E6.

Method names:
  cold, hint, floor, floor_hint, repaired_hint_only, spt_cold, mwkr_cold
      deadline-correct Gate 1 methods (phase0/reuse_methods.py)
  iaip|key=value|...
      integrated method with an IAIPConfig, e.g.
      iaip|portfolio=full|alpha=0.2|neighbourhood=N5|global_mode=unhinted
  lns_prev_solution, fix_and_optimize_50, local_branching_prev
      archived reoptimization baselines (phase0/baselines.py), unchanged;
      their trajectories are re-validated and recorded the same way
Every method carries its own previous returned solution. Records go to one
atomically written file per (stream, solver seed); finished files are
skipped on resume. The stream seed sets (development vs. confirmatory) are
chosen on the command line and logged in the manifest.

    .venv/bin/python -m phase0.run_iaip_campaign --out results/research_extension/dev_e3e4 \\
        --sizes 15 20 --stream-seeds 301 302 ... --methods cold floor ... --cpus 16 17 18 19
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import random
import socket
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import baselines as bl
from .impact_aware_reoptimization import IAIPConfig, run_iaip
from .reuse_methods import GATE1_METHODS, RunResult, run_method
from .run_gate1 import StreamSpec, _init_worker, _write_atomic, git_rev, instance_to_dict
from .schedule_validator import ScheduleError, check_schedule

ARCHIVED = ("lns_prev_solution", "fix_and_optimize_50", "local_branching_prev")
_CFG_FIELDS = {f.name: f.type for f in fields(IAIPConfig)}


def parse_iaip(name: str) -> IAIPConfig:
    kw = {}
    for part in name.split("|")[1:]:
        k, v = part.split("=")
        cur = getattr(IAIPConfig(), k)
        kw[k] = type(cur)(v) if not isinstance(cur, bool) else v in ("1", "true", "True")
    return IAIPConfig(**kw)


def _archived(name, inst, prev, budget, workers, seed) -> RunResult:
    t0 = time.monotonic()
    if name == "lns_prev_solution":
        from .run_icaps_jssp_suite import FIXED_ARM_LNS
        r = bl.lns_prev_solution(inst, budget, prev, workers=workers, seed=seed, arm_names=FIXED_ARM_LNS)
    elif name == "fix_and_optimize_50":
        r = bl.fix_and_optimize(inst, budget, prev, freeze_frac=0.5, workers=workers, seed=seed)
    else:
        r = bl.local_branching_prev(inst, budget, prev, workers=workers, seed=seed)
    total = time.monotonic() - t0
    res = RunResult(method=name, budget=budget, total_s=total, overrun_s=max(0.0, total - budget))
    best = None
    for t, o in sorted(r.trajectory):
        if best is None or o < best:
            best = o
            res.events.append((t, o, "archived"))
    if r.solution is not None:
        try:
            obj = check_schedule(inst, r.solution)
            res.objective, res.solution, res.validated = obj, r.solution, obj == r.objective
        except ScheduleError as e:
            res.notes.append(f"archived solution rejected: {e}")
    res.solver_status = "ARCHIVED"
    return res


@dataclass(frozen=True)
class Task:
    spec: StreamSpec
    solver_seed: int
    methods: tuple[str, ...]
    budget: float
    workers: int
    out: str
    rev: str
    tag: str

    @property
    def path(self) -> Path:
        return Path(self.out) / "runs" / f"{self.spec.name}_k{self.solver_seed}.jsonl"


def _run(task: Task):
    t0 = time.monotonic()
    stream = task.spec.build()
    prev = {m: None for m in task.methods}
    recs = []
    for k, inst in enumerate(stream):
        prev_inst = stream[k - 1] if k else None
        order = list(task.methods)
        random.Random(f"{task.spec.name}|{task.solver_seed}|{inst.index}").shuffle(order)
        for m in order:
            meta = {}
            if m in GATE1_METHODS:
                res = run_method(m, inst, prev[m], task.budget, task.workers, task.solver_seed)
            elif m in ARCHIVED:
                res = _archived(m, inst, prev[m], task.budget, task.workers, task.solver_seed)
            elif m.startswith("iaip|"):
                res, meta = run_iaip(inst, prev[m], prev_inst if prev[m] is not None else None,
                                     task.budget, parse_iaip(m), task.workers, task.solver_seed, m)
            else:
                raise ValueError(m)
            d = asdict(res)
            d.update({"protocol": "B", "stream": task.spec.name,
                      "size": f"{task.spec.machines}x{task.spec.jobs}", "stream_seed": task.spec.seed,
                      "step": inst.index, "delta_kind": inst.delta_kind, "solver_seed": task.solver_seed,
                      "workers": task.workers, "has_prev": prev[m] is not None, "prev_source": "own",
                      "algo_config": m, "rev": task.rev, "host": socket.gethostname(),
                      "campaign": task.tag, "order_position": order.index(m), "meta": meta})
            recs.append(d)
            if res.solution is not None:
                prev[m] = res.solution
    _write_atomic(task.path, recs)
    return task.path.name, len(recs), time.monotonic() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True, help="campaign label, e.g. dev or confirmatory")
    ap.add_argument("--sizes", type=int, nargs="+", default=[15, 20])
    ap.add_argument("--stream-seeds", type=int, nargs="+", required=True)
    ap.add_argument("--solver-seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--stream-length", type=int, default=6)
    ap.add_argument("--budget", type=float, default=8.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--methods", nargs="+", required=True)
    ap.add_argument("--cpus", type=int, nargs="+", required=True)
    a = ap.parse_args()
    for m in a.methods:
        if m.startswith("iaip|"):
            parse_iaip(m)
        elif m not in GATE1_METHODS and m not in ARCHIVED:
            raise SystemExit(f"unknown method {m}")
    out = Path(a.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    (out / "instances").mkdir(exist_ok=True)
    rev = git_rev()
    specs = [StreamSpec(m, m, s, a.stream_length) for m in a.sizes for s in a.stream_seeds]
    for spec in specs:
        p = out / "instances" / f"{spec.name}.json"
        if not p.exists():
            p.write_text(json.dumps([instance_to_dict(i) for i in spec.build()]))
    with open(out / "manifests.jsonl", "a") as f:
        f.write(json.dumps({"argv": vars(a), "rev": rev, "python": platform.python_version(),
                            "platform": platform.platform(),
                            "started": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
    tasks = [Task(s, k, tuple(a.methods), a.budget, a.workers, str(out), rev, a.tag)
             for k in a.solver_seeds for s in specs]
    todo = [t for t in tasks if not t.path.exists()]
    print(f"{len(tasks) - len(todo)} done, {len(todo)} to run", flush=True)
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    for c in a.cpus:
        q.put(c)
    with ctx.Pool(len(a.cpus), initializer=_init_worker, initargs=(q,)) as pool:
        for i, (name, n, dt) in enumerate(pool.imap_unordered(_run, todo), 1):
            print(f"[{i}/{len(todo)}] {name}: {n} records, {dt:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
