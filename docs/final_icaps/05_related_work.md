# Final-phase 05 — Related work (Phase 5)

## 5.1-5.2: Full-text access, re-attempted

Both target papers were re-attempted via legitimate routes this phase (no paywall bypass):

| Route tried | Sun et al. (2026) | Lin & Yang (2026) |
|---|---|---|
| DOI resolution | `https://doi.org/10.1016/j.cie.2026.111943` | `https://doi.org/10.1016/j.cie.2026.112299` -> redirects to `linkinghub.elsevier.com/retrieve/pii/S0360835226005000` |
| Direct fetch of the resolved publisher URL | access-controlled ("Redirecting", no content) | same (fetched directly; no content beyond a redirect page) |
| arXiv / preprint search | none found | none found |
| Author-posted or aggregator copy (ResearchGate) | not attempted this phase (no new lead found) | searched; only unrelated papers and a different "Mingqi Yang" surfaced in related-items sidebars; no full text of the target paper |
| Institutional access / Elsevier TDM API | unavailable in this environment | unavailable in this environment |

**Result: both remain unavailable.** Marked explicitly as such in the manuscript (Related Work and Limitations) rather than inferred further from titles/abstracts. No implementation detail of either paper beyond what their Crossref/OpenAlex abstracts state is asserted anywhere in this study's documents or manuscript.

## 5.3: Novelty comparison table (consolidated from `docs/unified_icaps/02_prior_work_and_novelty.md`, corrected per Phase 2)

| Method | Model | Dynamic disturbance | Prev-solution reuse | Incumbent portfolio | Local neighbourhood | Critical-region targeting | Repeated local opt. | Global continuation | Parallel solver | Anytime metric | Verified? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| This study (SR+Crit / SR+TimeWin / etc.) | job shop | yes (4 delta types) | yes | yes | 4 strategies, size-matched | yes (one of 4) | yes, matched-round protocol | yes, hinted | 1 and 4 workers, both measured | PI | fully (Phase 1) |
| IAIP-SR (prior stage, `SR` baseline here) | job shop | yes | yes | yes | disruption-centred, single round | no | **no** | yes | 1 worker (confirmatory) | PI | fully (prior stage + Phase 1) |
| SLR2 \citep{linyang2026} | flexible job shop | yes (event-driven) | yes (incumbent-aware) | not stated | learned kept/released split | not stated | not stated (abstract does not say whether repair iterates) | not stated | not stated | final makespan/tardiness/stability, not anytime PI | **abstract only** |
| Sun et al. \citep{sun2026} | flexible job shop | yes | scope-dependent | not applicable (evolutionary) | 4 hierarchical scopes | scope-selection, not targeting within a fixed scope | iterative (evolutionary) | yes (global scope option) | not stated | RPD, stability | **abstract only** |
| CP-SAT native LNS | any CP-SAT model | n/a (static re-solve) | via hint | n/a | 4 built-in generators incl. 2 of our 4 analogues | no (random-interval/time-window/precedence, no critical-path generator) | yes, adaptive difficulty | is the global search itself | only active at $>1$ worker or `interleave_search` | n/a | fully (Phase 2, saved logs) |

Fields marked "not stated" or "abstract only" are explicitly left unfilled rather than guessed, consistent with the instruction not to infer implementation details from a title or abstract alone.

## 5.4: Positioning language check

A grep of the final manuscript for the specific phrases the brief flags as overclaiming (`first-ever`, `novel critical-path`, `guaranteed superiority`, `universally better`, `consistently better than native`) finds none present. The strongest claims made are: "reproducibly improves ... over a single restricted stage, over unstructured repetition, and over the installed solver's single-thread scheduling search" (qualified, evidenced, and immediately followed by the two explicit non-claims: no superiority over time-window targeting, no survival at four workers).
