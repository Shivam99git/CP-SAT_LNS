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
