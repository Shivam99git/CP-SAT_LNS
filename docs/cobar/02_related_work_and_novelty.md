# COBAR 02 — Related work and novelty (Phase 2)

## Verification standard

Bibliographic data comes from Crossref (DOI), DataCite, or OpenAlex records fetched on 2026-10-25. The **access** column says exactly what was read:
- **abstract** — the registry abstract or the publisher abstract;
- **search summary** — only a search engine's summary of the abstract; the publisher returned HTTP 403;
- **standard knowledge** — the classical content is well known and was not re-read for this document.

Statements marked "standard knowledge" or "search summary" must be checked against the full text before they appear in a submitted paper.

## 1. Closest methods

| Work | Problem / objective | Repair / neighbourhood | Bound or certificate | Solver and continuation | Adaptation / budget | Evaluation | Access |
|---|---|---|---|---|---|---|---|
| **Lin & Yang 2026**, *An incumbent-aware selective-repair framework for dynamic flexible job shop scheduling*, C&IE 221:112299, doi:10.1016/j.cie.2026.112299 (online 2026-08-11) | dynamic FJSP; makespan, total tardiness, stability | **SLR2**: a heterogeneous schedule graph; a dual-head GNN splits active-window operations into kept and released sets; a **reduced CP-SAT model repairs only the released neighbourhood** under a strict time budget; rolling horizon | none stated | reduced CP-SAT; continuation to a full solve not stated in the abstract | learned release policy; fixed time budget | Brandimarte Mk1–Mk10, 7 methods, 10 seeds; final quality, stability, runtime; zero-shot transfer to 100×20 | abstract (OpenAlex) |
| **Sun, Cheng, Ding & Zhao 2026**, *Impact of optimization scope on solution quality and stability in dynamic flexible job shop rescheduling*, C&IE 215:111943, doi:10.1016/j.cie.2026.111943 | dynamic FJSP; quality (RPD) and stability | four hierarchical optimization scopes, from minimal repair to global re-optimization; "greedy trap" of myopic local optimization; **ERRE** (event-driven rescheduling with elite evolution) | none stated | evolutionary | scope chosen per strategy | Mean-RPD 0.76% for ERRE vs 4.15% for global rescheduling under strict real-time limits | **search summary only** |
| **Li, Ouyang, Ma & Wu 2025**, *Learning-guided rolling horizon optimization for long-horizon flexible job-shop scheduling* (L-RHO), ICLR 2025 | static long-horizon FJSP | rolling-horizon subproblems; a network predicts which operations to **fix** (unchanged assignments) | none | CP-based subproblem solver | learned fixing | up to 54% faster RHO | abstract (search summary of the arXiv abstract) |
| **Li, Wang, Peng, Li & Xu 2026**, *Graph-RHO: critical-path-aware heterogeneous graph network for long-horizon FJSP*, arXiv:2604.10073 (preprint) | as L-RHO | GNN predicts stable (fixable) operations; **critical-path operations are used as a training inductive bias**; adaptive thresholds | **none** (the abstract mentions no bound or certificate) | solver not named in the abstract | online uncertainty-calibrated thresholds | — | abstract (arXiv) |
| **IAIP-SR** (this project, unpublished) | dynamic JSSP; anytime PI | portfolio; BFS neighbourhood around the disruption set; restricted CP-SAT with `C_max ≤ U − 1`; hinted global continuation | improvement bound only | CP-SAT, separate local and global solves | fixed α = 0.6 | stream-level, 5 seeds, frozen configuration | — |
| **CP-SAT internal LNS** (OR-Tools 9.15) | any CP-SAT model | generic and scheduling-specific neighbourhoods (`scheduling_precedences_lns`, `scheduling_time_window_lns`, `scheduling_intervals_lns`, `scheduling_resource_windows_lns`, graph/random) | solver's own bounds | inside one solve | adaptive LNS difficulty | — | solver logs on this model; `sat_parameters.proto` v9.15 (`interleave_search` is documented as "experimental … deterministic (independently of num_workers)"); Perron, Didier & Gay, *The CP-SAT-LP solver*, CP 2023 invited talk, LIPIcs 280, doi:10.4230/LIPIcs.CP.2023.3 |

## 2. Classical results COBAR builds on

None of these is a COBAR contribution.

| Result | Source | Access |
|---|---|---|
| In the disjunctive graph of a complete acyclic selection, the makespan of the earliest-start schedule equals the longest source–sink path | Balas 1969, OR 17(6):941–957, doi:10.1287/opre.17.6.941 | standard knowledge |
| Neighbourhoods that reverse arcs on a critical path. Reversing a non-critical arc cannot decrease the makespan | van Laarhoven, Aarts & Lenstra 1992, OR 40(1):113–125 | standard knowledge |
| Critical-block neighbourhoods; moving operations to block ends | Nowicki & Smutnicki 1996, MS 42(6):797–813; Balas & Vazacopoulos 1998, MS 44(2):262–275, doi:10.1287/mnsc.44.2.262 | standard knowledge |
| Block approach in branch and bound | Brucker, Jurisch & Sievers 1994, DAM 49:107–127, doi:10.1016/0166-218X(94)90204-6 | standard knowledge |
| One-machine (head–body–tail) lower bounds | Carlier 1982, EJOR 11(1):42–47, doi:10.1016/S0377-2217(82)80007-6; Carlier & Pinson 1989, MS 35(2):164–176, doi:10.1287/mnsc.35.2.164; Applegate & Cook 1991, ORSA JoC 3(2):149–156, doi:10.1287/ijoc.3.2.149 | standard knowledge |
| Max-flow / min-cut; an s–t edge cut hits every s–t path (Menger) | Ford & Fulkerson 1956, Can. J. Math. 8:399–404, doi:10.4153/CJM-1956-045-5; Edmonds & Karp 1972, JACM 19(2):248–264, doi:10.1145/321694.321699 | standard knowledge |
| Affected-operations rescheduling | Abumaizar & Svestka 1997; Subramaniam & Raheja 2003 (verified in the IAIP-SR bibliography) | — |
| LNS with CP | Shaw 1998; Godard, Laborie & Nuijten 2005; Pacino & Van Hentenryck 2011 | — |
| Portfolios / multi-start | Gomes & Selman 2001; Feo & Resende 1995 | — |

## 3. Classification of the proposed COBAR ingredients

| Ingredient | Classification | Reason |
|---|---|---|
| L_N = longest path over job arcs, *kept* machine arcs, release dates, commitments and outage-aware earliest starts; L_N ≤ C*_N | **known lemma** (adapted) | a relaxation bound; the fixed-precedence longest-path bound is Balas-type. The calendar-aware head propagation is a standard earliest-start argument |
| "L_N ≥ U ⇒ the neighbourhood cannot improve" | **known lemma** | follows immediately; the critical-arc reasoning of van Laarhoven et al. |
| Skipping certified neighbourhoods | known idea, **expected negligible value** here | CP-SAT already proves such neighbourhoods infeasible in ~21 ms (01 §F1) |
| Releasing a minimum-cost set of machine arcs that hits **all** longest paths of the kept-arc graph, via an s–t min cut on its tight subgraph, mapped to operation releases with fill-in arcs | **potentially new procedure** in this setting | classical neighbourhoods use one critical path or its blocks. No source found that computes a min cut over the tight subgraph to choose CP-SAT releases. **Absence of evidence only** (one web search plus the papers above) |
| Certificate-aware budget allocation (skip / short / long local stage) | **potentially new combination** | adaptive LNS difficulty exists inside CP-SAT; deterministic certificate-driven allocation between separate local and global solves was not found |
| Native CP-SAT scheduling LNS as the explanation for E6b | **empirical hypothesis** | must be tested (A9) |

## 4. What COBAR must show to be a distinct contribution

1. **Soundness:** L_N ≤ C*_N on exact-oracle instances, with outages, releases and commitments; zero false certificates.
2. **Information beyond what CP-SAT already exploits:** the certificate must change a decision, not merely predict an INFEASIBLE status that CP-SAT would reach in milliseconds. The relevant decisions are which arcs to release, and how much time to give the local stage.
3. **Value beyond simple adaptation:** COBAR must beat a budget/worker-only policy (A4), not just fixed IAIP-SR.
4. **Value beyond native LNS:** COBAR must beat portfolio + hinted CP-SAT with `interleave_search` (A9), which already runs scheduling LNS on one core.
5. **Differences from SLR2 and L-RHO / Graph-RHO:**
   - those methods *learn* the kept/released split from data;
   - COBAR's release rule is a *sound structural* necessary condition computed per instance, with no training;
   - COBAR is evaluated by anytime PI under one end-to-end deadline.

   Whether this difference matters empirically has not yet been tested.

## 5. Gate decision

The complete proposed mechanism was not found in prior work:
- a sound neighbourhood certificate;
- min-cut release of the tight subgraph;
- certificate-aware deadline allocation between restricted and unrestricted CP-SAT.

**Decision: proceed.** Two standing constraints apply:
- the no-improvement theorem is presented as a known lemma, never as a new result;
- the skip rule is expected to be worth ≤ 0.1% of the budget (01 §F1). If the experiments confirm this, it is reported as a negative result.

**Must-cite for any manuscript:** Lin & Yang 2026; Sun et al. 2026; L-RHO 2025; Graph-RHO (preprint); Balas 1969; van Laarhoven et al. 1992; Nowicki & Smutnicki 1996.

**Must-read before submission:** the full texts of Lin & Yang 2026 and Sun et al. 2026.

## 6. Final classification (after the confirmatory study, 2026-10-26)

| Ingredient | Outcome | Classification |
|---|---|---|
| certificate L(N, R), no-improvement test, global certificate | sound: 5,500 oracle cases, 0 violations; no measurable effect on decisions | known lemma, adapted; **negative empirical result** |
| min-cut release of obstructing chains | correct and minimum: 1,000 cases; no measurable effect as release or as round seeds | possibly new procedure in this setting; **not credited** |
| certificate-aware budget allocation | no measurable effect | **not credited** |
| budget-only skip rule | harmful in development | **negative result** |
| repeated restricted rounds seeded at the critical region | held-out vs IAIP-SR: S1 −24.8% (39/1) and better in S2–S7; vs random seeds −17.7% | **known idea** (critical-path neighbourhoods); new **empirical** finding about its value under a deadline in this pipeline |

**Distinction from the closest work:**
- SLR2 learns the kept/released split.
- The candidate uses a structural, per-instance critical region and is evaluated by anytime PI under one end-to-end deadline against fresh-incumbent and IAIP-SR baselines.

This is a difference in method and evaluation, not a claim of superiority over SLR2: they were never compared, and SLR2 targets flexible job shops.
