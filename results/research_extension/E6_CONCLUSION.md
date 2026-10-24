# E6 — robustness of the frozen IAIP-SR configuration (exploratory)

**Provenance**
- Specified in `docs/research_extension/04_experimental_methodology.md` §6 on 2026-10-24, after the confirmatory analysis and before any E6 run.
- Runner: `scripts/run_e6.sh`. E6e was run separately and added to §6 before it ran.
- Analysis: `.venv/bin/python -m phase0.analyze_e6 <dirs>`, output in `e6_analysis.json`. E6e output: `e6e_lns/analysis.json`.

**Common setup**
- Configuration: the frozen one, unchanged.
- Streams: seeds 601–610, never used before; 15×15 and 20×20; 10 deltas each.
- Solver: seed 0.
- Hardware: performance cores, except E6e, which ran on the efficiency cores.

**Statistics**
- Unit: the stream. For E6d the unit is the published base instance, with its two streams averaged first.
- Exact sign test with Holm correction over the four comparisons within each campaign, plus a stream-clustered bootstrap 95% CI.

**Status:** every number here is **exploratory**, because E6 was not part of the confirmatory family.

## Integrity

| Campaign | records | not validated | no solution | max overrun (s) |
|---|---|---|---|---|
| E6a B = 2 s | 1,100 | 0 | 0 | 0.035 |
| E6a B = 30 s | 1,100 | 0 | 0 | 0.096 |
| E6b 4 workers | 1,100 | 0 | 0 | 0.033 |
| E6c arrival-only | 1,100 | 0 | 0 | 0.019 |
| E6c outage-only | 1,100 | 0 | 0 | 0.016 |
| E6c high severity | 1,100 | 0 | 0 | 0.017 |
| E6d published bases | 3,740 | 0 | 0 | 0.038 |
| E6e archived baselines | 880 | 0 | 0 | 0.280 (archived LNS) |

## Results: IAIP-SR vs comparators, stream mean PI

Δ = relative difference in mean PI; W/L = units on which IAIP-SR is better / worse. "ns" means Holm p ≥ 0.05 within the campaign.

| Setting | units | vs Fresh+Cold | vs Port+Hint (selective stage) | vs Floor | vs Cold |
|---|---|---|---|---|---|
| B = 2 s | 20 | −36.1% (17/3) | −7.8% (13/7) **ns**, p = 0.26 | −28.2% (15/5) **ns**, p = 0.083 | −58.4% (20/0) |
| B = 30 s | 20 | −55.3% (20/0) | −33.5% (18/2) | −45.2% (20/0) | −57.3% (20/0) |
| 4 workers, B = 8 s | 20 | −65.7% (20/0) | −9.4% (10/10) **ns**, p = 1 | −60.6% (20/0) | −67.9% (20/0) |
| arrival-only | 20 | −63.1% (20/0) | −59.1% (20/0) | −64.5% (20/0) | −66.4% (20/0) |
| outage-only | 20 | −42.2% (18/2) | −24.8% (17/3) | −25.2% (16/4) | −47.7% (18/2) |
| high severity | 20 | −58.5% (20/0) | −41.3% (17/3) | −50.0% (19/1) | −61.5% (20/0) |
| published bases (ta, dmu, swv, yn) | 34 | −61.2% (34/0) | −37.9% (33/1) | −54.3% (34/0) | −63.7% (34/0) |

Every comparison not marked ns has Holm p ≤ 0.012.

**Final gap at B** for IAIP-SR vs Fresh+Cold:
- the gap is lower in every setting: −36.2% to −76.5%;
- the bootstrap CI excludes 0 in every setting **except outage-only** (−36.2%, CI [−0.0080, +0.0013]);
- **no setting shows a final-gap regression.**

**Published bases by family** (vs Fresh+Cold; uncorrected sign tests, small n):

| Family | Δ PI | W/L | p |
|---|---|---|---|
| Taillard ta01–ta20 | −61.1% | 20/0 | < 1e-5 |
| DMU | −70.1% | 5/0 | 0.0625 |
| SWV | −61.5% | 5/0 | 0.0625 |
| YN | −45.4% | 4/0 | 0.125 |

With 4 or 5 bases, a sign test cannot reach p < 0.05 even when every base wins. These families are consistent with the overall result but are not separately significant.

**E6e: archived neighbourhood baselines** (efficiency cores, 20 streams):

| IAIP-SR vs | Δ PI | W/L |
|---|---|---|
| Floor | −45.0% | 20/0 |
| LNS from the previous solution | −84.2% | 20/0 |
| fix-and-optimize 50% | −77.6% | 18/2 |

## What E6 changes in the conclusions

1. **The overall gain is robust, and it is not a short-budget artefact.** Against the fresh-incumbent baseline the gain is larger at B = 30 s (−55%) and with 4 workers (−66%) than in the confirmatory setting (−43%). It also holds on published-instance bases (34/34) and at high severity. The confirmatory caveat that the gain might come only from a weak 8 s single-worker baseline is not supported.
2. **The selective stage's own contribution depends on the compute regime.**
   - It is large at B = 30 s, on arrival-only streams (−59%), at high severity and on published bases.
   - It is **not detectable at B = 2 s** (13/7) **or with 4 workers** (10/10).
   - With 4 workers, the hinted continuation from the portfolio incumbent already reaches almost the same quality (PI 0.0117 vs 0.0106).
   - With 2 s, there is little time to split.

   The claim "the selective stage adds value" therefore holds for the confirmatory setting (one worker, 8 s) and the settings above, not universally.
3. **Arrivals favour IAIP-SR most.** On arrival-only streams, Floor (0.0504) and Port+Hint (0.0437) are close to Fresh+Cold (0.0484). IAIP-SR (0.0179) is far ahead, mostly because of the restricted stage.
4. **Outages remain the weakest case.** The effect is smallest there: vs Floor −25%, 16/4. The final-gap gain is not established.
5. **Freeze-only streams were not run**, for the reason stated in §6: the generator needs the previous solution at generation time.
