# Unified study 05 — Correctness and verification (Part VI)

Status legend: **PASS** (independent oracle), **PASS (self)** (same codebase only), **FAIL->fixed**, **NOT VERIFIED**.

## 1. Formal invariants

**Incumbent retention (not a new theorem).** `RunResult.objective` is updated only by `_accept`/`retain`/the strict-improvement check inside `run_cpsat`, all of which require `obj < res.objective` (or `res.objective is None`). Every round in `critical_region_anytime.run_crgar` goes through `_restricted_solve`, which calls `run_cpsat` the same way. Consequently U_(k+1) <= U_k for every accepted incumbent, by construction, not by proof about any individual CP-SAT round (a round may fail, time out at INFEASIBLE/UNKNOWN, or return a non-improving feasible result — all of these leave `res.objective` untouched). | **PASS (self)**, checked by `test_every_strategy_runs_valid_and_within_the_deadline` (asserts `r["objective_after"] <= r["objective_before"]` for every non-empty round) and by the strictly-decreasing-event-objective assertion in `_check_run`, run across all 10 strategies x 3 streams.

## 2. Neighbourhood correctness

| Property | Status | Evidence |
|---|---|---|
| job precedence preserved in every restricted model | PASS | `build_cobar_restricted_model` reuses `build_research_model` (job-chain constraints always present); `test_restricted_models_contain_incumbent_and_are_not_relaxations` additionally checks the *restricted* optimum is always >= the *full* optimum and <= U on 250 randomized tiny instances (25 x 10 strategies) with outages, releases and commitments |
| machine non-overlap preserved | PASS | same (research model always imposes no-overlap; restricted model only *adds* precedences, never removes the no-overlap) |
| outages, release dates preserved | PASS | same instances include outages and release dates (`random_instance(..., releases=...)`); the independent oracle (`cpsat_optimum`) solves the exact same base model with kept arcs added |
| frozen/committed operations preserved | PASS | 30% of oracle instances get `with_commitments`; `test_restricted_models_contain_incumbent_and_are_not_relaxations` fixes the incumbent in the model and checks it solves OPTIMAL/FEASIBLE (i.e. the commitments plus kept arcs don't exclude it) |
| the incumbent belongs to every restricted neighbourhood | PASS | same test: fixing S in the restricted model is always solvable; `kept_arcs` only includes arcs S itself satisfies (shared code with COBAR, independently oracle-tested there: 5,500 cases, 0 violations, `docs/cobar/06_correctness_verification.md`) |
| machine-order restrictions applied only as intended (N free, kept arcs elsewhere) | PASS | `test_crit_expand_equals_cobar_critical_expand` cross-checks `make_round_neighbourhood("crit_expand", ...)` against COBAR's independently-implemented `_neighbourhood(..., "critical+expand")` -- identical N on 3 streams x 3 steps |
| size matching of controls is exact | PASS | `test_size_matching_of_controls`: random_matched and time_window always produce \|N\| == \|N(crit_expand)\|; precedence always releases the same arc count as crit_expand's kept-arc deficit |
| no stale/invalid operation identifiers | PASS | the restricted model is rebuilt from the *current* `res.solution` every round (via `build_cobar_restricted_model(instance, res.solution, ...)`); operations not in the current instance cannot appear because `kept_arcs`/`make_round_neighbourhood` iterate only over `instance.all_ops` |
| solver statuses interpreted correctly | PASS | `_restricted_solve` records `res.solver_status` verbatim and restores the outer status afterward (does not conflate local and global solver statuses); covered by `test_every_strategy_...` across OPTIMAL/FEASIBLE/INFEASIBLE outcomes (observed in round diagnostics, SS7 of doc 04) |
| unrestricted continuation solves the *current* instance | PASS | `run_cpsat(res, clock, instance, res.solution, ...)` passes `instance` (the current disrupted instance), not any cached/previous one; `test_benchmark_stream_runs_valid` exercises this across a full stream |

## 3. Independent oracle testing

Shared infrastructure with the COBAR study (`tests/cobar/test_certificates.py`): an enumeration oracle (every machine order consistent with given arcs, scheduled by an independent earliest-start routine) and a from-scratch CP-SAT oracle, neither sharing code with the neighbourhood-construction module under test.

| Check | Cases | Result |
|---|---|---|
| restricted optimum >= full optimum, restricted optimum <= U, across all 10 strategies | 250 (25 x 10) tiny instances, outages/releases/commitments | 0 violations |
| job arrivals, cancellations, duration changes, outages, release dates, commitments | covered by `random_instance`'s generator parameters, exercised across all oracle and integration tests | all pass |

## 4. Deadline and anytime correctness

- One monotonic `Clock` per run (`phase0/reuse_methods.py`), shared by the portfolio, every round, and the global stage -- unchanged from IAIP-SR/COBAR, which this study reuses rather than reimplements per the brief's "do not reimplement functionality that already exists and is correct."
- The first feasible incumbent's timestamp is the real elapsed time when the portfolio returned it (via the `on_improve` callback recording `clock.elapsed()`), never 0 -- verified by `test_every_strategy_runs_valid_and_within_the_deadline`'s `0 < ts[0]` assertion across all strategies.
- Failed/non-feasible solver runs are never silently discarded: every round's outcome (`status`, `objective_before`, `objective_after`, `improved`) is appended to `meta["rounds"]` whether or not it improved; `test_no_initial_incumbent_skips_rounds_and_global_still_solves` covers the no-feasible-incumbent-yet case.
- Deadline overshoot is recorded (`overrun_s` in every run record); confirmatory overruns never exceeded 0.050s (U5, 30s budget), p99 <=0.035s in every setting (`06_statistical_results.md`).

## 5. Integration test coverage (tests/unified/test_critical_region_anytime.py, 32 tests)

| Scenario (brief's list) | Test |
|---|---|
| failed round | covered implicitly: `stop_on_fail` tests and round diagnostics include INFEASIBLE/non-improving rounds |
| unchanged incumbent | `test_stop_on_fail_and_fixed_round_protocol` (M1 stops; M2 continues regardless) |
| multiple improvements | round-by-round `objective_after <= objective_before` checked across all non-empty rounds |
| no initial feasible incumbent | `test_no_initial_incumbent_skips_rounds_and_global_still_solves` |
| empty critical region | `test_empty_critical_region_is_handled` (single-operation instance) |
| repeated critical region (frozen vs. recomputed) | `test_frozen_neighbourhood_is_reused_when_recompute_is_off` |
| time exhaustion | `test_time_exhaustion_and_multiworker_execution` (0.2s budget) |
| single-worker execution | all parametrized tests (default workers=1) |
| multiworker execution | `test_time_exhaustion_and_multiworker_execution` (workers=4) |
| resume from an interrupted campaign | `test_campaign_resume_skips_finished_tasks_and_keeps_files` -- runs the campaign CLI twice via subprocess, confirms the second run reports "1 done, 0 to run" and the output file is byte-identical |
| exact trajectory reconstruction | `test_trajectory_reconstruction_matches_independent_integrator` -- compares the archived `per_run` PI computation against the independent `own_pi` integrator from `scripts/unified/verify_baseline.py` on live CRGAR trajectories |

Plus: 9 strategy-parametrized validity tests, a published-benchmark-stream test, a strategy-vs-COBAR cross-check, and a determinism/round-dependence test for every randomized strategy.

## 6. Full suite

Run 2026-10-26 on the efficiency cores (16-19), while the confirmatory campaign ran on the performance cores.

| Suite | Tests | Result | JUnit |
|---|---|---|---|
| fast | 269 (237 pre-existing + 32 new) | all pass | `results/unified_icaps/verification_fast.xml` |
| slow | 25 | all pass | `results/unified_icaps/verification_slow.xml` |

## 7. Not verified

- The round-level correlation between neighbourhood/chain length and improvement quality (recorded in run metadata but not separately analysed; left as future work, noted in `04_mechanism_analysis.md` SS7).
- Behaviour with more than 4 CP-SAT workers.
- CP-SAT per-generator LNS difficulty/selection internals (deliberately not probed; see `02_prior_work_and_novelty.md`).
