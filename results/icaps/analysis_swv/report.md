# ICAPS Experiment Report
Generated from 560 result rows (560 ok, 0 errors).
## 1. Executive summary
Best method by mean primal integral: **boot_warm** (mean PI 0.0205) vs baseline `cpsat_cold` (mean PI 0.0435).
## 2. What was implemented
Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, 3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-specific bootstrap floor policies, static benchmark loaders, an RCPSP second domain, and stability metrics -- see docs/icaps_experiment_plan.md.
## 3. What experiments were run
- `swv_benchmarks`: 560 rows
## 4. Failed / unfinished parts
No row-level errors in this data.

Not executed in this pass (compute cost appropriate for an unattended multi-day run; grids validated via `--dry-run`, not run): `main`, `ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP are documented TODOs, not implemented.
scipy available: True (Wilcoxon computed). matplotlib available: True (plots generated).
## 5. Main results
| method | n | mean_pi | median_pi | std_pi | iqr_pi | mean_final_gap | median_final_gap | mean_bootstrap_time_ms | median_bootstrap_time_ms | mean_moved_ops_frac | optimality_proof_rate | feasibility_failure_rate | n_all | n_errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_warm | 140 | 0.0205 | 0.0184 | 0.0144 | 0.0182 | 0.0085 | 0.0016 | 0.0000 | 0.0000 | 0.9042 | 0.0000 | 0.0000 | 140 | 0 |
| boot_cold | 140 | 0.0269 | 0.0246 | 0.0163 | 0.0235 | 0.0133 | 0.0075 | 0.0000 | 0.0000 | 0.8701 | 0.0000 | 0.0000 | 140 | 0 |
| cpsat_warm | 140 | 0.0295 | 0.0230 | 0.0269 | 0.0235 | 0.0112 | 0.0030 | 0.0000 | 0.0000 | 0.8882 | 0.0000 | 0.0000 | 140 | 0 |
| cpsat_cold | 140 | 0.0435 | 0.0426 | 0.0173 | 0.0219 | 0.0154 | 0.0105 | 0.0000 | 0.0000 | 0.9871 | 0.0000 | 0.0000 | 140 | 0 |
## 6. Tables
### Pairwise vs cpsat_cold
| method | n_common | pi_win | pi_tie | pi_loss | final_gap_win | final_gap_tie | final_gap_loss | stability_win | stability_tie | stability_loss | sign_test_p | wilcoxon_p | mean_pi_improvement | ci95_lo | ci95_hi | sign_test_p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_warm | 140 | 117 | 0 | 23 | 78 | 18 | 44 | 57 | 29 | 34 | 0.0000 | 0.0000 | 0.0231 | 0.0197 | 0.0265 | 0.0000 |
| boot_cold | 140 | 125 | 0 | 15 | 28 | 94 | 18 | 40 | 68 | 12 | 0.0000 | 0.0000 | 0.0166 | 0.0142 | 0.0190 | 0.0000 |
| cpsat_warm | 140 | 102 | 0 | 38 | 72 | 17 | 51 | 59 | 15 | 46 | 0.0000 | 0.0000 | 0.0141 | 0.0085 | 0.0189 | 0.0000 |
### Breakdown by delta_kind
| method | delta_kind | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | arrival | 0.0161 | 0.0075 | 55 |
| boot_warm | arrival | 0.0207 | 0.0110 | 55 |
| boot_cold | arrival | 0.0293 | 0.0187 | 55 |
| cpsat_cold | arrival | 0.0485 | 0.0209 | 55 |
| cpsat_warm | base | 0.0265 | 0.0009 | 20 |
| cpsat_cold | base | 0.0265 | 0.0011 | 20 |
| boot_warm | base | 0.0277 | 0.0017 | 20 |
| boot_cold | base | 0.0282 | 0.0017 | 20 |
| boot_warm | cancellation | 0.0222 | 0.0099 | 20 |
| cpsat_warm | cancellation | 0.0287 | 0.0091 | 20 |
| boot_cold | cancellation | 0.0290 | 0.0149 | 20 |
| cpsat_cold | cancellation | 0.0456 | 0.0165 | 20 |
| boot_warm | duration_jitter | 0.0156 | 0.0090 | 25 |
| boot_cold | duration_jitter | 0.0170 | 0.0078 | 25 |
| cpsat_cold | duration_jitter | 0.0409 | 0.0122 | 25 |
| cpsat_warm | duration_jitter | 0.0561 | 0.0289 | 25 |
| boot_warm | outage | 0.0170 | 0.0068 | 20 |
| boot_cold | outage | 0.0297 | 0.0156 | 20 |
| cpsat_warm | outage | 0.0367 | 0.0117 | 20 |
| cpsat_cold | outage | 0.0482 | 0.0176 | 20 |
### Breakdown by severity
| method | severity | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | medium | 0.0205 | 0.0085 | 140 |
| boot_cold | medium | 0.0269 | 0.0133 | 140 |
| cpsat_warm | medium | 0.0295 | 0.0112 | 140 |
| cpsat_cold | medium | 0.0435 | 0.0154 | 140 |
### Breakdown by budget_s
| method | budget_s | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | 8 | 0.0205 | 0.0085 | 140 |
| boot_cold | 8 | 0.0269 | 0.0133 | 140 |
| cpsat_warm | 8 | 0.0295 | 0.0112 | 140 |
| cpsat_cold | 8 | 0.0435 | 0.0154 | 140 |
### Breakdown by workers
| method | workers | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | 1 | 0.0205 | 0.0085 | 140 |
| boot_cold | 1 | 0.0269 | 0.0133 | 140 |
| cpsat_warm | 1 | 0.0295 | 0.0112 | 140 |
| cpsat_cold | 1 | 0.0435 | 0.0154 | 140 |
### Breakdown by instance_size
| method | instance_size | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | swv01_20x10 | 0.0186 | 0.0063 | 28 |
| cpsat_warm | swv01_20x10 | 0.0321 | 0.0104 | 28 |
| boot_cold | swv01_20x10 | 0.0368 | 0.0210 | 28 |
| cpsat_cold | swv01_20x10 | 0.0524 | 0.0214 | 28 |
| boot_warm | swv02_20x10 | 0.0229 | 0.0080 | 28 |
| boot_cold | swv02_20x10 | 0.0277 | 0.0122 | 28 |
| cpsat_warm | swv02_20x10 | 0.0306 | 0.0093 | 28 |
| cpsat_cold | swv02_20x10 | 0.0451 | 0.0137 | 28 |
| boot_warm | swv03_20x10 | 0.0211 | 0.0108 | 28 |
| boot_cold | swv03_20x10 | 0.0261 | 0.0139 | 28 |
| cpsat_warm | swv03_20x10 | 0.0355 | 0.0182 | 28 |
| cpsat_cold | swv03_20x10 | 0.0444 | 0.0176 | 28 |
| boot_cold | swv04_20x10 | 0.0170 | 0.0067 | 28 |
| boot_warm | swv04_20x10 | 0.0183 | 0.0095 | 28 |
| cpsat_warm | swv04_20x10 | 0.0247 | 0.0090 | 28 |
| cpsat_cold | swv04_20x10 | 0.0330 | 0.0101 | 28 |
| boot_warm | swv05_20x10 | 0.0214 | 0.0081 | 28 |
| cpsat_warm | swv05_20x10 | 0.0244 | 0.0090 | 28 |
| boot_cold | swv05_20x10 | 0.0270 | 0.0128 | 28 |
| cpsat_cold | swv05_20x10 | 0.0427 | 0.0144 | 28 |
### Breakdown by objective
| method | objective | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | makespan | 0.0205 | 0.0085 | 140 |
| boot_cold | makespan | 0.0269 | 0.0133 | 140 |
| cpsat_warm | makespan | 0.0295 | 0.0112 | 140 |
| cpsat_cold | makespan | 0.0435 | 0.0154 | 140 |
### Breakdown by bootstrap_policy
| method | bootstrap_policy | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_warm | append | 0.0205 | 0.0085 | 140 |
| boot_cold | append | 0.0269 | 0.0133 | 140 |
| cpsat_warm | append | 0.0295 | 0.0112 | 140 |
| cpsat_cold | append | 0.0435 | 0.0154 | 140 |
### Breakdown by stream_step
| method | stream_step | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | 0 | 0.0265 | 0.0009 | 20 |
| cpsat_cold | 0 | 0.0265 | 0.0011 | 20 |
| boot_warm | 0 | 0.0277 | 0.0017 | 20 |
| boot_cold | 0 | 0.0282 | 0.0017 | 20 |
| cpsat_warm | 1 | 0.0198 | 0.0089 | 20 |
| boot_warm | 1 | 0.0206 | 0.0098 | 20 |
| boot_cold | 1 | 0.0273 | 0.0194 | 20 |
| cpsat_cold | 1 | 0.0455 | 0.0207 | 20 |
| boot_warm | 2 | 0.0214 | 0.0113 | 20 |
| boot_cold | 2 | 0.0296 | 0.0159 | 20 |
| cpsat_warm | 2 | 0.0347 | 0.0150 | 20 |
| cpsat_cold | 2 | 0.0432 | 0.0161 | 20 |
| boot_warm | 3 | 0.0144 | 0.0092 | 20 |
| boot_cold | 3 | 0.0205 | 0.0065 | 20 |
| cpsat_cold | 3 | 0.0410 | 0.0090 | 20 |
| cpsat_warm | 3 | 0.0428 | 0.0170 | 20 |
| boot_warm | 4 | 0.0150 | 0.0051 | 20 |
| boot_cold | 4 | 0.0273 | 0.0162 | 20 |
| cpsat_warm | 4 | 0.0318 | 0.0109 | 20 |
| cpsat_cold | 4 | 0.0489 | 0.0179 | 20 |
| boot_warm | 5 | 0.0180 | 0.0096 | 20 |
| cpsat_warm | 5 | 0.0206 | 0.0067 | 20 |
| boot_cold | 5 | 0.0271 | 0.0153 | 20 |
| cpsat_cold | 5 | 0.0514 | 0.0207 | 20 |
| boot_warm | 6 | 0.0262 | 0.0131 | 20 |
| boot_cold | 6 | 0.0286 | 0.0183 | 20 |
| cpsat_warm | 6 | 0.0301 | 0.0191 | 20 |
| cpsat_cold | 6 | 0.0483 | 0.0226 | 20 |
## 7. Figures
- results/icaps/analysis_swv/figures/final_gap_boxplot.pdf
- results/icaps/analysis_swv/figures/pi_scatter.pdf
## 8. Interpretation
- **Where it helps:** `boot_warm` shows the largest mean PI improvement over `cpsat_cold` (0.0231, 117W/0T/23L, sign-test p=0.0000).
- **Where it weakens:** `cpsat_warm` shows the smallest/negative mean PI improvement (0.0141).
- **Arrivals:** cpsat_warm=0.0161, boot_warm=0.0207, boot_cold=0.0293, cpsat_cold=0.0485 (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).
- **Multi-worker:** not exercised in this pass (workers=1 only); this is a known, explicitly flagged limitation, not a claim.
## 9. ICAPS paper recommendation
**Ready:** the method (boot_cold), the domination guarantee (in its precise form -- see below), the pilot primal-integral result on job-shop across 7 seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and the benchmark/loader infrastructure.

**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/worker counts) for the actual paper table; `workers` preset specifically to characterize whether gains shrink under CP-SAT's own multi-worker portfolio search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only activates with workers>1); `arrivals` preset to confirm gap_insert/regret_insert/beam_insert close the arrival weak case at scale, not just in the single case checked by unit tests.

**Strongest claim supported by data so far:** a near-zero-cost constructive repair of the previous schedule, kept as an anytime floor under an unmodified CP-SAT solve, improves primal integral, replicated across seeds and domains (BOOT_COLD_PAPER.md).

**Domination guarantee -- precise form (do not overstate):** boot_cold's final objective is provably never worse than **its own unmodified continuation** (same run, same budget window) -- this is a theorem, not an empirical tendency. It is *not* an exact guarantee against a *separately invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 re-analysis) boot_cold's final objective was strictly worse than an independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%), attributable to wall-clock non-reproducibility, not a flaw in the proof. State the theorem in its precise form; report the 92.4% empirical non-loss rate as a strong-but-not-absolute finding, never as "provably never worse than cold-solving."

**Claims to avoid:** this is not a machine-learning method; CP-SAT's own search is not improved or sped to proof; final objective is not usually better (ties are the norm, by design); "provably never worse than cold" (only true against its own continuation, see above); weak cases (arrivals, and any case not yet run at the `main`/`workers`/`budgets` scale) should not be papered over.
