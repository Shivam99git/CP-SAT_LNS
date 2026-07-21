"""RCPSP streams: a base project instance + deltas.

Implemented deltas (the "minimal robust version" per the task's own
allowance when full scope is too large for one pass):
  * duration_jitter          -- perturb one activity's duration
  * resource_capacity_reduction -- reduce one resource's capacity
  * activity_insertion       -- add a new activity with random predecessors
                                 among existing (index-ordered, so the
                                 precedence graph is acyclic by construction)
  * activity_cancellation    -- remove one activity (successors simply lose
                                 that precedence edge -- model_builder
                                 already tolerates dangling predecessor ids)

NOT implemented (documented TODO, per docs/icaps_experiment_plan.md):
  * precedence_change  -- reassigning predecessors risks introducing cycles;
                           needs a topological-order-preserving redraw, not
                           implemented in this pass.
  * partial_schedule_freeze -- would need the same prev_solution-threading
                           pattern as the JSSP version; not implemented here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .instances import Activity, RInstance

SEVERITY_SCALE = {"low": 0.5, "medium": 1.0, "high": 2.0, "extreme": 3.5}


@dataclass
class RStreamConfig:
    num_activities: int = 15
    num_resources: int = 2
    resource_capacity: tuple[int, int] = (4, 8)
    duration_range: tuple[int, int] = (2, 10)
    max_predecessors: int = 2
    max_resources_per_activity: int = 2
    resource_amount_range: tuple[int, int] = (1, 3)
    stream_length: int = 10
    severity: str = "medium"
    p_duration_jitter: float = 0.35
    p_resource_capacity_reduction: float = 0.2
    p_activity_insertion: float = 0.3
    p_activity_cancellation: float = 0.15
    seed: int = 0


def _random_activity(rng: random.Random, cfg: RStreamConfig, act_num: int,
                     resource_ids: list[str], existing_ids: list[str]) -> Activity:
    n_pred = rng.randint(0, min(cfg.max_predecessors, len(existing_ids)))
    preds = tuple(sorted(rng.sample(existing_ids, n_pred))) if n_pred else ()
    n_res = rng.randint(1, min(cfg.max_resources_per_activity, len(resource_ids)))
    used = rng.sample(resource_ids, n_res)
    usage = {r: rng.randint(*cfg.resource_amount_range) for r in used}
    return Activity(
        activity_id=f"a{act_num}",
        duration=rng.randint(*cfg.duration_range),
        resource_usage=usage,
        predecessors=preds,
    )


def generate_rcpsp_instance(cfg: RStreamConfig) -> RInstance:
    rng = random.Random(cfg.seed)
    resource_ids = [f"r{i}" for i in range(cfg.num_resources)]
    resources = {r: rng.randint(*cfg.resource_capacity) for r in resource_ids}
    activities: list[Activity] = []
    for i in range(cfg.num_activities):
        act = _random_activity(rng, cfg, i, resource_ids,
                               [a.activity_id for a in activities])
        activities.append(act)
    return RInstance(index=0, resources=resources, activities=tuple(activities))


def _d_duration_jitter(rng, cfg, prev, next_num, scale):
    acts = list(prev.activities)
    if not acts:
        return acts, prev.resources, set(), next_num
    i = rng.randrange(len(acts))
    lo, hi = cfg.duration_range
    factor = rng.uniform(1 - 0.3 * scale, 1 + 0.3 * scale)
    acts[i] = replace(acts[i], duration=max(1, min(hi * 3, round(acts[i].duration * factor))))
    return acts, prev.resources, {acts[i].activity_id}, next_num


def _d_resource_capacity_reduction(rng, cfg, prev, next_num, scale):
    resources = dict(prev.resources)
    r = rng.choice(list(resources))
    max_single_usage = max(
        (a.resource_usage.get(r, 0) for a in prev.activities), default=1
    )
    factor = max(0.3, 1 - 0.15 * scale)
    new_cap = max(max_single_usage, round(resources[r] * factor))
    resources[r] = new_cap
    touched = {a.activity_id for a in prev.activities if a.resource_usage.get(r, 0) > 0}
    return list(prev.activities), resources, touched, next_num


def _d_activity_insertion(rng, cfg, prev, next_num, scale):
    acts = list(prev.activities)
    resource_ids = list(prev.resources)
    n_new = max(1, round(scale))
    touched = set()
    for _ in range(n_new):
        act = _random_activity(rng, cfg, next_num, resource_ids,
                               [a.activity_id for a in acts])
        next_num += 1
        acts.append(act)
        touched.add(act.activity_id)
    return acts, prev.resources, touched, next_num


def _d_activity_cancellation(rng, cfg, prev, next_num, scale):
    acts = list(prev.activities)
    if len(acts) <= 2:
        return _d_activity_insertion(rng, cfg, prev, next_num, scale)
    victim = acts.pop(rng.randrange(len(acts)))
    touched = {a.activity_id for a in acts if victim.activity_id in a.predecessors}
    return acts, prev.resources, touched, next_num


_DELTA_FN = {
    "duration_jitter": _d_duration_jitter,
    "resource_capacity_reduction": _d_resource_capacity_reduction,
    "activity_insertion": _d_activity_insertion,
    "activity_cancellation": _d_activity_cancellation,
}
_WEIGHT_ATTR = {
    "duration_jitter": "p_duration_jitter",
    "resource_capacity_reduction": "p_resource_capacity_reduction",
    "activity_insertion": "p_activity_insertion",
    "activity_cancellation": "p_activity_cancellation",
}


def _apply_delta(rng, cfg: RStreamConfig, prev: RInstance, next_num: int):
    kinds = list(_DELTA_FN)
    weights = [getattr(cfg, _WEIGHT_ATTR[k]) for k in kinds]
    kind = rng.choices(kinds, weights=weights, k=1)[0]
    scale = SEVERITY_SCALE[cfg.severity]
    acts, resources, touched, next_num = _DELTA_FN[kind](rng, cfg, prev, next_num, scale)
    inst = RInstance(
        index=prev.index + 1, resources=resources, activities=tuple(acts),
        touched_activities=frozenset(touched), delta_kind=kind, severity=cfg.severity,
    )
    return inst, next_num


def generate_rcpsp_stream(cfg: RStreamConfig, base_instance: RInstance | None = None) -> list[RInstance]:
    """Return [base, delta_1, ..., delta_N].

    base_instance: optional pre-built RInstance (e.g. loaded from a real
    PSPLIB/.rcp benchmark file via rcpsp.benchmark_loaders) to use as index 0
    instead of randomly generating one from cfg. Deltas are still applied on
    top of it using cfg's severity/weights, mirroring the JSSP
    streams.generate_stream(base_instance=...) pattern. New activity IDs for
    activity_insertion must never collide with existing ones -- computed
    defensively by scanning every existing "a<int>" id and starting one past
    the max found, rather than trusting len(activities) to predict a free
    id (which silently breaks if a loader's ID convention isn't a dense
    0..n-1 range matching generation order -- found 2026-07-12 via a 1-indexed
    loader colliding on a real instance's last activity id).
    """
    rng = random.Random(cfg.seed)
    if base_instance is not None:
        base = replace(base_instance, index=0, severity=cfg.severity)
        existing_nums = []
        for a in base_instance.activities:
            if a.activity_id.startswith("a") and a.activity_id[1:].isdigit():
                existing_nums.append(int(a.activity_id[1:]))
        next_num = (max(existing_nums) + 1) if existing_nums else len(base_instance.activities)
    else:
        base = generate_rcpsp_instance(cfg)
        next_num = cfg.num_activities
    stream = [base]
    for _ in range(cfg.stream_length):
        inst, next_num = _apply_delta(rng, cfg, stream[-1], next_num)
        ids = [a.activity_id for a in inst.activities]
        assert len(ids) == len(set(ids)), (
            f"duplicate activity_id introduced at stream step {inst.index} "
            f"(delta={inst.delta_kind}): {[i for i in ids if ids.count(i) > 1]}"
        )
        stream.append(inst)
    return stream
