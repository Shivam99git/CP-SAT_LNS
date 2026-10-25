# COBAR 08 — Confirmatory protocol (frozen before any held-out run)

- **Written:** 2026-10-25, after the development pilots (`07_pilot_protocol.md`) and before any run on stream seeds 901–920.
- **Held-out check:** a scan of every archived manifest and CSV found no use of seeds 901–920.
- **Frozen artifact:** `results/cobar/confirmatory/FROZEN_CONFIG.json`, with its SHA-256 in `FROZEN_CONFIG.sha256`, written by `scripts/cobar/freeze_cobar.py` at a clean `phase0/` revision.
- **Analysis:** `phase0/analyze_cobar_confirmatory.py` verifies the hash before reading any data.

## Methods

| Role | Method string |
|---|---|
| candidate | `cobar\|neighbourhood=iaip\|use_certificate=0\|skip_certified=0\|global_certificate=0\|policy=fixed\|rounds=10\|round_neighbourhood=critical+expand` |
| iaip_sr | `iaip\|portfolio=full\|alpha=0.6\|neighbourhood=N5\|global_mode=hinted` |
| portfolio_hinted | `iaip\|portfolio=full\|global_mode=hinted` |
| random_rounds (S1 only) | same as the candidate with `round_neighbourhood=random+expand` |

## Data and settings

- **Streams:** 15×15 and 20×20, stream seeds 901–920 (40 streams), 10 deltas each.
- **Solver seeds:** 0–4.
- **Hardware:** one process per physical performance core; the 4-worker runs use one process per group of 4 physical cores.

| Setting | Budget | Workers | Streams | Methods | Status |
|---|---|---|---|---|---|
| S1 primary | 8 s | 1 | 40 | all four | core |
| S2 short | 2 s | 1 | 40 | candidate, iaip_sr, portfolio_hinted | core |
| S3 workers | 8 s | 4 | 20 (901–910) | same | core |
| S4 arrival-only | 8 s | 1 | 20 | same | secondary |
| S5 outage-only | 8 s | 1 | 20 | same | secondary |
| S6 longer budget | 30 s | 1 | 20, solver seeds 0–2 | same | secondary |
| S7 published bases | 8 s | 1 | 34 bases × stream seed 901; unit = base | same | secondary |

**Order and reporting.** Settings run in this order. Every setting that runs is reported, whatever it shows; a setting that does not run is reported as not run.

## Analysis

- **Unit:** the stream (S7: the base instance). Steps 1–10 and the solver seeds are averaged within a unit.
- **Reference makespan:** a shared z\* per physical instance within each setting.
- **Tests:** exact sign test with Holm correction over the S1 family (4 comparisons) and within each other setting; stream-clustered bootstrap 95% CI (10,000 resamples).

## Criteria (fixed now)

| Criterion | Definition |
|---|---|
| primary target | S1, candidate vs iaip_sr: mean PI reduction ≥ 5%, CI upper bound < 0, Holm p < 0.05 |
| stronger target | S1, candidate vs portfolio_hinted: reduction ≥ 10%, CI upper bound < 0 |
| location matters | S1, candidate vs random_rounds: CI upper bound < 0 |
| non-inferiority (S2, S3) | upper 95% CI bound of mean(candidate − iaip_sr) < 0.05 × mean(iaip_sr); margin fixed now. A non-significant difference is **not** read as equivalence |
| no final-gap regression | S1 gap_B: CI lower bound ≤ 0 or mean difference ≤ 0 |
| validity | 100% validated outputs |

## Classification (fixed now)

| Verdict | Condition |
|---|---|
| **GO** | all criteria hold **and** a credited component is a new mechanism |
| **CONDITIONAL GO** | the performance criteria hold, but the credited mechanism is not new. This is the expected best case: the credited mechanism is critical-region-seeded rounds, a known idea, and the certificate components showed no value in development |
| **NO-GO** | the primary target fails |
