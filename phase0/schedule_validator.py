"""Strict, solver-independent feasibility check for job-shop schedules.

Stricter than model_builder.validate_solution, which predates release dates
and committed operations and does not check them. Checks, in order:

  1. coverage: every operation of the instance has exactly one start time and
     no other key is present (cancelled operations must be absent);
  2. starts are integers >= 0 and >= the job's release date;
  3. job precedence: s[b] >= s[a] + p[a] for consecutive operations a, b;
  4. machine capacity: half-open intervals [s, s + p) of operations sharing a
     machine are disjoint, and none intersects an outage [start, end);
  5. commitments: every operation in instance.frozen_starts that still exists
     starts exactly at its committed time.

Returns the makespan. Uses no CP-SAT code, so it can catch modelling bugs.
"""

from __future__ import annotations

from .streams import Instance

Solution = dict[str, int]


class ScheduleError(AssertionError):
    """Raised when a schedule violates a constraint of its instance."""


def check_schedule(instance: Instance, solution: Solution) -> int:
    ops = instance.all_ops
    expected = {op.op_id for op in ops}
    if len(expected) != len(ops):
        raise ScheduleError("instance has duplicate operation ids")
    given = set(solution)
    if given != expected:
        missing = sorted(expected - given)[:5]
        extra = sorted(given - expected)[:5]
        raise ScheduleError(f"coverage: missing={missing} extra={extra}")

    for job in instance.jobs:
        for k, op in enumerate(job.ops):
            s = solution[op.op_id]
            if not isinstance(s, int) or isinstance(s, bool):
                raise ScheduleError(f"{op.op_id}: start {s!r} is not an int")
            if s < 0:
                raise ScheduleError(f"{op.op_id}: negative start {s}")
            if s < job.release_date:
                raise ScheduleError(f"{op.op_id}: start {s} before release {job.release_date}")
            if k > 0:
                prev = job.ops[k - 1]
                if s < solution[prev.op_id] + prev.duration:
                    raise ScheduleError(
                        f"precedence: {op.op_id} starts {s} before {prev.op_id} "
                        f"ends {solution[prev.op_id] + prev.duration}")

    by_machine: dict[int, list[tuple[int, int, str]]] = {}
    for op in ops:
        s = solution[op.op_id]
        by_machine.setdefault(op.machine, []).append((s, s + op.duration, op.op_id))
    for o in instance.outages:
        by_machine.setdefault(o.machine, []).append((o.start, o.end, f"outage@{o.start}"))
    for machine, spans in by_machine.items():
        spans = [sp for sp in spans if sp[1] > sp[0]]  # zero-length occupies nothing
        spans.sort()
        for (s1, e1, a), (s2, e2, b) in zip(spans, spans[1:]):
            if s2 < e1:
                raise ScheduleError(f"machine {machine}: {a} [{s1},{e1}) overlaps {b} [{s2},{e2})")

    for op_id, committed in instance.frozen_starts.items():
        if op_id in solution and solution[op_id] != committed:
            raise ScheduleError(f"commitment: {op_id} starts {solution[op_id]}, committed {committed}")

    return max((solution[op.op_id] + op.duration for op in ops), default=0)
