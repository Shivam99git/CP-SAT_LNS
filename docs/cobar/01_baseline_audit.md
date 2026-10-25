# COBAR 01 — Baseline audit of IAIP-SR (Phase 1)

- **Date:** 2026-10-25.
- **Branch:** `research/cobar-certificate-guided`, created from `research/iaip-sr` at `6a66978`. Nothing has been pushed.
- **Manifest:** `results/cobar/baseline_manifest.json` (versions, hardware, seeds, instance hashes, checksum files).

## 1. Environment

| Item | Value |
|---|---|
| Python | 3.12.3 |
| OR-Tools | 9.15.6755 |
| numpy / pandas / scipy | 2.5.1 / 3.0.3 / 1.18.0 (full freeze: `requirements_research.txt`) |
| OS | Ubuntu 24.04.4 LTS, Linux 7.0.0-34-generic |
| CPU | Intel Core i7-12700, 8 P-cores (logical 0–15) + 4 E-cores (16–19) |
| Memory | 31 GB |
| CP-SAT parameters | `max_time_in_seconds` = remaining budget, `num_workers` (1; E6b 4), `random_seed` (solver seed); everything else default |

## 2. Reproduction

| Check | Result |
|---|---|
| fast tests (`pytest tests/`) | **204 passed** (`results/cobar/baseline_fast.xml`) |
| slow tests (`-m slow`) | **25 passed** (`results/cobar/baseline_slow.xml`) |
| raw run files vs committed `RUNS.sha256` | **0 mismatches** over 913 files (Gate 1 495 incl. reference chains, confirmatory 200, E6 218) |
| re-running `analyze_gate1`, `analyze_confirmatory`, `analyze_e6` on the raw files | outputs **byte-identical** to the committed JSON (`git diff` empty) |
| development campaigns `dev_e3e4`, `dev_e5`, `dev_e5b`, `dev_e5c` | had no checksum file; `RUNS.sha256` created now (20 files each). Provenance: written by `run_iaip_campaign` at the revisions in their `manifests.jsonl`; never modified since |

**Provenance of untracked files.** The raw run files under `results/research_extension/*/runs/` are not in git because of their size (about 380 MB in total). The committed `RUNS.sha256` files make them tamper-evident, and they are preserved in place.

## 3. Reference claims recomputed

All values are recomputed from raw trajectories by the archived analysis scripts. Each reduction is the relative reduction in stream-mean PI against Fresh+Cold.

| Claim (report) | Recomputed | Source |
|---|---|---|
| confirmatory −43% | −43.2%, 40/0 streams, CI [−0.0288, −0.0228], Holm 1.5e-11 | `confirmatory/confirmatory_analysis.json` |
| B = 30 s −55% | −55.3%, 20/0 | `e6_analysis.json` |
| 4 workers −66% | −65.7%, 20/0 | same |
| arrival-only −63% | −63.1%, 20/0 | same |
| outage-only −42% | −42.2%, 18/2 | same |
| high severity −58% | −58.5%, 20/0 | same |
| published bases −61% | −61.2%, 34/0 base instances | same |
| 11,220 validated E6 runs | 10,340 (E6a–d) + 880 (E6e), 0 not validated | same |

**Status of these values:**
- **Confirmatory:** 5 seeds, frozen configuration.
- **Exploratory:** all E6 values; 1 solver seed, 20 streams per setting.

## 4. What the validated runs do and do not prove

**Final schedules: validated.** Every returned final schedule was checked by `phase0/schedule_validator.py`, which is independent of the CP-SAT model.

**Intermediate solver incumbents: NOT validated.** `run_cpsat` records each improving solver solution at callback time from `objective_value`; only the final solution is validated.
- The CP-SAT model's optimum equals brute-force enumeration on 40 tiny instances (`tests/test_selective_reoptimization.py`).
- Even so, the PI of every CP-SAT-based method relies on solver-reported objective values for intermediate points.
- This affects all methods equally. COBAR keeps this convention so that comparisons stay matched, and Phase 7 adds an audit that validates intermediate solutions on a subset.

**Timing fairness** (confirmatory data):

| Check | Result |
|---|---|
| mean deadline overrun per method | 3.3–4.1 ms; p99 13–18 ms |
| mean position in the shuffled within-step order | 4.43–4.64 for every method (expected 4.5) |

- All methods of a stream run sequentially in one process pinned to one physical core.
- Incumbents after B are ignored, so overruns buy no PI.

**Causal attribution.**
- The component steps (history → hinting → restricted stage) are differences between separately run methods.
- The predeclared selective-stage comparison is valid as a paired contrast. The 40/20/40% attribution depends on the order in which components are added.

## 5. Findings that shape the COBAR study

### F1. Non-improving neighbourhoods are already cheap
On development streams (`dev_e5c`, α = 0.6, 120 local stages):

| Local status | n | median time | max time |
|---|---|---|---|
| INFEASIBLE | 29 | 21 ms | 41 ms |
| OPTIMAL | 88 | 0.52 s | 4.2 s |
| FEASIBLE (ran to α·B) | 3 | 4.7 s | 4.7 s |

INFEASIBLE means no improvement is possible under the `C_max ≤ U − 1` bound. CP-SAT proves this in tens of milliseconds, and the local stage usually ends early (OPTIMAL) anyway.

**Consequence:** a certificate that only *skips* non-improving neighbourhoods can save at most a few tens of milliseconds in roughly a quarter of the steps, which is ≤ 0.1% of an 8 s budget. Any COBAR benefit must come from *changing* the neighbourhood or the budget split, not from skipping.

### F2. With several workers, CP-SAT already runs scheduling LNS
The solver logs (OR-Tools 9.15, this model) show:
- **`num_workers = 1`:** a single `main` subsolver; no LNS.
- **`num_workers = 4`:** 3 full-problem subsolvers, plus 13 interleaved subsolvers including `scheduling_precedences_lns`, `scheduling_time_window_lns`, `scheduling_intervals_lns` and `scheduling_resource_windows_lns`.

This is a plausible mechanism, **not yet tested**, for E6b's finding that IAIP-SR's restricted stage adds nothing with 4 workers.

**Single-core native-LNS control:** `num_workers = 1, interleave_search = True` runs the full-problem subsolvers *and* the scheduling LNS neighbourhoods interleaved on one thread. This is the matched native-LNS control (A9). `use_lns_only = True` with one worker runs no LNS.

### F3. Closest literature not cited by the IAIP-SR manuscript
Lin & Yang, *An incumbent-aware selective-repair framework for dynamic flexible job shop scheduling*, C&IE 221:112299 (2026; online 2026-08-11).
- The method: SLR2 uses a GNN to split operations into kept and released sets, and a reduced CP-SAT model repairs only the released neighbourhood under a time budget.
- This is very close to IAIP-SR's restricted stage, and it is **not cited** in `paper/icaps27_iaip/`.
- Any manuscript, IAIP-SR or COBAR, must cite and contrast it. See `02_related_work_and_novelty.md`.

## 6. Limitations recorded, not fixed

- Intermediate incumbents are not validated (§4).
- E6 is single-seed and exploratory.
- Freeze-only streams were never run.
- Development and confirmatory streams share one generator.
- No dataset was modified to match any manuscript claim.
