# Visual Manuscript Comparison (Phase 10C)

Before: `paper/icaps27_unified_final/manuscript_candidate.pdf` (preserved unchanged). After: `paper/icaps27_unified_visual/manuscript.pdf` (pending rename to `manuscript_visual_candidate.pdf` after author review per Part D below).

## Quantitative comparison

| Metric | Before | After |
|---|---|---|
| Pages | 6 body + references (6 total incl. refs on last body page) | 6 body + 1 references page = 7 total |
| Figures | 2 (architecture diagram, real trajectories) | 5 (architecture diagram, trajectories, forest plot, 3-panel mechanism figure, robustness heatmap) |
| Tables | 1 (monolithic 9-row x 8-col cross-setting table) | 4 (notation; method configuration; experimental configuration; compact main-results) |
| Algorithm/pseudocode boxes | 0 (4-step method described as a prose paragraph) | 1 |
| Equation blocks | 0 (gap/PI defined inline in prose) | 2 (gap, primal integral) |
| Body prose word count (excl. figure/table/algorithm contents) | ~3{,}820 | ~3{,}030 (-21%) |
| Claim macros (numbers.tex) | 284 | 362 (extended with per-method gap/first-incumbent-time macros for the new main-results table) |

Word-count reduction is reported for completeness only, not as the quality measure for this restructuring: the real target was information density per page (more figures/tables conveying the same or more evidence in less running prose), not a smaller word count for its own sake. Page count grew by one page (6->7) because 5 new/retained figures and 4 tables need room; this is within the explicit ~7.5-8 page target and the 8-page limit.

## New visual information (not merely reformatted)

- **Forest plot (new Figure 2):** makes the 6 pairwise U1 comparisons' point estimates, 95% CIs and significance simultaneously visible; the prior version required reading 3 inline numbers per comparison scattered across 2 paragraphs plus Table 1 columns.
- **3-panel mechanism figure (new Figure 4):** the single most information-dense new artifact. Panel A (end-to-end, confirmatory) vs. Panel B (matched-round, confirmatory + exploratory) side by side makes the sign reversal plainly visible in a way the prior all-prose section 6 could only state in words; Panel C's round-count bar chart supplies the causal mechanism in the same figure rather than three sentences later.
- **Robustness heatmap (new Figure 5):** consolidates U1 and U3-U9 (eight settings x two comparators = 16 numbers) into one glance, including the "4 workers" column that visually demonstrates finding 5 (the advantage narrows) without needing the reader to compare two separately-stated percentages from different paragraphs.

## Content moved to supplement (not main text)

- The Gantt-style worked example (illustrative only, no experimental content) was never built into the main text; per the restructuring plan (`VISUAL_RESTRUCTURING_PLAN.md` item 9) it remains deferred to the supplement, consistent with the explicit fallback instruction to prioritize space for data-backed figures.
- The development-phase exploratory ablation tables (A5/A7/A9) remain pointer-only (one sentence + supplement reference), not given main-text table space, to avoid presenting exploratory and confirmatory evidence with equal visual weight.

## Content removed as redundant (not moved, not lost)

- The prior monolithic Table 1's per-setting "vs. Base" and "vs. TimeWin" columns for U3-U9 are now carried by the robustness heatmap (Figure 5) instead of a table column, since the heatmap conveys the same comparisons with the added information of significance (dashed outline) in less space.
- Restating every reported percentage in both prose and a table (a pattern flagged in the task's own anti-pattern list) was removed throughout: Results subsections A-D now reference figures/tables for the number and state only the interpretation in prose, rather than repeating, e.g., "22.4%" in both the paragraph and Table 4's caption.

## What did not change

- All scientific claims, the CONDITIONAL GO classification, the six enumerated findings, the certificate negative result, the native-LNS log-verification language, and every numeric claim trace to the same `results/unified_icaps/confirmatory/confirmatory_analysis.json` and `docs/final_icaps/03_critical_vs_timewindow.md` sources as the prior manuscript. No new experiments were run; no existing finding was strengthened or softened to make a figure look better (see `FINAL_VISUAL_MANUSCRIPT_AUDIT.md` item 1).

## Remaining limitations of this restructuring

- The exploratory by-disruption-type points in Figure 4 Panel B are transcribed from an already-published markdown table (no separately-computed CI exists for them); the figure marks this visually (hollow markers, no whisker, asterisk) but a careless reader could still conflate them with the confirmatory overall point unless they read the caption.
- The heatmap's color scale is shared across both rows (vs. SR and vs. Port+Hint), which have different typical magnitudes; a reader comparing absolute color intensity across rows rather than reading the printed numbers could slightly misjudge relative scale. The printed numeric value in every cell is the authoritative reading.
- A richer visual presentation does not, by itself, address the novelty concern raised about this paper's contribution; the plots make the existing evidence easier to evaluate, not stronger than it was ([[icaps-full-paper-plan]] / [[feedback_icaps_venue_only]] context).
