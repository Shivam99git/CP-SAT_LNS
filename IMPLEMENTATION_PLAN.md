# Implementation Plan: Persistent Contextual-Bandit LNS for CP-SAT over Agent-Generated Problem Streams

**Target venue:** ICML 2027 (deadline ~late January 2027; fallback NeurIPS 2027)
**Authors:** Shivam Sharma & Mayank
**Working directory:** `~/CP-SAT model`
**Status as of 2026-07-07:** Phase 0 implemented; one budget-allocation bug found and verified; ceiling experiment needs a re-run before the Phase 0 gate can be judged.

---

## 1. One-paragraph summary

We build a learned outer-loop Large Neighborhood Search (LNS) controller around Google OR-Tools CP-SAT, targeting the setting where an agent emits a **stream of related optimization instances** that drift over time. The learner is a contextual multi-armed bandit whose statistics **persist across the stream** — occupying a quadrant left empty by prior work: BALANS (IJCAI'25) learns online but resets per instance and uses no context; a GNN fix-and-optimize lot-sizing paper (arXiv, May 2026) transfers across instances but is offline-trained, frozen at deployment, and needs ground-truth labels costing 600× the solve budget. Our headline claim: gains over both grow with stream length and degrade gracefully under distribution shift.

---

## 2. Positioning against prior work (must-beat baselines)

Verified directly against the primary sources (arXiv:2412.14382 for BALANS, arXiv:2605.27339 for the lot-sizing paper) — see §7 for how each number was checked.

| | BALANS (IJCAI'25) | Lot-sizing GNN (2026) | Ours |
|---|---|---|---|
| Learns online during solving | Yes | No (frozen GNN) | Yes |
| Transfers across instances | No (resets per instance; doesn't model a sequence of instances at all) | Yes | Yes |
| Uses instance/context features | No (non-contextual MAB) | Yes | Yes |
| Iterative LNS rounds | Yes | No (one-shot fix-and-optimize) | Yes |
| Handles stream / drift | No | No (single episode) | **Yes (the claim)** |
| Needs expensive labels | No | Yes (6000 work-units per label, 600× the 10wu deployment budget) | No |
| Solver | SCIP / Gurobi (MIP) | Gurobi (MIP) | **CP-SAT** — no existing learned-LNS work targets CP-SAT specifically (checked; closest hit, a CPAIOR'26 paper on neural constraint heuristics, uses no classical solver backend, no bandit, no streaming, and names adaptive LNS as its own future work) |

**Adopted from BALANS:** above-solver ALNS layer (their own ablation: above-solver LNS improves 79/94 instances vs. 8/94 for SCIP's in-tree ALNS — verified against the paper); four-outcome reward shaping (best / better / accepted / rejected); simulated-annealing acceptance; destroy-operator menu adapted to CP-SAT; their open-source stack (`pip install balans`) for a MIP-side ablation.

**Adopted from the lot-sizing paper:** buffered selection (unfreeze ~3× the strictly-needed set — verified finding: a "tight" λ=κ selector is *frequently worse than the baseline* because misclassification traps the solver in a bad subspace, while a buffered λ=3κ selector matches or beats a perfect predictor); deterministic-time budgets (work units) instead of raw wall-clock; metric pair gap-to-best-known + improvement-over-repaired; instance-level train/test splits.

---

## 3. Method skeleton (surgical delta over BALANS)

1. **Contextual arms.** Replace the non-contextual MAB with LinUCB / contextual Thompson sampling. Context vector = instance embedding (hand-crafted features v1: sizes, constraint-tightness stats, delta magnitude; GNN over the bipartite variable–constraint graph v1.5) + within-solve dynamics (stall count, incumbent quality, budget remaining) + stream position.
2. **Persistence.** Bandit posterior carried across instances, with discounting / sliding-window updates from the non-stationary-bandit literature to track drift.
3. **Delta-centric destroy operator (novel).** Unfreeze the variables touched by the last delta plus their constraint-graph neighborhood — an operator that only exists in a stream setting; neither prior paper can express it.
4. **Arm menu.** BALANS's operators translated to CP-SAT semantics: random relax, constraint-graph-local, objective-contribution, incumbent-tenure, delta-centric × destroy sizes {5%, 15%, 30%} ≈ 15 arms. (Phase 0's harness currently ships a smaller 4-strategy × 3-size = 12-arm menu — random, machine, critical, delta — as the minimal set needed to run the ceiling experiment; the full 15-arm menu is a Phase 2 item.)
5. **Warm start.** Previous instance's solution passed via `add_hint`; frozen variables pinned via order-preserving chain constraints (not exact-start pinning — see §6); rounds time-sliced with `max_time_in_seconds`. All through the public OR-Tools Python API — no solver fork.

---

## 4. The two do-or-die experiments

1. **Ours vs. BALANS-with-reset** on the same stream — identical arms, identical rewards; only context + persistence differ. The margin must **grow with stream length**. This curve is the learning contribution.
2. **Ours vs. offline-frozen policy** (lot-sizing style: train on first stream segment, freeze) **under distribution shift** — frozen degrades, ours adapts. This is the non-stationarity contribution.

---

## 5. Implementation phases

### Phase 0 — Harness + ceiling experiment (weeks 1–3) — everything depends on this

**Goal:** measure headroom between naive CP-SAT / non-adaptive LNS and a best-arm-in-hindsight oracle. If headroom is small or arm choice is homogeneous, kill the idea cheaply.

**Built (`phase0/`):**
- `streams.py` — seeded generator of dynamic job-shop streams: base instance + deltas (arrival, cancellation, duration jitter, machine outage). Deterministic, tested.
- `model_builder.py` — CP-SAT interval model (precedence, `no_overlap` with outages as fixed intervals, makespan objective) + an independent (non-CP-SAT) `validate_solution` used by tests.
- `harness.py` — outer LNS loop: policy picks an arm (destroy strategy × size, 12 arms), non-destroyed ops keep their incumbent **machine order** (chain constraints; starts float so schedules can left-shift — exact-start pinning was tried first and made repairs nearly impossible), CP-SAT repairs within a time slice, hill-climbing acceptance.
- `policies.py` — uniform-random and epsilon-greedy (reset-per-instance = BALANS-like, or persistent across the stream).
- `metrics.py` — normalized primal integral and final gap.
- `run_phase0.py` — the experiment runner: baselines (a)–(e) plus the oracle.

**Methods compared:** `cpsat_cold`, `cpsat_warm`, `lns_uniform`, `lns_eps_reset` (BALANS-like), `lns_eps_persist`, `oracle` (every round evaluates all 12 arms and keeps the best; only the kept arm's time is charged to a virtual clock).

**Status: 9/9 unit tests pass. Core model logic verified correct** — order-based freezing preserves feasibility and is guaranteed satisfiable from the incumbent (checked algebraically and empirically), stream generation is deterministic and reproducible, outage/no-overlap handling is correct.

**Known bug (verified 2026-07-07, not yet fixed):** `lns_solve` ([harness.py:197](phase0/harness.py#L197)) and `oracle_solve` ([run_phase0.py:73](phase0/run_phase0.py#L73)) both cap the *initial* incumbent solve at `slice_budget` (2s) instead of giving it a fair share of `total_budget` (10s), while `cpsat_cold` gets the full 10s as one continuous solve. Since CP-SAT is anytime, this systematically starts every LNS/oracle method from a worse incumbent than `cpsat_cold` for the same nominal budget. Directly measured on instance 0 of the `--full-shop --machines 15 --initial-jobs 15` stream:

| condition | objective |
|---|---|
| plain CP-SAT, 2s | 729 |
| plain CP-SAT, 10s (= `cpsat_cold` in the existing `phase0_results.csv`) | 701 |
| 8s initial solve + ~43 round-robin repair rounds in the remaining 2s | **699** |

I.e. once the initial-incumbent budget is fixed, even a naive round-robin arm schedule *beats* `cpsat_cold` on this instance. **The existing `phase0_results.csv` (oracle loses to `cpsat_cold` on 7/13 instances) is very likely an artifact of this bug, not a real ceiling.** A separate hypothesis (per-round `build_model()` rebuild overhead) was checked and ruled out — rebuild costs ~3ms out of a ~35–50ms round, not the dominant cost.

**Exit criterion (not yet met — re-run pending the fix):** oracle mean primal integral meaningfully below the best non-oracle baseline, and oracle's improving-arm choices spread across several arms and correlated with context — otherwise a static arm schedule would capture the gain without learning.

### Phase 1 — Stream benchmark + data pipeline (weeks 2–5, overlaps)

- Domain: dynamic job-shop / resource-constrained scheduling (CP-SAT's home turf; interval variables + `no_overlap` give a rich constraint graph; avoids routing, where LKH/HGS comparisons would be demanded).
- Stream = base instance + 50–200 deltas (task arrivals, machine outages, deadline changes). Deltas driven by an actual LLM agent managing a simulated shop, so the stream structure is real, not synthetic noise. Seeded, versioned — released as a benchmark in its own right.
- Feature extractor from `CpModel.Proto()` to bipartite variable–constraint graph; target <100ms for a 5k-variable instance.
- Second domain (nurse rostering or multi-mode assignment) reserved for the generalization section.

### Phase 2 — Contextual bandit v1 (weeks 5–10)

- 15-arm contextual bandit (LinUCB / contextual TS), BALANS four-outcome reward shaping plus improvement-per-second; SA acceptance; posterior persisted across instances with discounting.
- Train offline on Phase-0 logged tuples (off-policy, importance-weighted from the uniform logging policy), then evaluate online with continued adaptation on held-out streams.
- Target: beat baselines (a), (b), (d) on cumulative primal integral with the gap widening over stream position.
- v1.5 upgrade once v1 wins: per-variable GNN scoring with top-k destroy sets, buffered (k ≈ 3× the intended change set).

### Phase 3 — Full evaluation protocol (weeks 10–16)

- All baselines: CP-SAT default (single-thread and 8-worker — the 8-worker run is needed to actually exercise CP-SAT's own built-in adaptive LNS subsolvers, which are inactive at `workers=1`), warm-start-only, random arms, BALANS-with-reset, offline-frozen policy, one learned-CO baseline from the literature (IL-LNS / CL-LNS line adapted).
- Distribution-shift suite: train on one delta distribution, evaluate on shifted arrival/outage rates; report degradation curves (ours vs. frozen).
- Metrics: primal gap + primal integral (BALANS's) and gap-to-best-known + improvement-over-repaired (lot-sizing's), per-instance and stream-cumulative; report rounds-to-target as the Python-overhead-free metric.
- MIP-side ablation on BALANS's own stack to answer "does this only work on CP-SAT?"
- Ablation table: −context, −persistence, −delta-centric operator, −warm-start — every component must earn its place.

### Phase 4 — v2 RL + analysis (weeks 16–22)

- Policy-gradient over the round-sequence MDP *only if* the bandit result stands (stronger second result, not a rescue).
- Interpretability: what did the policy learn? (e.g. delta-centric destroy early in a stream, tenure-based when stalled.) Reviewers reward this.

### Phase 5 — Writing + release (weeks 20–28)

- Paper, benchmark release, code release. Related-work file starts in week 1, not week 20.
- Positioning to write against explicitly: BALANS, lot-sizing GNN, IL-LNS/RL-LNS/CL-LNS, non-stationary bandits, learned warm-starts.

---

## 6. Design notes / methodological findings (accumulated during Phase 0)

- **Default random streams are far too easy** — CP-SAT proves optimality in milliseconds even at ~250 ops. Use `--full-shop` (every job visits every machine, e.g. 15 machines × 15 jobs) for genuinely hard instances (unproven after the full budget).
- **Exact-start freezing kills LNS.** Pinning non-destroyed ops to incumbent *start times* left almost no improving rounds (destroyed ops boxed in by immovable neighbors, makespan locked by frozen job ends). Fixed by **order-based freezing**: preserve incumbent *machine order* via chain constraints between consecutive frozen ops on each machine, letting all starts float so schedules can left-shift. This is the standard JSP LNS neighborhood, and it's proven (algebraically and by test) that the incumbent's own values always satisfy the relaxed chain constraint, so feasibility is never at risk.
- **Oracle wall-clock pathology:** the virtual clock advances by the *chosen* (often cheapest) arm's time while wall-clock time pays for evaluating all 12 arms every round; guarded by `max_rounds` and by exiting early when the initial solve already proves `OPTIMAL`.
- **`cpsat_warm` (hinting with the previous instance's solution) was slightly worse than cold** on the one full run so far — hints can mislead search. Worth re-checking once the initial-incumbent bug is fixed, since that bug affects all methods that call the same `initial_incumbent` path.
- **Initial-incumbent budget asymmetry (see §5, Phase 0):** the highest-priority open bug. Fix before trusting any Phase 0 conclusion.

---

## 7. Citation verification log

Both load-bearing citations in §2 were independently checked against the primary sources (not taken on faith):

- **BALANS** (arXiv:2412.14382, IJCAI'25): confirmed non-contextual (MABWiser e-Greedy/Softmax/Thompson Sampling over historical arm performance only), confirmed resets per instance (no cross-instance concept in the paper's design at all), confirmed the 79/94-vs-8/94 above-solver-vs-in-tree ablation figure.
- **Lot-sizing GNN** (arXiv:2605.27339, May 2026): confirmed short-term budget = 10 work-units vs. long-term ground-truth budget = 6000 work-units (600× — exact figure, from the paper's own footnote on Gurobi work units); confirmed the GNN is frozen supervised single-shot prediction (focal loss, ~1% positive-label imbalance); confirmed the "tight" λ=κ selector is frequently worse than baseline while the buffered λ=3κ selector matches/beats a perfect predictor; confirmed the conclusion explicitly names DRL-based iterative, label-free sequential learning as future work (supports the "closing window" urgency claim).
- **Prior art search for "learned LNS on CP-SAT" specifically:** no existing work found. Closest hit — a CPAIOR'26 paper adapting ConsFormer into an LNS framing — uses no classical CP/MIP solver backend at all (neural-only), is single-instance, doesn't reference BALANS or bandits, and names adaptive LNS as its own future work. Does not compete with this project's angle.

---

## 8. Repository layout

| Directory | Contents |
|---|---|
| `phase0/` | Ceiling-experiment package: `streams.py`, `model_builder.py`, `harness.py`, `policies.py`, `metrics.py`, `run_phase0.py`, `README.md` |
| `tests/` | Unit tests (`test_phase0.py`, 9 tests, all passing) |
| `phase0_results.csv` | Output of the (currently bugged — see §5) ceiling experiment run |
| *(future, per original plan)* `streams/`, `harness/`, `features/`, `policies/`, `baselines/`, `eval/`, `experiments/` | To be split out of `phase0/` as the project grows past Phase 0 |

**Stack:** Python 3.11+, `ortools` ≥ 9.10 (currently 9.15), pytest, pandas, numpy. Planned for later phases: PyTorch + PyTorch Geometric, MABWiser, `balans` (baseline).

---

## 9. Risks and mitigations

- **Warm-starting alone may be too good.** On mild streams, `add_hint` can capture nearly all the gain. Mitigation: `cpsat_warm` baseline present from day one; stream generator supports cranking perturbation size; pivot path defined at the Phase-0 gate.
- **"Incremental over BALANS" review.** Defense: the setting (streams, drift), the benchmark, the growing-margin evidence, and CP-SAT are each new; ablations isolate exactly what context and persistence buy. Experiment 4.1 (§4) is do-or-die.
- **Python outer-loop overhead.** Checked directly (§5) — NOT currently the dominant cost (rebuild ≈ 3ms/round vs. ≈ 35–50ms total). The real Phase 0 risk turned out to be the initial-incumbent budget bug, not rebuild overhead. Still worth watching as instance sizes grow in later phases.
- **Closing window.** The lot-sizing paper (May 2026) names iterative, label-free sequential learning as its own future work. Move fast; Phase 0 is the current bottleneck.
- **Empirical premise unresolved.** The single most important open risk: does real headroom exist above CP-SAT's default once the harness is fixed? Phase 0's own gate exists to answer this before any further investment. Preliminary patched-harness numbers (§5) are promising (699 vs. 701) but come from one instance, one seed, no smart policy — not yet a real ceiling measurement.

---

## 10. Timeline overview

| Weeks | Phase | Exit criterion | Status |
|---|---|---|---|
| 1–3 | 0: Harness + ceiling experiment | Headroom confirmed above defaults + warm-start (GATE) | **In progress** — harness built, bug found, fix + re-run pending |
| 2–5 | 1: Benchmark + pipeline | Frozen, seeded stream generator; <100ms feature extraction | Not started |
| 5–10 | 2: Contextual bandit v1 | Beats CP-SAT default, warm-start-only, BALANS-with-reset | Not started |
| 10–16 | 3: Full evaluation | All baselines + shift curves + ablation table complete | Not started |
| 16–22 | 4: RL v2 + interpretability | Optional stronger result; policy analysis | Not started |
| 20–28 | 5: Writing + release | ICML 2027 submission (~late Jan 2027) | Not started |

## 11. Immediate next action

Fix the initial-incumbent budget allocation in `lns_solve` ([harness.py:197](phase0/harness.py#L197)) and `oracle_solve` ([run_phase0.py:73](phase0/run_phase0.py#L73)) so LNS/oracle methods get a fair share of `total_budget` for their first incumbent, matching what `cpsat_cold` receives. Re-run the ceiling experiment across multiple instances/seeds and judge the Phase 0 gate on corrected numbers before writing any further code.
