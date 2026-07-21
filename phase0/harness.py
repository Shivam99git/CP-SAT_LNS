"""Outer-loop LNS harness around CP-SAT.

Each LNS round: a policy picks an arm (destroy strategy x size), the chosen
subset of operations is destroyed while every other operation keeps its
incumbent *machine order* (start times stay free so the schedule can
left-shift), CP-SAT repairs within a time slice, and the round is logged as
a (context, arm, reward) tuple. Hill-climbing acceptance: the incumbent
never worsens (the incumbent always satisfies the order chains, so a round
can only improve or stall).
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field

from .model_builder import Solution, build_model, solve
from .streams import Instance, Operation

# ---------------------------------------------------------------------------
# Destroy arms
# ---------------------------------------------------------------------------

DESTROY_SIZES = (0.10, 0.25, 0.40)  # fraction of operations unfrozen
# Original basic strategies plus schedule-aware ones added for the pre-learning
# neighborhood-quality diagnostic. Kept in one tuple so ARMS stays the full
# cross-product; no old arm is removed (backward compatible). Size 0.60 was
# considered for the structured strategies but skipped to avoid a per-strategy
# size refactor of ARMS — the diagnostic only exercises the *_40 arms.
STRATEGIES = (
    "random", "machine", "critical", "delta",        # original
    "bottleneck", "critical_block", "delta_expand",  # schedule-aware
    "late_jobs", "outage_window",
)


@dataclass(frozen=True)
class Arm:
    strategy: str
    size: float

    @property
    def name(self) -> str:
        return f"{self.strategy}_{int(self.size * 100)}"


ARMS: tuple[Arm, ...] = tuple(
    Arm(strategy=s, size=z) for s in STRATEGIES for z in DESTROY_SIZES
)


def _critical_path_ops(instance: Instance, solution: Solution) -> list[str]:
    """Walk back from the op that finishes last, following tight
    predecessors (job or machine) to approximate the critical path."""
    job_pred: dict[str, Operation] = {}
    op_by_id: dict[str, Operation] = {}
    for job in instance.jobs:
        for a, b in zip(job.ops, job.ops[1:]):
            job_pred[b.op_id] = a
        for op in job.ops:
            op_by_id[op.op_id] = op

    machine_ops: dict[int, list[Operation]] = {}
    for op in op_by_id.values():
        machine_ops.setdefault(op.machine, []).append(op)

    last = max(op_by_id.values(), key=lambda op: solution[op.op_id] + op.duration)
    path = []
    current: Operation | None = last
    seen = set()
    while current is not None and current.op_id not in seen:
        path.append(current.op_id)
        seen.add(current.op_id)
        start = solution[current.op_id]
        nxt = None
        pred = job_pred.get(current.op_id)
        if pred is not None and solution[pred.op_id] + pred.duration == start:
            nxt = pred
        else:
            for op in machine_ops[current.machine]:
                if op.op_id != current.op_id and solution[op.op_id] + op.duration == start:
                    nxt = op
                    break
        current = nxt
    return path


# ---------------------------------------------------------------------------
# Schedule-aware destroy helpers
#
# All helpers are deterministic (no RNG); randomness is confined to the final
# top-up fallback in `_top_up_structured`. Every op_id they emit is drawn from
# the current instance, so selected destroy sets always reference live ops.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _OpMaps:
    op_by_id: dict[str, Operation]
    job_ops: dict[str, tuple[str, ...]]   # job_id -> ordered op_ids
    job_of_op: dict[str, str]             # op_id -> job_id
    pos_in_job: dict[str, int]            # op_id -> index within its job
    ops_by_machine: dict[int, list[str]]  # machine -> op_ids (input order)


def _op_maps(instance: Instance) -> _OpMaps:
    """Precompute the lookups the structured strategies share, once per call."""
    op_by_id: dict[str, Operation] = {}
    job_ops: dict[str, tuple[str, ...]] = {}
    job_of_op: dict[str, str] = {}
    pos_in_job: dict[str, int] = {}
    ops_by_machine: dict[int, list[str]] = {}
    for job in instance.jobs:
        job_ops[job.job_id] = tuple(op.op_id for op in job.ops)
        for i, op in enumerate(job.ops):
            op_by_id[op.op_id] = op
            job_of_op[op.op_id] = job.job_id
            pos_in_job[op.op_id] = i
            ops_by_machine.setdefault(op.machine, []).append(op.op_id)
    return _OpMaps(op_by_id, job_ops, job_of_op, pos_in_job, ops_by_machine)


def _job_neighbors(maps: _OpMaps, op_id: str) -> list[str]:
    """Immediate predecessor and successor op_ids within the same job."""
    ids = maps.job_ops[maps.job_of_op[op_id]]
    i = maps.pos_in_job[op_id]
    out: list[str] = []
    if i > 0:
        out.append(ids[i - 1])
    if i + 1 < len(ids):
        out.append(ids[i + 1])
    return out


def _machine_order(instance: Instance, solution: Solution) -> dict[int, list[str]]:
    """machine -> op_ids sorted by incumbent start time (tie-broken by id)."""
    by_machine: dict[int, list[str]] = {}
    for op in instance.all_ops:
        by_machine.setdefault(op.machine, []).append(op.op_id)
    for m in by_machine:
        by_machine[m].sort(key=lambda oid: (solution[oid], oid))
    return by_machine


def _machine_neighbors(
    order_map: dict[int, list[str]], maps: _OpMaps, op_id: str
) -> list[str]:
    """Predecessor/successor of op_id on its machine, in incumbent start order."""
    seq = order_map.get(maps.op_by_id[op_id].machine, [])
    try:
        i = seq.index(op_id)
    except ValueError:
        return []
    out: list[str] = []
    if i > 0:
        out.append(seq[i - 1])
    if i + 1 < len(seq):
        out.append(seq[i + 1])
    return out


def _ops_near_time(
    instance: Instance, solution: Solution, center_time: float, k: int,
    exclude: set[str] = frozenset(),
) -> list[str]:
    """Up to k op_ids whose incumbent start is closest to center_time."""
    cands = [op.op_id for op in instance.all_ops if op.op_id not in exclude]
    cands.sort(key=lambda oid: (abs(solution[oid] - center_time), oid))
    return cands[:k]


def _top_up_structured(
    picked: set[str], candidates: list[str], all_ops: list[Operation],
    k: int, rng: random.Random,
) -> set[str]:
    """Fill `picked` up to size k: first from `candidates` in their given
    (deterministic) order, then — only if still short — at random from the
    remaining ops. Random is strictly the last resort, per the design intent
    that structured strategies stay structured wherever candidates exist."""
    for oid in candidates:
        if len(picked) >= k:
            break
        picked.add(oid)
    if len(picked) < k:
        rest = [op.op_id for op in all_ops if op.op_id not in picked]
        if rest:
            picked.update(rng.sample(rest, min(k - len(picked), len(rest))))
    return picked


def select_destroy_set(
    arm: Arm, instance: Instance, solution: Solution, rng: random.Random
) -> set[str]:
    """Return the op_ids to unfreeze for this round."""
    all_ops = instance.all_ops
    k = max(2, math.ceil(len(all_ops) * arm.size))

    if arm.strategy == "random":
        chosen = rng.sample(all_ops, min(k, len(all_ops)))
        return {op.op_id for op in chosen}

    if arm.strategy == "machine":
        machines = list(range(instance.num_machines))
        rng.shuffle(machines)
        picked: set[str] = set()
        for m in machines:
            picked.update(op.op_id for op in all_ops if op.machine == m)
            if len(picked) >= k:
                break
        return picked

    if arm.strategy == "critical":
        path = _critical_path_ops(instance, solution)
        picked = set(path[:k])
        if len(picked) < k:  # top up with random ops
            rest = [op.op_id for op in all_ops if op.op_id not in picked]
            picked.update(rng.sample(rest, min(k - len(picked), len(rest))))
        return picked

    if arm.strategy == "delta":
        picked = {op_id for op_id in instance.touched_ops if op_id in
                  {op.op_id for op in all_ops}}
        if len(picked) > k:
            picked = set(rng.sample(sorted(picked), k))
        elif len(picked) < k:
            rest = [op.op_id for op in all_ops if op.op_id not in picked]
            picked.update(rng.sample(rest, min(k - len(picked), len(rest))))
        return picked

    # --- schedule-aware strategies -----------------------------------------

    if arm.strategy == "bottleneck":
        # Load = total processing duration per machine (independent of idle
        # gaps, so it flags the genuinely over-subscribed machine). Take that
        # machine's ops in incumbent start order (a contiguous block), then
        # spill onto the next-most-loaded machines until k is reached.
        maps = _op_maps(instance)
        order_map = _machine_order(instance, solution)
        load = {m: sum(maps.op_by_id[oid].duration for oid in ids)
                for m, ids in maps.ops_by_machine.items()}
        machines_by_load = sorted(load, key=lambda m: (-load[m], m))
        candidates: list[str] = []
        for m in machines_by_load:
            candidates.extend(order_map.get(m, []))
        return _top_up_structured(set(), candidates, all_ops, k, rng)

    if arm.strategy == "critical_block":
        # Grow a connected block outward from the critical path along job and
        # machine adjacency (BFS), then top up with ops nearest in start time
        # to the makespan tail. Random only if structure runs out.
        maps = _op_maps(instance)
        order_map = _machine_order(instance, solution)
        path = _critical_path_ops(instance, solution)
        picked = set()
        queue: list[str] = []
        for oid in path:
            if oid not in picked:
                picked.add(oid)
                queue.append(oid)
            if len(picked) >= k:
                break
        idx = 0
        while len(picked) < k and idx < len(queue):
            oid = queue[idx]
            idx += 1
            for nb in _job_neighbors(maps, oid) + _machine_neighbors(order_map, maps, oid):
                if nb not in picked:
                    picked.add(nb)
                    queue.append(nb)
                    if len(picked) >= k:
                        break
        near: list[str] = []
        if len(picked) < k and path:
            near = _ops_near_time(instance, solution, solution[path[0]], k, exclude=picked)
        return _top_up_structured(picked, near, all_ops, k, rng)

    if arm.strategy == "delta_expand":
        # Grow outward from the ops the last stream delta touched. For outage
        # deltas, also pull in the outage machine's ops. If nothing was touched
        # (e.g. the base instance), defer to critical_block rather than random.
        maps = _op_maps(instance)
        order_map = _machine_order(instance, solution)
        touched = [oid for oid in instance.touched_ops if oid in maps.op_by_id]
        if not touched:
            return select_destroy_set(Arm("critical_block", arm.size),
                                      instance, solution, rng)
        picked = set()
        queue: list[str] = []
        for oid in touched:
            if oid not in picked:
                picked.add(oid)
                queue.append(oid)
            if len(picked) >= k:
                break
        if instance.delta_kind == "outage" and instance.outages:
            outage_machines = {o.machine for o in instance.outages}
            for op in all_ops:
                if len(picked) >= k:
                    break
                if op.machine in outage_machines and op.op_id not in picked:
                    picked.add(op.op_id)
                    queue.append(op.op_id)
        idx = 0
        while len(picked) < k and idx < len(queue):
            oid = queue[idx]
            idx += 1
            neigh = (_job_neighbors(maps, oid)
                     + _machine_neighbors(order_map, maps, oid)
                     + _ops_near_time(instance, solution, solution[oid], 4, exclude=picked))
            for nb in neigh:
                if nb not in picked:
                    picked.add(nb)
                    queue.append(nb)
                    if len(picked) >= k:
                        break
        return _top_up_structured(picked, [], all_ops, k, rng)

    if arm.strategy == "late_jobs":
        # Target the jobs that finish latest in the incumbent (the ones on or
        # near the makespan), taking all their ops, then expanding onto the
        # same machines if still short.
        maps = _op_maps(instance)
        order_map = _machine_order(instance, solution)
        completion = {
            job.job_id: max(solution[op.op_id] + op.duration for op in job.ops)
            for job in instance.jobs
        }
        jobs_sorted = sorted(instance.jobs,
                             key=lambda j: (-completion[j.job_id], j.job_id))
        candidates: list[str] = []
        for job in jobs_sorted:
            candidates.extend(op.op_id for op in job.ops)
        picked = set()
        for oid in candidates:
            if len(picked) >= k:
                break
            picked.add(oid)
        if len(picked) < k:
            expand: list[str] = []
            for oid in list(picked):
                expand.extend(_machine_neighbors(order_map, maps, oid))
            return _top_up_structured(picked, expand, all_ops, k, rng)
        return picked

    if arm.strategy == "outage_window":
        # Specialised outage repair: unfreeze ops whose scheduled interval
        # overlaps an expanded window around each outage. No outage => defer to
        # delta_expand (never plain random).
        if not instance.outages:
            return select_destroy_set(Arm("delta_expand", arm.size),
                                      instance, solution, rng)
        maps = _op_maps(instance)
        order_map = _machine_order(instance, solution)
        margin = max(1, round(sum(op.duration for op in all_ops) / max(1, len(all_ops))))
        starts = [o.start for o in instance.outages]
        picked = set()
        for outage in instance.outages:
            lo, hi = outage.start - margin, outage.end + margin
            for oid in order_map.get(outage.machine, []):
                s = solution[oid]
                e = s + maps.op_by_id[oid].duration
                if e >= lo and s <= hi:  # interval overlaps expanded window
                    picked.add(oid)
        if len(picked) > k:  # keep those closest to an outage start
            keep = sorted(picked, key=lambda oid:
                          (min(abs(solution[oid] - st) for st in starts), oid))[:k]
            return set(keep)
        outage_machines = {o.machine for o in instance.outages}
        cand = [op.op_id for op in all_ops
                if op.machine in outage_machines and op.op_id not in picked]
        cand.sort(key=lambda oid: (min(abs(solution[oid] - st) for st in starts), oid))
        return _top_up_structured(picked, cand, all_ops, k, rng)

    raise ValueError(f"unknown strategy {arm.strategy}")


# ---------------------------------------------------------------------------
# LNS driver
# ---------------------------------------------------------------------------

@dataclass
class RoundLog:
    round_index: int
    arm: str
    objective_before: int
    objective_after: int
    elapsed: float          # cumulative seconds at end of round
    round_time: float
    reward: float           # improvement per second


@dataclass
class SolveResult:
    method: str
    objective: int | None
    solution: Solution | None
    trajectory: list[tuple[float, int]]  # (elapsed seconds, incumbent objective)
    rounds: list[RoundLog] = field(default_factory=list)
    # objective of the first incumbent, before any LNS repair round. Lets the
    # sweep report repair_improvement = initial_objective - objective without
    # re-deriving it. None for plain CP-SAT solves (nothing to repair).
    initial_objective: int | None = None
    # ICAPS-extension timing decomposition, additive/optional so existing
    # callers that never set them (LNS/reopt code) are unaffected.
    bootstrap_time_s: float | None = None
    solver_time_s: float | None = None
    proven_optimal: bool = False

    @property
    def improving_rounds(self) -> int:
        return sum(1 for r in self.rounds if r.objective_after < r.objective_before)


class Policy:
    """Interface. select() gets the instance + incumbent for context."""

    def select(self, instance: Instance, solution: Solution) -> Arm:
        raise NotImplementedError

    def update(self, arm: Arm, reward: float, improved: bool) -> None:
        pass

    def reset_instance(self) -> None:
        """Called at each new instance in the stream."""
        pass


def initial_incumbent(
    instance: Instance,
    prev_solution: Solution | None,
    time_limit: float,
    workers: int,
    seed: int,
    recorder: list[tuple[float, int]] | None = None,
    t_offset: float = 0.0,
) -> tuple[Solution | None, int | None, bool]:
    """Returns (solution, objective, proven_optimal). When the initial solve
    already proves optimality there is nothing for LNS to improve."""
    from ortools.sat.python import cp_model

    built = build_model(instance, hint=prev_solution)
    solution, objective, status = solve(
        built, time_limit=time_limit, workers=workers, seed=seed,
        recorder=recorder, t_offset=t_offset,
    )
    return solution, objective, status == cp_model.OPTIMAL


def lns_solve(
    instance: Instance,
    policy: Policy,
    total_budget: float,
    slice_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    method_name: str = "lns",
    initial_budget: float | None = None,
    repair_total_budget: float | None = None,
    round_slice_budget: float | None = None,
) -> SolveResult:
    """Outer-loop LNS with three *decoupled* budgets so experiments can vary
    how much time goes to the first incumbent vs. the repair phase vs. any one
    repair round, independently:

      * initial_budget      — time for the initial incumbent solve.
      * repair_total_budget — total time across all LNS repair rounds.
      * round_slice_budget  — CP-SAT time limit for a single repair round.

    Intended invariant: initial_budget + repair_total_budget <= total_budget,
    and total_budget is still the hard wall-clock cap (all methods stay
    comparable under the same total). Each repair round is capped at
    min(round_slice_budget, remaining_total_time, remaining_repair_time).

    Backward compatibility: callers that pass only (total_budget, slice_budget)
    get exactly the previous behaviour — initial_budget defaults to
    total_budget - slice_budget (reserving one slice for repair), the repair
    phase gets whatever total_budget leaves, and each round is capped at
    slice_budget. Decoupling the initial budget from slice_budget was the fix
    that flipped LNS from losing to beating cpsat_cold on a full-shop instance
    (729/701 vs 699/701); that default is preserved here."""
    rng = random.Random(seed)
    t0 = time.monotonic()

    # Resolve the decoupled budgets, falling back to the legacy coupling when a
    # new argument is not supplied.
    if initial_budget is None:
        initial_budget = max(0.1, total_budget - slice_budget)
    if round_slice_budget is None:
        round_slice_budget = slice_budget
    if repair_total_budget is None:
        repair_total_budget = max(0.0, total_budget - initial_budget)

    trajectory: list[tuple[float, int]] = []
    rounds: list[RoundLog] = []
    incumbent, objective, optimal = initial_incumbent(
        instance, prev_solution, time_limit=initial_budget, workers=workers,
        seed=seed, recorder=trajectory, t_offset=time.monotonic() - t0,
    )
    if incumbent is None:
        # could not even find an initial solution within initial_budget; spend
        # the rest of the total wall-clock on one plain solve
        remaining = total_budget - (time.monotonic() - t0)
        if remaining > 0:
            incumbent, objective, optimal = initial_incumbent(
                instance, prev_solution, remaining, workers, seed,
                recorder=trajectory, t_offset=time.monotonic() - t0,
            )
        if incumbent is None:
            return SolveResult(method_name, None, None, [])

    initial_objective = objective  # snapshot before any repair round

    round_index = 0
    repair_elapsed = 0.0
    while not optimal:
        elapsed_total = time.monotonic() - t0
        remaining_total = total_budget - elapsed_total
        remaining_repair = repair_total_budget - repair_elapsed
        # stop when either the total wall-clock or the repair budget is spent
        if remaining_total < 0.05 or remaining_repair < 0.05:
            break
        round_start = time.monotonic()
        arm = policy.select(instance, incumbent)
        destroy = select_destroy_set(arm, instance, incumbent, rng)
        frozen = {
            op.op_id: incumbent[op.op_id]
            for op in instance.all_ops
            if op.op_id not in destroy
        }
        built = build_model(instance, hint=incumbent, frozen=frozen)
        # a round never runs past either budget cap
        round_limit = min(round_slice_budget, remaining_total, remaining_repair)
        sub_solution, sub_objective, _ = solve(
            built,
            time_limit=max(0.1, round_limit),
            workers=workers,
            seed=seed + round_index + 1,
        )
        round_time = time.monotonic() - round_start
        repair_elapsed += round_time
        obj_before = objective
        improved = sub_objective is not None and sub_objective < objective
        if improved:
            incumbent, objective = sub_solution, sub_objective
        reward = max(0, obj_before - objective) / max(round_time, 1e-6)
        policy.update(arm, reward, improved)
        elapsed = time.monotonic() - t0
        rounds.append(
            RoundLog(round_index, arm.name, obj_before, objective, elapsed, round_time, reward)
        )
        trajectory.append((elapsed, objective))
        round_index += 1

    return SolveResult(
        method_name, objective, incumbent, trajectory, rounds,
        initial_objective=initial_objective,
    )


def cpsat_default_solve(
    instance: Instance,
    total_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    method_name: str = "cpsat_default",
) -> SolveResult:
    """Baselines (a) and (b): one full-budget CP-SAT solve, optionally
    warm-started with the previous instance's solution."""
    built = build_model(instance, hint=prev_solution)
    solver = None
    t0 = time.monotonic()
    trajectory: list[tuple[float, int]] = []

    from ortools.sat.python import cp_model

    class _Recorder(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()

        def on_solution_callback(self):
            trajectory.append((time.monotonic() - t0, int(self.objective_value)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = total_budget
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    status = solver.solve(built.model, _Recorder())
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {op_id: solver.value(var) for op_id, var in built.starts.items()}
        objective = solver.value(built.makespan)
        if not trajectory or trajectory[-1][1] != objective:
            trajectory.append((time.monotonic() - t0, objective))
        return SolveResult(method_name, objective, solution, trajectory)
    return SolveResult(method_name, None, None, [])


def list_schedule_bootstrap(
    instance: Instance, prev_solution: Solution
) -> Solution:
    """Build a feasible schedule for `instance` from the PREVIOUS instance's
    solution in pure Python (~1ms, no CP-SAT). Ops that survived the delta are
    replayed in their previous start order; brand-new ops (arrivals) go last in
    (job, position-within-job) order — position, NOT op_id string order: a
    lexicographic sort puts "o10" before "o2" and would schedule a job's 10th
    op before its 2nd, breaking precedence for any new job with >9 ops.
    Each op starts at max(job predecessor end, machine available), pushed past
    any overlapping outage window. Feasible by construction for every delta
    kind: cancellations simply drop ops, duration jitter re-times, outages
    shift work right."""
    pos_in_job: dict[str, int] = {}
    for job in instance.jobs:
        for k, op in enumerate(job.ops):
            pos_in_job[op.op_id] = k
    ordered = sorted(
        instance.all_ops,
        key=lambda op: (op.op_id not in prev_solution,          # old ops first
                        prev_solution.get(op.op_id, 0),
                        pos_in_job[op.op_id], op.op_id),
    )
    outages_by_machine: dict[int, list] = {}
    for o in instance.outages:
        outages_by_machine.setdefault(o.machine, []).append(o)
    for lst in outages_by_machine.values():
        lst.sort(key=lambda o: o.start)

    job_of: dict[str, str] = {}
    for job in instance.jobs:
        for op in job.ops:
            job_of[op.op_id] = job.job_id

    machine_avail: dict[int, int] = {}
    job_end: dict[str, int] = {}
    out: Solution = {}
    for op in ordered:
        s = max(job_end.get(job_of[op.op_id], 0),
                machine_avail.get(op.machine, 0))
        for o in outages_by_machine.get(op.machine, ()):  # sorted by start
            if s < o.end and s + op.duration > o.start:
                s = o.end
        out[op.op_id] = s
        machine_avail[op.machine] = s + op.duration
        job_end[job_of[op.op_id]] = s + op.duration
    return out


def warm_bootstrap_solve(
    instance: Instance,
    total_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    use_hint: bool = True,
    method_name: str = "boot_warm",
    floor_fn=None,
) -> SolveResult:
    """Stream-aware warm start: convert the PREVIOUS instance's solution into
    a feasible schedule for the new instance almost instantly, then spend the
    whole remaining budget on one continuous CP-SAT solve seeded with it.

    The bootstrap freezes every op that survived the delta to its previous
    machine ORDER (the same chain constraints as the LNS freeze; starts float,
    so arrivals slot in, jittered durations stretch, and outages shift work
    right without infeasibility). CP-SAT solves this near-fixed model in tens
    of milliseconds, yielding an incumbent close to the previous instance's
    quality at t~=0.05s — where cpsat_cold's early solutions are still far
    worse. cpsat_cold structurally cannot do this: it ignores the stream.

    Two continuation flavours:
      * use_hint=True  ("boot_warm"): the remaining budget is one continuous
        solve HINTED with the bootstrap incumbent. Captures hint's big wins
        but can also be hint-trapped below what an unbiased search finds.
      * use_hint=False ("boot_cold"): the remaining budget is exactly
        cpsat_cold's own (unhinted, same-seed) search; the bootstrap incumbent
        only acts as an anytime FLOOR on the trajectory and final result. By
        construction this never ends worse than cpsat_cold (modulo the ~50ms
        bootstrap cost) and its primal integral is cold's clipped from above.

    The win is concentrated in the primal integral (anytime quality over the
    stream). Instance 0 (no previous solution) degrades gracefully to exactly
    cpsat_cold behaviour.

    floor_fn: optional (instance, prev_solution) -> Solution override for the
    floor-construction function, used by the arrival-specific bootstrap
    policies in bootstrap_policies.py (gap_insert/regret_insert/beam_insert).
    Defaults to list_schedule_bootstrap -- the exact function used by every
    boot_cold/boot_warm result reported in BOOT_COLD_PAPER.md; passing None
    changes nothing about existing behaviour.
    """
    floor_fn = floor_fn or list_schedule_bootstrap
    t0 = time.monotonic()
    trajectory: list[tuple[float, int]] = []
    incumbent: Solution | None = None
    objective: int | None = None

    if prev_solution is not None:
        boot = floor_fn(instance, prev_solution)
        boot_obj = max(
            boot[job.ops[-1].op_id] + job.ops[-1].duration
            for job in instance.jobs
        )
        incumbent, objective = boot, boot_obj
        trajectory.append((time.monotonic() - t0, boot_obj))

    initial_objective = objective

    remaining = total_budget - (time.monotonic() - t0)
    if remaining > 0.05:
        sol, obj, _status = solve(
            build_model(instance, hint=incumbent if use_hint else None),
            time_limit=remaining, workers=workers, seed=seed,
            recorder=trajectory, t_offset=time.monotonic() - t0,
        )
        if sol is not None and (objective is None or obj < objective):
            incumbent, objective = sol, obj

    if incumbent is None:
        return SolveResult(method_name, None, None, [])

    # enforce a monotone anytime trajectory: with an unhinted continuation the
    # fresh solve's early solutions can be worse than the bootstrap floor and
    # must not count against the primal integral
    monotone: list[tuple[float, int]] = []
    best = None
    for t, o in sorted(trajectory):
        if best is None or o < best:
            best = o
            monotone.append((t, o))

    return SolveResult(
        method_name, objective, incumbent, monotone, [],
        initial_objective=initial_objective,
    )


# ---------------------------------------------------------------------------
# Stall-triggered interleaved solver
#
# Motivation (from the seeds 1-2 smart-arms sweep): cpsat_cold wins primal
# integral only because fixed-split LNS burns 6-8s on its initial solve before
# the first repair round; on FINAL objective, LNS arms beat cold on 5/10
# instances. So instead of a fixed budget split, track cpsat_cold's trajectory
# exactly — run one continuous CP-SAT solve — and only divert time to LNS
# repair once that solve has visibly STALLED (no improving solution for
# stall_window seconds). If LNS repair then stalls too, reheat with another
# global solve seeded by the improved incumbent. Worst case we roughly match
# cold (we only give up time cold was spending stalled anyway); whenever a
# repair round improves the incumbent, we strictly beat cold's final quality.
# ---------------------------------------------------------------------------

# arms the per-instance Virtual Best Arm analysis actually picked on the
# seeds 1-2 sweep, in rough order of how often they won
STALL_ROTATION = (
    "delta_40", "random_40", "critical_40", "bottleneck_40", "critical_block_40",
)


def _solve_until_stall(
    built,
    time_limit: float,
    stall_window: float,
    workers: int,
    seed: int,
    recorder: list[tuple[float, int]],
    t_offset: float,
) -> tuple[Solution | None, int | None, bool]:
    """One CP-SAT solve that self-terminates once it has a feasible solution
    and hasn't improved it for `stall_window` seconds. A tiny watchdog thread
    calls solver.stop_search() (thread-safe in OR-Tools) when the stall is
    detected; before the first solution the solve is never interrupted."""
    from ortools.sat.python import cp_model

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed

    t0 = time.monotonic()
    state = {"last_improve": t0, "best": None}

    class _CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            obj = int(self.objective_value)
            if state["best"] is None or obj < state["best"]:
                state["best"] = obj
                state["last_improve"] = time.monotonic()
                recorder.append((t_offset + time.monotonic() - t0, obj))

    stop_evt = threading.Event()

    def _watchdog():
        while not stop_evt.wait(0.05):
            if (state["best"] is not None
                    and time.monotonic() - state["last_improve"] > stall_window):
                solver.stop_search()
                return

    th = threading.Thread(target=_watchdog, daemon=True)
    th.start()
    status = solver.solve(built.model, _CB())
    stop_evt.set()
    th.join(timeout=1.0)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {op_id: solver.value(var) for op_id, var in built.starts.items()}
        return solution, solver.value(built.makespan), status == cp_model.OPTIMAL
    return None, None, False


def stall_interleaved_solve(
    instance: Instance,
    total_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    stall_window: float | None = None,
    round_slice_budget: float = 1.0,
    rotation: tuple[str, ...] = STALL_ROTATION,
    global_frac: float = 0.6,
    method_name: str = "lns_stall",
) -> SolveResult:
    """One global CP-SAT stint, then LNS repair rounds rotating through
    `rotation` for the remainder, under one total wall-clock budget.

    The global stint ends at whichever comes first:
      * a real stall — no improving solution for `stall_window` seconds, or
      * the `global_frac` cap — at most global_frac * total_budget.

    Design notes from the failed v1 (measured, seeds 1-2, 6s budget):
      * CP-SAT improves in BURSTS with long silences (observed 3.2s gaps
        followed by big improvement bursts), so a small stall window amputates
        future bursts and hands LNS a much worse incumbent. stall_window
        defaults generously to max(1.5, 0.25 * total_budget).
      * Reheating with a fresh solver cannot recreate the interrupted solver's
        internal state (nogoods, restarts schedule) and mostly re-derives the
        hint then idles for a stall window. So: no reheat — one global stint,
        then rotation repair to the end. The 60/40 split matches the best
        final-quality split (i6_r4 at 10s) from the smart-arms sweep.
    Rotation + hill-climbing acceptance approximates per-instance arm
    selection: whichever arm finds an improvement keeps it; rounds are cheap
    (~40ms typical), so all arms get many tries.
    """
    if stall_window is None:
        stall_window = max(1.5, 0.25 * total_budget)
    arm_by_name = {arm.name: arm for arm in ARMS}
    arms = tuple(arm_by_name[name] for name in rotation)

    rng = random.Random(seed)
    t0 = time.monotonic()
    trajectory: list[tuple[float, int]] = []
    rounds: list[RoundLog] = []

    # ---- global stint: continuous CP-SAT until stall or the cap ----
    built = build_model(instance, hint=prev_solution)
    stint_limit = min(total_budget, max(0.1, global_frac * total_budget))
    incumbent, objective, optimal = _solve_until_stall(
        built, time_limit=stint_limit, stall_window=stall_window,
        workers=workers, seed=seed, recorder=trajectory, t_offset=0.0,
    )
    if incumbent is None:
        # no feasible solution inside the stint: spend the rest on one solve
        remaining = total_budget - (time.monotonic() - t0)
        if remaining > 0.05:
            sol2, obj2, st2 = solve(
                build_model(instance, hint=prev_solution), time_limit=remaining,
                workers=workers, seed=seed, recorder=trajectory,
                t_offset=time.monotonic() - t0,
            )
            from ortools.sat.python import cp_model
            incumbent, objective, optimal = sol2, obj2, st2 == cp_model.OPTIMAL
        if incumbent is None:
            return SolveResult(method_name, None, None, [])
    initial_objective = objective

    # ---- repair phase: rotation rounds to the end of the budget ----
    round_index = 0
    while not optimal:
        remaining = total_budget - (time.monotonic() - t0)
        if remaining < 0.05:
            break
        round_start = time.monotonic()
        arm = arms[round_index % len(arms)]
        destroy = select_destroy_set(arm, instance, incumbent, rng)
        frozen = {
            op.op_id: incumbent[op.op_id]
            for op in instance.all_ops
            if op.op_id not in destroy
        }
        sub_built = build_model(instance, hint=incumbent, frozen=frozen)
        sub_solution, sub_objective, _ = solve(
            sub_built,
            time_limit=max(0.1, min(round_slice_budget, remaining)),
            workers=workers,
            seed=seed + 1000 + round_index,
        )
        round_time = time.monotonic() - round_start
        obj_before = objective
        improved = sub_objective is not None and sub_objective < objective
        if improved:
            incumbent, objective = sub_solution, sub_objective
        reward = max(0, obj_before - objective) / max(round_time, 1e-6)
        elapsed = time.monotonic() - t0
        rounds.append(RoundLog(round_index, arm.name, obj_before, objective,
                               elapsed, round_time, reward))
        trajectory.append((elapsed, objective))
        round_index += 1

    return SolveResult(
        method_name, objective, incumbent, trajectory, rounds,
        initial_objective=initial_objective,
    )
