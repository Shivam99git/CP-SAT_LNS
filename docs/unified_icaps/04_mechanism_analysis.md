# Unified study 04 — Mechanism analysis (Part V)

All numbers here are from the frozen confirmatory campaign (`results/unified_icaps/confirmatory/`), analysed by `phase0.analyze_unified` and `phase0.analyze_unified_confirmatory`. Compared with development (`03_lns_baseline_protocol.md` §§6–8), these are confirmatory where marked, exploratory otherwise.

## 1. Do extra rounds alone explain the gain?

**No, not fully.** In U1 (confirmatory, primary):
- B1 (random-seeded rounds, matched neighbourhood size) vs B0 (IAIP-SR, one round): **−2.5%**, 21/19, Holm 0.87 — **not significant**.
- B2 (critical rounds) vs B1 (random rounds): **−20.4%**, 35/5, Holm 8.3e-06.

So repeating the restricted solve with *randomly* chosen neighbourhoods of the same size as the critical ones gives almost nothing beyond IAIP-SR's single round. Extra rounds by themselves are not the mechanism; *where* the neighbourhood sits is what matters, and criticality is one way (not the only way, see §2) to choose that location well.

## 2. Does critical-region targeting add value beyond random neighbourhoods of the same size?

**Yes, reproducibly.** U1: B2 vs B1 −20.4% (35/5, Holm 8.3e-06); B2 vs B4 (random precedence relaxation, arc-count matched) −24.5% (34/6, Holm 3.3e-05). Both hold in every setting where tested (U3–U9 use B0/B6/B3 as controls, not B1/B4, per the frozen protocol, so this specific comparison is U1/U2 only).

U2 (mechanism-isolation protocol M2, fixed 6 rounds × 0.4 s): M2_crit vs M2_random **−10.8%** (28/12, Holm 0.033); M2_crit vs M2_prec **−10.9%** (31/9, Holm 0.002). Smaller than under M1 but still significant — matching exactly on round count and per-round time budget does not erase the advantage over *unstructured* neighbourhoods.

## 3. Does the advantage survive comparison with time-window and precedence LNS?

**Against precedence LNS: yes**, consistently (§2).

**Against time-window LNS: not established.** This is the central, pre-registered finding.

| Setting | B2 vs B3 (time window) | W/L | Holm p |
|---|---|---|---|
| U1 primary (8 s, 1 worker) | −6.1% | 26/14 | 0.16 |
| U2 mechanism (M2, fixed rounds) | **+11.4%** (crit *worse*) | 13/27 | 0.038 |
| U3 (4 workers) | +2.2% | 10/10 | 1 |
| U4 (2 s) | −1.3% | 22/18 | 0.86 |
| U5 (30 s) | −7.0% | 13/7 | 0.26 |
| U6 (arrival-only) | **−23.6%** | 18/2 | **0.0004** |
| U7 (outage-only) | −7.0% | 14/6 | 0.23 |
| U8 (high severity) | −9.5% | 14/6 | 0.12 |
| U9 (34 published bases) | −6.9% | 21/13 | 0.23 |

The only setting where critical targeting is significantly better than time-window targeting is **U6, arrival-only disruptions**. Everywhere else the two are statistically indistinguishable, and under the fixed-round mechanism-isolation protocol (U2) time-window is significantly *better*.

**Reading.** A size-matched time-window neighbourhood is, on these instances, an almost-as-good (and under matched-round accounting, slightly better) proxy for "the region of the schedule worth re-optimizing." The schedule's critical chain and the window of operations near the end of the horizon substantially overlap for job-shop instances built from uniform-random durations, which is plausibly why a purely temporal heuristic does nearly as well as one that explicitly computes criticality. Job arrivals are the one event type that adds new operations at job starts rather than perturbing the existing schedule locally, and there the critical region (which naturally gets pulled toward the disrupted job once it's chained in) tracks the actual disruption better than a static time window does.

This directly answers decisive question 3 from the brief: **the advantage over time-window LNS is not established**; it is confined to one disruption type (arrivals) and is reversed under the fixed-round protocol.

## 4. Does the method offer benefits beyond installed CP-SAT's native scheduling search?

**Beyond the 1-worker interleaved configuration: yes.** B2 vs B5 (native LNS, 1 worker, `interleave_search`): U1 **−43.8%** (40/0, Holm 1.5e-11). CP-SAT's own LNS subsolvers, run on one thread via `interleave_search`, do not close the gap to a hinted hand-built pipeline at 8 s.

**Beyond the 4-worker native configuration: not established.** U3, B2 vs B6 with 4 workers (B6 at 4 workers *is* CP-SAT's default multi-worker LNS portfolio, confirmed active in solver logs, `02_prior_work_and_novelty.md`): **−9.1%**, 15/5, **Holm 0.12 — not significant**. B2 vs B0 at 4 workers: 0.0%, 12/8, not significant either. With four workers, none of IAIP-SR, the critical-rounds candidate, or the time-window candidate is distinguishable from each other; all are ahead of unhinted B6 but the differences among the reoptimization strategies vanish once CP-SAT's own multi-worker scheduling LNS is running.

## 5. Do the gains persist across budgets, worker counts, and disruption types?

| Factor | B2 vs B0 (IAIP-SR) | Direction vs. U1 |
|---|---|---|
| 2 s (U4) | −6.2%, not significant (23/17, Holm 0.86) | weaker |
| 8 s (U1) | −22.4%, significant | — |
| 30 s (U5) | −19.2%, significant (17/3, Holm 0.0052) | similar |
| 4 workers (U3) | +0.0%, not significant | gone |
| arrival-only (U6) | −44.8%, significant | stronger |
| outage-only (U7) | −9.9%, not significant after Holm | weaker |
| high severity (U8) | −18.8%, significant | similar |
| published bases (U9) | −31.5%, significant (33/1) | stronger |

The improvement over IAIP-SR survives most budgets and disruption types but **disappears with 4 workers** and is **weak at 2 s** and **after outages**. It is strongest after arrivals and on published benchmark bases.

## 6. Early vs. final quality

U1 gap_B (final gap at the deadline): B2 vs B0 included in the family check (not separately reported above, but computed): mean gap_B 0.0163 (B2) vs 0.0224 (B0), a reduction in the same direction as PI, so the advantage is not purely an early-anytime effect — it persists to the final returned schedule as well.

## 7. Round-level diagnostics (U1, confirmatory; stop-on-fail protocol)

| Strategy | Rounds/instance | Improving rounds/instance | Round improvement rate | Mean \|N\| | Mean critical ops in N |
|---|---|---|---|---|---|
| crit_expand (B2) | 2.90 | 1.93 | 0.66 | 87.2 | 39.5 |
| time_window (B3) | 1.97 | 0.99 | 0.50 | 87.1 | 10.0 |
| random_matched (B1) | 1.62 | 0.63 | 0.39 | 84.6 | 9.6 |
| precedence (B4) | 1.30 | 0.30 | 0.23 | — (arcs 84.4) | 0.0 |

**Does the per-round success rate decay with round number?** Critical rounds hold a roughly constant 60–68% improvement rate from round 0 through round 8 (no visible decay); time-window holds steady near 45–52%; random starts at 36% and *rises* with round number, but this reflects survivorship under the stop-on-fail protocol (only instances whose earlier rounds succeeded reach later rounds), not a real trend. Precedence drops off sharply after round 2 and almost never reaches round 4+.

**Is the same critical region repeatedly selected?** Not separately instrumented in this run (recomputation is on by default, `recompute=True`, confirmed to matter in D2: forcing a single frozen neighbourhood, `recompute=0`, made things **worse** by +40.2% in development, §3 of doc 03). The critical region is recomputed from the current incumbent every round, so later rounds see a different, moved chain once an earlier round improved the schedule.

**Does neighbourhood quality correlate with chain length?** Not directly tested; left for future work. The per-round diagnostics record `L_path` and `U` so this could be computed from the raw run metadata without further runs.

## 8. Summary (answers to the brief's six questions, Part IX framing)

1. Repeated rounds alone: **not sufficient** (B1 vs B0 not significant).
2. Critical-region targeting beyond random: **established** (B2 vs B1, B2 vs B4, both confirmatory and under the mechanism-isolation protocol).
3. Critical-region targeting beyond time-window/precedence LNS: **established vs precedence; not established vs time-window** (inconclusive overall, confined to arrival disruptions, reversed under fixed-round accounting).
4. Beyond CP-SAT's native search: **established at 1 worker; not established at 4 workers**.
5. Survives budgets/workers/disruption types: **mostly, except 4 workers (gone) and 2 s / outages (weak)**.
6. Early vs. final quality: **both improve together**, not only the early anytime curve.

These findings jointly support **CONDITIONAL GO**: a real, reproducible advantage over IAIP-SR and over unstructured LNS, but no defensible claim that criticality specifically (as opposed to time-locality more generally) is what drives it, and no advantage once CP-SAT's own multi-worker LNS is engaged.
