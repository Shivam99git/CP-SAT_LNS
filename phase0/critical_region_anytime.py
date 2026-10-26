"""Critical-Region Guided Anytime Reoptimization (CRGAR; provisional name) and
its controls (docs/unified_icaps/03_lns_baseline_protocol.md).

One monotonic deadline B covers:
  1. disruption set D; anytime incumbent portfolio (validated members retained
     when built)                                                 [IAIP-SR]
  2. optional initial restricted stage on IAIP-SR's disruption neighbourhood
     (25% breadth-first expansion of D), C_max <= U - 1, until alpha*B or a
     proof of optimality / infeasibility of the restricted problem  [IAIP-SR]
  3. up to `max_rounds` further restricted rounds inside the local window,
     each on a neighbourhood built by `strategy` from the *current* incumbent
  4. unrestricted CP-SAT, hinted with the incumbent, until B     [IAIP-SR]

Restricted model of a round: the full research model (job precedence,
no-overlap with outages, release dates, commitments) plus the incumbent's
machine-order precedences between consecutive positive-duration operations
outside N, minus the released arcs R, plus C_max <= U - 1; hinted with the
incumbent. This is the restriction structure of CP-SAT's own
scheduling_intervals_lns (relaxed intervals + incumbent precedences among the
rest). The incumbent satisfies every added precedence (positive durations),
so it belongs to every restricted problem; only validated strict
improvements replace it (incumbent retention: the retained objective is
non-increasing).

Strategies (all deterministic given the instance, the incumbent and the round):
  crit_expand          seeds = every operation on the longest binding chains of
                       the incumbent's machine orders (left-shifted if it has
                       idle time); 25% breadth-first expansion over job and
                       machine adjacency  (= COBAR's critical+expand)
  crit_onechain_expand seeds = one longest chain; same expansion
  crit_blocks_expand   seeds = critical blocks (>= 2 consecutive same-machine
                       operations joined by binding machine arcs); same expansion
  crit_disr_expand     seeds = chain operations in the forward closure of D
                       (all chain operations if none); same expansion
  crit_onehop          chain operations plus their job/machine neighbours
  crit_chain           chain operations only
  random_bfs           as many random seeds as crit_expand has; same expansion
  random_matched       uniformly random operations, |N| = |N(crit_expand)|
  time_window          |N(crit_expand)| operations consecutive in (start, end)
                       order from a random index (external analogue of
                       CP-SAT's scheduling_time_window_lns)
  precedence           N = {}; release a uniformly random set R of incumbent
                       machine-order arcs, |R| = number of arcs crit_expand
                       releases (analogue of scheduling_precedences_lns)
"""

from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass

from .cobar import SOLVER_PARAMS, build_cobar_restricted_model
from .cobar_certificates import certificate, kept_arcs
from .cobar_neighborhood import obstruction
from .event_localized_repair import index_instance, orders_from_schedule
from .incumbent_portfolio import PORTFOLIOS, build_portfolio
from .reuse_methods import Clock, RunResult, _finish, run_cpsat
from .selective_reoptimization import bounded_expansion, disruption_set, forward_closure, make_neighbourhood
from .streams import Instance

Solution = dict[str, int]
STRATEGIES = ("crit_expand", "crit_onechain_expand", "crit_blocks_expand", "crit_disr_expand", "crit_onehop",
              "crit_chain", "random_bfs", "random_matched", "time_window", "precedence")


@dataclass(frozen=True)
class CRGARConfig:
    portfolio: str = "full"
    construction_frac: float = 0.05
    initial_stage: bool = True          # IAIP-SR's disruption-centred restricted stage first
    expansion_frac: float = 0.25
    alpha: float = 0.6                  # local window ends at alpha * B
    max_rounds: int = 9                 # further rounds after the initial stage
    strategy: str = "crit_expand"
    recompute: bool = True              # False: the round neighbourhood is computed once and reused
    stop_on_fail: bool = True           # M1 policy; M2 uses False
    round_time: float = -1.0            # > 0: each round stops after round_time seconds (M2)
    final_global: bool = True           # False: rounds use the whole budget, no unrestricted stage
    global_params: str = "default"
    require_improvement: bool = True


# ------------------------------------------------------------ structures

def critical_structure(inst: Instance, S: Solution, ix=None) -> dict:
    """Longest binding chains of S's own machine orders (03_certificate_theory.md §3):
    chain operations, one chain, critical blocks."""
    cert0 = certificate(inst, S, set())
    ob = obstruction(inst, S, set(), set(), cert0.L_path)
    chain_ops = {x for u, v, _ in ob.arcs for x in (u, v)} | set(ob.sinks) | set(ob.starts)
    parent = {v: v for v in chain_ops}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u, v, k in ob.arcs:
        if k == "machine":
            parent[find(u)] = find(v)
    comp: dict[str, set] = {}
    for v in chain_ops:
        comp.setdefault(find(v), set()).add(v)
    blocks = set().union(*[c for c in comp.values() if len(c) >= 2]) if comp else set()
    return {"chain_ops": chain_ops, "one_chain": set(cert0.path), "blocks": blocks,
            "L_path": cert0.L_path, "U": cert0.U}


def _adjacency(inst, S, ix):
    orders = orders_from_schedule(inst, S, ix)
    adj = {v: set() for v in ix.op}
    for ops in ix.job_ops.values():
        for a, b in zip(ops, ops[1:]):
            adj[a].add(b); adj[b].add(a)
    for seq in orders.values():
        for a, b in zip(seq, seq[1:]):
            adj[a].add(b); adj[b].add(a)
    return adj


def _rng(inst, U, round_no, strategy):
    return random.Random(f"{inst.index}|{U}|{round_no}|{strategy}")


def make_round_neighbourhood(strategy: str, inst: Instance, S: Solution, D: set[str], frac: float,
                             round_no: int) -> tuple[set[str], set, dict]:
    ix = index_instance(inst)
    ids = sorted(ix.op)
    cs = critical_structure(inst, S, ix)
    chain = cs["chain_ops"]
    base_N = bounded_expansion(inst, S, chain, frac) if chain else set()
    info = {"chain_ops": len(chain), "blocks": len(cs["blocks"]), "L_path": cs["L_path"], "U": cs["U"]}
    rng = _rng(inst, cs["U"], round_no, strategy)
    R: set = set()
    if strategy == "crit_expand":
        N = base_N
    elif strategy == "crit_onechain_expand":
        N = bounded_expansion(inst, S, cs["one_chain"], frac) if cs["one_chain"] else set()
    elif strategy == "crit_blocks_expand":
        seeds = cs["blocks"] or chain
        N = bounded_expansion(inst, S, seeds, frac) if seeds else set()
    elif strategy == "crit_disr_expand":
        seeds = chain & forward_closure(inst, S, D) if D else set()
        info["disruption_seeds"] = len(seeds)
        seeds = seeds or chain
        N = bounded_expansion(inst, S, seeds, frac) if seeds else set()
    elif strategy == "crit_onehop":
        adj = _adjacency(inst, S, ix)
        N = set(chain) | {w for v in chain for w in adj[v]}
    elif strategy == "crit_chain":
        N = set(chain)
    elif strategy == "random_bfs":
        seeds = set(rng.sample(ids, min(len(chain), len(ids))))
        N = bounded_expansion(inst, S, seeds, frac) if seeds else set()
    elif strategy == "random_matched":
        N = set(rng.sample(ids, min(len(base_N), len(ids))))
    elif strategy == "time_window":
        order = sorted(ids, key=lambda v: (S[v], S[v] + ix.op[v].duration, v))
        k = min(len(base_N), len(order))
        i = rng.randint(0, len(order) - k) if k < len(order) else 0
        N = set(order[i:i + k])
    elif strategy == "precedence":
        all_arcs = kept_arcs(inst, S, set(), set(), ix)
        m = len(all_arcs) - len(kept_arcs(inst, S, base_N, set(), ix))
        R = set(rng.sample(all_arcs, min(m, len(all_arcs))))
        N = set()
    else:
        raise ValueError(strategy)
    n_all = len(kept_arcs(inst, S, set(), set(), ix))
    n_kept = len(kept_arcs(inst, S, N, R, ix))
    info.update({"n_released_ops": len(N), "n_ops": len(ids), "released_frac": len(N) / len(ids),
                 "n_released_arcs_explicit": len(R), "machine_arcs_total": n_all, "machine_arcs_kept": n_kept,
                 "machine_arcs_released": n_all - n_kept, "critical_in_N": len(N & chain),
                 "noncritical_in_N": len(N - chain), "matched_target_ops": len(base_N)})
    return N, R, info


# ------------------------------------------------------------ method

def _restricted_solve(res, clock, inst, N, R, end_abs, workers, seed, cfg):
    t = clock.elapsed()
    built, n_arcs = build_cobar_restricted_model(inst, res.solution, N, R, cfg.require_improvement, res.objective)
    build_s = clock.elapsed() - t
    res.build_s += build_s
    sub = Clock(0.0)
    sub.t0, sub.deadline = clock.t0, min(end_abs, clock.deadline)
    status_before, solver_before, before = res.solver_status, res.solver_s, res.objective
    run_cpsat(res, sub, inst, None, workers, seed, source="local", built=built)
    out = {"status": res.solver_status, "build_s": build_s, "solver_s": res.solver_s - solver_before,
           "time_s": clock.elapsed() - t, "objective_before": before, "objective_after": res.objective,
           "improved": res.objective < before, "kept_arcs": n_arcs}
    res.solver_status = status_before
    return out


def run_crgar(instance: Instance, previous: Solution | None, prev_instance: Instance | None,
              budget: float, cfg: CRGARConfig, workers: int = 1, seed: int = 0,
              method_name: str = "crgar") -> tuple[RunResult, dict]:
    if cfg.strategy not in STRATEGIES:
        raise ValueError(cfg.strategy)
    clock = Clock(budget)
    res = RunResult(method=method_name, budget=budget)
    meta: dict = {"config": asdict(cfg), "rounds": []}
    D = disruption_set(prev_instance, instance, previous)

    def retain(sol, obj, name):
        res.objective, res.solution = obj, sol
        res.events.append((clock.elapsed(), obj, f"portfolio:{name}"))

    t = clock.elapsed()
    pf = build_portfolio(instance, previous, PORTFOLIOS[cfg.portfolio],
                         construction_budget=cfg.construction_frac * budget, deadline=clock.deadline,
                         on_improve=retain)
    res.construction_s += clock.elapsed() - t
    meta["portfolio"] = {"chosen": pf.chosen, "objective": pf.objective, "n_candidates": len(pf.candidates)}
    if pf.solution is not None:
        res.construction_objective, res.construction_source = pf.objective, f"portfolio:{pf.chosen}"
    meta["initial_objective"] = res.objective

    local_end = clock.t0 + (cfg.alpha if cfg.final_global else 1.0) * budget
    if res.solution is not None and cfg.initial_stage:
        t = clock.elapsed()
        N0 = make_neighbourhood("N5", instance, res.solution, D, cfg.expansion_frac)
        if N0 and local_end - time.monotonic() > 0.01:
            st = _restricted_solve(res, clock, instance, N0, set(), local_end, workers, seed, cfg)
            st.update({"neighbourhood_s": 0.0, "n_released_ops": len(N0)})
            meta["initial_stage"] = st
        meta["initial_stage_s"] = clock.elapsed() - t

    frozen = None
    for k in range(cfg.max_rounds):
        if res.solution is None or local_end - time.monotonic() < 0.05:
            break
        t = clock.elapsed()
        if frozen is not None and not cfg.recompute:
            N, R, info = frozen
        else:
            N, R, info = make_round_neighbourhood(cfg.strategy, instance, res.solution, D, cfg.expansion_frac, k)
            if frozen is None:
                frozen = (N, R, info)
        nb_s = clock.elapsed() - t
        if not N and not R:
            meta["rounds"].append({"round": k, "empty": True, "neighbourhood_s": nb_s})
            break
        end = local_end if cfg.round_time <= 0 else min(local_end, time.monotonic() + cfg.round_time)
        st = _restricted_solve(res, clock, instance, N, R, end, workers, seed, cfg)
        st.update({"round": k, "neighbourhood_s": nb_s, **info})
        meta["rounds"].append(st)
        if not st["improved"] and cfg.stop_on_fail:
            break
    meta["local_window_s"] = clock.elapsed()

    if cfg.final_global:
        before = res.objective
        t = clock.elapsed()
        run_cpsat(res, clock, instance, res.solution, workers, seed, source="global",
                  params=SOLVER_PARAMS[cfg.global_params])
        meta["global"] = {"status": res.solver_status, "time_s": clock.elapsed() - t,
                          "improved": before is None or (res.objective is not None and res.objective < before)}
    return _finish(res, clock, instance), meta
