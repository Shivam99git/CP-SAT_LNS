# 06 — Related Work and Novelty Assessment

Verification standard: every entry below was checked against a registry record (Crossref DOI or OpenAlex), a publisher or institutional page, or a proceedings anthology. A "Source" note marks the weakest check. Where only a search-engine summary of an abstract was available, this is stated, and the paper is treated as **not fully read**.

## 1. Closest prior work, by component

| Component of IAIP-SR | Prior work that already does it | Novel here? |
|---|---|---|
| Reschedule only the operations affected by a disruption | **Affected Operations Rescheduling (AOR):** Abumaizar & Svestka, *Rescheduling job shops under random disruptions*, IJPR 35(7):2065–2082, 1997, doi:10.1080/002075497195074. Compared with total and right-shift rescheduling on efficiency and stability. Extended as **mAOR:** Subramaniam & Raheja, IJAMT 22(9–10):669–680, 2003, doi:10.1007/s00170-003-1601-6 | **No.** ELR's dependency closure A_Δ is the affected-operations idea. |
| Choosing the rescheduling scope (minimal repair … global re-optimization) | **Sun, Cheng, Ding & Zhao**, *Impact of optimization scope on solution quality and stability in dynamic flexible job shop rescheduling*, Computers & Industrial Engineering 215:111943, 2026, doi:10.1016/j.cie.2026.111943. Per a search-engine summary of its abstract (full text not accessed; publisher pages refuse automated access): four hierarchical scopes; a "greedy trap" for myopic local optimization; an affected-scope evolutionary strategy (ERRE) best under strict real-time limits. | **No** for the scope question itself. This is the closest paper and must be cited and contrasted; it should be read in full before submission. |
| Inserting operations into fixed machine sequences | **Werner & Winkler**, *Insertion techniques for the heuristic solution of the job shop problem*, Discrete Applied Mathematics 58(2):191–211, 1995, doi:10.1016/0166-218X(93)E0127-K | **No.** ELR's INSERT step is this principle. |
| Critical-path / block neighbourhoods | **van Laarhoven, Aarts & Lenstra**, OR 40(1):113–125, 1992, doi:10.1287/opre.40.1.113; **Nowicki & Smutnicki**, Management Science 42(6):797–813, 1996, doi:10.1287/mnsc.42.6.797 | **No.** N3 is the standard critical-path notion. |
| CP-based LNS for scheduling | **Shaw**, CP-98, LNCS, pp. 417–431, 1998, doi:10.1007/3-540-49481-2_30; **Godard, Laborie & Nuijten**, ICAPS 2005, pp. 81–89 (source: TU/e research portal); **Pacino & Van Hentenryck**, IJCAI 2011, pp. 1997–2002 (source: IJCAI anthology) | **No.** The selective phase is a single CP-SAT large-neighbourhood step. |
| Online-learned LNS operator selection | **Cai, Kadıoğlu & Dilkina** (BALANS), IJCAI 2025, pp. 2566–2574, doi:10.24963/ijcai.2025/286 | Not used. A contextual-bandit selector failed earlier in this project (`01_repository_audit.md` §9). |
| Reusing a previous solution in dynamic CSP / MIP | **Verfaillie & Schiex**, AAAI-94, pp. 307–312 (source: proceedings listing, HAL); **Bolusani et al.**, Mathematical Programming Computation 16(2):255–266, 2024, doi:10.1007/s12532-024-00256-w | **No.** |
| Several constructive starts, keep the best | **Feo & Resende** (GRASP), Journal of Global Optimization 6(2):109–133, 1995, doi:10.1007/BF01096763; **Gomes & Selman**, *Algorithm portfolios*, AIJ 126(1–2):43–62, 2001, doi:10.1016/S0004-3702(00)00081-3 | **No.** The incumbent portfolio is a best-of-k selection. |
| Rescheduling frameworks and surveys | Vieira, Herrmann & Lin, J. Scheduling 6(1):39–62, 2003; Ouelhadj & Petrovic, J. Scheduling 12(4):417–431, 2009; Mohan, Lanka & Rao, Procedia Manufacturing 30:34–39, 2019, doi:10.1016/j.promfg.2019.02.006; match-up: Bean et al., OR 39(3):470–483, 1991 | — |
| Plan repair and stability | Nebel & Koehler, AIJ 76(1–2):427–454, 1995; van der Krogt & de Weerdt, ICAPS 2005, pp. 161–170; Fox et al., ICAPS 2006, pp. 212–221 | — |
| Anytime evaluation | Dean & Boddy, AAAI-88, pp. 49–54; Zilberstein, AI Magazine 17(3):73–83, 1996; primal integral: Berthold, ORL 41(6):611–614, 2013 | — |

## 2. What could still be a contribution

No individual component is new. A defensible contribution can only come from **the combination and its evaluation**, and only if the experiments support it:

1. **An anytime, budget-shared pipeline:** portfolio, then restricted CP-SAT, then unrestricted CP-SAT, under *one* wall-clock deadline, with construction overhead charged. AOR and Sun et al. compare final schedule quality and stability; here the subject is the quality available at every moment of a fixed budget.
2. **Separating the value of history from the value of having an incumbent at all:** fresh-portfolio+Cold is the predeclared comparator (Gate 1 and §5 of the methodology). None of the cited rescheduling papers was found to compare against fresh dispatch-plus-solver baselines under matched anytime budgets. This is an absence-of-evidence statement, limited to the papers read.
3. **A characterization of when solver hints help or hurt**, measured with stream-level statistics (from the archived data and Gate 1).

If the experiments show the selective stage adds nothing over a portfolio of incumbents followed by an unrestricted solver, the honest paper is the empirical one: **when does history help an anytime rescheduler, and when does a fresh constructive incumbent suffice?** That conclusion would be reported as such.

## 3. To do before submission

- Read Sun et al. (2026) in full; the summary above is not a substitute.
- Search specifically for CP-SAT or CP Optimizer *reactive* scheduling papers with warm starts (none were found in this pass).
- Check whether Abumaizar & Svestka's affected-operations set matches A_Δ exactly for each event type, and say so precisely in the paper.
