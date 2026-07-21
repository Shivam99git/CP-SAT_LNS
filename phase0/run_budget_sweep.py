"""No-oracle budget-split + neighborhood-quality diagnostic sweep.

Runs `cpsat_cold`, `cpsat_warm`, and a set of fixed-arm LNS methods across one
or more seeds and one or more (initial, repair_total, round_slice) budget
splits, all under the SAME total wall-clock budget, and writes per-row results
plus overall / by-delta / by-seed / by-size summaries.

This is a *pre-learning* diagnostic: its only question is whether the stronger,
schedule-aware destroy neighborhoods create any headroom over CP-SAT's own
defaults. It deliberately does NOT run the oracle (too expensive) and does NOT
train any learned policy.

Fairness contract (preserved throughout):
  * every method gets the same `--total-budget` wall-clock per instance;
  * `cpsat_cold`/`cpsat_warm` spend it as one continuous solve (cold = no hint,
    warm = hinted with the previous instance's solution);
  * LNS methods spend it as initial_budget + repair rounds, capped by the split;
  * `best_known` for gap/primal-integral is the best objective ANY method found
    on that (seed, instance), so all methods are scored against one target.

Usage (from the project root):
    .venv/bin/python -m phase0.run_budget_sweep --seeds 1 2 --full-shop \\
        --machines 15 --initial-jobs 15 --stream-length 12 --total-budget 10 \\
        --initial-budgets 8 6 6 --repair-total-budgets 2 4 4 \\
        --round-slice-budgets 0.5 0.5 1.0
"""

from __future__ import annotations

import argparse
import time
from collections import Counter

import pandas as pd

from .harness import SolveResult, cpsat_default_solve, lns_solve
from .metrics import final_gap, primal_integral
from .model_builder import Solution, validate_solution
from .policies import make_policy
from .streams import Instance, StreamConfig, generate_stream

BASELINE_METHODS = ("cpsat_cold", "cpsat_warm")

DEFAULT_LNS_METHODS = (
    "fixed_random_40", "fixed_delta_40",
    "fixed_critical_40", "fixed_machine_40",
    "fixed_bottleneck_40", "fixed_critical_block_40",
    "fixed_delta_expand_40", "fixed_late_jobs_40",
    "fixed_outage_window_40",
)


# ---------------------------------------------------------------------------
# Budget splits
# ---------------------------------------------------------------------------

class Split:
    """One (initial, repair_total, round_slice) budget allocation."""

    def __init__(self, initial: float, repair_total: float, round_slice: float):
        self.initial = initial
        self.repair_total = repair_total
        self.round_slice = round_slice

    @property
    def label(self) -> str:
        return f"i{self.initial:g}_r{self.repair_total:g}_s{self.round_slice:g}"


def _build_stream(seed: int, args: argparse.Namespace) -> list[Instance]:
    cfg = StreamConfig(
        num_machines=args.machines,
        initial_jobs=args.initial_jobs,
        stream_length=args.stream_length,
        seed=seed,
    )
    if args.full_shop:
        cfg.ops_per_job = (args.machines, args.machines)
        cfg.duration_range = (5, 50)
    return generate_stream(cfg)


# ---------------------------------------------------------------------------
# Per-method stream runs
# ---------------------------------------------------------------------------

def _run_baseline_stream(
    method: str, stream: list[Instance], total_budget: float,
    workers: int, seed: int,
) -> list[tuple[int, SolveResult]]:
    """cpsat_cold / cpsat_warm over the whole stream at the full budget."""
    warm = method == "cpsat_warm"
    out: list[tuple[int, SolveResult]] = []
    prev: Solution | None = None
    for idx, inst in enumerate(stream):
        res = cpsat_default_solve(
            inst, total_budget, prev_solution=prev if warm else None,
            workers=workers, seed=seed, method_name=method,
        )
        if res.solution is not None:
            assert validate_solution(inst, res.solution) == res.objective
        out.append((idx, res))
        prev = res.solution if res.solution is not None else prev
    return out


def _run_lns_stream(
    method: str, split: Split, stream: list[Instance], total_budget: float,
    workers: int, seed: int,
) -> list[tuple[int, SolveResult]]:
    """A fixed-arm LNS method over the whole stream under one budget split.
    The previous instance's solution is carried forward as the warm-start hint,
    matching the stream-amortization premise."""
    out: list[tuple[int, SolveResult]] = []
    prev: Solution | None = None
    policy = make_policy(method, seed=seed)
    for idx, inst in enumerate(stream):
        policy.reset_instance()
        res = lns_solve(
            inst, policy, total_budget, split.round_slice,
            prev_solution=prev, workers=workers, seed=seed, method_name=method,
            initial_budget=split.initial,
            repair_total_budget=split.repair_total,
            round_slice_budget=split.round_slice,
        )
        if res.solution is not None:
            assert validate_solution(inst, res.solution) == res.objective
        out.append((idx, res))
        prev = res.solution if res.solution is not None else prev
    return out


# ---------------------------------------------------------------------------
# Row assembly + metrics
# ---------------------------------------------------------------------------

def derive_context_mapping(
    df: pd.DataFrame, split: str, context_col: str = "delta_kind",
    metric: str = "final_gap",
) -> tuple[dict[str, str], str]:
    """Derive a context -> best-arm table from a sweep DataFrame at one split.

    For each value of `context_col`, pick the LNS arm with the lowest mean
    `metric` on the given rows; the global best arm (lowest mean metric across
    all contexts) is the fallback for unseen contexts. Returns (mapping,
    default_arm) with method-name arms (e.g. "fixed_random_40"). MUST be called
    on *training* rows only — applying the table to the same rows it was
    derived from is circular and overstates its quality (see the delta_kind
    diagnostic: the best in-sample delta-gated table only matches cpsat_warm).
    """
    lns = df[(df.split == split) & (~df.method.isin(BASELINE_METHODS))]
    if lns.empty:
        raise ValueError(f"no LNS rows at split {split!r}")
    mapping: dict[str, str] = {}
    for ctx, g in lns.groupby(context_col):
        mapping[ctx] = g.groupby("method")[metric].mean().idxmin()
    default_arm = lns.groupby("method")[metric].mean().idxmin()
    return mapping, default_arm


def _size_bucket(num_ops: int) -> str:
    if num_ops < 150:
        return "small"
    if num_ops <= 250:
        return "medium"
    return "large"


def _assemble_rows(
    raw: list[dict], total_budget: float,
) -> pd.DataFrame:
    """raw items carry the SolveResult under 'result' plus metadata. best_known
    is computed per (seed, instance) across ALL methods/splits, then gap and
    primal integral are scored against it."""
    best_known: dict[tuple[int, int], int] = {}
    for item in raw:
        res: SolveResult = item["result"]
        if res.objective is None:
            continue
        key = (item["seed"], item["instance"])
        if key not in best_known or res.objective < best_known[key]:
            best_known[key] = res.objective

    rows = []
    for item in raw:
        res = item["result"]
        key = (item["seed"], item["instance"])
        bk = best_known.get(key)
        pi = (primal_integral(res.trajectory, bk, total_budget)
              if bk is not None else 1.0)
        fg = final_gap(res, bk) if bk is not None else 1.0
        repair_improvement = (
            res.initial_objective - res.objective
            if res.initial_objective is not None and res.objective is not None
            else 0
        )
        rows.append({
            "seed": item["seed"],
            "method": item["method"],
            "split": item["split"],
            "instance": item["instance"],
            "delta_kind": item["delta_kind"],
            "num_ops": item["num_ops"],
            "size_bucket": _size_bucket(item["num_ops"]),
            "objective": res.objective,
            "initial_objective": res.initial_objective,
            "best_known": bk,
            "final_gap": fg,
            "primal_integral": pi,
            "rounds": len(res.rounds),
            "improving_rounds": res.improving_rounds,
            "repair_improvement": repair_improvement,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def _overall_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["method", "split"])
        .agg(
            mean_pi=("primal_integral", "mean"),
            median_pi=("primal_integral", "median"),
            mean_final_gap=("final_gap", "mean"),
            wins=("final_gap", lambda g: int((g == 0).sum())),
            mean_rounds=("rounds", "mean"),
            mean_improving_rounds=("improving_rounds", "mean"),
            mean_repair_improvement=("repair_improvement", "mean"),
        )
        .reset_index()
        .sort_values("mean_pi")
    )


def _by_delta_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["method", "split", "delta_kind"])
        .agg(
            mean_pi=("primal_integral", "mean"),
            mean_final_gap=("final_gap", "mean"),
            wins=("final_gap", lambda g: int((g == 0).sum())),
        )
        .reset_index()
        .sort_values(["delta_kind", "mean_pi"])
    )


def _by_seed_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["seed", "method", "split"])
        .agg(
            mean_pi=("primal_integral", "mean"),
            mean_final_gap=("final_gap", "mean"),
            wins=("final_gap", lambda g: int((g == 0).sum())),
        )
        .reset_index()
        .sort_values(["seed", "mean_pi"])
    )


def _by_size_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["method", "split", "size_bucket"])
        .agg(
            mean_pi=("primal_integral", "mean"),
            mean_final_gap=("final_gap", "mean"),
            wins=("final_gap", lambda g: int((g == 0).sum())),
        )
        .reset_index()
        .sort_values(["size_bucket", "mean_pi"])
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--total-budget", type=float, default=10.0)
    ap.add_argument("--initial-budgets", type=float, nargs="+",
                    default=[8.0, 6.0, 6.0])
    ap.add_argument("--repair-total-budgets", type=float, nargs="+",
                    default=[2.0, 4.0, 4.0])
    ap.add_argument("--round-slice-budgets", type=float, nargs="+",
                    default=[0.5, 0.5, 1.0])
    ap.add_argument("--machines", type=int, default=15)
    ap.add_argument("--initial-jobs", type=int, default=15)
    ap.add_argument("--stream-length", type=int, default=12)
    ap.add_argument("--full-shop", action="store_true",
                    help="every job visits every machine (hard JSP)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--methods", nargs="+", default=list(DEFAULT_LNS_METHODS),
                    help="LNS methods to sweep (baselines are always included)")
    ap.add_argument("--out-prefix", default="phase0_smart_arms")
    args = ap.parse_args()

    if not (len(args.initial_budgets) == len(args.repair_total_budgets)
            == len(args.round_slice_budgets)):
        ap.error("--initial-budgets, --repair-total-budgets and "
                 "--round-slice-budgets must have the same length")

    splits = [
        Split(i, r, s) for i, r, s in zip(
            args.initial_budgets, args.repair_total_budgets,
            args.round_slice_budgets)
    ]
    for sp in splits:
        if sp.initial + sp.repair_total > args.total_budget + 1e-9:
            ap.error(f"split {sp.label}: initial+repair "
                     f"({sp.initial + sp.repair_total}) exceeds total budget "
                     f"({args.total_budget})")

    suffix = "seeds" + "_".join(str(s) for s in args.seeds)
    print(f"seeds={args.seeds} total_budget={args.total_budget}s "
          f"splits={[sp.label for sp in splits]}")
    print(f"baselines={list(BASELINE_METHODS)}")
    print(f"lns methods={args.methods}\n")

    raw: list[dict] = []

    def record(seed, method, split_label, runs, stream):
        for idx, res in runs:
            inst = stream[idx]
            raw.append({
                "seed": seed, "method": method, "split": split_label,
                "instance": idx, "delta_kind": inst.delta_kind,
                "num_ops": len(inst.all_ops), "result": res,
            })

    for seed in args.seeds:
        stream = _build_stream(seed, args)
        print(f"seed {seed}: {len(stream)} instances, "
              f"{len(stream[0].all_ops)} ops initially, "
              f"deltas={Counter(i.delta_kind for i in stream[1:])}")

        # baselines: full budget, one run per method (independent of split)
        for method in BASELINE_METHODS:
            t0 = time.monotonic()
            runs = _run_baseline_stream(method, stream, args.total_budget,
                                        args.workers, seed)
            record(seed, method, "full", runs, stream)
            print(f"  {method:22s} full           "
                  f"{time.monotonic() - t0:6.1f}s")

        # LNS methods: one run per (method, split)
        for split in splits:
            for method in args.methods:
                t0 = time.monotonic()
                runs = _run_lns_stream(method, split, stream, args.total_budget,
                                       args.workers, seed)
                record(seed, method, split.label, runs, stream)
                print(f"  {method:22s} {split.label:14s} "
                      f"{time.monotonic() - t0:6.1f}s")

    df = _assemble_rows(raw, args.total_budget)

    sweep_path = f"{args.out_prefix}_sweep_{suffix}.csv"
    overall = _overall_summary(df)
    by_delta = _by_delta_summary(df)
    by_seed = _by_seed_summary(df)
    by_size = _by_size_summary(df)

    df.to_csv(sweep_path, index=False)
    overall.to_csv(f"{args.out_prefix}_summary_{suffix}.csv", index=False)
    by_delta.to_csv(f"{args.out_prefix}_by_delta_{suffix}.csv", index=False)
    by_seed.to_csv(f"{args.out_prefix}_by_seed_{suffix}.csv", index=False)
    by_size.to_csv(f"{args.out_prefix}_by_size_{suffix}.csv", index=False)

    fmt = lambda x: f"{x:.4f}"
    print(f"\nwrote {sweep_path} and 4 summary files (suffix {suffix})")
    print("\n=== overall (lower mean_pi is better; wins = instances at best_known) ===")
    print(overall.to_string(index=False, float_format=fmt))

    # compact baseline-vs-best-LNS readout
    base = overall[overall.method.isin(BASELINE_METHODS)]
    lns = overall[~overall.method.isin(BASELINE_METHODS)]
    if not base.empty and not lns.empty:
        best_base = base.loc[base.mean_pi.idxmin()]
        best_lns = lns.loc[lns.mean_pi.idxmin()]
        print(f"\nbest baseline : {best_base.method} ({best_base.split}) "
              f"mean_pi={best_base.mean_pi:.4f}")
        print(f"best LNS arm  : {best_lns.method} ({best_lns.split}) "
              f"mean_pi={best_lns.mean_pi:.4f}")
        verdict = ("LNS BEATS best baseline"
                   if best_lns.mean_pi < best_base.mean_pi
                   else "baseline still wins")
        print(f"verdict       : {verdict}")


if __name__ == "__main__":
    main()
