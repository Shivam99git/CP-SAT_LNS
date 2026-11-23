# Final-phase 04 — Scientific positioning (Phase 4)

## 4.1-4.2: Empirical framing and research questions

The manuscript (`paper/icaps27_unified_final/manuscript.tex`) is framed entirely around RQ1-RQ6 (stated verbatim in its Introduction), not around a claimed new algorithm. Only RQ5 (is the improvement explained by neighbourhood content, round count, or budget split) is answered only partially: Phase 3's reanalysis (`03_critical_vs_timewindow.md`) isolates round count as the dominant confound behind the one apparent disruption-specific exception, but a full decomposition (e.g. what fraction of the U1 PI gain is attributable to the initial selective stage alone vs. the portfolio vs. the rounds) was already measured in the prior-stage ablations (A5/A7/A9 in `docs/unified_icaps/03_lns_baseline_protocol.md`) and is summarized, not re-derived, here.

## 4.3: Contribution classification

| Element | Classification |
|---|---|
| Incumbent portfolio, selective reoptimization, hinted global continuation | known algorithmic mechanism (reused unchanged from a prior stage) |
| Critical-chain computation (calendar-aware longest-path) | known algorithmic mechanism, reused unchanged |
| Faithful, size-matched external analogues of CP-SAT's own scheduling LNS generators | verified implementation technique (built from solver source, confirmed via saved logs) |
| The M1/M2 dual-protocol comparison design | new experimental comparison (not found in the cited prior work's abstracts) |
| "Repeated rounds alone help little; targeted repetition helps; which structured target is used barely matters; the whole thing loses its edge at 4 workers" | new empirical finding |
| Incumbent retention ($U_{k+1}\le U_k$ by construction) | mathematical correctness property of the acceptance rule, explicitly **not** called a theorem anywhere in the manuscript or this documentation |
| The sound lower-bound certificate and its decisiveness statistics | previously established (classical relaxation-bound reasoning) + a completed negative empirical result about its practical value |
| "Critical-path search is new" / "repeated LNS is new" | **explicitly disclaimed** in the manuscript's Related Work and Introduction |

No contribution in this study is classified as "unsupported hypothesis"; everything reported is either independently verified data (Phase 1) or a documented limitation (Phases 1.5, 2.3, discussion).

## 4.4: Negative findings, prioritized

The manuscript allocates space to negative findings in proportion to how much they change a reader's understanding of the pipeline, not equally:

1. **Given the most space** (a dedicated section, §6 "Resolving the Disruption-Type Question by Reanalysis"): critical-region targeting does not survive matched-round comparison against time-window targeting, in any disruption type, including the one case (arrivals) where an uncontrolled comparison initially suggested otherwise. This is the single most important corrective finding of the whole study, because it is the one most likely to have been overclaimed.
2. **Given prominent single-paragraph treatment**: the four-worker result (C6 fails outright); unstructured-repetition's near-null effect (RQ2's negative half).
3. **Given one sentence plus a pointer to supplementary material**: the certificate study's negative result (full proofs, oracle campaign and ablations remain in `docs/cobar/` and `docs/unified_icaps/`, not reproduced in the main text) and the adaptive-budget-skipping failure (recorded in `docs/cobar/05_budget_adaptation.md` and `docs/unified_icaps/03_lns_baseline_protocol.md`, referenced but not re-derived here since it concerns a component --- certificate-driven skipping --- that is not part of the final pipeline at all).

This matches the brief's instruction not to give every negative result equal space while still reporting all of them somewhere with a traceable location.
