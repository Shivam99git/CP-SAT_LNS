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

Source: `results/unified_icaps/confirmatory/confirmatory_analysis.json`. All 9 settings ran; 46,720 records total; **0 not validated, 0 without a solution** in every setting.

### U1 primary (40 streams x 5 seeds, 8 s, 1 worker)

Mean PI: B2_crit .0256 < B3_timewin .0273 < B1_random .0322 < B0_iaip .0330 < B4_prec .0340 < B6_port_hint .0447 < B5_native1w .0456.

| Comparison | DeltaPI | W/L | 95% CI | Holm p |
|---|---|---|---|---|
| B2 vs B0 (IAIP-SR) | -22.4% | 35/5 | [-0.0097,-0.0053] | 8.3e-06 |
| B2 vs B1 (random, matched) | -20.4% | 35/5 | [-0.0088,-0.0046] | 8.3e-06 |
| B2 vs B3 (time window, matched) | -6.1% | 26/14 | [-0.0036,+0.0002] | 0.16 |
| B2 vs B4 (precedence, matched) | -24.5% | 34/6 | [-0.0109,-0.0060] | 3.3e-05 |
| B2 vs B5 (native LNS, 1 worker) | -43.8% | 40/0 | [-0.0239,-0.0162] | 1.5e-11 |
| B2 vs B6 (portfolio+hint) | -42.7% | 40/0 | [-0.0230,-0.0154] | 1.5e-11 |
| B3 vs B0 | -17.4% | 32/8 | [-0.0087,-0.0031] | 5.5e-04 |
| B1 vs B0 | -2.5% | 21/19 | [-0.0024,+0.0006] | 0.87 |

### U2 mechanism (M2: 6 fixed rounds x 0.4 s)

M2_timewin .0240 < M2_crit .0268 < M2_random .0301 ~ M2_prec .0301.

| Comparison | DeltaPI | W/L | Holm p |
|---|---|---|---|
| crit vs random | -10.8% | 28/12 | 0.033 |
| crit vs time window | **+11.4%** (crit worse) | 13/27 | 0.038 |
| crit vs precedence | -10.9% | 31/9 | 0.002 |
| time window vs random | -20.0% | 34/6 | 3.3e-05 |

### U3 (4 workers, 20 streams x 5 seeds) -- native multi-worker LNS active (B6)

| Comparison | DeltaPI | W/L | Holm p |
|---|---|---|---|
| B2 vs B0 | +0.0% | 12/8 | 1 |
| B2 vs B6 (native, 4w) | -9.1% | 15/5 | 0.12 |
| B2 vs B3 | +2.2% | 10/10 | 1 |

### Secondary settings (B2 vs B0 / B2 vs B3)

| Setting | B2 vs B0 | Holm | B2 vs B3 | Holm |
|---|---|---|---|---|
| U4 (2 s) | -6.2% (23/17) | 0.86 | -1.3% (22/18) | 0.86 |
| U5 (30 s) | -19.2% (17/3) | 0.0052 | -7.0% (13/7) | 0.26 |
| U6 (arrival) | -44.8% (20/0) | 5.7e-06 | **-23.6%** (18/2) | **4e-04** |
| U7 (outage) | -9.9% (14/6) | 0.23 | -7.0% (14/6) | 0.23 |
| U8 (high sev.) | -18.8% (16/4) | 0.024 | -9.5% (14/6) | 0.12 |
| U9 (34 bases) | -31.5% (33/1) | 8.1e-09 | -6.9% (21/13) | 0.23 |

Full per-setting tables with all comparisons, means and CIs are in `confirmatory_analysis.json` and reproduced in `04_mechanism_analysis.md`.

## 3. Criteria and verdict

| Criterion | Result |
|---|---|
| C1 replication (B2 vs B0, >=5%, CI excl. 0, Holm <0.05) | **true** |
| C2 vs random (CI excl. 0, Holm <0.05) | **true** |
| C3 vs time window | **inconclusive** (not superior: CI upper +0.0002 > 0; not inferior either) |
| C4 vs precedence | **true** |
| C5 vs native 1-worker LNS | **true** |
| C6 vs native 4-worker LNS | **false** (Holm 0.12) |
| validity | **true** |

**CLASSIFICATION: CONDITIONAL GO**, exactly as anticipated from development (`03_lns_baseline_protocol.md` SS8). The candidate (IAIP-SR + critical-region rounds) reproducibly beats IAIP-SR, a size-matched random neighbourhood, a size-matched random-precedence neighbourhood, and CP-SAT's own single-thread interleaved LNS. It does **not** reproducibly beat a size-matched time-window neighbourhood (indistinguishable overall, confined to arrival disruptions, reversed under the fixed-round mechanism-isolation protocol), and it does **not** beat CP-SAT's native multi-worker LNS with 4 workers.

Per the pre-registered framing: **no claim of superior critical-region search is made.** The defensible claim is empirical: an incumbent-aware anytime pipeline with repeated, recomputed, spatially-targeted restricted rounds (criticality being one effective, but not uniquely best, targeting rule) reliably improves on IAIP-SR and on unstructured LNS, under a single CP-SAT worker, across most budgets and disruption types, but this advantage is not established over a comparably simple time-window heuristic and vanishes once CP-SAT is given multiple workers.
