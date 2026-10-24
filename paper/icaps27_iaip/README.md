# Revised ICAPS-27 manuscript candidate: "Reuse, Then Focus: Incumbent Portfolios and Impact-Selective CP-SAT for Anytime Rescheduling"

This is a **candidate** revision written on the research branch `research/iaip-sr`. The archived submission in `paper/icaps27/` is unchanged.

## Files

| File | Role |
|---|---|
| `manuscript_submission.pdf` | the file to upload (PDF Info dictionary removed) |
| `manuscript.tex`, `references.bib` | sources |
| `figures/anytime.pdf` | the figure |
| `aaai2027.sty`, `aaai2027.bst` | AAAI kit files |

## Format

- **Format rules:** the same as for `paper/icaps27/` (see that README). ICAPS-27 requires AAAI format; the AAAI-27 Author Kit (TemplateVersion 2027.1) was used.
- **Kit files:** byte-identical copies (SHA-256):
  - `aaai2027.sty` 391bce82…
  - `aaai2027.bst` 5db7765b…
- **Length:** 6 pages including references. The long-paper limit is 8 pages plus references.
- **Build:** pdfLaTeX with 0 errors and 0 overfull/underfull boxes; US Letter; all fonts Type 1, including the figure, whose text is typeset with LaTeX.
- **Kit rules:** no forbidden packages or commands; anonymous author line.

## How the content was kept factual

**Numbers.** `verify_numbers.py` recomputes 149 stated values from the saved analysis outputs and checks that each formatted value occurs in `manuscript.tex`. Its current result is 149/149. The check is a substring match: it confirms that each value occurs in the text, not that it sits next to the right label. The sources are:

| File | Produced by |
|---|---|
| `results/research_extension/gate1_historical_reuse/analysis.json` | `phase0.analyze_gate1` |
| `results/research_extension/confirmatory/confirmatory_analysis.json` | `phase0.analyze_confirmatory` (checks the frozen-config SHA-256) |
| `results/research_extension/confirmatory/supplementary_analysis.json` | post-hoc comparisons and stability; not predeclared |
| `results/research_extension/e6_analysis.json`, `e6e_lns/analysis.json` | `phase0.analyze_e6` |
| `figure_numbers.json` | `make_figure.py` |

**Error found by the verification script:** one rounding error (high-severity vs Fresh+Cold, −58.46% had been written as −59%). It has been fixed.

**References.**
- Every entry inherited from `paper/icaps27/references.bib` was verified there.
- The eleven added entries were checked on 2026-10-24:
  - eight journal articles against their Crossref DOI records (authors, title, venue, volume, issue, pages);
  - three proceedings papers without DOIs (Godard et al. 2005, Pacino & Van Hentenryck 2011, Verfaillie & Schiex 1994) against OpenAlex for authors, title and year; their pages come from the proceedings listings recorded in `docs/research_extension/06_related_work_novelty.md`.
- **Sun et al. (2026) has not been read in full.** It is cited only for what its abstract states. It must be read before submission.

**What the text claims, and how strongly.**
- **Confirmatory claims:** the predeclared family only.
- **Not predeclared, and labelled so in the text:** Port+Hint vs Port+Cold; Fresh+Hint vs Fresh+Cold; stability; the by-delta breakdowns; all robustness and neighbourhood-baseline results.

## Open before submission

1. Read Sun et al. (2026) in full and contrast it precisely.
2. Search specifically for CP-SAT / CP Optimizer reactive-scheduling work with warm starts.
3. Decide whether to keep the archived paper's cross-solver (Gurobi/CPLEX) and PSPLIB Floor results. They concern Floor, not IAIP-SR, and are omitted here.
4. Re-run `verify_numbers.py` and the format checks after any edit.
