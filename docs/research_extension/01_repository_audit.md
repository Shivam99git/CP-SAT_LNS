# 01 — Repository Audit (before any extension)

Audit date: 2026-10-23. Frozen baseline: commit `8178b2a`, local branch `research/iaip-sr`. Archived results under `results/` were not modified; all new output goes to `results/research_extension/`.

## 0. Files named in the brief that do not exist

The brief lists `phase0/instance_io.py`, `phase0/robust_analysis.py`, `phase0/mechanism_analysis.py`, `phase0/reconcile.py`, `scripts/validate_new_campaign.py`, `scripts/make_confirmatory_tables.py`, `scripts/run_causal_confirmatory.sh`, `scripts/submission_certification_gate.py`, `README_REWORK.md`, `SUBMISSION_READINESS.md` and `requirements_rework.txt`, plus the methods `repaired_hint_only`, `dispatch_spt_plus_cold` and `dispatch_mwkr_plus_cold`. None of these exist anywhere: not in the working copy, not on any branch of the GitHub remote, and not elsewhere on this machine. They appear to come from a separate copy of the project that was never pushed. Everything below describes the code that does exist. The missing experiment was rebuilt from the brief's specification (§12).

## 1. Mathematical model (job shop)

`phase0/streams.py` defines `Operation(op_id, machine, duration)`, `Job(job_id, ops, due_date, weight, release_date)`, `Outage(machine, start, end)` and `Instance(index, num_machines, jobs, outages, touched_ops, delta_kind, severity, frozen_ops, frozen_starts)`.

`phase0/model_builder.py::build_model` builds the CP-SAT model:
- one interval per operation, with integer start and end in `[0, horizon]`, where `horizon` = total processing time + last outage end + 1;
- **job precedence:** `start[b] >= end[a]` for consecutive operations;
- **machine non-overlap:** `add_no_overlap` per machine;
- **outages:** fixed-size intervals inside each machine's `no_overlap`;
- **objective:** minimize `makespan = max(job end)`.

Optional arguments:
- `hint`: `add_hint` on surviving operations' starts.
- `frozen`: preserve the machine order of the listed operations through chain constraints; start times float.
- `exact_frozen`: equality pins.

Validation: `model_builder.validate_solution` checks presence, non-negative starts, job precedence and machine/outage overlap.

## 2. Release dates and committed operations — correctness gaps

- **Release dates** (`Job.release_date`) are honoured only by the dispatching rules (`baselines._dispatch_schedule`). `build_model`, the Floor repair (`harness.list_schedule_bootstrap`) and `validate_solution` ignore them.
- **Commitments** (`Instance.frozen_starts`, created by the `partial_schedule_freeze` delta) are enforced only when a caller passes `exact_frozen`. Cold, Hint and Floor never do, and neither the Floor repair nor the validator checks them.
- **Impact on archived results: none.** No archived campaign used `partial_schedule_freeze` (all delta kinds in `results/icaps/runs/*.csv` were checked). `rush_job` sets only a due date and a weight, so every release date in archived data is 0.
- **New code:** `phase0/schedule_validator.py` checks exactly-once coverage, integer starts, release dates, precedence, machine/outage overlap and commitments. `reuse_methods.build_research_model` adds release-date and commitment constraints to the CP-SAT model. All new methods use both.

## 3. Repair strategies (existing)

- **`harness.list_schedule_bootstrap`** (the Floor repair, "append"): surviving operations are ordered by previous start; new operations are appended in (position in job, op id) order. One greedy pass then starts each operation at max(job-predecessor end, machine available), pushed past overlapping outages. For deltas without new operations, this is exactly the earliest-start evaluation of the previous machine orders. The new `event_localized_repair.evaluate` reproduces it (tested).
- **`bootstrap_policies.py`:** `gap_insert`, `regret_insert` and `beam_insert` insert new jobs' operations into idle machine gaps without moving existing operations, appending when no gap fits. `boot_cold_micro_cp` spends real CP-SAT time on a floor.
- **Archived evidence:** in the arrivals campaign, none of the three insertion rules improved on appending (wins against Cold 84.7–87.5% vs 87.5%; mean PI 0.0238–0.0247).

## 4. Solver configurations and reuse methods (existing)

| Archived method | Implementation | Notes |
|---|---|---|
| `cpsat_cold` | `harness.cpsat_default_solve(prev_solution=None)` | clock starts **after** `build_model` (1.5–3.5 ms excluded, measured) |
| `cpsat_warm` (Hint) | same, `hint=previous` | |
| `boot_cold` (Floor) | `harness.warm_bootstrap_solve(use_hint=False)` | repair recorded at its real elapsed time; continuation `time_limit` is computed before `build_model`, so the run overruns by the build time |
| `boot_warm` (Floor+Hint) | same, `use_hint=True` | |
| `repair_only` | `baselines.repair_only` | SPT on the first instance; repairs its **own previous repair** afterwards |
| `dispatch_spt/mwkr/lpt/fifo/random` | `baselines._dispatch_schedule` | list scheduling on earliest start, priority tie-break; deterministic (job-id tie-break fixed earlier) |
| `fix_and_optimize_50` | floor; earliest-starting 50% of operations pinned exactly; floor as hint | trajectory records solver incumbents only |
| `lns_prev_solution` | floor, then 1 s destroy-and-repair rounds cycling random/delta/critical/outage-window neighbourhoods (25%), hinted, machine order kept outside the destroyed set | |
| `local_branching_prev` | hint = previous; at most 30% of surviving operations may change start (reified equalities) | approximation of local branching |

## 5. Objective, time accounting, primal integral (existing)

- **Primal integral** (`metrics.primal_integral`): gap g = max(0, (z − z*)/z*), with g = 1 before the first incumbent; the integral over [0, B] is divided by B. The gap is uncapped, so PI can exceed 1.
- **z\*:** the best objective any method found on that instance within the same stream configuration (`run_icaps_jssp_suite`). Different configurations (for example, different floor policies) therefore have different z\* even on identical instances.
- **Unrecorded timing:** `bootstrap_time_ms` is 0 for every boot_cold row, because `warm_bootstrap_solve` never sets it. Floor construction cost was never measured before this audit. It is measured now: median 0.05–0.18 ms, max 0.32 ms (`paper/icaps27/time_floor.py`).
- **Never-set status:** `cpsat_default_solve` never sets `proven_optimal`.

## 6. Experiments and data (existing)

`results/icaps/runs/`: pilot, arrivals, workers, paper_main (45 streams: 10×10/15×15/20×20 × seeds 101–115, 10 deltas, B = 8 s, one solver seed, 10 methods), real_benchmarks (OR-Library), Taillard, DMU, SWV, YN. Also RCPSP (`results/icaps/rcpsp/`) and cross-solver (`results/multisolver/`).

Campaigns ran up to 16 concurrent, unpinned processes on a CPU with performance and efficiency cores.

## 7. Statistical practice in the archived analysis — a validity concern

All archived significance tests (`phase0/analyze_icaps_results.py`, `paper/icaps27/verify_numbers.py`, and therefore every p-value in `paper/icaps27/manuscript.tex`) pair at the **instance** level. For example, n = 495 in the main campaign is 45 streams × 11 steps. Consecutive steps of one stream share instance structure, predecessor and solver state, so they are not independent, and those p-values overstate the evidence. Each archived campaign also used a single solver seed. The new analysis (`phase0/analyze_gate1.py`) uses streams as the unit of inference, averaging over seeds and steps within a stream. Gate 1 re-runs the main campaign's configuration with five solver seeds.

## 8. Tests (existing)

155 tests (130 fast, 25 slow), all passing; see `02_environment.md`.

## 9. Earlier unsuccessful extensions

- **Phase 0 / `reopt/`:** learned LNS operator selection (a 27-arm portfolio; round-robin; stall-triggered; persistent contextual epsilon-greedy), a linear Thompson-sampling contextual bandit over reuse actions on deliberately hardened streams (58% worse mean PI than always using Floor), and an oracle-mined context rule (3.9% worse on held-out seeds). Documented in `BOOT_COLD_PAPER.md` §7 and `reopt/README.md`.
- **Gap/regret/beam insertion** for arrivals: no improvement (§3).

## 10. Historical reuse vs fresh construction in archived data (main campaign, 450 stream instances)

Initial makespan of the repaired floor (`bootstrap_objective`, repairing the **solver's** previous output) compared with the better of fresh SPT and MWKR:

| Delta | Floor better | Median initial gap: floor | fresh |
|---|---|---|---|
| arrival | **0 / 163** | **52.2%** | 14.0% |
| cancellation | 104 / 106 | 5.0% | 14.4% |
| duration jitter | 121 / 124 | 3.8% | 14.7% |
| outage | 42 / 57 | 9.1% | 14.5% |

`repair_only`, which repairs its own **unoptimized** history, never beats the best fresh schedule (0/450). Historical repair is therefore not uniformly beneficial: it is good after changes that perturb existing work and poor after arrivals. This motivates both event-localized repair (for arrivals) and a portfolio that includes fresh schedules.

## 11. Manuscript claims that depend on archived data

Every number in `paper/icaps27/manuscript.tex` is recomputed from the archived CSVs by `paper/icaps27/verify_numbers.py` (`verified_numbers.json`). The claims at risk from §7 are its significance statements. The comparisons themselves (means, win shares) are descriptive and unaffected, but their p-values must be replaced by stream-level tests before resubmission. None of the archived claims compares Floor with SPT+Cold or MWKR+Cold; that is the gap Gate 1 fills.

## 12. What was built to replace the missing items

| Brief item | Implemented as |
|---|---|
| seven-method confirmatory comparison | `phase0/reuse_methods.py` (methods), `phase0/run_gate1.py` (Protocol A and B campaign), `phase0/analyze_gate1.py` (stream-level analysis) |
| strict validation | `phase0/schedule_validator.py` |
| event-localized repair | `phase0/event_localized_repair.py` |
| incumbent portfolio | `phase0/incumbent_portfolio.py` |
| impact-selective CP-SAT | `phase0/selective_reoptimization.py` |
| integrated method | `phase0/impact_aware_reoptimization.py`, `phase0/run_iaip_campaign.py` |
