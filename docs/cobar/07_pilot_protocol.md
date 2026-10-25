# COBAR 07 — Pilot protocol (development data; written before the pilot runs)

- **Written:** 2026-10-25, before any COBAR run.
- **Status of all pilot results:** exploratory. They are used to choose what to freeze; they are not evidence for any claim.
- **Data:** streams 301–310 (15×15, 20×20; these were IAIP-SR's development seeds), 10 deltas, generator defaults unless stated, solver seed 0. No seed ≥ 900 is touched before the confirmatory freeze.

## Methods

| ID | Method string | Role |
|---|---|---|
| A0 | `iaip\|portfolio=full\|global_mode=hinted` | portfolio + hinted global CP-SAT |
| A1 | `iaip\|portfolio=full\|alpha=0.6\|neighbourhood=N5\|global_mode=hinted` | IAIP-SR (archived code path) |
| A2 | `cobar\|neighbourhood=iaip\|use_certificate=1\|skip_certified=1\|global_certificate=0\|policy=fixed` | IAIP-SR + certificate skip |
| A3 | `cobar\|neighbourhood=iaip+release\|use_certificate=1\|skip_certified=0\|global_certificate=0\|policy=fixed` | IAIP-SR + certificate-guided release |
| A4 | `cobar\|neighbourhood=iaip\|use_certificate=0\|skip_certified=0\|global_certificate=0\|policy=budget` | IAIP-SR + budget-only policy (skip the local stage if workers ≥ 4 or B < 4 s) |
| A5 | `cobar\|neighbourhood=iaip\|use_certificate=1\|skip_certified=1\|global_certificate=0\|policy=cert+budget` | IAIP-SR + certificate-aware policy |
| A6 | `cobar\|neighbourhood=iaip+release\|use_certificate=1\|skip_certified=1\|global_certificate=1\|policy=cert+budget` | full single-round COBAR |
| A7 | ≡ A4 by construction | COBAR with the certificate disabled. Without the certificate, the release, skip and certificate rules all vanish, leaving A4's configuration. Not run twice |
| A8 | `cobar\|neighbourhood=iaip+release\|use_certificate=1\|skip_certified=1\|global_certificate=1\|policy=fixed` | full COBAR with the budget policy disabled |
| A9 | `cobar\|neighbourhood=none\|use_certificate=0\|global_certificate=0\|policy=fixed\|global_params=interleave` | portfolio + hinted CP-SAT with `interleave_search` (native scheduling LNS on one core) |
| A6r | A6 + `rounds=10` | COBAR with certificate-guided rounds (`release+expand`) |
| A10 | `cobar\|neighbourhood=iaip\|use_certificate=0\|skip_certified=0\|global_certificate=0\|policy=fixed\|rounds=10\|round_neighbourhood=iaip` | same rounds, IAIP-SR neighbourhood re-centred on the new incumbent (no certificate) |
| A12 | as A10 with `round_neighbourhood=critical` | same rounds, classical critical-operations neighbourhood |

**Pre-specified policy parameters** (not tuned before the pilot): α_long = 0.6, α_short = 0.2, gap threshold 0.02, skip_workers = 4, min_budget_s = 4.

## Runs

| Pilot | Setting | Streams | Methods |
|---|---|---|---|
| P1 | B = 8 s, 1 worker | 20 (15/20 × 301–310) | all of the above |
| P2 | B = 2 s | 10 (15/20 × 301–305) | A0, A1, A4, A6, A6r, A9 |
| P3 | B = 30 s | 10 | same |
| P4 | 4 workers per run, B = 8 s (process pinned to 4 physical cores) | 10 | same |
| P5 | arrival-only, B = 8 s | 10 | same |
| P6 | outage-only, B = 8 s | 10 | same |
| P7 | high severity, B = 8 s | 10 | same |

## Analysis

- **Metrics:** stream-mean PI over steps 1–10, with a shared z\* per physical instance within each pilot; final gap; time to first incumbent; stage timings; certificate statistics.
- **Comparisons:** paired, over streams.
- **Primary pilot question:** does any COBAR variant beat A1 (IAIP-SR) and A0 in P1?
- **Component questions:** A2 vs A1, A3 vs A1, A4 vs A1, A5 vs A4, A6 vs A4, A8 vs A1, A6r vs A10, A6r vs A12, A9 vs A0.

**Gate:** if no certificate-dependent variant beats its certificate-free counterpart (A4, A10 or A12), the certificate is not credited. In that case the confirmatory study either becomes CONDITIONAL GO with the simpler variant, or the decision is NO-GO.

---

## Round 1 results (P1–P7, development streams, solver seed 0)

Source: `results/cobar/pilot/p1_b8/analysis.json` and `regimes_analysis.json`. All runs validated. Exploratory.

**P1 (B = 8 s, 1 worker, 20 streams)**

| Comparison | ΔPI | W/L | CI | Interpretation |
|---|---|---|---|---|
| A2 / A3 / A5 / A6 / A8 vs their counterparts | −1.9% to +2.4% | 7/13 – 12/8 | all include 0 | the single-round certificate components (skip, release, certificate-aware allocation) change nothing |
| A4 vs A1 | −4.1% | 11/9 | includes 0 | the budget rule is inactive at 8 s / 1 worker; this is the noise level |
| A9 vs A0 | −1.4% | 9/11 | includes 0 | native single-core interleaved LNS ≈ hinted search |
| **A6r vs A1** | **−26.2%** | 14/6 | [−0.0095, −0.0029] | certificate-guided rounds help |
| A6r vs A10 (rounds, `iaip` neighbourhood) | −27.6% | 16/4 | [−0.0097, −0.0038] | |
| A6r vs A12 (rounds, `critical` neighbourhood) | −18.0% | 14/6 | [−0.0064, −0.0015] | |
| A12 vs A1 | −9.9% | 16/4 | includes 0 | |

**P2–P7 (10 streams; A6r uses `cert+budget`)**

| Setting | A1 vs A0 | A6r vs A1 |
|---|---|---|
| 2 s | −31.3% (8/2) | **+46.6% (2/8)**: the budget rule skipped the useful local stage |
| 30 s | −30.0% | +4.4% (3/7); A9 is best here (−34% vs A0) |
| 4 workers | −27.5% (9/1) | **+34.6% (3/7)**: the budget rule skipped the useful local stage. A9 with `interleave_search` and 4 workers is pathological (+318% vs A0) |
| arrival-only | −50.7% | −36.8% (6/4) |
| outage-only | −27.9% | −3.4% (4/6) |
| high severity | −35.9% | −12.3% (7/3) |

### Negative results recorded

1. **The pre-specified budget-only rule is harmful** (skip the local stage if B < 4 s or workers ≥ 4).
   - It was derived from IAIP-SR E6, where the selective stage was *not significant* at 2 s (13/7) and with 4 workers (10/10).
   - Treating a non-significant result as "no effect" was an error.
   - On these development streams the local stage helps in both settings.
2. **The certificate's skip, release and allocation uses have no measurable effect** at 8 s.

## Round 2 (written before it runs)

### Question
Is the gain of A6r due to the certificate (min-cut seeding), or to repeated breadth-first neighbourhoods around any seed?

### Simplified candidate and controls

All share `cobar|neighbourhood=iaip|use_certificate=0|skip_certified=0|global_certificate=0|policy=fixed|rounds=10` and differ only in `round_neighbourhood`:

| ID | `round_neighbourhood` | Seeds of the 25% breadth-first expansion |
|---|---|---|
| C1 | `release+expand` | endpoints of a minimum cut of the incumbent's longest binding chains |
| C2 | `critical+expand` | every operation on those chains |
| C3 | `random+expand` | the same number of uniformly random operations (deterministic per instance) |

**Interpreting C1 vs C3.** If C1 beats C3, *where* the rounds search matters. Only C1 vs C2 separates the min cut from a critical-path seeding, which is known prior art.

### Runs

| Run | Setting | Streams | Solver seed | Methods |
|---|---|---|---|---|
| P8 | B = 8 s, 1 worker | 15/20 × 301–310 | **1** (replication) | A0, A1, A6r, C1, C2, C3 |
| P9a | B = 2 s | 15/20 × 301–305 | 1 | A0, A1, C1 |
| P9b | 4 workers | 15/20 × 301–305 | 1 | A0, A1, C1 |
| P9c | B = 30 s | 15/20 × 301–305 | 1 | A0, A1, C1 |

### Decision rules for the freeze (development only)

1. If C1 does not beat C3 at 8 s, the certificate is not credited. The candidate for confirmation is then the simplest variant that beats A1.
2. If C1 is clearly worse than A1 at 2 s or with 4 workers, the freeze must address it, and the reason is documented.
