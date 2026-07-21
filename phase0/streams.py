"""Agent-generated problem streams for dynamic job-shop scheduling.

A stream is a base job-shop instance followed by a sequence of deltas
(job arrivals, cancellations, duration jitter, machine outages, and the
ICAPS-extension deltas below). Each element of the stream is a full
instance; consecutive instances share most of their structure, which is the
premise boot_cold exploits.

Everything is seeded and deterministic so streams are reproducible and can
be versioned as a benchmark.

Backward compatibility: `generate_stream(StreamConfig(...))` with a
StreamConfig that does not set any of the new `p_*` weights (all default to
0.0) or `severity` (defaults to "medium", which reproduces the exact
pre-extension numeric formulas for the original four deltas) produces
byte-identical streams to the pre-ICAPS version of this module. Verified by
a golden-stream regression test in tests/test_phase0.py.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Literal

Severity = Literal["low", "medium", "high", "extreme"]

# Generic magnitude multiplier used by severity-scaled deltas. medium=1.0 is
# calibrated so the ORIGINAL four deltas' medium-severity formulas match the
# pre-extension code exactly (see per-delta functions below).
SEVERITY_SCALE: dict[Severity, float] = {
    "low": 0.5, "medium": 1.0, "high": 2.0, "extreme": 3.5,
}


@dataclass(frozen=True)
class Operation:
    op_id: str          # stable across the stream, e.g. "j3_o1"
    machine: int
    duration: int


@dataclass(frozen=True)
class Job:
    job_id: str
    ops: tuple[Operation, ...]  # processed in sequence
    # ICAPS extension fields, additive with neutral defaults so existing
    # callers that never set them are unaffected (no due date, unit weight,
    # released at t=0 -- makespan-only code paths ignore all three).
    due_date: int | None = None
    weight: float = 1.0
    release_date: int = 0


@dataclass(frozen=True)
class Outage:
    machine: int
    start: int
    end: int


@dataclass(frozen=True)
class Instance:
    index: int                      # position in the stream
    num_machines: int
    jobs: tuple[Job, ...]
    outages: tuple[Outage, ...] = ()
    # op_ids belonging to jobs touched by the delta that produced this
    # instance (empty for the base instance). Used by the delta-centric
    # destroy operator and by ICAPS runners to compute stability metrics.
    touched_ops: frozenset[str] = frozenset()
    delta_kind: str = "base"
    severity: str = "medium"
    # op_ids that must keep their previous start time (partial_schedule_freeze).
    # Empty for every delta except partial_schedule_freeze.
    frozen_ops: frozenset[str] = frozenset()
    # start times for frozen_ops, required by the model builder / bootstrap
    # to actually pin them. Empty unless frozen_ops is non-empty.
    frozen_starts: dict = field(default_factory=dict)

    @property
    def all_ops(self) -> list[Operation]:
        return [op for job in self.jobs for op in job.ops]

    @property
    def horizon(self) -> int:
        # Worst case: wait out every outage, then run all ops serially.
        total = sum(op.duration for op in self.all_ops)
        outage_end = max((o.end for o in self.outages), default=0)
        return total + outage_end + 1


@dataclass
class StreamConfig:
    num_machines: int = 5
    initial_jobs: int = 10
    ops_per_job: tuple[int, int] = (3, 5)       # min, max
    duration_range: tuple[int, int] = (5, 30)
    stream_length: int = 20                     # number of deltas
    severity: Severity = "medium"
    # relative weights of the delta kinds. New (ICAPS) kinds default to 0.0
    # so they are never selected unless explicitly opted into -- this is
    # what makes the extension backward compatible.
    p_arrival: float = 0.4
    p_cancellation: float = 0.2
    p_duration_jitter: float = 0.25
    p_outage: float = 0.15
    p_batch_arrival: float = 0.0
    p_rush_job: float = 0.0
    p_machine_speed_degradation: float = 0.0
    p_due_date_change: float = 0.0
    p_priority_change: float = 0.0
    p_partial_schedule_freeze: float = 0.0
    seed: int = 0


def _random_job(rng: random.Random, cfg: StreamConfig, job_num: int,
                machines: list[int] | None = None) -> Job:
    n_ops = rng.randint(*cfg.ops_per_job)
    pool = machines if machines is not None else list(range(cfg.num_machines))
    ms = rng.sample(pool, min(n_ops, len(pool)))
    while len(ms) < n_ops:
        ms.append(rng.choice(pool))
    ops = tuple(
        Operation(
            op_id=f"j{job_num}_o{k}",
            machine=ms[k],
            duration=rng.randint(*cfg.duration_range),
        )
        for k in range(n_ops)
    )
    return Job(job_id=f"j{job_num}", ops=ops)


def _merge_outages(outages: list[Outage]) -> list[Outage]:
    """Merge overlapping/touching outages per machine. Overlapping fixed
    intervals on one machine would make the no_overlap model infeasible."""
    merged: list[Outage] = []
    by_machine: dict[int, list[Outage]] = {}
    for o in outages:
        by_machine.setdefault(o.machine, []).append(o)
    for machine, group in sorted(by_machine.items()):
        group.sort(key=lambda o: o.start)
        current = group[0]
        for o in group[1:]:
            if o.start <= current.end:
                current = Outage(machine, current.start, max(current.end, o.end))
            else:
                merged.append(current)
                current = o
        merged.append(current)
    return merged


# ---------------------------------------------------------------------------
# Per-kind delta functions. Each takes (rng, cfg, prev, next_job_num, scale)
# and returns (jobs, outages, touched, frozen_ops, frozen_starts, next_job_num).
# `scale` = SEVERITY_SCALE[cfg.severity]; scale=1.0 ("medium") reproduces the
# pre-extension numeric formula EXACTLY for the original four kinds.
# ---------------------------------------------------------------------------

def _d_arrival(rng, cfg, prev, nj, scale):
    jobs = list(prev.jobs)
    job = _random_job(rng, cfg, nj)
    jobs.append(job)
    return jobs, list(prev.outages), {op.op_id for op in job.ops}, nj + 1


def _d_cancellation(rng, cfg, prev, nj, scale):
    jobs = list(prev.jobs)
    if len(jobs) <= 2:
        return _d_arrival(rng, cfg, prev, nj, scale)
    victim = jobs.pop(rng.randrange(len(jobs)))
    victim_machines = {op.machine for op in victim.ops}
    touched = {op.op_id for j in jobs for op in j.ops if op.machine in victim_machines}
    return jobs, list(prev.outages), touched, nj


def _d_duration_jitter(rng, cfg, prev, nj, scale):
    jobs = list(prev.jobs)
    ji = rng.randrange(len(jobs))
    job = jobs[ji]
    lo, hi = cfg.duration_range
    new_ops = []
    for op in job.ops:
        factor = rng.uniform(0.6, 1.6)
        new_ops.append(replace(op, duration=max(lo, min(hi * 2, round(op.duration * factor)))))
    jobs[ji] = replace(job, ops=tuple(new_ops))
    return jobs, list(prev.outages), {op.op_id for op in new_ops}, nj


def _d_outage(rng, cfg, prev, nj, scale):
    jobs = list(prev.jobs)
    machine = rng.randrange(cfg.num_machines)
    span = sum(op.duration for j in jobs for op in j.ops) // cfg.num_machines
    start = rng.randint(0, max(1, span))
    length = rng.randint(cfg.duration_range[0] * 2, cfg.duration_range[1] * 3)
    outages = _merge_outages(list(prev.outages) + [Outage(machine, start, start + length)])
    touched = {op.op_id for j in jobs for op in j.ops if op.machine == machine}
    return jobs, outages, touched, nj


# --- new ICAPS deltas --------------------------------------------------

def _d_batch_arrival(rng, cfg, prev, nj, scale):
    """Add several jobs at once. Count scales with severity:
    low ~ 1-2, medium ~ 5% of current jobs, high ~ 10-20%, extreme ~ 30%+."""
    jobs = list(prev.jobs)
    frac = {0.5: 0.02, 1.0: 0.05, 2.0: 0.15, 3.5: 0.30}.get(scale, 0.05 * scale)
    n_new = max(2, round(frac * len(jobs)))
    touched = set()
    for _ in range(n_new):
        job = _random_job(rng, cfg, nj)
        nj += 1
        jobs.append(job)
        touched.update(op.op_id for op in job.ops)
    return jobs, list(prev.outages), touched, nj


def _d_rush_job(rng, cfg, prev, nj, scale):
    """Add one job with a tight due date and high weight -- requires the
    due-date/weighted-tardiness objective support to matter downstream;
    always feasible to *represent* regardless of which objective is used."""
    jobs = list(prev.jobs)
    job = _random_job(rng, cfg, nj)
    total_proc = sum(op.duration for op in job.ops)
    tightness = {0.5: 2.5, 1.0: 1.5, 2.0: 1.1, 3.5: 1.0}.get(scale, 1.5)
    due = max(total_proc, round(total_proc * tightness))
    job = replace(job, due_date=due, weight=3.0 * scale)
    jobs.append(job)
    return jobs, list(prev.outages), {op.op_id for op in job.ops}, nj + 1


def _d_machine_speed_degradation(rng, cfg, prev, nj, scale):
    """Slow down operations on one or more machines (a fatigued/degraded
    machine), by inflating their durations. Severity controls the slowdown
    factor and how many machines are affected."""
    jobs = list(prev.jobs)
    n_machines = max(1, round(scale / 2))
    hit = set(rng.sample(range(cfg.num_machines), min(n_machines, cfg.num_machines)))
    factor = 1.0 + 0.5 * scale
    touched = set()
    new_jobs = []
    for job in jobs:
        new_ops = []
        for op in job.ops:
            if op.machine in hit:
                new_ops.append(replace(op, duration=max(1, round(op.duration * factor))))
                touched.add(op.op_id)
            else:
                new_ops.append(op)
        new_jobs.append(replace(job, ops=tuple(new_ops)))
    return new_jobs, list(prev.outages), touched, nj


def _d_due_date_change(rng, cfg, prev, nj, scale):
    """Modify due dates for a severity-scaled fraction of jobs. Jobs without
    a due date get one assigned (based on total processing time); jobs with
    one get it tightened or loosened."""
    jobs = list(prev.jobs)
    frac = min(1.0, 0.1 * scale)
    idx = rng.sample(range(len(jobs)), max(1, round(frac * len(jobs))))
    new_jobs = list(jobs)
    touched = set()
    for ji in idx:
        job = jobs[ji]
        total_proc = sum(op.duration for op in job.ops)
        base_due = job.due_date if job.due_date is not None else round(total_proc * 1.5)
        new_due = max(total_proc, round(base_due * rng.uniform(0.6, 1.2)))
        new_jobs[ji] = replace(job, due_date=new_due)
        touched.update(op.op_id for op in job.ops)
    return new_jobs, list(prev.outages), touched, nj


def _d_priority_change(rng, cfg, prev, nj, scale):
    """Modify job weights for a severity-scaled fraction of jobs (needed for
    weighted-tardiness objectives)."""
    jobs = list(prev.jobs)
    frac = min(1.0, 0.1 * scale)
    idx = rng.sample(range(len(jobs)), max(1, round(frac * len(jobs))))
    new_jobs = list(jobs)
    touched = set()
    for ji in idx:
        job = jobs[ji]
        new_weight = max(0.1, job.weight * rng.uniform(0.5, 1.0 + scale))
        new_jobs[ji] = replace(job, weight=new_weight)
        touched.update(op.op_id for op in job.ops)
    return new_jobs, list(prev.outages), touched, nj


def _d_partial_schedule_freeze(rng, cfg, prev, nj, scale, prev_solution=None):
    """Freeze a severity-scaled prefix fraction of the previous schedule
    (operations already "executed"/committed and non-movable). Requires the
    previous instance's SOLUTION (not just structure) to know which ops to
    freeze and at what start time; if none is available (e.g. this is the
    first stream instance), degrades to a no-op delta (nothing frozen).
    low=25%, medium=50%, high=75%, extreme=90% of ops frozen, chosen as the
    earliest-starting ops in the previous solution."""
    jobs = list(prev.jobs)
    if not prev_solution:
        return jobs, list(prev.outages), set(), nj, frozenset(), {}
    frac = {0.5: 0.25, 1.0: 0.5, 2.0: 0.75, 3.5: 0.9}.get(scale, 0.5)
    all_ids = [op.op_id for job in jobs for op in job.ops if op.op_id in prev_solution]
    all_ids.sort(key=lambda oid: prev_solution[oid])
    n_freeze = round(frac * len(all_ids))
    frozen_ids = frozenset(all_ids[:n_freeze])
    frozen_starts = {oid: prev_solution[oid] for oid in frozen_ids}
    return jobs, list(prev.outages), set(), nj, frozen_ids, frozen_starts


_ORIGINAL_KINDS = ("arrival", "cancellation", "duration_jitter", "outage")
_NEW_KINDS = ("batch_arrival", "rush_job", "machine_speed_degradation",
             "due_date_change", "priority_change", "partial_schedule_freeze")
_DELTA_FN = {
    "arrival": _d_arrival,
    "cancellation": _d_cancellation,
    "duration_jitter": _d_duration_jitter,
    "outage": _d_outage,
    "batch_arrival": _d_batch_arrival,
    "rush_job": _d_rush_job,
    "machine_speed_degradation": _d_machine_speed_degradation,
    "due_date_change": _d_due_date_change,
    "priority_change": _d_priority_change,
    # partial_schedule_freeze has a different signature (needs prev_solution)
    # and is dispatched specially in _apply_delta, not via _DELTA_FN.
}
_WEIGHT_ATTR = {
    "arrival": "p_arrival", "cancellation": "p_cancellation",
    "duration_jitter": "p_duration_jitter", "outage": "p_outage",
    "batch_arrival": "p_batch_arrival", "rush_job": "p_rush_job",
    "machine_speed_degradation": "p_machine_speed_degradation",
    "due_date_change": "p_due_date_change", "priority_change": "p_priority_change",
    "partial_schedule_freeze": "p_partial_schedule_freeze",
}


def _apply_delta(
    rng: random.Random, cfg: StreamConfig, prev: Instance, next_job_num: int,
    prev_solution: dict | None = None,
) -> tuple[Instance, int]:
    kinds = _ORIGINAL_KINDS + _NEW_KINDS
    weights = [getattr(cfg, _WEIGHT_ATTR[k]) for k in kinds]
    kind = rng.choices(kinds, weights=weights, k=1)[0]
    scale = SEVERITY_SCALE[cfg.severity]

    if kind == "partial_schedule_freeze":
        jobs, outages, touched, next_job_num, frozen_ids, frozen_starts = \
            _d_partial_schedule_freeze(rng, cfg, prev, next_job_num, scale, prev_solution)
    else:
        jobs, outages, touched, next_job_num = _DELTA_FN[kind](rng, cfg, prev, next_job_num, scale)
        frozen_ids, frozen_starts = frozenset(), {}

    inst = Instance(
        index=prev.index + 1,
        num_machines=cfg.num_machines,
        jobs=tuple(jobs),
        outages=tuple(outages),
        touched_ops=frozenset(touched),
        delta_kind=kind,
        severity=cfg.severity,
        frozen_ops=frozen_ids,
        frozen_starts=dict(frozen_starts),
    )
    return inst, next_job_num


def generate_stream(cfg: StreamConfig,
                    prev_solutions: dict[int, dict] | None = None,
                    base_instance: Instance | None = None) -> list[Instance]:
    """Return [base_instance, delta_1_instance, ..., delta_N_instance].

    prev_solutions: optional {instance_index: Solution} used only by the
    partial_schedule_freeze delta to know which ops to freeze. Callers that
    don't use that delta kind (p_partial_schedule_freeze=0.0, the default)
    never need to pass this.

    base_instance: optional pre-built Instance (e.g. loaded from a static
    benchmark file via benchmark_loaders.py) to use as index 0 instead of
    randomly generating one from cfg.initial_jobs/ops_per_job/duration_range.
    Deltas are still applied on top of it using cfg's severity/weights, so a
    static benchmark instance can be turned into a dynamic stream. next job
    numbers for arrival-type deltas continue from
    len(base_instance.jobs) so IDs never collide with the loaded jobs."""
    rng = random.Random(cfg.seed)
    if base_instance is not None:
        base = replace(base_instance, index=0, severity=cfg.severity)
        next_job_num = len(base_instance.jobs)
    else:
        jobs = tuple(_random_job(rng, cfg, i) for i in range(cfg.initial_jobs))
        base = Instance(index=0, num_machines=cfg.num_machines, jobs=jobs,
                        severity=cfg.severity)
        next_job_num = cfg.initial_jobs
    stream = [base]
    for _ in range(cfg.stream_length):
        prev_sol = (prev_solutions or {}).get(stream[-1].index)
        inst, next_job_num = _apply_delta(rng, cfg, stream[-1], next_job_num, prev_sol)
        stream.append(inst)
    return stream
