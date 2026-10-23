# 04 — Experimental Methodology (pre-registration)

This section was written on 2026-10-23, after the Gate 1 campaign was launched but **before any Gate 1, development or confirmatory result was inspected**. Changes after that point are listed in §8 with their date and reason.

## 1. Units of inference

- **Independent unit:** the physical stream, i.e. one seeded sequence of instances. Solver seeds and stream steps are averaged within a stream before any comparison. Neither steps nor seeds are ever counted as independent observations.
- **Paired comparison:** methods are compared within a stream, so differences are stream-level paired differences.
- **Inference:**
  - exact two-sided sign test over streams;
  - stream-clustered bootstrap 95% confidence interval of the mean stream difference (10,000 resamples of streams);
  - Holm–Bonferroni correction within each predeclared family.
- **Published benchmarks:** repeated streams built on the same base benchmark are additionally clustered by base instance.

## 2. Metrics (per run, from the saved trajectory)

| Metric | Definition |
|---|---|
| `pi` (primary) | archived primal integral: g = (z − z\*)/z\*, g = 1 before the first incumbent, uncapped, averaged over [0, B] |
| `pi_capped` | the same with g capped at 1 |
| `pi_early`, `pi_late` | the same over [0, B/8] and [B/8, B] |
| `gap_B` | gap of the best incumbent found by elapsed time B (incumbents after the deadline are ignored) |
| `t_first` | elapsed time of the first incumbent (construction time included) |
| integrity | validation failures, runs without a solution, deadline overruns (recorded, never excluded), solver statuses |
| timing | construction, model build, local solver, global solver, total |
| stability | fraction of surviving operations whose start changed |

- **z\*** is shared per physical instance: the best objective found by any run of any method, protocol or solver seed. It is never called an optimum.
- **Proven optima:** recorded separately where known (unchanged PSPLIB instances only).

## 3. Gate 1: historical reuse vs fresh construction

| Parameter | Value |
|---|---|
| Streams | 45: full job shops 10×10, 15×15, 20×20 × stream seeds 101–115 (the archived main-campaign configuration) |
| Stream content | 10 deltas (arrival 0.4, cancellation 0.2, duration jitter 0.25, outage 0.15), durations U[5,50], severity medium |
| Budget | B = 8 s |
| Solver | one worker; solver seeds 0–4 |
| CPU | each process pinned to its own performance core |

Methods: Cold, Hint, Floor, Floor+Hint, Repaired-Hint-Only, SPT+Cold and MWKR+Cold (`phase0/reuse_methods.py`). Each uses one deadline covering construction, model building, solving and validation. A constructed incumbent counts from its real construction time.

Protocols:
- **Protocol B (primary):** each method carries its own previous solution.
- **Protocol A:** the four history-based methods receive a common predecessor from a reference chain (Cold, solver seed 1000) whose cost is excluded under an offline-information protocol. Cold, SPT+Cold and MWKR+Cold do not read history, so their Protocol B runs serve both protocols.

The two protocols are reported separately and never pooled.

**Primary endpoint:** stream mean of `pi` over steps 1–10.

**Predeclared family** (Holm within each protocol): Floor−Cold, Floor−SPT+Cold, Floor−MWKR+Cold, Hint−Cold, Floor+Hint−Floor, Repaired-Hint-Only−Floor, SPT+Cold−Cold, MWKR+Cold−Cold.

**Decision:** historical reuse "has demonstrated measurable value" if Floor beats **both** SPT+Cold and MWKR+Cold under Protocol B, with Holm-corrected p < 0.05 and a confidence interval excluding 0. Otherwise the conclusion is reported as such. In that case the fresh portfolio becomes the baseline that IAIP-SR must beat.

Breakdowns by delta type and size are exploratory.

## 4. IAIP-SR development (exploratory)

Streams: 15×15 and 20×20 × seeds **301–310** (20 streams), 6 deltas, B = 8 s, solver seed 0, efficiency cores. Used only for:
- E2: repair quality;
- E3: portfolio ablation;
- E4: neighbourhood choice;
- E5: budget allocation α and global mode.

Parameter choices are made on these streams only. Development results are labelled exploratory everywhere.

## 5. IAIP-SR confirmatory (frozen before running)

Streams: 15×15 and 20×20 × held-out seeds **501–520** (40 streams), 10 deltas, B = 8 s, solver seeds 0–4, pinned performance cores. No seed in 501–520 is used before the confirmatory run.

The method set and every parameter value are written to `results/research_extension/confirmatory/FROZEN_CONFIG.json`, together with its SHA-256 and the source revision, **before** the run starts.

**Primary comparator:** the strongest fresh-incumbent baseline, fixed in advance as **fresh-portfolio+Cold**. This is the best of SPT, MWKR, LPT and FIFO retained as incumbent, followed by unhinted CP-SAT, so it is at least as good at construction time as any single dispatching rule.

**Primary endpoint:** stream mean `pi`, steps 1–10.

**Predeclared confirmatory family** (Holm): IAIP-SR vs fresh-portfolio+Cold, IAIP-SR vs MWKR+Cold, IAIP-SR vs Floor, IAIP-SR vs Cold, and portfolio+selective vs portfolio+Cold (does the selective stage add value?).

**GO criteria** (from the brief):
- mean PI reduction of at least 15% vs fresh-portfolio+Cold, overhead included;
- improvement on at least 70% of streams;
- a stream-clustered CI excluding 0;
- no systematic final-gap regression;
- 100% validated outputs;
- the selective stage contributes measurable value.

Results that miss these criteria are reported as CONDITIONAL GO or NO-GO under the brief's definitions.

## 6. Robustness (exploratory unless separately frozen)

Budgets, worker counts, delta-only streams (arrival-heavy, outage-heavy, freeze), severities, and published benchmark families (Taillard, DMU, SWV, YN as stream bases), with the frozen configuration and no further tuning.

## 7. Rules

These are fixed in advance:
- No instance, stream or seed is removed after observing results.
- Endpoints are not changed after confirmatory results are seen.
- No parameter is tuned on streams 101–115 or 501–520.
- Runs with deadline overruns, failures or no solution stay in the analysis: a run without a solution has gap 1 throughout.
- Every reported percentage is produced by a script from saved raw records.

## 8. Deviations log

(none yet)
