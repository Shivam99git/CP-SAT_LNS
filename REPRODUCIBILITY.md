# Reproducibility guide

This document explains how to reproduce every result reported in the ICAPS 2027
submission (`paper/icaps27_multisolver_final/manuscript_candidate.pdf`) and its
supplement, from archived raw records (Level 1, minutes) and, where licenses and
hardware allow, from a fresh live solver campaign (Level 2, hours).

## 1. Repository organization

```
phase0/                  core research code: instance generation (streams.py), the
                          CP-SAT research model, the solver-independent model and
                          MILP formulation, solver adapters, methods S0-S5, analysis
                          scripts for each historical study (analyze_*.py)
scripts/multisolver/      the multi-solver campaign: discovery, smoke tests, the
                          campaign runner, validation, statistics, figures
tests/                    unit, integration and cross-solver equivalence tests
results/                  all raw run records, instance archives, frozen plans and
                          analysis outputs (see "Expected output directories" below)
paper/icaps27_multisolver_final/  the manuscript: LaTeX source, numerical macro
                          registry (make_numbers.py -> numbers.tex), figures,
                          the supplement, and the compiled candidate PDFs
docs/                     per-phase audits, the final research report, and the
                          git-sync / attribution reports
reproducibility/          this interface: setup, checks, and reproduction scripts
```

## 2. Environment setup

```bash
bash reproducibility/setup_environment.sh
```

Creates `.venv` (CP-SAT study and manuscript tooling), `.venv_ms` (multi-solver
study; reuses `.venv`'s site-packages via a `.pth` file, then adds the solver
bindings that only `.venv_ms` needs), and downloads the pinned MiniZinc 2.10.1
bundle (Gecode 6.4.0, Chuffed 0.14.0) to `.solvers/`. None of these three
directories is committed (`.gitignore`); nothing elsewhere in the repository
depends on an absolute path into them.

## 3. Solver installation

Open-source engines (OR-Tools/CP-SAT, SCIP, HiGHS, CBC, GLPK, Gecode, Chuffed)
install automatically in step 2. Commercial engines are **optional**:

| Engine | Needed for | Without it |
|---|---|---|
| Gurobi (`pip install gurobipy`) | 8x6-tier comparisons | that engine reads NOT EXECUTED, nothing is fabricated |
| IBM CPLEX + docplex (`pip install cplex docplex`, plus the `cpoptimizer` binary on PATH or at `.venv/bin/cpoptimizer`) | 8x6-tier comparisons | same |

All three commercial engines were evaluated here only under their free/community
editions, which refuse models above 1,000-2,000 variables or constraints
(`docs/multisolver/SOLVER_AVAILABILITY.md`); the 15x15 and 20x20 tiers therefore
never include them, by design, not by omission.

**FICO Xpress, Hexaly:** no Python module and no licence were available; they were
never evaluated and the manuscript does not claim otherwise. **Choco:** requires a
Java runtime, absent on the development machine.

## 4. Dataset preparation

The instance archives used by every reported result are generated once and
committed (hashed, with a reference history per step):
`results/multisolver/instances/{dev,heldout}/{S,M15,M20}/*.json`. Nothing needs to
be regenerated to reproduce analysis; `phase0/streams.py` and
`phase0/solver_independent_model.py` are the generator and canonical serializer if
you want to verify an instance's hash yourself.

## 5. Quick validation

```bash
bash reproducibility/check_dependencies.sh    # environment sanity (seconds)
bash reproducibility/run_smoke_tests.sh       # fast+equivalence tests, solver
                                               # discovery, method-level smoke run
```

## 6. Reproduction from archived records (Level 1)

```bash
bash reproducibility/reproduce_analysis.sh
```

Recomputes, from the raw run files already in `results/`, with no new solver
call:

1. the IAIP-SR confirmatory analysis,
2. the COBAR certificate confirmatory analysis,
3. the unified critical-region / matched-round confirmatory analysis,
4. a third, code-disjoint recomputation of the final CP-SAT study's 60,720
   records and 33 comparisons (`scripts/multisolver/reproduce_cpsat_confirmatory.py`),
5. the multi-solver held-out campaign (19,440 records): re-validation, PI
   statistics, the contention sensitivity analysis, the post-hoc stage
   attribution and post-hoc comparisons,
6. every figure and LaTeX table those analyses feed.

It ends by running `reproducibility/compare_results.py`, which diffs every
regenerated JSON against the version committed at `HEAD` and classifies each as
EXACT MATCH / MATCH WITHIN TOLERANCE / MISMATCH (Task A10); see
`reproducibility/REPRODUCTION_COMPARISON.json`. These recomputations are
deterministic (same raw records, same code), so anything other than EXACT MATCH
indicates a real reproducibility problem, not solver randomness.

**Known gap verified by a fresh-clone test, not just asserted:** of the four
historical confirmatory studies, two (the final CP-SAT study and the unified
critical-rounds study) reproduce EXACT MATCH from a clean `git clone` with no
other setup, because their raw per-run records are fully committed. The other
two do not: IAIP-SR's analysis script raises on a fresh clone (its `runs/`
directory is absent) and COBAR's analysis script silently writes an empty
result for every setting whose `runs/` directory is absent, which earlier
versions of `compare_results.py` failed to flag as a mismatch (a dict-vs-dict
comparison that only checked keys present on *both* sides silently ignored
keys missing entirely from one side -- fixed, and re-verified against the
archive on the original development machine, where IAIP-SR and COBAR's raw
records still exist and reproduce EXACT MATCH). See section 11 (expected
output directories) and `docs/git_sync/FINAL_PUSH_AND_REPRODUCTION_REPORT.md`
for the verified state of each study's raw data.

## 7. Full experimental reproduction (Level 2)

```bash
bash reproducibility/reproduce_all_experiments.sh         # smoke scale: minutes
FULL=1 bash reproducibility/reproduce_all_experiments.sh  # the entire frozen
                                                           # campaign: hours
```

This actually re-executes the optimization solvers. It writes to
`results/multisolver_rerun/` — a separate directory from the archived
`results/multisolver/` — so the campaign this manuscript reports is never
overwritten. The frozen plan's SHA-256 is checked before any task runs; held-out
configurations are never altered after being examined. A solver unavailable on
your machine (missing licence/module/software) is recorded as NOT_SUPPORTED or
left NOT EXECUTED for that engine; it is never silently replaced.

`reproducibility/compare_live_rerun.py` then compares the fresh run against the
archived one. Because two independent, wall-clock-budgeted executions are not
expected to be byte-identical, the acceptance criteria are fixed in that script
*before* any rerun and are not touched afterward; the result is classified
STATISTICALLY CONSISTENT STOCHASTIC RESULT or MISMATCH, with the reasoning
recorded alongside it. See `reproducibility/FINAL_REPRODUCIBILITY_REPORT.md` for
the actual outcome recorded for this submission, including any smoke-scale
limitation discovered along the way.

### Resource requirements (Task A11)

`reproducibility/reproduce_all_experiments.sh FULL=1` first prints a dry-run
estimate (`run_benchmark.py --dry-run`): approximate task count, budgeted
core-hours, and the per-(experiment, tier, solver) task breakdown. For the
frozen plan as committed: 19,440 tasks, ~54 budgeted core-hours, 8-way
parallelism on 8 dedicated physical cores, around 50 MB of run records, no more
than a few hundred MB of peak RSS per task (CBC/GLPK on 20x20 peak under
330 MB; see Table S4 of the supplement).

## 8. Statistical analysis

`scripts/multisolver/analyze_results.py` and `phase0/analyze_*confirmatory.py`
implement every statistic reported (primal integral under both gap definitions,
sign test, Holm correction, stream-bootstrap CI). Definitions are documented in
each script's module docstring; see also `REPRODUCTION_MANIFEST.json`'s
`statistical_analysis_settings`.

## 9. Figure and table generation

```bash
bash reproducibility/rebuild_manuscript.sh
```

also covers this (step "Regenerating... / figures/tables"), or run the
individual generators directly: `paper/icaps27_multisolver_final/figures/make_figure{4,5,6}_*.py`
and `scripts/multisolver/generate_figures.py`.

## 10. Manuscript compilation

```bash
bash reproducibility/rebuild_manuscript.sh
```

Regenerates `numbers.tex` from the analysis files, checks every manuscript
number resolves to a registered macro (`check_claims.py`), compiles
`manuscript.tex` and `supplement.tex`, strips metadata and pdfTeX inclusion keys
to produce the double-blind `manuscript_candidate.pdf` (`make_candidate.py`), and
writes a SHA-256 manifest of every generated artifact
(`reproducibility/ARTIFACT_MANIFEST.json`).

## 11. Expected output directories

| Path | Contents |
|---|---|
| `results/multisolver/analysis/` | held-out statistics, sensitivity analysis, stage attribution, post-hoc comparisons |
| `results/multisolver/audit/` | the CP-SAT study's third, code-disjoint recomputation |
| `results/multisolver_rerun/` | Level 2's independent live rerun (not committed; regenerate locally) |
| `paper/icaps27_multisolver_final/figures/ms/` | multi-solver figures and tables |
| `reproducibility/*.json`, `*LOG*.txt` | reproduction run logs and comparison reports |

**Raw per-run records, by study** (needed to re-derive a `confirmatory_analysis.json`
from raw events rather than trust the one already committed):

| Study | Raw records committed? |
|---|---|
| Final CP-SAT confirmatory (`results/unified_icaps/confirmatory/*/runs/`) | yes |
| Unified critical-rounds (same directory, shared with the above) | yes |
| Multi-solver held-out campaign (`results/multisolver/runs/`) | yes |
| IAIP-SR (`results/research_extension/confirmatory/runs/`) | **no** -- its analysis script raises on a fresh clone |
| COBAR (`results/cobar/confirmatory/*/runs/`) | **no** -- its analysis script silently writes an empty result per missing setting on a fresh clone (caught by `compare_results.py`) |

For the two "no" rows, the already-computed, checksummed `confirmatory_analysis.json`
is committed and can be read/cited, but cannot currently be independently
re-derived from raw events by someone who only has this repository.

## 12. Expected computational resources

Level 1 (archived-data reproduction): a few minutes, single machine, no special
hardware. Level 2 smoke scale: a few minutes. Level 2 full: hours, 8+ cores
recommended, ~1 GB RAM per concurrent task, ~50-200 MB disk for a fresh run's
records.

## 13. Known platform differences

- Wall-clock-budgeted anytime trajectories are not bit-identical across hosts
  or under different contention; see Task A10's acceptance bands.
- `cp_model_lns`'s internal subsolver selection is OR-Tools-version-specific; a
  different version may show different four-worker behaviour (noted in the
  manuscript's Limitations).
- `.solvers/MiniZincIDE-...`'s binaries are platform-specific (x86_64 Linux here).

## 14. License limitations

CP Optimizer, Gurobi and CPLEX were run only under free/community editions,
capped at 1,000-2,000 variables/constraints; results above that size are
recorded as licence refusals (`LICENSE_LIMIT`), never as performance, and the
manuscript's claims about those engines are scoped accordingly.

## 15. Troubleshooting

- `check_dependencies.sh` reports exactly which required package or binary is
  missing; `setup_environment.sh` installs everything it can automatically.
- If MiniZinc fails to download automatically, install 2.10.1 manually to
  `.solvers/MiniZincIDE-2.10.1-x86_64-linux-gnu` (official release archive;
  see the URL in `setup_environment.sh`).
- A "FROZEN_PLAN hash mismatch" means `results/multisolver/FROZEN_PLAN.json`
  was edited after being frozen; `reproduce_all_experiments.sh` refuses to run
  rather than reproduce a different experiment than the one reported.
- `verify_visuals.py` reporting "stale" means `numbers.tex` was not committed
  after the last `make_numbers.py` run; re-run `rebuild_manuscript.sh`.

## 16. Verification of reproduced results

`reproducibility/compare_results.py` (Level 1, deterministic) and
`reproducibility/compare_live_rerun.py` (Level 2, stochastic) are the
verification scripts; `reproducibility/verify_everything.sh` runs dependency
checks, smoke tests, Level 1 reproduction and the manuscript rebuild in one
command and prints a single ARCHIVED-DATA REPRODUCTION PASS/FAIL verdict (Level
2 is intentionally excluded from that command because of its runtime; run it
separately). See `reproducibility/FINAL_REPRODUCIBILITY_REPORT.md` for this
submission's actual, recorded verdicts.
