# 03 — Event-Localized Repair (ELR)

Code: `phase0/event_localized_repair.py`. Tests: `tests/test_event_localized_repair.py` (22 tests). Data: `results/research_extension/e2_repair/dev_default.jsonl` (development streams 301–310 only).

## 1. Representation

A schedule is represented by its machine orders π_m, the sequence of operations processed on machine m. Together with the job chains, the orders define a graph G = (V, E_J ∪ E_M). For fixed orders, the earliest-start schedule is computed in one topological pass:

```
ready(v) = max( r_job(v) if v has no job predecessor in the graph,
                c(job predecessor), c(machine predecessor) )
s(v)     = nextfit_m(ready(v), p_v)   # earliest t >= ready(v) with [t, t+p_v) free of outages on m
c(v)     = s(v) + p_v
committed v: s(v) = committed start; error if nextfit result is later
```

**Claim:** for sorted, merged (disjoint) outage intervals, a single forward scan returns the earliest feasible start. The scan only raises t to the end of an outage that [t, t+p) intersects. Any feasible start ≥ the current t must also clear that outage, so it is ≥ its end.

**Verification.** `evaluate` is compared with an independent formulation on 150 random instances that include outages and release dates. The oracle is a CP-SAT model with the machine orders imposed as precedences, minimizing the sum of starts; its unique optimum is the earliest-start schedule. The two agree on every acyclic case. On cyclic orders, `evaluate` raises `CycleError` exactly when the oracle reports infeasibility.

## 2. Algorithm

```
ELR(I_t, S_prev):
  orders <- machine orders of S_prev restricted to surviving operations
            (sorted by previous start, then position in job, then id)
  core   <- new operations                                  (arrivals)
          u operations delayed by an outage under `orders`  (outages, not committed ones)
  remove core from orders
  for each job touching core, in decreasing total processing time:
      for each core operation v of the job, in job order:
          INSERT(v)
  S <- evaluate(orders); validate S independently
  on CycleError / CommitmentError / validation failure:
      return committed_dispatch(I_t) and record the cause

INSERT(v) on machine m with sequence x_0 .. x_{L-1}:
  heads  <- evaluate(orders)            # exact, with calendars
  tails  <- calendar-free longest path to the sink
  jp, js <- nearest job predecessor / successor of v already in the graph
  forbidden: positions before x_i in Anc(jp) u {jp}; positions after x_{i-1} in Desc(js) u {js};
             positions ahead of any committed operation on m
  for every allowed position i:
      s_v   <- nextfit_m(max(c(jp) or release, c(x_{i-1})), p_v)
      thr   <- s_v + p_v + max(tail(x_i), tail(js) or remaining work of v's job)
      key_i <- (max(current makespan, thr), thr, i)
  insert v at argmin key_i
```

**Cycle safety (proved).** With v absent, the graph still contains the arc jp → js, so it is acyclic. Placing v between x_{i−1} and x_i closes a cycle exactly when x_i reaches jp, or js reaches x_{i−1}, which is what the forbidden sets exclude. An allowed position always exists. If some descendant d of js preceded an ancestor a of jp on m, then d → … → a → … → jp → js → … → d would be a cycle in the current graph. A randomized test (`test_insertion_never_creates_cycles`) inserts every operation of 40 random instances in random order without ever producing a cycle.

**Insertion estimate.** Without outages, max(current makespan, thr) is the exact makespan of the partial graph after inserting v. Paths that avoid v are unchanged, and the longest path through v is head + p_v + tail. With outages, tails ignore the calendar, so the estimate is approximate. Only the final schedule is evaluated exactly.

This is the classical insertion principle for the job shop (Werner & Winkler 1995, *Discrete Applied Mathematics* 58(2):191–211), applied here to the operations a disruption affects. It is **not a new algorithm**. The design decision specific to this work is *which* operations are removed and re-inserted for each event type.

**Fallback.** `committed_dispatch` is MWKR dispatching that keeps committed operations at their committed starts and treats their intervals as blocked time. It needs every committed operation's job predecessors to be committed as well, which holds for prefix commitments. If not, it raises instead of returning an invalid schedule.

## 3. Complexity

Here n = |V|, K = number of outages, and c = number of core operations.

- `evaluate`: O(n + n·K_m), where K_m is the outage count on an operation's machine.
- `INSERT`: O(n) for heads, tails, ancestors and descendants, plus O(L) over positions.
- ELR overall: O(c · n).

Measured on development streams (median construction time): 4.3 ms at 10×10, 8.9 ms at 15×15, 11.9 ms at 20×20. The archived append repair takes 0.2–0.7 ms and MWKR 0.9–11 ms. At B = 8 s, ELR's cost is about 0.15% of the budget.

## 4. Locality of recomputation

`incremental_evaluate(orders, base, dirty)` recomputes only the operations reachable in the **new** graph from `dirty`.

**Proposition (locality).** Let:
- G be the old fixed-order graph;
- E_old be the earliest-start schedule of G on the old instance;
- G' be the new graph and E_new its earliest-start schedule on the new instance.

Assume the new calendar only adds outages. Let D contain every operation v of the new instance for which at least one of the following holds:
1. v is new, or p_v changed;
2. v's release date or commitment changed;
3. v's predecessor set in G' differs from its set in G (a job or machine predecessor changed);
4. v's old interval [E_old(v), E_old(v) + p_v) intersects an added outage.

Then E_new(v) = E_old(v) for every v outside D ∪ Reach⁺_{G'}(D).

**Proof.** By induction over a topological order of G'. Take v ∉ D ∪ Reach⁺(D).
- Every predecessor u of v in G' is also outside that set, since otherwise v would be reachable from D. By induction E_new(u) = E_old(u), and p_u is unchanged. Since v ∉ D, v has the same predecessors and release in G' as in G, so ready_new(v) = ready_old(v).
- The new calendar's feasible start set is contained in the old one. E_old(v) is the earliest old-feasible start ≥ ready, and by (4) its interval avoids every added outage, so it remains feasible. No earlier start is feasible under the new calendar, because none was feasible under the old one. Hence nextfit returns E_old(v).
- The commitment is unchanged. ∎

This is ordinary dirty-set propagation for longest paths, stated with its assumptions. It is not a new theorem. `test_incremental_equals_full_recomputation` checks it on 6 seeds × 5 delta mixes against full recomputation.

**Counterexamples: where the statement fails if an assumption is dropped.**
1. **Machine-order changes without marking the successor dirty.** Inserting b0 before a0 changes a0's predecessor set. Starting from base {c0: 0, a0: 1, b0: 6} with orders c0, b0, a0, incremental evaluation with an empty dirty set keeps a0 = 1, but the correct value is 4 (`test_counterexample_insertion_without_dirty_successor`).
2. **Reachability in the old graph.** New arcs (insertions) create paths that did not exist in G, so the closure must be computed in G'.
3. **Removed outages.** If the calendar loses an outage, an operation the outage delayed can start earlier even though its interval intersects no added outage. Condition (4) must then also include operations delayed by removed outages. The generator never removes outages.
4. **Non-semi-active previous schedules.** CP-SAT solutions can contain idle slack, so S_prev ≠ E_old. Unaffected operations still move to their earliest start when re-evaluated. The proposition concerns E_old, not S_prev. Reported stability metrics compare with S_prev.

**Practical relevance.** Full evaluation already takes 0.2–0.7 ms at these sizes, so incremental evaluation buys no meaningful speed. ELR uses full evaluation. The value of the event-localized design lies in *quality* (which operations are re-placed), not speed.

## 5. Stage E2 results (development streams, initial makespan only, exploratory)

Data: 300 stream instances (10×10/15×15/20×20 × seeds 301–310 × 10 deltas). The predecessor is a 2 s CP-SAT solution of the previous step. The gap is measured against the best of a 2 s CP-SAT solve and all candidates. All 2,100 candidate schedules were valid; ELR had no fallbacks.

| Median initial gap | append (Floor) | gap / regret / beam insertion | **ELR** | MWKR | SPT |
|---|---|---|---|---|---|
| arrival | 46.1% | 31.2 / 31.2 / 31.5% | **4.6%** | 6.1% | 16.0% |
| cancellation | 3.2% | 3.2% | 3.2% | 6.6% | 14.1% |
| duration jitter | 2.4% | 2.4% | 2.4% | 6.9% | 15.3% |
| outage | 7.8% | 7.8% | 7.8% | 6.7% | 19.7% |

Per instance:
- **Arrivals (n = 121):** ELR beats append on 121/121 and beats MWKR on 69 vs 51 (mean gap 5.7% vs 7.5%).
- **Cancellations and duration jitter:** ELR equals append by construction (no core). It beats MWKR on about 70% of instances.
- **Outages (n = 45):** ELR vs append is 7 better / 33 equal / 5 worse; vs MWKR 24 / 20. **Re-inserting outage-delayed operations gave no measurable improvement.** This is a negative result for that design choice.
- **Portfolio:** the best of {append, ELR, SPT, MWKR} has a mean gap of 3.8% / 2.6% / 2.5% / 4.1% (arrival / cancellation / jitter / outage), lower than any single member.

**Interpretation (exploratory).** ELR removes the arrival weakness of historical repair at the level of the initial incumbent. Whether this improves anytime quality after the solver continues is tested in E3–E5.
