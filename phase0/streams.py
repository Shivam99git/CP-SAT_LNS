"""Agent-generated problem streams for dynamic job-shop scheduling.

A stream is a base job-shop instance followed by a sequence of deltas
(job arrivals, cancellations, duration jitter, machine outages). Each
element of the stream is a full instance; consecutive instances share
most of their structure, which is the premise the learned LNS exploits.

Everything is seeded and deterministic so streams are reproducible and
can be versioned as a benchmark.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Operation:
    op_id: str          # stable across the stream, e.g. "j3_o1"
    machine: int
    duration: int


@dataclass(frozen=True)
class Job:
    job_id: str
    ops: tuple[Operation, ...]  # processed in sequence


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
    # destroy operator.
    touched_ops: frozenset[str] = frozenset()
    delta_kind: str = "base"

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
    # relative weights of the delta kinds
    p_arrival: float = 0.4
    p_cancellation: float = 0.2
    p_duration_jitter: float = 0.25
    p_outage: float = 0.15
    seed: int = 0


def _random_job(rng: random.Random, cfg: StreamConfig, job_num: int) -> Job:
    n_ops = rng.randint(*cfg.ops_per_job)
    machines = rng.sample(range(cfg.num_machines), min(n_ops, cfg.num_machines))
    while len(machines) < n_ops:
        machines.append(rng.randrange(cfg.num_machines))
    ops = tuple(
        Operation(
            op_id=f"j{job_num}_o{k}",
            machine=machines[k],
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


def _apply_delta(
    rng: random.Random, cfg: StreamConfig, prev: Instance, next_job_num: int
) -> tuple[Instance, int]:
    kinds = ["arrival", "cancellation", "duration_jitter", "outage"]
    weights = [cfg.p_arrival, cfg.p_cancellation, cfg.p_duration_jitter, cfg.p_outage]
    kind = rng.choices(kinds, weights=weights, k=1)[0]

    jobs = list(prev.jobs)
    outages = list(prev.outages)
    touched: set[str] = set()

    if kind == "cancellation" and len(jobs) <= 2:
        kind = "arrival"  # never shrink below 2 jobs

    if kind == "arrival":
        job = _random_job(rng, cfg, next_job_num)
        next_job_num += 1
        jobs.append(job)
        touched.update(op.op_id for op in job.ops)
    elif kind == "cancellation":
        victim = jobs.pop(rng.randrange(len(jobs)))
        # neighbours on the victim's machines are the perturbed region
        victim_machines = {op.machine for op in victim.ops}
        touched.update(
            op.op_id for j in jobs for op in j.ops if op.machine in victim_machines
        )
    elif kind == "duration_jitter":
        ji = rng.randrange(len(jobs))
        job = jobs[ji]
        new_ops = []
        for op in job.ops:
            lo, hi = cfg.duration_range
            factor = rng.uniform(0.6, 1.6)
            new_ops.append(
                replace(op, duration=max(lo, min(hi * 2, round(op.duration * factor))))
            )
        jobs[ji] = Job(job_id=job.job_id, ops=tuple(new_ops))
        touched.update(op.op_id for op in new_ops)
    else:  # outage
        machine = rng.randrange(cfg.num_machines)
        # place the outage somewhere inside the rough schedule span
        span = sum(op.duration for j in jobs for op in j.ops) // cfg.num_machines
        start = rng.randint(0, max(1, span))
        length = rng.randint(cfg.duration_range[0] * 2, cfg.duration_range[1] * 3)
        outages.append(Outage(machine=machine, start=start, end=start + length))
        outages = _merge_outages(outages)
        touched.update(
            op.op_id for j in jobs for op in j.ops if op.machine == machine
        )

    inst = Instance(
        index=prev.index + 1,
        num_machines=cfg.num_machines,
        jobs=tuple(jobs),
        outages=tuple(outages),
        touched_ops=frozenset(touched),
        delta_kind=kind,
    )
    return inst, next_job_num


def generate_stream(cfg: StreamConfig) -> list[Instance]:
    """Return [base_instance, delta_1_instance, ..., delta_N_instance]."""
    rng = random.Random(cfg.seed)
    jobs = tuple(_random_job(rng, cfg, i) for i in range(cfg.initial_jobs))
    base = Instance(index=0, num_machines=cfg.num_machines, jobs=jobs)
    stream = [base]
    next_job_num = cfg.initial_jobs
    for _ in range(cfg.stream_length):
        inst, next_job_num = _apply_delta(rng, cfg, stream[-1], next_job_num)
        stream.append(inst)
    return stream
