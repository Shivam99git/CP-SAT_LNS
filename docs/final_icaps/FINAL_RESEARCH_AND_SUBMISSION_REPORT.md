# Final ICAPS 2027 Research and Submission Report

- **Branch:** `research/icaps2027-final-empirical`, created from `research/icaps-unified-critical-rounds` at `4761b79`. All prior branches (`main`, `research/iaip-sr`, `research/cobar-certificate-guided`, `research/icaps-unified-critical-rounds`) preserved untouched throughout this phase.
- **Date:** 2026-11-23.
- **Final verdict (reaffirmed, §17): CONDITIONAL GO.**

## 1. Original Floor method

Retaining an externally-repaired feasible incumbent beside an unmodified solver run, never degrading that solver run's own anytime trajectory. Reused unchanged in every later stage; not re-verified this phase (no claim in this study depends on re-deriving it).

## 2. IAIP-SR extension

Portfolio of validated incumbents + a single disruption-centred restricted CP-SAT stage + hinted global continuation, one deadline. This is the `\base`/`SR` baseline throughout this study. Reused unchanged; independently re-verified this phase as part of the broader confirmatory re-reconciliation (`01_baseline_verification.md`).

## 3. COBAR findings

A sound, calendar-aware lower-bound certificate and a minimum-cut release procedure, verified against 5,500 independent oracle cases with zero violations, but decisive for only 13/200 restricted neighbourhoods and producing no measurable change in primal integral when used for skipping, releasing, or budget allocation. **Completed negative result, not revisited this phase** beyond citing it and re-confirming (via the independent reconciliation in Phase 1) that its reported numbers still stand unchanged.

## 4. Unified evaluation

The prior stage (`research/icaps-unified-critical-rounds`) built the critical-region-rounds pipeline, its matched external LNS controls (random, time-window, random-precedence), and ran a frozen confirmatory campaign (9 settings, originally reported as 46,720 records). **This phase's Phase 1 found and corrected a genuine arithmetic error**: the true total is **60,720** records, independently re-verified from raw files (`01_baseline_verification.md`). Every individual comparison was already correct; only the grand-total sentence in two documents was wrong.

## 5. Corrected native-solver terminology

Phase 2 found that the prior stage's "native LNS" labels were *correct* but under-evidenced (based on an unsaved, interactive log observation) and that one adjacent claim ("per-generator selection is internal, not exposed to callers") was **wrong**. Both are now backed by saved solver-log transcripts (`results/final_icaps/solver_logs/`) generated from the exact production configuration on an actual confirmatory instance, and the overclaim about subsolver-filtering inaccessibility is corrected in both `docs/unified_icaps/02_prior_work_and_novelty.md` and the manuscript text (`docs/final_icaps/02_native_solver_verification.md`).

## 6. Critical vs. time-window results

No new experiments. Reanalysis of already-archived U1 (end-to-end) and U2 (fixed-round) raw trajectories (`docs/final_icaps/03_critical_vs_timewindow.md`) found that the prior stage's reported "critical beats time-window specifically after arrivals" finding **does not survive matched-round accounting**: under the fixed-round protocol, time-window beats critical in every disruption type including arrivals. The mechanism is a round-count confound (critical-region rounds complete more rounds per instance under the end-to-end protocol in every disruption type, because they succeed more often per attempt, not because their content is better). This **supersedes** the prior stage's "confined to arrivals" framing with a cleaner, stronger, and more defensible finding (time-window is at least as good everywhere once effort is held equal), which the final manuscript now states instead.

## 7. Matched-round analysis

Protocol M2 (U2, 6 fixed rounds $\times$ 0.4s) isolates targeting content from round count. Neighbourhood size is matched almost exactly between critical/time-window/random (82.3-82.4 operations), but per-round solver difficulty is not: time-window rounds take 43% longer to resolve than critical-region rounds despite equal size, and more often exhaust the per-round time cap without a definitive status (901 vs. 376 "FEASIBLE/timeout" outcomes). Critical-region neighbourhoods contain far more genuinely-critical operations by construction (39.8 vs. 9.9 for time-window), yet this does not translate into better final quality. This is new evidence (from reanalysis, not new runs) for why: the harder, slower-to-resolve time-window subproblems apparently make comparably good or better use of their round budget despite containing fewer operations that are actually on a critical chain.

## 8. Worker-count analysis

C6 (U3, 4 workers): critical-region rounds vs. CP-SAT's native 4-worker portfolio is -9.1%, not significant (15/5, Holm $p=0.12$); vs. the one-round pipeline, 0.0%, also not significant. **C6 fails**, confirmed both in the prior stage's analysis and independently re-verified this phase (Phase 1, bit-for-bit). Phase 2 found the mechanistic reason is plausible, not merely asserted: the 4-worker configuration runs 13 interleaved subsolvers (including all four scheduling LNS generators) vs. 10 at 1-worker-interleaved, confirmed from saved logs, making it a strictly richer native search portfolio.

## 9. Main anytime-performance evidence

C1/C2/C4/C5 all hold reproducibly (independently re-verified, Phase 1): critical-region rounds beat the one-round pipeline (-22.4%), size-matched random rounds (-20.4%), random-precedence rounds (-24.5%), and native single-thread search (-43.8%), every comparison significant at Holm $p<10^{-4}$ or better. A real archived-trajectory figure (Figure 2 of the final manuscript, built from actual U1 confirmatory runs, not illustrative) visualizes this.

## 10. Statistical independence

Explicitly re-verified this phase (`01_baseline_verification.md`): 40 streams = 2 sizes $\times$ 20 distinct seed values, not 40 independent seed values; seed sharing across sizes does not create non-independence because every analysis groups by the full size-and-seed stream identifier and the two sizes diverge from the very first size-dependent random draw. No analysis anywhere treats the bare seed number or a solver seed as an independent unit. Published-benchmark streams (U9) are correctly clustered by base instance.

## 11. Novelty relative to prior work

No individual component (incumbent portfolios, selective repair, critical-path neighbourhoods, repeated LNS) is claimed as new anywhere in the final manuscript or this documentation (`04_scientific_positioning.md`, `05_related_work.md`). The contribution is the controlled comparison and its two correctivereanalyses (§6, §8 above). Full texts of Sun et al. (2026) and Lin & Yang (2026) were re-attempted via legitimate routes this phase and remain genuinely inaccessible; this is disclosed, not concealed.

## 12. Correctness verification

269/269 fast and 25/25 slow tests pass on a clean run this phase (`results/final_icaps/final_fast.xml`, `final_slow.xml`); one pre-existing, unrelated, timing-sensitive integration test (`test_checkpoint_partial_progress_then_resume_completes`, tests the archived `phase0.run_icaps_jssp_suite` crash/resume mechanism, untouched by any study in this project) flaked once under load across three runs and is documented, not hidden (`01_baseline_verification.md`). The independently-verified checkpoint/resume test relevant to *this* study's own campaign runner (`test_campaign_resume_skips_finished_tasks_and_keeps_files`) passed deterministically in every run.

## 13. Code-to-manuscript consistency

Reviewed explicitly in Phase 10 (`08_manuscript_review.md`): every method description in the manuscript matches its implementation (`phase0/critical_region_anytime.py`, `phase0/cobar.py`), cross-checked by existing unit tests (`test_crit_expand_equals_cobar_critical_expand`) and, where new claims were made this phase (the native-LNS paragraph), by newly-saved solver logs.

## 14. Unresolved limitations

1. Full texts of the two closest related papers remain inaccessible (not a correctness issue; a human author with institutional access should resolve before actual submission).
2. A resource-normalized (equal-core-second) variant of the 4-worker comparison was not run; U3 holds wall-clock, not CPU-seconds, equal by design, and this is now stated explicitly in the manuscript rather than left implicit.
3. A scheduling-LNS-only native baseline (isolating just the four scheduling generators via `extra_subsolvers` combined with a retained core-search subsolver) is feasible, per Phase 2's finding that subsolver filtering is exposed, but was not run; it would answer a narrower question than any claim this manuscript makes.
4. The by-disruption-type Phase 3 reanalysis is exploratory (no multiplicity correction; not in the pre-registered family), clearly labeled as such everywhere it appears.
5. Raw per-run trajectory files are not in the capped (100MB) anonymous supplement; their checksums are, and a stable anonymous deposit for the camera-ready version is planned but not executed (requires the user's own external account/action).

## 15. Manuscript audit

11/12 original checks pass outright (`docs/unified_icaps/07_manuscript_audit.md`); the 12th (bibliographic completeness) remains correctly flagged as a disclosed, unresolved limitation rather than silently converted to a pass (§14.1 above). This phase's independent reviewer-style pass (`08_manuscript_review.md`) found no unsupported claim requiring correction in the new manuscript; the one defect found and fixed during preparation was a **formatting** bug (`\S\ref{sec:...}` resolving to an empty string throughout, because `secnumdepth=0` suppresses section numbers per the AAAI kit's house style), not a content defect.

## 16. Supplement audit

Updated this phase (`scripts/unified/build_supplement.sh`) to include the new manuscript (`paper/icaps27_unified_final/`), the final-phase documentation and analysis outputs, and the saved solver logs. Re-verified against the live ICAPS-27 CFP (confirmed again on 2026-11-23: 100MB cap, anonymization required, reviewers not obliged to read it). Result: **90MB uncompressed, 5.7MB zipped** (`results/unified_icaps/supplement/anonymous_supplement.zip`, SHA-256 `48a506b72e9a06489756466f583b67b73ad47447f1d7f955dc073fdcf632a28f`), well under the cap. Anonymity re-scrubbed; one residual match is the scrub script's own search-pattern string literal (not leaked author data). Raw trajectory-file omission is disclosed inside the package's own `README_SUPPLEMENT.md`, not silently made.

## 17. Final GO / CONDITIONAL GO / NO-GO verdict

**CONDITIONAL GO**, per the pre-registered classification, reaffirmed and in two respects **strengthened by this phase's corrections**, not weakened:

- Performance criteria C1, C2, C4, C5 hold, independently re-verified bit-for-bit.
- C3 (critical vs. time-window) was previously reported as "inconclusive, with one disruption-specific exception"; this phase's reanalysis shows the exception does not survive proper accounting, yielding a *cleaner* negative finding (no exception anywhere) rather than a muddled partial one. This is a narrowing of the claim, achieved by additional scrutiny, exactly the direction scientific honesty should move in.
- C6 (vs. native 4-worker search) fails, now with saved-log evidence for a plausible mechanism (a richer native subsolver portfolio at 4 workers), rather than an unexplained null result.
- Per the explicit instruction not to change the classification to satisfy an acceptance-probability target: **the classification is unchanged from the prior stage's own determination.** What changed is the precision and evidentiary strength behind two of its six component criteria, and the correction of one genuine arithmetic error and one genuine overclaim, both found by this phase's independent re-verification work and both fixed rather than left standing.

**The manuscript does not claim a new search algorithm.** It reports: incumbent reuse and a single selective stage help; repeating that stage with a *structured* (not random) neighbourhood helps further; which structured neighbourhood is used barely matters, and a simple time-window heuristic is, if anything, slightly better once computational effort is held equal; and the entire advantage over the installed solver's own search is specific to a single worker. This is the empirical, bounded contribution the task's own fallback criteria anticipated for this evidentiary outcome.

## Final source status (Part D)

- **Branch:** `research/icaps2027-final-empirical`.
- **Latest commit at time of writing:** `af7dead` (supplement update); this report and the remaining Phase 12-13 artifacts are committed immediately after.
- **New files this phase:** `docs/final_icaps/01`-`08`.md, `docs/final_icaps/FINAL_RESEARCH_AND_SUBMISSION_REPORT.md` (this file), `scripts/final/verify_unified_confirmatory.py`, `scripts/final/build_verified_metrics.py`, `results/final_icaps/*` (verification JSON, solver logs, test JUnit XML, verified_metrics.json), `paper/icaps27_unified_final/*` (new manuscript, figures, registry).
- **Modified files this phase:** `docs/unified_icaps/02_prior_work_and_novelty.md` (native-LNS correction), `docs/unified_icaps/04_mechanism_analysis.md` (supersession notice added, original text preserved), `docs/unified_icaps/06_statistical_results.md` / `FINAL_SUBMISSION_RESEARCH_REPORT.md` (record-count correction), `scripts/unified/build_supplement.sh` (extended), `results/unified_icaps/supplement/*` (regenerated), the project memory file (record-count correction).
- **Exact reproduction commands:**
  - Independent reconciliation: `.venv/bin/python scripts/final/verify_unified_confirmatory.py`
  - Solver-log capture: inline snippets in `docs/final_icaps/02_native_solver_verification.md`
  - Verified-metrics build: `.venv/bin/python scripts/final/build_verified_metrics.py`
  - Manuscript build: `cd paper/icaps27_unified_final && ../../.venv/bin/python make_numbers.py && pdflatex manuscript.tex && bibtex manuscript && pdflatex manuscript.tex && pdflatex manuscript.tex`
  - Claim check: `cd paper/icaps27_unified_final && ../../.venv/bin/python check_claims.py`
  - Supplement rebuild: `scripts/unified/build_supplement.sh <output-dir>`
- **Test results:** 269/269 fast, 25/25 slow (one flaky pre-existing unrelated test documented, not blocking).
- **Remaining author actions** (cannot be completed from this environment):
  1. Obtain and read the full texts of Sun et al. (2026) and Lin & Yang (2026); revise Related Work if warranted.
  2. Review and approve the title and the Discussion section's framing (marked inline in `manuscript.tex` with an author-review comment block); remove the marker once approved.
  3. Decide, in the author's real submission system, how `paper/icaps27_iaip/` and `paper/icaps27_cobar/` are formally superseded or withdrawn (this environment has no such system).
  4. Rename `manuscript_candidate.pdf` to `manuscript_submission.pdf` only after (1)-(3) are complete, per the task's own naming policy.
  5. Deposit raw trajectory files at a stable anonymous host for the camera-ready version (requires the user's own external account).
  6. Push the branch, or merge it, only with explicit authorization -- **not done**, and not attempted, in this phase.

**Not pushed. Not submitted. Nothing in this repository was altered without a corresponding commit documenting why.**
