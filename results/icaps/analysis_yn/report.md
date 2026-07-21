# ICAPS Experiment Report
Generated from 448 result rows (448 ok, 0 errors).
## 1. Executive summary
Best method by mean primal integral: **boot_cold** (mean PI 0.0338) vs baseline `cpsat_cold` (mean PI 0.0497).
## 2. What was implemented
Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, 3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-specific bootstrap floor policies, static benchmark loaders, an RCPSP second domain, and stability metrics -- see docs/icaps_experiment_plan.md.
## 3. What experiments were run
- `yn_benchmarks`: 448 rows
## 4. Failed / unfinished parts
No row-level errors in this data.

Not executed in this pass (compute cost appropriate for an unattended multi-day run; grids validated via `--dry-run`, not run): `main`, `ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP are documented TODOs, not implemented.
scipy available: True (Wilcoxon computed). matplotlib available: True (plots generated).
## 5. Main results
| method | n | mean_pi | median_pi | std_pi | iqr_pi | mean_final_gap | median_final_gap | mean_bootstrap_time_ms | median_bootstrap_time_ms | mean_moved_ops_frac | optimality_proof_rate | feasibility_failure_rate | n_all | n_errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_cold | 112 | 0.0338 | 0.0357 | 0.0179 | 0.0269 | 0.0143 | 0.0064 | 0.0000 | 0.0000 | 0.8620 | 0.0000 | 0.0000 | 112 | 0 |
| boot_warm | 112 | 0.0340 | 0.0352 | 0.0192 | 0.0261 | 0.0142 | 0.0083 | 0.0000 | 0.0000 | 0.9065 | 0.0000 | 0.0000 | 112 | 0 |
| cpsat_warm | 112 | 0.0417 | 0.0357 | 0.0287 | 0.0450 | 0.0101 | 0.0021 | 0.0000 | 0.0000 | 0.7904 | 0.0000 | 0.0000 | 112 | 0 |
| cpsat_cold | 112 | 0.0497 | 0.0478 | 0.0187 | 0.0249 | 0.0155 | 0.0068 | 0.0000 | 0.0000 | 0.9573 | 0.0000 | 0.0000 | 112 | 0 |
## 6. Tables
### Pairwise vs cpsat_cold
| method | n_common | pi_win | pi_tie | pi_loss | final_gap_win | final_gap_tie | final_gap_loss | stability_win | stability_tie | stability_loss | sign_test_p | wilcoxon_p | mean_pi_improvement | ci95_lo | ci95_hi | sign_test_p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_cold | 112 | 94 | 0 | 18 | 20 | 73 | 19 | 39 | 38 | 19 | 0.0000 | 0.0000 | 0.0159 | 0.0126 | 0.0194 | 0.0000 |
| boot_warm | 112 | 73 | 0 | 39 | 53 | 10 | 49 | 49 | 3 | 44 | 0.0017 | 0.0000 | 0.0158 | 0.0112 | 0.0206 | 0.0034 |
| cpsat_warm | 112 | 70 | 0 | 42 | 59 | 13 | 40 | 48 | 5 | 43 | 0.0104 | 0.0106 | 0.0080 | 0.0019 | 0.0147 | 0.0104 |
### Breakdown by delta_kind
| method | delta_kind | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | arrival | 0.0182 | 0.0053 | 40 |
| boot_warm | arrival | 0.0363 | 0.0203 | 40 |
| boot_cold | arrival | 0.0364 | 0.0203 | 40 |
| cpsat_cold | arrival | 0.0570 | 0.0222 | 40 |
| cpsat_cold | base | 0.0431 | 0.0001 | 16 |
| cpsat_warm | base | 0.0455 | 0.0017 | 16 |
| boot_cold | base | 0.0483 | 0.0045 | 16 |
| boot_warm | base | 0.0493 | 0.0046 | 16 |
| boot_cold | cancellation | 0.0232 | 0.0106 | 20 |
| boot_warm | cancellation | 0.0248 | 0.0152 | 20 |
| cpsat_warm | cancellation | 0.0293 | 0.0082 | 20 |
| cpsat_cold | cancellation | 0.0448 | 0.0134 | 20 |
| boot_warm | duration_jitter | 0.0228 | 0.0081 | 20 |
| boot_cold | duration_jitter | 0.0313 | 0.0158 | 20 |
| cpsat_cold | duration_jitter | 0.0496 | 0.0172 | 20 |
| cpsat_warm | duration_jitter | 0.0741 | 0.0150 | 20 |
| boot_cold | outage | 0.0292 | 0.0117 | 16 |
| boot_warm | outage | 0.0380 | 0.0149 | 16 |
| cpsat_cold | outage | 0.0447 | 0.0146 | 16 |
| cpsat_warm | outage | 0.0716 | 0.0271 | 16 |
### Breakdown by severity
| method | severity | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | medium | 0.0338 | 0.0143 | 112 |
| boot_warm | medium | 0.0340 | 0.0142 | 112 |
| cpsat_warm | medium | 0.0417 | 0.0101 | 112 |
| cpsat_cold | medium | 0.0497 | 0.0155 | 112 |
### Breakdown by budget_s
| method | budget_s | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | 8 | 0.0338 | 0.0143 | 112 |
| boot_warm | 8 | 0.0340 | 0.0142 | 112 |
| cpsat_warm | 8 | 0.0417 | 0.0101 | 112 |
| cpsat_cold | 8 | 0.0497 | 0.0155 | 112 |
### Breakdown by workers
| method | workers | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | 1 | 0.0338 | 0.0143 | 112 |
| boot_warm | 1 | 0.0340 | 0.0142 | 112 |
| cpsat_warm | 1 | 0.0417 | 0.0101 | 112 |
| cpsat_cold | 1 | 0.0497 | 0.0155 | 112 |
### Breakdown by instance_size
| method | instance_size | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | yn1_20x20 | 0.0272 | 0.0078 | 28 |
| cpsat_cold | yn1_20x20 | 0.0339 | 0.0075 | 28 |
| boot_warm | yn1_20x20 | 0.0350 | 0.0139 | 28 |
| cpsat_warm | yn1_20x20 | 0.0431 | 0.0096 | 28 |
| boot_cold | yn2_20x20 | 0.0363 | 0.0161 | 28 |
| boot_warm | yn2_20x20 | 0.0370 | 0.0174 | 28 |
| cpsat_warm | yn2_20x20 | 0.0431 | 0.0093 | 28 |
| cpsat_cold | yn2_20x20 | 0.0469 | 0.0134 | 28 |
| boot_warm | yn3_20x20 | 0.0317 | 0.0140 | 28 |
| boot_cold | yn3_20x20 | 0.0332 | 0.0170 | 28 |
| cpsat_warm | yn3_20x20 | 0.0436 | 0.0126 | 28 |
| cpsat_cold | yn3_20x20 | 0.0564 | 0.0211 | 28 |
| boot_warm | yn4_20x20 | 0.0321 | 0.0116 | 28 |
| cpsat_warm | yn4_20x20 | 0.0370 | 0.0090 | 28 |
| boot_cold | yn4_20x20 | 0.0385 | 0.0162 | 28 |
| cpsat_cold | yn4_20x20 | 0.0618 | 0.0200 | 28 |
### Breakdown by objective
| method | objective | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | makespan | 0.0338 | 0.0143 | 112 |
| boot_warm | makespan | 0.0340 | 0.0142 | 112 |
| cpsat_warm | makespan | 0.0417 | 0.0101 | 112 |
| cpsat_cold | makespan | 0.0497 | 0.0155 | 112 |
### Breakdown by bootstrap_policy
| method | bootstrap_policy | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | append | 0.0338 | 0.0143 | 112 |
| boot_warm | append | 0.0340 | 0.0142 | 112 |
| cpsat_warm | append | 0.0417 | 0.0101 | 112 |
| cpsat_cold | append | 0.0497 | 0.0155 | 112 |
### Breakdown by stream_step
| method | stream_step | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_cold | 0 | 0.0431 | 0.0001 | 16 |
| cpsat_warm | 0 | 0.0455 | 0.0017 | 16 |
| boot_cold | 0 | 0.0483 | 0.0045 | 16 |
| boot_warm | 0 | 0.0493 | 0.0046 | 16 |
| cpsat_warm | 1 | 0.0245 | 0.0056 | 16 |
| boot_cold | 1 | 0.0301 | 0.0160 | 16 |
| boot_warm | 1 | 0.0319 | 0.0234 | 16 |
| cpsat_cold | 1 | 0.0565 | 0.0239 | 16 |
| boot_cold | 2 | 0.0268 | 0.0112 | 16 |
| boot_warm | 2 | 0.0288 | 0.0128 | 16 |
| cpsat_cold | 2 | 0.0413 | 0.0104 | 16 |
| cpsat_warm | 2 | 0.0467 | 0.0151 | 16 |
| boot_cold | 3 | 0.0254 | 0.0118 | 16 |
| boot_warm | 3 | 0.0282 | 0.0178 | 16 |
| cpsat_cold | 3 | 0.0496 | 0.0149 | 16 |
| cpsat_warm | 3 | 0.0496 | 0.0067 | 16 |
| boot_cold | 4 | 0.0343 | 0.0150 | 16 |
| cpsat_warm | 4 | 0.0354 | 0.0111 | 16 |
| boot_warm | 4 | 0.0407 | 0.0183 | 16 |
| cpsat_cold | 4 | 0.0463 | 0.0153 | 16 |
| boot_warm | 5 | 0.0324 | 0.0155 | 16 |
| boot_cold | 5 | 0.0363 | 0.0220 | 16 |
| cpsat_warm | 5 | 0.0390 | 0.0152 | 16 |
| cpsat_cold | 5 | 0.0588 | 0.0220 | 16 |
| boot_warm | 6 | 0.0263 | 0.0070 | 16 |
| boot_cold | 6 | 0.0355 | 0.0196 | 16 |
| cpsat_warm | 6 | 0.0514 | 0.0156 | 16 |
| cpsat_cold | 6 | 0.0526 | 0.0220 | 16 |
## 7. Figures
- results/icaps/analysis_yn/figures/final_gap_boxplot.pdf
- results/icaps/analysis_yn/figures/pi_scatter.pdf
## 8. Interpretation
- **Where it helps:** `boot_cold` shows the largest mean PI improvement over `cpsat_cold` (0.0159, 94W/0T/18L, sign-test p=0.0000).
- **Where it weakens:** `cpsat_warm` shows the smallest/negative mean PI improvement (0.0080).
- **Arrivals:** cpsat_warm=0.0182, boot_warm=0.0363, boot_cold=0.0364, cpsat_cold=0.0570 (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).
- **Multi-worker:** not exercised in this pass (workers=1 only); this is a known, explicitly flagged limitation, not a claim.
## 9. ICAPS paper recommendation
**Ready:** the method (boot_cold), the domination guarantee (in its precise form -- see below), the pilot primal-integral result on job-shop across 7 seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and the benchmark/loader infrastructure.

**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/worker counts) for the actual paper table; `workers` preset specifically to characterize whether gains shrink under CP-SAT's own multi-worker portfolio search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only activates with workers>1); `arrivals` preset to confirm gap_insert/regret_insert/beam_insert close the arrival weak case at scale, not just in the single case checked by unit tests.

**Strongest claim supported by data so far:** a near-zero-cost constructive repair of the previous schedule, kept as an anytime floor under an unmodified CP-SAT solve, improves primal integral, replicated across seeds and domains (BOOT_COLD_PAPER.md).

**Domination guarantee -- precise form (do not overstate):** boot_cold's final objective is provably never worse than **its own unmodified continuation** (same run, same budget window) -- this is a theorem, not an empirical tendency. It is *not* an exact guarantee against a *separately invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 re-analysis) boot_cold's final objective was strictly worse than an independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%), attributable to wall-clock non-reproducibility, not a flaw in the proof. State the theorem in its precise form; report the 92.4% empirical non-loss rate as a strong-but-not-absolute finding, never as "provably never worse than cold-solving."

**Claims to avoid:** this is not a machine-learning method; CP-SAT's own search is not improved or sped to proof; final objective is not usually better (ties are the norm, by design); "provably never worse than cold" (only true against its own continuation, see above); weak cases (arrivals, and any case not yet run at the `main`/`workers`/`budgets` scale) should not be papered over.
