"""Solver-independent view of a dynamic job-shop instance (multisolver phase).

Reuses the validated `streams.Instance` as the single source of truth (no
duplicate representation); adds what every solver backend needs:

  * canonical JSON serialization + a stable SHA-256 instance hash, so every
    solver provably receives byte-identical data;
  * valid per-operation time bounds (head = earliest start, latest start
    given horizon H), shared by the CP and MILP models so both search the
    same domain (H = Instance.horizon, the bound the CP-SAT research model
    already uses);
  * an exhaustive exact oracle for tiny instances (enumerates machine orders,
    builds the earliest schedule for each), written without any solver code.

Semantics, identical to phase0/schedule_validator.check_schedule: integer
starts >= job release date; job precedence; half-open machine intervals
disjoint from each other and from outages; committed operations start
exactly at their committed time; objective = makespan. Zero-duration
operations occupy no machine time.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass

from .streams import Instance, Job, Operation, Outage

Solution = dict[str, int]


def to_canonical_dict(inst: Instance) -> dict:
    return {
        "index": inst.index, "num_machines": inst.num_machines, "delta_kind": inst.delta_kind,
        "severity": inst.severity,
        "jobs": [{"job_id": j.job_id, "release_date": j.release_date,
                  "ops": [[o.op_id, o.machine, o.duration] for o in j.ops]} for j in inst.jobs],
        "outages": [[o.machine, o.start, o.end] for o in inst.outages],
        "frozen_starts": {k: inst.frozen_starts[k] for k in sorted(inst.frozen_starts)},
        "touched_ops": sorted(inst.touched_ops),
    }


def from_canonical_dict(d: dict) -> Instance:
    jobs = tuple(Job(job_id=j["job_id"], release_date=j.get("release_date", 0),
                     ops=tuple(Operation(op_id=o[0], machine=o[1], duration=o[2]) for o in j["ops"]))
                 for j in d["jobs"])
    fs = dict(d.get("frozen_starts", {}))
    return Instance(index=d["index"], num_machines=d["num_machines"], jobs=jobs,
                    outages=tuple(Outage(*o) for o in d.get("outages", [])),
                    touched_ops=frozenset(d.get("touched_ops", [])), delta_kind=d.get("delta_kind", "base"),
                    severity=d.get("severity", "medium"), frozen_ops=frozenset(fs), frozen_starts=fs)


def instance_hash(inst: Instance) -> str:
    """Hash of the physical problem only (jobs, outages, commitments)."""
    d = to_canonical_dict(inst)
    phys = {k: d[k] for k in ("num_machines", "jobs", "outages", "frozen_starts")}
    return hashlib.sha256(json.dumps(phys, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class OpBounds:
    op_id: str
    job_id: str
    machine: int
    duration: int
    lb: int          # earliest start (release + job predecessors, or the committed time)
    ub: int          # latest start for any schedule with makespan <= H


def op_bounds(inst: Instance, H: int | None = None) -> tuple[list[OpBounds], int]:
    H = inst.horizon if H is None else H
    out = []
    for job in inst.jobs:
        t = job.release_date
        tails = [sum(o.duration for o in job.ops[k:]) for k in range(len(job.ops))]
        for k, op in enumerate(job.ops):
            if op.op_id in inst.frozen_starts:
                c = inst.frozen_starts[op.op_id]
                lb = ub = c
            else:
                lb, ub = t, H - tails[k]
            if lb > ub:
                raise ValueError(f"{op.op_id}: empty start domain [{lb},{ub}] (H={H})")
            out.append(OpBounds(op.op_id, job.job_id, op.machine, op.duration, lb, ub))
            t = lb + op.duration
    return out, H


def model_size_hint(inst: Instance) -> dict:
    ops = inst.all_ops
    by_m: dict[int, int] = {}
    for o in ops:
        if o.duration > 0:
            by_m[o.machine] = by_m.get(o.machine, 0) + 1
    pairs = sum(n * (n - 1) // 2 for n in by_m.values())
    return {"n_ops": len(ops), "n_jobs": len(inst.jobs), "n_machines": inst.num_machines,
            "n_outages": len(inst.outages), "machine_pairs": pairs, "n_frozen": len(inst.frozen_starts)}


# ---------------------------------------------------------------- exact oracle

def _earliest_schedule(inst: Instance, orders: dict[int, list[str]]) -> Solution | None:
    """Earliest-start schedule respecting job order, the given machine orders,
    releases, outages and commitments; None if the orders are cyclic or a
    commitment cannot be met."""
    dur = {o.op_id: o.duration for o in inst.all_ops}
    mach = {o.op_id: o.machine for o in inst.all_ops}
    job_pred, release = {}, {}
    for job in inst.jobs:
        for k, op in enumerate(job.ops):
            job_pred[op.op_id] = job.ops[k - 1].op_id if k else None
            release[op.op_id] = job.release_date
    mach_pred = {}
    for seq in orders.values():
        for k, v in enumerate(seq):
            mach_pred[v] = seq[k - 1] if k else None
    outages = {}
    for o in inst.outages:
        if o.end > o.start:
            outages.setdefault(o.machine, []).append((o.start, o.end))
    for v in outages.values():
        v.sort()
    S: Solution = {}
    remaining = set(dur)
    while remaining:
        ready = [v for v in remaining
                 if (job_pred[v] is None or job_pred[v] in S) and (mach_pred.get(v) is None or mach_pred[v] in S)]
        if not ready:
            return None
        for v in ready:
            t = release[v]
            if job_pred[v] is not None:
                t = max(t, S[job_pred[v]] + dur[job_pred[v]])
            if mach_pred.get(v) is not None:
                t = max(t, S[mach_pred[v]] + dur[mach_pred[v]])
            if dur[v] > 0:
                for a, b in outages.get(mach[v], []):
                    if t < b and t + dur[v] > a:
                        t = b
            if v in inst.frozen_starts:
                c = inst.frozen_starts[v]
                if t > c:
                    return None
                t = c
                if dur[v] > 0 and any(t < b and t + dur[v] > a for a, b in outages.get(mach[v], [])):
                    return None
            S[v] = t
            remaining.discard(v)
    return S


def exhaustive_optimum(inst: Instance, max_combos: int = 2_000_000) -> tuple[int, Solution]:
    """Exact optimum by enumerating every machine order (regular objective:
    the earliest schedule of the optimal orders is optimal). Commitments make
    some earliest schedules non-left-justified; the enumeration still covers
    them because each order set yields its unique earliest feasible schedule."""
    from .schedule_validator import ScheduleError, check_schedule
    by_m: dict[int, list[str]] = {}
    for o in inst.all_ops:
        if o.duration > 0:
            by_m.setdefault(o.machine, []).append(o.op_id)
    machines = sorted(by_m)
    total = 1
    for m in machines:
        for k in range(2, len(by_m[m]) + 1):
            total *= k
    if total > max_combos:
        raise ValueError(f"too many order combinations ({total})")
    best, best_S = None, None
    for perms in itertools.product(*[itertools.permutations(by_m[m]) for m in machines]):
        S = _earliest_schedule(inst, {m: list(p) for m, p in zip(machines, perms)})
        if S is None:
            continue
        try:
            obj = check_schedule(inst, S)
        except ScheduleError:
            continue
        if best is None or obj < best:
            best, best_S = obj, S
    if best is None:
        raise ValueError("instance infeasible")
    return best, best_S
