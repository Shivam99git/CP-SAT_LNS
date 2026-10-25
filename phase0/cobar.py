"""COBAR: certificate-guided, budget-adaptive reoptimization (provisional
name; docs/cobar/). A separate implementation built from the shared,
validated modules; IAIP-SR (`impact_aware_reoptimization.py`) is unchanged.

One monotonic deadline B covers every step:
  1. disruption set D (previous vs current instance)
  2. anytime incumbent portfolio (each validated improving member is
     retained at the moment it is built)
  3. optional global certificate: if a valid lower bound of the full problem
     equals the incumbent's makespan, the incumbent is optimal; both solver
     stages are skipped
  4. neighbourhood (N, R) of the incumbent; optional certificate L(N, R);
     optional release of obstructing machine arcs
  5. deterministic budget policy: skip the local stage, or run it until an
     absolute elapsed time alpha * B
  6. restricted CP-SAT on (N, R) with Cmax <= U - 1, hinted with the incumbent;
     only validated strict improvements are retained
  7. unrestricted CP-SAT for the remaining time, hinted with the current
     incumbent (a separate solver run: no internal search state is carried
     over from step 6)
  8. return the best validated schedule and its trajectory

Guarantee: the returned value is no worse than the best incumbent seen in the
run. Local optimality proofs (INFEASIBLE under the improvement bound, or a
decisive certificate) concern the restricted problem only. Nothing is
guaranteed against an independently executed solver run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .cobar_budget_policy import Features, PolicyConfig, decide
from .cobar_certificates import CertificateError, certificate, global_certificate, kept_arcs
from .cobar_neighborhood import release_obstructions
from .event_localized_repair import index_instance
from .incumbent_portfolio import PORTFOLIOS, build_portfolio
from .reuse_methods import Clock, RunResult, _finish, build_research_model, run_cpsat
from .selective_reoptimization import bounded_expansion, disruption_set, make_neighbourhood
from .streams import Instance

Solution = dict[str, int]
NEIGHBOURHOODS = ("none", "iaip", "closure", "critical", "release", "release+expand", "iaip+release")
SOLVER_PARAMS = {"default": None, "interleave": {"interleave_search": True}}


@dataclass(frozen=True)
class COBARConfig:
    portfolio: str = "full"
    construction_frac: float = 0.05
    neighbourhood: str = "iaip+release"
    expansion_frac: float = 0.25
    release_mode: str = "arcs"          # arcs | ops
    use_certificate: bool = True
    skip_certified: bool = True         # skip the local stage when certified non-improving
    global_certificate: bool = True
    policy: str = "cert+budget"
    alpha: float = 0.6                  # alpha_long
    alpha_short: float = 0.2
    gap_threshold: float = 0.02
    skip_workers: int = 4
    min_budget_s: float = 4.0
    stall_s: float = -1.0               # < 0: no stall stop in the local stage
    global_params: str = "default"      # default | interleave (native CP-SAT LNS, see 01 F2)
    require_improvement: bool = True

    def policy_config(self) -> PolicyConfig:
        return PolicyConfig(self.policy, self.alpha, self.alpha_short, self.gap_threshold,
                            self.skip_workers, self.min_budget_s)


def build_cobar_restricted_model(instance: Instance, incumbent: Solution, N: set[str], R: set,
                                 require_improvement: bool, incumbent_obj: int):
    """Full research model + kept arcs of (N, R) (cobar_certificates.kept_arcs)
    + Cmax <= U - 1, hinted with the incumbent."""
    built = build_research_model(instance, hint=incumbent)
    ix = index_instance(instance)
    arcs = kept_arcs(instance, incumbent, N, R, ix)
    for u, v in arcs:
        built.model.add(built.starts[v] >= built.starts[u] + ix.op[u].duration)
    if require_improvement:
        built.model.add(built.makespan <= incumbent_obj - 1)
    return built, len(arcs)


def _neighbourhood(cfg: COBARConfig, instance, incumbent, D, meta):
    """(N, R, certificate of (N, R) if the release loop computed it)."""
    kind = cfg.neighbourhood
    R: set = set()
    if kind == "none":
        return set(), R, None
    if kind in ("iaip", "iaip+release"):
        N = make_neighbourhood("N5", instance, incumbent, D, cfg.expansion_frac)
    elif kind == "closure":
        N = make_neighbourhood("N2", instance, incumbent, D, cfg.expansion_frac)
    elif kind == "critical":
        N = make_neighbourhood("N3", instance, incumbent, D, cfg.expansion_frac)
    elif kind in ("release", "release+expand"):
        N = set()
    else:
        raise ValueError(kind)
    if kind in ("iaip+release", "release", "release+expand"):
        rel = release_obstructions(instance, incumbent, N, mode=cfg.release_mode if kind == "iaip+release" else "arcs")
        meta["release"] = {"status": rel.status, "iterations": rel.iterations, "cut_cost": rel.cut_cost,
                           "n_released_arcs": len(rel.R), "n_added_ops": len(rel.added_ops),
                           "time_s": rel.time_s, "before_L": rel.before.L, "after_L": rel.after.L,
                           "before_decisive": rel.before.decisive, "after_decisive": rel.after.decisive}
        N, R = rel.N, rel.R
        if kind == "release+expand":
            seeds = {x for a in R for x in a}
            N = bounded_expansion(instance, incumbent, seeds, cfg.expansion_frac) if seeds else set()
            return N, set(), None
        return N, R, rel.after
    return N, R, None


def run_cobar(instance: Instance, previous: Solution | None, prev_instance: Instance | None,
              budget: float, cfg: COBARConfig, workers: int = 1, seed: int = 0,
              method_name: str = "cobar") -> tuple[RunResult, dict]:
    clock = Clock(budget)
    res = RunResult(method=method_name, budget=budget)
    meta: dict = {"config": asdict(cfg), "fallbacks": []}
    stage = {}

    t = clock.elapsed()
    D = disruption_set(prev_instance, instance, previous)
    meta["disruption_size"] = len(D)
    stage["disruption_s"] = clock.elapsed() - t

    def retain(sol, obj, name):
        res.objective, res.solution = obj, sol
        res.events.append((clock.elapsed(), obj, f"portfolio:{name}"))

    t = clock.elapsed()
    pf = build_portfolio(instance, previous, PORTFOLIOS[cfg.portfolio],
                         construction_budget=cfg.construction_frac * budget, deadline=clock.deadline,
                         on_improve=retain)
    res.construction_s += clock.elapsed() - t
    stage["portfolio_s"] = clock.elapsed() - t
    meta["portfolio"] = {"chosen": pf.chosen, "objective": pf.objective, "n_candidates": len(pf.candidates),
                         "skipped": pf.skipped_for_budget}
    if pf.solution is not None:
        res.construction_objective, res.construction_source = pf.objective, f"portfolio:{pf.chosen}"
    meta["initial_objective"] = res.objective
    new_ops = previous is not None and any(o.op_id not in previous for o in instance.all_ops)
    meta["new_ops"] = bool(new_ops)

    run_global = True
    if res.solution is not None and cfg.global_certificate:
        t = clock.elapsed()
        try:
            g = global_certificate(instance, res.solution)
            meta["global_certificate"] = {"L": g.L, "U": g.U, "decisive": g.decisive, "kind": g.kind}
            if g.decisive:
                run_global = False
        except CertificateError as e:
            meta["fallbacks"].append(f"global certificate: {e}")
        stage["global_certificate_s"] = clock.elapsed() - t

    decision = None
    if res.solution is not None and run_global and cfg.neighbourhood != "none":
        t = clock.elapsed()
        N, R, cert = set(), set(), None
        try:
            N, R, cert = _neighbourhood(cfg, instance, res.solution, D, meta)
        except CertificateError as e:
            meta["fallbacks"].append(f"release: {e}; using the IAIP-SR neighbourhood")
            N, R = make_neighbourhood("N5", instance, res.solution, D, cfg.expansion_frac), set()
        stage["neighbourhood_s"] = clock.elapsed() - t
        meta["neighbourhood_size"], meta["n_released_arcs"] = len(N), len(R)
        if cfg.use_certificate:
            t = clock.elapsed()
            try:
                if cert is None:  # the release loop's final certificate is reused when available
                    cert = certificate(instance, res.solution, N, R)
                meta["certificate"] = {"U": cert.U, "L": cert.L, "L_path": cert.L_path, "L_mach": cert.L_mach,
                                       "decisive": cert.decisive, "kind": cert.kind,
                                       "n_kept_arcs": cert.n_kept_arcs, "time_s": cert.time_s}
            except CertificateError as e:
                meta["fallbacks"].append(f"certificate: {e}")
            stage["certificate_s"] = clock.elapsed() - t
        certified = bool(cert and cert.decisive)
        f = Features(budget, workers, clock.elapsed(), res.objective, cert.L if cert else 0, certified,
                     len(N) + len(R), len(instance.all_ops), bool(new_ops))
        decision = decide(f, cfg.policy_config())
        if certified and cfg.skip_certified and decision.run_local:
            decision = type(decision)(False, None, decision.alpha, "certified non-improving (skip rule)")
        meta["decision"] = {"run_local": decision.run_local, "alpha": decision.alpha, "reason": decision.reason}
        if decision.run_local:
            before = res.objective
            t = clock.elapsed()
            built, n_arcs = build_cobar_restricted_model(instance, res.solution, N, R,
                                                         cfg.require_improvement, res.objective)
            loc = {"local_build_s": clock.elapsed() - t, "fixed_order_arcs": n_arcs}
            res.build_s += loc["local_build_s"]
            sub = Clock(0.0)
            sub.t0, sub.deadline = clock.t0, min(clock.t0 + decision.local_end, clock.deadline)
            status_before, solver_before = res.solver_status, res.solver_s
            run_cpsat(res, sub, instance, None, workers, seed, source="local", built=built,
                      stall_s=cfg.stall_s if cfg.stall_s >= 0 else None)
            loc.update({"local_status": res.solver_status, "local_improved": res.objective < before,
                        "local_time_s": clock.elapsed() - t, "local_solver_s": res.solver_s - solver_before})
            res.solver_status = status_before
            meta["local"] = loc
            stage["local_s"] = loc["local_time_s"]

    if run_global:
        before = res.objective
        t = clock.elapsed()
        run_cpsat(res, clock, instance, res.solution, workers, seed, source="global",
                  params=SOLVER_PARAMS[cfg.global_params])
        stage["global_s"] = clock.elapsed() - t
        meta["global"] = {"status": res.solver_status,
                          "improved": before is None or (res.objective is not None and res.objective < before)}
    else:
        res.solver_status = "CERTIFIED_OPTIMAL"
    meta["stage_s"] = stage
    return _finish(res, clock, instance), meta
