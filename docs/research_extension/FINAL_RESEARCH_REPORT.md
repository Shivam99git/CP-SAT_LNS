# IAIP-SR — Final Research Report

- **Branch:** local branch `research/iaip-sr`, never pushed.
- **Scope:** this report covers the research brief "Impact-Aware Incumbent Portfolio with Selective Reoptimization (IAIP-SR)", an extension of the archived manuscript *Floor, Not Hint*.
- **Sources:** every number is from a script output saved under `results/research_extension/`; the source file is named in each section.
- **Exploratory results** are labelled as such.

## 1. Verdict

| Question | Answer | Evidence |
|---|---|---|
| Does historical reuse add value beyond a fresh incumbent? (Gate 1) | **Yes**, predeclared rule met | Floor beats SPT+Cold −16.9% (45/0 streams) and MWKR+Cold −15.8% (44/1), Holm p ≤ 1e-11 |
| Does IAIP-SR meet the brief's GO criteria? | **GO**: all 7 criteria met | vs fresh-portfolio+Cold −43.2% PI, 40/0 streams, CI [−0.0288, −0.0228], Holm 1.5e-11 |
| Does the selective stage add value? | **Yes** | vs portfolio + hinted global with no local stage: −23.4%, 40/0, Holm 1.5e-11 |
| Does impact-awareness matter? | **Yes** | vs random neighbourhood of equal size: −19.4%, 36/4, Holm 1.9e-7 |
| Is any component new? | **No**, individually | §7 and `06_related_work_novelty.md` |
| Robust beyond the confirmatory setting? | see §5 (E6, exploratory) | |

**Scope of the GO:**
- synthetic full job shops, 15×15 and 20×20;
- the default delta mix at medium severity;
- one CP-SAT worker, B = 8 s;
- the configuration frozen in `results/research_extension/confirmatory/FROZEN_CONFIG.json` (SHA-256 `5fddfb71…`).

## 2. What was built

| Component | File | Tests |
|---|---|---|
| Schedule validator (independent of the solver model) | `phase0/schedule_validator.py` | `tests/test_reuse_methods.py` |
| Deadline-correct Gate 1 methods (one monotonic deadline) | `phase0/reuse_methods.py` | same |
| Event-localized repair (ELR), fixed-order evaluation, insertion | `phase0/event_localized_repair.py` | `tests/test_event_localized_repair.py` (22 tests, incl. a CP-SAT oracle on 150 instances) |
| Anytime incumbent portfolio | `phase0/incumbent_portfolio.py` | `tests/test_incumbent_portfolio.py` |
| Disruption set, neighbourhoods N1–N5 and random, restricted CP-SAT | `phase0/selective_reoptimization.py` | `tests/test_selective_reoptimization.py` (incl. an enumeration oracle on 40 tiny instances) |
| Integrated method | `phase0/impact_aware_reoptimization.py` | same |
| Campaign runners | `phase0/run_gate1.py`, `phase0/run_iaip_campaign.py`, `scripts/run_e6.sh` | `tests/test_run_iaip_campaign.py` |
| Analyses | `phase0/analyze_gate1.py`, `analyze_campaign.py`, `analyze_confirmatory.py`, `analyze_e6.py` | `tests/test_analyze_gate1.py` |

The archived Floor implementation is unchanged. Floor is the `hist` member of the portfolio and the `floor` method.

## 3. Gate 1: historical reuse vs fresh construction

Source: `results/research_extension/gate1_historical_reuse/GATE1_CONCLUSION.md`, `analysis.json`.

**Setup:** 45 streams (10/15/20 × seeds 101–115) × solver seeds 0–4, B = 8 s; 26,325 runs, all validated.

Protocol B (each method keeps its own previous solution):

| Comparison | Δ PI | W/L | Holm p |
|---|---|---|---|
| Floor vs Cold | −23.6% | 45/0 | 4.5e-13 |
| Floor vs SPT+Cold | −16.9% | 45/0 | 4.5e-13 |
| Floor vs MWKR+Cold | −15.8% | 44/1 | 1.0e-11 |
| Hint vs Cold | +20.9% | 9/36 | 1.3e-4 |
| Floor+Hint vs Floor | +18.2% | 9/36 | 1.3e-4 |
| Repaired-hint-only vs Floor | +25.6% | 4/41 | 2.8e-8 |

- **Protocol A** (common predecessor) agrees in sign on every comparison.
- **Weak case:** after arrivals, Floor loses to MWKR+Cold (+4.8%, 5/40 streams). The appended repair's median initial gap there is 53.1%, against 15.1% for MWKR.

## 4. Confirmatory campaign

Source: `results/research_extension/confirmatory/CONFIRMATORY_CONCLUSION.md`, `confirmatory_analysis.json`, `supplementary_analysis.json`.

**Setup:** 40 held-out streams (15/20 × seeds 501–520) × solver seeds 0–4; 22,000 runs, all validated; deadline overrun max 0.24 s, p99 0.017 s.

| IAIP-SR vs | Δ PI | W/L | Holm p (8-member family) |
|---|---|---|---|
| fresh-portfolio+Cold (primary) | −43.2% | 40/0 | 1.5e-11 |
| fresh-portfolio+hinted | −44.6% | 40/0 | 1.5e-11 |
| MWKR+Cold | −43.2% | 40/0 | 1.5e-11 |
| Floor | −36.1% | 39/1 | 1.5e-10 |
| Cold | −49.1% | 40/0 | 1.5e-11 |
| portfolio+hinted (selective stage) | −23.4% | 40/0 | 1.5e-11 |
| random neighbourhood | −19.4% | 36/4 | 1.9e-7 |
| *(portfolio+Cold vs fresh-portfolio+Cold)* | −17.1% | 40/0 | 1.5e-11 |

- **Final gap at B** (primary comparison): −38.6% (39/1).
- **By delta type** (exploratory):

  | Delta | Δ PI | W/L |
  |---|---|---|
  | arrival | −41.7% | 38/1 |
  | cancellation | −42.3% | 38/0 |
  | jitter | −47.0% | 39/1 |
  | outage | −28.4% | 25/4 |

- **Ablation chain.** PI goes 0.0597 → 0.0495 (history members) → 0.0443 (hinted continuation) → 0.0339 (selective stage). The middle step is not predeclared: −10.5%, 34/6, uncorrected p = 8.4e-6.
- **Hinting a fresh schedule** does not help: +2.5%, 13/27, uncorrected p = 0.038.

## 5. Robustness (E6, exploratory)

Specified in `04_experimental_methodology.md` §6 before any E6 run. Uses stream seeds 601–610, solver seed 0, and the frozen configuration.

**E6e: archived neighbourhood baselines** (20 streams, efficiency cores; source `results/research_extension/e6e_lns/analysis.json`):

| IAIP-SR vs | Δ PI | W/L | Holm p | Δ gap_B |
|---|---|---|---|---|
| Floor | −45.0% | 20/0 | 5.7e-6 | −60.4% (18/2) |
| LNS from the previous solution (archived) | −84.2% | 20/0 | 5.7e-6 | −92.0% (20/0) |
| fix-and-optimize 50% (archived) | −77.6% | 18/2 | 4.0e-4 | −92.6% (17/3) |

The archived LNS consists of 1 s rounds with fixed neighbourhoods and no unrestricted continuation, and it is far behind Floor, as in the archived paper. IAIP-SR's restricted stage differs in three ways:
- it is a single solve on an event-derived neighbourhood;
- it carries an improvement bound;
- it is followed by an unrestricted continuation.

E6a–E6d: *pending; filled in from `results/research_extension/e6_analysis.json` once the runs finish.*

## 6. Correctness

`05_correctness_and_verification.md` lists each property as PASS / FAIL→fixed / NOT VERIFIED.

**Defects found and fixed during the work:**
- the ELR outage core was always empty;
- insertion could create a cycle when re-inserting a mid-chain operation;
- insertion and the fallback could violate commitments;
- the portfolio was not anytime, which was logged as a deviation.

**Test suite:** 199 fast + 25 slow tests pass, plus 5 tests for the E6 runner options.

**Not verified:**
- multi-worker behaviour, except through E6b;
- any non-job-shop domain. The new methods are job-shop only.

## 7. Novelty (see `06_related_work_novelty.md`)

| Ingredient | Prior work |
|---|---|
| affected-operations scope | AOR (Abumaizar & Svestka 1997), mAOR (Subramaniam & Raheja 2003); Sun et al. 2026 on optimization scope |
| insertion repair | Werner & Winkler 1995 |
| CP-based LNS | Shaw 1998; Godard, Laborie & Nuijten 2005 |
| best-of-k incumbents | GRASP; algorithm portfolios |

What remains as a contribution is empirical:
1. an anytime, single-deadline evaluation against **fresh-incumbent** baselines;
2. a stream-level, multi-seed, pre-registered protocol;
3. the finding that a solver hint hurts when it comes from the previous schedule, but helps when it comes from the current history-informed incumbent.

**Open before submission:**
- Sun et al. (2026) has been seen only through a search summary of its abstract and must be read in full.
- A targeted search for CP-SAT / CP Optimizer reactive-scheduling papers with warm starts is still to do.

## 8. Deviations from the pre-registration

All are logged in `04_experimental_methodology.md` §8, and all were made before the confirmatory run:
1. the portfolio was made anytime, which strengthens the comparator;
2. `alpha_rule` was tried on development streams and dropped;
3. the confirmatory comparators changed:
   - portfolio+hinted replaced portfolio+Cold as the control for the selective stage;
   - fresh-portfolio+hinted, the random neighbourhood, and portfolio+Cold vs fresh were added;
   - the family therefore grew to 8.

E6e was added to §6 before it was run.

## 9. Threats to validity

- **Generator.** The development and confirmatory streams come from the same generator, so the configuration is selected for that distribution.
- **Budget.** The baselines' final gaps at 8 s are about 3% with one worker. Part of the gain is better use of a short budget. E6a/E6b test longer budgets and more workers.
- **z\*.** It is the best value found within each campaign, not a proven optimum. Absolute PI values are therefore not comparable across campaigns.
- **Stability.** It is not optimized. IAIP-SR moves 85.9% of surviving operations per step (Cold: 94.7%).
- **Domain.** Job shop only.

## 10. Claim-to-evidence map (revised manuscript `paper/icaps27_iaip/manuscript.tex`)

| Claim in the manuscript | Evidence file | Status |
|---|---|---|
| Floor beats Cold / SPT+Cold / MWKR+Cold by 23.6 / 16.9 / 15.8% (Protocol B) | gate1 `analysis.json` | verified |
| 41–45 of 45 streams under Protocol A | same | verified |
| every hint variant worse (Table 1) | same | verified |
| late-window −12.4% (40/4), final gap −4.8% (27/9) | same | verified |
| arrival breakdown +4.8% (5/40); median initial gap 53.1% vs 15.1% | same | verified |
| 26,325 / 22,000 runs validated; overruns ≤ 0.18 / 0.24 s; p99 0.016–0.017 s | gate1 and confirmatory analysis | verified |
| −43.2% vs Fresh+Cold, 40/40, CI, Holm p | `confirmatory_analysis.json` | verified |
| final gap −38.6% (39/1) | same | verified |
| all seven GO criteria met | same (`go_criteria`) | verified |
| Table 2 (all PI / gap_B / Δ / W/L) | same | verified |
| median gap at 8 s: 1.6 / 2.1% vs 2.5 / 3.6% | `paper/icaps27_iaip/figure_numbers.json` | verified |
| chain 0.0597 → 0.0495 → 0.0443 → 0.0339; 40 / 20 / 40% attribution | `confirmatory_analysis.json` | verified (arithmetic) |
| middle step −10.5% (34/6, p = 8.4e-6) | `supplementary_analysis.json` | verified, not predeclared |
| Fresh+Hint vs Fresh +2.5% (13/27, p = 0.038) | same | verified, not predeclared |
| 1,608 improved / 392 proved-no-better local runs | confirmatory run files (`meta.local`) | verified |
| by-delta reductions | `confirmatory_analysis.json` (`by_delta`) | verified, exploratory |
| stability 85.9 / 91.1 / 94.7% | `supplementary_analysis.json` | verified, exploratory |
| E6 statements | `e6_analysis.json` | pending |
