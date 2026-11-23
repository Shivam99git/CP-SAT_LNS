"""Run the tasks of a frozen multisolver plan (Task 7.1).

    .venv_ms/bin/python scripts/multisolver/run_benchmark.py --plan results/multisolver/FROZEN_PLAN.json \
        [--experiments A,B] [--cores 0,2,4,6,8,10,12,14] [--dry-run]

Each task runs in a fresh interpreter (run_task.py) pinned to `workers`
distinct physical P-cores taken from a token pool, so concurrent tasks never
share a core. Task order is shuffled with a fixed seed (solvers/methods are
not systematically co-scheduled). Tasks already recorded are skipped (resume).
Every outcome -- OK, NO_SOLUTION, INVALID, NOT_SUPPORTED, ERROR, licence
refusals inside stages -- is appended; nothing is dropped.
"""
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from campaign_lib import OUT, P_CORES, ROOT, done_ids, result_file, rev, task_id  # noqa: E402

PY = str(ROOT / ".venv_ms/bin/python")


def expand(plan: dict, only: set | None):
    tasks = []
    for exp in plan["experiments"]:
        if only and exp["name"] not in only:
            continue
        for block in exp["blocks"]:
            for f in sorted((ROOT / block["instances"]).glob("*.json"))[: block.get("max_streams", 999)]:
                for step in block["steps"]:
                    for solver in block["solvers"]:
                        for method in block["methods"]:
                            seeds = block["seeds"].get(solver, block["seeds"]["default"]) \
                                if isinstance(block["seeds"], dict) else block["seeds"]
                            if method in block.get("seeds_by_method", {}):
                                seeds = [s for s in seeds if s in block["seeds_by_method"][method]] or seeds[:1]
                            for budget in block["budgets"]:
                                for workers in block["workers"]:
                                    for seed in seeds:
                                        tasks.append({"experiment": exp["name"], "tier": block["tier"],
                                                      "stream": f.stem, "stream_file": str(f), "step": step,
                                                      "solver": solver, "method": method, "budget": budget,
                                                      "workers": workers, "seed": seed})
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--experiments", default="")
    ap.add_argument("--cores", default=",".join(map(str, P_CORES)))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    only = set(a.experiments.split(",")) if a.experiments else None
    tasks = expand(plan, only)
    seen, uniq = set(), []
    for t in tasks:
        if task_id(t) not in seen:
            seen.add(task_id(t)); uniq.append(t)
    done = done_ids()
    todo = [t for t in uniq if task_id(t) not in done]
    random.Random(plan.get("shuffle_seed", 2027)).shuffle(todo)
    cpu_s = sum(t["budget"] * t["workers"] for t in todo)
    print(f"tasks: {len(uniq)} total, {len(done & seen)} done, {len(todo)} to run; "
          f"~{cpu_s / 3600:.1f} budgeted core-hours", flush=True)
    if a.dry_run:
        from collections import Counter
        print(Counter((t["experiment"], t["tier"], t["solver"]) for t in todo))
        return
    r = rev()
    free = [int(c) for c in a.cores.split(",")]
    running = []
    manifest = OUT / "runs" / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    n_done = 0
    t_start = time.time()
    while todo or running:
        launched = True
        while launched and todo:
            launched = False
            for i, t in enumerate(todo):
                if t["workers"] <= len(free):
                    cpus = [free.pop(0) for _ in range(t["workers"])]
                    t = dict(t, cpus=cpus, rev=r)
                    p = subprocess.Popen(["taskset", "-c", ",".join(map(str, cpus)), PY,
                                          str(ROOT / "scripts/multisolver/run_task.py"), json.dumps(t)],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    running.append((p, t, cpus, time.time()))
                    todo.pop(i)
                    launched = True
                    break
        time.sleep(0.05)
        still = []
        for p, t, cpus, ts in running:
            if p.poll() is None:
                if time.time() - ts > t["budget"] * 3 + 120:     # hard watchdog: record, never hang
                    p.kill()
                    p.wait()
                    rec = {"task_id": task_id(t), **{k: v for k, v in t.items() if k not in ("stream_file", "cpus")},
                           "status": "ERROR", "error": "watchdog: task exceeded 3*budget+120s"}
                else:
                    still.append((p, t, cpus, ts))
                    continue
            else:
                out, err = p.communicate()
                line = next((l for l in out.splitlines() if l.startswith("@@RECORD@@")), None)
                if line is None:
                    rec = {"task_id": task_id(t), **{k: v for k, v in t.items() if k not in ("stream_file", "cpus")},
                           "status": "ERROR", "error": ("child crashed: " + err[-400:])}
                else:
                    rec = json.loads(line[len("@@RECORD@@"):])
            f = result_file(t)
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            with open(manifest, "a") as fh:
                fh.write(json.dumps({"task_id": rec["task_id"], "status": rec["status"], "cpus": cpus,
                                     "rev": t["rev"], "finished": time.time()}) + "\n")
            free.extend(cpus)
            n_done += 1
            if n_done % 50 == 0:
                el = time.time() - t_start
                print(f"{n_done} done, {len(todo)} queued, {len(running)} running, {el / 60:.1f} min", flush=True)
        running = still
    print("campaign finished", flush=True)


if __name__ == "__main__":
    main()
