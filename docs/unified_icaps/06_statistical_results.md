# Unified study 06 — Confirmatory protocol and statistical results

## 1. Pre-registration

- **Written:** 2026-10-30, after the development pilots D1–D3 (`03_lns_baseline_protocol.md`) and before any run on the held-out seeds.
- **Frozen file:** `results/unified_icaps/confirmatory/FROZEN_CONFIG.json`, with its SHA-256 in `FROZEN_CONFIG.sha256`. The launcher and the analysis check the hash.

### Data
- **Held-out streams:** stream seeds **1101–1120**, never used before. A scan of every manifest and CSV in the repository found no seed above 920.
- **Instances:** full m×m job shops with m ∈ {15, 20} (40 streams), durations U[5, 50], 10 deltas.
- **Solver seeds:** 0–4.

**The COBAR held-out streams 901–920 are not reused.** They were examined when choosing this direction.

### Methods
Defined in `03_lns_baseline_protocol.md`.

| ID | Method | Role |
|---|---|---|
| B2 | IAIP-SR + critical-region rounds | candidate |
| B0 | IAIP-SR | archived pipeline |
| B6 | portfolio + hinted CP-SAT | strong baseline; with 4 workers it is CP-SAT's native multi-worker LNS |
| B1 | size-matched random rounds | external LNS control |
| B3 | size-matched time-window rounds | external LNS control |
| B4 | arc-count-matched random-precedence rounds | external LNS control |
| B5 | hinted CP-SAT with `interleave_search` on one worker | native single-thread LNS |
| M2 variants | the same four neighbourhood strategies, 6 rounds × 0.4 s each | mechanism isolation |

### Settings (run in this order)

| Setting | Budget | Workers | Streams × solver seeds | Methods |
|---|---|---|---|---|
| U1 primary | 8 s | 1 | 40 × 5 | B2, B0, B6, B1, B3, B4, B5 |
| U2 mechanism (M2) | 8 s | 1 | 40 × 5 | M2: crit, random, time window, precedence |
| U3 | 8 s | 4 | 20 × 5 | B2, B0, B6 (native LNS), B3 |
| U4 | 2 s | 1 | 40 × 5 | B2, B0, B6, B3 |
| U5 | 30 s | 1 | 20 × 3 | same |
| U6 arrival-only | 8 s | 1 | 20 × 5 | same |
| U7 outage-only | 8 s | 1 | 20 × 5 | same |
| U8 high severity | 8 s | 1 | 20 × 5 | same |
| U9 published bases | 8 s | 1 | 34 bases × 1 stream × 5; unit = base | same |

### Statistics
- **Unit:** the stream (U9: the base instance). Steps 1–10 and the solver seeds are averaged within the unit.
- **Reference:** a shared z\* per physical instance within each setting.
- **Tests:** exact two-sided sign test with Holm correction within each family (U1: 8 comparisons; U2: 4; others: 3), plus a stream-clustered bootstrap 95% CI of the mean difference.
- **Equivalence margin** for B2 vs B3: ±10% of B3's mean PI. It is set here, before any held-out data.

**Power** (from D1). The stream-level SD of the B2 − B3 difference is about 0.008 with one seed. With five seeds and 40 streams, differences of about 15–17% of the mean PI are detectable with 80% power. A non-significant result therefore does **not** show equivalence; only the equivalence criterion can.

### Criteria and classification
These are the frozen file's text.

| Criterion | Condition |
|---|---|
| C1 | U1, B2 vs B0: reduction ≥ 5%, CI upper < 0, Holm < 0.05 |
| C2 | U1, B2 vs B1: CI upper < 0, Holm < 0.05 |
| C3 | U1, B2 vs B3: *superior* if CI upper < 0 and Holm < 0.05; *inferior* if CI lower > 0 and Holm < 0.05; *equivalent* if the 95% CI lies within ±10% of B3's mean; else *inconclusive* |
| C4 | U1, B2 vs B4: CI upper < 0 |
| C5 | U1, B2 vs B5: CI upper < 0 |
| C6 | U3, B2 vs B6 (4 workers): CI upper < 0 |
| validity | all outputs validated |

| Verdict | Condition |
|---|---|
| **STRONG GO** | C1, C2, C3 superior, C4, C5, C6, validity |
| **CONDITIONAL GO** | C1 and validity, but C3 not superior or C6 fails. Then no claim of superior critical-region search is made, and the paper is framed empirically |
| **NO-GO** (novelty) | C1 fails, or C3 inferior |

**Development expectation** (written before the run): CONDITIONAL GO, because time-window rounds matched or beat critical rounds on development data.

## 2. Results

*Filled from `results/unified_icaps/confirmatory/confirmatory_analysis.json` after the runs.*
