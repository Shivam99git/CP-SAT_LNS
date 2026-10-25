"""Deterministic budget allocation between the restricted (local) and the
unrestricted (global) CP-SAT stage (COBAR, docs/cobar/05_budget_adaptation.md).

The policy sees only features available when it is called: the budget, the
worker count, the elapsed time, the event, the neighbourhood and its
certificate. It returns the absolute elapsed time at which the local stage
must end (alpha * B, never in the past) or None to skip the local stage. It
never sees solver outcomes of the current instance or anything about later
instances, so it is deterministic for fixed inputs.

Policies
  fixed        alpha_long whenever a neighbourhood exists (IAIP-SR: 0.6)
  budget       skip when workers >= skip_workers or B < min_budget_s,
               otherwise alpha_long
  certificate  skip when the neighbourhood is certified non-improving and
               could not be released; alpha_short when the certified
               opportunity (U - L)/U is below gap_threshold; else alpha_long
  cert+budget  the budget rule first, then the certificate rule
"""

from __future__ import annotations

from dataclasses import dataclass

POLICIES = ("fixed", "budget", "certificate", "cert+budget")


@dataclass(frozen=True)
class PolicyConfig:
    policy: str = "fixed"
    alpha_long: float = 0.6
    alpha_short: float = 0.2
    gap_threshold: float = 0.02     # certified opportunity (U - L)/U below which the stage is short
    skip_workers: int = 4
    min_budget_s: float = 4.0


@dataclass(frozen=True)
class Features:
    budget: float
    workers: int
    elapsed: float                  # time already used (construction, certificate, neighbourhood)
    U: int                          # incumbent makespan
    L: int                          # certified lower bound of the neighbourhood (0 if not computed)
    certified_non_improving: bool   # decisive certificate after any release attempt
    neighbourhood_size: int
    n_ops: int
    new_ops: bool


@dataclass(frozen=True)
class Decision:
    run_local: bool
    local_end: float | None         # elapsed time at which the local stage stops
    alpha: float
    reason: str


def decide(f: Features, cfg: PolicyConfig) -> Decision:
    if cfg.policy not in POLICIES:
        raise ValueError(cfg.policy)
    if f.neighbourhood_size == 0:
        return Decision(False, None, 0.0, "empty neighbourhood")
    if cfg.policy in ("budget", "cert+budget"):
        if f.workers >= cfg.skip_workers:
            return Decision(False, None, 0.0, f"workers {f.workers} >= {cfg.skip_workers}")
        if f.budget < cfg.min_budget_s:
            return Decision(False, None, 0.0, f"budget {f.budget} < {cfg.min_budget_s}")
    alpha = cfg.alpha_long
    reason = "alpha_long"
    if cfg.policy in ("certificate", "cert+budget"):
        if f.certified_non_improving:
            return Decision(False, None, 0.0, "certified non-improving")
        gap = (f.U - f.L) / f.U if f.U > 0 else 0.0
        if gap < cfg.gap_threshold:
            alpha, reason = cfg.alpha_short, f"certified opportunity {gap:.4f} < {cfg.gap_threshold}"
    end = alpha * f.budget
    if end <= f.elapsed:
        return Decision(False, None, alpha, "no local time left after preprocessing")
    return Decision(True, end, alpha, reason)
