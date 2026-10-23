"""Gate 1 campaign: does historical reuse help beyond fresh constructive
incumbents? (docs/research_extension/04_experimental_methodology.md)

Protocol B (closed loop): every method carries its OWN previous returned
solution through the stream -- deployment behaviour.
Protocol A (common predecessor): every history-based method receives the SAME
previous schedule, taken from a reference chain computed offline by Cold with
a dedicated solver seed (REF_SEED). The reference chain's computation time is
excluded under this explicitly offline-information protocol. Cold, SPT+Cold
and MWKR+Cold do not read the predecessor, so their Protocol-B runs are also
their Protocol-A runs; they are not re-executed.

Output layout (one file per task, written atomically, never rewritten):
  <out>/instances/<stream>.json          serialized stream
  <out>/reference/<stream>.jsonl         Protocol-A reference chain
  <out>/runs/<protocol>_<stream>_k<solver_seed>.jsonl
Re-running with the same --out skips finished tasks, so a resumed campaign
cannot change recorded results.

    .venv/bin/python -m phase0.run_gate1 --out results/research_extension/gate1_historical_reuse \
        --cpus 0 2 4 6 8 10 12 14
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import random
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .reuse_methods import GATE1_METHODS, RunResult, run_method
from .streams import Instance, StreamConfig, generate_stream

REF_SEED = 1000
HISTORY_METHODS = ("hint", "floor", "floor_hint", "repaired_hint_only")


def git_rev() -> str:
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.call(["git", "diff", "--quiet", "HEAD", "--", "phase0"]) != 0
        return rev + ("+dirty" if dirty else "")
    except Exception:  # noqa: BLE001
        return "unknown"


@dataclass(frozen=True)
class StreamSpec:
    machines: int
    jobs: int
    seed: int
    length: int

    @property
    def name(self) -> str:
        return f"{self.machines}x{self.jobs}_s{self.seed}"

    def build(self) -> list[Instance]:
        cfg = StreamConfig(num_machines=self.machines, initial_jobs=self.jobs,
                           stream_length=self.length, seed=self.seed, severity="medium")
        cfg.ops_per_job = (self.machines, self.machines)
        cfg.duration_range = (5, 50)
        return generate_stream(cfg)


def instance_to_dict(inst: Instance) -> dict:
    return {"index": inst.index, "num_machines": inst.num_machines, "delta_kind": inst.delta_kind,
            "jobs": [{"job_id": j.job_id, "release_date": j.release_date,
                      "ops": [[o.op_id, o.machine, o.duration] for o in j.ops]} for j in inst.jobs],
            "outages": [[o.machine, o.start, o.end] for o in inst.outages],
            "frozen_starts": dict(inst.frozen_starts)}


def _record(res: RunResult, *, protocol, spec: StreamSpec, inst: Instance, solver_seed,
            workers, has_prev, prev_source, rev, extra=None) -> dict:
    d = asdict(res)
    d.pop("solution")
    d.update({"protocol": protocol, "stream": spec.name, "size": f"{spec.machines}x{spec.jobs}",
              "stream_seed": spec.seed, "step": inst.index, "delta_kind": inst.delta_kind,
              "solver_seed": solver_seed, "workers": workers, "severity": "medium",
              "has_prev": has_prev, "prev_source": prev_source, "algo_config": "gate1-v1",
              "rev": rev, "host": socket.gethostname(), "cpu": os.sched_getaffinity(0).__repr__(),
              "solution": res.solution})
    if extra:
        d.update(extra)
    return d


def _write_atomic(path: Path, records: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, path)


# --- tasks (module level for multiprocessing) ---------------------------------

@dataclass(frozen=True)
class Task:
    kind: str            # "ref", "B", "A"
    spec: StreamSpec
    solver_seed: int
    budget: float
    workers: int
    out: str
    rev: str

    @property
    def path(self) -> Path:
        o = Path(self.out)
        if self.kind == "ref":
            return o / "reference" / f"{self.spec.name}.jsonl"
        return o / "runs" / f"{self.kind}_{self.spec.name}_k{self.solver_seed}.jsonl"


def _run_task(task: Task) -> tuple[str, int, float]:
    t0 = time.monotonic()
    stream = task.spec.build()
    recs: list[dict] = []
    if task.kind == "ref":
        prev = None
        for inst in stream:
            res = run_method("cold", inst, None, task.budget, task.workers, REF_SEED)
            recs.append(_record(res, protocol="REF", spec=task.spec, inst=inst, solver_seed=REF_SEED,
                                workers=task.workers, has_prev=False, prev_source="none", rev=task.rev))
            prev = res.solution
    elif task.kind == "B":
        prev = {m: None for m in GATE1_METHODS}
        for inst in stream:
            order = list(GATE1_METHODS)
            random.Random(f"{task.spec.name}|{task.solver_seed}|{inst.index}").shuffle(order)
            for m in order:
                res = run_method(m, inst, prev[m], task.budget, task.workers, task.solver_seed)
                recs.append(_record(res, protocol="B", spec=task.spec, inst=inst,
                                    solver_seed=task.solver_seed, workers=task.workers,
                                    has_prev=prev[m] is not None, prev_source="own", rev=task.rev,
                                    extra={"order_position": order.index(m)}))
                if res.solution is not None:
                    prev[m] = res.solution
    else:  # Protocol A
        ref_path = Path(task.out) / "reference" / f"{task.spec.name}.jsonl"
        ref = {r["step"]: r["solution"] for r in map(json.loads, open(ref_path))}
        for inst in stream[1:]:
            pred = ref.get(inst.index - 1)
            order = list(HISTORY_METHODS)
            random.Random(f"A|{task.spec.name}|{task.solver_seed}|{inst.index}").shuffle(order)
            for m in order:
                res = run_method(m, inst, pred, task.budget, task.workers, task.solver_seed)
                recs.append(_record(res, protocol="A", spec=task.spec, inst=inst,
                                    solver_seed=task.solver_seed, workers=task.workers,
                                    has_prev=pred is not None, prev_source=f"ref_cold_seed{REF_SEED}",
                                    rev=task.rev, extra={"order_position": order.index(m)}))
    _write_atomic(task.path, recs)
    return str(task.path), len(recs), time.monotonic() - t0


_CPU_QUEUE = None


def _init_worker(q):
    cpu = q.get()
    if cpu is not None:
        os.sched_setaffinity(0, {cpu})


def _run_pool(tasks: list[Task], cpus: list[int | None]) -> None:
    todo = [t for t in tasks if not t.path.exists()]
    print(f"  {len(tasks) - len(todo)} done already, {len(todo)} to run on {len(cpus)} workers", flush=True)
    if not todo:
        return
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    for c in cpus:
        q.put(c)
    with ctx.Pool(len(cpus), initializer=_init_worker, initargs=(q,)) as pool:
        for i, (path, n, dt) in enumerate(pool.imap_unordered(_run_task, todo), 1):
            print(f"  [{i}/{len(todo)}] {Path(path).name}: {n} records, {dt:.0f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 15, 20])
    ap.add_argument("--stream-seeds", type=int, nargs="+", default=list(range(101, 116)))
    ap.add_argument("--solver-seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--stream-length", type=int, default=10)
    ap.add_argument("--budget", type=float, default=8.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--protocols", nargs="+", default=["B", "A"], choices=["A", "B"])
    ap.add_argument("--cpus", type=int, nargs="+", default=None,
                    help="pin one worker process per listed CPU id")
    ap.add_argument("--processes", type=int, default=4, help="used when --cpus is not given")
    args = ap.parse_args()

    out = Path(args.out)
    for sub in ("instances", "reference", "runs"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    rev = git_rev()
    specs = [StreamSpec(m, m, s, args.stream_length) for m in args.sizes for s in args.stream_seeds]
    for spec in specs:
        p = out / "instances" / f"{spec.name}.json"
        if not p.exists():
            p.write_text(json.dumps([instance_to_dict(i) for i in spec.build()]))
    manifest = {"argv": vars(args), "rev": rev, "python": platform.python_version(),
                "platform": platform.platform(), "host": socket.gethostname(),
                "methods": GATE1_METHODS, "history_methods": HISTORY_METHODS, "ref_seed": REF_SEED,
                "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(out / "manifests.jsonl", "a") as f:
        f.write(json.dumps(manifest) + "\n")

    cpus = args.cpus if args.cpus else [None] * args.processes
    mk = lambda kind, spec, k: Task(kind, spec, k, args.budget, args.workers, str(out), rev)  # noqa: E731
    if "A" in args.protocols:
        print("reference chains (Protocol A predecessors):", flush=True)
        _run_pool([mk("ref", s, REF_SEED) for s in specs], cpus)
    tasks = []
    for k in args.solver_seeds:  # seed-major order: early partial results cover all streams
        for spec in specs:
            for proto in args.protocols:
                tasks.append(mk(proto, spec, k))
    print("main tasks:", flush=True)
    _run_pool(tasks, cpus)
    print("done", flush=True)


if __name__ == "__main__":
    main()
