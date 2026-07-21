# ICAPS Experiment Report
Generated from 560 result rows (560 ok, 0 errors).
## 1. Executive summary
Best method by mean primal integral: **boot_warm** (mean PI 0.0238) vs baseline `cpsat_cold` (mean PI 0.0701).
## 2. What was implemented
Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, 3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-specific bootstrap floor policies, static benchmark loaders, an RCPSP second domain, and stability metrics -- see docs/icaps_experiment_plan.md.
## 3. What experiments were run
- `dmu_benchmarks`: 560 rows
## 4. Failed / unfinished parts
No row-level errors in this data.

Not executed in this pass (compute cost appropriate for an unattended multi-day run; grids validated via `--dry-run`, not run): `main`, `ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP are documented TODOs, not implemented.
scipy available: True (Wilcoxon computed). matplotlib available: True (plots generated).
## 5. Main results
| method | n | mean_pi | median_pi | std_pi | iqr_pi | mean_final_gap | median_final_gap | mean_bootstrap_time_ms | median_bootstrap_time_ms | mean_moved_ops_frac | optimality_proof_rate | feasibility_failure_rate | n_all | n_errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_warm | 140 | 0.0238 | 0.0217 | 0.0177 | 0.0263 | 0.0085 | 0.0000 | 0.0000 | 0.0000 | 0.7991 | 0.0000 | 0.0000 | 140 | 0 |
| cpsat_warm | 140 | 0.0313 | 0.0250 | 0.0288 | 0.0348 | 0.0092 | 0.0010 | 0.0000 | 0.0000 | 0.6267 | 0.0000 | 0.0000 | 140 | 0 |
| boot_cold | 140 | 0.0406 | 0.0414 | 0.0178 | 0.0277 | 0.0240 | 0.0209 | 0.0000 | 0.0000 | 0.6977 | 0.0000 | 0.0000 | 140 | 0 |
| cpsat_cold | 140 | 0.0701 | 0.0679 | 0.0223 | 0.0316 | 0.0277 | 0.0268 | 0.0000 | 0.0000 | 0.9614 | 0.0000 | 0.0000 | 140 | 0 |
## 6. Tables
### Pairwise vs cpsat_cold
| method | n_common | pi_win | pi_tie | pi_loss | final_gap_win | final_gap_tie | final_gap_loss | stability_win | stability_tie | stability_loss | sign_test_p | wilcoxon_p | mean_pi_improvement | ci95_lo | ci95_hi | sign_test_p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_warm | 140 | 123 | 0 | 17 | 105 | 12 | 23 | 75 | 5 | 40 | 0.0000 | 0.0000 | 0.0463 | 0.0411 | 0.0513 | 0.0000 |
| cpsat_warm | 140 | 114 | 0 | 26 | 97 | 14 | 29 | 79 | 4 | 37 | 0.0000 | 0.0000 | 0.0388 | 0.0318 | 0.0453 | 0.0000 |
| boot_cold | 140 | 121 | 0 | 19 | 51 | 56 | 33 | 66 | 29 | 25 | 0.0000 | 0.0000 | 0.0295 | 0.0252 | 0.0338 | 0.0000 |
### Breakdown by delta_kind
| method | delta_kind | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | arrival | 0.0154 | 0.0053 | 70 |
| boot_warm | arrival | 0.0184 | 0.0108 | 70 |
| boot_cold | arrival | 0.0386 | 0.0293 | 70 |
| cpsat_cold | arrival | 0.0763 | 0.0341 | 70 |
| cpsat_cold | base | 0.0445 | 0.0007 | 20 |
| cpsat_warm | base | 0.0469 | 0.0005 | 20 |
| boot_warm | base | 0.0489 | 0.0022 | 20 |
| boot_cold | base | 0.0490 | 0.0014 | 20 |
| boot_warm | cancellation | 0.0265 | 0.0123 | 15 |
| cpsat_warm | cancellation | 0.0354 | 0.0141 | 15 |
| boot_cold | cancellation | 0.0474 | 0.0258 | 15 |
| cpsat_cold | cancellation | 0.0692 | 0.0223 | 15 |
| boot_warm | duration_jitter | 0.0155 | 0.0046 | 25 |
| boot_cold | duration_jitter | 0.0388 | 0.0287 | 25 |
| cpsat_warm | duration_jitter | 0.0438 | 0.0181 | 25 |
| cpsat_cold | duration_jitter | 0.0765 | 0.0346 | 25 |
| boot_warm | outage | 0.0281 | 0.0085 | 10 |
| boot_cold | outage | 0.0328 | 0.0179 | 10 |
| cpsat_cold | outage | 0.0635 | 0.0283 | 10 |
| cpsat_warm | outage | 0.0733 | 0.0240 | 10 |
### Breakdown by severity
| method | severity | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | medium | 0.0238 | 0.0085 | 140 |
| cpsat_warm | medium | 0.0313 | 0.0092 | 140 |
| boot_cold | medium | 0.0406 | 0.0240 | 140 |
| cpsat_cold | medium | 0.0701 | 0.0277 | 140 |
### Breakdown by budget_s
| method | budget_s | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | 8 | 0.0238 | 0.0085 | 140 |
| cpsat_warm | 8 | 0.0313 | 0.0092 | 140 |
| boot_cold | 8 | 0.0406 | 0.0240 | 140 |
| cpsat_cold | 8 | 0.0701 | 0.0277 | 140 |
### Breakdown by workers
| method | workers | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | 1 | 0.0238 | 0.0085 | 140 |
| cpsat_warm | 1 | 0.0313 | 0.0092 | 140 |
| boot_cold | 1 | 0.0406 | 0.0240 | 140 |
| cpsat_cold | 1 | 0.0701 | 0.0277 | 140 |
### Breakdown by instance_size
| method | instance_size | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | dmu01_20x15 | 0.0252 | 0.0047 | 28 |
| boot_warm | dmu01_20x15 | 0.0257 | 0.0109 | 28 |
| boot_cold | dmu01_20x15 | 0.0426 | 0.0277 | 28 |
| cpsat_cold | dmu01_20x15 | 0.0695 | 0.0257 | 28 |
| boot_warm | dmu02_20x15 | 0.0226 | 0.0072 | 28 |
| cpsat_warm | dmu02_20x15 | 0.0355 | 0.0128 | 28 |
| boot_cold | dmu02_20x15 | 0.0438 | 0.0268 | 28 |
| cpsat_cold | dmu02_20x15 | 0.0713 | 0.0284 | 28 |
| boot_warm | dmu03_20x15 | 0.0228 | 0.0050 | 28 |
| cpsat_warm | dmu03_20x15 | 0.0376 | 0.0132 | 28 |
| boot_cold | dmu03_20x15 | 0.0459 | 0.0248 | 28 |
| cpsat_cold | dmu03_20x15 | 0.0720 | 0.0309 | 28 |
| boot_warm | dmu04_20x15 | 0.0217 | 0.0104 | 28 |
| boot_cold | dmu04_20x15 | 0.0303 | 0.0190 | 28 |
| cpsat_warm | dmu04_20x15 | 0.0315 | 0.0065 | 28 |
| cpsat_cold | dmu04_20x15 | 0.0638 | 0.0289 | 28 |
| boot_warm | dmu05_20x15 | 0.0261 | 0.0088 | 28 |
| cpsat_warm | dmu05_20x15 | 0.0265 | 0.0088 | 28 |
| boot_cold | dmu05_20x15 | 0.0406 | 0.0219 | 28 |
| cpsat_cold | dmu05_20x15 | 0.0739 | 0.0250 | 28 |
### Breakdown by objective
| method | objective | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | makespan | 0.0238 | 0.0085 | 140 |
| cpsat_warm | makespan | 0.0313 | 0.0092 | 140 |
| boot_cold | makespan | 0.0406 | 0.0240 | 140 |
| cpsat_cold | makespan | 0.0701 | 0.0277 | 140 |
### Breakdown by bootstrap_policy
| method | bootstrap_policy | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | append | 0.0238 | 0.0085 | 140 |
| cpsat_warm | append | 0.0313 | 0.0092 | 140 |
| boot_cold | append | 0.0406 | 0.0240 | 140 |
| cpsat_cold | append | 0.0701 | 0.0277 | 140 |
### Breakdown by stream_step
| method | stream_step | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_cold | 0 | 0.0445 | 0.0007 | 20 |
| cpsat_warm | 0 | 0.0469 | 0.0005 | 20 |
| boot_warm | 0 | 0.0489 | 0.0022 | 20 |
| boot_cold | 0 | 0.0490 | 0.0014 | 20 |
| boot_warm | 1 | 0.0222 | 0.0071 | 20 |
| cpsat_warm | 1 | 0.0314 | 0.0116 | 20 |
| boot_cold | 1 | 0.0376 | 0.0284 | 20 |
| cpsat_cold | 1 | 0.0749 | 0.0359 | 20 |
| boot_warm | 2 | 0.0149 | 0.0076 | 20 |
| cpsat_warm | 2 | 0.0203 | 0.0081 | 20 |
| boot_cold | 2 | 0.0392 | 0.0310 | 20 |
| cpsat_cold | 2 | 0.0716 | 0.0304 | 20 |
| cpsat_warm | 3 | 0.0133 | 0.0064 | 20 |
| boot_warm | 3 | 0.0154 | 0.0100 | 20 |
| boot_cold | 3 | 0.0389 | 0.0259 | 20 |
| cpsat_cold | 3 | 0.0798 | 0.0327 | 20 |
| boot_warm | 4 | 0.0184 | 0.0111 | 20 |
| cpsat_warm | 4 | 0.0328 | 0.0086 | 20 |
| boot_cold | 4 | 0.0345 | 0.0226 | 20 |
| cpsat_cold | 4 | 0.0751 | 0.0295 | 20 |
| boot_warm | 5 | 0.0233 | 0.0116 | 20 |
| cpsat_warm | 5 | 0.0287 | 0.0125 | 20 |
| boot_cold | 5 | 0.0406 | 0.0283 | 20 |
| cpsat_cold | 5 | 0.0709 | 0.0306 | 20 |
| boot_warm | 6 | 0.0235 | 0.0097 | 20 |
| boot_cold | 6 | 0.0447 | 0.0306 | 20 |
| cpsat_warm | 6 | 0.0454 | 0.0167 | 20 |
| cpsat_cold | 6 | 0.0739 | 0.0344 | 20 |
## 7. Figures
- results/icaps/analysis_dmu/figures/final_gap_boxplot.pdf
- results/icaps/analysis_dmu/figures/pi_scatter.pdf
## 8. Interpretation
- **Where it helps:** `boot_warm` shows the largest mean PI improvement over `cpsat_cold` (0.0463, 123W/0T/17L, sign-test p=0.0000).
- **Where it weakens:** `boot_cold` shows the smallest/negative mean PI improvement (0.0295).
- **Arrivals:** cpsat_warm=0.0154, boot_warm=0.0184, boot_cold=0.0386, cpsat_cold=0.0763 (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).
- **Multi-worker:** not exercised in this pass (workers=1 only); this is a known, explicitly flagged limitation, not a claim.
## 9. ICAPS paper recommendation
**Ready:** the method (boot_cold), the domination guarantee (in its precise form -- see below), the pilot primal-integral result on job-shop across 7 seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and the benchmark/loader infrastructure.

**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/worker counts) for the actual paper table; `workers` preset specifically to characterize whether gains shrink under CP-SAT's own multi-worker portfolio search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only activates with workers>1); `arrivals` preset to confirm gap_insert/regret_insert/beam_insert close the arrival weak case at scale, not just in the single case checked by unit tests.

**Strongest claim supported by data so far:** a near-zero-cost constructive repair of the previous schedule, kept as an anytime floor under an unmodified CP-SAT solve, improves primal integral, replicated across seeds and domains (BOOT_COLD_PAPER.md).

**Domination guarantee -- precise form (do not overstate):** boot_cold's final objective is provably never worse than **its own unmodified continuation** (same run, same budget window) -- this is a theorem, not an empirical tendency. It is *not* an exact guarantee against a *separately invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 re-analysis) boot_cold's final objective was strictly worse than an independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%), attributable to wall-clock non-reproducibility, not a flaw in the proof. State the theorem in its precise form; report the 92.4% empirical non-loss rate as a strong-but-not-absolute finding, never as "provably never worse than cold-solving."

**Claims to avoid:** this is not a machine-learning method; CP-SAT's own search is not improved or sped to proof; final objective is not usually better (ties are the norm, by design); "provably never worse than cold" (only true against its own continuation, see above); weak cases (arrivals, and any case not yet run at the `main`/`workers`/`budgets` scale) should not be papered over.
