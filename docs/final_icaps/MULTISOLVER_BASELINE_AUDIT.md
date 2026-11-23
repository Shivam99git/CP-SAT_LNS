# Multisolver phase, Part 1: baseline audit of the CP-SAT study

Branch `research/icaps2027-final-multisolver` (created from `research/icaps2027-final-empirical` at 39e658d+visual work; all earlier branches preserved, nothing pushed).

## 1. Independent reproduction of the confirmatory numbers

A third, code-disjoint recomputation (`scripts/multisolver/reproduce_cpsat_confirmatory.py`) reads only the raw run files and `FROZEN_CONFIG.json`; it imports nothing from `phase0/analyze_*` or `scripts/final/*`, and manuscript numbers are not inputs. Output: `results/multisolver/audit/cpsat_reproduction.json`.

| Quantity | Recomputed | Agreement with archived analysis |
|---|---|---|
| Top-level run records (one method on one instance-step) | 60,720 | exact |
| Internal CP-SAT invocations inside those records (initial stage, rounds, global) | ~213,000 | not previously reported; distinct from records |
| Restricted solves (initial stages + rounds) | 152,651 | new |
| Confirmatory comparisons | 33 | exact |
| Max \|relative-difference error\| | 2.5e-14 percentage points | — |
| Win/loss mismatches | 0 | — |
| Max \|Holm-p error\| | 0 | — |

Headline values reproduced: SR+Crit vs IAIP-SR −22.41% (35/5, Holm 8.3e-6); vs random rounds −20.38%; vs random-precedence −24.51%; vs time-window −6.13% (26/14, Holm 0.16, n.s.); vs native one-worker CP-SAT −43.80% (40/0); vs four-worker Port+Hint −9.12% (15/5, Holm 0.12, n.s.); M2 critical vs time-window +11.44% (13/27, Holm 0.038).

**Observation that changes wording (not numbers).** For U3 (four workers, −9.1%), U7 vs SR (−9.9%) and U8 vs time-window (−9.5%), the stream-clustered bootstrap CI excludes zero while the Holm-adjusted sign test is not significant. Under the pre-registered dual rule these are "not significant", but "no difference" or "indistinguishable" overstates the evidence; the manuscript now says the residual four-worker advantage is "possible but not established".

## 2. Mechanism quantities recomputed from raw records

`scripts/multisolver/reproduce_mechanism.py` → `results/multisolver/audit/mechanism_reproduction.json`. The manuscript previously transcribed these from `docs/final_icaps/03_critical_vs_timewindow.md` without archived precision or CIs; every transcribed value reproduces exactly, and CIs are now available:

| M2 crit vs time-window (exploratory, uncorrected) | Rel. diff | W/L | 95% CI | p |
|---|---|---|---|---|
| arrival | +8.9% | 13/27 | [+2.5, +15.5] | 0.039 |
| cancellation | +18.5% | 9/29 | [+7.8, +29.5] | 0.002 |
| duration change | +13.3% | 12/26 | [+1.8, +25.0] | 0.034 |
| outage | +9.8% | 11/20 | **[−4.6, +24.8]** | 0.15 |

Correction: "worse in every disruption type" holds for point estimates only; for outage the CI includes zero.

What each protocol holds fixed (new, from raw round metadata):

| | M1 crit | M1 time-window | M2 crit | M2 time-window |
|---|---|---|---|---|
| completed rounds / instance | 2.90 | 1.97 | 5.97 | 5.95 |
| restricted-solver s / instance | 0.28 | 0.29 | 0.33 | 0.48 (+45%) |
| round improvement rate | 66% | 50% | 32% | 38% |
| global-continuation s / instance | 6.55 | 6.54 | 6.51 | 6.35 |

Correction: M1 equalizes restricted time but not rounds; M2 equalizes rounds but gives time-window 45% more restricted-solver time. The earlier statement that the arrival advantage "is an artifact of unequal round counts" is a causal claim the data do not support; the supported statement is that the comparison's sign depends on which resource is matched, and critical-region superiority is not established.

## 3. Strict-improvement semantics (Task 2.1)

Code (`phase0/cobar.py:build_cobar_restricted_model`, `require_improvement=True` is the CRGAR default) adds `C_max <= U - 1`. Hence S ∈ P(S, N) (the base neighbourhood: S satisfies every kept arc) but S ∉ P_imp(S, N). The module docstring and the manuscript both said the incumbent "belongs to every restricted problem"; corrected (docstrings only, no behaviour change), and `tests/unified/test_critical_region_anytime.py::test_strict_improvement_cutoff_excludes_the_incumbent` (10 strategies × 15 instances) now pins: S pinned is feasible in P and infeasible in P_imp; P_imp is INFEASIBLE exactly when P's optimum equals U. Status semantics across the 152,651 restricted solves: 66,224 INFEASIBLE (proof: no strictly better schedule in N), 82,023 OPTIMAL, 3,804 FEASIBLE (improved, no proof), 600 UNKNOWN (no information). The pre-existing test `test_restricted_models_contain_incumbent_and_are_not_relaxations` uses `require_improvement=False`, i.e. it correctly tests the base neighbourhood.

## 4. Test suite

| Suite | Result |
|---|---|
| fast (`pytest`) | 268 passed, 1 failed: `test_icaps_runner_parallel.py::test_checkpoint_partial_progress_then_resume_completes` (checkpoint not yet written when the test interrupts the worker, under a load average of ~15–28 from an unrelated workload); passes 3/3 in isolation. Same timing-sensitive test documented in the previous phase. |
| slow (`pytest -m slow`) | 25/25 passed |
| new strict-improvement test | 10/10 passed |
| new multisolver equivalence suite (`tests/multisolver`) | 183/183 passed |

Logs: `results/multisolver/audit/pytest_fast.txt`, `pytest_slow.txt`.

## 5. Implementation inventory (reused, not rewritten)

Instances, deltas, outages, releases, commitments: `phase0/streams.py`. Validator: `phase0/schedule_validator.py`. CP-SAT research model: `phase0/reuse_methods.build_research_model`. Portfolio (history repairs + dispatching): `phase0/incumbent_portfolio.py`. IAIP-SR: `phase0/impact_aware_reoptimization.py`, `selective_reoptimization.py`. Repeated rounds and neighbourhood strategies: `phase0/critical_region_anytime.py`. Kept arcs / certificates: `phase0/cobar_certificates.py`. PI/statistics: `phase0/analyze_gate1.py`, `analyze_unified_confirmatory.py`. All multisolver code reuses these unchanged (S4 calls the same portfolio, IAIP-SR neighbourhood, `make_round_neighbourhood("crit_expand")` and `kept_arcs`).

## 6. Host condition during this phase

The host was shared with an unrelated CPU-bound workload (14 `xsimk` processes at 100% CPU, load average 15–28) that this work did not start and did not stop. All multisolver runs record per-run CPU/wall and the 1-minute load average; see the final report for the sensitivity analysis.
