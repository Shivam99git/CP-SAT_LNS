# Unified study 02 — Prior work and novelty audit (Stage 2)

## 1. Access status

| Work | Access obtained | Limitation |
|---|---|---|
| Sun, Cheng, Ding & Zhao 2026, C&IE 215:111943, doi:10.1016/j.cie.2026.111943 | Crossref metadata; a search engine's summary of the abstract | **Full text not read.** ScienceDirect returns HTTP 403 to automated access; the Elsevier text-mining API (listed in Crossref) requires an API key (`AUTHENTICATION_ERROR: Invalid API Key`). No preprint found |
| Lin & Yang 2026, C&IE 221:112299, doi:10.1016/j.cie.2026.112299 | Crossref metadata; full abstract (OpenAlex) | **Full text not read**, for the same reasons. No preprint found (web search 2026-10-26) |
| OR-Tools CP-SAT v9.15 (installed 9.15.6755) | source at tag `v9.15`: `ortools/sat/cp_model_lns.{h,cc}`, `cp_model_solver.cc`, `sat_parameters.proto`, `docs/scheduling.md`; solver logs on this project's model | the tag source is assumed to match the installed wheel (same release number); the binary itself was not rebuilt |
| Classical job-shop theory | bibliographic records verified (Crossref); content from standard knowledge | not re-read |

Everything said below about Sun et al. and Lin & Yang rests on their abstracts and must be checked against the full texts before submission.

## 2. Closest work

### Lin & Yang 2026 (SLR2), from the abstract
- **Problem:** event-driven dynamic *flexible* job shop. It revises an incumbent plan rather than rescheduling from scratch.
- **Representation:** a heterogeneous schedule graph encodes the plan, machine states and disturbance impacts.
- **Decision:** a dual-head GNN partitions active-window operations into **kept** and **released** sets.
- **Solve:** a **reduced CP-SAT model repairs only the released neighbourhood under a strict time budget**, in a rolling horizon.
- **Results:** on Brandimarte Mk6–Mk10 (7 methods, 10 seeds) it matches the quality of full re-optimization (lowest mean makespan and tardiness) with a 14.6% lower changed-operation ratio, half the changed-machine ratio, and 1.5× speed. It transfers zero-shot to 100×20 instances.
- **Overlap with us:** incumbent-aware selective repair with a restricted CP-SAT model is **shared**. IAIP-SR's restricted stage is the same idea.
- **Differences** (as far as the abstract shows):
  - SLR2 *learns* the release set, while ours is structural and per-instance;
  - SLR2 does one repair per event, while ours runs repeated rounds plus an unrestricted continuation under one deadline;
  - SLR2 reports final quality, stability and runtime, while ours reports anytime PI;
  - SLR2 targets flexible job shops; ours targets job shops.

  Whether SLR2 iterates or continues globally is not stated in the abstract.

### Sun et al. 2026, from a search summary of the abstract
- **Framework:** four hierarchical optimization scopes, from minimal repair to global re-optimization.
- **Finding:** myopic local optimization falls into a "greedy trap", with cascading delays and instability.
- **ERRE** (event-driven rescheduling with elite evolution, evolutionary) has the lowest mean RPD (0.76% vs 4.15% for global rescheduling) under strict real-time limits. "Precise scope definition outperforms blind global search."
- **Overlap:** scope selection for rescheduling.
- **Differences:** an evolutionary solver; no CP-SAT; no anytime PI; flexible job shops.

### CP-SAT internal scheduling LNS (v9.15 source)

| Item | Behaviour |
|---|---|
| Activation | LNS subsolvers are created when `use_lns` (default true) and the model has an objective (`cp_model_solver.cc` ~l.1898). They run only with `num_workers > 1`, or with `interleave_search` (then all subsolvers share the thread pool; with one worker they run on one thread, l.2150). Logs on our model: 1 worker = `main` only; 4 workers = 13 interleaved subsolvers including the four scheduling LNS |
| `scheduling_intervals_lns` | relaxes a random subset of intervals (size = difficulty × #active intervals), then **adds the incumbent's precedences between non-relaxed intervals** on each no-overlap resource; hinted with the incumbent. The code comment cites Godard, Laborie & Nuijten (ICAPS 2005). This is exactly the restriction structure of IAIP-SR's restricted model |
| `scheduling_time_window_lns` | sorts intervals by (start, end), takes ⌊difficulty·n⌋ consecutive intervals from a random index, relaxes them, keeps precedences among the rest |
| `scheduling_resource_windows_lns` | one such window per resource |
| `scheduling_precedences_lns` | extracts all incumbent precedences on resources and **keeps a random (1 − difficulty) fraction** |
| Difficulty | adapted online per generator (`lns_initial_difficulty` 0.5, then adaptive) |
| Solution pool | improving solutions are shared through the solution repository |
| Public controls | `use_lns`, `use_lns_only`, `interleave_search`, `num_workers`, and subsolver name filters (`ignore_subsolvers` / `extra_subsolvers`) |

**Limits on use (corrected 2026-11-23).** An earlier version of this document overstated the restriction: `SatParameters.filter_subsolvers` / `extra_subsolvers` / `ignore_subsolvers` ARE exposed to Python and were verified (`results/final_icaps/solver_logs/`) to isolate exactly the four scheduling LNS generators when used (confirmed: with `filter_subsolvers` set to the four scheduling-LNS names, only those four plus the three helper subsolvers run; status UNKNOWN results because no full-problem/first-solution subsolver remains to produce an initial incumbent on its own). A global *initial* LNS difficulty (`lns_initial_difficulty`, default 0.5) is likewise exposed, though the per-generator adaptive difficulty that evolves during search is not independently settable per generator after that. We did **not** use subsolver filtering in any reported experiment: B5/B6 use CP-SAT's default or `interleave_search` portfolio exactly as a user would get it without special configuration, which includes the four scheduling generators alongside graph/random/RINS-RENS generators (confirmed active together in the logs below), not an isolated scheduling-only variant. Isolating scheduling-LNS-only behaviour (combining `extra_subsolvers` with a retained core search subsolver, which `filter_subsolvers` alone removes) is a feasible follow-up experiment, not attempted here because it answers a narrower question than any claim this study makes. We use:
- (a) the supported configurations, with activity confirmed from logs: 4-worker default, and 1-worker `interleave_search`;
- (b) independently implemented **external analogues** of the three scheduling generators, for single-worker mechanism comparisons.

### Classical

| Topic | Reference |
|---|---|
| makespan = longest path of a complete selection | Balas 1969 |
| critical-arc reversal neighbourhoods | van Laarhoven et al. 1992 |
| critical-block neighbourhoods and tabu search | Nowicki & Smutnicki 1996; Balas & Vazacopoulos 1998 |
| CP-based LNS | Shaw 1998; Godard et al. 2005; Pacino & Van Hentenryck 2011 |
| the shuffle heuristic for job shops | Applegate & Cook 1991 |
| affected-operations rescheduling | Abumaizar & Svestka 1997; Subramaniam & Raheja 2003 |
| portfolios | Gomes & Selman 2001 |

## 3. Comparison table

| Component | Floor (stage 1) | IAIP-SR | Critical-region rounds (this study) | SLR2 | Sun et al. ERRE | CP-SAT native LNS | Classical critical-path LS |
|---|---|---|---|---|---|---|---|
| previous-schedule reuse | repaired floor | portfolio (history members) | inherited | yes (incumbent graph) | yes | via hint only | — |
| fresh constructive incumbents | — | dispatching rules in portfolio | inherited | not stated | not stated | first-solution workers | — |
| selective repair (restricted region) | — | disruption-centred, 25% | inherited | learned release set | scope levels | random / time-window / precedence | move-based |
| critical-path-guided selection | — | — | **seeds at all ops of the longest binding chains** | Graph-RHO uses critical-path bias in training (different paper) | not stated | no | **yes** (core idea) |
| repeated neighbourhood rounds | — | one round | up to 10 within the local window | one repair per event (as far as stated) | evolutionary iterations | yes, many | yes |
| solver hints | evaluated (they hurt) | global stage hinted with incumbent | inherited | not stated | — | hint = incumbent | — |
| budgeted global continuation | unhinted global | hinted global after α·B | inherited | not stated | global scope option | is the global search | — |
| anytime evaluation (PI) | yes | yes | yes | no (final quality) | no | no | no |
| mathematical guarantees | floor never worse than its own solver run | incumbent retention | incumbent retention; restricted model contains the incumbent | not stated | — | complete solver | local optimality w.r.t. moves |

## 4. What is established, and what remains for the contribution

**Established, so not ours to claim:**
- critical-path / critical-region search;
- LNS with CP, including restricted re-solves that keep incumbent precedences (Godard et al. 2005; CP-SAT's `scheduling_intervals_lns`);
- selective CP-SAT repair of a released neighbourhood (SLR2);
- portfolios;
- hints;
- global continuation.

**The contribution can only be one of these:**
1. *Empirical*, if it holds: under one end-to-end deadline, repeated restricted rounds seeded at the incumbent's critical region beat size-matched external analogues of CP-SAT's own scheduling neighbourhoods (random intervals, time window, precedences), beat CP-SAT's native LNS under matched resources, and improve a strong incumbent-aware pipeline.
2. A finding about **where** the advantage holds or vanishes (budgets, workers, disruption types).

**Duplication check.** No source found combines critical-region-seeded repeated restricted CP-SAT rounds with an incumbent portfolio and a hinted global continuation under one anytime deadline. This rests on the sources above and is an absence of evidence. SLR2's full text could change this assessment: if SLR2 iterates repairs or seeds them at critical operations, the integration claim narrows further.

## 5. Gate

The critical-region idea is not new. The decisive question is now empirical: do critical rounds beat strong, faithful LNS controls?

**Decision: proceed to Stage 3–4, the controls first.**
