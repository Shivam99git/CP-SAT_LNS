# Final-phase 06 — Statistical validation (Phase 6)

## 6.1: Primal-integral definition, verified

Definition used throughout (`phase0/analyze_gate1.py::integrate_gap`/`per_run`, independently reimplemented in `scripts/unified/verify_baseline.py::own_pi` and re-verified again in Phase 1 of this final stage): $\mathrm{PI} = \frac{1}{B}\int_0^B g(\tau)\,d\tau$, $g(\tau) = (z(\tau) - z^*)/z^*$, $g=1$ before the first incumbent, **uncapped** (not clipped to 1), integrated as a right-continuous step function over the trajectory of recorded events. Checked explicitly:
- time origin: $\tau=0$ is the method's own clock start (`Clock.t0`), which covers construction overhead — the first incumbent is never timestamped at $\tau=0$ unless construction was instantaneous (verified: `test_every_strategy_runs_valid_and_within_the_deadline`'s `0 < ts[0]` assertion, and independently by Phase 1's `t_first` recomputation).
- incumbents after $B$ are excluded from the integral (events with $\tau > B$ do not contribute; checked in `tests/test_analyze_gate1.py` and re-confirmed by the independent `own_pi` in this phase, which clips $t$ to $[0, B]$ before integrating).
- no-feasible-solution intervals get $g=1$ (the declared penalty), never silently omitted — confirmed 0 of 60,720 confirmatory runs lacked a feasible final schedule, and 0 runs lacked an in-budget incumbent entirely (`01_baseline_verification.md`).
- the objective reference $z^*$ is shared per physical instance (`stream`, `step`) across every compared method and solver seed within a setting, never per-method.
- gap clipping (`cap=True` variant) exists in the codebase but is **not** used for the primary metric anywhere in this study; the manuscript's reported PI is always the uncapped variant, matching the methodology documents.

No normalization was silently changed between stages of this project; the definition above is identical across Floor, IAIP-SR, COBAR and this unified study.

## 6.2: All headline comparisons, independently recomputed

Completed in Phase 1 (`01_baseline_verification.md`); all 33 confirmatory comparisons (not just the 6 headline ones) match to floating-point rounding. See `results/final_icaps/verified_metrics.json` for the full machine-readable record.

## 6.3: Statistical independence

Resolved explicitly in Phase 1: the unit of inference is the full stream identifier (size + seed), never the bare seed number or a solver-seed/step combination; 40/20/34 physical units per setting are correctly treated as independent throughout, and seed-sharing across sizes does not violate this (different physical instances result). Published-benchmark streams (U9) are clustered by base instance (the base, not the seed-stream pair, is the unit), avoiding pseudoreplication across the two streams built on each base.

## 6.4: Multiplicity

Holm-Bonferroni correction is applied within each setting's pre-registered family (U1: 8 comparisons; U2: 4; others: 3), implemented in `phase0/analyze_gate1.py::holm` and independently re-verified bit-for-bit in Phase 1's `own_holm`. The Phase 3 by-disruption-type reanalysis (§3.5/3.6 of `03_critical_vs_timewindow.md`) is **explicitly labeled exploratory** in both that document and the manuscript (no Holm correction applied to those 4+4 post-hoc comparisons, because they were not in the pre-registered family); this label is never dropped when the finding is summarized elsewhere.

## 6.5: Machine-readable evidence record

`results/final_icaps/verified_metrics.json` (built by `scripts/final/build_verified_metrics.py`): one record per reported confirmatory comparison (33 total), with every required field (experiment id, method/comparator plus their exact configuration strings, instance population, $n$ units, $n$ solver seeds, $n$ runs, budget, workers, metric, numerator/denominator, statistic, 95\% CI, Holm-adjusted $p$, raw/archived/independent-verification file locations, and a `verification_status` flag). **All 33 records are `INDEPENDENTLY_VERIFIED`** (cross-checked against Phase 1's from-scratch reanalysis, not merely copied from the original pipeline's output).
