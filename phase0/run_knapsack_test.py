"""Domain-transfer test: cpsat_cold vs boot_cold on 0-1 knapsack streams.

Same experimental contract as the job-shop runs: a stream of related
instances (base + deltas: item arrivals, removals, value jitter, capacity
changes), every method gets the same wall-clock budget per instance with the
same solver seed on one worker, and best_known per (seed, instance) is the
best value ANY method found.

boot_cold's knapsack bootstrap is the analog of the job-shop list-scheduling
bootstrap: take the previously chosen items that still exist, drop the worst
value/weight items until the (possibly changed) capacity fits, then greedily
add fitting items by value/weight. ~1ms, feasible by construction, recorded
as an anytime FLOOR under an otherwise-identical unhinted CP-SAT solve.

Knapsack is a MAXIMISATION problem, so gap = (best_known - value)/best_known
and trajectories are clipped to be monotone non-decreasing.

Hardness: uniform random instances are trivial for CP-SAT. `--correlated`
generates strongly correlated instances (value = weight + K), the classic
hard family for branch-and-bound.

Usage:
    .venv/bin/python -m phase0.run_knapsack_test --seeds 1 2 --items 500 \\
        --correlated --total-budget 10 --stream-length 4
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass, field, replace

import pandas as pd

from ortools.sat.python import cp_model

# ---------------------------------------------------------------------------
# Knapsack streams
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KInstance:
    index: int
    items: dict[str, tuple[int, int]]   # item_id -> (weight, value)
    capacity: int
    delta_kind: str = "base"


@dataclass
class KConfig:
    n_items: int = 500
    weight_range: tuple[int, int] = (1, 10_000)
    correlated: bool = True     # value = weight + K  (hard family)
    corr_k: int = 5_000
    capacity_frac: float = 0.5
    stream_length: int = 4
    # delta weights
    p_arrival: float = 0.3
    p_removal: float = 0.2
    p_value_jitter: float = 0.3
    p_capacity: float = 0.2
    delta_frac: float = 0.05    # fraction of items touched per delta
    seed: int = 0


def _new_item(rng: random.Random, cfg: KConfig, item_num: int) -> tuple[str, tuple[int, int]]:
    w = rng.randint(*cfg.weight_range)
    v = w + cfg.corr_k if cfg.correlated else rng.randint(*cfg.weight_range)
    return f"it{item_num}", (w, v)


def generate_kstream(cfg: KConfig) -> list[KInstance]:
    rng = random.Random(cfg.seed)
    items = dict(_new_item(rng, cfg, i) for i in range(cfg.n_items))
    cap = int(cfg.capacity_frac * sum(w for w, _ in items.values()))
    stream = [KInstance(0, items, cap)]
    next_num = cfg.n_items
    k = max(1, int(cfg.delta_frac * cfg.n_items))
    for step in range(cfg.stream_length):
        prev = stream[-1]
        items = dict(prev.items)
        cap = prev.capacity
        kind = rng.choices(
            ["arrival", "removal", "value_jitter", "capacity"],
            weights=[cfg.p_arrival, cfg.p_removal, cfg.p_value_jitter, cfg.p_capacity],
        )[0]
        if kind == "removal" and len(items) <= 2 * k:
            kind = "arrival"
        if kind == "arrival":
            for _ in range(k):
                iid, wv = _new_item(rng, cfg, next_num)
                next_num += 1
                items[iid] = wv
        elif kind == "removal":
            for iid in rng.sample(sorted(items), k):
                del items[iid]
        elif kind == "value_jitter":
            for iid in rng.sample(sorted(items), k):
                w, v = items[iid]
                items[iid] = (w, max(1, round(v * rng.uniform(0.7, 1.3))))
        else:  # capacity
            cap = max(1, round(cap * rng.uniform(0.9, 1.1)))
        stream.append(KInstance(prev.index + 1, items, cap, kind))
    return stream


def validate_kselection(inst: KInstance, chosen: set[str]) -> int:
    """Independent feasibility check; returns total value."""
    assert chosen <= set(inst.items), "chosen item not in instance"
    total_w = sum(inst.items[i][0] for i in chosen)
    assert total_w <= inst.capacity, f"over capacity: {total_w} > {inst.capacity}"
    return sum(inst.items[i][1] for i in chosen)


# ---------------------------------------------------------------------------
# Bootstrap (the boot_cold ingredient)
# ---------------------------------------------------------------------------

def knapsack_bootstrap(inst: KInstance, prev_chosen: set[str]) -> set[str]:
    """Adapt the previous selection to the new instance in ~1ms:
    keep surviving items, shed lowest value/weight until capacity fits,
    then greedily add fitting items by value/weight."""
    chosen = {i for i in prev_chosen if i in inst.items}
    total_w = sum(inst.items[i][0] for i in chosen)
    if total_w > inst.capacity:
        for iid in sorted(chosen, key=lambda i: inst.items[i][1] / inst.items[i][0]):
            chosen.discard(iid)
            total_w -= inst.items[iid][0]
            if total_w <= inst.capacity:
                break
    for iid in sorted(inst.items,
                      key=lambda i: -inst.items[i][1] / inst.items[i][0]):
        if iid in chosen:
            continue
        w = inst.items[iid][0]
        if total_w + w <= inst.capacity:
            chosen.add(iid)
            total_w += w
    return chosen


# ---------------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------------

@dataclass
class KResult:
    method: str
    value: int | None
    chosen: set[str] | None
    trajectory: list[tuple[float, int]]  # (elapsed s, value) non-decreasing
    initial_value: int | None = None
    proven_optimal: bool = False


def _solve_knapsack(inst: KInstance, time_limit: float, seed: int,
                    recorder: list[tuple[float, int]], t_offset: float,
                    workers: int = 1) -> tuple[set[str] | None, int | None, bool]:
    model = cp_model.CpModel()
    x = {iid: model.new_bool_var(iid) for iid in inst.items}
    model.add(sum(inst.items[i][0] * x[i] for i in inst.items) <= inst.capacity)
    model.maximize(sum(inst.items[i][1] * x[i] for i in inst.items))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    t0 = time.monotonic()

    class _CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            recorder.append((t_offset + time.monotonic() - t0,
                             int(self.objective_value)))

    status = solver.solve(model, _CB())
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        chosen = {i for i in inst.items if solver.value(x[i])}
        return chosen, int(solver.objective_value), status == cp_model.OPTIMAL
    return None, None, False


def kcold(inst: KInstance, budget: float, seed: int, workers: int = 1) -> KResult:
    traj: list[tuple[float, int]] = []
    chosen, val, opt = _solve_knapsack(inst, budget, seed, traj, 0.0, workers)
    return KResult("cpsat_cold", val, chosen, traj, proven_optimal=opt)


def kboot_cold(inst: KInstance, budget: float, seed: int,
               prev_chosen: set[str] | None, workers: int = 1) -> KResult:
    t0 = time.monotonic()
    traj: list[tuple[float, int]] = []
    floor_val = None
    floor_sel = None
    if prev_chosen is not None:
        floor_sel = knapsack_bootstrap(inst, prev_chosen)
        floor_val = validate_kselection(inst, floor_sel)
        traj.append((time.monotonic() - t0, floor_val))
    chosen, val, opt = _solve_knapsack(
        inst, budget - (time.monotonic() - t0), seed, traj,
        time.monotonic() - t0, workers)
    if val is None or (floor_val is not None and floor_val >= val):
        chosen, val = floor_sel, floor_val
    # monotone non-decreasing anytime trajectory
    mono, best = [], None
    for t, v in sorted(traj):
        if best is None or v > best:
            best = v
            mono.append((t, v))
    return KResult("boot_cold", val, chosen, mono,
                   initial_value=floor_val, proven_optimal=opt)


# ---------------------------------------------------------------------------
# Metrics (maximisation)
# ---------------------------------------------------------------------------

def k_primal_integral(traj: list[tuple[float, int]], best_known: int,
                      budget: float) -> float:
    area, prev_t, prev_gap = 0.0, 0.0, 1.0
    for t, v in sorted(traj):
        t = min(t, budget)
        area += prev_gap * (t - prev_t)
        prev_t, prev_gap = t, max(0.0, (best_known - v) / best_known)
    area += prev_gap * (budget - prev_t)
    return area / budget


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--items", type=int, default=500)
    ap.add_argument("--correlated", action="store_true")
    ap.add_argument("--weight-max", type=int, default=10_000,
                    help="max item weight; large values (1e6) with "
                         "--correlated give instances CP-SAT cannot close "
                         "in a 10s budget")
    ap.add_argument("--total-budget", type=float, default=10.0)
    ap.add_argument("--stream-length", type=int, default=4)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--run-seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for seed in args.seeds:
        cfg = KConfig(n_items=args.items, correlated=args.correlated,
                      weight_range=(1, args.weight_max),
                      corr_k=args.weight_max // 2,
                      stream_length=args.stream_length, seed=seed)
        stream = generate_kstream(cfg)
        print(f"seed {seed}: {len(stream)} instances, {args.items} items, "
              f"deltas={[i.delta_kind for i in stream[1:]]}")
        for method in ("cpsat_cold", "boot_cold"):
            prev: set[str] | None = None
            t0 = time.monotonic()
            for inst in stream:
                if method == "cpsat_cold":
                    res = kcold(inst, args.total_budget, args.run_seed,
                                args.workers)
                else:
                    res = kboot_cold(inst, args.total_budget, args.run_seed,
                                     prev, args.workers)
                if res.chosen is not None:
                    assert validate_kselection(inst, res.chosen) == res.value
                rows.append({"seed": seed, "method": method,
                             "instance": inst.index,
                             "delta_kind": inst.delta_kind,
                             "value": res.value,
                             "initial_value": res.initial_value,
                             "proven_optimal": res.proven_optimal,
                             "_traj": res.trajectory})
                prev = res.chosen if res.chosen is not None else prev
            print(f"  {method:12s} {time.monotonic() - t0:6.1f}s wall")

    df = pd.DataFrame(rows)
    best = df.groupby(["seed", "instance"])["value"].transform("max")
    df["best_known"] = best
    df["final_gap"] = (df.best_known - df.value) / df.best_known
    df["primal_integral"] = [
        k_primal_integral(t, bk, args.total_budget)
        for t, bk in zip(df._traj, df.best_known)
    ]
    out_df = df.drop(columns="_traj")
    if args.out:
        out_df.to_csv(args.out, index=False)
        print(f"\nwrote {args.out}")

    fmt = lambda x: f"{x:.5f}"
    print("\n=== per-instance values ===")
    print(out_df.pivot_table(index=["seed", "instance", "delta_kind"],
                             columns="method",
                             values="value").to_string())
    print("\n=== summary ===")
    print(out_df.groupby("method").agg(
        mean_pi=("primal_integral", "mean"),
        mean_final_gap=("final_gap", "mean"),
        wins=("final_gap", lambda g: int((g == 0).sum())),
        proven_optimal=("proven_optimal", "sum"),
    ).sort_values("mean_pi").to_string(float_format=fmt))

    cold = out_df[out_df.method == "cpsat_cold"].set_index(["seed", "instance"])
    ours = out_df[out_df.method == "boot_cold"].set_index(["seed", "instance"])
    n = len(ours)
    vb = int((ours.value > cold.value).sum())
    vw = int((ours.value < cold.value).sum())
    pb = int((ours.primal_integral < cold.primal_integral).sum())
    print(f"\nboot_cold vs cpsat_cold over {n} instances:")
    print(f"  final value     : better {vb}, worse {vw}, tied {n - vb - vw}")
    print(f"  primal integral : better {pb} / {n}")


if __name__ == "__main__":
    main()
