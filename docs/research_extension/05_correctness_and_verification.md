# 05 — Correctness and Verification

Status legend:
- **PASS** — checked by an executed test or check whose oracle is independent of the code under test.
- **PASS (self-consistency)** — checked only against the same codebase.
- **FAIL** — a defect was found; the line records its fix.
- **NOT VERIFIED** — no check exists.

Test files: `tests/test_reuse_methods.py`, `tests/test_analyze_gate1.py`, `tests/test_event_localized_repair.py`, `tests/test_incumbent_portfolio.py`, `tests/test_selective_reoptimization.py`. The full-suite run is recorded in §H.

## A. Schedule validity (`phase0/schedule_validator.py`)

| Property | Status | Evidence |
|---|---|---|
| every operation present exactly once; cancelled operations absent | PASS | `test_validator_rejects` (missing and extra ids) |
| integer, non-negative starts | PASS | `test_validator_rejects` |
| job precedence | PASS | `test_validator_rejects` |
| machine non-overlap (adjacent-pair check is sufficient) | PASS | `test_validator_rejects` + argument in the validator docstring (if no consecutive pair in start order overlaps, e_i ≤ s_{i+1} ≤ … ≤ s_j, so none does) |
| outages respected | PASS | `test_validator_outage_release_and_commitment` |
| release dates respected | PASS | same |
| commitments preserved | PASS | same |
| zero-length operations occupy no time | PASS | `test_validator_zero_length_interval_does_not_occupy_machine` |
| objective equals the returned schedule's makespan | PASS | every method test asserts `check_schedule(...) == objective` |

## B. Graph algorithms (`phase0/event_localized_repair.py`)

| Property | Status | Evidence |
|---|---|---|
| fixed-order earliest-start evaluation (incl. outages, release dates) | PASS | equals an independent CP-SAT formulation (orders as precedences, min sum of starts) on 150 random instances |
| cycle detection | PASS | hand-built cycle; on random orders `CycleError` ⇔ the oracle reports infeasible |
| insertion never creates a cycle | PASS | proof in `03_event_localized_repair.md` §2 + randomized test (40 instances, every operation inserted in random order) |
| cycle check when re-inserting a mid-chain operation | FAIL → fixed | first version ignored the job successor; random outage streams produced `CycleError` fallbacks; fixed by forbidding positions after descendants of js |
| outage core = operations delayed by the calendar | FAIL → fixed | first version tested evaluated intervals, which never intersect outages (core always empty); found by code review |
| commitments respected by insertion and fallback | FAIL → fixed | insertion could precede a committed operation, and the MWKR fallback ignored commitments; fixed (insert only after the last committed op; `committed_dispatch`); tested |
| incremental = full recomputation under the stated dirty-set assumptions | PASS | 6 seeds × 5 delta mixes |
| counterexample: changed machine predecessor not marked dirty | PASS (shows failure as predicted) | `test_counterexample_insertion_without_dirty_successor` |
| repair valid on every delta kind, release dates, commitments, empty / single job / garbage history | PASS | `test_repair_*` |
| contradictory history → validated fallback | PASS | `test_repair_handles_contradictory_history_with_fallback` |
| repair = archived Floor for deltas without a core | PASS (self-consistency) | `test_repair_reproduces_floor_when_nothing_is_removed` |

## C. Solver integration

| Property | Status | Evidence |
|---|---|---|
| CP-SAT model optimum = exact optimum | PASS | equals brute-force enumeration of all machine orders on 40 tiny instances with outages (`test_cpsat_model_optimum_matches_enumeration`) |
| restricted model contains the incumbent; empty neighbourhood = fixed-order evaluation | PASS | `test_restriction_contains_incumbent_and_empty_neighbourhood_is_fixed_orders` |
| full neighbourhood = unrestricted optimum | PASS | equals enumeration on 15 instances |
| improvement cutoff on an optimal incumbent → INFEASIBLE, incumbent kept | PASS | `test_require_improvement_on_optimal_incumbent_is_infeasible` |
| retained incumbent never replaced by a worse or invalid schedule | PASS | `test_selective_solve_never_worsens_and_validates`; `run_cpsat` validates before accepting |
| no-time-left / no-solution paths | PASS (code path) | `run_cpsat` returns without a solver call when < 10 ms remain; noted in `notes` |
| UNKNOWN / timeout statuses recorded | PASS | statuses are recorded per run; campaign integrity counts |

## D. Deadlines

| Property | Status | Evidence |
|---|---|---|
| one monotonic deadline covering construction, model build, solve and validation | PASS | `Clock` in `reuse_methods.py`; construction and model build are timed inside it |
| constructed incumbent never timestamped at t = 0 | PASS | `test_constructed_incumbent_is_timestamped_after_construction`, integrated tests |
| local phase ≤ α·B; overall ≤ B plus recorded solver overshoot | PASS | integrated tests; overruns recorded per run (`overrun_s`) and reported, never excluded |

## E. Reproducibility

| Property | Status | Evidence |
|---|---|---|
| resume does not change recorded results | PASS | Gate 1 smoke: second run skipped every task; output files byte-identical (MD5) |
| full configuration identity per record | PASS | protocol, stream, size, stream seed, step, solver seed, method/config string, budget, workers, severity, previous-solution source, git revision, host, CPU affinity |
| streams reproducible from seed; instances serialized | PASS | `instances/*.json` written per campaign |

## F. Statistics (`phase0/analyze_gate1.py`)

| Property | Status | Evidence |
|---|---|---|
| primal-integral integration (no incumbent, windows, cap, post-deadline events, ordering) | PASS | hand-computed cases in `tests/test_analyze_gate1.py` |
| sign test, Holm, cluster bootstrap | PASS | same file |

## G. Not verified

- Behaviour with more than one CP-SAT worker for the new methods (not yet exercised).
- RCPSP or knapsack versions of the new mechanism: **not implemented**. The new methods are job-shop only, and no cross-domain claim is made for them.

## H. Full-suite run

2026-10-23, run on the efficiency cores (CPUs 16–19), after the anytime-portfolio change. JUnit files: `results/research_extension/extension_{fast,slow}.xml`.

| Suite | Tests | Failures | Errors |
|---|---|---|---|
| fast (`pytest tests/ -q`): 130 pre-existing + 69 new | 199 | 0 | 0 |
| slow (`-m slow`) | 25 | 0 | 0 |

No pre-existing test was modified. Before any extension code, the same suites ran 130 + 25 tests with 0 failures.
