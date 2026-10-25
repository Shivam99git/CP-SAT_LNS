# COBAR 06 — Correctness and verification

Status legend:
- **PASS** — independent oracle;
- **PASS (self)** — same codebase only;
- **FAIL→fixed** — a defect was found and fixed;
- **NOT VERIFIED** — no check exists.

## Test runs

Run 2026-10-25 on the efficiency cores (16–19), concurrently with the confirmatory campaign on the performance cores. Test wall times are irrelevant here.

| Suite | Tests | Passed | Failed | Result file |
|---|---|---|---|---|
| fast, whole repository | 237 (130 pre-existing + 74 IAIP-SR + 33 COBAR) | 237 | 0 | `results/cobar/final_fast.xml` |
| slow | 25 | 25 | 0 | `results/cobar/final_slow.xml` |
| of which `tests/cobar/` | 33 (25 functions; parametrized) | 33 | 0 | — |

**Solver dependence:**
- **Solver-dependent:** the CP-SAT oracles in `test_certificates.py`, `test_neighborhood.py` and `test_counterexamples.py`, and all of `test_cobar.py`.
- **Solver-independent:** the enumeration oracle, max-flow vs brute force, chain/hitting-set enumeration, and the policy rules.

## Certificates (`phase0/cobar_certificates.py`)

| Property | Status | Evidence |
|---|---|---|
| L(N, R) ≤ exact restricted optimum | PASS | 400 enumeration cases + 200 CP-SAT cases, with outages, releases, commitments, zero durations (CP-SAT), random N and R, and slack incumbents; 0 violations |
| no false certificate | PASS | 177 + 58 decisive cases, each checked: exact optimum = U |
| global certificate | PASS | 150 cases against the full CP-SAT model |
| integer bound handling | PASS | integers throughout; L ≥ U is the integer test of L > U − 1 |
| release dates on first operations only, as in the research model | PASS (self) | same rule as `build_research_model`; exercised by the oracle tests |
| calendars: next-fit only for p > 0 | PASS | `test_zero_length_operation_inside_outage_is_not_pushed` |
| incumbent membership checked; infeasible incumbents rejected | PASS | `test_invalid_inputs_rejected`; membership asserted in every call |
| cyclic fixed-precedence graphs rejected | PASS | same |
| zero-length operations chained by machine order (C3) | FAIL→fixed | positive-duration chains only. The IAIP-SR builder is unaffected on archived data: minimum duration over all 373 instance files is 1 |
| validator vs CP-SAT semantics for zero-length operations (C4) | documented | `test_zero_length_semantics_cpsat_vs_validator` |
| horizon can exclude feasible schedules (C5) | documented | archived instances have no release dates or commitments |

## Graph and release (`phase0/cobar_neighborhood.py`)

| Property | Status | Evidence |
|---|---|---|
| max flow = brute-force minimum cut | PASS | 300 random graphs |
| the cut meets every obstructing chain; it is minimum | PASS | 300 decisive cases; chains and subsets enumerated |
| chain starts with release ties (C7) | FAIL→fixed | found by `test_without_outages_one_cut_removes_the_path_obstruction`; regression test kept |
| one cut suffices without calendar effects (Prop. 3) | PASS | 200 cases |
| outage counterexample to one-cut sufficiency (C6) | PASS (shows the predicted failure) | `test_C6_…` |
| release loop: status consistent, final bound sound, kept arcs as specified | PASS | 250 × 2 modes, CP-SAT oracle |

## Scheduling and integration (`phase0/cobar.py`)

| Property | Status | Evidence |
|---|---|---|
| every configuration returns validated schedules; events ordered and strictly improving; first event after 0; total ≤ B + 0.3 s | PASS | `test_every_configuration_…` (7 configurations) |
| local stage stays inside α·B, including multi-round | PASS | same; `test_multi_round_…` |
| budget rules skip / run as specified | PASS | `test_decide_rules`, `test_budget_policy_…` |
| a certified-optimal incumbent is truly optimal | PASS | `test_global_certificate_…` (CP-SAT proves the same optimum) |
| restricted model contains the incumbent; kept arcs equal IAIP-SR's for positive durations | PASS | `test_restricted_model_…` |
| stall stop and solver parameters reach CP-SAT; an unknown parameter raises | PASS | `test_stall_stop_…`, `test_interleave_parameter_…` |
| round-neighbourhood controls valid and deterministic | PASS | `test_round_neighbourhood_controls_…` |
| extension of the shared `run_cpsat` leaves the archived behaviour unchanged | PASS (self) | default arguments take the old code path; all pre-existing tests pass |

## Campaign-level checks

| Property | Status | Evidence |
|---|---|---|
| intermediate CP-SAT incumbents are valid schedules with the reported makespan | PASS | `results/cobar/audit_intermediate.json`: 977 solutions (945 unrestricted, 32 restricted), 24 instances, 0 invalid |
| pilot outputs validated | PASS | every pilot record (P1–P10) `validated`, 0 without a solution |
| portfolio replay determinism | PASS | `diagnose_certificates.py`: 120/120 replayed construction objectives equal the recorded ones |
| held-out seeds unused before the freeze | PASS | scan of all manifests and CSVs for seeds 901–920: none |
| frozen configuration unchanged during analysis | PASS (by construction) | `run_confirmatory.sh` and `analyze_cobar_confirmatory.py` verify the SHA-256 |

## Not verified

- Behaviour with more than 4 workers.
- Disconnected precedence structures, beyond the random single-operation jobs in the oracle instances.
- Partial-schedule-freeze streams. The generator cannot produce them up front; commitments are covered only in oracle instances.
- Determinism of whole runs across machines: wall-clock budgets make CP-SAT trajectories run-dependent. Five solver seeds and stream-level inference address this statistically, not deterministically.
