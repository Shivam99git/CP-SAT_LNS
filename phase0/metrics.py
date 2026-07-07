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
