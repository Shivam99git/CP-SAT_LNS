# ICAPS-27 Submission: "Floor, Not Hint: Robust Solution Reuse for Anytime Rescheduling"

`manuscript_submission.pdf` is the file to upload (metadata cleared). `manuscript.tex` + `references.bib` + `figures/anytime.pdf` + `aaai2027.sty` + `aaai2027.bst` are its complete sources.

## Format requirements followed, and where they come from

**ICAPS-27 call for papers** (https://icaps27.icaps-conference.org/calls/cfp, fetched 2026-10-06), quoted:

- "All papers submitted to ICAPS-27 must be in AAAI Format."
- Long papers: "8 pages plus additional page(s) for references". "An over-length paper is one in which content other than references and the optional ethical impact statement appears on page 9 (long papers)." **This manuscript's main text ends on page 5; references occupy pages 5–6.**
- "Submissions must be double-blind. Authors should omit their names and affiliations and refer to their own prior work in the third person."
- Dates: abstract **December 7, 2026**, paper **December 14, 2026**, notification February 26, 2027.

The CFP gives no link to a specific author kit, so the current **AAAI-27 Author Kit** was used: https://aaai.org/authorkit27/ (redirects to `AuthorKit27.zip`, TemplateVersion 2027.1). `aaai2027.sty` and `aaai2027.bst` here are byte-identical to the kit's:

```
391bce82815bf698b8e382dd3ae7e30c75d7ab46df140cb295b1266016bc8623  aaai2027.sty
5db7765ba99de5c1e4686f9b3940a0add9c5e702f2164514462bec130ccb6e3c  aaai2027.bst
```

Checked against the kit's rules (`AnonymousSubmission2027.tex`):

| Rule | Status |
|---|---|
| `\documentclass[letterpaper]{article}`, `\usepackage[submission]{aaai2027}`, kit preamble lines unchanged | yes, copied verbatim |
| No forbidden packages (hyperref, geometry, float, times, titlesec, ...) or commands (`\clearpage`, `\vspace{-`, `\resizebox`, ...) | none present (grep check) |
| US Letter, two columns | 612 × 792 pt |
| No Type 3 fonts; no CID/Identity-H fonts, including inside figures | all fonts Type 1 (figure text typeset with LaTeX in Helvetica) |
| No embedded links or bookmarks | 0 annotations, no outline |
| Title in Title Case; anonymous author line; no copyright notice | yes (style's submission mode) |
| Table and figure captions below the float | yes |
| Single `.tex` source, bibliography with `aaai2027.bst` | yes |
| PDF metadata cleared before submission | `manuscript_submission.pdf` has no Info dictionary |
| Compiles with pdfLaTeX without errors or overfull boxes | 0 errors, 0 overfull/underfull boxes |

The toolchain was validated first: compiling the kit's own `AnonymousSubmission2027.tex` with this pdfLaTeX (TeX Live 2026 via TinyTeX) gives the same page count as AAAI's shipped PDF.

## How the content was kept factual

**Numbers.** Every number in the paper is recomputed from the raw per-instance CSVs under `results/` by `verify_numbers.py`, using the project's tested statistics functions; output in `verified_numbers.json`. Nothing was copied from earlier write-ups. Floor construction time is not recorded in the CSVs (see below), so it was measured separately by `time_floor.py` (`floor_timing.json`). The figure is produced by `make_figure.py` from `results/icaps/figures/trajectories.pkl`.

**Experimental settings.** Taken from the code and from the commands actually launched, not from presets: e.g. the `workers` campaign actually ran 15×15, seeds 11–12, budgets 2 and 8 s (the preset nominally lists other values), and the synthetic RCPSP campaign used `--num-activities 60 --num-resources 3 --resource-capacity 4 6`.

**References.** Every bibliographic field comes from a registry record: Crossref (DOI resolves to the stated title, authors, venue, volume and pages), OpenAlex for conference papers without DOIs, and the vendors' own citation pages for CP-SAT and Gurobi; software versions and release years come from the installed packages and PyPI. One field on which sources disagreed (page numbers of Yamada & Nakano 1992) was omitted rather than guessed. Descriptions of related work only state what the cited paper's abstract (or, where no abstract was reachable, its title) supports.

## Errors found in earlier drafts and corrected here

The verification pass found statements in the project's earlier write-ups (`BOOT_COLD_PAPER.md`, `paper/boot_cold_icaps.tex`, `PROJECT_DOCUMENTATION.md`) that the raw data do not support. The manuscript uses the corrected versions:

- **"Three solvers agreed on the optimum on all 60 instances."** True for the 30 job-shop instances only. On knapsack, Gurobi and CPLEX stop at their default relative MIP gap of 1e-4, and final values differ by up to 9.4e-5.
- **"boot_warm loses single-threaded (36%, p = 1.9e-8)."** An artifact of pooling only the four earliest campaigns (dominated by the arrivals campaign). In the main campaign boot_warm wins 58.2%; on OR-Library streams 83.9%. The robust finding is that hint-based reuse changes sign across campaigns.
- **"87% win rate at 1 worker, n = 28–424 per level."** The workers campaign has 28 paired instances per worker count; at 1 worker the floor wins 28/28.
- **"~1 ms bootstrap."** Never measured: the `bootstrap_time_ms` column is 0.0 for every boot_cold row because `warm_bootstrap_solve` does not set it. Measured now: median 0.05–0.18 ms, maximum 0.32 ms.
- **"Gap insertion not significant (p = 0.38–0.71)."** Within each configuration, all four insertion rules beat Cold on 84.7–87.5% of instances with mean PI 0.0238–0.0247: no improvement over appending.
- **Holm-corrected p-values in the cross-solver table** were computed with inconsistent families; here the family is all six rows.
- **The `proven_optimal` column for `cpsat_cold`** is always False (`cpsat_default_solve` never sets it), so it is not cited.
- **Figures in `results/`** embed Type 3 fonts and cannot be submitted; `figures/anytime.pdf` is a compliant regeneration.

## Still to do by a human before submission

1. Register the abstract on EasyChair by **December 7, 2026** and select **long paper**; upload by **December 14, 2026**.
2. Confirm on the ICAPS-27 site whether a reproducibility checklist is required (the CFP fetched on 2026-10-06 does not mention one; ICAPS-26 said it was not required).
3. Do not post the paper on arXiv from two weeks before the deadline until notification (CFP policy).
4. Add a code/data link only after acceptance: the project repository would de-anonymize the submission.
5. Read the paper in full. The text was checked against the data, but the scientific framing is the authors' responsibility.

## Rebuild

```bash
export PATH="$HOME/.TinyTeX/bin/x86_64-linux:$PATH"
cd paper/icaps27
../../.venv/bin/python verify_numbers.py      # numbers
../../.venv/bin/python time_floor.py          # floor timing
../../.venv/bin/python make_figure.py         # figure (needs LaTeX)
pdflatex manuscript && bibtex manuscript && pdflatex manuscript && pdflatex manuscript
```
