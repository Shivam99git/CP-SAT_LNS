"""RCPSP (Resource-Constrained Project Scheduling) instance dataclasses.

A second scheduling domain for cross-domain transfer evidence (the job-shop
+ knapsack pilot already showed the reuse-floor idea transfers across a
scheduling and a non-scheduling combinatorial domain; RCPSP tests it within
a second, more general scheduling structure: activities may need MULTIPLE
concurrent renewable resources, not just one machine, and precedence forms
a general DAG rather than simple per-job chains).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Activity:
    activity_id: str
    duration: int
    resource_usage: dict[str, int]           # resource_id -> amount required
    predecessors: tuple[str, ...] = ()        # activity_ids that must finish first


@dataclass(frozen=True)
class RInstance:
    index: int
    resources: dict[str, int]                 # resource_id -> renewable capacity
    activities: tuple[Activity, ...]
    touched_activities: frozenset[str] = frozenset()
    delta_kind: str = "base"
    severity: str = "medium"

    @property
    def activity_by_id(self) -> dict[str, Activity]:
        return {a.activity_id: a for a in self.activities}

    @property
    def horizon(self) -> int:
        return sum(a.duration for a in self.activities) + 1
