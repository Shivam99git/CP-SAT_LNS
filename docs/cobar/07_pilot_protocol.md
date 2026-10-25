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
