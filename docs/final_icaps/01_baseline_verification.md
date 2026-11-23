# Final-phase 01 — Baseline verification (Phase 1)

- **Branch:** `research/icaps2027-final-empirical`, created from `research/icaps-unified-critical-rounds` at `4761b79`. All prior branches (`main`, `research/iaip-sr`, `research/cobar-certificate-guided`, `research/icaps-unified-critical-rounds`) preserved untouched. Nothing pushed.
- **Independent verification script:** `scripts/final/verify_unified_confirmatory.py`, reusing (not duplicating) the zero-shared-code checker from `scripts/unified/verify_baseline.py` (own instance reader, own feasibility checker, own PI integrator, own sign test/Holm/bootstrap — none of it is `phase0.analyze_*`).
- **Full output:** `results/final_icaps/unified_confirmatory_independent_verification.json`.

## 1.3: Independent reproduction of every headline comparison

All 9 confirmatory settings (U1-U9) were re-verified from the raw run files, with a tool that has never executed and shares no logic with the original analysis path.

| Setting | Records | Infeasible (own check) | Objective mismatch | Checksum mismatches |
|---|---|---|---|---|
| U1_primary | 15,400 | 0 | 0 | 0/200 |
| U2_mechanism | 8,800 | 0 | 0 | 0/200 |
| U3_workers4 | 4,400 | 0 | 0 | 0/100 |
| U4_b2 | 8,800 | 0 | 0 | 0/200 |
| U5_b30 | 2,640 | 0 | 0 | 0/60 |
| U6_arrival | 4,400 | 0 | 0 | 0/100 |
| U7_outage | 4,400 | 0 | 0 | 0/100 |
| U8_high | 4,400 | 0 | 0 | 0/100 |
| U9_benchmarks | 7,480 | 0 | 0 | 0/170 |
| **TOTAL** | **60,720** | **0** | **0** | **0/1230** |

**Correction found and fixed:** the prior-stage `FINAL_SUBMISSION_RESEARCH_REPORT.md` and `06_statistical_results.md` stated "46,720 records." Independent summation of the actual per-setting record counts (verified both from this fresh reconciliation and from the original `confirmatory_analysis.json`, which agree) gives **60,720**. This was a hand-arithmetic error, not a data problem — the per-setting counts (and every downstream statistical result) were always correct; only the grand total sentence was wrong. Fixed in both documents and in the project memory file. The manuscript itself was unaffected: it never hardcoded the grand total, using only per-setting macros (`\UOneRecords`, etc.), confirmed by direct grep of `manuscript.tex`.

### All six headline comparisons, independently recomputed

| Comparison | Reported | Independently recomputed | Agreement |
|---|---|---|---|
| Critical rounds vs IAIP-SR (B2 vs B0, U1) | -22.4% | -22.4% | rel-diff error 0.0, W/L identical (35/5), Holm p identical (8.3e-6) |
| vs size-matched random rounds (B2 vs B1) | -20.4% | -20.4% | error 5.6e-17, 35/5, 8.3e-6 |
| vs random-precedence rounds (B2 vs B4) | -24.5% | -24.5% | error 5.6e-17, 34/6, 3.3e-5 |
| vs native single-thread search (B2 vs B5) | -43.8% | -43.8% | error 5.6e-17, 40/0, 1.5e-11 |
| vs size-matched time-window rounds (B2 vs B3) | -6.1%, not significant | -6.1%, not significant | error 3.5e-17, 26/14, Holm 0.16 |
| vs native four-worker search (B2 vs B6, U3) | -9.1%, not significant | -9.1%, not significant | error 1.4e-17, 15/5, Holm 0.12 |

Every relative-difference error is floating-point rounding (<1.2e-16); every W/L count and every Holm-adjusted p-value is bit-identical; every bootstrap CI matches within Monte-Carlo noise (<1.5e-4, expected from an independently-seeded resampling). **Sign convention checked:** the independent script computes `(a - b) / mean(b)` matching the archived `rel_diff` definition in `phase0/analyze_gate1.py::compare`; both report a negative sign as "first method (candidate) better," consistent throughout.

## Stream/seed relationship (explicitly checked, per instruction)

| Setting | Physical streams | Distinct `stream_seed` values | Sizes | Seeds shared across sizes? |
|---|---|---|---|---|
| U1, U2, U4 | 40 | 20 (1101-1120) | 15x15, 20x20 | yes |
| U3, U6, U7, U8 | 20 | 10 (1101-1110) | 15x15, 20x20 | yes |
| U5 | 20 | 10 (1101-1110) | 15x15, 20x20 | yes |
| U9 | 34 | 1 (1101, single stream seed) | 4 distinct base-instance shapes (10x20, 15x15, 15x20, 20x20, from Taillard/DMU/SWV/YN) | n/a (unit is the base instance, not the seed) |

**Finding: 40 = 2 sizes x 20 stream seeds, not 40 independent seed values.** Seed numbers ARE reused across sizes (seed 1101 backs both a `15x15_s1101` stream and a `20x20_s1101` stream). This does **not** create a statistical-independence violation: `phase0/streams.py::generate_stream` seeds one `random.Random(cfg.seed)` instance per call, but `num_machines`/`ops_per_job`/`duration_range` differ by size, so every size-dependent random draw diverges between the two streams from the very first call; the two streams are genuinely different physical instance sequences. Critically, **no analysis anywhere treats the bare seed number as the unit** — every `stream_tab`/`unit_tab` groupby in the codebase keys on the full stream identifier (`"15x15_s1101"`, a unique string per size-seed pair), and the archived frozen protocol's unit of inference was always declared as "the stream," which is this full identifier. This is verified directly by inspecting `phase0/analyze_cobar.py::unit_tab` and `phase0/analyze_unified.py::role`/`analyze` (grouping is always on the `stream` column, never on `stream_seed` alone). No correction was needed; the finding is recorded because the brief asked for it to be checked explicitly, and it had not previously been stated this plainly.

## 1.4: Test suite results

| Suite | Run 1 | Run 2 | Run 3 (isolated) |
|---|---|---|---|
| fast (269 tests) | **268 passed, 1 failed** | 269 passed | `test_checkpoint_partial_progress_then_resume_completes` alone: passed |
| slow (25 tests) | 25 passed | — | — |

**One genuine failure recorded, not hidden.** `tests/test_icaps_runner_parallel.py::test_checkpoint_partial_progress_then_resume_completes` failed on the first full-suite run of this session and passed on an immediate full-suite rerun and in isolation. Root-cause analysis: the test hard-codes `subprocess.run(..., timeout=2)` to interrupt a real CP-SAT campaign mid-run and asserts `0 < len(partial) < 3*6*4` rows were checkpointed before the kill (`tests/test_icaps_runner_parallel.py:88-95`). This is a wall-clock race: under transient system load (expected after days of continuous solver campaigns on this machine), the 2-second window can complete faster or slower than the reference timing the test's bounds assume, producing 0 or all rows instead of a partial count. This is:
- **pre-existing** (the test predates every stage of this project's own code; it exercises `phase0.run_icaps_jssp_suite`, the original archived ICAPS campaign runner, never touched by Floor/IAIP-SR/COBAR/unified work);
- **unrelated to any claim in this study** (no method, baseline, or result in this manuscript depends on `run_icaps_jssp_suite`'s checkpoint/resume behaviour);
- **not a correctness defect in the system under test** — a real crash-and-resume integration test of this kind is inherently timing-sensitive, and the underlying checkpoint/resume mechanism itself is separately, non-flakily verified by `tests/unified/test_critical_region_anytime.py::test_campaign_resume_skips_finished_tasks_and_keeps_files` (deterministic: lets the campaign finish, then checks a second invocation does no redundant work and produces a byte-identical file — no race condition, and this test passed in every run of this phase).

This is reported honestly as a flaky pre-existing test, not silently re-run until green and not labeled as a blocking failure of anything this study claims.

## 1.5: The outstanding manuscript-audit check, resolved

The prior-stage audit (`docs/unified_icaps/07_manuscript_audit.md`) found 11/12 checks PASS and one, **#9 Bibliographic completeness**, marked "PASS-with-disclosure": the full texts of Sun et al. (2026) and Lin & Yang (2026) were inaccessible.

**Re-attempted via legitimate routes** (no access-control bypass): the DOI resolver's actual redirect target (`linkinghub.elsevier.com`), a direct fetch of that target, and a targeted search for an author-posted or aggregator-hosted copy (ResearchGate, specifically). Result: the DOI redirect leads only to a paywalled publisher page ("Redirecting" with no visible content); no arXiv preprint, no author-hosted PDF, and no ResearchGate full-text copy of this specific paper exists (ResearchGate search returned only unrelated papers by a possibly-different "Mingqi Yang" in related-work sidebars, explicitly not the target paper).

**Conclusion: not resolvable with available evidence.** This is a correctness/access limitation, not fixable from this environment (no institutional subscription or Elsevier TDM API key is available). It is **not** silently converted into a pass; the manuscript's Related Work and Limitations sections already state plainly that both papers are read only via their abstracts, and this document records the specific, concrete access attempts made, so a human author with institutional access can complete this check before actual submission. **This does not change any numerical claim** in the manuscript — no result depends on the content of either paper, only the related-work positioning does, and that positioning is already hedged (no claim of "first" or "novel" relative to either).

## Summary

- 60,720 confirmatory records independently reconciled, 0 discrepancies with the archived analysis beyond the one hand-arithmetic total error (now fixed), 0 feasibility violations, 0 checksum mismatches.
- Stream/seed relationship explicitly verified: 40/20/34 physical units are correctly constructed and correctly treated as the unit of inference throughout.
- 269/269 fast and 25/25 slow tests pass on a clean run; one pre-existing, unrelated, timing-sensitive test flaked once and is documented rather than hidden.
- The one remaining manuscript-audit gap (full-text access to two related papers) was re-attempted, found genuinely unresolvable from this environment, and is explicitly flagged for a human author with institutional access rather than silently waived.
