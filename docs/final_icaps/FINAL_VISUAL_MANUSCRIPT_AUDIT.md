# Final Visual Manuscript Audit (Phase 9/10D)

Audit of `paper/icaps27_unified_visual/manuscript.tex` (compiled `manuscript.pdf`, 7 pages: 6 body + 1 references). Companion to `docs/final_icaps/08_manuscript_review.md` (the prior-phase prose review, whose conclusions this inherits for any text carried over unchanged) and `VISUAL_MANUSCRIPT_COMPARISON.md`.

## 1. Scientific consistency with the prior verified manuscript

No scientific claim was added, strengthened, or softened relative to `paper/icaps27_unified_final/manuscript_candidate.pdf`. Checked explicitly against the task's six prohibited overclaims:
- Does **not** claim critical-region universally beats time-window (Discussion finding 3, §B: "does NOT consistently beat ... once rounds are matched"; "we therefore do not claim critical targeting is better suited to any disruption type").
- Native-LNS activity claims are stated as "confirmed active from solver logs" throughout, never from source-inspection alone.
- C6's failure is stated as "none ... is distinguishable from the others" (non-significance), never as "parallel CP-SAT performs worse."
- The certificate result is stated as "a completed negative result" with "no measurable change in primal integral," never as an improvement.
- No claim that a more complex neighbourhood automatically helps more: finding 2 is scoped to "some random alternatives," and finding 3 explicitly withholds a complexity-based claim for critical vs. time-window.
- U3's four-worker setting is explicitly flagged in both the Neighbourhood-Targeting section and Discussion as using 4x the CPU-seconds of one-worker settings ("matched wall-clock, not matched core-seconds"), never presented as an equal-resource comparison.
The central CONDITIONAL GO conclusion, and all six enumerated Discussion findings, match the matched-round/resource-aware analyses, not the uncontrolled end-to-end readings they supersede.

## 2. Figure correctness

All 5 figures traced to their generating scripts under `paper/icaps27_unified_visual/figures/`. Two real bugs were found and fixed during construction, before being included in any compiled PDF (not found by a separate reviewer after the fact): a CI/mean unit mismatch in the forest plot (Figure 2; CI bounds were in raw PI units while the point estimate was a relative percentage) and a float-placement defect in the mechanism figure (Figure 4; originally 3 stacked panels caused LaTeX to defer it to an isolated, mostly-blank page — redesigned as a 1x3 horizontal layout). `verify_visuals.py` additionally checks CI-bracket correctness for every comparison in the shared JSON, not just the ones currently plotted, guarding against the same bug class recurring if the plotted set changes.

## 3. Table correctness

All 4 new tables (notation, method configuration, experimental configuration, main results) were checked by hand against their sources: the method-configuration table (stage presence, worker counts) against `phase0/critical_region_anytime.py`/`cobar.py` method definitions (reused unchanged from the prior manuscript's own verified description); the experimental-configuration table against `FROZEN_CONFIG.json`-derived values already stated in the prior manuscript's Methodology paragraph; the main-results table's PI/gap values are claim-macro-driven (`\UOneMeanB*`, `\UOneGapBB*`), not hand-typed.

## 4. Statistical verification

No new statistics were computed; all CIs, Holm-adjusted p-values, and significance classifications are read directly from `results/unified_icaps/confirmatory/confirmatory_analysis.json`, the same file independently re-verified in the prior phase (`results/final_icaps/verified_metrics.json`, 33/33 comparisons). The four exploratory by-disruption-type points in Figure 4 Panel B are visually distinguished (hollow markers, no CI whisker, asterisk) from the confirmatory points, matching their true evidentiary status (no pre-registered multiplicity correction, no separately-computed CI, as stated in the original `docs/final_icaps/03_critical_vs_timewindow.md`).

## 5. Macro/claim-registry checks

`check_claims.py` (extended, reused unchanged in logic from `icaps27_unified_final`): 51 claim-like macros used in the new manuscript, 0 undefined, 0 hand-typed result literals (2 design-constant literals — worker-count "1/4", budget "2/30" — added to `allowed_literals.json`, consistent with the existing allow-list's purpose), `numbers.tex` not stale, 0 sample-size mismatches against the archived analysis file.

## 6. Source-to-figure traceability

Every figure script states its data source in its own module docstring and reads only from `results/unified_icaps/confirmatory/confirmatory_analysis.json` (Figures 2, 4 panels A/B-overall, 5) or from the already-published, previously-verified `docs/final_icaps/03_critical_vs_timewindow.md` reanalysis table (Figure 4 panels B-exploratory and C, transcribed verbatim with the source cited in-script, since that document itself states the underlying per-delta values were never separately archived at full precision). `verify_visuals.py` checks 1-8 (figure/script/source existence, method-label and metric validity, CI-bracket correctness, independent recomputation of every heatmap cell against the script's own printed output, staleness) automate this traceability check going forward rather than relying on a one-time manual trace.

## 7. Layout verification

All 7 pages rendered to PNG and visually inspected. Defects found and fixed during this process: two overfull hboxes from un-hyphenated long `\texttt{}` identifiers (fixed with manual discretionary hyphens, matching the pattern already used elsewhere in the prior manuscript), one table too wide for a single column (method-configuration table: reduced to `\footnotesize` and shortened cell text), and the float-placement/clipping issues in item 2. No remaining overfull/underfull warnings from the final `pdflatex` run; no tiny fonts (smallest is `\footnotesize`, used only in the method-configuration table, consistent with Table 2 of the prior manuscript's own precedent); no misplaced floats on the final render.

## 8. Page-limit compliance

7 pages total (6 body + 1 references page), within the ICAPS-27 8-page long-paper limit (references customarily excluded from the page count; even counting them, 7 <= 8). This is below the ~7.5-8 page target suggested by the task, leaving headroom rather than requiring further cuts.

## 9. Citation completeness

References unchanged from the prior, already-verified manuscript (`paper/icaps27_unified_final/references.bib`, reused via `references.bib` copied into this directory). The two citations whose full text remains inaccessible (Sun et al. 2026, Lin & Yang 2026) are flagged identically in Related Work and Discussion, as in the prior manuscript; this remains an open author action (Part D below), not resolved by this restructuring.

## 10. Double-blind anonymity

Author field remains "Anonymous Submission," no affiliations, no acknowledgments section, no author-identifying file paths or emails in the compiled PDF text (checked by rendering and reading all 7 pages). The AI-assistance authorship-policy marker comment at the top of `manuscript.tex` (non-printing LaTeX comment) was updated to reference this restructuring explicitly rather than silently inheriting the prior phase's marker text unchanged.

## 11. Reproducibility package status

Not yet updated for this restructuring: `scripts/unified/build_supplement.sh` still stages `paper/icaps27_unified` and `paper/icaps27_unified_final` only. Recommended action (not performed automatically, since it changes what ships in the anonymous bundle): add `paper/icaps27_unified_visual` to that script once a human author has reviewed and approved this manuscript, so the submitted manuscript's own sources are the ones in the supplement rather than its immediate predecessor.

## 12. Remaining author-approval requirements

Carried over from the prior manuscript (`docs/final_icaps/FINAL_RESEARCH_AND_SUBMISSION_REPORT.md` Part D) and unchanged by this restructuring: (a) title and framing review; (b) a renewed attempt to obtain the two inaccessible citations through non-automated means (e.g. emailing the authors) before submission; (c) review of the Discussion section's framing choices. New to this phase: (d) review of the 6 enumerated Discussion findings' wording (verbatim-required list, each now paired with a "Consequence" sentence that is new editorial framing, not a new claim, and should be read by a human author for tone); (e) approval to rename `manuscript.pdf` to `manuscript_visual_candidate.pdf` (not yet performed, pending this audit's acceptance) and, after that, to `manuscript_submission.pdf` only once a human author has completed (a)-(d).
