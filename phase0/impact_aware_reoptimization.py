"""Integrated method (provisional name IAIP-SR): feasible incumbent portfolio,
impact-selective CP-SAT, then unrestricted CP-SAT, under one deadline.

    1. start one monotonic deadline (all later work counts against it)
    2. disruption set D from the previous and current instances
    3. build the portfolio; retain the best validated member at the elapsed
       time it became available
    4. if alpha > 0: neighbourhood N of the incumbent; restricted CP-SAT until
       elapsed = alpha * B (or earlier if it proves the neighbourhood
       optimal/infeasible); retain only validated strict improvements
    5. unrestricted CP-SAT for the remaining time (global_mode: 'unhinted',
       'hinted' with the incumbent, or 'cutoff' = unhinted with
       Cmax <= incumbent - 1); retain only validated strict improvements
    6. return the best validated schedule, its full trajectory and timings

Guarantee and its limit: the returned value is no worse than the best
incumbent observed within this run (portfolio member, local or global
solution). It is NOT guaranteed to be no worse than an independently
executed Cold solver with the same budget, because steps 3-4 take time away
from the unrestricted search.
"""

from __future__ import annotations

from dataclasses import dataclass

from .incumbent_portfolio import PORTFOLIOS, build_portfolio
from .reuse_methods import Clock, RunResult, _finish, build_research_model, run_cpsat
from .selective_reoptimization import disruption_set, make_neighbourhood, selective_solve
from .streams import Instance

Solution = dict[str, int]


@dataclass(frozen=True)
class IAIPConfig:
    portfolio: str = "full"
    construction_frac: float = 0.05     # share of B the portfolio may use
    neighbourhood: str = "N5"
    expansion_frac: float = 0.25
    alpha: float = 0.0                  # share of B given to the local phase
    require_improvement: bool = True
    global_mode: str = "unhinted"       # unhinted | hinted | cutoff


def run_iaip(instance: Instance, previous: Solution | None, prev_instance: Instance | None,
             budget: float, cfg: IAIPConfig, workers: int = 1, seed: int = 0,
             method_name: str = "iaip") -> tuple[RunResult, dict]:
    clock = Clock(budget)
    res = RunResult(method=method_name, budget=budget)
    meta: dict = {"config": cfg.__dict__.copy()}

    D = disruption_set(prev_instance, instance, previous)
    meta["disruption_size"] = len(D)

    t = clock.elapsed()
    pf = build_portfolio(instance, previous, PORTFOLIOS[cfg.portfolio],
                         construction_budget=cfg.construction_frac * budget, deadline=clock.deadline)
    res.construction_s += clock.elapsed() - t
    meta["portfolio"] = {"chosen": pf.chosen, "objective": pf.objective,
                         "skipped": pf.skipped_for_budget,
                         "members": [c.__dict__ for c in pf.candidates]}
    if pf.solution is not None:
        res.construction_objective, res.construction_source = pf.objective, f"portfolio:{pf.chosen}"
        res.objective, res.solution = pf.objective, pf.solution
        res.events.append((clock.elapsed(), pf.objective, f"portfolio:{pf.chosen}"))

    if cfg.alpha > 0 and res.solution is not None:
        t = clock.elapsed()
        N = make_neighbourhood(cfg.neighbourhood, instance, res.solution, D, cfg.expansion_frac)
        meta["neighbourhood_build_s"] = clock.elapsed() - t
        local_end = clock.t0 + cfg.alpha * budget
        meta["local"] = selective_solve(res, clock, instance, N, local_end, workers, seed,
                                        cfg.require_improvement)

    built = None
    hint = None
    if cfg.global_mode == "hinted":
        hint = res.solution
    elif cfg.global_mode == "cutoff" and res.objective is not None:
        t = clock.elapsed()
        built = build_research_model(instance)
        built.model.add(built.makespan <= res.objective - 1)
        res.build_s += clock.elapsed() - t
    elif cfg.global_mode != "unhinted" and cfg.global_mode != "cutoff":
        raise ValueError(cfg.global_mode)
    run_cpsat(res, clock, instance, hint, workers, seed, source="global", built=built)
    if cfg.global_mode == "cutoff" and res.solver_status == "INFEASIBLE":
        meta["global_proved_incumbent_optimal"] = True
    return _finish(res, clock, instance), meta


# named configurations used in the experiments (Stage E3-E5)
CONFIGS = {
    "portfolio_cold": IAIPConfig(portfolio="full"),
    "fresh_portfolio_cold": IAIPConfig(portfolio="fresh"),
    "elr_cold": IAIPConfig(portfolio="elr"),
    "hist_cold": IAIPConfig(portfolio="hist"),          # == Floor, through this code path
}
