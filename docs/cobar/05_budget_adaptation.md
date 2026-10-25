# COBAR 05 — Deadline-aware computation allocation

- **Code:** `phase0/cobar_budget_policy.py`, `phase0/cobar.py`.
- **Tests:** `tests/cobar/test_cobar.py` (`test_decide_rules`, `test_budget_policy_…`, `test_multi_round_…`, `test_stall_stop_…`).

## 1. Accounting

One monotonic clock starts when the method is called. Every step runs against it:
- disruption set;
- portfolio construction and validation;
- global certificate;
- neighbourhood and release;
- certificate;
- local model build and solve;
- global model build and solve;
- final validation.

So B_init + B_cert + B_local + B_global ≤ B, plus the recorded solver return overshoot (`overrun_s`).

**Local window.** The local stage ends at the absolute elapsed time α·B. Preprocessing is therefore charged to the local window; if α·B has already passed, the stage is skipped. The global stage gets whatever remains.

**Separate solver runs.** The local and global stages are separate CP-SAT runs. The global run receives only the current incumbent as a hint; no internal search state carries over, since no such API is used.

## 2. Policies

All policies are deterministic and use only features available at decision time (`Features`):
- budget, worker count, elapsed time;
- incumbent makespan U, certificate bound L, whether the neighbourhood is certified non-improving;
- neighbourhood size, number of operations, whether operations were added.

| Policy | Rule |
|---|---|
| `fixed` | run the local stage until α_long·B (IAIP-SR: α_long = 0.6) |
| `budget` | skip if workers ≥ 4 or B < 4 s; else `fixed` |
| `certificate` | skip if certified non-improving; α_short·B if (U − L)/U < 0.02; else α_long·B |
| `cert+budget` | `budget`, then `certificate` |

Two further rules apply whatever the policy:
- **skip rule** (`skip_certified`): a certified non-improving neighbourhood is never solved;
- **global certificate:** if L_global ≥ U, both solver stages are skipped.

**Within the local stage:**
- the stage stops when CP-SAT proves the restricted problem optimal or infeasible (both are its own proofs, for the restricted model only);
- or at α·B;
- or, optionally, after `stall_s` seconds without an improving solution (watchdog calling `CpSolver.stop_search`);
- with `rounds` > 1, further certificate-guided rounds run inside the same window, while the previous round improved.

**Bounds.** No intermediate CP-SAT bound is used: the policy relies only on the certificate computed before the stage.

**Policy parameters.** These are pre-specified, not tuned: α_long = 0.6 (IAIP-SR's frozen value), α_short = 0.2, gap threshold 0.02, skip_workers = 4, min_budget_s = 4.
- The thresholds 4 workers and 4 s come from the exploratory IAIP-SR E6 observations: the local stage was not detectable with 4 workers or at 2 s, and was at 8 s.
- **Consequence:** the budget-only rule A4 encodes knowledge from E6 streams 601–610. Those streams are therefore development data for COBAR.

## 3. Evidence available before the pilot (development data)

From the `dev_e5c` replay (`scripts/cobar/diagnose_certificates.py`):

| (U − L)/U of the IAIP-SR neighbourhood | local stage improved | INFEASIBLE |
|---|---|---|
| ≤ 0.028 (lowest third) | 44% | 56% |
| 0.028–0.068 | 90% | 10% |
| > 0.068 | 100% | 0% |

**The opportunity gap is informative. Two facts limit what an allocation rule can gain from it:**
- an INFEASIBLE local stage costs a median 21 ms;
- successful stages mostly end early (OPTIMAL: median 0.52 s).

The skip/short rules can therefore save only milliseconds per step. Whether that changes the PI is an empirical question for the pilot.

## 4. Pilot results

*To be filled from `results/cobar/pilot/*/analysis.json`.*
