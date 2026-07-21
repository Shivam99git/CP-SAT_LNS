# ICAPS Experiments: boot_cold for Streaming Reoptimization

## 1. What this project studies

Dynamic scheduling / replanning under a tight compute budget: a solver
faces a **stream** of related job-shop (and, for cross-domain evidence,
project-scheduling/RCPSP and 0-1 knapsack) instances, each a small
structured **delta** away from the last (a job arrives, a machine breaks, a
duration changes). Each instance must be re-solved within a fixed
wall-clock budget. The core method, **boot_cold**, repairs the *previous*
instance's solution into a feasible solution for the *new* instance with a
near-zero-cost (~1ms) constructive heuristic, keeps that repair as an
**anytime incumbent floor** under an otherwise completely unmodified CP-SAT
solve, and reports whichever is better at every point in time. This gives a
formal **never-worse-than-cold-solving** guarantee on final quality and,
empirically, large improvements in *anytime* solution quality (primal
integral) — see `BOOT_COLD_PAPER.md` for the pilot results this repository
extends.

**This is explicitly not a machine-learning contribution** — there is no
training, no learned model. It is framed for dynamic scheduling / replanning
/ anytime optimization venues (ICAPS and similar).

## 2. Installing dependencies

```bash
cd "CP-SAT model"
python3 -m venv .venv          # if .venv/ doesn't already exist
.venv/bin/pip install ortools pandas numpy
# optional, for extra analysis features (both are auto-detected and
# gracefully skipped if absent -- see §10):
.venv/bin/pip install scipy matplotlib
```

## 3. Running smoke tests

```bash
bash scripts/run_icaps_smoke.sh
```

Runs the full pytest suite, then a tiny (~seconds) correctness pass over 4
methods on a 5x5 instance. Stops on the first failure. Output:
`results/icaps/runs/smoke.csv`.

## 4. Reproducing pilot results

```bash
bash scripts/run_icaps_pilot.sh
```

2 sizes (10x10, 15x15) x 3 seeds x 3 budgets (1, 5, 10s) x 7 methods x
6-instance streams = 126 stream-runs. Takes **~30-45 minutes** on typical
hardware (most of it is `cpsat_cold`/`cpsat_warm`/`boot_cold`/`boot_warm`
actually using their full CP-SAT budget on full-shop instances, which don't
close quickly by design — see `BOOT_COLD_PAPER.md`'s hardness discussion).
Safe to re-run: uses `--resume --skip-existing`, so an interrupted run
picks up where it left off. Output: `results/icaps/runs/pilot.csv`.

## 5. Running the ICAPS main suite

```bash
bash scripts/run_icaps_main.sh          # LARGE — days, run in background
bash scripts/run_icaps_ablation.sh      # ~hours
bash scripts/run_icaps_severity.sh      # ~hours
bash scripts/run_icaps_workers.sh       # ~hours (needs a multi-core machine)
bash scripts/run_icaps_budgets.sh       # ~hours (30s budget entries dominate)
bash scripts/run_icaps_arrivals.sh      # ~hours
```

**Check the grid size first** with `--dry-run` before committing compute:

```bash
.venv/bin/python -m phase0.run_icaps_jssp_suite --preset main --dry-run
```

All of these were validated via `--dry-run` in this repository's setup but
**not executed** — their compute cost is appropriate for an unattended
multi-day run on dedicated hardware, not a single working session. All are
resumable (`--resume --skip-existing`) and record per-instance failures into
the CSV's `status`/`error_message` columns without aborting the whole run.

## 6. Analyzing results

```bash
bash scripts/analyze_icaps.sh
```

Reads every CSV in `results/icaps/runs/`, writes aggregate/pairwise/
breakdown tables (CSV + LaTeX) to `results/icaps/tables/`, figures (if
matplotlib is installed) to `results/icaps/figures/`, and a full narrative
report to `results/icaps/report.md`.

## 7. Expected output files

```
results/icaps/
  runs/<preset>.csv              per-instance-per-method rows, unified schema
  runs/<preset>_metadata.json    command, git hash, ortools/python version, timestamp
  tables/per_method_aggregate.csv
  tables/pairwise_vs_cpsat_cold.csv
  tables/breakdown_by_{delta_kind,severity,budget_s,workers,instance_size,...}.csv
  tables/*.tex                   LaTeX tables (every row verified to end in \\)
  figures/*.pdf                  only if matplotlib is installed
  report.md
```

## 8. Hardware / time warnings

- `main` preset: 4 sizes x 30 seeds x 4 budgets x 2 worker counts x 10
  methods x 20-instance streams = **28,800 stream-runs**. At a rough average
  of a few seconds per instance this is on the order of **days**, not hours.
  Run it in the background (`nohup`, `tmux`, `screen`) and monitor
  `logs/main.log`.
- `workers` preset needs a machine with at least 16 physical/logical cores
  to be meaningful (`--workers-list 1 4 8 16`); on a smaller machine, CP-SAT
  will silently clamp to available cores.
- Every preset's instances are **full-shop** (every job visits every
  machine) by construction — this repo's own pilot found smaller/easier
  configurations solve to proven optimality in milliseconds, leaving
  nothing to measure (see `BOOT_COLD_PAPER.md`).

## 9. Meaning of each method

| method | what it does |
|---|---|
| `cpsat_cold` | one full-budget CP-SAT solve, no reuse of history |
| `cpsat_warm` | same, hinted with the previous instance's solution |
| `boot_cold` | ~1ms greedy repair kept as an anytime floor under an **unhinted** CP-SAT continuation — the paper's main method |
| `boot_warm` | same floor, **hinted** continuation |
| `repair_only` | the floor alone, no CP-SAT afterward — measures floor quality in isolation |
| `greedy_from_scratch` | SPT-dispatch construction, ignores any previous solution |
| `dispatch_spt/lpt/mwkr/fifo/random` | 5 classical priority-dispatch rules, solver-free |
| `prev_raw` | naively reuses the previous solution verbatim (usually infeasible — demonstrates why repair is needed) |
| `repair_plus_solver_no_floor` | builds (and pays for) the floor but discards it entirely — isolates whether the *pocket* mechanism, not just the hint, matters |
| `fix_and_optimize_{25,50,75}` | exact-freezes 25/50/75% of operations (by earliest/unaffected/random strategy), reoptimizes the rest |
| `lns_prev_solution` | destroy/repair rounds seeded from the floor (not a fresh CP-SAT solve) |
| `local_branching_prev` | CP-SAT + an approximate constraint limiting how many operations may move from their previous position |
| `micro_repair_cp` | a tiny (default 100ms) CP-SAT repair of only the touched operations, used as the floor (CP-assisted, not near-zero-cost — kept separate from boot_cold) |
| `boot_cold` with `--bootstrap-policy {gap_insert,regret_insert,beam_insert}` | arrival-specific floor variants that insert new operations into machine idle gaps instead of always appending |

## 10. Meaning of each metric

- **primal_integral (PI)**: area under the relative-gap-vs-time curve,
  normalized to [0, 1]. Lower is better. This is the **primary** metric —
  it captures anytime quality (how good the answer is *throughout* the
  budget), which is exactly what boot_cold targets.
- **final_gap**: relative gap of the *final* reported objective to the best
  known answer across all methods on that instance. boot_cold is expected
  to **mostly tie** here (its domination guarantee is exact only against its
  own unmodified continuation, not against a separately-invoked cpsat_cold
  run -- at ICAPS-preset scale it ties/beats independent cpsat_cold 92.4% of
  the time (n=1547), with occasional small losses from wall-clock non-reproducibility;
  see BOOT_COLD_PAPER.md §8), not usually win outright.
- **bootstrap_gap / bootstrap_objective**: the floor's own quality, before
  any CP-SAT continuation.
- **num_moved_ops / fraction_moved_ops / mean|median|max_abs_start_shift /
  machine_order_distance**: stability metrics — how much the schedule
  changed from the previous instance's schedule (relevant to real
  replanning, where excessive schedule churn has its own cost).
- **time_to_{10,5,1}pct_gap_s**: how long until the anytime curve first
  reaches within 10%/5%/1% of the best known answer.
- **optimality_proved**: whether the solver's status was `OPTIMAL` (not
  just `FEASIBLE`) — i.e. whether the search proved no better solution
  exists, independent of which incumbent is reported.
- **Significance**: sign test (exact, dependency-free) and a percentile
  bootstrap 95% CI on the mean pairwise PI difference are always computed
  and are the analysis's primary tools. Wilcoxon signed-rank is computed
  only if `scipy` is installed (checked directly: **not installed** in the
  environment this was built in) and otherwise reported as `NaN` with an
  explicit note in `report.md` — never silently omitted.

## 11. Known limitations

- **Not a learning method.** No training, no learned model, anywhere.
  Framed for ICAPS/dynamic-scheduling venues, not ML venues.
- **Small pilot sample.** The executed `smoke`/`pilot` presets are for
  correctness and a first look, not publication-scale (that's `main`,
  documented but not run here — see §5, §8).
- **Single-threaded by default.** `main`/`workers`/`budgets` presets are
  configured for multi-worker runs but were not executed in this pass; CP-
  SAT's own internal adaptive LNS only activates at `workers > 1`, so this
  is a real, currently-untested confound, not a settled result.
- **Arrivals are the known weak case** for the default `append` floor
  policy (see `BOOT_COLD_PAPER.md` §6/§8); `gap_insert`/`regret_insert`/
  `beam_insert` are implemented and unit-tested to strictly improve the
  floor on a synthetic arrival case, but not yet validated at the `arrivals`
  preset's full scale.
- **RCPSP domain implements 4 of 6 delta kinds.** `duration_jitter`,
  `resource_capacity_reduction`, `activity_insertion`,
  `activity_cancellation` are implemented; `precedence_change` and
  `partial_schedule_freeze`-for-RCPSP are documented TODOs
  (`docs/icaps_experiment_plan.md` §6), not implemented. **Update
  (2026-07-11): validated at real scale** (60 activities, 3 resources, 10
  seeds, 90 instances) — 80/80 primal-integral wins on stream instances
  (p=1.65e-24), see `BOOT_COLD_PAPER.md` §5.4. Previously only smoke-tested.
- **Objectives**: only `makespan` is wired into the ICAPS suite runner.
  `Job.due_date`/`Job.weight`/`Job.release_date` fields exist and the
  `rush_job`/`due_date_change`/`priority_change` deltas populate them, but a
  tardiness/weighted-tardiness *objective* in the CP-SAT model itself is not
  implemented — a documented TODO, not silently missing.
- **Benchmark loader is unvalidated against real files.** No internet
  access in this environment; `benchmark_loaders.py` was tested only
  against small synthetic fixture files in the documented format (see its
  module docstring for the exact caveat and what to spot-check before
  trusting it on a real downloaded instance).
- **scipy/matplotlib not installed** in this environment — Wilcoxon and all
  plots are skipped with an explicit note rather than silently absent; CSV
  and Markdown/LaTeX tables are always produced regardless.
