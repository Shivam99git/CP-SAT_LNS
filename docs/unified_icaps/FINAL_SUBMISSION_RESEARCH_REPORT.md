# Unified ICAPS-27 Study — Final Submission Research Report

- **Branch:** `research/icaps-unified-critical-rounds` (local only; never pushed). Archived branches `research/iaip-sr` and `research/cobar-certificate-guided` are untouched.
- **Period:** 2026-10-26 to 2026-11-23.
- **Verdict: CONDITIONAL GO** (full justification: §21, §25).

## 1. The original Floor contribution

A prior stage of this project (archived manuscript, `paper/icaps27_iaip/`, precursor `Floor, Not Hint`) established that keeping an external, repaired feasible incumbent beside an unmodified solver run ("Floor") never degrades the solver's own anytime trajectory and empirically beat cold-start and warm-hint baselines on synthetic job-shop streams. This is foundational to every later stage; it is reused unchanged and not re-verified here.

## 2. The IAIP-SR contribution

IAIP-SR (Impact-Aware Incumbent Portfolio with Selective Reoptimization) added: a portfolio of validated incumbents (repairs + dispatching rules, each retained when built); a single disruption-centred restricted CP-SAT stage (25% breadth-first neighbourhood, `Cmax <= U-1`); and a hinted global continuation, all under one deadline. It was confirmed, on its own frozen held-out streams (seeds 901-920, the COBAR study's later freeze; IAIP-SR's own earlier freeze used different seeds — see `docs/research_extension/FINAL_RESEARCH_REPORT.md`), to beat Fresh+Cold and other historical-reuse baselines with stream-level significance. **Reused unchanged** as the base pipeline (`\base`/B0 in this study) for every comparison.

## 3. COBAR certificate findings (completed negative result)

A sound, calendar-aware lower-bound certificate for restricted neighbourhoods, and a minimum-cut procedure for releasing exactly the machine-order constraints it identifies as blocking improvement, were built and verified against 5,500 independent oracle cases with zero violations (`docs/cobar/03_certificate_theory.md`). As a *decision* device — skipping, releasing, or allocating budget based on the certificate — it changed almost nothing: decisive for only 13/200 restricted neighbourhoods, and CP-SAT itself already proves the same non-improvement in a median 21ms. We do not revisit this mechanism in this study beyond citing it (per the task instruction: "treat the certificate study as a completed negative result"). What COBAR's development pilots *also* found, as a byproduct unrelated to the certificate, was that repeating the restricted stage with the neighbourhood re-centred each round substantially improved anytime quality — this is the question the present study answers with proper controls.

## 4. Critical-region rounds contribution (this study)

This study's contribution is the controlled evaluation, not a new algorithm: `phase0/critical_region_anytime.py` integrates IAIP-SR's portfolio/initial-stage/global-continuation (reused unchanged) with repeated restricted rounds, each re-seeded at the current incumbent's critical region, inside faithful size-matched external analogues of three of CP-SAT's own internal scheduling-LNS generators, so that the value of criticality specifically (versus repetition alone, versus randomness, versus simple time-locality, versus the installed solver's own search) can be separated.

## 5. Existing literature overlap

`docs/unified_icaps/02_prior_work_and_novelty.md`. Full texts of Sun et al. (2026) and Lin & Yang (2026) were **not accessible** (ScienceDirect returns HTTP 403 to automated access; the Elsevier text-mining API listed in the Crossref record requires a key we do not have) — this limitation is recorded, not concealed, and repeated in the manuscript itself. From their abstracts: Lin & Yang's SLR2 already does incumbent-aware selective CP-SAT repair with a *learned* keep/release split; Sun et al. study optimization-scope selection directly with an evolutionary method. Neither critical-path targeting, LNS with CP, nor incumbent portfolios is new (classical references: Balas 1969; van Laarhoven et al. 1992; Nowicki & Smutnicki 1996; Shaw 1998; Godard et al. 2005). Inspecting the installed OR-Tools v9.15 source confirmed CP-SAT ships random-interval, time-window, resource-window and random-precedence scheduling LNS generators with the *same restriction structure* (relax intervals, keep incumbent precedences among the rest) as our method, active only with >1 worker or the experimental `interleave_search` flag on 1 worker.

## 6. Final unified algorithm

`phase0/critical_region_anytime.py::run_crgar` (CRGAR, provisional name — not claimed as novel per se). One deadline covers: portfolio construction -> optional IAIP-SR initial restricted stage -> up to 9 further restricted rounds (each: recompute critical chains -> 25% BFS expansion -> solve restricted model, hinted, `Cmax<=U-1` -> accept iff strictly improving) -> hinted global continuation. Ten neighbourhood-construction strategies share this skeleton, differing only in round-seed selection (`STRATEGIES` in the module), enabling apples-to-apples comparison.

## 7. Source modifications

| File | Change |
|---|---|
| `phase0/critical_region_anytime.py` | new: CRGAR + 10 strategies + M1/M2 protocols + ablations |
| `phase0/run_iaip_campaign.py` | added `crgar\|...` method-string dispatch (additive; existing dispatch unchanged) |
| `phase0/analyze_unified.py`, `analyze_unified_confirmatory.py` | new analysis scripts (stream-level stats, round diagnostics, frozen-hash verification) |
| `scripts/unified/*` | new: independent baseline verifier, dev-pilot and confirmatory launchers, freeze script, supplement builder |
| `tests/unified/test_critical_region_anytime.py` | new: 32 tests |
| `docs/unified_icaps/*`, `paper/icaps27_unified/*` | new |

**No existing behavioral code was altered.** `phase0/cobar.py`, `phase0/cobar_certificates.py`, `phase0/cobar_neighborhood.py`, `phase0/impact_aware_reoptimization.py` (IAIP-SR) and all IAIP-SR/COBAR analysis scripts are untouched; this is verified by the fact that all 237 pre-existing fast tests (169 pre-dating this study plus the 68 COBAR tests) continue to pass unchanged (§9).

## 8. Mathematical verification

`docs/unified_icaps/05_verification.md`. The only formal claim is incumbent retention (U_(k+1) <= U_k by construction of the acceptance rule, not by per-round proof) — stated as elementary, not as a theorem, with its scope (an individual round may fail/timeout/return non-improving) explicit. All certificate-level formal results are inherited unchanged from the COBAR stage and not re-derived.

## 9. Scheduling feasibility verification

269 fast + 25 slow tests pass (`results/unified_icaps/verification_fast.xml`, `verification_slow.xml`), including 32 new tests: every strategy validated on real streams within its deadline; restricted models proven to contain the incumbent and to lie between the full and incumbent objectives on 250 randomized instances with outages/releases/commitments across all 10 strategies; exact size-matching of controls verified; `crit_expand` proven identical to COBAR's independently-implemented `critical+expand`; campaign resume proven byte-identical; trajectory reconstruction proven to match an independent PI integrator.

## 10. Exact-oracle results

Reused from COBAR (shared, unmodified infrastructure): 5,500 cases (2,000 enumeration + 1,000 CP-SAT + 500 global + 1,000 cut-correctness + 1,000 release-loop), 0 violations (`results/cobar/oracle_campaign.json`). This study's own oracle extension: 250 additional randomized cases across the 10 new strategies, 0 violations (§9).

## 11. Existing reported results, independently reproduced

`docs/unified_icaps/01_baseline_verification.md`, `scripts/unified/verify_baseline.py` (shares zero code with the original pipeline: own feasibility checker, own PI integrator, own sign test/Holm/bootstrap). Re-verified 32,890 COBAR records and 22,000 IAIP-SR confirmatory records: 0 infeasible, 0 objective mismatches, complete method x seed grids, 0 checksum mismatches over 913+200 raw files. Recomputed PI matched the archived analysis to rounding error (<=1.2e-16) on every relative difference, W/L and Holm p; bootstrap CIs matched within 1.5e-4 (expected Monte-Carlo noise from a different resampling seed).

## 12. Random-round comparison

U1 (confirmatory): critical rounds (B2) vs. size-matched random rounds (B1): **-20.4%** (35/5 streams, Holm p=8.3e-6). Random rounds themselves vs. the one-round pipeline (B0): -2.5%, **not significant** (21/19, Holm p=0.87) — repeated rounds alone, without structured targeting, add almost nothing.

## 13. Time-window LNS comparison

The central, nuanced finding. U1: B2 vs. size-matched time-window rounds (B3): -6.1%, **not significant** (26/14, Holm p=0.16). Under the fixed-round mechanism-isolation protocol (U2), the sign **reverses**: +11.4% (crit worse), significant (13/27, Holm p=0.038). Across 5 of 6 secondary settings where both were tested, never significant; the sole exception is arrival-only disruptions (U6: -23.6%, 18/2, Holm p=4e-4), where critical targeting is genuinely better. **Not established as superior overall.**

## 14. Precedence-LNS comparison

U1: B2 vs. size-matched random-precedence rounds (B4): **-24.5%** (34/6, Holm p=3.3e-5). Holds; critical targeting beats unstructured precedence relaxation reproducibly.

## 15. Native CP-SAT search comparison

Single-thread (`interleave_search`, confirmed from solver logs to activate CP-SAT's 4 scheduling LNS generators on 1 thread): B2 beats this by **-43.8%** (40/0, Holm p=1.5e-11). **Four workers** (CP-SAT's default multi-worker portfolio, logs confirm the same 4 generators among 13 interleaved subsolvers): B2 vs. this is **-9.1%, not significant** (15/5, Holm p=0.12); B2 vs. B0 at 4 workers is 0.0%, also not significant. **The advantage over native LNS does not survive matched multi-worker comparison.**

## 16. Neighbourhood-size fairness

Verified exactly, not approximately: random and time-window controls always build |N| identical to the critical-region neighbourhood computed on the same incumbent in the same round (`test_size_matching_of_controls`); precedence always releases the same machine-arc count as critical targeting's kept-arc deficit. Confirmed in round diagnostics: mean |N| 85-88 across all three N-based strategies in every setting checked.

## 17. End-to-end timing fairness

One shared monotonic deadline for every method; all controls use identical initial incumbent, round policy, local window (0.6B), global continuation, and worker count, differing only in neighbourhood-construction logic. Native LNS is compared only at matched worker count (1w-vs-1w, 4w-vs-4w), never 1-worker-ours against 4-worker-native. Deadline overrun recorded in every run: max 0.055s (U5, 30s budget), p99 <=0.035s in every setting.

## 18. Multi-seed confirmatory results

`docs/unified_icaps/06_statistical_results.md`. 46,720 records across 9 settings, 5 solver seeds (U5 and some U9 use 3; declared in advance), 40 held-out streams (U1/U2/U4) or 20 (U3,U6-U8) or 34 base instances (U9), stream seeds 1101-1120, confirmed unused anywhere in this project's history before this run.

## 19. Clustered statistical analysis

Unit of inference = stream (base instance for U9); steps and solver seeds averaged within unit before any test; exact sign test with Holm correction within each setting's declared family; stream-clustered bootstrap 95% CI (10,000 resamples). An equivalence margin (+-10% of comparator mean) for the critical-vs-time-window question was fixed *before* the confirmatory run, justified by a development-pilot power calculation (stream-level SD ~0.008-0.01, giving ~80% power to detect differences of roughly 15-17% of mean PI at this sample size — smaller true differences could go undetected, which is why "not significant" is reported as "inconclusive," never as "equivalent," except where the margin criterion is explicitly met).

## 20. Robustness and failure cases

| Setting | B2 vs B0 |
|---|---|
| 2s (U4) | -6.2%, not significant |
| 8s (U1) | **-22.4%**, significant |
| 30s (U5) | **-19.2%**, significant |
| 4 workers (U3) | +0.0%, not significant — **advantage gone** |
| arrival-only (U6) | **-44.8%**, significant, strongest |
| outage-only (U7) | -9.9%, not significant after Holm — **weakest disruption type** |
| high severity (U8) | **-18.8%**, significant |
| published bases (U9) | **-31.5%**, significant |

No setting shows the candidate performing *worse* than the one-round pipeline with statistical significance (no reversal). The advantage is weak/absent at short budgets, with multiple workers, and after outages.

## 21. Scientific novelty assessment

No individual component is new (§5). The decisive empirical questions, per the task's own framing:
1. Does critical-region targeting outperform size-matched random and time-window neighbourhoods? **Yes vs. random (established); not established vs. time-window** (inconclusive, confined to arrivals, reversed under fixed rounds).
2. Does it outperform standard CP-SAT scheduling search under comparable resources? **Yes at 1 worker; not established at 4 workers.**
3. Can the improvement be attributed to a technically distinguishable mechanism rather than more rounds? **Partially**: structured targeting (any of critical/time-window) beats unstructured repetition, but criticality specifically is not shown to be the superior structured choice.

Per the brief's own fallback instruction, since (1) and (2) only partially succeed, **we did not force an algorithmic-novelty claim**; the manuscript is framed as an empirical investigation (its title and abstract state this directly).

## 22. Final manuscript audit

`docs/unified_icaps/07_manuscript_audit.md`. 11/12 checks PASS; 1 (bibliographic completeness) PASS-with-disclosure (two key related papers accessible only via abstract, stated openly in the manuscript itself). 108 claim macros, 0 undefined, 0 hand-typed result literals (mechanically verified by `check_claims.py`, which itself had a masking bug found and fixed during the COBAR stage and is reused correctly here). 5 pages including references (8-page limit), AAAI-27 kit, Type 1 fonts only, 0 forbidden packages/commands, metadata-stripped submission PDF with 0 annotations.

## 23. Anonymous supplement verification

ICAPS-27's CFP (fetched 2026-11-23, quoted directly) sets a **100MB** supplementary-material limit, requires anonymization, and states reviewers are not obliged to read it. Built via `scripts/unified/build_supplement.sh`: all code (phase0/, tests/, scripts/, ~3.3MB), all documentation, the manuscript sources, every saved *analysis* output (not raw per-run trajectories, which total several hundred MB across all campaigns and would exceed the limit), frozen-configuration files, run manifests, and per-campaign raw-file SHA-256 checksums (so the included analyses remain independently checkable against the — separately preserved, not redistributed in the capped bundle — raw files). Result: **89MB uncompressed, 5.0MB zipped** (`results/unified_icaps/supplement/anonymous_supplement.zip`, SHA-256 `5de1e557b277bc7d24925a9d270f789d82aea09f194828ac56b74b30c8021694`), well under the cap. Scrubbed for identifying paths/emails/git history; one residual match is the scrub script's own search-pattern string literal (not actual leaked author data — see the script's own grep command). The omission of raw trajectory files is **disclosed in `README_SUPPLEMENT.md` inside the package**, not silently made; the plan for the camera-ready version (an anonymized stable deposit) is stated but not executed, since that requires the user's own account/action outside this environment.

## 24. Unresolved issues

1. Full texts of Sun et al. (2026) and Lin & Yang (2026) remain inaccessible; both are flagged in the manuscript itself rather than silently treated as fully read.
2. No more than 4 CP-SAT workers were tested; whether the native-LNS advantage gap widens further at higher worker counts is open.
3. The round-level correlation between critical-chain length and improvement quality was recorded in raw metadata but not separately analysed (noted as future work in `04_mechanism_analysis.md`).
4. Raw per-run trajectory files for the full study (COBAR + IAIP-SR + this study) are not bundled in the capped anonymous supplement; a stable anonymous deposit for them is planned, not yet created.
5. `paper/icaps27_iaip/` and `paper/icaps27_cobar/` remain as separate directories (preserved per instruction, not deleted); a decision is still needed on whether to formally withdraw/merge them in the author's actual submission system, since this environment has no such system.

## 25. Final recommendation

**CONDITIONAL GO.**

The frozen, pre-registered decision tree (`results/unified_icaps/confirmatory/FROZEN_CONFIG.json`, SHA-256 `a594a25f...`) classifies this result as CONDITIONAL GO, not STRONG GO, because C3 (vs. time-window) is inconclusive rather than superior and C6 (vs. 4-worker native LNS) fails outright — exactly the two criteria explicitly designed to catch an overclaimed novelty result. Per the task's explicit instruction, this has been honored: the manuscript (`paper/icaps27_unified/`) does not claim critical-region search is a superior targeting mechanism. It reports, with full pre-registration and independent verification, that repeated and recomputed (not frozen, not single-shot) restricted reoptimization targeted at *some* coherent region of the incumbent reliably improves an incumbent-aware anytime pipeline over no repetition and over unstructured repetition, under a single solver worker across most budgets and disruption types — and that this entire family of findings is specific to single-worker CP-SAT and to the choice between structured-vs-unstructured targeting, not to the superiority of criticality as the specific structuring principle. This is offered as the defensible, non-overstated empirical contribution the task's own fallback criteria anticipated for exactly this outcome.
