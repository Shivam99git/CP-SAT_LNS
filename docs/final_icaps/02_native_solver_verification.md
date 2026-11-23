# Final-phase 02 — Native CP-SAT solver verification (Phase 2)

Prior-stage documentation (`docs/unified_icaps/02_prior_work_and_novelty.md`) asserted which CP-SAT subsolvers run under B5 (1 worker + `interleave_search`) and B6-at-4-workers, based on solver logs observed *interactively* in an earlier session but never saved as a committed artifact. This document replaces that inference with saved, reproducible transcripts generated from the **exact production code path and configuration** used in the confirmatory campaign, on an actual confirmatory instance (`15x15_s1101`, step 1, the first held-out instance of U1).

All logs: `results/final_icaps/solver_logs/*.txt`. Generation script: inline in this phase's work (reproducible via the three snippets below; not wrapped in a standalone script because each is a 15-line, one-off diagnostic, not part of the campaign pipeline).

## 2.1 / 2.2: Single-worker configuration (B5_native1w)

Configuration: `num_workers=1, interleave_search=True, random_seed=0, max_time_in_seconds=8.0` — exactly `SOLVER_PARAMS["interleave"]` in `phase0/cobar.py`, used by the `B5_native1w` role (`cobar|neighbourhood=none|...|global_params=interleave`).

```
8 full problem subsolvers: [default_lp, fixed, max_lp, no_lp, pseudo_costs, quick_restart, quick_restart_no_lp, reduced_costs]
1 first solution subsolver: [fj]
10 interleaved subsolvers: [graph_arc_lns, graph_cst_lns, graph_dec_lns, graph_var_lns, rnd_cst_lns, rnd_var_lns,
    scheduling_intervals_lns, scheduling_precedences_lns, scheduling_resource_windows_lns, scheduling_time_window_lns]
3 helper subsolvers: [neighborhood_helper, synchronization_agent, update_gap_integral]
```
(full file: `results/final_icaps/solver_logs/B5_native1w_log.txt`)

**Confirmed, not inferred:** all four scheduling-specific LNS generators (`scheduling_intervals_lns`, `scheduling_precedences_lns`, `scheduling_resource_windows_lns`, `scheduling_time_window_lns`) run, interleaved with six generic LNS generators, on one thread. The "native single-thread LNS" label for B5 is **accurate**, and is retained unchanged.

**Contrast: B0/B2/B3/B4's own global-continuation stage** (default params, `num_workers=1`, no `interleave_search` — i.e. what IAIP-SR and all three repeated-round candidates actually use for their final unrestricted stage):

```
Starting search at 0.05s with 1 workers.
1 full problem subsolver: [main]
Starting subsolver 'main' hint search at 0.06s
Starting subsolver 'main' search at 0.06s
```
(full file: `results/final_icaps/solver_logs/default_1worker_no_interleave_log.txt`)

**No LNS subsolver of any kind runs** in this configuration — only a single `main` search thread. This confirms the asymmetry that makes B5 a meaningful comparator at all: it is the *only* single-worker configuration in the study where CP-SAT's own scheduling-aware search is active, and the external repeated-round methods' final global stage gets none of it.

## 2.3: Four-worker configuration (B6 at 4 workers, U3)

Configuration: `num_workers=4`, default parameters (no `interleave_search` — not needed at `num_workers>1`), same instance.

```
Starting search at 0.02s with 4 workers.
3 full problem subsolvers: [default_lp, fixed, no_lp]
1 first solution subsolver: [fj]
13 interleaved subsolvers: [feasibility_pump, graph_arc_lns, graph_cst_lns, graph_dec_lns, graph_var_lns, ls, rins/rens,
    rnd_cst_lns, rnd_var_lns, scheduling_intervals_lns, scheduling_precedences_lns, scheduling_resource_windows_lns,
    scheduling_time_window_lns]
3 helper subsolvers: [neighborhood_helper, synchronization_agent, update_gap_integral]
```
(full file: `results/final_icaps/solver_logs/B6_native4w_log.txt`)

**Confirmed:** the same four scheduling generators run, now alongside three additional generic mechanisms (`feasibility_pump`, `ls`, `rins/rens`) not present in the 1-worker interleaved configuration. The "native four-worker LNS" label for B6-at-4-workers is **accurate** and retained. Because more of CP-SAT's portfolio is active at 4 workers than at 1 (13 vs. 10 interleaved subsolvers, plus 3 vs. 8 full-problem subsolvers run differently across the two regimes), the 4-worker comparator is a *stronger* opponent in a way the 1-worker one is not — consistent with, and a partial mechanistic explanation for, the confirmatory finding (§15 of `FINAL_SUBMISSION_RESEARCH_REPORT.md`) that the external methods' advantage over native search shrinks from -43.8% at 1 worker to a non-significant -9.1% at 4 workers.

## 2.3 (continued): a genuine correction to a prior claim

Testing whether CP-SAT's subsolver selection is actually inaccessible (as the prior-stage manuscript and `02_prior_work_and_novelty.md` claimed) found that it is **not**:

```python
s.parameters.filter_subsolvers.extend(["scheduling_intervals_lns", "scheduling_precedences_lns",
                                       "scheduling_resource_windows_lns", "scheduling_time_window_lns"])
```
produces, verified from a saved log:
```
4 interleaved subsolvers: [scheduling_intervals_lns, scheduling_precedences_lns, scheduling_resource_windows_lns, scheduling_time_window_lns]
3 helper subsolvers: [neighborhood_helper, synchronization_agent, update_gap_integral]
32 ignored subsolvers: [core, default_lp, fixed, fj, ...]
status: UNKNOWN
```
`filter_subsolvers`, `extra_subsolvers` and `ignore_subsolvers` are exposed `SatParameters` fields; a global initial LNS difficulty (`lns_initial_difficulty`) is also exposed. The prior claim ("per-generator selection... [is] internal and not exposed to callers") was **wrong** and has been corrected in `02_prior_work_and_novelty.md` and in the manuscript (`manuscript.tex`, recompiled, resubmission PDF regenerated: still 5 pages, 0 errors, 108/108 claim macros defined, 0 hand-typed result literals).

**What this does and does not change:** no numeric result changes — B5 and B6-at-4-workers were never run with subsolver filtering, and their logged behaviour (full default/interleaved portfolio, scheduling generators active alongside others) is exactly what the confirmatory campaign actually used. The correction is purely to the *prose claim* about what CP-SAT exposes. Isolating "scheduling-LNS-only" behaviour (`filter_subsolvers` removes the core search entirely, so a usable isolated-scheduling-LNS baseline would need `extra_subsolvers` combined with a retained core search subsolver, not `filter_subsolvers` alone) is noted as a feasible but **not attempted** follow-up experiment: it answers a narrower, different question (does scheduling-LNS specifically, versus the whole native portfolio, explain the 4-worker result?) than anything this study claims, and per the standing instruction not to launch new experiments except to resolve a material ambiguity in an existing claim, it is left for future work rather than run here.

## 2.4: Baseline fairness accounting

| Item | B2 (candidate) / B1 / B3 / B4 | B5 (native 1w) | B6 (native 4w, U3) |
|---|---|---|---|
| wall-clock budget | identical across all (8s in U1, matched per setting elsewhere) | identical | identical |
| workers | 1 | 1 | 4 |
| physical cores pinned | 1 | 1 | 4 (one process per 4-core group, `taskset`-style pinning via `--cpu-groups`) |
| solver invocations per instance | portfolio (1) + up to 1 initial stage + up to 9 rounds + 1 global = up to 12 CP-SAT calls | 1 CP-SAT call (whole budget) | 1 CP-SAT call (whole budget) |
| model-building overhead | charged inside each call's wall-clock budget (one shared monotonic clock; verified in `05_verification.md` §4) | charged inside the single call | charged inside the single call |
| incumbent availability | portfolio construction time recorded exactly (never t=0); see round diagnostics in `04_mechanism_analysis.md` | first incumbent whenever CP-SAT's own search finds one | same |
| CPU-second accounting | 1 worker x B seconds = B core-seconds per instance | 1 x B = B core-seconds | 4 x B = 4B core-seconds |

**Equal wall-clock, unequal core-seconds at 4 workers (explicit, not hidden).** B6-at-4-workers consumes 4x the CPU-seconds of B2/B0/B3 in U3, because U3's purpose (per the frozen protocol, `06_statistical_results.md`) is specifically to ask "does the candidate's advantage survive when CP-SAT is given its own multi-worker search," not "is the candidate equally CPU-efficient." The manuscript's Methodology section already states this distinction ("we compare it only at matched worker count ... never 1-worker-ours vs. 4-worker-native") but did not explicitly flag the core-second asymmetry; this document records it for completeness. **A resource-normalized (core-second-matched) comparison was not run**: it would require giving the external methods 4 workers too (resource-normalized wall-clock) or giving native CP-SAT 1 worker for 4x the wall-clock (resource-normalized core-seconds), and either changes what U3 is designed to measure. This is recorded as a limitation (§8 of the final report), not resolved here, consistent with "do not launch another large experiment campaign."

## Summary of Phase 2 findings

1. **B5 ("native single-thread LNS") label: verified accurate**, saved log evidence attached.
2. **B6-at-4-workers ("native four-worker LNS") label: verified accurate**, saved log evidence attached, and is a *strictly richer* subsolver portfolio than the 1-worker case (13 vs. 10 interleaved subsolvers), which is a plausible mechanistic reason the external advantage shrinks at 4 workers.
3. **One prior claim was found to be an overclaim and corrected**: CP-SAT's subsolver selection IS exposed to Python callers (contrary to the previous documentation and manuscript text); this was not used in any reported experiment, so no numeric result is affected, only the prose explaining why external analogues were built instead of calling internal generators directly.
4. **Resource accounting is explicit**: equal wall-clock budgets throughout; U3's 4-worker comparison uses 4x the core-seconds of the 1-worker comparisons by design, and this is now stated plainly rather than left implicit.
