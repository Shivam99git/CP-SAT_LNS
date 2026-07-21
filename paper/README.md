# ICAPS paper: boot_cold

`boot_cold_icaps.tex` is the ICAPS technical-track draft. It is derived from
the comprehensive source-of-truth writeup in `../BOOT_COLD_PAPER.md`; every
number in it is recomputed from the raw result CSVs, not transcribed.

## Building the PDF

The `.tex` compiles with the standard `article` class and only widely-available
packages (amsmath, amsthm, booktabs, graphicx, hyperref, xcolor), so it builds
as-is on [Overleaf](https://overleaf.com) or any TeX Live install:

```bash
cd paper && pdflatex boot_cold_icaps && pdflatex boot_cold_icaps
```

(No `bibtex` step: the bibliography is a self-contained `thebibliography`.)

### Figures (required before building)

The `\includegraphics` references live in `../results/icaps/figures/`. Generate
them first:

```bash
bash ../scripts/make_paper_figures.sh
```

This (1) captures solver trajectories on a small held-out grid — needed for the
anytime curves, since the result CSVs store only summary statistics, not the
per-moment gap trajectory — and (2) renders every figure. Takes a few minutes.

## Converting to the AAAI/ICAPS submission format

ICAPS uses an AAAI-derived LaTeX class distributed from the submission site.
To switch: replace the lines marked `% AAAI-SWAP` in the preamble with the
official author kit (`\documentclass[letterpaper]{aaai24}` plus `aaai24.sty`,
`aaai24.bst`). The body — sections, the domination theorem, tables, figures,
and bibliography — is written to port with minimal change.

## Status / TODO before submission

- [ ] Full-text (not abstract-only) verification of the MIP Workshop 2023
      Reoptimization Competition citation's exact claims (§Related Work).
- [ ] Swap in the official AAAI/ICAPS class + `.bst`; convert `thebibliography`
      to a `.bib` file.
- [ ] Optionally restore the 30x20 instance size to the main table if a
      reviewer asks or compute allows (see `../docs/icaps_full_paper_plan.md`).
- [ ] Author/affiliation block, acknowledgements, reproducibility checklist.
