# ICAPS Experiment Report
Generated from 2240 result rows (2240 ok, 0 errors).
## 1. Executive summary
Best method by mean primal integral: **cpsat_warm** (mean PI 0.0218) vs baseline `cpsat_cold` (mean PI 0.0480).
## 2. What was implemented
Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, 3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-specific bootstrap floor policies, static benchmark loaders, an RCPSP second domain, and stability metrics -- see docs/icaps_experiment_plan.md.
## 3. What experiments were run
- `taillard_benchmarks`: 2240 rows
## 4. Failed / unfinished parts
No row-level errors in this data.

Not executed in this pass (compute cost appropriate for an unattended multi-day run; grids validated via `--dry-run`, not run): `main`, `ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP are documented TODOs, not implemented.
scipy available: True (Wilcoxon computed). matplotlib available: True (plots generated).
## 5. Main results
| method | n | mean_pi | median_pi | std_pi | iqr_pi | mean_final_gap | median_final_gap | mean_bootstrap_time_ms | median_bootstrap_time_ms | mean_moved_ops_frac | optimality_proof_rate | feasibility_failure_rate | n_all | n_errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpsat_warm | 560 | 0.0218 | 0.0149 | 0.0228 | 0.0251 | 0.0061 | 0.0000 | 0.0000 | 0.0000 | 0.6347 | 0.0000 | 0.0000 | 560 | 0 |
| boot_warm | 560 | 0.0229 | 0.0216 | 0.0144 | 0.0199 | 0.0096 | 0.0043 | 0.0000 | 0.0000 | 0.8726 | 0.0000 | 0.0000 | 560 | 0 |
| boot_cold | 560 | 0.0300 | 0.0280 | 0.0167 | 0.0223 | 0.0156 | 0.0118 | 0.0000 | 0.0000 | 0.8546 | 0.0000 | 0.0000 | 560 | 0 |
| cpsat_cold | 560 | 0.0480 | 0.0460 | 0.0197 | 0.0267 | 0.0176 | 0.0136 | 0.0000 | 0.0000 | 0.9460 | 0.0000 | 0.0000 | 560 | 0 |
## 6. Tables
### Pairwise vs cpsat_cold
| method | n_common | pi_win | pi_tie | pi_loss | final_gap_win | final_gap_tie | final_gap_loss | stability_win | stability_tie | stability_loss | sign_test_p | wilcoxon_p | mean_pi_improvement | ci95_lo | ci95_hi | sign_test_p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cpsat_warm | 560 | 483 | 0 | 77 | 362 | 77 | 121 | 276 | 21 | 183 | 0.0000 | 0.0000 | 0.0261 | 0.0236 | 0.0286 | 0.0000 |
| boot_warm | 560 | 473 | 0 | 87 | 314 | 82 | 164 | 253 | 26 | 201 | 0.0000 | 0.0000 | 0.0251 | 0.0234 | 0.0268 | 0.0000 |
| boot_cold | 560 | 494 | 0 | 66 | 115 | 400 | 45 | 145 | 274 | 61 | 0.0000 | 0.0000 | 0.0180 | 0.0166 | 0.0193 | 0.0000 |
### Breakdown by delta_kind
| method | delta_kind | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | arrival | 0.0109 | 0.0040 | 280 |
| boot_warm | arrival | 0.0273 | 0.0138 | 280 |
| boot_cold | arrival | 0.0356 | 0.0208 | 280 |
| cpsat_cold | arrival | 0.0527 | 0.0215 | 280 |
| cpsat_warm | base | 0.0270 | 0.0002 | 80 |
| cpsat_cold | base | 0.0276 | 0.0007 | 80 |
| boot_cold | base | 0.0279 | 0.0012 | 80 |
| boot_warm | base | 0.0280 | 0.0014 | 80 |
| boot_warm | cancellation | 0.0139 | 0.0067 | 70 |
| cpsat_warm | cancellation | 0.0168 | 0.0061 | 70 |
| boot_cold | cancellation | 0.0220 | 0.0129 | 70 |
| cpsat_cold | cancellation | 0.0473 | 0.0186 | 70 |
| boot_warm | duration_jitter | 0.0144 | 0.0078 | 100 |
| boot_cold | duration_jitter | 0.0227 | 0.0154 | 100 |
| cpsat_warm | duration_jitter | 0.0449 | 0.0149 | 100 |
| cpsat_cold | duration_jitter | 0.0520 | 0.0207 | 100 |
| boot_warm | outage | 0.0179 | 0.0054 | 30 |
| boot_cold | outage | 0.0266 | 0.0133 | 30 |
| cpsat_warm | outage | 0.0451 | 0.0121 | 30 |
| cpsat_cold | outage | 0.0466 | 0.0131 | 30 |
### Breakdown by severity
| method | severity | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | medium | 0.0218 | 0.0061 | 560 |
| boot_warm | medium | 0.0229 | 0.0096 | 560 |
| boot_cold | medium | 0.0300 | 0.0156 | 560 |
| cpsat_cold | medium | 0.0480 | 0.0176 | 560 |
### Breakdown by budget_s
| method | budget_s | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | 8 | 0.0218 | 0.0061 | 560 |
| boot_warm | 8 | 0.0229 | 0.0096 | 560 |
| boot_cold | 8 | 0.0300 | 0.0156 | 560 |
| cpsat_cold | 8 | 0.0480 | 0.0176 | 560 |
### Breakdown by workers
| method | workers | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | 1 | 0.0218 | 0.0061 | 560 |
| boot_warm | 1 | 0.0229 | 0.0096 | 560 |
| boot_cold | 1 | 0.0300 | 0.0156 | 560 |
| cpsat_cold | 1 | 0.0480 | 0.0176 | 560 |
### Breakdown by instance_size
| method | instance_size | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | ta01_15x15 | 0.0134 | 0.0015 | 28 |
| boot_warm | ta01_15x15 | 0.0221 | 0.0104 | 28 |
| boot_cold | ta01_15x15 | 0.0331 | 0.0195 | 28 |
| cpsat_cold | ta01_15x15 | 0.0436 | 0.0123 | 28 |
| cpsat_warm | ta02_15x15 | 0.0168 | 0.0067 | 28 |
| boot_warm | ta02_15x15 | 0.0196 | 0.0080 | 28 |
| boot_cold | ta02_15x15 | 0.0256 | 0.0144 | 28 |
| cpsat_cold | ta02_15x15 | 0.0339 | 0.0102 | 28 |
| cpsat_warm | ta03_15x15 | 0.0153 | 0.0038 | 28 |
| boot_warm | ta03_15x15 | 0.0225 | 0.0097 | 28 |
| boot_cold | ta03_15x15 | 0.0308 | 0.0209 | 28 |
| cpsat_cold | ta03_15x15 | 0.0489 | 0.0256 | 28 |
| boot_warm | ta04_15x15 | 0.0184 | 0.0101 | 28 |
| cpsat_warm | ta04_15x15 | 0.0248 | 0.0106 | 28 |
| boot_cold | ta04_15x15 | 0.0296 | 0.0168 | 28 |
| cpsat_cold | ta04_15x15 | 0.0533 | 0.0196 | 28 |
| cpsat_warm | ta05_15x15 | 0.0112 | 0.0007 | 28 |
| boot_warm | ta05_15x15 | 0.0246 | 0.0125 | 28 |
| boot_cold | ta05_15x15 | 0.0260 | 0.0138 | 28 |
| cpsat_cold | ta05_15x15 | 0.0480 | 0.0174 | 28 |
| cpsat_warm | ta06_15x15 | 0.0102 | 0.0033 | 28 |
| boot_cold | ta06_15x15 | 0.0183 | 0.0070 | 28 |
| boot_warm | ta06_15x15 | 0.0188 | 0.0117 | 28 |
| cpsat_cold | ta06_15x15 | 0.0277 | 0.0090 | 28 |
| cpsat_warm | ta07_15x15 | 0.0135 | 0.0027 | 28 |
| boot_warm | ta07_15x15 | 0.0194 | 0.0094 | 28 |
| boot_cold | ta07_15x15 | 0.0238 | 0.0108 | 28 |
| cpsat_cold | ta07_15x15 | 0.0446 | 0.0148 | 28 |
| cpsat_warm | ta08_15x15 | 0.0152 | 0.0032 | 28 |
| boot_warm | ta08_15x15 | 0.0196 | 0.0109 | 28 |
| boot_cold | ta08_15x15 | 0.0266 | 0.0155 | 28 |
| cpsat_cold | ta08_15x15 | 0.0440 | 0.0183 | 28 |
| cpsat_warm | ta09_15x15 | 0.0138 | 0.0036 | 28 |
| boot_warm | ta09_15x15 | 0.0214 | 0.0107 | 28 |
| boot_cold | ta09_15x15 | 0.0279 | 0.0153 | 28 |
| cpsat_cold | ta09_15x15 | 0.0459 | 0.0194 | 28 |
| cpsat_warm | ta10_15x15 | 0.0165 | 0.0053 | 28 |
| boot_warm | ta10_15x15 | 0.0244 | 0.0094 | 28 |
| boot_cold | ta10_15x15 | 0.0301 | 0.0148 | 28 |
| cpsat_cold | ta10_15x15 | 0.0461 | 0.0175 | 28 |
| boot_cold | ta11_20x15 | 0.0176 | 0.0044 | 28 |
| boot_warm | ta11_20x15 | 0.0197 | 0.0075 | 28 |
| cpsat_warm | ta11_20x15 | 0.0332 | 0.0120 | 28 |
| cpsat_cold | ta11_20x15 | 0.0433 | 0.0084 | 28 |
| boot_warm | ta12_20x15 | 0.0221 | 0.0067 | 28 |
| cpsat_warm | ta12_20x15 | 0.0317 | 0.0118 | 28 |
| boot_cold | ta12_20x15 | 0.0380 | 0.0200 | 28 |
| cpsat_cold | ta12_20x15 | 0.0620 | 0.0237 | 28 |
| boot_warm | ta13_20x15 | 0.0277 | 0.0105 | 28 |
| cpsat_warm | ta13_20x15 | 0.0298 | 0.0047 | 28 |
| boot_cold | ta13_20x15 | 0.0418 | 0.0260 | 28 |
| cpsat_cold | ta13_20x15 | 0.0599 | 0.0271 | 28 |
| boot_warm | ta14_20x15 | 0.0237 | 0.0091 | 28 |
| cpsat_warm | ta14_20x15 | 0.0260 | 0.0070 | 28 |
| boot_cold | ta14_20x15 | 0.0303 | 0.0129 | 28 |
| cpsat_cold | ta14_20x15 | 0.0470 | 0.0139 | 28 |
| cpsat_warm | ta15_20x15 | 0.0260 | 0.0056 | 28 |
| boot_warm | ta15_20x15 | 0.0270 | 0.0098 | 28 |
| boot_cold | ta15_20x15 | 0.0288 | 0.0124 | 28 |
| cpsat_cold | ta15_20x15 | 0.0457 | 0.0137 | 28 |
| boot_warm | ta16_20x15 | 0.0222 | 0.0075 | 28 |
| cpsat_warm | ta16_20x15 | 0.0280 | 0.0063 | 28 |
| boot_cold | ta16_20x15 | 0.0300 | 0.0166 | 28 |
| cpsat_cold | ta16_20x15 | 0.0471 | 0.0195 | 28 |
| boot_warm | ta17_20x15 | 0.0207 | 0.0045 | 28 |
| cpsat_warm | ta17_20x15 | 0.0242 | 0.0069 | 28 |
| boot_cold | ta17_20x15 | 0.0380 | 0.0228 | 28 |
| cpsat_cold | ta17_20x15 | 0.0574 | 0.0239 | 28 |
| cpsat_warm | ta18_20x15 | 0.0251 | 0.0079 | 28 |
| boot_warm | ta18_20x15 | 0.0261 | 0.0125 | 28 |
| boot_cold | ta18_20x15 | 0.0274 | 0.0100 | 28 |
| cpsat_cold | ta18_20x15 | 0.0476 | 0.0119 | 28 |
| cpsat_warm | ta19_20x15 | 0.0281 | 0.0069 | 28 |
| boot_warm | ta19_20x15 | 0.0314 | 0.0153 | 28 |
| boot_cold | ta19_20x15 | 0.0395 | 0.0225 | 28 |
| cpsat_cold | ta19_20x15 | 0.0574 | 0.0275 | 28 |
| boot_warm | ta20_20x15 | 0.0267 | 0.0061 | 28 |
| cpsat_warm | ta20_20x15 | 0.0341 | 0.0109 | 28 |
| boot_cold | ta20_20x15 | 0.0366 | 0.0163 | 28 |
| cpsat_cold | ta20_20x15 | 0.0559 | 0.0181 | 28 |
### Breakdown by objective
| method | objective | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | makespan | 0.0218 | 0.0061 | 560 |
| boot_warm | makespan | 0.0229 | 0.0096 | 560 |
| boot_cold | makespan | 0.0300 | 0.0156 | 560 |
| cpsat_cold | makespan | 0.0480 | 0.0176 | 560 |
### Breakdown by bootstrap_policy
| method | bootstrap_policy | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | append | 0.0218 | 0.0061 | 560 |
| boot_warm | append | 0.0229 | 0.0096 | 560 |
| boot_cold | append | 0.0300 | 0.0156 | 560 |
| cpsat_cold | append | 0.0480 | 0.0176 | 560 |
### Breakdown by stream_step
| method | stream_step | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | 0 | 0.0270 | 0.0002 | 80 |
| cpsat_cold | 0 | 0.0276 | 0.0007 | 80 |
| boot_cold | 0 | 0.0279 | 0.0012 | 80 |
| boot_warm | 0 | 0.0280 | 0.0014 | 80 |
| cpsat_warm | 1 | 0.0203 | 0.0064 | 80 |
| boot_warm | 1 | 0.0235 | 0.0100 | 80 |
| boot_cold | 1 | 0.0303 | 0.0169 | 80 |
| cpsat_cold | 1 | 0.0496 | 0.0173 | 80 |
| cpsat_warm | 2 | 0.0199 | 0.0083 | 80 |
| boot_warm | 2 | 0.0256 | 0.0133 | 80 |
| boot_cold | 2 | 0.0336 | 0.0180 | 80 |
| cpsat_cold | 2 | 0.0493 | 0.0185 | 80 |
| cpsat_warm | 3 | 0.0093 | 0.0025 | 80 |
| boot_warm | 3 | 0.0250 | 0.0117 | 80 |
| boot_cold | 3 | 0.0335 | 0.0208 | 80 |
| cpsat_cold | 3 | 0.0538 | 0.0224 | 80 |
| boot_warm | 4 | 0.0170 | 0.0086 | 80 |
| cpsat_warm | 4 | 0.0250 | 0.0085 | 80 |
| boot_cold | 4 | 0.0268 | 0.0184 | 80 |
| cpsat_cold | 4 | 0.0536 | 0.0226 | 80 |
| boot_warm | 5 | 0.0245 | 0.0133 | 80 |
| cpsat_warm | 5 | 0.0245 | 0.0083 | 80 |
| boot_cold | 5 | 0.0336 | 0.0193 | 80 |
| cpsat_cold | 5 | 0.0520 | 0.0210 | 80 |
| boot_warm | 6 | 0.0167 | 0.0091 | 80 |
| boot_cold | 6 | 0.0243 | 0.0148 | 80 |
| cpsat_warm | 6 | 0.0268 | 0.0083 | 80 |
| cpsat_cold | 6 | 0.0499 | 0.0205 | 80 |
## 7. Figures
- results/icaps/analysis_taillard/figures/final_gap_boxplot.pdf
- results/icaps/analysis_taillard/figures/pi_scatter.pdf
## 8. Interpretation
- **Where it helps:** `cpsat_warm` shows the largest mean PI improvement over `cpsat_cold` (0.0261, 483W/0T/77L, sign-test p=0.0000).
- **Where it weakens:** `boot_cold` shows the smallest/negative mean PI improvement (0.0180).
- **Arrivals:** cpsat_warm=0.0109, boot_warm=0.0273, boot_cold=0.0356, cpsat_cold=0.0527 (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).
- **Multi-worker:** not exercised in this pass (workers=1 only); this is a known, explicitly flagged limitation, not a claim.
## 9. ICAPS paper recommendation
**Ready:** the method (boot_cold), the domination guarantee (in its precise form -- see below), the pilot primal-integral result on job-shop across 7 seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and the benchmark/loader infrastructure.

**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/worker counts) for the actual paper table; `workers` preset specifically to characterize whether gains shrink under CP-SAT's own multi-worker portfolio search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only activates with workers>1); `arrivals` preset to confirm gap_insert/regret_insert/beam_insert close the arrival weak case at scale, not just in the single case checked by unit tests.

**Strongest claim supported by data so far:** a near-zero-cost constructive repair of the previous schedule, kept as an anytime floor under an unmodified CP-SAT solve, improves primal integral, replicated across seeds and domains (BOOT_COLD_PAPER.md).

**Domination guarantee -- precise form (do not overstate):** boot_cold's final objective is provably never worse than **its own unmodified continuation** (same run, same budget window) -- this is a theorem, not an empirical tendency. It is *not* an exact guarantee against a *separately invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 re-analysis) boot_cold's final objective was strictly worse than an independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%), attributable to wall-clock non-reproducibility, not a flaw in the proof. State the theorem in its precise form; report the 92.4% empirical non-loss rate as a strong-but-not-absolute finding, never as "provably never worse than cold-solving."

**Claims to avoid:** this is not a machine-learning method; CP-SAT's own search is not improved or sped to proof; final objective is not usually better (ties are the norm, by design); "provably never worse than cold" (only true against its own continuation, see above); weak cases (arrivals, and any case not yet run at the `main`/`workers`/`budgets` scale) should not be papered over.
