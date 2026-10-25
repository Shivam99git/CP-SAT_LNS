# COBAR — Final Research Report

- **Branch:** `research/cobar-certificate-guided` (local; nothing pushed).
- **Period:** 2026-10-25 to 2026-10-26.
- **Sources:** every number is from a saved analysis output named in its section.
- **Labels:** development results are exploratory; confirmatory results come from a configuration frozen before the held-out run (`results/cobar/confirmatory/FROZEN_CONFIG.json`, SHA-256 `7d3dec95…`).

## 17. Recommendation (summary first)

**CONDITIONAL GO**, under the classification fixed before the confirmatory run (`08_confirmatory_protocol.md`).

- **Performance criteria:** all met on held-out data.
- **Certificate:** sound, but it provides no measurable value as a decision device.
- **Credited mechanism:** repeated restricted rounds seeded at the incumbent's critical region. This is a known idea (critical-path neighbourhoods), not a new one.
- **Implication for a paper:**
  - keep only the components with evidence (IAIP-SR + critical-region rounds);
  - report the certificate framework as a sound but negative result;
  - do not present the rounds as a novel algorithm.

## 1. Existing IAIP-SR baseline

`01_baseline_audit.md` reproduces it:
- 204 + 25 tests pass;
- 913 raw files match their checksums;
- re-running the analyses gives byte-identical outputs.

Reference claims, recomputed:

| Setting | IAIP-SR vs Fresh+Cold |
|---|---|
| confirmatory | −43.2% |
| E6: 30 s | −55.3% |
| E6: 4 workers | −65.7% |
| E6: arrival-only | −63.1% |
| E6: outage-only | −42.2% |
| E6: high severity | −58.5% |
| E6: published bases | −61.2% |

All E6 runs: 11,220, validated.

**Audit findings:**
- intermediate solver incumbents are not validated by the campaigns (a later audit found them all valid, §7);
- Lin & Yang 2026 (SLR2) is uncited by the IAIP-SR manuscript.

## 2. Original hypothesis

Sound improvement-opportunity certificates, combined with disruption-aware neighbourhoods and deadline-aware solver allocation, improve anytime scheduling beyond IAIP-SR and strong portfolio + global CP-SAT baselines.

## 3. Proposed COBAR mechanism

1. Certificate L(N, R): the path bound and the machine bound over the restricted problem, with outages, releases and commitments.
2. Skip of certified neighbourhoods.
3. Minimum-cut release of the arcs on obstructing binding chains, with recomputation.
4. Certificate-aware budget policy: skip, short or long local stage.
5. Global certificate.
6. Certificate-guided local rounds (added in development).

## 4. Implemented functionality

| Module | File | Tests |
|---|---|---|
| certificates | `phase0/cobar_certificates.py` | `tests/cobar/test_certificates.py` |
| obstruction, min cut, release loop | `phase0/cobar_neighborhood.py` | `tests/cobar/test_neighborhood.py`, `test_counterexamples.py` |
| budget policy | `phase0/cobar_budget_policy.py` | `tests/cobar/test_cobar.py` |
| integrated method (rounds, controls, stall stop, native-LNS control) | `phase0/cobar.py` | `tests/cobar/test_cobar.py` |
| shared solver call: optional `params`, `stall_s`; defaults unchanged | `phase0/reuse_methods.py` | all pre-existing tests |
| runner (`cobar\|…` methods), analyses | `phase0/run_iaip_campaign.py`, `analyze_cobar.py`, `analyze_cobar_confirmatory.py` | — |
| scripts | `scripts/cobar/*` (pilots, freeze, confirmatory, oracle campaign, intermediate audit, certificate diagnostic) | — |

## 5. Verified mathematical results

Details in `03_certificate_theory.md`.

| Result | Classification |
|---|---|
| L(N, R) ≤ C*(N, R) (Prop. 1); L ≥ U ⇒ no improvement in the neighbourhood; global certificate | known lemma, adapted to the restricted problem |
| membership of S needs chaining positive-duration operations only | adapted; the counterexample C3 found by the oracle also affects IAIP-SR's builder (no archived instance has zero durations) |
| min cut over binding chains = minimum hitting set of obstructing chains (Prop. 2) | standard reduction (Menger / max-flow min-cut) applied to a specific graph |
| one cut suffices without calendar effects (Prop. 3); fails with outages (C6) | new proposition with proof, elementary |
| release-tie chain starts (C7); validator vs CP-SAT zero-length semantics (C4); horizon exclusion (C5) | empirical / modeling observations |
| any empirical claim about decisions | not promoted to a theorem |

## 6. Novelty comparison

Details in `02_related_work_and_novelty.md`.

| Work | Relation to COBAR |
|---|---|
| SLR2 (Lin & Yang 2026) | already does selective CP-SAT repair with a *learned* kept/released split |
| L-RHO (Li et al., ICLR 2025), Graph-RHO (2026 preprint) | learn which variables to fix; Graph-RHO uses critical paths as a training bias |
| classical theory (Balas 1969; van Laarhoven et al. 1992; Nowicki & Smutnicki 1996; Balas & Vazacopoulos 1998) | critical-path / critical-block theory and neighbourhoods |
| CP-SAT (OR-Tools 9.15) | runs scheduling LNS internally with more than one worker, or in interleaved mode |

**Possibly new, as a procedure:** the min-cut release and the calendar-aware certificate for restricted CP-SAT neighbourhoods. Neither improved performance.

**Not new:** the credited mechanism (critical-region-seeded restricted rounds).

**Not read in full:** Lin & Yang and Sun et al. (abstract / search summary only).

## 7. Correctness tests

Details in `06_correctness_verification.md`.

| Check | Result |
|---|---|
| repository fast suite | 237 passed |
| slow suite | 25 passed |
| `tests/cobar/` | 33 passed |
| defects found and fixed | C3 (zero-length chaining), C7 (release-tie chain starts), and a bug in the manuscript claim checker (it dropped text after an escaped `\%`) |
| intermediate incumbents (`results/cobar/audit_intermediate.json`) | 977 audited, 0 invalid |

## 8. Exact-oracle results

Source: `results/cobar/oracle_campaign.json`.

| Check | Cases | Decisive | Violations |
|---|---|---|---|
| bound vs exact enumeration | 2,000 | 808 | 0 |
| bound vs exact CP-SAT, incl. zero durations | 1,000 | 358 | 0 |
| global certificate | 500 | 82 | 0 |
| min cut: hits every chain and is minimum (subset enumeration) | 1,000 decisive cases | — | 0 |
| release loop vs exact oracle | 1,000 | — | 0 (578 released, 314 unreleasable, 108 machine-obstructed) |

## 9. Primary confirmatory result

Source: `results/cobar/confirmatory/confirmatory_analysis.json`. Setting S1: 8 s, 1 worker, 40 held-out streams (seeds 901–920) × 5 solver seeds, 8,800 runs, all validated.

| Candidate vs | ΔPI | W/L | 95% CI | Holm p |
|---|---|---|---|---|
| **IAIP-SR (primary)** | **−24.8%** | 39/1 | [−0.0108, −0.0063] | 2.2e-10 |
| portfolio + hinted | −42.7% | 40/0 | [−0.0222, −0.0161] | 7.3e-12 |
| same rounds, random seeds | −17.7% | 38/2 | [−0.0073, −0.0039] | 3.0e-9 |
| *(random rounds vs IAIP-SR)* | −8.6% | 34/6 | [−0.0045, −0.0015] | 8.4e-6 |

Final gap at B vs IAIP-SR: −31.1% (37/3).

Criteria:
- primary target (≥ 5%): met;
- stronger target (≥ 10% vs portfolio + hinted): met;
- location matters: met;
- no final-gap regression: met;
- validity: met.

Exploratory breakdowns (`S1_breakdowns.json`):
- by delta: arrivals −25.4%, cancellations −19.7%, duration changes −25.8%, outages −24.2%;
- by size: 15×15 −17.8% (20/0); 20×20 −29.4% (19/1).

## 10. Ablations (development pilots; `07_pilot_protocol.md`)

| Component | Comparison | ΔPI | W/L | Verdict |
|---|---|---|---|---|
| certificate skip | A2 vs A1 | −1.4% | 8/12 | no effect |
| certificate-guided release | A3 vs A1 | −0.4% | 10/10 | no effect |
| certificate-aware allocation | A5 vs A4 | +2.2% | 11/9 | no effect |
| full single-round COBAR | A6 vs A4 | +2.4% | 12/8 | no effect |
| COBAR with the certificate disabled | A7 ≡ A4 | — | — | identical by construction |
| COBAR with the budget policy disabled | A8 vs A1 | +0.2% | 7/13 | no effect |
| budget-only skip rule, 2 s | A4 vs A1 | **+41.0%** | 3/7 | harmful |
| budget-only skip rule, 4 workers | A4 vs A1 | **+23.7%** | 2/8 | harmful |
| native single-core interleaved LNS (A9) | A9 vs A0 | −1.4% | 9/11 | no effect at 8 s |
| rounds, min-cut seeds (seed 1) | C1 vs A1 | −9.9% | 10/10 | not credited |
| min-cut vs random seeds (seed 1) | C1 vs C3 | −8.8% | 11/9 | not credited |
| rounds, critical-region seeds | C2 vs A1 | −33.5% (seed 1), −28.3% (seed 2) | 16/4, 16/4 | frozen |

**Gain attribution:**

| Source | Evidence | Effect |
|---|---|---|
| better initial incumbents (history-based portfolio) | IAIP-SR study, `confirmatory/supplementary_analysis.json` | −17.1% |
| hinted global continuation | same | −10.5% |
| opportunity screening | development | none |
| released constraints | development | none |
| budget allocation | development | none |
| repeated rounds per se | held-out | −8.6% |
| where the rounds search (critical vs random seeds) | held-out | −17.7% |

## 11. Robustness

Held-out, frozen; settings S2–S7 were predeclared and run in a fixed order.

| Setting | Units | Candidate vs IAIP-SR | W/L | Holm p | vs portfolio + hinted |
|---|---|---|---|---|---|
| S2: 2 s | 40 × 5 seeds | −13.2% | 27/13 | 0.038 | −26.8% |
| S3: 4 workers | 20 × 5 | −7.9% | 14/6 | 0.12 (CI [−0.0026, −0.0002]) | −15.6% |
| S4: arrival-only | 20 × 5 | −40.8% | 20/0 | 3.8e-6 | −64.8% |
| S5: outage-only | 20 × 5 | −14.7% | 16/4 | 0.012 | −27.7% |
| S6: 30 s | 20 × 3 | −21.5% | 19/1 | 4.0e-5 | −46.0% |
| S7: published bases | 34 bases × 5 | −22.4% | 31/3 | 7.7e-7 | −43.0% |

Non-inferiority (5% margin) holds in S2 and S3. Total held-out runs: 32,890, all validated. (The commit message of `09a4479` says 33,690, an addition error; this figure is the correct sum of the per-setting counts.)

## 12. Computational overhead

| Item | Cost |
|---|---|
| certificate | 1.3 ms mean |
| release | 1.5 ms mean |
| candidate's extra rounds (S1) | 2.9 per instance (2.0 improving), seeded at a median of 35 operations |
| local window used (S1) | 1.03 s of the 4.8 s window |
| local stage overshoot | at most 14 ms past α·B (recorded) |
| deadline overruns | max 0.055 s (S3); p99 0.031 s at B = 30 s (S6), ≤ 0.014 s in the other settings |

## 13. Negative results

1. Certificates are decisive for 13/200 IAIP-SR neighbourhoods (P1). They explain 3/29 of CP-SAT's non-improvement proofs, which take a median of 21 ms.
2. Skip, release and certificate-aware allocation have no measurable PI effect.
3. A budget rule built from non-significant evidence was harmful (+41% at 2 s, +24% at 4 workers).
4. Min-cut seeding of the rounds does not beat random seeding.
5. CP-SAT's interleaved search with 4 workers is pathological (+318% vs portfolio + hinted, pilot P4).
6. The first rounds variant's effect was seed-sensitive in development (−26.2% on seed 0, −11.1% on seed 1).

## 14. Threats to validity

- **Generator and objective:** one generator for development and held-out streams; makespan only; stability not controlled.
- **z\*:** best value found, not a proven optimum.
- **Method choice:** the frozen variant (C2) emerged from development rather than from the original plan. It was replicated on a second development seed and then confirmed on held-out data, but the choice itself was data-driven.
- **Single runs:** S3 used 20 streams, and its sign test is not significant after Holm correction.
- **Untested comparison:** CP-SAT's interleaved search was not compared with the candidate on held-out data. It was best at 30 s in a development pilot (P3, 10 streams).
- **Prior art:** Lin & Yang 2026 and Sun et al. 2026 were not read in full.
- **Solver version:** CP-SAT behaviour is version-specific (OR-Tools 9.15).

## 15. Reproducibility status

- **Environment:** `results/cobar/baseline_manifest.json` (versions, hardware, seeds, instance hashes).
- **Configuration:** frozen, with hash.
- **Raw runs:** every COBAR campaign's run files carry a committed `RUNS.sha256`. The files are not in git because of their size.
- **Launchers:** `scripts/cobar/run_pilot*.sh`, `run_confirmatory.sh`.
- **Analyses** are deterministic: the bootstrap uses a fixed seed, and re-running gave identical outputs for the archived campaigns.
- **Not reproducible bit-for-bit:** CP-SAT trajectories under wall-clock limits.

## 16. Manuscript status

`paper/icaps27_cobar/manuscript_submission.pdf`: 5 pages, AAAI-27 kit, anonymous, metadata removed.

**Claim verification.** Every result is a registry macro: 72 used, 0 undefined, 0 hand-typed result literals. Each records its source file, setting, algorithm, comparator, metric, statistic and table (`claims.json`, `claim_map.md`). Tables are generated from the registry.

**Open before submission:**
- read Lin & Yang and Sun et al. in full;
- decide the relationship with the IAIP-SR candidate paper, which presents the same base pipeline;
- add the SLR2 citation to any IAIP-SR version.
