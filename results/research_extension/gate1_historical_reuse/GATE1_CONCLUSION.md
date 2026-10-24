# Gate 1 — historical reuse vs fresh construction: conclusion

Produced by `.venv/bin/python -m phase0.analyze_gate1 results/research_extension/gate1_historical_reuse` (run on CPUs 16–19, 2026-10-24) from the raw run files in `runs/`. All numbers below are from `analysis.json`. Design and decision rule: `docs/research_extension/04_experimental_methodology.md` §3, written before any result was inspected.

## Setup

- **Streams:** 45 (10×10, 15×15 and 20×20 full job shops × stream seeds 101–115), each with 10 deltas.
- **Budget and solver:** B = 8 s; CP-SAT with one worker; solver seeds 0–4; performance cores.
- **Unit of inference:** the stream. Seeds and steps 1–10 are averaged within a stream.
- **Tests:** exact two-sided sign test with Holm correction over the 8-member family per protocol; stream-clustered bootstrap 95% CI (10,000 resamples).
- **z\*:** shared per physical instance across all methods, protocols and seeds.

## Integrity

| Check | Value |
|---|---|
| runs | 26,325 (17,988 FEASIBLE, 8,337 OPTIMAL) |
| not validated | 0 |
| no solution | 0 |
| runs with a deadline overrun > 0 | 17,835 |
| overrun, p99 | 0.016 s |
| overrun, max | 0.176 s |

Most runs exceed the deadline by a few milliseconds. This is solver return latency plus final validation. Overruns are recorded and included in every run, never excluded.

## Decision (predeclared rule)

The predeclared rule says historical reuse "has demonstrated measurable value" if Floor beats **both** SPT+Cold and MWKR+Cold under Protocol B, with Holm-adjusted p < 0.05 and a CI excluding 0.

**The rule is met.** Historical reuse has demonstrated measurable value on this stream family.

## Protocol B (primary: each method carries its own predecessor)

Stream mean PI:

| Method | PI |
|---|---|
| Floor | 0.0364 |
| Floor+Hint | 0.0430 |
| MWKR+Cold | 0.0433 |
| SPT+Cold | 0.0438 |
| Repaired-Hint-Only | 0.0457 |
| Cold | 0.0477 |
| Hint | 0.0576 |

Comparisons (rel. Δ = relative change in the first method's PI; negative means the first method is better):

| Comparison | rel. Δ | mean Δ [95% CI] | streams W/L | Holm p |
|---|---|---|---|---|
| Floor − Cold | −23.6% | −0.0112 [−0.0136, −0.0091] | 45/0 | 4.5e-13 |
| **Floor − SPT+Cold** | **−16.9%** | −0.0074 [−0.0093, −0.0057] | 45/0 | 4.5e-13 |
| **Floor − MWKR+Cold** | **−15.8%** | −0.0069 [−0.0086, −0.0052] | 44/1 | 1.0e-11 |
| Hint − Cold | +20.9% | +0.0100 [+0.0068, +0.0133] | 9/36 | 1.3e-4 |
| Floor+Hint − Floor | +18.2% | +0.0066 [+0.0038, +0.0096] | 9/36 | 1.3e-4 |
| Repaired-Hint-Only − Floor | +25.6% | +0.0093 [+0.0067, +0.0122] | 4/41 | 2.8e-8 |
| SPT+Cold − Cold | −8.1% | −0.0038 [−0.0045, −0.0032] | 45/0 | 4.5e-13 |
| MWKR+Cold − Cold | −9.2% | −0.0044 [−0.0052, −0.0036] | 45/0 | 4.5e-13 |

## Protocol A (common predecessor from a reference chain)

| Comparison | rel. Δ | mean Δ [95% CI] | streams W/L | Holm p |
|---|---|---|---|---|
| Floor − Cold | −21.5% | −0.0102 [−0.0122, −0.0084] | 45/0 | 4.5e-13 |
| Floor − SPT+Cold | −14.6% | −0.0064 [−0.0079, −0.0049] | 42/3 | 4.3e-9 |
| Floor − MWKR+Cold | −13.5% | −0.0058 [−0.0073, −0.0044] | 41/4 | 3.7e-8 |
| Hint − Cold | +22.7% | +0.0108 [+0.0073, +0.0146] | 5/40 | 1.6e-7 |
| Floor+Hint − Floor | +15.3% | +0.0057 [+0.0033, +0.0083] | 12/33 | 2.5e-3 |
| Repaired-Hint-Only − Floor | +25.8% | +0.0097 [+0.0071, +0.0124] | 4/41 | 3.7e-8 |

The two protocols agree in sign on every comparison. Protocol A gives the history-based methods the same predecessor; its effects are slightly smaller.

## What the result says, and what it does not

1. **The value comes from retaining the repaired incumbent, not from hinting.**
   - Hinting CP-SAT with the previous solution is worse than Cold.
   - Adding the hint to Floor is worse than Floor alone.
   - Hinting with the repaired schedule but not retaining it is worse than Floor.
   - All three hold on most streams under both protocols.
2. **The effect is not uniform across delta types** (exploratory, Protocol B, Floor − MWKR+Cold):

   | Delta | streams | rel. Δ PI | W/L | median initial gap: Floor | median initial gap: MWKR |
   |---|---|---|---|---|---|
   | arrival | 45 | **+4.8%** | 5/40 | 53.1% | 15.1% |
   | cancellation | 44 | −23.0% | 44/0 | 5.9% | 15.2% |
   | duration jitter | 45 | −30.0% | 42/3 | 5.1% | 17.0% |
   | outage | 35 | −19.4% | 30/5 | 10.6% | 16.0% |

   After job arrivals, Floor's repaired incumbent (new jobs appended after the old schedule) is far worse than an MWKR dispatch, and Floor loses on 40 of 45 streams. This is the weakness that event-localized repair (insertion of new operations) and the portfolio are designed to address. It is why the strongest fresh baseline, not Cold, is the comparator IAIP-SR must beat.
3. **By size** (exploratory, Protocol B, Floor − MWKR+Cold):
   - 10×10: −19.4% (14/1);
   - 15×15: −12.9% (15/0);
   - 20×20: −17.6% (15/0).
4. **Other metrics** (Protocol B, Floor − MWKR+Cold):

   | Metric | rel. Δ | W/L | 95% CI |
   |---|---|---|---|
   | capped PI | −15.8% | 44/1 | [−0.0086, −0.0052] |
   | late-window PI [B/8, B] | −12.4% | 40/4 | [−0.0056, −0.0031] |
   | final gap at B | −4.8% | 27/9 | [−0.0014, −0.0005] |

   The advantage is not only an earlier first incumbent: it persists in the late window and in the final gap, though the final-gap effect is small.
5. **Scope.**
   - Synthetic full job shops of three sizes, one delta mix, medium severity, B = 8 s, one worker.
   - No claim is made for other budgets, worker counts, delta mixes or published benchmark bases until E6 is run.
   - These stream-level, five-seed results supersede the instance-level significance figures in the archived write-ups for the reuse-vs-fresh question.
