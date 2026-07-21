"""Evaluation metrics. Primary: primal integral over each instance solve,
aggregated cumulatively over the stream (amortization is the whole point).
"""

from __future__ import annotations

from .harness import SolveResult


def primal_integral(
    trajectory: list[tuple[float, int]],
    best_known: int,
    budget: float,
) -> float:
    """Area under the relative-gap-vs-time curve on [0, budget].

    gap(t) = (incumbent(t) - best_known) / best_known, with gap = 1 before
    the first solution (the standard convention). Lower is better; 0 means
    the best-known value was found instantly.
    """
    if best_known <= 0:
        raise ValueError("best_known must be positive")
    events = sorted(trajectory)
    area = 0.0
    prev_t = 0.0
    prev_gap = 1.0  # no solution yet
    for t, obj in events:
        t = min(t, budget)
        area += prev_gap * (t - prev_t)
        prev_t = t
        prev_gap = max(0.0, (obj - best_known) / best_known)
    area += prev_gap * (budget - prev_t)
    return area / budget  # normalized to [0, 1]


def final_gap(result: SolveResult, best_known: int) -> float:
    if result.objective is None:
        return 1.0
    return max(0.0, (result.objective - best_known) / best_known)


# ---------------------------------------------------------------------------
# Stability metrics (ICAPS extension). Pure functions over two solutions
# (op_id -> start time dicts) plus, where needed, the Instance for machine
# assignment. No dependency on SolveResult, so they work for any runner/
# domain that uses the same Solution representation (job-shop, RCPSP).
# ---------------------------------------------------------------------------

def _common_ops(prev_solution: dict, new_solution: dict) -> list[str]:
    return sorted(set(prev_solution) & set(new_solution))


def num_moved_operations(
    prev_solution: dict, new_solution: dict,
    common_ops: list[str] | None = None, tolerance: int = 0,
) -> int:
    """Count common operations whose start time changed by more than
    `tolerance`. tolerance=0 means any change counts."""
    ops = common_ops if common_ops is not None else _common_ops(prev_solution, new_solution)
    return sum(
        1 for op in ops
        if abs(new_solution[op] - prev_solution[op]) > tolerance
    )


def fraction_moved_operations(
    prev_solution: dict, new_solution: dict,
    common_ops: list[str] | None = None, tolerance: int = 0,
) -> float:
    ops = common_ops if common_ops is not None else _common_ops(prev_solution, new_solution)
    if not ops:
        return 0.0
    return num_moved_operations(prev_solution, new_solution, ops, tolerance) / len(ops)


def _shifts(prev_solution: dict, new_solution: dict,
            common_ops: list[str] | None = None) -> list[int]:
    ops = common_ops if common_ops is not None else _common_ops(prev_solution, new_solution)
    return [abs(new_solution[op] - prev_solution[op]) for op in ops]


def mean_abs_start_shift(prev_solution: dict, new_solution: dict,
                         common_ops: list[str] | None = None) -> float:
    shifts = _shifts(prev_solution, new_solution, common_ops)
    return sum(shifts) / len(shifts) if shifts else 0.0


def median_abs_start_shift(prev_solution: dict, new_solution: dict,
                           common_ops: list[str] | None = None) -> float:
    shifts = sorted(_shifts(prev_solution, new_solution, common_ops))
    if not shifts:
        return 0.0
    n = len(shifts)
    mid = n // 2
    return float(shifts[mid]) if n % 2 else (shifts[mid - 1] + shifts[mid]) / 2.0


def max_abs_start_shift(prev_solution: dict, new_solution: dict,
                        common_ops: list[str] | None = None) -> int:
    shifts = _shifts(prev_solution, new_solution, common_ops)
    return max(shifts) if shifts else 0


def machine_order_distance(
    instance, prev_solution: dict, new_solution: dict,
    common_ops: list[str] | None = None,
) -> int:
    """Pairwise-disagreement distance between the two solutions' relative
    orderings of common operations sharing a machine (a Kendall-tau-style
    inversion count, restricted to same-machine pairs since only those pairs
    have a meaningful "order" in a job-shop schedule). O(n^2) in the number
    of common ops on the busiest machine; fine at benchmark scale."""
    ops = common_ops if common_ops is not None else _common_ops(prev_solution, new_solution)
    op_ids = set(ops)
    by_machine: dict[int, list[str]] = {}
    for job in instance.jobs:
        for op in job.ops:
            if op.op_id in op_ids:
                by_machine.setdefault(op.machine, []).append(op.op_id)
    inversions = 0
    for machine_ops in by_machine.values():
        for i in range(len(machine_ops)):
            for j in range(i + 1, len(machine_ops)):
                a, b = machine_ops[i], machine_ops[j]
                prev_order = prev_solution[a] < prev_solution[b]
                new_order = new_solution[a] < new_solution[b]
                if prev_order != new_order:
                    inversions += 1
    return inversions


def frozen_violation_count(frozen: dict, new_solution: dict) -> int:
    """Number of frozen (op_id -> required start) entries the new solution
    violates. 0 for a correctly-respected freeze; used as a correctness
    check for fix_and_optimize / partial_schedule_freeze."""
    return sum(
        1 for op_id, required in frozen.items()
        if op_id in new_solution and new_solution[op_id] != required
    )


def time_to_first_feasible(trajectory: list[tuple[float, int]]) -> float | None:
    if not trajectory:
        return None
    return min(t for t, _ in trajectory)


def time_to_gap_threshold(
    trajectory: list[tuple[float, int]], best_known: int, threshold: float,
) -> float | None:
    """First elapsed time at which relative gap to best_known is <=
    threshold, or None if never reached within the recorded trajectory."""
    if best_known <= 0:
        raise ValueError("best_known must be positive")
    for t, obj in sorted(trajectory):
        gap = max(0.0, (obj - best_known) / best_known)
        if gap <= threshold:
            return t
    return None


def bootstrap_gap(bootstrap_objective: int | None, best_known: int) -> float | None:
    """Relative gap of the bootstrap floor's objective against best_known.
    None when there was no bootstrap (e.g. first stream instance)."""
    if bootstrap_objective is None:
        return None
    if best_known <= 0:
        raise ValueError("best_known must be positive")
    return max(0.0, (bootstrap_objective - best_known) / best_known)
