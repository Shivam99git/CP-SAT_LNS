# Real RCPSP benchmark instances

Downloaded 2026-07-12 from the ScheduleOpt/benchmarks GitHub repository
(https://github.com/ScheduleOpt/benchmarks/tree/main/rcpsp/instances), which
redistributes the classic PSPLIB instance sets in the compact "Patterson"
`.rcp` format (documented in `phase0/rcpsp/benchmark_loaders.py`).

40 files: 10 each of j30, j60, j90, j120 (numbers = activity count including
2 dummy source/sink nodes), sampled as `{size}_{i}_{j}.rcp` for i=1..5, j=1..2.

| set | activities | files here | source |
|---|---|---|---|
| j30 | 32 | 10 | PSPLIB, via ScheduleOpt/benchmarks |
| j60 | 62 | 10 | PSPLIB, via ScheduleOpt/benchmarks |
| j90 | 92 | 10 | PSPLIB, via ScheduleOpt/benchmarks |
| j120 | 122 | 10 | PSPLIB, via ScheduleOpt/benchmarks |

## Validation performed

Two independent checks:

1. **Self-certifying**: 5 j30 instances were solved to CP-SAT's `OPTIMAL`
   status (a machine-checked branch-and-bound proof) with independent
   solution validation passing — see
   `tests/test_rcpsp_benchmark_loaders.py::test_real_j30_instances_solve_to_proven_optimality`
   (marked `slow`, run explicitly with `-m slow`).

2. **External best-known reference** (added 2026-07-13): `optalcp_bks_reference.json`
   in this directory holds proven-optimal objective values for all 40 fixture
   instances here, extracted from the public leaderboard at
   https://optalcp.com/benchmarks/rcpsp/main.html — a paired comparison of
   OptalCP (Optal solver, versions ~0.9.1.9) and IBM CP Optimizer 22.1.0.0 on
   the full official PSPLIB set (2040 instances: j30=480, j60=480, j90=480,
   j120=600, run at 600s/4 workers each). All 40 of our fixture instances have
   an entry there where **both solvers independently proved the same optimal
   objective** (`proof: true`, `objective == lowerBound` for both), extracted
   via bracket-matching the `window.scheduleopt.main([...])` inline JSON
   payload embedded in the page's HTML (the data is not exposed via a
   separate JSON/CSV endpoint — it's inlined directly in `main.html`).
   modelName scheme: `rcpsp_{fam}_{fam}{set}_{inst}` (e.g. `rcpsp_j30_j301_1`)
   maps to our `{fam}_{set}_{inst}.rcp` (e.g. `j30_1_1.rcp`).

   Cross-checked against our own `results/icaps/rcpsp/rcpsp_real_benchmarks.csv`
   base-instance (unperturbed, `delta_kind=="base"`) rows, 8s budget, 1
   worker: 222/240 runs (40 instances × 3 seeds × 2 methods) found the exact
   externally-proven-optimal value (216 of those with CP-SAT's own `OPTIMAL`
   proof, matching the external proof exactly; 6 found the right value without
   completing the proof in 8s). **Zero** runs found an objective *better* than
   the external optimum (a basic correctness sanity check — would indicate a
   model or validator bug). The remaining 18/240 (all on the 3 hardest
   instances — `j120_1_1`, `j60_5_2`, `j90_5_2`, each × 3 seeds × 2 methods)
   did not reach optimal within the 8s budget; mean excess 2.13%, max 3.81% —
   expected, given a 75x shorter time budget and a quarter of the workers
   versus the reference runs. See
   `tests/test_rcpsp_benchmark_loaders.py::test_real_instances_match_external_optalcp_bks`.
