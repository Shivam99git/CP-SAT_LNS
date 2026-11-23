# Unified ICAPS-27 manuscript candidate: "When Does Repeated Restricted Reoptimization Help? An Empirical Study of Anytime Dynamic Job-Shop Rescheduling"

This is the single, consolidated manuscript candidate superseding `paper/icaps27_iaip/` and `paper/icaps27_cobar/` as competing submissions (per explicit instruction: do not submit overlapping papers). Both earlier directories are preserved, untouched, as prior-stage artifacts.

## Files

| File | Role |
|---|---|
| `manuscript_submission.pdf` | upload file (metadata stripped, no annotations) |
| `manuscript.tex`, `references.bib`, `numbers.tex` | sources |
| `aaai2027.sty`, `aaai2027.bst` | AAAI-27 kit (identical to the kit used in the two prior candidates) |
| `make_numbers.py` | builds `numbers.tex` / `claims.json` from `results/unified_icaps/confirmatory/confirmatory_analysis.json` and development pilot files |
| `check_claims.py` | verifies every result macro is defined and no hand-typed result literal appears |
| `allowed_literals.json` | design/methodology constants permitted as literals (budget fractions, generator weights, the pre-specified equivalence margin) |

## Format

- 5 pages including references (within the 8-page long-paper limit).
- AAAI-27 kit unchanged; anonymous; no forbidden packages/commands (grep-checked).
- All fonts Type 1; submission PDF has no Info dictionary and no annotations.
- pdfLaTeX: 0 errors, 0 overfull boxes.

## Verdict

**CONDITIONAL GO**, per the protocol frozen in `docs/unified_icaps/06_statistical_results.md` before any held-out run (`results/unified_icaps/confirmatory/FROZEN_CONFIG.json`, SHA-256 `a594a25f...`). Repeated, recomputed, critical-region-targeted restricted reoptimization reproducibly beats the one-round incumbent-aware pipeline, random-neighbourhood rounds, random-precedence rounds, and CP-SAT's single-thread interleaved search (criteria C1, C2, C4, C5 all hold). It does **not** establish an advantage over a size-matched time-window neighbourhood (C3: inconclusive, confined to arrival disruptions, reversed under the fixed-round protocol) and does **not** survive CP-SAT's native four-worker scheduling LNS (C6 fails). No claim of superior critical-region search is made; the manuscript is framed as an empirical study, per the brief's own fallback instruction for this outcome.

## Claim verification

`check_claims.py`: 108 claim macros used, 0 undefined, 0 hand-typed result literals, after one iteration to allowlist genuine methodology constants (generator delta weights, protocol fractions) that a naive regex flagged as result-like.

## Open before an actual submission

1. Full texts of Sun et al. (2026) and Lin & Yang (2026) were not accessible (ScienceDirect 403; Elsevier TDM API requires a key). Read in full and revise the related-work comparison if warranted.
2. The archived `paper/icaps27_iaip/` and `paper/icaps27_cobar/` candidates are now superseded by this one for submission purposes; they remain as historical artifacts of the research trajectory and are referenced, not duplicated, in the final report.
3. Regenerate (`make_numbers.py`, then `check_claims.py`) and recompile after any further edit.
