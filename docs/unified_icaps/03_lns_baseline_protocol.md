# Unified study 03 — LNS baselines and development-pilot protocol

- **Code:** `phase0/critical_region_anytime.py` (method string `crgar|key=value|...`), `phase0/cobar.py` (native-LNS configuration).
- **Tests:** `tests/unified/test_critical_region_anytime.py`.
- **Written:** 2026-10-26, before any pilot of this study ran.

## 1. Baselines

| ID | Method | Category | Method string |
|---|---|---|---|
| B6 | portfolio + hinted global CP-SAT | strong incumbent baseline | `iaip\|portfolio=full\|global_mode=hinted` |
| B0 | IAIP-SR | archived pipeline | `iaip\|portfolio=full\|alpha=0.6\|neighbourhood=N5\|global_mode=hinted` |
| B2 | IAIP-SR + critical-region rounds (CRGAR candidate) | proposed | `crgar\|strategy=crit_expand` |
| B1a | IAIP-SR + random-seed rounds, BFS-expanded; seed count matched | external LNS | `crgar\|strategy=random_bfs` |
| B1b | IAIP-SR + random rounds, \|N\| matched exactly | external analogue of `scheduling_intervals_lns` | `crgar\|strategy=random_matched` |
| B3 | IAIP-SR + time-window rounds, \|N\| matched | external analogue of `scheduling_time_window_lns` | `crgar\|strategy=time_window` |
| B4 | IAIP-SR + random-precedence rounds; released-arc count matched | external analogue of `scheduling_precedences_lns` | `crgar\|strategy=precedence` |
| B5-1w | B6 with `interleave_search` on one worker | **native** CP-SAT LNS. Logs show the 4 scheduling LNS subsolvers active on one thread | `cobar\|neighbourhood=none\|use_certificate=0\|global_certificate=0\|policy=fixed\|global_params=interleave` |
| B5-4w | B6 with 4 workers | **native** CP-SAT LNS (default multi-worker portfolio; 13 interleaved subsolvers in the logs) | `iaip\|portfolio=full\|global_mode=hinted`, `--workers 4` |

**Matching.** Every external control uses the same initial incumbent, initial stage, round policy, local window (α·B), global continuation and worker count as B2.
- Random and time-window controls: same |N| as B2 on the same incumbent, computed in the same round.
- Precedence control: same number of released machine-order relations.

**Recorded per round:**
- \|N\|; released fraction;
- explicit and total released arcs; kept and total machine arcs;
- critical / non-critical operations in N;
- neighbourhood time, model-build time, solver time;
- status;
- objective before and after.

**Native LNS.** Native LNS is compared only under resource-matched settings:
- the 1-worker interleaved configuration against 1-worker external methods;
- the 4-worker default against 4-worker methods.

It is never one-worker vs four-worker. CP-SAT's per-generator selection and difficulty are internal and are not set; see `02_prior_work_and_novelty.md`.

## 2. Critical-region variants (experimental alternatives, not claims)

| Brief ID | Strategy | Seeds / set |
|---|---|---|
| C1 | `crit_onechain_expand` | one longest chain, then 25% BFS |
| C2 | `crit_expand` | all operations on the longest binding chains, then 25% BFS |
| C3 | `crit_blocks_expand` | critical blocks, then 25% BFS |
| C4 | `crit_disr_expand` | chain operations in the forward closure of the disruption set, then 25% BFS |
| C5 | `crit_onehop` | chain operations and their job/machine neighbours |
| — | `crit_chain` | chain operations only |
| C6 | `random_matched` | size-matched random |
| C7 | `time_window` | size-matched time window |

## 3. Protocols

- **M1 (end-to-end).** Up to 9 rounds after the initial stage, inside the window [elapsed, 0.6B]. A round ends at the window end or when CP-SAT proves the restricted problem optimal or infeasible; the loop stops at the first non-improving round. Then hinted global CP-SAT runs until B.
- **M2 (mechanism isolation).** Exactly up to 6 rounds, each limited to 0.4 s, with no stop on failure, inside the same window. Every strategy gets the same round count and the same per-round cap. A round still ends early when its restricted problem is proved, so actual time is recorded and compared.

**Ablations:**

| Brief ID | Configuration |
|---|---|
| A5 | `recompute=0` (neighbourhood computed once) |
| A6 | B2 |
| A7 ≡ A8 | `initial_stage=0` (portfolio + critical rounds + global) |
| A9 | `final_global=0` (rounds use the whole budget) |
| A10 | B5 |

## 4. Development pilots (exploratory)

**Data:** development streams 301–310, 15×15 and 20×20, 10 deltas. **Solver seed 3**, which no earlier pilot on these streams used.

| Pilot | Setting | Methods |
|---|---|---|
| D1 | 8 s, 1 worker, 20 streams | B6, B0, B2, C1, C3, C4, C5, crit_chain, B1a, B1b, B3, B4, B5-1w |
| D2 | 8 s, 1 worker, 20 streams | B0, B2 (M1); B2, B1b, B3, B4 under M2; A5, A7, A9 |
| D3 | 8 s, 4 workers, 10 streams (one process per 4 physical cores) | B5-4w (= B6 with 4 workers), B0, B2, and the best external control of D1 |

**Purpose:**
- verify execution, validity, timing and size matching;
- screen the variants;
- estimate the stream-level SD of the key differences, for power.

Nothing here is a claim.

**Decision rule for the freeze** (written now):
1. The candidate is `crit_expand` unless another critical variant beats it in D1 by more than its bootstrap interval half-width. If several qualify, the simplest is chosen.
2. The confirmatory control set is fixed as B6, B0, B1b, B3, B4 and B5 (B5-1w at 1 worker, B5-4w at 4 workers), whatever their pilot results.

---

## 5. D1 results (8 s, 1 worker, 20 dev streams, solver seed 3; exploratory)

Source: `results/unified_icaps/dev/d1_b8/analysis.json`. 2,860 records, all validated.

Mean PI:

| Method | PI |
|---|---|
| time_window | .0216 |
| crit_onehop | .0226 |
| crit_expand | .0227 |
| crit_disr | .0234 |
| crit_blocks | .0237 |
| crit_onechain | .0270 |
| crit_chain | .0279 |
| random_bfs | .0300 |
| random_matched | .0308 |
| precedence | .0319 |
| B0 | .0322 |
| B6 | .0399 |
| B5-1w | .0410 |

| Comparison | ΔPI | W/L | CI | SD of stream differences |
|---|---|---|---|---|
| crit_expand vs B0 | −29.4% | 19/1 | [−0.0140, −0.0057] | 0.0098 |
| crit_expand vs random_matched | −26.2% | 18/2 | [−0.0118, −0.0045] | 0.0086 |
| crit_expand vs precedence | −28.7% | 17/3 | [−0.0129, −0.0057] | 0.0084 |
| crit_expand vs random_bfs | −24.2% | 17/3 | [−0.0115, −0.0035] | 0.0095 |
| **crit_expand vs time_window** | **+4.9%** | **10/10** | **[−0.0025, +0.0046]** | 0.0084 |
| crit_expand vs B5-1w (native, 1 thread) | −44.5% | 20/0 | [−0.0245, −0.0126] | |
| B5-1w vs B6 | +2.6% | 11/9 | — | — |
| time_window vs B0 | −32.7% | 17/3 | — | — |
| random_matched vs B0 | −4.3% | 10/10 | — | — |
| precedence vs B0 | −1.0% | 9/11 | — | — |

**Variants vs crit_expand:**

| Variant | ΔPI | W/L |
|---|---|---|
| onehop | −0.3% | 11/9 |
| blocks | +4.4% | 7/13 |
| disruption | +3.0% | 10/10 |
| onechain | +18.7% | 5/15 |
| chain-only | +22.9% | 5/15 |

**Size matching held:**
- mean |N| per round: crit_expand 87.8, random_matched 84.8, time_window 85.9;
- mean released machine relations: precedence 81.8 vs crit_expand 87.8.

The small differences come from rounds starting on different incumbents. **Critical operations in N:** crit_expand 39.8, time_window 9.8, random 9.1.

**Reading (exploratory):**
- Critical targeting beats random and precedence neighbourhoods of the same size.
- A *time-window* neighbourhood of the same size, which contains few critical operations, does as well. What these neighbourhoods share is locality in the incumbent's time line, not criticality as such.
- Native single-thread LNS gives no gain over hinted search at 8 s.
- **Freeze rule 1:** no critical variant beats crit_expand by more than its interval half-width, so the candidate remains crit_expand. The time-window control is not a candidate; it is a fixed control.

**Power.** The SD of stream differences between crit_expand and time_window is about 0.0084 with one seed. With 5 seeds averaged and 40 streams, the standard error is about 0.0084/√40 ≈ 0.0013 or less. A difference of about 0.0037 (≈ 17% of the mean PI) is then detectable with 80% power at two-sided α = 0.05, so smaller differences may go undetected. An **equivalence margin** is therefore pre-specified for the confirmation (doc 06).

## 6. D2 results (mechanism protocol M2 and ablations; 20 dev streams, seed 3)

Source: `results/unified_icaps/dev/d2_b8_mech/analysis.json`. 1,980 records, all validated.

**M2** (6 rounds × 0.4 s, no stop on failure):

| Method | PI |
|---|---|
| time_window@M2 | .0191 |
| crit_expand@M2 | .0224 |
| random_matched@M2 | .0277 |
| precedence@M2 | .0283 |

| Comparison | ΔPI | W/L | CI |
|---|---|---|---|
| crit vs random | −19.1% | 16/4 | [−0.0094, −0.0015] |
| crit vs precedence | −20.8% | 17/3 | [−0.0102, −0.0022] |
| **crit vs time window** | **+17.3%** | **6/14** | [−0.0011, +0.0075] |
| time window vs random | −31.0% | 16/4 | [−0.0129, −0.0046] |

Round improvement rate:

| Strategy | Rate |
|---|---|
| crit | 0.34 |
| time window | 0.38 |
| random | 0.28 |
| precedence | 0.19 |

Mean \|N\| is 81.5 for all three N-based strategies; precedence releases 81.6 arcs.

**Ablations** (M1), relative to crit_expand:

| Ablation | ΔPI | W/L | Verdict |
|---|---|---|---|
| neighbourhood computed once | +40.2% | 4/16 | recomputation matters |
| no initial IAIP-SR stage | +28.2% | 4/16 | the initial stage matters |
| no final global stage | +119.2% | 1/19 | the global continuation is essential |
| M2 vs M1 | +11.2% | 8/12 | not significant |

## 7. D3 results (4 workers, native CP-SAT LNS active; 10 dev streams, seed 3)

Source: `results/unified_icaps/dev/d3_w4/analysis.json`.

| Comparison | ΔPI | W/L | CI |
|---|---|---|---|
| crit vs B6-4w (native LNS) | −29.3% | 7/3 | [−0.0091, −0.0009] |
| crit vs B0 | −15.9% | 4/6 | [−0.0063, +0.0013] |
| crit vs time window | −7.9% | 5/5 | [−0.0040, +0.0022] |
| time window vs B6 | −23.2% | 7/3 | — |

## 8. Development conclusion (before freezing)

- Critical targeting beats size-matched random and precedence neighbourhoods. Time-window neighbourhoods of the same size match or beat it, with one worker (M1 +4.9%, M2 +17.3%; both CIs include 0).
- Recomputing the region every round, the initial stage and the global continuation each matter.
- With 4 workers, the pipeline with rounds is ahead of CP-SAT's native multi-worker LNS, on small samples.
- **Expected verdict, if confirmation agrees:** CONDITIONAL GO, i.e. no superiority claim for critical targeting over time-window LNS. This is written down before the confirmatory run so that it cannot be adjusted afterwards.
