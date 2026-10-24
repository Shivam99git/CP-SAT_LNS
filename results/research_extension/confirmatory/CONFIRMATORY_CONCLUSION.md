# IAIP-SR confirmatory campaign — conclusion

- **Analysis:** `.venv/bin/python -m phase0.analyze_confirmatory results/research_extension/confirmatory`, run 2026-10-24 on CPUs 16–19, after all 200 tasks had finished. The script refuses to run if `FROZEN_CONFIG.json` no longer matches its SHA-256 (`5fddfb71c7d9f9804231331ae8c4ecaab5f59c5c19d5c2ccfa9582dba3ba9758`), and the check passed.
- **Numbers:** every number below is from `confirmatory_analysis.json` or from the run files.
- **Design:** frozen on development streams only (`docs/research_extension/04_experimental_methodology.md` §5 and §8).

## Setup

| Item | Value |
|---|---|
| Streams | 40 held-out streams: 15×15 and 20×20 full job shops × stream seeds 501–520, 10 deltas each. Not used before this run. |
| Solver | CP-SAT, one worker, solver seeds 0–4 |
| Budget | B = 8 s, one deadline covering everything |
| CPU pinning | performance cores 0, 2, …, 14 |
| Protocol | closed loop: every method carries its own previous solution (checked: `prev_source = own` for all 20,000 step ≥ 1 records) |
| Unit of inference | the stream (seeds and steps 1–10 averaged within a stream) |
| Tests | exact two-sided sign test, Holm over the 8-member predeclared family; stream-clustered bootstrap 95% CI (10,000 resamples) |
| z\* | shared per physical instance across all 10 methods and 5 seeds |

## Frozen method

| Item | Value |
|---|---|
| Configuration | `iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted` |
| Phase 1 | anytime incumbent portfolio (hist, elr, mwkr, spt, insert, lpt, fifo) |
| Phase 2 | restricted CP-SAT on the N5 neighbourhood (bounded expansion, 25% of operations), improvement cutoff, budget α·B = 4.8 s |
| Phase 3 | full CP-SAT hinted with the current incumbent, for the rest of the budget |

## Integrity

| Check | Value |
|---|---|
| records | 22,000 |
| not validated | 0 |
| no solution | 0 |
| runs with a deadline overrun > 0 | 20,907 |
| overrun p99 | 0.017 s |
| overrun max | 0.244 s |
| min gap_B over all runs | 0.0 (no negative gap, so z\* is consistent) |
| local phase time, max | 4.75 s (≤ α·B) |
| construction time, max | 0.27 s |
| latest incumbent recorded | 8.009 s (incumbents after B are excluded from gap_B and the integral) |

- **Overruns:** they are solver return and validation latency. They are recorded and kept in every run.
- **Local phase outcomes** (2,000 runs):
  - improved the incumbent in 1,608;
  - OPTIMAL 1,570, FEASIBLE 38, INFEASIBLE 392. INFEASIBLE means the improvement cutoff proved there is no better schedule inside the neighbourhood.

**Fresh-portfolio check.** `fresh_portfolio_cold` and `mwkr_cold` have nearly equal means (0.059673 vs 0.059679). They are distinct methods:
- the fresh portfolio chose SPT, LPT or FIFO over MWKR in 310 of 2,200 runs;
- its trajectory differed from MWKR+Cold in 647 of 2,200 runs.

Unhinted CP-SAT with the same solver seed soon overwrites the small construction differences.

## Stream mean primal integral (steps 1–10)

| Role | PI | late PI | gap_B | t_first (s) |
|---|---|---|---|---|
| **iaip_sr** | **0.0339** | 0.0289 | 0.0197 | 0.002 |
| random_nbh_control | 0.0420 | 0.0374 | 0.0257 | 0.002 |
| portfolio_hinted | 0.0443 | 0.0395 | 0.0267 | 0.002 |
| portfolio_cold | 0.0495 | 0.0448 | 0.0308 | 0.002 |
| elr_cold | 0.0512 | 0.0449 | 0.0310 | 0.024 |
| floor | 0.0530 | 0.0465 | 0.0311 | 0.001 |
| fresh_portfolio_cold (primary comparator) | 0.0597 | 0.0514 | 0.0322 | 0.006 |
| mwkr_cold | 0.0597 | 0.0513 | 0.0322 | 0.006 |
| fresh_portfolio_hinted | 0.0612 | 0.0526 | 0.0333 | 0.007 |
| cold | 0.0666 | 0.0513 | 0.0322 | 0.067 |

## Predeclared family (primary endpoint: PI)

Negative rel. Δ means the first method is better.

| Comparison | rel. Δ | mean Δ [95% CI] | W/L | Holm p |
|---|---|---|---|---|
| **iaip_sr vs fresh_portfolio_cold (primary)** | **−43.2%** | −0.0258 [−0.0288, −0.0228] | 40/0 | 1.5e-11 |
| iaip_sr vs fresh_portfolio_hinted | −44.6% | −0.0273 [−0.0302, −0.0244] | 40/0 | 1.5e-11 |
| iaip_sr vs mwkr_cold | −43.2% | −0.0258 [−0.0288, −0.0228] | 40/0 | 1.5e-11 |
| iaip_sr vs floor | −36.1% | −0.0191 [−0.0218, −0.0164] | 39/1 | 1.5e-10 |
| iaip_sr vs cold | −49.1% | −0.0327 [−0.0358, −0.0295] | 40/0 | 1.5e-11 |
| iaip_sr vs portfolio_hinted (selective stage) | −23.4% | −0.0104 [−0.0124, −0.0084] | 40/0 | 1.5e-11 |
| iaip_sr vs random_nbh_control (impact-awareness) | −19.4% | −0.0081 [−0.0102, −0.0061] | 36/4 | 1.9e-7 |
| portfolio_cold vs fresh_portfolio_cold (history) | −17.1% | −0.0102 [−0.0116, −0.0089] | 40/0 | 1.5e-11 |

Secondary metrics for the primary comparison:

| Metric | rel. Δ | W/L | 95% CI |
|---|---|---|---|
| capped PI | −43.2% | 40/0 | |
| early PI [0, B/8] | −41.7% | 40/0 | |
| late PI [B/8, B] | −43.7% | 40/0 | |
| final gap at B | −38.6% | 39/1 | [−0.0146, −0.0102] |

## GO criteria (brief / methodology §5)

| Criterion | Result |
|---|---|
| PI reduction ≥ 15% vs fresh-portfolio+Cold, overhead included | PASS (43.2%) |
| improvement on ≥ 70% of streams | PASS (40/40) |
| stream-clustered CI excludes 0 | PASS ([−0.0288, −0.0228]) |
| primary Holm p < 0.05 | PASS (1.5e-11) |
| no systematic final-gap regression | PASS (final gap improves, 39/1) |
| 100% validated outputs | PASS (22,000/22,000) |
| selective stage adds measurable value | PASS (vs portfolio + hinted global with no local phase: −23.4%, 40/0, Holm 1.5e-11) |

**Verdict: GO**, for the configuration and scope tested.

## Exploratory breakdowns (not part of the confirmatory claim)

PI by delta type, primary comparison:

| Delta | streams | iaip_sr | fresh+Cold | Floor | portfolio_hinted | portfolio_cold | rel. Δ (primary) | W/L |
|---|---|---|---|---|---|---|---|---|
| arrival | 39 | 0.0363 | 0.0622 | 0.0650 | 0.0522 | 0.0573 | −41.7% | 38/1 |
| cancellation | 38 | 0.0328 | 0.0569 | 0.0445 | 0.0374 | 0.0448 | −42.3% | 38/0 |
| duration jitter | 40 | 0.0312 | 0.0589 | 0.0444 | 0.0386 | 0.0446 | −47.0% | 39/1 |
| outage | 29 | 0.0391 | 0.0546 | 0.0459 | 0.0469 | 0.0443 | −28.4% | 25/4 |

By size: 15×15 −45.0% (20/0); 20×20 −41.7% (20/0).

## Observations

- **Arrivals.** In Gate 1 and here, Floor is worse than fresh construction after arrivals (here 0.0650 vs 0.0622). IAIP-SR removes that weakness.
- **Outages.** Outage steps have the smallest effect. There, hinting the global phase hurts: portfolio_hinted 0.0469 vs portfolio_cold 0.0443. The selective stage still recovers the loss.
- **Where the gain comes from.** The chain fresh_portfolio_cold → portfolio_cold → portfolio_hinted → iaip_sr adds one component at a time. The steps sum exactly to the total of −0.0258:
  - history-based incumbents in the portfolio: 0.0597 → 0.0495, −0.0102;
  - hinting the global phase with that incumbent: → 0.0443, −0.0052;
  - the selective local stage: → 0.0339, −0.0104.

  This attribution depends on the order in which components are added; other orders were not run.

## Supplementary comparisons (not predeclared; uncorrected sign tests)

Source: `supplementary_analysis.json`, computed after the predeclared analysis.

| Comparison | rel. Δ PI | 95% CI | W/L | p |
|---|---|---|---|---|
| portfolio_hinted vs portfolio_cold (middle step of the chain) | −10.5% | [−0.0068, −0.0036] | 34/6 | 8.4e-6 |
| fresh_portfolio_hinted vs fresh_portfolio_cold | +2.5% | [−0.0001, +0.0031] | 13/27 | 0.038 |
| elr_cold vs floor | −3.5% | [−0.0028, −0.0010] | 28/12 | 0.017 |
| random_nbh_control vs portfolio_hinted | −5.0% | [−0.0035, −0.0010] | 28/12 | 0.017 |
| portfolio_cold vs floor | −6.7% | [−0.0046, −0.0026] | 37/3 | 1.9e-8 |

Reading:
- Hinting the continuation with the current, history-informed incumbent helps.
- Hinting it with a fresh dispatching schedule does not; if anything it hurts slightly.
- A random neighbourhood still adds a little over no restricted stage.

**Stability** (exploratory): the share of operations present in both S_{t−1} and S_t whose start time changed (same method, same solver seed), averaged over steps 1–10:

| Method | Share changed |
|---|---|
| iaip_sr | 85.9% |
| floor | 91.1% |
| portfolio_hinted | 92.6% |
| cold, mwkr_cold, fresh_portfolio_cold | 94.7% |

No method is stable in the sense of Fox et al. (2006). None optimizes stability.

## Scope and caveats

1. **Setup.** Synthetic full job shops of two sizes, one delta mix, medium severity, B = 8 s, one CP-SAT worker. Other budgets, worker counts, delta mixes and published benchmark bases are E6 (exploratory) and are not covered by this verdict.
2. **The comparator.** The baselines are single-worker CP-SAT runs whose final gaps are still about 3% at 8 s. Much of the gain is that a focused restricted solve plus a hinted continuation makes better use of a short budget than one global solve. Whether this holds with more workers or longer budgets is open until E6.
3. **What "GO" means.** It refers to the brief's predeclared criteria on this frozen configuration. It is not a claim of novelty: see `docs/research_extension/06_related_work_novelty.md` for the closest prior work (AOR/mAOR, Sun et al. 2026, LNS/RINS-style restriction).
