# COBAR 03 — Improvement-opportunity certificates: theory

- **Code:** `phase0/cobar_certificates.py`, `phase0/cobar_neighborhood.py`.
- **Tests:** `tests/cobar/test_certificates.py`, `test_neighborhood.py`, `test_counterexamples.py`.
- **Classification** (per `02_related_work_and_novelty.md`):
  - every bound and the no-improvement statement below are **known lemmas**, adapted;
  - the release cut is a **standard reduction** (Menger / max-flow min-cut) applied to a specific graph.

  Nothing in this document is claimed as a new theorem.

## 1. Problem and neighbourhoods

**Instance**
- Jobs J; each job j has a sequence of operations v with machine m(v), integer duration p_v ≥ 0, and release date r_j ≥ 0 on its first operation.
- Outages: integer intervals [a, b) per machine, pairwise disjoint on each machine.
- Commitments: s_v = f_v for v ∈ F.

**Feasible schedule** (validator semantics, `schedule_validator.py`): integer starts s_v ≥ 0 satisfying
1. the job sequence: s_w ≥ s_v + p_v for consecutive operations of a job;
2. the first operation's release date;
3. no two positive-length intervals on one machine overlap, and none overlaps an outage;
4. the commitments.

**The CP-SAT model** (`build_research_model`) is a *subset* of these semantics. It is stricter in two ways, both found by the oracle tests:
- a zero-length operation may not lie strictly inside an outage or another interval (C4);
- all ends are bounded by `horizon` = Σp + max outage end + 1 (C5).

The archived experiments contain no zero durations, release dates or commitments (checked over all 373 instance files), so the two semantics coincide on them.

**Restricted problem P(S, N, R).** Given a feasible incumbent S with makespan U, free operations N and released arcs R, take the feasible schedules that also satisfy

> s_v ≥ s_u + p_u for every kept arc (u, v) ∈ K(S, N, R).

Here K(S, N, R) is the set of pairs consecutive in S's machine order, restricted to operations of positive duration outside N, minus R. The machine order is sorted by (start, position in job, id).

C*(N, R) denotes the minimum makespan over P(S, N, R).

**Lemma 0 (membership).** S ∈ P(S, N, R).
- *Proof.* If u precedes v on a machine in S and both have positive duration, their intervals are disjoint and s_u < s_v, so s_u + p_u ≤ s_v. ∎
- *Scope.* This needs the positive-duration restriction. IAIP-SR's builder also chains zero-length operations; then the lemma fails (C3). This is irrelevant to the archived data, which has no zero durations.

## 2. The lower bound

Let G be the graph of job arcs and kept arcs. It is acyclic, because S satisfies all of its arcs and every arc forces a strictly later start, except arcs out of zero-length operations. An implementation check rejects cyclic input in any case.

In a topological order of G define:
- ready(v) = max(r_j if v is the first operation of job j else 0, max over preds u of h(u) + p_u);
- h(v) = f_v if v ∈ F; else nextfit_m(v)(ready(v), p_v) if p_v > 0; else ready(v).

Here nextfit_m(t, p) is the least t' ≥ t with [t', t'+p) disjoint from every outage of machine m.

> L_path = max_v h(v) + p_v
>
> L_mach = max over machines m of [ min_{v on m} h(v) + Σ_{v on m} p_v + min_{v on m} q(v) ]
>
> q(v) = calendar-free longest path after v in G: q(v) = max over successors w of p_w + q(w), and 0 if v has none.
>
> L(N, R) = max(L_path, L_mach)

**Proposition 1 (validity).** For every schedule s' ∈ P(S, N, R): s'_v ≥ h(v) for all v, and C_max(s') ≥ L(N, R). Hence L(N, R) ≤ C*(N, R).

*Proof.* By induction over the topological order:
1. Every predecessor u of v satisfies s'_u ≥ h(u), so s'_v ≥ s'_u + p_u ≥ h(u) + p_u. The release constraint gives s'_v ≥ r_j. Hence s'_v ≥ ready(v).
2. If v ∈ F, then s'_v = f_v = h(v). If ready(v) > f_v, the problem has no feasible schedule; the implementation raises, which never happens when S ∈ P.
3. If p_v > 0, s'_v is an outage-free start ≥ ready(v). nextfit returns the least such start, so s'_v ≥ h(v). The forward scan over outages sorted by start is exact for disjoint outages (`03_event_localized_repair.md` §1), and nextfit is monotone in t.
4. If p_v = 0, h(v) = ready(v) ≤ s'_v. No outage reasoning is applied: the validator lets a zero-length operation sit inside an outage.

This gives C_max(s') ≥ s'_v + p_v ≥ h(v) + p_v for every v, i.e. C_max(s') ≥ L_path.

For L_mach, fix a machine m. Its operations run without overlap, each starting at or after min h, so the last one, w, completes at or after min h + Σp. After w, its successors in G need at least q(w) ≥ min q more time. ∎

The proposition also holds for the CP-SAT restricted model, whose feasible set is a subset of P(S, N, R).

**Corollary 1 (no-improvement certificate; known).** Since S ∈ P, C*(N, R) ≤ U. If L(N, R) ≥ U, then C*(N, R) = U: no schedule in the neighbourhood is better than S. For integer data, L > U − 1 is equivalent.
- The certificate is a statement about P(S, N, R) only.
- For N = all operations, K is empty and P is the full problem. The global certificate L ≥ U then proves S optimal.
- For smaller N, a decisive certificate says nothing about the full problem (C8).

**Complexity.**
- Building G and the heads costs O(n + |K| + Σ_v k_{m(v)}), where k_m is the number of outages on machine m.
- Tails and the machine bound cost O(n + |K|).
- Measured on the development replay (225–400 operations): about 1 ms (`dev_e5c/cobar_certificate_diagnostic.jsonl`).

## 3. Obstructions and the release cut

**Binding subgraph**
- An arc (u, v) is *binding* if h(u) + p_u = ready(v) = h(v), i.e. v is not held up by an outage and not committed.
- v is a *chain start* if h(v) would not decrease even if all its incoming arcs were removed. That is: v is committed, or held up by an outage, or its release date or 0 attains ready(v). The last case includes ties with predecessors; see C7.
- An *obstructing chain* is a path of binding arcs from a chain start to an operation t with h(t) + p_t = U.
- Its length, counted from the start's head, is exactly U, because heads add up along binding arcs.

**Lemma 2.** If L_path = U, every path of G that realizes U lies in the binding subgraph and contains an obstructing chain as a suffix starting at a chain start. (Trace the binding predecessors back from the end of the path.)

**Releasing arcs.** Removing an arc of K can only lower heads (monotonicity). It never creates a path.

**Proposition 2** (the minimum cut is the minimum hitting set; standard). Build a flow network:
- arcs of the binding subgraph, with capacity w(e) for a releasable machine arc and ∞ for a job arc;
- a super-source linked to every chain start, and every sink t linked to a super-sink, all with capacity ∞.

Then a minimum s–t cut is a minimum-weight set of releasable machine arcs meeting every obstructing chain. If the cut is infinite, some obstructing chain contains no releasable arc.
- *Proof.* s–t paths of the network correspond one-to-one to obstructing chains. An edge set meets all s–t paths iff it is an s–t cut (Menger). Only finite-capacity arcs can be in a finite cut. ∎

**Proposition 3** (one cut suffices without calendar effects). Suppose that after removing a finite minimum cut C, no operation of the released graph is held up by an outage at a head where it was not held up before. Then L_path(N, R ∪ C) < U.

*Proof.* Suppose some t in the new graph has h'(t) + p_t = U. Trace a binding chain backward to a new chain start s'.
1. Every arc on it exists in the old graph, and the old heads are at least the new heads (monotonicity).
2. Summing along the chain gives h(t) ≥ h(s') + Σp ≥ h'(s') + Σp = h'(t) = h(t). So all old and new heads on the chain agree, and every arc on it was binding before.
3. s' is a new chain start whose head did not change. By the assumption it is held by its release date, a commitment or 0, so it was an old chain start too.
4. The chain was therefore an old obstructing chain avoiding C, contradicting Proposition 2. ∎

The assumption is violated in C6: after the cut, an operation becomes held by an outage at exactly its old head. This is why `release_obstructions` recomputes the certificate and iterates.
- *Termination:* each iteration adds at least one arc to R (mode `arcs`) or one operation to N (mode `ops`).
- *Output:* the final certificate is recomputed from scratch, so whatever the loop returns is covered by Proposition 1.

**Proposition 3 is a pure statement about the bound.** It does not imply that C*(N, R ∪ C) < U, nor that CP-SAT finds an improvement.

**Machine-bound obstructions.** If L_mach ≥ U, releasing arcs cannot help: the load term Σp is order-independent. The loop returns `machine_obstructed`.

## 4. Counterexamples

Each counterexample is an executable test.

| ID | Statement it refutes | Example | Test |
|---|---|---|---|
| C1 | "the incumbent's observed critical path is a lower-bound obstruction" | one machine, p = 2, 2, S = {0, 5}: U = 7 but L_path(∅, ∅) = 4 (idle time); the restricted optimum is 4 | `test_C1_…` |
| C3 | "the incumbent satisfies the kept arcs" (IAIP-SR builder, zero durations) | a zero-length operation at the start of, or inside, a positive interval on its machine gets an arc s_w ≥ s_u + p_u that S violates | `test_bound_sound_against_cpsat_with_zero_durations` (found there); fixed by chaining only positive durations |
| C4 | "the validator and the CP-SAT model have the same feasible set" | a zero-length operation at 7 inside outage [6, 9): the validator accepts, CP-SAT INFEASIBLE (OR-Tools 9.15) | `test_zero_length_semantics_cpsat_vs_validator` |
| C5 | "every feasible schedule fits the model horizon" | with release dates and idle time a feasible schedule can end after Σp + max outage end + 1 | generator guard in `test_certificates.py` |
| C6 | "one cut always removes the obstruction" | machine 0: x (6) before v (4); job u (m2, 3) → v → w (m1, 3); outage [7, 10) on m1. Chain x→v→w = 13 = U. After cutting (x, v), v ends at 7 and w is held by the outage at 10: still 13 (in fact 13 is optimal) | `test_C6_…` |
| C7 | "an operation with a binding predecessor is not a chain start" (a bug in the first implementation) | release date equal to the predecessor's completion: cutting the predecessor arc leaves the head unchanged | `test_without_outages_one_cut_removes_the_path_obstruction` (regression) |
| C8 | "a decisive neighbourhood certificate shows the incumbent cannot be improved" | 2 machines, jobs a (3, 1), b (1, 3), S with U = 7: the certificate is decisive for N = R = ∅, but the optimum is 5 | `test_C8_…` |

## 5. Exact-oracle evidence

| Test | Oracle | Cases | Decisive | Violations |
|---|---|---|---|---|
| `test_bound_sound_against_enumeration` | all machine orders + independent earliest start (positive durations; outages, releases, commitments, random N and R, slack incumbents) | 400 | 177 | 0 |
| `test_bound_sound_against_cpsat_with_zero_durations` | CP-SAT restricted model solved to optimality | 200 | 58 | 0 |
| `test_global_certificate_sound` | CP-SAT full model | 150 | ≥ 5 | 0 |
| `test_cut_hits_every_obstructing_chain_and_is_minimum` | enumeration of chains and of subsets of releasable arcs | 300 decisive cases | — | 0 |
| `test_release_loop_outcomes_are_consistent_and_sound` | CP-SAT restricted model | 250 × 2 modes | — | 0 |
| `test_max_flow_equals_brute_force_min_cut` | brute-force edge cuts | 300 graphs | — | 0 |

## 6. Scope of the guarantees

- **Valid:** for the problem class of §1, with integer data and disjoint outages per machine. The membership lemma additionally needs positive durations for the operations that are chained.
- **Not implied:**
  - nothing about the unrestricted problem, except the global certificate;
  - nothing about what CP-SAT finds within a time limit;
  - nothing about other objectives (only makespan).
- **Empirically weak on IAIP-SR neighbourhoods:** decisive in 3 of 120 development steps, and it explains 3 of 29 CP-SAT INFEASIBLE local stages (`docs/cobar/01` §F1, diagnostic above).
