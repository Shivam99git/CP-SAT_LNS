# 02 — Environment

## What was verified

| Item | Value |
|---|---|
| Source revision of the frozen baseline | `8178b2a` on local branch `research/iaip-sr` (snapshot of `main` + the uncommitted ICAPS-27 manuscript work) |
| OS | Linux 7.0.0-34-generic x86_64, glibc 2.39 (Ubuntu 24.04) |
| Python | 3.12.3 (project virtualenv `.venv`) |
| OR-Tools / CP-SAT | 9.15.6755 |
| Other pinned packages | `requirements_research.txt` (output of `pip freeze` in `.venv`) |
| CPU | 12th Gen Intel Core i7-12700: 8 performance cores (CPUs 0–15, two hardware threads each, max 4.8–4.9 GHz) and 4 efficiency cores (CPUs 16–19, max 3.6 GHz); 31 GB RAM |

CP-SAT runs in this environment. The brief's statement that "the previous audit environment could not execute CP-SAT" refers to a different environment; nothing in this repository depends on it.

## Files the brief names that do not exist

`requirements_rework.txt`, `README_REWORK.md`, `SUBMISSION_READINESS.md`, `phase0/instance_io.py`, `phase0/robust_analysis.py`, `phase0/mechanism_analysis.py`, `phase0/reconcile.py`, `scripts/validate_new_campaign.py`, `scripts/make_confirmatory_tables.py`, `scripts/run_causal_confirmatory.sh`, `scripts/submission_certification_gate.py`, and the methods `repaired_hint_only`, `dispatch_spt_plus_cold`, `dispatch_mwkr_plus_cold`. They are absent from the working copy, from every branch of the GitHub remote (`git fetch --all` on 2026-10-23), and from the rest of the filesystem. The equivalent functionality was implemented here (`phase0/reuse_methods.py`, `phase0/run_gate1.py`, `phase0/analyze_gate1.py`); see `01_repository_audit.md`.

## Frozen pre-extension test baseline

Run before any extension code existed (`results/research_extension/baseline_test_report.json`, JUnit files alongside):

| Suite | Tests | Failures | Errors | Time |
|---|---|---|---|---|
| fast (`pytest tests/ -q`) | 130 | 0 | 0 | 18 s |
| slow solver integration (`-m slow`: real-instance optimality, Gurobi/CPLEX) | 25 | 0 | 0 | 100 s |

No existing test was modified.

## Timing discipline for experiments

All comparisons are wall-clock limited, so CPU placement matters. Archived campaigns ran up to 16 unpinned processes, so some solves ran on efficiency cores, which are about 25% slower.

- **Confirmatory and Gate 1 runs:** one process per physical performance core (CPUs 0, 2, …, 14), pinned with `sched_setaffinity`. Hyperthread siblings are left idle.
- **Development runs:** efficiency cores only (CPUs 16–19). They are therefore comparable with one another, but their absolute values are not comparable with confirmatory runs.

## Reproduce

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements_research.txt
.venv/bin/python -m pytest tests/ -q            # fast
.venv/bin/python -m pytest tests/ -q -m slow    # slow
```
