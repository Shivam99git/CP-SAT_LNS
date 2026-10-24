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

**E6 plan, written 2026-10-24 after the confirmatory analysis and before any E6 run.**

Common settings:
- the frozen IAIP-SR configuration from `FROZEN_CONFIG.json`, unchanged;
- comparators: fresh-portfolio+Cold (the primary comparator), portfolio + hinted global (the selective-stage control), Floor and Cold;
- 10 deltas per stream; solver seed 0;
- new stream seeds 601–610, never used in the research extension before;
- performance cores;
- runner: `phase0/run_iaip_campaign.py`. The options `--delta-mix`, `--severity`, `--benchmarks` and `--cpu-groups` were added for E6; their defaults reproduce the confirmatory streams exactly, as tested.

| Run | Variation | Streams |
|---|---|---|
| E6a | B = 2 s and B = 30 s | 15×15, 20×20 × 601–610 |
| E6b | B = 8 s, 4 CP-SAT workers; each process pinned to 4 physical cores ({0,2,4,6}, {8,10,12,14}) | same 20 |
| E6c | B = 8 s; arrival-only, outage-only and high-severity streams | same 20 sizes and seeds |
| E6d | B = 8 s; published instances as stream bases: ta01–ta20, dmu01–05, swv01–05, yn1–4 (34 bases) × stream seeds 601–602 | 68 |

Arriving jobs in E6d have one operation per machine, with durations drawn from the base's own duration range. E6d inference uses the **base instance** as the unit: the two streams per base are averaged first.

All E6 results are exploratory. They are reported in full, whichever way they come out.

Freeze-only streams are **not run**. The generator's `partial_schedule_freeze` delta needs the previous step's solution at generation time. These campaigns generate streams up front, so every freeze step would be a no-op, and running them would test nothing.

## 7. Rules

These are fixed in advance:
- No instance, stream or seed is removed after observing results.
- Endpoints are not changed after confirmatory results are seen.
- No parameter is tuned on streams 101–115 or 501–520.
- Runs with deadline overruns, failures or no solution stay in the analysis: a run without a solution has gap 1 throughout.
- Every reported percentage is produced by a script from saved raw records.

## 8. Deviations log

**2026-10-23 — anytime portfolio (affects §5's primary comparator).**

*What the development sweep showed.* The first version of `build_portfolio` retained an incumbent only after all members were built. Under the predeclared metric (g = 1 before the first incumbent), the delay cost more PI than the extra members recovered:
- the fresh portfolio (first incumbent at about 20 ms) did worse than MWKR+Cold (5 ms): stream mean PI 0.0438 vs 0.0412;
- the full portfolio did no better than ELR alone.

*Change.* The portfolio now publishes every validated improving member at the moment it is built. Construction order became hist, elr, mwkr, spt, insert, lpt, fifo (the fresh portfolio therefore builds MWKR first).

*Effect on the comparator.* This makes the predeclared comparator, fresh-portfolio+Cold, strictly stronger. The change was made on development streams only, before any confirmatory stream was run.

**2026-10-23 — `alpha_rule` added (development only).** By delta type, the local phase helped after arrivals and hurt after cancellations and outages. An option `alpha_rule = new_ops` (run the local phase only when the disruption added operations) was added to the E5 development sweep. It is a pre-solve rule based on an observable event feature. Whether it enters the frozen configuration is decided on development streams only.

**2026-10-24 — confirmatory configuration and comparators (before any confirmatory run, and before Gate 1 was analysed).**

*Selection.* Chosen on development streams 301–310 only:
- `dev_e5` (budget allocation × global mode): the hinted global continuation beat unhinted, and the cutoff variant was worst.
- `dev_e5b` (control: portfolio + hinted global with no local phase): N5 beat N1; a random neighbourhood of equal size was worse than no local phase; `alpha_rule=new_ops` was worse than fixed α and was dropped.
- `dev_e5c` (α ∈ {0.4, 0.6, 0.8}): α = 0.6 was an interior optimum.

Frozen: portfolio=full (anytime), neighbourhood N5 (bounded expansion, 25% of operations), α = 0.6, improvement cutoff in the local phase, global continuation hinted with the current incumbent.

*Added comparators* (the predeclared primary comparison is unchanged: IAIP-SR vs fresh-portfolio+Cold):
- **portfolio + hinted global, no local phase.** It replaces "portfolio+Cold" as the control for the selective stage's value, because the frozen method's global phase is hinted.
- **fresh-portfolio + hinted global.** It gives the fresh baseline the same hinting; on development data it was weaker than unhinted.
- **random-neighbourhood control** at the same α.
- **portfolio+Cold vs fresh-portfolio+Cold**, testing whether history helps.

*Family.* The predeclared family therefore has 8 members (listed in FROZEN_CONFIG.json); Holm correction is over all 8.

*Development caution.* The selective-stage gain over portfolio + hinted varied between development campaigns (α = 0.4: −27%, 13/7 streams in dev_e5b; −38.5%, 15/5 in dev_e5c). No development comparison against that control was significant at 20 streams except in dev_e5c.