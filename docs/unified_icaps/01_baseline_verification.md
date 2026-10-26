# Unified study 01 — Baseline verification (Stage 1)

- **Date:** 2026-10-26.
- **Branch:** `research/icaps-unified-critical-rounds`, created from `research/cobar-certificate-guided` at `5302800`. The archived branches `research/iaip-sr` and `research/cobar-certificate-guided` are untouched. Nothing has been pushed.
- **Manifest:** `results/unified_icaps/baseline_manifest.json`.
- **Full verifier output:** `results/unified_icaps/baseline_verification.json`.

## Method

`scripts/unified/verify_baseline.py` re-verifies the archived COBAR confirmatory settings S1–S7 and the IAIP-SR confirmatory campaign. It shares **no code** with the run or analysis pipeline:
- its own instance reader, built from `instances/*.json`;
- its own feasibility checker: coverage, integer starts, release dates, job precedence, machine overlap including outages, commitments;
- its own primal-integral integrator, sign test, Holm correction, and bootstrap (different resampling seed).

## Results

| Check | COBAR S1–S7 | IAIP-SR confirmatory |
|---|---|---|
| run records | 32,890 (8,800 / 6,600 / 3,300 / 3,300 / 3,300 / 1,980 / 5,610) | 22,000 |
| solver invocations (local + rounds + global, from run metadata) | 91,591 | — |
| physical instances; method × seed grid complete; duplicate run keys | 2,134 instances; complete; 0 | 440; complete; 0 |
| final schedules infeasible under the independent checker | **0** | **0** |
| objective ≠ independent makespan, or ≠ last trajectory value | **0** | **0** |
| predecessor policy | `prev_source = own` for every record; `has_prev` ⇔ step ≥ 1 | same |
| budgets per setting | single value each (8 / 2 / 8 / 8 / 8 / 30 / 8 s) | 8 s |
| mean deadline overrun per method | ≤ 5 ms in every setting; max 55 ms (S3, 4 workers) | ≤ 4 ms |
| solver seeds vs streams | seeds 0–4 (S6: 0–2); stream seeds distinct; one record per (stream, seed, method, step) | same |
| raw files vs committed `RUNS.sha256` | 950 files, 0 mismatches | 200 files, 0 mismatches |
| instances where z\* is attained only after the deadline | 0 | 0 |
| runs with no in-budget incumbent | 0 | 0 |
| runs whose final schedule was found after B (ignored by PI and gap_B) | 16 | 11 |
| published bases (S7) clustered by base instance | yes: 34 units, one stream per base | — |

**PI recomputed from trajectories**, compared with the committed `confirmatory_analysis.json`:

| Quantity | Agreement |
|---|---|
| relative differences | max absolute error ≤ 1.2e-16, i.e. rounding |
| W/L | identical in every comparison of every setting |
| Holm-adjusted p | identical |
| bootstrap CIs | within 1.5e-4 (expected Monte-Carlo difference with another seed) |

**Reproduced table** (candidate = IAIP-SR + critical-region rounds):

| Setting | vs IAIP-SR | W/L | Holm p |
|---|---|---|---|
| S1 8 s | −24.8% | 39/1 | 2.2e-10 |
| S1, vs random rounds | −17.7% | 38/2 | 3.0e-9 |
| S1, random rounds vs IAIP-SR | −8.6% | 34/6 | 8.4e-6 |
| S2 2 s | −13.2% | 27/13 | 0.038 |
| S3 4 workers | −7.9% | 14/6 | 0.12 |
| S4 arrivals | −40.8% | 20/0 | 3.8e-6 |
| S5 outages | −14.7% | 16/4 | 0.012 |
| S6 30 s | −21.5% | 19/1 | 4.0e-5 |
| S7 published bases | −22.4% | 31/3 (bases) | 7.7e-7 |

The IAIP-SR confirmatory family reproduces exactly: vs Fresh+Cold −43.2% (40/0), and the other seven comparisons.

**Tests:** 237 fast + 25 slow, all passed (`results/unified_icaps/baseline_{fast,slow}.xml`).

## Limitations and notes carried forward

1. **"Final makespan" metric.** In 16 COBAR and 11 IAIP-SR runs the returned schedule was found after B, between 0 and 55 ms late. PI and gap_B ignore post-deadline incumbents, but a "final makespan" metric must use the best *in-budget* incumbent. The new study reports that.
2. **Intermediate incumbents** are recorded from CP-SAT objective values; only final schedules are validated in campaigns. The COBAR audit validated 977 intermediate solutions (0 invalid). The new study validates every incumbent that is **accepted** as the retained schedule.
3. **The COBAR held-out streams 901–920 have been examined**, to choose this research direction. They are **not** reused as untouched test data. The new confirmation uses fresh stream seeds (§10 of the protocol, document 06).
4. **The comparison of the candidate with random rounds is not size-matched.** Random rounds used the same number of *seeds* and the same 25% breadth-first cap, not the same neighbourhood size. The new study records neighbourhood sizes per round and adds size-matched controls.

## Gate

The reported numbers and the solver infrastructure are verified.

**Decision: proceed to Stage 2.**
