"""Shared campaign machinery for the multisolver study (Tasks 6-7).

Instance archive: every stream is generated once, serialized canonically
(phase0/solver_independent_model), hashed, and stored with a REFERENCE
previous schedule for each step (CP-SAT, 4 workers, 6 s on step t-1, offline,
not part of any measured run), so every solver and method faces byte-identical
instances and an identical history. prev_source = "reference".

Tasks run one per fresh child process (maxtasksperchild=1), pinned to one
logical CPU of a distinct physical performance core, so per-task CPU time
(self + children, i.e. including MiniZinc / cpoptimizer subprocesses) and peak
RSS are measured per run. Results are appended to one JSONL file per
(experiment, tier, solver); a task id that is already present is skipped
(resume without duplicates).
"""
from __future__ import annotations

import json
import os
import resource
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from phase0.run_gate1 import StreamSpec  # noqa: E402
from phase0.solver_independent_model import (  # noqa: E402
    from_canonical_dict, instance_hash, model_size_hint, to_canonical_dict,
)

OUT = ROOT / "results/multisolver"
INST_DIR = OUT / "instances"
# one logical CPU per physical P-core (cores 0-7 have HT siblings 2k, 2k+1); E-cores 16-19 excluded
P_CORES = [0, 2, 4, 6, 8, 10, 12, 14]

TIERS = {
    # licence-feasible tier: every step must fit the strictest bundled licence (CPLEX CE 1000/1000)
    "S": {"machines": 8, "jobs": 6, "length": 10},
    # paper scale (as the CP-SAT confirmatory study)
    "M15": {"machines": 15, "jobs": 15, "length": 10},
    "M20": {"machines": 20, "jobs": 20, "length": 10},
}


def rev():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def fits_licences(stream) -> bool:
    from phase0.jobshop_milp import build_milp
    for inst in stream:
        lm = build_milp(inst)
        if lm.n_vars > 1000 or lm.n_rows > 1000:
            return False
        if len(inst.all_ops) + 1 > 1000:   # CP Optimizer CE: interval variables
            return False
    return True


def select_streams(tier: str, first_seed: int, count: int, max_scan: int = 200):
    """Size-only, pre-registered selection: scan seeds upward from first_seed and
    keep the first `count` streams (tier S: those fitting every licence)."""
    t = TIERS[tier]
    out, seed = [], first_seed
    while len(out) < count and seed < first_seed + max_scan:
        spec = StreamSpec(t["machines"], t["jobs"], seed, t["length"])
        st = spec.build()
        if tier != "S" or fits_licences(st):
            out.append((spec, st))
        seed += 1
    return out


def build_archive(phase: str, tier: str, first_seed: int, count: int, ref_budget: float = 6.0,
                  ref_workers: int = 4):
    from phase0.model_builder import solve
    from phase0.reuse_methods import build_research_model
    from phase0.schedule_validator import check_schedule
    d = INST_DIR / phase / tier
    d.mkdir(parents=True, exist_ok=True)
    for spec, st in select_streams(tier, first_seed, count):
        f = d / f"{spec.name}.json"
        if f.exists():
            continue
        steps = []
        for k, inst in enumerate(st):
            ref, obj = None, None
            if k < len(st) - 1:   # reference solution of step k = history for step k + 1
                sol, _, _ = solve(build_research_model(inst), time_limit=ref_budget, workers=ref_workers, seed=0)
                obj = check_schedule(inst, sol)
                ref = sol
            steps.append({"step": k, "hash": instance_hash(inst), "size": model_size_hint(inst),
                          "instance": to_canonical_dict(inst), "reference_schedule": ref,
                          "reference_objective": obj})
        f.write_text(json.dumps({"stream": spec.name, "tier": tier, "phase": phase, "seed": spec.seed,
                                 "reference": f"cpsat {ref_workers}w {ref_budget}s seed0", "steps": steps}))
        print("archived", f.relative_to(ROOT), flush=True)


def load_stream(path: Path):
    d = json.loads(path.read_text())
    insts = [from_canonical_dict(s["instance"]) for s in d["steps"]]
    for s, inst in zip(d["steps"], insts):
        assert instance_hash(inst) == s["hash"], f"hash mismatch {path} step {s['step']}"
    refs = [s["reference_schedule"] for s in d["steps"]]
    return d, insts, refs


def task_id(t: dict) -> str:
    return "|".join(str(t[k]) for k in ("experiment", "tier", "stream", "step", "solver", "method",
                                        "budget", "workers", "seed"))


def result_file(t: dict) -> Path:
    return OUT / "runs" / t["experiment"] / t["tier"] / f"{t['solver']}.jsonl"


def done_ids() -> set:
    ids = set()
    for f in (OUT / "runs").rglob("*.jsonl"):
        for line in open(f):
            try:
                ids.add(json.loads(line)["task_id"])
            except Exception:
                pass
    return ids


def execute(t: dict) -> dict:
    """Run one task in this (fresh) process and return its record."""
    from phase0.multisolver_methods import NotSupported, run_method, run_to_record
    from phase0.solver_adapters import ADAPTERS, cached_version
    if t.get("cpus"):
        os.sched_setaffinity(0, set(t["cpus"]))
    cached_version(ADAPTERS[t["solver"]])          # never charged to the budget
    d, insts, refs = load_stream(Path(t["stream_file"]))
    k = t["step"]
    inst, prev_inst, prev = insts[k], insts[k - 1] if k else None, refs[k - 1] if k else None
    ru0s, ru0c = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    w0 = time.monotonic()
    rec = {"task_id": task_id(t), **{k_: v for k_, v in t.items() if k_ not in ("stream_file", "cpus")}}
    try:
        run = run_method(t["method"], t["solver"], inst, prev, prev_inst, t["budget"], t["workers"], t["seed"])
        rec.update(run_to_record(run))
        sched = rec.pop("schedule", None)
        # compact final schedule (starts in canonical op order) for independent post-hoc validation
        rec["final_starts"] = [sched[o.op_id] for o in inst.all_ops] if sched else None
        rec["status"] = "OK" if run.validated else ("NO_SOLUTION" if run.schedule is None else "INVALID")
    except NotSupported as e:
        rec.update({"status": "NOT_SUPPORTED", "error": str(e)})
    except Exception as e:
        rec.update({"status": "ERROR", "error": f"{type(e).__name__}: {e}"[:500]})
    ru1s, ru1c = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    rec.update({
        "wall_s": time.monotonic() - w0,
        "cpu_self_s": (ru1s.ru_utime + ru1s.ru_stime) - (ru0s.ru_utime + ru0s.ru_stime),
        "cpu_children_s": (ru1c.ru_utime + ru1c.ru_stime) - (ru0c.ru_utime + ru0c.ru_stime),
        "peak_rss_mb_self": ru1s.ru_maxrss / 1024, "peak_rss_mb_children": ru1c.ru_maxrss / 1024,
        "instance_hash": d["steps"][k]["hash"], "delta_kind": inst.delta_kind, "n_ops": len(inst.all_ops),
        "host": socket.gethostname(), "rev": t.get("rev"), "loadavg_1m": os.getloadavg()[0],
    })
    return rec
