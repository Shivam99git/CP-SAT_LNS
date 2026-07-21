# ICAPS Experiment Report
Generated from 9306 result rows (9306 ok, 0 errors).
## 1. Executive summary
Best method by mean primal integral: **boot_cold** (mean PI 0.0170) vs baseline `cpsat_cold` (mean PI 0.0227).
## 2. What was implemented
Full ICAPS baseline menu (19 job-shop methods incl. 5 dispatch rules, 3 fix-and-optimize freeze fractions, LNS-from-floor, approximate local branching, micro-CP repair), 6 new severity-scaled deltas, 4 arrival-specific bootstrap floor policies, static benchmark loaders, an RCPSP second domain, and stability metrics -- see docs/icaps_experiment_plan.md.
## 3. What experiments were run
- `arrivals`: 864 rows
- `paper_main`: 4950 rows
- `pilot`: 756 rows
- `real_benchmarks`: 2160 rows
- `smoke`: 16 rows
- `workers`: 560 rows
## 4. Failed / unfinished parts
No row-level errors in this data.

Not executed in this pass (compute cost appropriate for an unattended multi-day run; grids validated via `--dry-run`, not run): `main`, `ablation`, `severity`, `workers`, `budgets`, `arrivals` presets beyond what appears in the loaded CSVs above. RCPSP tardiness/weighted-tardiness objectives, JSSP `precedence_change`/`partial_schedule_freeze`-for-RCPSP are documented TODOs, not implemented.
scipy available: True (Wilcoxon computed). matplotlib available: True (plots generated).
## 5. Main results
| method | n | mean_pi | median_pi | std_pi | iqr_pi | mean_final_gap | median_final_gap | mean_bootstrap_time_ms | median_bootstrap_time_ms | mean_moved_ops_frac | optimality_proof_rate | feasibility_failure_rate | n_all | n_errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_cold | 1547 | 0.0170 | 0.0110 | 0.0188 | 0.0279 | 0.0039 | 0.0000 | 0.0000 | 0.0000 | 0.8323 | 0.0000 | 0.0000 | 1547 | 0 |
| cpsat_cold | 1547 | 0.0227 | 0.0169 | 0.0230 | 0.0340 | 0.0045 | 0.0000 | 0.0000 | 0.0000 | 0.8644 | 0.0000 | 0.0000 | 1547 | 0 |
| boot_warm | 1543 | 0.0242 | 0.0113 | 0.0360 | 0.0367 | 0.0045 | 0.0000 | 0.0000 | 0.0000 | 0.8370 | 0.0000 | 0.0000 | 1543 | 0 |
| cpsat_warm | 1255 | 0.0246 | 0.0082 | 0.0330 | 0.0378 | 0.0067 | 0.0000 | 0.0000 | 0.0000 | 0.7898 | 0.0000 | 0.0000 | 1255 | 0 |
| lns_prev_solution | 495 | 0.0662 | 0.0565 | 0.0515 | 0.0698 | 0.0367 | 0.0304 | 0.4891 | 0.3258 | 0.6998 | 0.0000 | 0.0000 | 495 | 0 |
| fix_and_optimize_50 | 495 | 0.1215 | 0.1079 | 0.0694 | 0.0880 | 0.1188 | 0.1061 | 0.5053 | 0.3560 | 0.4408 | 1.0000 | 0.0000 | 495 | 0 |
| dispatch_mwkr | 603 | 0.1523 | 0.1465 | 0.0541 | 0.0707 | 0.1521 | 0.1464 | 2.3080 | 1.7220 | 0.5918 | 0.0000 | 0.0000 | 603 | 0 |
| greedy_from_scratch | 4 | 0.1625 | 0.0982 | 0.1416 | 0.0959 | 0.1623 | 0.0980 | 0.0447 | 0.0445 | 0.6800 | 0.0000 | 0.0000 | 4 | 0 |
| local_branching_prev | 495 | 0.2238 | 0.2291 | 0.1387 | 0.2137 | 0.1496 | 0.1434 | 7.8591 | 7.3570 | 0.2784 | 0.1657 | 0.0000 | 495 | 0 |
| dispatch_spt | 603 | 0.2467 | 0.2325 | 0.0905 | 0.1197 | 0.2464 | 0.2321 | 2.1397 | 1.5898 | 0.6305 | 0.0000 | 0.0000 | 603 | 0 |
| repair_only | 719 | 0.9327 | 0.8438 | 0.6135 | 0.8964 | 0.9327 | 0.8438 | 0.4253 | 0.2070 | 0.2488 | 0.0000 | 0.0000 | 719 | 0 |
## 6. Tables
### Pairwise vs cpsat_cold
| method | n_common | pi_win | pi_tie | pi_loss | final_gap_win | final_gap_tie | final_gap_loss | stability_win | stability_tie | stability_loss | sign_test_p | wilcoxon_p | mean_pi_improvement | ci95_lo | ci95_hi | sign_test_p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| boot_cold | 1547 | 1313 | 0 | 234 | 135 | 1327 | 85 | 285 | 902 | 188 | 0.0000 | 0.0000 | 0.0057 | 0.0051 | 0.0062 | 0.0000 |
| boot_warm | 1543 | 964 | 0 | 579 | 244 | 1074 | 225 | 671 | 102 | 599 | 0.0000 | 0.0000 | -0.0015 | -0.0031 | 0.0001 | 0.0000 |
| cpsat_warm | 1255 | 685 | 0 | 570 | 204 | 782 | 269 | 540 | 97 | 479 | 0.0013 | 0.5218 | -0.0030 | -0.0041 | -0.0018 | 0.0026 |
| lns_prev_solution | 495 | 121 | 0 | 374 | 71 | 45 | 379 | 426 | 4 | 20 | 0.0000 | 0.0000 | -0.0292 | -0.0334 | -0.0252 | 0.0000 |
| fix_and_optimize_50 | 495 | 65 | 0 | 430 | 13 | 1 | 481 | 445 | 0 | 5 | 0.0000 | 0.0000 | -0.0845 | -0.0917 | -0.0774 | 0.0000 |
| dispatch_mwkr | 603 | 1 | 0 | 602 | 0 | 0 | 603 | 526 | 0 | 14 | 0.0000 | 0.0000 | -0.1186 | -0.1236 | -0.1136 | 0.0000 |
| greedy_from_scratch | 4 | 0 | 0 | 4 | 0 | 0 | 4 | 1 | 1 | 1 | 0.1250 | 0.1250 | -0.1545 | -0.2904 | -0.0749 | 0.1250 |
| local_branching_prev | 495 | 27 | 0 | 468 | 13 | 41 | 441 | 449 | 0 | 1 | 0.0000 | 0.0000 | -0.1868 | -0.1980 | -0.1761 | 0.0000 |
| dispatch_spt | 603 | 0 | 0 | 603 | 0 | 0 | 603 | 525 | 2 | 13 | 0.0000 | 0.0000 | -0.2130 | -0.2202 | -0.2055 | 0.0000 |
| repair_only | 719 | 0 | 0 | 719 | 0 | 0 | 719 | 627 | 4 | 8 | 0.0000 | 0.0000 | -0.8993 | -0.9475 | -0.8573 | 0.0000 |
### Breakdown by delta_kind
| method | delta_kind | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | arrival | 0.0208 | 0.0043 | 453 |
| cpsat_cold | arrival | 0.0232 | 0.0043 | 453 |
| cpsat_warm | arrival | 0.0282 | 0.0071 | 393 |
| boot_warm | arrival | 0.0334 | 0.0076 | 453 |
| lns_prev_solution | arrival | 0.0922 | 0.0294 | 163 |
| fix_and_optimize_50 | arrival | 0.1255 | 0.1217 | 163 |
| dispatch_mwkr | arrival | 0.1489 | 0.1486 | 196 |
| local_branching_prev | arrival | 0.2510 | 0.1636 | 163 |
| dispatch_spt | arrival | 0.2608 | 0.2606 | 196 |
| repair_only | arrival | 1.2547 | 1.2547 | 236 |
| cpsat_warm | base | 0.0178 | 0.0027 | 139 |
| boot_cold | base | 0.0180 | 0.0024 | 172 |
| boot_warm | base | 0.0185 | 0.0026 | 171 |
| cpsat_cold | base | 0.0186 | 0.0025 | 172 |
| local_branching_prev | base | 0.0263 | 0.0042 | 45 |
| fix_and_optimize_50 | base | 0.0664 | 0.0626 | 45 |
| lns_prev_solution | base | 0.0880 | 0.0490 | 45 |
| dispatch_mwkr | base | 0.1417 | 0.1415 | 63 |
| dispatch_spt | base | 0.2225 | 0.2223 | 63 |
| repair_only | base | 0.2417 | 0.2414 | 80 |
| greedy_from_scratch | base | 0.3737 | 0.3735 | 1 |
| boot_cold | batch_arrival | 0.0231 | 0.0000 | 132 |
| cpsat_cold | batch_arrival | 0.0262 | 0.0000 | 132 |
| boot_warm | batch_arrival | 0.0561 | 0.0000 | 132 |
| boot_warm | cancellation | 0.0120 | 0.0049 | 251 |
| boot_cold | cancellation | 0.0146 | 0.0060 | 251 |
| cpsat_warm | cancellation | 0.0157 | 0.0058 | 251 |
| cpsat_cold | cancellation | 0.0241 | 0.0071 | 251 |
| lns_prev_solution | cancellation | 0.0464 | 0.0382 | 106 |
| fix_and_optimize_50 | cancellation | 0.1191 | 0.1172 | 106 |
| dispatch_mwkr | cancellation | 0.1537 | 0.1534 | 130 |
| local_branching_prev | cancellation | 0.2010 | 0.1475 | 106 |
| dispatch_spt | cancellation | 0.2411 | 0.2408 | 130 |
| repair_only | cancellation | 0.8100 | 0.8100 | 162 |
| boot_warm | duration_jitter | 0.0101 | 0.0037 | 281 |
| boot_cold | duration_jitter | 0.0124 | 0.0054 | 282 |
| cpsat_cold | duration_jitter | 0.0240 | 0.0070 | 282 |
| cpsat_warm | duration_jitter | 0.0330 | 0.0099 | 281 |
| lns_prev_solution | duration_jitter | 0.0466 | 0.0385 | 124 |
| greedy_from_scratch | duration_jitter | 0.0833 | 0.0831 | 1 |
| fix_and_optimize_50 | duration_jitter | 0.1305 | 0.1286 | 124 |
| dispatch_mwkr | duration_jitter | 0.1552 | 0.1550 | 133 |
| dispatch_spt | duration_jitter | 0.2452 | 0.2450 | 133 |
| local_branching_prev | duration_jitter | 0.2645 | 0.1730 | 124 |
| repair_only | duration_jitter | 0.9848 | 0.9848 | 158 |
| boot_cold | outage | 0.0107 | 0.0033 | 193 |
| boot_warm | outage | 0.0116 | 0.0038 | 191 |
| cpsat_cold | outage | 0.0173 | 0.0040 | 193 |
| cpsat_warm | outage | 0.0215 | 0.0053 | 191 |
| lns_prev_solution | outage | 0.0542 | 0.0414 | 57 |
| greedy_from_scratch | outage | 0.0965 | 0.0963 | 2 |
| fix_and_optimize_50 | outage | 0.1386 | 0.1364 | 57 |
| dispatch_mwkr | outage | 0.1620 | 0.1617 | 81 |
| dispatch_spt | outage | 0.2427 | 0.2425 | 81 |
| local_branching_prev | outage | 0.2561 | 0.1775 | 57 |
| repair_only | outage | 0.8237 | 0.8237 | 83 |
| boot_cold | rush_job | 0.0244 | 0.0000 | 64 |
| cpsat_cold | rush_job | 0.0286 | 0.0000 | 64 |
| boot_warm | rush_job | 0.0557 | 0.0000 | 64 |
### Breakdown by severity
| method | severity | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | extreme | 0.0195 | 0.0000 | 72 |
| cpsat_cold | extreme | 0.0268 | 0.0000 | 72 |
| boot_warm | extreme | 0.0470 | 0.0000 | 72 |
| boot_cold | high | 0.0245 | 0.0000 | 72 |
| cpsat_cold | high | 0.0269 | 0.0000 | 72 |
| boot_warm | high | 0.0478 | 0.0000 | 72 |
| boot_cold | low | 0.0249 | 0.0000 | 76 |
| cpsat_cold | low | 0.0273 | 0.0000 | 76 |
| boot_warm | low | 0.0516 | 0.0000 | 72 |
| greedy_from_scratch | low | 0.1625 | 0.1623 | 4 |
| repair_only | low | 0.3523 | 0.3522 | 4 |
| boot_cold | medium | 0.0160 | 0.0045 | 1327 |
| boot_warm | medium | 0.0202 | 0.0052 | 1327 |
| cpsat_cold | medium | 0.0220 | 0.0052 | 1327 |
| cpsat_warm | medium | 0.0246 | 0.0067 | 1255 |
| lns_prev_solution | medium | 0.0662 | 0.0367 | 495 |
| fix_and_optimize_50 | medium | 0.1215 | 0.1188 | 495 |
| dispatch_mwkr | medium | 0.1523 | 0.1521 | 603 |
| local_branching_prev | medium | 0.2238 | 0.1496 | 495 |
| dispatch_spt | medium | 0.2467 | 0.2464 | 603 |
| repair_only | medium | 0.9359 | 0.9359 | 715 |
### Breakdown by budget_s
| method | budget_s | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | 0.2000 | 0.0025 | 0.0000 | 4 |
| cpsat_cold | 0.2000 | 0.0080 | 0.0000 | 4 |
| greedy_from_scratch | 0.2000 | 0.1625 | 0.1623 | 4 |
| repair_only | 0.2000 | 0.3523 | 0.3522 | 4 |
| boot_cold | 1.0000 | 0.0255 | 0.0038 | 36 |
| cpsat_cold | 1.0000 | 0.0347 | 0.0039 | 36 |
| cpsat_warm | 1.0000 | 0.0403 | 0.0091 | 36 |
| boot_warm | 1.0000 | 0.0419 | 0.0117 | 36 |
| dispatch_mwkr | 1.0000 | 0.1547 | 0.1542 | 36 |
| dispatch_spt | 1.0000 | 0.2587 | 0.2582 | 36 |
| repair_only | 1.0000 | 0.6507 | 0.6506 | 36 |
| boot_warm | 2.0000 | 0.0282 | 0.0078 | 56 |
| boot_cold | 2.0000 | 0.0311 | 0.0099 | 56 |
| cpsat_warm | 2.0000 | 0.0345 | 0.0086 | 56 |
| cpsat_cold | 2.0000 | 0.0423 | 0.0127 | 56 |
| repair_only | 2.0000 | 0.8450 | 0.8450 | 56 |
| cpsat_warm | 5.0000 | 0.0142 | 0.0018 | 36 |
| boot_cold | 5.0000 | 0.0225 | 0.0002 | 324 |
| cpsat_cold | 5.0000 | 0.0260 | 0.0002 | 324 |
| boot_warm | 5.0000 | 0.0460 | 0.0003 | 324 |
| dispatch_mwkr | 5.0000 | 0.1639 | 0.1638 | 36 |
| dispatch_spt | 5.0000 | 0.2686 | 0.2685 | 36 |
| repair_only | 5.0000 | 0.6643 | 0.6643 | 36 |
| boot_cold | 8.0000 | 0.0148 | 0.0048 | 1091 |
| boot_warm | 8.0000 | 0.0175 | 0.0054 | 1091 |
| cpsat_cold | 8.0000 | 0.0208 | 0.0055 | 1091 |
| cpsat_warm | 8.0000 | 0.0244 | 0.0068 | 1091 |
| lns_prev_solution | 8.0000 | 0.0662 | 0.0367 | 495 |
| fix_and_optimize_50 | 8.0000 | 0.1215 | 0.1188 | 495 |
| dispatch_mwkr | 8.0000 | 0.1502 | 0.1499 | 495 |
| local_branching_prev | 8.0000 | 0.2238 | 0.1496 | 495 |
| dispatch_spt | 8.0000 | 0.2423 | 0.2421 | 495 |
| repair_only | 8.0000 | 0.9990 | 0.9990 | 551 |
| boot_cold | 10.0000 | 0.0071 | 0.0006 | 36 |
| boot_warm | 10.0000 | 0.0091 | 0.0018 | 36 |
| cpsat_cold | 10.0000 | 0.0092 | 0.0009 | 36 |
| cpsat_warm | 10.0000 | 0.0105 | 0.0020 | 36 |
| dispatch_mwkr | 10.0000 | 0.1680 | 0.1679 | 36 |
| dispatch_spt | 10.0000 | 0.2728 | 0.2728 | 36 |
| repair_only | 10.0000 | 0.6698 | 0.6697 | 36 |
### Breakdown by workers
| method | workers | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | 1 | 0.0167 | 0.0037 | 1463 |
| cpsat_cold | 1 | 0.0222 | 0.0042 | 1463 |
| boot_warm | 1 | 0.0246 | 0.0044 | 1459 |
| cpsat_warm | 1 | 0.0248 | 0.0068 | 1171 |
| lns_prev_solution | 1 | 0.0662 | 0.0367 | 495 |
| fix_and_optimize_50 | 1 | 0.1215 | 0.1188 | 495 |
| dispatch_mwkr | 1 | 0.1523 | 0.1521 | 603 |
| greedy_from_scratch | 1 | 0.1625 | 0.1623 | 4 |
| local_branching_prev | 1 | 0.2238 | 0.1496 | 495 |
| dispatch_spt | 1 | 0.2467 | 0.2464 | 603 |
| repair_only | 1 | 0.9409 | 0.9409 | 635 |
| boot_warm | 4 | 0.0163 | 0.0058 | 28 |
| cpsat_warm | 4 | 0.0205 | 0.0073 | 28 |
| boot_cold | 4 | 0.0228 | 0.0084 | 28 |
| cpsat_cold | 4 | 0.0309 | 0.0102 | 28 |
| repair_only | 4 | 0.8685 | 0.8685 | 28 |
| boot_warm | 8 | 0.0162 | 0.0040 | 28 |
| cpsat_warm | 8 | 0.0207 | 0.0047 | 28 |
| boot_cold | 8 | 0.0222 | 0.0062 | 28 |
| cpsat_cold | 8 | 0.0289 | 0.0081 | 28 |
| repair_only | 8 | 0.8712 | 0.8712 | 28 |
| boot_warm | 16 | 0.0200 | 0.0056 | 28 |
| cpsat_warm | 16 | 0.0235 | 0.0040 | 28 |
| boot_cold | 16 | 0.0237 | 0.0066 | 28 |
| cpsat_cold | 16 | 0.0352 | 0.0086 | 28 |
| repair_only | 16 | 0.8714 | 0.8714 | 28 |
### Breakdown by instance_size
| method | instance_size | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | 10x10 | 0.0080 | 0.0005 | 219 |
| cpsat_cold | 10x10 | 0.0094 | 0.0001 | 219 |
| boot_warm | 10x10 | 0.0106 | 0.0013 | 219 |
| cpsat_warm | 10x10 | 0.0136 | 0.0015 | 219 |
| lns_prev_solution | 10x10 | 0.0323 | 0.0240 | 165 |
| local_branching_prev | 10x10 | 0.1041 | 0.0665 | 165 |
| fix_and_optimize_50 | 10x10 | 0.1456 | 0.1447 | 165 |
| dispatch_mwkr | 10x10 | 0.1702 | 0.1701 | 219 |
| dispatch_spt | 10x10 | 0.2529 | 0.2528 | 219 |
| repair_only | 10x10 | 1.0127 | 1.0127 | 219 |
| boot_cold | 15x15 | 0.0263 | 0.0046 | 619 |
| cpsat_cold | 15x15 | 0.0329 | 0.0056 | 619 |
| cpsat_warm | 15x15 | 0.0408 | 0.0112 | 331 |
| boot_warm | 15x15 | 0.0415 | 0.0059 | 619 |
| lns_prev_solution | 15x15 | 0.0816 | 0.0427 | 165 |
| fix_and_optimize_50 | 15x15 | 0.1295 | 0.1268 | 165 |
| dispatch_mwkr | 15x15 | 0.1519 | 0.1516 | 219 |
| local_branching_prev | 15x15 | 0.2495 | 0.1612 | 165 |
| dispatch_spt | 15x15 | 0.2568 | 0.2565 | 219 |
| repair_only | 15x15 | 0.9633 | 0.9632 | 331 |
| boot_cold | 20x20 | 0.0395 | 0.0173 | 165 |
| boot_warm | 20x20 | 0.0470 | 0.0163 | 165 |
| cpsat_cold | 20x20 | 0.0578 | 0.0186 | 165 |
| cpsat_warm | 20x20 | 0.0745 | 0.0248 | 165 |
| lns_prev_solution | 20x20 | 0.0848 | 0.0435 | 165 |
| fix_and_optimize_50 | 20x20 | 0.0894 | 0.0849 | 165 |
| dispatch_mwkr | 20x20 | 0.1292 | 0.1288 | 165 |
| dispatch_spt | 20x20 | 0.2250 | 0.2247 | 165 |
| local_branching_prev | 20x20 | 0.3179 | 0.2210 | 165 |
| repair_only | 20x20 | 0.7793 | 0.7793 | 165 |
| boot_cold | 5x5 | 0.0025 | 0.0000 | 4 |
| cpsat_cold | 5x5 | 0.0080 | 0.0000 | 4 |
| greedy_from_scratch | 5x5 | 0.1625 | 0.1623 | 4 |
| repair_only | 5x5 | 0.3523 | 0.3522 | 4 |
| boot_warm | abz5_10x10 | 0.0027 | 0.0000 | 54 |
| boot_cold | abz5_10x10 | 0.0029 | 0.0000 | 54 |
| cpsat_warm | abz5_10x10 | 0.0037 | 0.0000 | 54 |
| cpsat_cold | abz5_10x10 | 0.0052 | 0.0000 | 54 |
| boot_warm | abz6_10x10 | 0.0003 | 0.0000 | 54 |
| boot_cold | abz6_10x10 | 0.0004 | 0.0000 | 54 |
| cpsat_warm | abz6_10x10 | 0.0012 | 0.0000 | 54 |
| cpsat_cold | abz6_10x10 | 0.0014 | 0.0000 | 54 |
| boot_cold | ft06_6x6 | 0.0001 | 0.0000 | 54 |
| boot_warm | ft06_6x6 | 0.0002 | 0.0000 | 54 |
| cpsat_cold | ft06_6x6 | 0.0003 | 0.0000 | 54 |
| cpsat_warm | ft06_6x6 | 0.0003 | 0.0000 | 54 |
| boot_cold | ft10_10x10 | 0.0134 | 0.0021 | 54 |
| boot_warm | ft10_10x10 | 0.0146 | 0.0034 | 54 |
| cpsat_warm | ft10_10x10 | 0.0146 | 0.0030 | 54 |
| cpsat_cold | ft10_10x10 | 0.0167 | 0.0006 | 54 |
| boot_warm | ft20_20x5 | 0.0097 | 0.0011 | 54 |
| boot_cold | ft20_20x5 | 0.0133 | 0.0017 | 54 |
| cpsat_warm | ft20_20x5 | 0.0157 | 0.0018 | 54 |
| cpsat_cold | ft20_20x5 | 0.0283 | 0.0057 | 54 |
| boot_warm | la01_10x5 | 0.0002 | 0.0000 | 54 |
| boot_cold | la01_10x5 | 0.0003 | 0.0000 | 54 |
| cpsat_warm | la01_10x5 | 0.0006 | 0.0000 | 54 |
| cpsat_cold | la01_10x5 | 0.0007 | 0.0000 | 54 |
| boot_warm | la02_10x5 | 0.0005 | 0.0000 | 54 |
| boot_cold | la02_10x5 | 0.0006 | 0.0000 | 54 |
| cpsat_warm | la02_10x5 | 0.0010 | 0.0000 | 54 |
| cpsat_cold | la02_10x5 | 0.0013 | 0.0000 | 54 |
| boot_warm | la03_10x5 | 0.0006 | 0.0000 | 54 |
| boot_cold | la03_10x5 | 0.0009 | 0.0000 | 54 |
| cpsat_warm | la03_10x5 | 0.0010 | 0.0000 | 54 |
| cpsat_cold | la03_10x5 | 0.0016 | 0.0000 | 54 |
| boot_warm | la04_10x5 | 0.0005 | 0.0000 | 54 |
| boot_cold | la04_10x5 | 0.0009 | 0.0000 | 54 |
| cpsat_warm | la04_10x5 | 0.0010 | 0.0000 | 54 |
| cpsat_cold | la04_10x5 | 0.0018 | 0.0000 | 54 |
| boot_cold | la05_10x5 | 0.0001 | 0.0000 | 54 |
| boot_warm | la05_10x5 | 0.0002 | 0.0000 | 54 |
| cpsat_cold | la05_10x5 | 0.0005 | 0.0000 | 54 |
| cpsat_warm | la05_10x5 | 0.0005 | 0.0000 | 54 |
### Breakdown by objective
| method | objective | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | makespan | 0.0170 | 0.0039 | 1547 |
| cpsat_cold | makespan | 0.0227 | 0.0045 | 1547 |
| boot_warm | makespan | 0.0242 | 0.0045 | 1543 |
| cpsat_warm | makespan | 0.0246 | 0.0067 | 1255 |
| lns_prev_solution | makespan | 0.0662 | 0.0367 | 495 |
| fix_and_optimize_50 | makespan | 0.1215 | 0.1188 | 495 |
| dispatch_mwkr | makespan | 0.1523 | 0.1521 | 603 |
| greedy_from_scratch | makespan | 0.1625 | 0.1623 | 4 |
| local_branching_prev | makespan | 0.2238 | 0.1496 | 495 |
| dispatch_spt | makespan | 0.2467 | 0.2464 | 603 |
| repair_only | makespan | 0.9327 | 0.9327 | 719 |
### Breakdown by bootstrap_policy
| method | bootstrap_policy | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| boot_cold | append | 0.0159 | 0.0045 | 1331 |
| boot_warm | append | 0.0205 | 0.0052 | 1327 |
| cpsat_cold | append | 0.0219 | 0.0052 | 1331 |
| cpsat_warm | append | 0.0246 | 0.0067 | 1255 |
| lns_prev_solution | append | 0.0662 | 0.0367 | 495 |
| fix_and_optimize_50 | append | 0.1215 | 0.1188 | 495 |
| dispatch_mwkr | append | 0.1523 | 0.1521 | 603 |
| greedy_from_scratch | append | 0.1625 | 0.1623 | 4 |
| local_branching_prev | append | 0.2238 | 0.1496 | 495 |
| dispatch_spt | append | 0.2467 | 0.2464 | 603 |
| repair_only | append | 0.9327 | 0.9327 | 719 |
| boot_cold | beam_insert | 0.0247 | 0.0000 | 72 |
| cpsat_cold | beam_insert | 0.0278 | 0.0000 | 72 |
| boot_warm | beam_insert | 0.0549 | 0.0000 | 72 |
| boot_cold | gap_insert | 0.0239 | 0.0000 | 72 |
| cpsat_cold | gap_insert | 0.0276 | 0.0000 | 72 |
| boot_warm | gap_insert | 0.0419 | 0.0000 | 72 |
| boot_cold | regret_insert | 0.0240 | 0.0000 | 72 |
| cpsat_cold | regret_insert | 0.0277 | 0.0000 | 72 |
| boot_warm | regret_insert | 0.0441 | 0.0000 | 72 |
### Breakdown by stream_step
| method | stream_step | mean_pi | mean_final_gap | n |
| --- | --- | --- | --- | --- |
| cpsat_warm | 0 | 0.0178 | 0.0027 | 139 |
| boot_cold | 0 | 0.0180 | 0.0024 | 172 |
| boot_warm | 0 | 0.0185 | 0.0026 | 171 |
| cpsat_cold | 0 | 0.0186 | 0.0025 | 172 |
| local_branching_prev | 0 | 0.0263 | 0.0042 | 45 |
| fix_and_optimize_50 | 0 | 0.0664 | 0.0626 | 45 |
| lns_prev_solution | 0 | 0.0880 | 0.0490 | 45 |
| dispatch_mwkr | 0 | 0.1417 | 0.1415 | 63 |
| dispatch_spt | 0 | 0.2225 | 0.2223 | 63 |
| repair_only | 0 | 0.2417 | 0.2414 | 80 |
| greedy_from_scratch | 0 | 0.3737 | 0.3735 | 1 |
| boot_cold | 1 | 0.0178 | 0.0037 | 172 |
| cpsat_warm | 1 | 0.0206 | 0.0062 | 139 |
| boot_warm | 1 | 0.0219 | 0.0049 | 171 |
| cpsat_cold | 1 | 0.0227 | 0.0045 | 172 |
| fix_and_optimize_50 | 1 | 0.0892 | 0.0866 | 45 |
| lns_prev_solution | 1 | 0.0908 | 0.0489 | 45 |
| greedy_from_scratch | 1 | 0.1132 | 0.1130 | 1 |
| dispatch_mwkr | 1 | 0.1511 | 0.1509 | 63 |
| local_branching_prev | 1 | 0.1971 | 0.1185 | 45 |
| dispatch_spt | 1 | 0.2725 | 0.2723 | 63 |
| repair_only | 1 | 0.4243 | 0.4243 | 80 |
| boot_cold | 2 | 0.0149 | 0.0034 | 172 |
| cpsat_cold | 2 | 0.0200 | 0.0036 | 172 |
| cpsat_warm | 2 | 0.0222 | 0.0062 | 139 |
| boot_warm | 2 | 0.0262 | 0.0048 | 171 |
| lns_prev_solution | 2 | 0.0636 | 0.0367 | 45 |
| greedy_from_scratch | 2 | 0.0833 | 0.0831 | 1 |
| fix_and_optimize_50 | 2 | 0.0937 | 0.0914 | 45 |
| dispatch_mwkr | 2 | 0.1395 | 0.1392 | 63 |
| local_branching_prev | 2 | 0.2308 | 0.1547 | 45 |
| dispatch_spt | 2 | 0.2435 | 0.2433 | 63 |
| repair_only | 2 | 0.5990 | 0.5990 | 80 |
| boot_cold | 3 | 0.0197 | 0.0038 | 172 |
| boot_warm | 3 | 0.0207 | 0.0033 | 171 |
| cpsat_cold | 3 | 0.0252 | 0.0037 | 172 |
| cpsat_warm | 3 | 0.0257 | 0.0081 | 139 |
| lns_prev_solution | 3 | 0.0650 | 0.0389 | 45 |
| greedy_from_scratch | 3 | 0.0799 | 0.0796 | 1 |
| fix_and_optimize_50 | 3 | 0.1081 | 0.1056 | 45 |
| dispatch_mwkr | 3 | 0.1599 | 0.1596 | 63 |
| local_branching_prev | 3 | 0.2320 | 0.1582 | 45 |
| dispatch_spt | 3 | 0.2536 | 0.2534 | 63 |
| repair_only | 3 | 0.7787 | 0.7787 | 80 |
| boot_cold | 4 | 0.0149 | 0.0039 | 171 |
| boot_warm | 4 | 0.0216 | 0.0030 | 171 |
| cpsat_cold | 4 | 0.0224 | 0.0049 | 171 |
| cpsat_warm | 4 | 0.0229 | 0.0058 | 139 |
| lns_prev_solution | 4 | 0.0619 | 0.0352 | 45 |
| fix_and_optimize_50 | 4 | 0.1131 | 0.1103 | 45 |
| dispatch_mwkr | 4 | 0.1574 | 0.1571 | 63 |
| local_branching_prev | 4 | 0.2442 | 0.1636 | 45 |
| dispatch_spt | 4 | 0.2595 | 0.2593 | 63 |
| repair_only | 4 | 0.9461 | 0.9461 | 79 |
| boot_cold | 5 | 0.0178 | 0.0045 | 171 |
| cpsat_warm | 5 | 0.0220 | 0.0072 | 139 |
| boot_warm | 5 | 0.0237 | 0.0043 | 171 |
| cpsat_cold | 5 | 0.0243 | 0.0051 | 171 |
| lns_prev_solution | 5 | 0.0616 | 0.0334 | 45 |
| fix_and_optimize_50 | 5 | 0.1209 | 0.1182 | 45 |
| dispatch_mwkr | 5 | 0.1564 | 0.1561 | 63 |
| local_branching_prev | 5 | 0.2442 | 0.1626 | 45 |
| dispatch_spt | 5 | 0.2611 | 0.2609 | 63 |
| repair_only | 5 | 1.0733 | 1.0733 | 79 |
| boot_cold | 6 | 0.0146 | 0.0032 | 153 |
| cpsat_cold | 6 | 0.0212 | 0.0043 | 153 |
| cpsat_warm | 6 | 0.0251 | 0.0059 | 121 |
| boot_warm | 6 | 0.0274 | 0.0036 | 153 |
| lns_prev_solution | 6 | 0.0576 | 0.0297 | 45 |
| fix_and_optimize_50 | 6 | 0.1323 | 0.1293 | 45 |
| dispatch_mwkr | 6 | 0.1571 | 0.1569 | 45 |
| local_branching_prev | 6 | 0.2445 | 0.1602 | 45 |
| dispatch_spt | 6 | 0.2522 | 0.2519 | 45 |
| repair_only | 6 | 1.2856 | 1.2856 | 61 |
| boot_cold | 7 | 0.0137 | 0.0037 | 137 |
| cpsat_cold | 7 | 0.0204 | 0.0041 | 137 |
| cpsat_warm | 7 | 0.0230 | 0.0070 | 105 |
| boot_warm | 7 | 0.0251 | 0.0039 | 137 |
| lns_prev_solution | 7 | 0.0583 | 0.0356 | 45 |
| fix_and_optimize_50 | 7 | 0.1432 | 0.1409 | 45 |
| dispatch_mwkr | 7 | 0.1566 | 0.1563 | 45 |
| dispatch_spt | 7 | 0.2409 | 0.2406 | 45 |
| local_branching_prev | 7 | 0.2591 | 0.1743 | 45 |
| repair_only | 7 | 1.2871 | 1.2871 | 45 |
| boot_cold | 8 | 0.0147 | 0.0038 | 137 |
| cpsat_cold | 8 | 0.0203 | 0.0041 | 137 |
| cpsat_warm | 8 | 0.0232 | 0.0060 | 105 |
| boot_warm | 8 | 0.0243 | 0.0039 | 137 |
| lns_prev_solution | 8 | 0.0578 | 0.0309 | 45 |
| dispatch_mwkr | 8 | 0.1471 | 0.1468 | 45 |
| fix_and_optimize_50 | 8 | 0.1493 | 0.1466 | 45 |
| dispatch_spt | 8 | 0.2287 | 0.2284 | 45 |
| local_branching_prev | 8 | 0.2645 | 0.1799 | 45 |
| repair_only | 8 | 1.4434 | 1.4434 | 45 |
| boot_cold | 9 | 0.0280 | 0.0080 | 45 |
| cpsat_cold | 9 | 0.0365 | 0.0095 | 45 |
| boot_warm | 9 | 0.0418 | 0.0161 | 45 |
| cpsat_warm | 9 | 0.0492 | 0.0119 | 45 |
| lns_prev_solution | 9 | 0.0608 | 0.0327 | 45 |
| dispatch_mwkr | 9 | 0.1571 | 0.1568 | 45 |
| fix_and_optimize_50 | 9 | 0.1587 | 0.1561 | 45 |
| dispatch_spt | 9 | 0.2383 | 0.2380 | 45 |
| local_branching_prev | 9 | 0.2484 | 0.1778 | 45 |
| repair_only | 9 | 1.5709 | 1.5709 | 45 |
| boot_cold | 10 | 0.0281 | 0.0096 | 45 |
| cpsat_cold | 10 | 0.0406 | 0.0112 | 45 |
| boot_warm | 10 | 0.0408 | 0.0136 | 45 |
| cpsat_warm | 10 | 0.0566 | 0.0166 | 45 |
| lns_prev_solution | 10 | 0.0632 | 0.0329 | 45 |
| dispatch_mwkr | 10 | 0.1550 | 0.1547 | 45 |
| fix_and_optimize_50 | 10 | 0.1614 | 0.1588 | 45 |
| dispatch_spt | 10 | 0.2277 | 0.2274 | 45 |
| local_branching_prev | 10 | 0.2708 | 0.1914 | 45 |
| repair_only | 10 | 1.6800 | 1.6801 | 45 |
## 7. Figures
- results/icaps/figures/final_gap_boxplot.pdf
- results/icaps/figures/pi_scatter.pdf
- results/icaps/figures/severity_heatmap.pdf
- results/icaps/figures/overhead_scaling.pdf
## 8. Interpretation
- **Where it helps:** `boot_cold` shows the largest mean PI improvement over `cpsat_cold` (0.0057, 1313W/0T/234L, sign-test p=0.0000).
- **Where it weakens:** `repair_only` shows the smallest/negative mean PI improvement (-0.8993).
- **Arrivals:** boot_cold=0.0208, cpsat_cold=0.0232, cpsat_warm=0.0282, boot_warm=0.0334, lns_prev_solution=0.0922, fix_and_optimize_50=0.1255, dispatch_mwkr=0.1489, local_branching_prev=0.2510, dispatch_spt=0.2608, repair_only=1.2547, boot_cold=0.0231, cpsat_cold=0.0262, boot_warm=0.0561 (see the `arrivals` preset / bootstrap_policies.py for the fix attempt).
- **Multi-worker:** see `breakdown_by_workers.csv` for whether gains shrink as num_workers grows (not yet run at scale in this pass).
## 9. ICAPS paper recommendation
**Ready:** the method (boot_cold), the domination guarantee (in its precise form -- see below), the pilot primal-integral result on job-shop across 7 seeds (see BOOT_COLD_PAPER.md), the full baseline menu implemented here, and the benchmark/loader infrastructure.

**Still needs to be run:** the `main` grid (seeds 21-50, all sizes/budgets/worker counts) for the actual paper table; `workers` preset specifically to characterize whether gains shrink under CP-SAT's own multi-worker portfolio search (a real, unaddressed risk -- CP-SAT's internal adaptive LNS only activates with workers>1); `arrivals` preset to confirm gap_insert/regret_insert/beam_insert close the arrival weak case at scale, not just in the single case checked by unit tests.

**Strongest claim supported by data so far:** a near-zero-cost constructive repair of the previous schedule, kept as an anytime floor under an unmodified CP-SAT solve, improves primal integral, replicated across seeds and domains (BOOT_COLD_PAPER.md).

**Domination guarantee -- precise form (do not overstate):** boot_cold's final objective is provably never worse than **its own unmodified continuation** (same run, same budget window) -- this is a theorem, not an empirical tendency. It is *not* an exact guarantee against a *separately invoked* cpsat_cold run: at ICAPS-preset scale (n=508, 2026-07-11 re-analysis) boot_cold's final objective was strictly worse than an independent cpsat_cold on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%), attributable to wall-clock non-reproducibility, not a flaw in the proof. State the theorem in its precise form; report the 92.4% empirical non-loss rate as a strong-but-not-absolute finding, never as "provably never worse than cold-solving."

**Claims to avoid:** this is not a machine-learning method; CP-SAT's own search is not improved or sped to proof; final objective is not usually better (ties are the norm, by design); "provably never worse than cold" (only true against its own continuation, see above); weak cases (arrivals, and any case not yet run at the `main`/`workers`/`budgets` scale) should not be papered over.
