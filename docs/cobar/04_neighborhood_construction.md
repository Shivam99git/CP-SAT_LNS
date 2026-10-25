# COBAR 04 — Neighbourhood construction

- **Code:** `phase0/cobar_neighborhood.py` (release), `phase0/cobar.py` (`_neighbourhood`, `build_cobar_restricted_model`).
- **Tests:** `tests/cobar/test_neighborhood.py`, `test_cobar.py`.
- **Theory:** `03_certificate_theory.md` §3.

## 1. Representation

A neighbourhood is a pair (N, R):
- **N** — operations whose machine order is free;
- **R** — released machine arcs.

The restricted CP-SAT model is the full research model (job precedence, no-overlap with outages, release dates, commitments, hinted with the incumbent), plus:
- s_v ≥ s_u + p_u for every kept arc, i.e. the consecutive pairs of the incumbent's machine order among positive-duration operations outside N, minus R;
- C_max ≤ U − 1.

No original constraint is relaxed; only machine-order restrictions are added and then partly removed. With N = R = ∅ the kept arcs are the incumbent's own orders. With N = all operations the model is the full problem.

## 2. Neighbourhood types

The brief's N0–N5 are renamed to avoid clashing with IAIP-SR's names.

| COBAR name | Brief | Definition | Uses the certificate |
|---|---|---|---|
| `iaip` | N0 | IAIP-SR's N5: breadth-first expansion of the disruption set D over job and machine adjacency, capped at 25% of operations | no |
| `closure` | N1 | forward closure of D in the incumbent's graph | no |
| `critical` | N2 | operations on a longest path of the incumbent's orders (calendar-free tails) | no |
| `release` | N3 | N = ∅; R = the release loop's arcs on the incumbent's full order graph | yes |
| `release+expand` | N4 | breadth-first expansion (25%) seeded at the endpoints of a minimum cut of the longest binding chains of the incumbent's orders. If the incumbent has idle time, the chains of its left-shifted version (length L_path(∅, ∅)) are used | yes |
| `iaip+release` | N5 | `iaip`; if its certificate is decisive, release obstructing arcs until it is not (mode `arcs`: arcs go to R; mode `ops`: their successors join N) | yes |

## 3. Release procedure

`release_obstructions(instance, S, N, R, mode)`:
1. Compute the certificate of (N, R).
2. While it is decisive:
   - if only the machine bound is decisive: stop (`machine_obstructed`);
   - build the binding subgraph;
   - compute a minimum cut (unit weights; Edmonds–Karp);
   - if the cut is infinite: stop (`unreleasable`);
   - release the cut and recompute the certificate.
3. Return:
   - **status:** `not_needed`, `released`, `unreleasable`, `machine_obstructed` or `iteration_cap` (20);
   - **result:** the final (N, R), both certificates, the number of iterations, the cut cost and the time taken.

**What a status means** (`03` Propositions 2–3):

| Status | Meaning | Not implied |
|---|---|---|
| `released` | the final certificate is not decisive, i.e. the cheap bound no longer excludes improvement | does not imply that an improving schedule exists, nor that CP-SAT finds one |
| `unreleasable` or `machine_obstructed` | the final certificate is decisive: P(S, N, R) contains no better schedule (sound) | — |

**Weights.** Unit cost per arc. The brief lists other candidate weights (affected operations, neighbourhood size, disruption proximity, commitment penalties). They were not implemented: there was no evidence they would matter, and none may depend on solver outcomes.

## 4. Verification

| Property | Test | Result |
|---|---|---|
| max-flow value = brute-force minimum edge cut; returned cut disconnects s–t | `test_max_flow_equals_brute_force_min_cut` (300 graphs) | pass |
| the cut meets every obstructing chain (all chains enumerated) | `test_cut_hits_every_obstructing_chain_and_is_minimum` (300 decisive cases) | pass |
| the cut is a minimum hitting set (subsets of releasable arcs enumerated) | same | pass |
| an infinite cut ⇔ some chain has no releasable arc | same | pass |
| without outages and commitments, one cut makes L_path < U (Prop. 3) | `test_without_outages_one_cut_removes_the_path_obstruction` (200 cases) | pass (after fixing C7) |
| release-loop status consistent with the final certificate; final bound ≤ exact restricted optimum ≤ U; kept arcs as specified; modes keep N or R fixed as documented | `test_release_loop_outcomes_are_consistent_and_sound` (250 × 2 modes, CP-SAT oracle) | pass |
| unreleasable chain (single long job) | `test_single_long_job_is_unreleasable` | pass |
| restricted model contains the incumbent; kept arcs equal IAIP-SR's for positive durations | `test_restricted_model_contains_incumbent_and_matches_iaip_for_positive_durations` | pass |
| empty / global neighbourhoods | N = ∅ and N = all are drawn in the oracle tests (`_random_N_R`) | pass |

**Not separately tested:**
- disconnected precedence structures (generated instances include single-operation jobs, but no targeted test);
- infeasible historical schedules: the portfolio validates every member before it can become the incumbent, so an infeasible history never reaches the neighbourhood code.

## 5. Cost on development data

Replay of `dev_e5c`, 120 steps, 15×15 and 20×20 (`scripts/cobar/diagnose_certificates.py`):

| Item | Value |
|---|---|
| certificate, median | 0.9 ms (max 1.3 ms) |
| release loop, median | 0.9 ms (max 2.7 ms) |
| release needed (certificate of `iaip` decisive) | 3 of 120 steps |
| arcs released in those steps | 1 each |
