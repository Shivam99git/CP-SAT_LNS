# Final-phase 03 — Critical-region vs. time-window, resolved by reanalysis (Phase 3)

**No new experiments were run for this phase.** Every finding below comes from reanalysing the already-archived, already-validated confirmatory raw run files (U1, U2, U6) with new aggregation queries. This follows the standing instruction to add new runs only when existing data cannot resolve a material question; here it can.

## 3.2-3.3: The two protocols were already both executed

- **Protocol A (end-to-end, "M1"):** U1 (standard disruption mix), U6 (arrival-only), U7 (outage-only), and U3-U5/U8-U9. Every method runs until its local window or a stop-on-failure condition; round counts can differ between methods.
- **Protocol B (mechanism-isolation, "M2"):** U2, with exactly 6 rounds of at most 0.4s each for every method, regardless of success. Both protocols exist for the primary mix (U1 vs. U2) but **U2 (M2) was never run on the arrival-only-specific stream population used by U6** — this was a real gap. It is filled below by reanalysing U2's existing per-stream `delta_kind` breakdown (U2 uses the same default mixed-delta streams as U1, so its records already carry a `delta_kind` label per step; they were simply never grouped by it before).

## 3.5 (resolved): Does the arrival-specific critical advantage survive matched-round accounting?

**No.** Breaking out U2's existing mechanism-isolation (M2) comparison by `delta_kind` (using the same stream population, same `compare()` function already independently verified in Phase 1):

| Delta kind | M2: crit vs. time-window | Streams won/lost (crit) | $n$ |
|---|---|---|---|
| arrival | **+8.9%** (crit *worse*) | 13/27 | 40 |
| cancellation | +18.5% (crit worse) | 9/29 | 38 |
| duration_jitter | +13.3% (crit worse) | 12/26 | 38 |
| outage | +9.8% (crit worse) | 11/20 | 31 |

Under the matched-round protocol, critical-region targeting is **worse** than time-window targeting in every single disruption type, including arrivals — the opposite of the end-to-end (M1, U6) finding that critical beats time-window by -23.6% specifically after arrivals.

**Why the sign flips: round-count confound, found by reanalysis.** Under the end-to-end (M1) protocol, critical-region rounds complete systematically more rounds per instance than time-window rounds, in every disruption type (U1 raw run reanalysis):

| Delta kind | Mean completed rounds, critical | Mean completed rounds, time-window | Round-improvement rate, critical | Round-improvement rate, time-window |
|---|---|---|---|---|
| arrival | 3.15 | 2.02 | 69.1% | 51.9% |
| cancellation | 2.40 | 1.85 | 58.7% | 46.4% |
| duration_jitter | 2.91 | 2.06 | 66.4% | 51.9% |
| outage | 2.95 | 1.88 | 67.4% | 47.0% |

Because the end-to-end protocol's stop-on-fail rule lets a method keep going *only after an improving round*, and critical-region rounds succeed more often per attempt (a difference consistent across all four disruption types, largest for arrival at +17.2 percentage points), critical-region methods accumulate more total rounds — and therefore more total opportunities to improve — under M1. This is exactly the confound Protocol B (M2) is designed to remove by fixing the round count. Once removed, the sign reverses in every disruption type. **Conclusion: the arrival-specific advantage reported for U6 under the end-to-end protocol is best explained as an artifact of unequal completed-round counts, not as evidence that critical targeting is intrinsically better suited to arrivals.** This is a materially different, more precise conclusion than the earlier "confined to one disruption type" framing (`docs/unified_icaps/04_mechanism_analysis.md` §3) — the earlier framing is **superseded** by this finding. (The earlier document is corrected in Phase 4, not deleted; the superseded claim is marked as such, not silently removed.)

This is exploratory-of-the-confirmatory-data in the strict pre-registration sense (delta-kind breakdowns were always declared exploratory, `06_statistical_results.md`), but it is reanalysis of already-collected, already-frozen data under the already-pre-registered M2 protocol, not a new experiment and not data dredging for a different question.

## 3.4 (resolved): Neighbourhood-size matching is exact; solve-difficulty matching is not

From U2's (M2) round-level metadata, aggregated over 11,800-12,000 rounds per method:

| Strategy | Mean \|N\| | Mean critical ops in N | Mean neighbourhood-build time (ms) | Mean model-build time (ms) | Mean per-round solver time (s) | Status distribution (INFEASIBLE / OPTIMAL / FEASIBLE / UNKNOWN) |
|---|---|---|---|---|---|---|
| critical | 82.4 | 39.8 | 3.28 | 4.26 | **0.056** | 7988 / 3471 / 376 / 97 |
| time-window | 82.3 | 9.9 | 3.37 | 4.26 | **0.080** | 7289 / 3554 / 901 / 147 |
| random (matched) | 82.4 | 9.7 | 3.31 | 4.27 | 0.035 | 8928 / 2840 / 165 / 2 |
| precedence (arc-matched) | 0.0 (arcs only) | 0.0 | 3.57 | 4.27 | 0.021 | 10092 / 1842 / 20 / 1 |

**Confirmed: \|N\| (and preprocessing time) is matched essentially exactly** (82.3 vs. 82.4 operations; construction and model-build times agree to within measurement noise) between critical, time-window and random — this fairness property, already unit-tested (`test_size_matching_of_controls`), holds in the actual confirmatory data too.

**Not matched: the resulting restricted CP-SAT subproblem's solve difficulty.** Time-window rounds take **43% longer to resolve per round** on average (0.080s vs. 0.056s for critical) despite an identical neighbourhood size, and hit the 0.4s round-time cap without a definitive status 2.4x more often (901 FEASIBLE vs. 376). Precedence-relaxation rounds (which release no operations, only machine-order arcs) are both the fastest to resolve (0.021s) and the most often provably unimprovable (84% INFEASIBLE) — a tightly constrained restricted model that is easy to exhaust but rarely has anywhere left to go. Random neighbourhoods sit in between (fast, 0.035s, and INFEASIBLE most often of the three \|N\|-matched strategies, 8928/11935 = 75%).

**Reading:** critical-region neighbourhoods, despite being no larger than time-window neighbourhoods, induce an *easier* restricted subproblem (faster to prove INFEASIBLE or OPTIMAL) than time-window neighbourhoods do. This is consistent with — and offers a candidate mechanistic explanation for — the otherwise puzzling U2 result that time-window still edges out critical on final quality despite critical's higher raw per-round improvement rate (§7 of `04_mechanism_analysis.md`): time-window's harder, slower-to-resolve subproblems more often use their full 0.4s round budget productively (901 rounds returned FEASIBLE-but-improved or ran the full budget before being cut, versus critical's 376), effectively buying time-window more net search per round even though it attempts and completes fewer rounds in the same wall-clock window under Protocol A, and fewer *successful* rounds per attempt under Protocol B. **Do not equate \|N\| with search complexity** — this reanalysis is the concrete demonstration the brief asked for.

## Statistical reporting (per the required fields)

| Comparison | Mean PI (crit) | Mean PI (comparator) | Abs. diff | Rel. diff | 95% CI | W/L | Adj. $p$ | $n$ | Unit |
|---|---|---|---|---|---|---|---|---|---|
| U2 crit vs. timewin, arrival | (per-delta means not separately archived at full precision; W/L and rel-diff as shown are exact) | — | — | +8.9% | not separately computed (exploratory re-grouping) | 13/27 | uncorrected, single comparison | 40 | stream |
| U2 crit vs. timewin, cancellation | — | — | — | +18.5% | — | 9/29 | uncorrected | 38 | stream |
| U2 crit vs. timewin, duration_jitter | — | — | — | +13.3% | — | 12/26 | uncorrected | 38 | stream |
| U2 crit vs. timewin, outage | — | — | — | +9.8% | — | 11/20 | uncorrected | 31 | stream |

These four delta-kind breakdowns are **exploratory, not confirmatory** (not in the pre-registered family; no multiplicity correction applied; CIs not separately computed for this post-hoc grouping). They are reported because they resolve a specific, material ambiguity (does the arrival effect survive matched rounds?) raised by the task, not promoted as a new confirmatory finding. The headline confirmatory numbers (U1 and U2's un-stratified comparisons) remain exactly as reported in Phase 1's independent reproduction, with full CIs and Holm correction.

## Conclusion of Phase 3

The central open question — is critical-region targeting established as superior to time-window targeting, even narrowly after arrivals — is now answered **no, not even after arrivals**, once the round-count confound is removed. This strengthens (does not weaken) the CONDITIONAL GO framing: it removes the one exception that might have tempted an overclaim ("critical targeting helps specifically after arrivals"), replacing it with a cleaner, more defensible statement: *time-window targeting is at least as good as critical-region targeting, and plausibly slightly better, once computational effort is held equal; critical-region targeting's apparent edge under uncontrolled end-to-end accounting is attributable to it completing more rounds, not to better neighbourhood content.*
