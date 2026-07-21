# Implementation Plan: boot_cold — Full ICAPS Technical Paper

Prepared 2026-07-11. Supersedes the "workshop-viable" framing from the prior
assessment. This plan closes the seven gaps identified between the current
pilot-scale work and an ICAPS technical-track submission:
(1) scale, (2) figures, (3) real benchmark instances, (4) RCPSP at real
scale, (5) ICAPS-appropriate related work, (6) literature-SOTA baseline
comparison, (7) an actual paper draft.

## Progress log (updated as phases complete)

**2026-07-11, same-day implementation pass:**
- **C.0 (parallelize runner) — DONE.** `run_icaps_jssp_suite.py` now has
  `--parallel N` (multiprocessing at stream-config granularity). Measured
  ~4x speedup on 8 workers; verified output structurally/numerically
  identical to sequential (new tests in `tests/test_icaps_runner_parallel.py`).
  Also added **incremental checkpointing** (write-temp-then-rename after
  every completed config) — a crash mid-campaign now loses at most the
  in-flight configs, not the whole run; verified via a kill-mid-run +
  `--resume --skip-existing` test.
- **Reproducibility bug fixed**: `dispatch_mwkr`'s tie-breaking was
  `PYTHONHASHSEED`-dependent (fell back to set-iteration order over string
  job-ids). Fixed with a deterministic tie-break; added a subprocess-based
  regression test varying the hash seed. Full suite: **98 fast tests pass**
  (10 additional `slow`-marked tests for real-benchmark validation, see below).
- **C.1 (main comparison table)**: `paper_main` preset added (3 sizes x 15
  seeds x 10 methods, 450 stream-runs) and **launched in the background**
  with `--parallel 16` (`scripts/run_icaps_paper_main.sh`, log at
  `logs/paper_main.log`) — see current status in the CSV/metadata once complete.
- **Phase A (related work) — first pass done.** Added §2.2 to
  `BOOT_COLD_PAPER.md`: positions boot_cold against match-up scheduling
  (Bean/Birge/Mittenthal/Noon 1991), Herroelen & Leus's robust/reactive
  project scheduling line, and — most importantly — the **MIP Workshop 2023
  Reoptimization Competition** (arXiv:2311.14834), the closest adjacent
  work (same problem shape: a stream of instances differing by small input
  changes, solved under time pressure, reusing prior-solve information) but
  general-MILP and solver-internals-focused (branching history, parameter
  tuning) rather than a black-box, provably-safe floor mechanism. TODO before
  submission: full-text (not just abstract) verification of that competition
  paper's claims, since only abstracts were fetchable this pass.
- **Phase B (real benchmark instances) — first pass done.** Fetched OR-Library's
  `jobshop1.txt` (network access confirmed working), extracted 10 classic
  instances (ft06, ft10, ft20, la01-la05, abz5, abz6) into
  `tests/fixtures/benchmarks_real/` with `PROVENANCE.md`. **Validated all
  10/10 against their exact published optimal makespans** via CP-SAT +
  independent solution validation — the strongest possible correctness
  check for `benchmark_loaders.py`, previously untested against real files.
  Added as a permanent `slow`-marked regression test (`pytest.ini` added to
  keep the default fast-suite run excluding it; run explicitly with
  `-m slow`). Also **wired the previously-dead `--benchmark-dir`/
  `--benchmark-file` CLI flags** into the actual run loop (they were defined
  but never used) so real instances can now flow through the full suite via
  `generate_stream(base_instance=...)`, dry-run verified.
**2026-07-11, continued (same day, second pass):**
- **`paper_main` (C.1) completed**: 450/450 stream-runs, 4950 rows, **0 errors, 100% feasible, 0 duplicates** — verified structurally correct. Fresh independent confirmation of the core claim on this new data alone: boot_cold beats cpsat_cold on PI in 78.8% of instances (n=495, sign_p=1.44e-39).
- **Correctness audit performed** (explicitly requested by user: "verify whether the implementations are correct or not"). Found and fixed a **real, load-bearing bug**: `sign_test()` in `phase0/analyze_icaps_results.py` used `2 ** n` where `n` could be a `numpy.int64` — numpy's fixed-width integer silently overflows on `2 ** n` for n>63 (wraps instead of raising), corrupting the p-value (a 27/136 split returned `sign_p=1.0` instead of the true ~1e-18). **Confirmed this did NOT corrupt any previously generated report/table**: the one production call site (`pairwise_vs_baseline`) already explicit-casts `int(...)` before calling `sign_test`, so historical outputs are safe — but the function was hardened with an internal cast anyway (defense in depth, since the safety was accidental/caller-dependent, not by design). Added `tests/test_analyze_icaps_results.py` (20 tests, previously **zero** coverage for this module despite it computing every p-value in the project) — includes a direct cross-check against `scipy.stats.binomtest` (scipy was pip-installed this pass; Wilcoxon now actually computes instead of always skipping).
- **Refined the domination-guarantee correction numbers** with the larger post-paper_main pooled dataset (n=1007, up from n=508): 111/1007 losses (11.0%, down from 12.4%) vs an independently-run `cpsat_cold`, median excess 0.60%, max 3.63%. PI headline updated to n=1007: 82.5% win rate, confirmed by BOTH sign test (p≈2.7e-102) and Wilcoxon (p≈9.3e-98) agreeing. Propagated to `BOOT_COLD_PAPER.md` (abstract, §2.2, §3.3, §8), `README_ICAPS_EXPERIMENTS.md`, and the auto-generated `report.md` template in `analyze_icaps_results.py` (so future regenerations don't regress the language).
- **Phase B launched for real**: `real_benchmarks` preset (60 configs, 240 stream-runs, 10 real instances x 6 seeds x 4 methods) running in background via `scripts/run_icaps_real_benchmarks.sh --parallel 8`; checkpointing verified working in production (partial CSV growing correctly, 100% feasible so far).
- **Phase D launched**: RCPSP real-scale run (60 activities, 3 resources, capacity 4-6 — confirmed non-trivial via a smoke check first, not proving instantly), 10 seeds split across 2 background batches (`results/icaps/rcpsp/rcpsp_seeds{1_5,6_10}.csv`).
- **Verified `primal_integral`'s monotonicity enforcement is correct and consistent** across both JSSP (`harness.py::warm_bootstrap_solve`) and RCPSP (`rcpsp/harness.py`) — both independently implement the same running-min "pocket" merge over the bootstrap floor point + solver trajectory, confirmed by direct code comparison. Scanned the codebase for other instances of the same numpy-overflow pattern (`2 ** n`-style) — none found elsewhere.
- **Not yet done**: Phase D analysis once RCPSP batches finish; Phase B analysis once `real_benchmarks` finishes; Phase E (new anytime-curve figure specifically, beyond the 4 plot types already in `make_plots`); Phase F (paper draft).

**2026-07-11, third pass (Phases D/B analysis, E, F all completed):**
- **RCPSP (Phase D) analyzed**: 90 instances, 80/80 stream-instance PI wins (p=1.65e-24, 72.3% mean improvement), 0 final-objective losses. Cross-domain finding: RCPSP's additive delta `activity_insertion` is NOT a weak case (56% improvement) unlike job-shop arrivals — additive-delta difficulty is floor-policy-specific, not delta-type-inherent. Written into `BOOT_COLD_PAPER.md` §5.4.
- **Real benchmarks (Phase B) analyzed**: 240 stream-runs on 10 real OR-Library instances, 89.3% PI win rate (n=540, p=3.4e-84) — slightly stronger than synthetic, directly closing the "only synthetic instances" gap. Written into §8.
- **Final pooled headline (n=1547, all 6 JSSP experiments incl. real benchmarks)**: 84.9% PI win rate, sign p≈4.1e-182 AND Wilcoxon p≈1.6e-152 (agree). Final-objective non-loss vs independent cpsat_cold 92.4% (117/1547 losses, median 0.63%, max 3.63%). Verified 9306 total solved rows are 100% feasible, 0 errors (independent validation of every solution).
- **Phase E (figures) DONE**: wrote `phase0/make_paper_figures.py` (two-step: `capture` trajectories on a held-out grid since CSVs store only summary stats, then `plot`). Generated 6 paper figures incl. the flagship **anytime-curve** figure (median gap-vs-time, IQR band) — visually verified: on 20x20, boot_cold reaches gap≈0.05 at t≈0 via the ~1ms floor while cpsat_cold sits at ≈0.11 and takes ~3s to catch up; cpsat_warm is visibly worse early (hint slows CP-SAT's initial trajectory). y-axis zoomed to the informative region (all methods start at gap=1). `scripts/make_paper_figures.sh` wraps both steps.
- **Phase F (paper draft) DONE**: `paper/boot_cold_icaps.tex` — a complete ICAPS technical-track LaTeX draft (abstract, intro, reactive-scheduling related work, problem formulation, method + domination theorem/proof, experimental setup, results with main table + 3 figures, robustness negative result, limitations, conclusion, embedded bibliography). Compiles with standard `article` class (self-contained; documented `% AAAI-SWAP` markers for the official AAAI/ICAPS class). Structurally validated (balanced envs/braces, all \\ref/\\cite defined, table rows end in \\, all referenced figures exist). All numbers cross-checked against the CSVs. `paper/README.md` documents build + submission-conversion steps.

**Remaining before actual submission** (not blocking, documented in `paper/README.md`): full-text verification of the MIP Workshop 2023 competition citation; swap in official AAAI class + convert bib to .bib; author/affiliation block; optionally restore 30x20 size to main table.

---

## 0. What "done" looks like

A submittable PDF with: a related-work section that cites and positions
against the reactive/dynamic-scheduling literature (not just the ML-CO
literature already covered in `BOOT_COLD_PAPER.md`); a main results table
at real scale (tens of seeds, multiple standard instance sizes, at least
one real benchmark-derived size class); a budget-sensitivity and a
worker-sensitivity study at a scale that supports the confidence intervals
reported; an RCPSP cross-domain result at more than smoke-test scale; real
figures; and a comparison against at least one baseline traceable to
published reactive-scheduling work, not only self-designed OR baselines.

---

## Phase A — Related work & positioning (do first, cheap, de-risks everything else)

**Why first:** if the reactive-scheduling literature already has a method
structurally similar to boot_cold's pocket/floor mechanism, that reshapes
the contribution claim before any more compute is spent. Cheap to check,
expensive to discover late.

**Actions:**
1. Literature search (I have `WebSearch`/`WebFetch` available and will run
   this directly, not ask you to do it): match-up scheduling (Bean et al.),
   right-shift repair, classic reactive/dynamic scheduling surveys (Ouelhadj
   & Petrovic 2009 is the standard one; Vieira, Herroelen & Leus 2003 for
   RCPSP reoptimization specifically), schedule stability/robustness
   literature (Herroelen & Leus), and recent (2023-2026) dynamic job-shop
   rescheduling papers to check nothing already claims this exact mechanism.
2. Write the ICAPS-flavored related-work section as a new subsection in
   `BOOT_COLD_PAPER.md` (or the paper draft directly, see Phase F) —
   positioning against reactive scheduling methods, not just BALANS/lot-sizing.
3. **Decision gate:** if a near-identical mechanism turns up, the paper's
   contribution claim shifts to "first formal domination guarantee + first
   application to CP-SAT + the largest-scale empirical validation," which
   is still a real contribution but changes the abstract/intro framing.
   Flag this back before Phase F.

**Deliverable:** related-work section, draft.
**Estimated effort:** a few hours, no compute.

---

## Phase B — Real benchmark instances

**Why:** `benchmark_loaders.py` exists and is unit-tested but has never
touched a real published instance — a reviewer will ask why a paper about
job-shop scheduling has no OR-Library/Taillard results.

**Actions:**
1. Fetch a small set of standard instances (I now have network access,
   confirmed working this session) — Taillard's `ta01`-`ta10` (15x15) and a
   few OR-Library classics (`ft06`, `ft10`, `la01`-`la05`) as a starting set.
2. Validate each against `benchmark_loaders.py`'s existing loader; fix
   format edge cases as they appear (the loader was only tested against
   synthetic fixtures — expect at least minor format surprises).
3. Turn each static instance into a stream via
   `generate_stream(cfg, base_instance=...)` (already implemented) with the
   standard mixed delta profile, at a handful of seeds each (deltas are
   randomized on top of the fixed base, so seed = which delta sequence, not
   a different base instance).
4. Add one results table specifically on these real instances, matching the
   synthetic-stream tables' schema so it drops into the same analysis
   pipeline unchanged.

**Deliverable:** `tests/fixtures/taillard/` (or similar) with real instance
files + provenance notes (source URL, retrieval date), one additional
results table.
**Estimated effort:** ~1-2 hours setup, then folds into Phase C's compute budget.

---

## Phase C — Scaled experimental campaign (the core of this plan)

### C.0 — Parallelize the runner first (prerequisite, changes the whole budget)

**This is the highest-leverage single change available.** The current
`run_icaps_jssp_suite.py` runs every stream-method job strictly
sequentially. Every experiment so far used `workers=1` CP-SAT calls, and
this machine has **20 cores** — meaning up to ~18-20 independent
single-threaded jobs (leaving headroom for the OS) could run concurrently
with zero contention, since CP-SAT workers=1 jobs don't share state.

**Action:** add a `--parallel N` flag using `multiprocessing.Pool` at the
stream-config granularity (one process per (size, seed, budget, workers,
severity, bootstrap_policy) combination, each running its own methods
sequentially within the process — safe because each combination already
writes independent rows, and the existing best_known computation is
already scoped per-stream so it doesn't need cross-process coordination).
For `workers>1` CP-SAT calls specifically, cap concurrent jobs so
`sum(workers across concurrent jobs) <= ~18` to avoid oversubscription.

**Expected impact:** the estimates below assume 12-16x parallelism (leaving
margin for workers>1 jobs), turning what would be a ~7-37 hour sequential
run into roughly **30 min - 3 hours** depending on the exact grid.

**This must be tested for correctness before trusting its output** — add a
regression test that a `--parallel 4` run and a `--parallel 1` run on the
same small grid produce identical CSVs (mod row order and metadata
timestamps), since silent cross-process corruption would be worse than the
slower sequential baseline.

### C.1 — Main comparison table (redesigned, not the original oversized "main" preset)

The original `main` preset was a full factorial (4 sizes × 30 seeds × 4
budgets × 2 worker counts × 10 methods × 20-instance streams = 28,800
stream-runs, ~15-31 hours even before considering the redundancy of sweeping
every axis simultaneously). That design is both too expensive and
statistically inefficient — better practice, and what we already did
opportunistically across pilot/workers/arrivals, is **one fixed-condition
main table plus separate targeted sensitivity studies per axis**, holding
the others at a sensible default. Formalizing that:

- **Sizes:** 10x10, 15x15, 20x20 (drop 30x20 from the main table; it's the
  most expensive and least essential for demonstrating the core effect —
  revisit only if reviewers ask or compute allows after everything else).
- **Seeds:** 15 (up from pilot's 3 — a real jump in statistical power
  without the original preset's 30-seed cost).
- **Stream length:** 10 (11 instances/stream, matching what `workers`/
  `arrivals` already used).
- **Budget:** single representative value (8s — matches `workers`'s longer
  budget, which showed the cleanest signal).
- **Workers:** 1 (the `workers` study already covers 1/4/8/16 separately).
- **Methods:** `cpsat_cold, cpsat_warm, boot_cold, boot_warm, repair_only,
  dispatch_spt, dispatch_mwkr, fix_and_optimize_50, lns_prev_solution,
  local_branching_prev` (10 methods — the full comparison set minus the
  clearly-dominated `dispatch_lpt/fifo/random` and redundant freeze
  fractions, which stay available for an appendix ablation if reviewers want it).
- **Delta mix:** the default weighted mix (all 10 delta kinds available,
  matching real deployment rather than isolating one type).

Sequential estimate: 3 sizes × 15 seeds × 11 instances × 7 CP-SAT-heavy
methods × 8s ≈ 7.1 hours. **With C.0's parallelization (~14x): ~30 min.**

### C.2 — Budget-sensitivity study (scale up from what's implied by pilot)

Sizes: 15x15 only. Seeds: 10. Budgets: 0.5, 2, 5, 10, 20 (5 levels — wider
than pilot's 3). Methods: `cpsat_cold, cpsat_warm, boot_cold, boot_warm`
(the 4 that matter for this specific question). Stream length: 8.

Sequential estimate: 1 × 10 × 9 × 4 × (0.5+2+5+10+20) ≈ 34,200s ≈ 9.5h.
**Parallelized: ~45 min.**

### C.3 — Worker-sensitivity study (extend the existing pilot-scale result)

Already have n=24/level from the earlier scaled run. Extend to n=60/level
for the paper: sizes 15x15+20x20, seeds 11-20 (10 seeds), budgets [2, 8],
workers [1,4,8,16], methods `cpsat_cold, cpsat_warm, boot_cold, boot_warm`.

Sequential estimate: 2 × 10 × 9 × 4 workers-values × 4 methods ×
(2+8) ≈ 57,600s ≈ 16h. **Parallelized (mind the workers>1 oversubscription
cap from C.0): ~2-3h.**

### C.4 — Arrivals / bootstrap-policy study (extend existing 864-row result)

Already solid at n=64-72/condition. Widen seeds from 2 to 6 for tighter
confidence intervals on the boot_cold vs boot_warm policy-interaction
finding specifically (that finding is publication-relevant and currently
sits on a modest sample). Sizes: 15x15 only (matches what's already run,
keeps this comparable). Same delta kinds/severities/policies as before.

Sequential estimate: ~3x the existing run's cost ≈ 3-4h. **Parallelized: ~20 min.**

### C.5 — Real-benchmark-instance results (Phase B's output, run through the same pipeline)

Small, fixed cost given Phase B's instance count — folds into the same
parallelized infrastructure, budget ~15 min.

**Phase C total estimated wall-clock with parallelization: ~4-5 hours**,
realistically run overnight or across a couple of background sessions
rather than one sitting.

---

## Phase D — RCPSP at real scale

Mirror C.1's design for the RCPSP domain: 3 activity-count classes (e.g.
20, 40, 60 activities), 10 seeds each, stream_length 8, methods
`cpsat_cold, boot_cold` at minimum (the two that matter for the
cross-domain claim), one representative budget. This is new infrastructure
work too: `run_rcpsp_test.py` currently only supports a `cpsat_cold` vs
`boot_cold` comparison with no CSV-schema alignment to the JSSP suite's
unified format — worth a small refactor so RCPSP results drop into the
same `analyze_icaps_results.py` pipeline rather than needing separate
analysis code.

**Deliverable:** RCPSP results at real scale, in the unified schema.
**Estimated effort:** ~2h refactor + ~1h parallelized compute.

---

## Phase E — Analysis, figures, tables

matplotlib is now installed (confirmed working this session — previously
every prior report generated with an empty `figures/` directory). Specific
figures needed for a paper, not just "some plots":

1. **Anytime curves** (median relative gap vs. time, with a confidence
   band) — one per instance size, boot_cold vs cpsat_cold vs cpsat_warm —
   this is the single most important figure for the paper's core claim.
2. **PI improvement vs. instance size** — does the effect grow, shrink, or
   hold as problems get larger? (Not yet known — this is a real open
   question C.1's 3-size sweep answers for the first time.)
3. **Worker-scaling curve** — PI improvement (%) vs. workers, extending
   the existing 4-point curve to n=60/level (C.3).
4. **Budget-sensitivity curve** — PI improvement vs. budget (C.2), the
   "real-time replanning" story figure.
5. **Severity × delta-kind heatmap** — already coded in
   `analyze_icaps_results.py::make_plots`, just needs real data at scale.
6. **Bootstrap-policy comparison** (boot_cold vs boot_warm × 4 policies) —
   makes the Phase-3 nuanced finding (policy helps boot_cold reliably-but-
   small, helps boot_warm unreliably-but-large) visually legible, since
   that finding is subtle enough that a table alone undersells it.
7. **RCPSP cross-domain summary** — same shape as the JSSP main table, to
   visually reinforce "this transfers."

**Deliverable:** `results/icaps/figures/*.pdf`, populated LaTeX tables.
**Estimated effort:** ~1 day once Phase C/D data exists (mostly automated
via the existing `analyze_icaps_results.py`, but each figure above needs a
dedicated function beyond what's currently stubbed in).

---

## Phase F — Paper draft

**Structure** (standard ICAPS technical-track shape):

1. Abstract — depends on Phase C's actual numbers, write last.
2. Introduction — streaming reoptimization framing, the "cold solving
   ignores history" problem, headline claim.
3. Related Work — Phase A's output: reactive/dynamic scheduling literature
   + the existing ML-CO positioning (BALANS, lot-sizing GNN) as secondary.
4. Problem Formulation — the stream model, delta taxonomy, primal-integral
   metric definition (all already precisely specified in the codebase;
   this section is mostly transcription + formalization).
5. Method — the bootstrap construction + pocket mechanism + **the
   domination-guarantee theorem and proof** (already written informally in
   `BOOT_COLD_PAPER.md` §3.3; needs tightening into theorem/proof form).
6. Experimental Setup — domains, fairness protocol, baseline menu (19
   methods — genuinely thorough, a strength to lead with), metrics.
7. Results — Phase C/D/E's output: main table, sensitivity studies,
   robustness-to-learned-alternatives finding (the three failed sophisticated
   attempts — real, citable negative-result evidence), cross-domain (knapsack
   + RCPSP), real-benchmark-instance results.
8. Discussion / Limitations — honest: final-quality ties (not
   improvements) by design; arrival-delta weak case and the partial fix;
   boot_warm's context-dependent instability (single-thread arrival-heavy
   losses vs. multi-worker wins) — this nuance is a genuine finding, not
   a weakness to hide.
9. Conclusion.

**What I can draft now, before Phase C completes:** §3 (Method + theorem),
§4 (Problem Formulation), §6 (Experimental Setup) — all fully determined by
existing code, not by not-yet-run experiments. I'd recommend drafting these
in parallel with Phase C's compute running in the background, not
sequentially after.

**What needs Phase C/D/E's actual numbers first:** §1 (Abstract), §2
(Introduction's quantitative claims), §7 (Results), most of §8.

**Template:** ICAPS uses an AAAI-derived LaTeX class distributed from the
submission site closer to the deadline (not yet available generically) —
I'll set up a placeholder document class now and swap in the official one
when you have it, so drafting isn't blocked on that.

---

## Timeline (phase-based; see open questions below for calendar mapping)

| Phase | Depends on | Est. effort |
|---|---|---|
| A — Related work | nothing | few hours, no compute |
| B — Benchmark instances | network access (have it) | 1-2h |
| C.0 — Parallelize runner | nothing | ~2-3h build + correctness test |
| C.1-C.5 — Scaled campaign | C.0 | ~4-5h wall-clock (parallelized), spread over background runs |
| D — RCPSP at scale | C.0 (shared infra) | ~3h |
| E — Figures/tables | C, D data | ~1 day |
| F — Paper draft (partial) | A (for related work) | can start immediately, in parallel with C |
| F — Paper draft (complete) | C, D, E | after all above |

**Critical path:** C.0 (parallelization) blocks everything in C/D from being
fast rather than slow — build and correctness-test this first.

---

## Risks and decision gates

- **Gate after C.1:** if the PI-improvement-vs-size curve shows the effect
  meaningfully shrinking at 20x20 vs 10x10, that's a real finding to report
  honestly (not to bury), and may argue for extending C.1 to 30x20 after
  all before finalizing the abstract's headline number.
- **Gate after Phase A:** if closely-related reactive-scheduling work
  exists, reframe the contribution claim before drafting §1-2.
- **Parallelization correctness is load-bearing** — a silent bug here
  would invalidate every subsequent number. Build the identical-output
  regression test in C.0 before trusting any C.1-C.5 result.
- **Real benchmark instances (Phase B) may not convert cleanly** — the
  loader has only seen synthetic fixtures; expect to spend real time on
  format edge cases, not just a fetch-and-go.

---

## Open questions (need your input, not something I can infer)

1. **Deadline / timeline.** No ICAPS deadline is on record in this
   project. The phase estimates above are effort-based, not calendar-based
   — I need a target date to turn this into a schedule with margin, and to
   decide how aggressively to parallelize/prioritize (e.g., whether C.1's
   3-size/15-seed design is right, or whether a tighter deadline means
   trimming further, or a looser one means restoring the 30x20 size and
   full seed count).
2. **Compute budget.** Is this single 20-core machine the only resource for
   Phase C/D, or is there access to more hardware (cloud, cluster) that
   would change the parallelization ceiling and let the original
   full-scale grids run directly instead of the trimmed C.1-C.4 design?
3. **Do you want me to start Phase A (literature search) and C.0
   (parallelization) now**, since both are deadline-independent and
   unblock everything else, while we settle the calendar question?
