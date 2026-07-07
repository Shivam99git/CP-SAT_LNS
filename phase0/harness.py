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
import time
from dataclasses import dataclass, field

from .model_builder import Solution, build_model, solve
from .streams import Instance, Operation

# ---------------------------------------------------------------------------
# Destroy arms
# ---------------------------------------------------------------------------

DESTROY_SIZES = (0.10, 0.25, 0.40)  # fraction of operations unfrozen
STRATEGIES = ("random", "machine", "critical", "delta")


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
) -> SolveResult:
    rng = random.Random(seed)
    t0 = time.monotonic()
    initial_budget = max(0.1, total_budget - slice_budget)

    trajectory: list[tuple[float, int]] = []
    rounds: list[RoundLog] = []
    incumbent, objective, optimal = initial_incumbent(
        instance, prev_solution, time_limit=initial_budget, workers=workers,
        seed=seed, recorder=trajectory, t_offset=time.monotonic() - t0,
    )
    if incumbent is None:
        # could not even find an initial solution within the slice; spend the
        # rest of the budget on one plain solve
        remaining = total_budget - (time.monotonic() - t0)
        if remaining > 0:
            incumbent, objective, optimal = initial_incumbent(
                instance, prev_solution, remaining, workers, seed,
                recorder=trajectory, t_offset=time.monotonic() - t0,
            )
        if incumbent is None:
            return SolveResult(method_name, None, None, [])

    round_index = 0
    while not optimal and time.monotonic() - t0 < total_budget - 0.05:
        round_start = time.monotonic()
        arm = policy.select(instance, incumbent)
        destroy = select_destroy_set(arm, instance, incumbent, rng)
        frozen = {
            op.op_id: incumbent[op.op_id]
            for op in instance.all_ops
            if op.op_id not in destroy
        }
        built = build_model(instance, hint=incumbent, frozen=frozen)
        remaining = total_budget - (time.monotonic() - t0)
        sub_solution, sub_objective, _ = solve(
            built,
            time_limit=min(slice_budget, max(0.1, remaining)),
            workers=workers,
            seed=seed + round_index + 1,
        )
        round_time = time.monotonic() - round_start
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

    return SolveResult(method_name, objective, incumbent, trajectory, rounds)


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
