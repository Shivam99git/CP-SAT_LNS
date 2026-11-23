# Final-phase 08 — Independent manuscript review (Phase 10)

Reviewer-style pass over `paper/icaps27_unified_final/manuscript_candidate.pdf` (6 pages). For each section: technical accuracy, scientific necessity, contribution to the central argument, consistency with implementation, experimental support, relation to prior work, potential reviewer objections.

## Abstract

Accurate (every number traced in Phase 1); necessary; states both the positive (C1/C2/C4/C5) and negative (C3/C6) findings in the same paragraph rather than burying the negative ones later. **Potential objection:** a reviewer could ask why the abstract leads with a positive framing at all if the central finding is "we could not establish X." **Response already in the text:** the abstract's final two sentences explicitly state the C3/C6 negatives before the paper's closing sentence, and the title itself avoids claiming the positive framing as the paper's thesis.

## Introduction

RQs are necessary and each is answered later; no RQ is introduced and then dropped. **Objection:** RQ5 (mechanism decomposition) is answered only partially (Phase 3 isolates the round-count confound for one specific question, not a full variance decomposition). **Response:** the Introduction does not promise a full decomposition, only that the paper "asks" the question; §6 answers the part it actually resolves and the Limitations section does not claim more.

## Related Work

Technically accurate per Phase 5's re-verification; the two inaccessible citations are flagged in-line, not silently treated as fully read. **Objection:** a reviewer with institutional access might ask why the authors didn't request the papers through other means (e.g. emailing the authors). **Response:** legitimate, should be attempted by a human author before submission; recorded as an explicit open item (`FINAL_RESEARCH_AND_SUBMISSION_REPORT.md` Part D).

## Problem Setting / Method / Neighbourhood-Targeting sections

Consistent with `phase0/critical_region_anytime.py` and `phase0/cobar.py` line-for-line (cross-checked in Phase 1/2 of the unified study, not re-verified again here since no code changed this phase). The acceptance-rule / incumbent-retention claim is correctly hedged as "elementary," not a theorem. The native-LNS paragraph is now backed by saved logs (Phase 2), not source-inspection inference alone — this was the one correction this phase made to an existing claim, and it is now accurate.

## Experimental Methodology

The stream/seed relationship (40 = 2 sizes $\times$ 20 seeds) is now stated explicitly in-text, not left for a reader to infer or discover as this phase did. The equivalence-margin and power-estimate caveats are present and are not silently dropped when the overall conclusion is stated.

## Results and §6 (reanalysis)

The strongest section of the manuscript. **Objection a reviewer would likely raise:** is the by-disruption-type reanalysis (exploratory, no multiplicity correction) strong enough evidence to overturn the manuscript's own earlier (U6, confirmatory) finding? **Response, already partly in the text:** the manuscript does not claim the reanalysis is confirmatory-grade evidence of "critical is worse" — it claims only that the *specific prior claim* (critical beats time-window after arrivals) does not survive a controlled reanalysis, which is a narrower and better-supported claim (absence of established superiority, not established inferiority). This distinction is maintained correctly in the text ("we therefore do not claim critical targeting is better suited to any disruption type," not "we have shown critical targeting is worse").

## Discussion and Limitations

Candid about the $4\times$ core-second asymmetry at U3, about the unattempted scheduling-LNS-only native baseline, and about solver-version-specificity. No claim exceeds what Table 1 and the cited analysis files support.

## Overall assessment

No section was found to contain an unsupported claim requiring correction during this review pass (the one real defect found during manuscript preparation this phase — the `\S\ref{sec:...}` rendering bug producing empty section numbers in running text and a figure caption — was a **formatting** defect, not a content defect, and was fixed before this review; see commit history). No results were rewritten to appear more significant; where a finding changed (Phase 3), the change narrowed the claim rather than strengthening it.
