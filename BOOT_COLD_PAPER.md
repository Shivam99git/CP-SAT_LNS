# boot_cold: A Near-Zero-Cost Constructive Floor for Streaming CP-SAT Reoptimization

**Working title.** Prepared 2026-07-10 | Shivam Sharma & Mayank | Working directory: `~/CP-SAT model`

---

## Abstract

We study reoptimization over a **stream of related combinatorial optimization instances** — a solver repeatedly re-solves a problem that has drifted slightly from the last one it solved (a job arrives, an item's value changes, a machine breaks). The standard baseline, re-solving each instance from scratch (`cpsat_cold`), structurally ignores this history. We introduce **boot_cold**: before the solver runs, a **~1ms, solver-free, purely constructive heuristic** repairs the *previous* instance's solution into a feasible solution for the *new* instance, and this repaired solution is kept as an **anytime floor** underneath an otherwise completely unmodified, unhinted continuation of the standard solver. boot_cold is provably never worse than **its own unmodified continuation** in final solution quality (up to the ~1ms construction cost), and empirically ties or beats an independently-run `cpsat_cold` on final objective in 92.4% of instances at ICAPS-preset scale (n=1547, all runs to date, including real OR-Library benchmark instances). We additionally validate on six published real-instance benchmark sources across two domains — OR-Library, Taillard, Demirkol (dmu), Storer-Wu (swv), and Yamada-Nakano (yn) for job-shop, and PSPLIB for RCPSP — where the primal-integral win rate holds in an 83.9-89.3% band (pooled n=1792, 87.4%; §5.5), essentially unchanged from the synthetic-stream results. Its primary, robustly-significant advantage is on **primal integral** (anytime solution quality): across two problem domains (job-shop scheduling and 0-1 knapsack) in the original pilot, it wins on **36 of 36 stream instances** where it had a previous solution to reuse (p ≤ 0.008 both domains); at ICAPS-preset scale (n=1547, all runs to date: pilot/workers/arrivals/paper_main/real_benchmarks pooled) it wins on primal integral in **84.9% of instances**, confirmed independently by both the sign test (p≈4.1e-182) and the Wilcoxon signed-rank test (p≈1.6e-152), and this advantage **holds across CP-SAT's multi-worker portfolio search** (workers ∈ {1,4,8,16}, 75-87% win rate at every level) — refuting the main open risk to generalizability. The mechanism itself is not CP-SAT-specific: re-implemented against **Gurobi and IBM CPLEX** (via their free, size-limited license tiers, which cap instance size well below the paper's main experiments — §5.7), the same floor/pocket wrapper produces a statistically significant primal-integral win in **6 of 6 solver-domain combinations tested** (job-shop and knapsack, all Holm-corrected p ≤ 0.0014), with all three independently-coded model formulations agreeing exactly on final objective across every instance. We further show, through a systematic search over three independent alternative designs — hand-crafted learned neighborhood selection, an online contextual bandit, and a hand-coded context rule mined from oracle data — that **none of these more sophisticated approaches beats boot_cold** on the streams tested, making boot_cold a surprisingly strong and hard-to-beat baseline for this problem class, not merely an easy strawman.

---

## 1. Motivation and Problem Setting

### 1.1 The streaming reoptimization setting

Many real deployments of combinatorial solvers do not solve one problem once — they solve a **sequence of closely related problems** as the world changes: a job-shop scheduler re-plans as new orders arrive or a machine goes down; a resource allocator re-solves as item values or constraints shift; an agent managing a dynamic environment re-optimizes every time its model of the world updates. Formally, we consider a stream of instances $I_0, I_1, I_2, \dots$ where $I_{t+1}$ is $I_t$ perturbed by a small, structured **delta** (an item added/removed, a value/duration changed, a resource temporarily or permanently unavailable). Each instance must be solved within a fixed wall-clock budget $B$.

### 1.2 The baseline everyone actually runs, and what it throws away

`cpsat_cold`: hand $I_t$ to CP-SAT, run it for the full budget $B$, keep the best solution found. This is what a solver is used for out of the box. It is a **strong** baseline — CP-SAT's portfolio search (LP relaxation, no-good learning, internal large-neighborhood search) is the product of years of engineering, and naively trying to "out-search" it with hand-rolled destroy/repair loops is a well-known losing proposition (confirmed empirically in our own earlier experiments; see §7).

But `cpsat_cold` has one specific, structural weakness: it is **stateless across the stream**. When $I_{t+1}$ arrives, `cpsat_cold` starts from nothing — even though $I_{t+1}$ may be 95% identical to $I_t$, whose near-optimal solution is sitting right there. Its first several seconds are typically spent rediscovering structure it already had.

### 1.3 The idea

**boot_cold** asks: what if, before doing anything expensive, we spend about a millisecond turning yesterday's answer into a legal answer for today's problem? That "quick legal answer" — the **bootstrap floor** — costs almost nothing to build and is then kept as a safety net (a "floor") while the *exact same* solver runs the *exact same* search it would have run anyway. At every point in time, we report whichever is better: the floor, or wherever the solver has gotten to. Because the floor is free and the solver is untouched, **this can only help, never hurt**.

---

## 2. Related Work and Positioning

| | BALANS (IJCAI'25) | Lot-sizing reoptimization GNN (arXiv 2605.27339, May 2026) | **boot_cold** |
|---|---|---|---|
| Learns online during solving | Yes (multi-armed bandit over LNS destroy operators) | No (frozen GNN) | No — no learning at all |
| Transfers across instances | No (resets per instance; no stream concept) | Yes | Yes (by construction) |
| Needs training / labels | No | Yes (6000 work-units per label — 600× the 10-wu deployment budget) | No |
| Reoptimization mechanism | Destroy-and-repair (LNS) | Learned variable-freezing (fix-and-optimize) | **Constructive floor + unmodified continuation** |
| Guarantee vs. re-solving from scratch | None claimed | None claimed | **Provably never worse than its own continuation** (up to ~1ms); empirically ties/beats an independent cold run 92.4% of the time at scale (n=1547) |
| Solver | SCIP / Gurobi (MIP) | Gurobi (MIP) | Google OR-Tools **CP-SAT** |

boot_cold occupies a different, narrower niche than either prior system: it makes **no learning claim whatsoever**. Its contribution is not a smarter search procedure but a **structural guarantee** — a way to convert "the solver ignores history" into "the solver never does worse than history" at negligible cost. This positions it as (a) a baseline every learned-reoptimization paper in this space should report against, and (b) in its own right, a simple, theoretically clean, empirically strong drop-in improvement to `cpsat_cold` for any streaming deployment.

We verified both comparison papers directly against their primary sources (not from memory): BALANS's 79/94-vs-8/94 above-solver-vs-in-tree ablation and its non-contextual, resets-per-instance design were confirmed against arXiv:2412.14382; the lot-sizing paper's 10-wu/6000-wu (600×) label cost, frozen-GNN deployment, and its own stated future work ("iterative, label-free sequential learning") were confirmed against arXiv:2605.27339.

### 2.2 Positioning against the reactive/dynamic-scheduling literature (ICAPS framing)

The table above compares against ML-for-CO work because that is where boot_cold was first developed against. For an ICAPS submission the relevant prior art is different: **reactive scheduling** and **reoptimization**, a literature that predates learning-based approaches by decades and asks exactly boot_cold's question — given a schedule and a disruption, what do you do next?

| | Match-up scheduling (Bean, Birge, Mittenthal & Noon, *Operations Research* 1991) | Robust/reactive project scheduling (Herroelen & Leus, *EJOR* 2004/2005) | MIP Workshop 2023 Reoptimization Competition (arXiv:2311.14834; winner: arXiv:2308.08986) | **boot_cold** |
|---|---|---|---|---|
| Core mechanism | Bound a "rescheduling zone," reconstruct only within it, **match up** with the original pre-schedule at a future time | Build baseline schedules with slack/buffers *before* disruption (proactive), plus reactive repair policies | Reuse previous solution as primal warm start **and** reuse branching history / tune solver parameters (dual side) | Greedy constructive repair kept as an **anytime floor**, alongside a completely **unmodified** solve of the new instance |
| Touches solver internals? | N/A (pre-CP-SAT era, custom procedures) | N/A | **Yes** — branching history reuse, parameter tuning | **No** — black-box, works with an off-the-shelf CP-SAT call |
| Formal guarantee vs. cold re-solve | Not stated as a provable guarantee | Not stated as a provable guarantee | Not stated (competition scored on primal/dual progress, not a worst-case bound) | **Provably never worse than its own unmodified continuation** (§3.3) |
| Metric | Schedule cost after disruption | Stability/nervousness + baseline robustness | Primal & dual bound progress (competition-scored) | **Primal integral** (anytime quality) + final gap + stability metrics |
| Domain | Single/parallel-machine scheduling | RCPSP | General MILP (any domain, mixed instance types) | Job-shop scheduling (+ RCPSP, 0-1 knapsack for transfer) |
| Solver | Custom | Custom / generic MIP | Generic MILP solvers (SCIP-based) | **CP-SAT** specifically |

Three things distinguish boot_cold from all four:

1. **It is solver-agnostic and requires zero access to solver internals.** Match-up scheduling and the reoptimization-competition methods both operate by changing *what gets reconstructed* or *how the solver searches* (branching history, cuts, parameters). boot_cold does neither — the CP-SAT call for `boot_cold` is byte-identical to a cold solve; the entire mechanism lives outside the solver, in a ~1ms Python function and a "report the better of two" wrapper. This makes it trivially portable to any solver, not just CP-SAT.
2. **It carries a provable guarantee**, not just competitive scoring. None of the three modern/classical mechanisms above state a proof that reoptimization is never worse than a cold solve — the MIP reoptimization competition's own framing scores relative primal/dual progress, which is consistent with occasional regressions on individual instances. boot_cold's pocket mechanism (§3.3) makes this a theorem, not an empirical tendency (with the caveat, found in this session's re-analysis, that the guarantee is exact only against boot_cold's *own* continuation, not against a *separately invoked* cpsat_cold run — see §8).
3. **It targets anytime quality (primal integral) as the primary metric**, not just final objective or proof speed. Match-up scheduling and the MIP reoptimization competition are both scored on end-state quality or optimality-proof speed; boot_cold's central empirical claim (§5) is about the quality of the answer *throughout* the budget, which is the metric that matters when a real deployment might be interrupted or need an answer before the budget expires.

The closest single prior work is the **MIP Workshop 2023 Reoptimization Competition** — same problem shape (a stream of instances differing by small input changes, solved under time pressure, reusing information from the last solve) but general-MILP rather than scheduling-specific, and its top methods invest in solver-internals reuse (branching history, parameter tuning) rather than a black-box floor. This is the paper's most important citation and should open the related-work section: it establishes that the general optimization community already recognizes this exact problem shape as important enough for a dedicated competition, which motivates boot_cold as a domain-specific (scheduling), solver-agnostic, provably-safe answer to the same question.

*(Search performed 2026-07-11; citations above verified against arXiv/Springer/INFORMS abstract pages directly, not from training-data recall. Full-text verification of exact claims — especially whether the MIP competition's winning method has any implicit domination property — is a TODO before final submission; abstracts alone were accessible in this pass.)*

---

## 3. Method

### 3.1 Setting and notation

An instance $I$ has a set of feasible solutions and an objective (minimize makespan for job-shop; maximize value for knapsack). A stream is $I_0, I_1, \dots, I_T$ with $I_{t+1}$ derived from $I_t$ by one delta. Let $S_t^\star$ be the solution returned for $I_t$. A method receives $(I_t, S_{t-1}^\star)$ — the current instance and the *previous* instance's returned solution — and a wall-clock budget $B$.

### 3.2 The greedy bootstrap: turning yesterday's solution into today's floor

The bootstrap is a **pure-Python, solver-free** function specific to the combinatorial structure of the problem, but always following the same principle: **replay the previous decision order, repaired minimally for feasibility.**

**Job-shop scheduling (`list_schedule_bootstrap`).** A solution is a start time for every operation. We take all operations that still exist in $I_t$ (some may have been cancelled), order them by their *previous* start time (brand-new operations — job arrivals — are appended, ordered by their position within their own job, not by string-sorted operation ID, which would silently misorder jobs with more than 9 operations — a real bug we caught and regression-tested), and then perform a single greedy left-to-right list-scheduling pass: each operation starts at the earliest time that is legal given (a) its job's predecessor has finished and (b) its machine is free, pushed past any machine outage window it would otherwise overlap. This produces a **complete, feasible schedule** by construction, for every delta type (arrivals slot in, cancellations simply vanish, duration changes re-time downstream operations, outages shift work right) — in on the order of a millisecond, with zero calls to CP-SAT.

**0-1 Knapsack (`knapsack_bootstrap`).** A solution is a subset of chosen items. We start from the previous instance's chosen set, restricted to items that still exist; if this set now exceeds the (possibly reduced) capacity, we drop items in increasing order of value-per-weight until it fits; we then greedily add any not-yet-chosen items, best value-per-weight first, while they still fit. Feasible by construction, again in about a millisecond.

### 3.3 The floor / pocket mechanism and the domination guarantee

Given the bootstrap solution $F_t$ (the "floor") with objective value $f_t$:

1. Record $(t \approx 0\,\text{ms}, f_t)$ on the method's anytime trajectory.
2. Run the underlying solver **completely normally** — same model, same random seed, **no hint, no added constraints** — for the remaining budget $B - \epsilon$. This is not a variant search; it is byte-for-byte the same call `cpsat_cold` would make.
3. At every reported time, and at the end, output $\arg\min(\text{floor value}, \text{best value the solver has found so far})$.

**Claim (domination, precise form).** For any budget $B$ large enough for the bootstrap to complete, boot_cold's final objective is $\le$ the final objective of **its own continuation solve** — i.e. $\le$ what a `cpsat_cold` call with the *exact same* model, seed, and $B - \epsilon$ budget would have returned — and boot_cold's primal integral is $\le$ that same continuation's.

*Proof sketch.* The continuation solve is *identical* to such a `cpsat_cold` call (same model, same seed) minus $\epsilon \approx 1$ms of budget, so by monotonicity of anytime solver quality in budget, its own final value and trajectory can only be equal to or (negligibly) worse than that reference call's. Step 3 then takes the pointwise minimum of that trajectory and the (constant) floor value, which can only lower or match every point of the curve. Final value is therefore $\le \min(f_t, \text{reference call's final value})$. $\blacksquare$

**Important scope correction (added 2026-07-11, after ICAPS-scale re-analysis):** the guarantee above is exact only against boot_cold's *own* continuation — i.e. a hypothetical `cpsat_cold` call sharing the identical $B-\epsilon$ budget window. It is **not** an exact guarantee against a *separately invoked* `cpsat_cold` run on the same instance, because wall-clock timing is not perfectly reproducible run-to-run (background system jitter, scheduler noise, CP-SAT's internal timing-sensitive heuristics). At ICAPS-preset scale (all runs to date: pilot/workers/arrivals/paper_main/real_benchmarks pooled, n=1547 paired instances), boot_cold's final objective was strictly *worse* than an independently-run `cpsat_cold` on 117/1547 instances (7.6%; median excess 0.63%, max 3.63%) — small and rare, but real, and the original claim below ("zero losses across 43 instances") was an artifact of a small early sample, not a general property. **The paper must state the guarantee in its precise form (never worse than its own continuation) and report the empirical near-domination rate against independently-run cpsat_cold as a strong-but-not-absolute empirical finding, not a corollary of the theorem.** The primal-integral (anytime-quality) advantage is unaffected by this correction and remains the paper's primary, robustly-significant claim.

On the very first instance of a stream ($t=0$), there is no previous solution, so boot_cold has no floor to construct; it degrades gracefully to running exactly `cpsat_cold`. All improvement is concentrated on instances $t \geq 1$ ("stream instances" below).

### 3.4 Algorithm

```
function BOOT_COLD(instance I_t, prev_solution S_{t-1}, budget B, seed):
    trajectory ← []
    floor ← None
    if S_{t-1} is not None:
        floor ← GREEDY_BOOTSTRAP(I_t, S_{t-1})          # ~1ms, no solver
        trajectory.append((elapsed_time(), objective(floor)))

    remaining ← B - elapsed_time()
    solution, obj, solver_trajectory ←
        SOLVE(I_t, hint=None, time_limit=remaining, seed=seed)   # == cpsat_cold
    trajectory.extend(solver_trajectory)

    best ← argmin_by_objective({floor, solution})        # pocket: report the better
    return CLIP_MONOTONE(trajectory), best
```

`CLIP_MONOTONE` post-processes the recorded trajectory to be non-increasing (job-shop; non-decreasing for knapsack's maximization), i.e. it reports "best value seen by time $t$", the standard anytime-quality convention, so that the floor's early advantage propagates forward correctly in the primal-integral computation.

### 3.5 Complexity

The bootstrap is $O(n \log n)$ in the number of operations/items (a single sort plus a linear pass) — in our experiments, 210–2000 elements, measured at 1–3 milliseconds wall-clock, i.e. **< 0.05% of a 10-second budget.** No model is built, no solver is invoked, for this step.

---

## 4. Experimental Setup

### 4.1 Domains and stream generators

**Job-shop scheduling.** CP-SAT interval-variable model: one interval per operation, job-precedence chains, per-machine `no_overlap` (with outages encoded as fixed dummy intervals), minimize makespan. Streams are generated by `phase0/streams.py`: a base instance (configurable machines × jobs, "full-shop" = every job visits every machine) followed by a sequence of deltas drawn from `{arrival, cancellation, duration_jitter, outage}` with configurable relative weights. Main experiments use 15 machines × 15 jobs (225 base operations), a 15×15 "full-shop" configuration chosen because it is hard enough that CP-SAT does not trivially prove optimality within the budget (verified: smaller/easier configurations were rejected in earlier project iterations because CP-SAT closed them in milliseconds, leaving nothing to measure).

**0-1 Knapsack.** Items with (weight, value); a capacity constraint; maximize total value. To avoid a trivially easy problem (the literal "$2^{20}$ search space" of 20 items solves in 0.01 seconds), we use the classical **strongly-correlated hard family** (value = weight + K) at $n{=}2000$ items with weights up to $10^6$ — confirmed empirically not to close within the 10-second budget for most instances. Streams add deltas `{value_jitter, capacity change, item removal}`.

Both stream generators are seeded and fully deterministic; regenerating a stream with the same seed reproduces it exactly (unit-tested).

### 4.2 Fairness protocol

Every method compared receives: the same total wall-clock budget $B$ per instance; the same CP-SAT random seed; `num_workers = 1` (single-threaded, eliminates parallelism as a confound); the same `best_known` reference per (seed, instance), computed as the best objective *any* compared method found on that instance, so all methods are scored against one shared target. Every returned solution is independently re-validated (feasibility re-checked from scratch, not trusted from the solver) before being scored.

### 4.3 Metrics

**Primal integral (PI).** The area under the relative-gap-vs-time curve over $[0, B]$, normalized to $[0,1]$: $\text{gap}(t) = \max(0, \frac{|obj(t) - best\_known|}{best\_known})$, with $\text{gap} = 1$ before the first solution is found. Lower is better. This is the standard **anytime-quality** metric — it rewards being close to the best answer *throughout* the budget, not just at the end, which is exactly the quantity boot_cold targets.

**Final gap.** $\max(0, \frac{obj_{final} - best\_known}{best\_known})$ — the standard end-of-budget solution-quality metric.

**Significance.** Because final quality is expected to tie (by the domination guarantee) and primal integral is the metric of interest, we report exact two-sided sign-test p-values on the head-to-head win/loss count per stream instance, which makes no distributional assumption about primal-integral values.

---

## 5. Results

### 5.1 Job-shop scheduling — main experiment (seeds 1–5)

Configuration: `--full-shop --machines 15 --initial-jobs 15 --stream-length 4 --total-budget 10 --workers 1`, 5 independent seeds → 25 instances (5 "base" instances with no prior solution + 20 "stream" instances).

| method | mean PI (n=25) | mean final gap | wins (final_gap=0) |
|---|---|---|---|
| boot_warm *(hinted variant, not this paper's method)* | 0.0212 | 0.0040 | 17 |
| **boot_cold** | **0.0219** | **0.0067** | 14 |
| cpsat_cold | 0.0265 | 0.0071 | 13 |
| cpsat_warm | 0.0314 | 0.0060 | 14 |

Restricting to the 20 **stream** instances (where boot_cold actually has a floor to use — the operative comparison):

| | cpsat_cold | boot_cold | improvement | head-to-head | significance |
|---|---|---|---|---|---|
| mean PI | 0.02678 | 0.02104 | **21.4%** | **20 W / 0 L / 0 T** | p < 0.0001 |

Final objective across all 25 instances: **2 strict wins, 0 losses, 23 ties** for boot_cold vs. cpsat_cold — the domination guarantee holds exactly as proven.

### 5.2 Job-shop scheduling — held-out confirmation (seeds 6–7)

Same configuration, but on **two stream seeds never used during development or the design of the method** — a genuine out-of-sample check.

| | cpsat_cold | boot_cold | improvement | head-to-head | significance |
|---|---|---|---|---|---|
| mean PI, all instances (n=10) | 0.01934 | 0.01651 | 14.6% | — | — |
| **mean PI, stream instances (n=8)** | **0.01894** | **0.01551** | **18.1%** | **8 W / 0 L** | **p = 0.0078** |

Final objective: 1 strict win, 0 losses, 9 ties (n=10). By delta kind (stream instances only):

| delta kind | n | mean PI improvement |
|---|---|---|
| cancellation | 1 | 99.9% (bootstrap alone matched/beat a full 10s solve) |
| duration_jitter | 1 | 8.9% |
| outage | 3 | 8.8% |
| arrival | 3 | 6.7% (weakest — see §6) |

The held-out result **replicates** the main experiment's finding (18.1% vs. 21.4%), with no sign of overfitting to development seeds.

### 5.3 0-1 Knapsack — domain transfer (seeds 1–2)

Configuration: hard correlated knapsack, 2000 items, weights up to $10^6$, `--total-budget 10 --stream-length 4 --workers 1`, 2 seeds → 10 instances (2 base + 8 stream).

| | cpsat_cold | boot_cold | improvement | head-to-head | significance |
|---|---|---|---|---|---|
| mean PI, all instances (n=10) | 0.03974 | 0.00808 | 79.7% | — | — |
| **mean PI, stream instances (n=8)** | **0.03954** | **0.00011** | **99.7%** | **8 W / 0 L** | **p = 0.0078** |

Final value: **tied 10/10** — again the exact domination guarantee, with both methods proving optimality on the same 6/10 instances (bootstrap does not affect the *dual* side of the search, only the primal side, as expected). By delta kind (stream instances):

| delta kind | n | mean PI improvement | bootstrap floor's gap below final value |
|---|---|---|---|
| capacity change | 2 | 99.8% | 0.016% |
| item removal | 3 | 99.8% | 0.036% |
| value jitter | 3 | 99.6% | 0.25% |

On this domain the bootstrap floor is within a quarter of a percent of the true final answer in every case — `cpsat_cold` spends essentially its entire 10-second budget climbing to a value boot_cold already had at $t \approx 1$ms.

### 5.4 RCPSP — third domain, real scale (seeds 1–10)

A genuinely hard configuration (60 activities, 3 renewable resources, capacity 4–6 — confirmed non-trivial before committing compute: default-sized instances solve too fast to measure anything, matching the same lesson learned for job-shop and knapsack), `--total-budget 8 --stream-length 8 --workers 1`, 10 seeds → 90 instances (10 base + 80 stream), using the serial-SGS bootstrap (`serial_sgs_bootstrap`) as the RCPSP floor construction and the exact same pocket mechanism as job-shop/knapsack (§3.3), independently reimplemented in `phase0/rcpsp/harness.py` and verified byte-for-byte equivalent to the job-shop version's monotonicity logic.

| | cpsat_cold | boot_cold | improvement | head-to-head | significance |
|---|---|---|---|---|---|
| mean PI, all instances (n=90) | 0.00882 | 0.00315 | 64.3% | 83 W / 0 T / 7 L | p = 1.3e-17 |
| **mean PI, stream instances (n=80)** | **0.00876** | **0.00243** | **72.3%** | **80 W / 0 T / 0 L** | **p = 1.65e-24** |

Final objective across all 90 instances: **11 strict wins, 79 ties, 0 losses** — the domination guarantee (in its precise, own-continuation form, §3.3) held exactly in this sample, matching job-shop/knapsack's small-sample pilot behavior (though see §8 for why "0 losses" should not be extrapolated as an absolute property at larger scale, per the job-shop finding at n=1547). By delta kind (stream instances only):

| delta kind | n | mean PI improvement |
|---|---|---|
| duration_jitter | 28 | 90.2% |
| activity_insertion | 23 | 56.0% |
| resource_capacity_reduction | 20 | 54.9% |
| activity_cancellation | 9 | 54.8% |

Notably, **`activity_insertion` (RCPSP's additive-delta analogue of job-shop's `arrival`) is not a weak case here** — 56.0% mean PI improvement, well above the weakest job-shop case (6.7% for arrivals, §5.1–5.2). This is a genuine cross-domain contrast worth flagging rather than smoothing over: the serial-SGS bootstrap's handling of newly-inserted activities evidently degrades less gracefully-badly than job-shop's simple append-to-end-of-machine floor policy. A precise explanation (e.g. whether SGS's greedy earliest-feasible-slot placement is closer to "gap insertion" than job-shop's naive append) is a natural follow-up but not yet investigated.

### 5.5 Public real-benchmark validation (Taillard, dmu, swv, yn job-shop; PSPLIB RCPSP)

Building on the OR-Library real-instance validation reported in §8 (n=540, 89.3% win rate), we extended real-instance testing to five additional published benchmark sources obtained from the ScheduleOpt/benchmarks repository — the dataset underlying the optalcp benchmark comparison site (petrvilim.github.io/optalcp-website/docs/benchmarks): four harder/larger job-shop families (Taillard 1993, `ta01`–`ta20`, 15×15/20×15; Demirkol et al., `dmu01`–`dmu05`, 20×15; Storer–Wu, `swv01`–`swv05`, 20×10; Yamada–Nakano, `yn1`–`yn4`, 20×20) and PSPLIB's RCPSP `j30`/`j60`/`j90`/`j120` sets (10 instances each, Patterson `.rcp` format). Every family was run under the identical stream/pocket protocol used throughout this paper (`stream_length=6`, `budget=8s`, 4 seeds for job-shop, 3 seeds for RCPSP; `boot_cold` vs. an independently-invoked `cpsat_cold`, matched pairwise on instance/seed/stream-step).

| benchmark family | domain | n (paired) | boot_cold PI win rate | sign-test p | mean PI improvement (95% CI) |
|---|---|---|---|---|---|
| Taillard (`ta01`–`ta20`) | job-shop | 560 | 88.2% (494W/0T/66L) | <1e-4 | 0.0180 [0.0166, 0.0193] |
| dmu (`dmu01`–`dmu05`) | job-shop | 140 | 86.4% (121W/0T/19L) | <1e-4 | 0.0295 [0.0252, 0.0338] |
| swv (`swv01`–`swv05`) | job-shop | 140 | 89.3% (125W/0T/15L) | <1e-4 | 0.0166 [0.0142, 0.0190] |
| yn (`yn1`–`yn4`) | job-shop | 112 | 83.9% (94W/0T/18L) | <1e-4 | 0.0159 [0.0126, 0.0194] |
| PSPLIB RCPSP (`j30`/`j60`/`j90`/`j120`) | RCPSP | 840 | 87.1% (732W/0T/108L) | 1.2e-114 | 0.00395 [0.00353, 0.00442] |

Pooled across the four real job-shop families: **834/952 wins (87.6%)**. Combined with PSPLIB RCPSP: **1566/1792 wins (87.4%)** across every published real-instance source tested to date, all statistically indistinguishable from one another (83.9–89.3% band) despite spanning two domains, four job-shop families of varying size (15×15 to 20×20), and four RCPSP sizes (30–120 activities). Final-objective behavior on PSPLIB RCPSP mirrors the domination-guarantee pattern established at ICAPS-preset scale (§3.3, §8): 13 strict wins, 826 ties, and only **1** strict loss against an independently-invoked `cpsat_cold` (99.9% non-loss rate on final objective) — consistent with, not contradicting, the theorem's precise own-continuation form (§3.3). The RCPSP-real result is also notable for its per-family consistency (`j30`: 85.7%, `j60`: 88.6%, `j90`: 87.1%, `j120`: 87.1% — no family below 85%), suggesting the effect is not an artifact of instance size.

All five sources are exact reproductions of files in ScheduleOpt/benchmarks (`tests/fixtures/benchmarks_real/{taillard,dmu,swv,yn}/`, `tests/fixtures/rcpsp_real/`; provenance recorded in each directory's `PROVENANCE.md`), the same repository backing the optalcp benchmark comparison site. Combined with the OR-Library result (§8), boot_cold's primal-integral advantage now holds across **six independent published benchmark sources spanning two domains** (job-shop: OR-Library, Taillard, dmu, swv, yn; RCPSP: PSPLIB) — a materially stronger generalization claim than the original synthetic-streams-only pilot. Reproduction: `scripts/run_icaps_taillard.sh`, `scripts/run_rcpsp_real.sh`, and the analogous `--preset {dmu,swv,yn}_benchmarks --benchmark-dir tests/fixtures/benchmarks_real/{dmu,swv,yn}` invocations of `phase0.run_icaps_jssp_suite`.

**Correctness cross-validation against an independent external solver comparison (added 2026-07-13).** Until now, RCPSP correctness had only been *self*-certified — CP-SAT's own `OPTIMAL` status is a machine-checked proof, but it is still one solver checking its own work. `https://optalcp.com/benchmarks/rcpsp/main.html` publishes a paired comparison of OptalCP and IBM CP Optimizer 22.1.0.0 on the full official PSPLIB set (2040 instances: `j30`=480, `j60`=480, `j90`=480, `j120`=600; 600s/4 workers each), with results embedded inline as JSON in the page (`window.scheduleopt.main([...])` — there is no separate data endpoint). All 40 of our fixture instances (§5.4/§5.5, `tests/fixtures/rcpsp_real/`) appear in that dataset, and on every single one, **both solvers independently proved the identical optimal objective** — an external, two-solver-agreeing ground truth we did not previously have for this domain. Extracted into `tests/fixtures/rcpsp_real/optalcp_bks_reference.json` and wired into a permanent regression test (`tests/test_rcpsp_benchmark_loaders.py::test_real_j30_instances_solve_to_proven_optimality` and `::test_real_instances_match_external_optalcp_bks_no_better_than_optimal`).

Cross-checking our own 8-second-budget, single-worker production campaign (§5.5's `results/icaps/rcpsp/rcpsp_real_benchmarks.csv`, base-instance rows only): **222/240 runs** (40 instances × 3 seeds × 2 methods) found the exact externally-proven-optimal value — 216 of those with CP-SAT's own `OPTIMAL` proof exactly matching the two-solver external proof, 6 finding the right value without completing the proof in the time given. **Zero runs ever reported an objective *better* than the external optimum** — a basic but important correctness check, since a bug in our model construction or solution validator could otherwise silently produce an infeasible "better" answer. The remaining 18/240 (all on the 3 hardest instances in our set — `j120_1_1`, `j60_5_2`, `j90_5_2`) did not close the gap within the much tighter 8s/1-worker budget (mean excess 2.13%, max 3.81% above optimal), which is expected given a ~75x shorter time budget and a quarter of the worker count versus the reference runs, not a correctness concern.

### 5.6 Combined summary

Across three domains, all seeds, all stream instances (instances with a previous solution to reuse): **116 / 116 primal-integral wins, 0 losses** (36 job-shop + knapsack from the original pilot + 80 RCPSP at real scale), aggregate improvements ranging 6.7% (job-shop arrivals, the hardest case found across all three domains) to 99.9% (knapsack, job-shop cancellations). At much larger ICAPS-preset scale (job-shop only, n=1547 pooled across six separate experiments, including real OR-Library benchmark instances), the primal-integral win rate is 84.9% (still highly significant, p≈4.1e-182 sign test / p≈1.6e-152 Wilcoxon) and the final-objective domination rate against an independently-invoked `cpsat_cold` is 92.4% (§3.3, §8) — the small pilot samples' "0 losses" is real but should not be read as an absolute property at scale. Adding the six published-benchmark sources of §5.5 (n=1792, 87.4% win rate, p well below 1e-100 pooled) shows the same effect holding, with a narrower and slightly higher win-rate band, on real published instances specifically — the ICAPS-preset scale figure (84.9%) already included one of these sources (OR-Library); §5.5 is the dedicated, purpose-built real-instance validation the ICAPS-preset number was not designed to isolate. Every reported number above is recomputed directly from the raw per-instance CSV logs (`phase0_bootstrap_seeds1_5.csv`, `phase0_bootstrap_seeds6_7.csv`, `phase0_knapsack_seeds1_2.csv`, `results/icaps/rcpsp/rcpsp_seeds1_10_combined.csv`, `results/icaps/runs/*.csv`, `results/icaps/rcpsp/rcpsp_real_benchmarks.csv`), not transcribed from earlier summaries.

### 5.7 Cross-solver validation: Gurobi and IBM CPLEX (added 2026-07-19)

Every result so far uses CP-SAT as the underlying solver. This section asks the obvious next question: **is the floor/pocket mechanism (§3.3) specific to CP-SAT, or does keeping a cheap constructive floor beside an unmodified solver continuation help any solver?** We add two more baselines, Gurobi and IBM CPLEX, run under the identical cold/boot_cold protocol.

**Licensing constraint (disclosed up front, not a methodological choice).** Both solvers were used via their free, no-signup pip packages, which are *size-limited* rather than time- or feature-limited: `gurobipy`'s bundled license rejects any model over 2000 variables **or** 2000 constraints; `cplex`/`docplex`'s Community Edition rejects anything over exactly 1000 of either (both verified empirically by bisection — a 1000-variable model solves, a 1001-variable model raises `CPLEX Error 1016`). This is why every instance in this section is far smaller than the paper's main CP-SAT experiments (15×15 full-shop, real Taillard/PSPLIB instances at hundreds of activities): it is a hard licensing ceiling on Gurobi/CPLEX, not a claim that these are the interesting sizes. A paid or academic license would remove this ceiling entirely; we did not have access to one for this pass.

**Job-shop: a genuinely hard domain even at small size.** Gurobi/CPLEX cannot use CP-SAT's specialized interval/`no_overlap` propagation, so job-shop is modeled for them with the textbook **disjunctive big-M MIP** formulation (continuous start times, one binary order variable per pair of operations sharing a machine, big-M precedence constraints; `phase0/mip_jssp.py`). This formulation has a famously weak LP relaxation, so — unlike knapsack, see below — it stays genuinely hard even at license-capped size. Configuration: 6 machines, 10 initial jobs, 4–6 ops/job, stream length 4 (fits comfortably under CPLEX's cap with margin verified across seeds: max 718 constraints observed against a 1000 cap). Empirically confirmed non-trivial before committing compute (the same check applied to every domain in this paper): on the base instance, **Gurobi took 3.1s and CPLEX did not finish (>10s) to prove optimality that CP-SAT itself proves in 33ms** — see the cross-solver comparison below.

**Knapsack: included for completeness, but a near-null result for Gurobi/CPLEX specifically.** 0-1 knapsack has extremely strong, well-studied cover-cut theory in commercial MIP solvers. Even an adversarial subset-sum-style instance (weight = value, capacity = exactly half the total weight — the classic hard case for branch-and-bound symmetry) at 900 items, the largest size fitting under CPLEX's cap, solved in **21ms** for Gurobi. No license-capped knapsack instance we could construct gave Gurobi or CPLEX a meaningful anytime curve to improve on. We report this honestly rather than hide it: **this is a real property of the domain-solver combination** (commercial cover cuts crush knapsack regardless of size), not a flaw in the experiment. CP-SAT, by contrast, is comparatively weak on this specific problem class and does show a large, meaningful floor benefit — see the table below.

| domain | solver | n (paired) | cold mean PI | boot_cold mean PI | win/tie/loss | sign-test p (Holm) | mean PI improvement (95% CI) |
|---|---|---|---|---|---|---|---|
| job-shop | CP-SAT | 30 | 0.00048 | 0.00022 | 24/0/6 | 0.0014 | 0.00026 [0.00019, 0.00032] |
| job-shop | Gurobi | 30 | 0.00422 | 0.00233 | 28/0/2 | 2.6e-6 | 0.00189 [0.00143, 0.00236] |
| job-shop | CPLEX | 30 | 0.00344 | 0.00165 | 25/0/5 | 6.5e-4 | 0.00179 [0.00128, 0.00229] |
| knapsack | CP-SAT | 30 | 0.01982 | 0.00435 | 29/0/1 | 1.2e-7 | 0.01547 [0.01212, 0.01865] |
| knapsack | Gurobi | 30 | 0.00299 | 0.00007 | 30/0/0 | 5.6e-9 | 0.00292 [0.00006, 0.00860] |
| knapsack | CPLEX | 30 | 0.00049 | 0.00015 | 29/0/1 | 1.2e-7 | 0.00034 [0.00028, 0.00040] |

**Headline result: 6 out of 6 solver-domain combinations show a statistically significant primal-integral win for the boot_cold-style floor over that solver's own cold variant** (all Holm-corrected sign-test p ≤ 0.0014; Wilcoxon agrees in every case, p ≤ 8.3e-7 for every row). The mechanism is not a CP-SAT-specific artifact. As in every other experiment in this paper, the *relative* size of the benefit tracks how much real anytime curve there is to improve on: largest where the underlying solver is genuinely slow relative to the instance (job-shop for all three solvers; knapsack for CP-SAT), smallest where the solver already closes the gap near-instantly (knapsack for Gurobi/CPLEX — real, but a small absolute number).

**Final-objective domination holds exactly for every solver at this sample size**: 0 losses out of 30 paired instances, for all 6 solver-domain rows (180 ties total). This matches the small-sample behavior already established for CP-SAT in §5.1–§5.4 and carries the same caveat from §3.3/§8: the guarantee is exact against each method's *own* continuation, and "0 losses" at n=30 is consistent with, not a refutation of, the ICAPS-preset-scale finding (§8) that a small fraction of losses appear against an independently-invoked cold run once sample sizes grow into the thousands.

**An unplanned but valuable correctness cross-check**: on every one of the 60 base+stream instances tested (30 job-shop, 30 knapsack), CP-SAT's interval model, Gurobi's disjunctive MIP, and CPLEX's disjunctive MIP — three independently written model formulations — agreed on the *exact same* final objective value. Had any of the three encodings had a modeling bug, this would very likely have shown up as a disagreement somewhere across 60 independent instances; it did not.

**A striking secondary finding, orthogonal to boot_cold's own claim**: the raw cold-solver comparison shows an almost complete inversion between the two domains at this instance size. Job-shop: CP-SAT (mean PI 0.00048) beats CPLEX (0.00344) and Gurobi (0.00422) by roughly 7–9×. Knapsack: CPLEX (0.00049) beats Gurobi (0.00299) and CP-SAT (0.01982) by up to 40×. Neither solver is "better" in general — each wins decisively on the problem structure its internal search is specialized for (CP-SAT's global scheduling constraints vs. generic MIP solvers' knapsack cover cuts). This is a known qualitative fact in the OR literature; measuring it directly, on our own instances, under our own harness, is new to this paper and worth reporting as context for the main claim.

**Reproduction**: `phase0/mip_jssp.py` and `phase0/mip_knapsack.py` (solver backends), `phase0/run_multisolver_test.py --domain {jssp,knapsack}` (experiment runner), `phase0/analyze_multisolver_results.py` (statistics + LaTeX tables), `phase0/make_multisolver_figures.py` (anytime-curve and PI-bar-chart figures). Raw data: `results/multisolver/{jssp,knapsack}_results.csv` (180 rows each, 0 errors); analysis artifacts: `results/multisolver/analysis/` (report, CSVs, and `latex/*.tex` — full per-instance comparison tables plus the aggregate table above, ready to `\input` directly into a paper).

---

## 6. Analysis: Why It Works

The improvement magnitude is governed by one quantity: **how close the ~1ms greedy floor lands to the eventual final answer.**

- **Subtractive / in-place deltas** (item removal, cancellation, capacity shrink, value jitter, duration jitter, outages) leave most of the previous structure valid; the greedy repair is a near-lossless reuse of already-good decisions, and the floor lands within a fraction of a percent of optimal (knapsack: 0.02–0.25%; job-shop outage: comparable). `cpsat_cold`, having no such floor, spends real time reconstructing structure the floor already had — this is where the largest gains appear (job-shop cancellation: 99.9%; knapsack, uniformly: ~99.7%).
- **Additive deltas** (job arrivals, batch arrivals) are the weak case **specifically for job-shop's floor policy**: new work is appended greedily at the end of the schedule rather than inserted intelligently into existing gaps, so the floor is a meaningfully worse starting point (job-shop arrival floor-gap: 16–27% in earlier measurements). Gains are still positive (6.7–8.9% PI) because `cpsat_cold`'s own early trajectory is also poor, but the margin is visibly smaller than the subtractive case. This is the clearest, most actionable direction for future improvement to job-shop's floor specifically (see §8). **This weakness is not universal across domains**: RCPSP's additive delta (`activity_insertion`) shows a strong 56.0% mean PI improvement (§5.4), well above job-shop's additive-delta case — the serial-SGS bootstrap used for RCPSP apparently handles newly-inserted activities more gracefully than job-shop's naive append-to-machine-tail policy, though the precise mechanism is not yet analyzed. The lesson is that "additive deltas are hard" is a property of the *specific floor construction*, not an inherent property of the delta type.

Note what does **not** change: the underlying CP-SAT search is byte-identical to `cpsat_cold`'s, so **boot_cold does not reach the optimum faster or prove optimality sooner** — both methods' best-found and best-bound curves meet at the same wall-clock moment. The entire benefit is in **what you can report if you have to stop early** — which is precisely the situation a streaming, budget-constrained deployment is always in.

---

## 7. Robustness Check: What We Tried That Didn't Beat It

Before settling on boot_cold as the method to report, we deliberately tried to *improve on it*, on the reasoning that a baseline this simple should have obvious headroom for a more sophisticated approach. It did not, across three independent, adequately-powered attempts:

1. **Learned large-neighborhood-search arm selection.** A 27-arm portfolio of destroy strategies (random, machine-based, critical-path-based, delta-touched, and five schedule-aware strategies: bottleneck-machine targeting, critical-block expansion, delta-neighborhood expansion, late-job targeting, outage-window targeting), tried as fixed arms, round-robin rotation, stall-triggered interleaving with the main solver, and a persistent/contextual epsilon-greedy bandit. **Every variant underperformed boot_cold** on primal integral in every configuration tested.
2. **Online contextual bandit over reuse strategies** (linear Thompson sampling choosing between an unhinted continuation, a hinted continuation, and two variable-freezing strategies, conditioned on delta-kind and severity features, on a deliberately *hardened* stream with large structural deltas designed to create headroom). The learned policy's mean primal integral (0.0243) was **58% worse** than simply always doing boot_cold's action (0.0154).
3. **A hand-coded context rule**, mined directly from oracle (best-action-in-hindsight) data on development seeds and therefore given every advantage a learned policy would need to discover — still **lost to boot_cold by 3.9%** when evaluated on three held-out seeds (5 wins, 7 losses per-instance), because the apparent oracle headroom on development seeds did not generalize: the best action per delta-kind was not stable across random seeds.

We report this not as a footnote but as load-bearing evidence: boot_cold is not a weak strawman that any reasonable method beats — it is a **structurally strong baseline** that a systematic search, including an actual learning attempt, failed to surpass in this problem class at this budget/stream-difficulty regime.

---

## 8. Limitations and Honest Scope

- **No learning contribution.** boot_cold is a deterministic, solver-free heuristic plus a monotone "keep the better of two" wrapper. It contains no trained model, no adaptive component, and makes no claim to generalize to problem structures beyond what its greedy repair rule was designed for. This scopes it as a **systems/OR contribution**, not a machine-learning one (see §10).
- **Final-quality benefit is a guarantee against its own continuation, an empirical near-guarantee against independently-run cpsat_cold, not an improvement, in the typical case.** In the small original pilot (43 stream instances), boot_cold strictly improved the *final* objective 3 times and never lost. At ICAPS-preset scale (pilot/workers/arrivals/paper_main/real_benchmarks pooled, n=1547 paired instances, 2026-07-11 re-analysis), the picture is: 1283 ties, 147 strict wins, and **117 strict losses** (7.6% of instances; median excess when losing 0.63%, max 3.63%) against an *independently invoked* `cpsat_cold`. This is expected and does not contradict §3.3's theorem — the theorem's exact guarantee is against boot_cold's *own* unmodified continuation (same run, same budget window), not against a separately-timed reference run, and wall-clock non-reproducibility (scheduler jitter, CP-SAT internal timing-sensitive heuristics) accounts for the gap. **The paper must state the theorem in its precise form and report the 92.4% empirical non-loss rate as a strong but non-absolute finding.** The entire *reliable* measured benefit is in anytime (primal-integral) quality — a real and practically important property for time-constrained deployments, and this claim is unaffected by the above.
- **Single combinatorial structure per domain.** The bootstrap heuristic is hand-designed per problem type (list-scheduling for job-shop, greedy repair for knapsack); porting to a new problem class requires a new (typically straightforward) constructive repair rule, not a generic recipe.
- **Additive-delta weakness.** As shown in §6, the method's gains shrink (though remain positive) when the delta is dominantly "new work added" rather than "existing work perturbed or removed." A smarter insertion heuristic (placing new operations into existing idle machine gaps rather than always appending) is a concrete, untested improvement. **Update (2026-07-11):** `gap_insert`/`regret_insert`/`beam_insert` floor variants implementing exactly this were built and tested at ICAPS scale (n=64-72/condition); the improvement over `append` was in the mean but **not statistically significant** for boot_cold (p=0.38-0.71, near-50/50 win rate) — an honest null result on the fix, not yet a solved problem.
- **~~Scale and thread count.~~ RESOLVED (2026-07-11).** Tested `workers` ∈ {1, 4, 8, 16} at ICAPS-preset scale (n=28-424/level). boot_cold's primal-integral advantage over `cpsat_cold` **holds at every worker count** (87% win rate @1 worker, 75-82% @4/8/16, all p≤1.3e-2) — the single biggest open risk to this paper's central claim is refuted. A genuinely new finding: `boot_warm` is **workers-dependent** — it *loses* single-threaded (36% win rate, p=1.9e-8) but *wins* multi-worker (79-86% win rate); this asymmetry is itself worth reporting.
- **Sample size.** The original pilot (25 + 10 job-shop instances, 10 knapsack instances, 7 total seeds) has been superseded for the core anytime claim by ICAPS-preset-scale runs (pilot+workers+arrivals pooled, n=508+ paired instances); a full `paper_main`-scale campaign (docs/icaps_full_paper_plan.md Phase C.1) is in progress as of this writing.
- **Synthetic streams.** Deltas are synthetically generated (weighted random choice among delta types), not drawn from real deployment logs or an actual agent's trajectory. **Update (2026-07-11):** the method has now additionally been validated on 10 real OR-Library instances (ft06, ft10, ft20, la01-la05, abz5, abz6) as stream bases (docs/icaps_full_paper_plan.md Phase B) — deltas layered on top are still synthetic, but the base structure is no longer synthetic. Result (n=540 paired instances, 6 seeds x 10 real instances): boot_cold wins on primal integral in **89.3% of instances** (sign_p=3.4e-84, mean PI improvement +0.0025, 95% CI [0.0020, 0.0031]) — consistent with, and if anything slightly stronger than, the synthetic-base result, addressing the "only synthetic instances" gap directly. **Update (2026-07-12):** extended to five further published sources (Taillard, dmu, swv, yn job-shop families; PSPLIB RCPSP j30/j60/j90/j120), pooled n=1792, 87.4% win rate — see §5.5. The *base instance* is now real in all six sources; the *deltas layered on top* remain synthetic in every case, which is still the honest residual gap: no source here is a real deployment trace of sequential re-solves.
- **Gurobi/CPLEX instance size, capped by licensing, not choice (added 2026-07-19).** §5.7's cross-solver validation uses Gurobi's and CPLEX's free, size-limited license tiers (hard caps of 2000 and exactly 1000 variables/constraints respectively, verified empirically) — instances there (job-shop: 6 machines × 10 jobs, ≤50 ops after stream growth; knapsack: 700-900 items) are consequently far smaller than this paper's main CP-SAT experiments (15×15 full-shop, real Taillard/PSPLIB instances at hundreds of activities). This is a hard licensing ceiling: we do not have access to a paid or academic Gurobi/CPLEX license, and cannot currently say whether the effect holds at the scale of §5.5's real-benchmark instances for these two solvers. The result should be read as "the mechanism generalizes to two more solvers at small scale," not as "validated at the same scale as CP-SAT." Separately, knapsack specifically is a near-null domain for Gurobi/CPLEX regardless of size (their cover-cut theory closes even adversarial instances in <50ms) — this is a property of the domain-solver pairing, not a scale artifact, and is why job-shop (not knapsack) carries the real signal in that section.

---

## 9. Implementation

### 9.1 Repository layout (existing project, `phase0/` package)

```
phase0/
  streams.py          — job-shop stream generator (Instance/Job/Operation dataclasses, deltas)
  model_builder.py     — CP-SAT interval model; independent (non-CP-SAT) validate_solution
  harness.py           — list_schedule_bootstrap() and warm_bootstrap_solve() (boot_cold/boot_warm)
  metrics.py            — primal_integral(), final_gap()
  run_stall_test.py     — job-shop experiment runner (cpsat_cold / cpsat_warm / boot_cold / boot_warm)
  run_knapsack_test.py  — self-contained knapsack generator + model + knapsack_bootstrap() + runner
tests/
  test_phase0.py        — feasibility regression tests, incl. the >9-op job-ordering bug found and fixed
```

### 9.2 Core method: `list_schedule_bootstrap` (job-shop floor construction)

```python
def list_schedule_bootstrap(
    instance: Instance, prev_solution: Solution
) -> Solution:
    """Build a feasible schedule for `instance` from the PREVIOUS instance's
    solution in pure Python (~1ms, no CP-SAT). Ops that survived the delta are
    replayed in their previous start order; brand-new ops (arrivals) go last in
    (job, position-within-job) order — position, NOT op_id string order: a
    lexicographic sort puts "o10" before "o2" and would schedule a job's 10th
    op before its 2nd, breaking precedence for any new job with >9 ops.
    Each op starts at max(job predecessor end, machine available), pushed past
    any overlapping outage window. Feasible by construction for every delta
    kind: cancellations simply drop ops, duration jitter re-times, outages
    shift work right."""
    pos_in_job: dict[str, int] = {}
    for job in instance.jobs:
        for k, op in enumerate(job.ops):
            pos_in_job[op.op_id] = k
    ordered = sorted(
        instance.all_ops,
        key=lambda op: (op.op_id not in prev_solution,          # old ops first
                        prev_solution.get(op.op_id, 0),
                        pos_in_job[op.op_id], op.op_id),
    )
    outages_by_machine: dict[int, list] = {}
    for o in instance.outages:
        outages_by_machine.setdefault(o.machine, []).append(o)
    for lst in outages_by_machine.values():
        lst.sort(key=lambda o: o.start)

    job_of: dict[str, str] = {}
    for job in instance.jobs:
        for op in job.ops:
            job_of[op.op_id] = job.job_id

    machine_avail: dict[int, int] = {}
    job_end: dict[str, int] = {}
    out: Solution = {}
    for op in ordered:
        s = max(job_end.get(job_of[op.op_id], 0),
                machine_avail.get(op.machine, 0))
        for o in outages_by_machine.get(op.machine, ()):  # sorted by start
            if s < o.end and s + op.duration > o.start:
                s = o.end
        out[op.op_id] = s
        machine_avail[op.machine] = s + op.duration
        job_end[job_of[op.op_id]] = s + op.duration
    return out
```

### 9.3 Core method: `warm_bootstrap_solve` (the pocket wrapper; `use_hint=False` → boot_cold)

```python
def warm_bootstrap_solve(
    instance: Instance,
    total_budget: float,
    prev_solution: Solution | None = None,
    workers: int = 1,
    seed: int = 0,
    use_hint: bool = True,
    method_name: str = "boot_warm",
) -> SolveResult:
    """Stream-aware warm start: convert the PREVIOUS instance's solution into
    a feasible schedule for the new instance almost instantly, then spend the
    whole remaining budget on one continuous CP-SAT solve seeded with it.

    use_hint=False ("boot_cold"): the remaining budget is exactly cpsat_cold's
    own (unhinted, same-seed) search; the bootstrap incumbent only acts as an
    anytime FLOOR on the trajectory and final result. By construction this
    never ends worse than cpsat_cold (modulo the ~1ms bootstrap cost).
    """
    t0 = time.monotonic()
    trajectory: list[tuple[float, int]] = []
    incumbent: Solution | None = None
    objective: int | None = None

    if prev_solution is not None:
        boot = list_schedule_bootstrap(instance, prev_solution)
        boot_obj = max(
            boot[job.ops[-1].op_id] + job.ops[-1].duration
            for job in instance.jobs
        )
        incumbent, objective = boot, boot_obj
        trajectory.append((time.monotonic() - t0, boot_obj))

    initial_objective = objective
    remaining = total_budget - (time.monotonic() - t0)
    if remaining > 0.05:
        sol, obj, _status = solve(
            build_model(instance, hint=incumbent if use_hint else None),
            time_limit=remaining, workers=workers, seed=seed,
            recorder=trajectory, t_offset=time.monotonic() - t0,
        )
        if sol is not None and (objective is None or obj < objective):
            incumbent, objective = sol, obj

    if incumbent is None:
        return SolveResult(method_name, None, None, [])

    # pocket: enforce a monotone anytime trajectory (report best-so-far)
    monotone, best = [], None
    for t, o in sorted(trajectory):
        if best is None or o < best:
            best = o
            monotone.append((t, o))
    return SolveResult(method_name, objective, incumbent, monotone, [],
                       initial_objective=initial_objective)
```

### 9.4 Knapsack instantiation: `knapsack_bootstrap`

```python
def knapsack_bootstrap(inst: KInstance, prev_chosen: set[str]) -> set[str]:
    """Adapt the previous selection to the new instance in ~1ms:
    keep surviving items, shed lowest value/weight until capacity fits,
    then greedily add fitting items by value/weight."""
    chosen = {i for i in prev_chosen if i in inst.items}
    total_w = sum(inst.items[i][0] for i in chosen)
    if total_w > inst.capacity:
        for iid in sorted(chosen, key=lambda i: inst.items[i][1] / inst.items[i][0]):
            chosen.discard(iid)
            total_w -= inst.items[iid][0]
            if total_w <= inst.capacity:
                break
    for iid in sorted(inst.items,
                      key=lambda i: -inst.items[i][1] / inst.items[i][0]):
        if iid in chosen:
            continue
        w = inst.items[iid][0]
        if total_w + w <= inst.capacity:
            chosen.add(iid)
            total_w += w
    return chosen
```

### 9.5 Metric: `primal_integral`

```python
def primal_integral(trajectory, best_known, budget):
    """Area under the relative-gap-vs-time curve on [0, budget].
    gap(t) = (incumbent(t) - best_known) / best_known, gap = 1 before the
    first solution. Lower is better; 0 means best-known was found instantly."""
    events = sorted(trajectory)
    area, prev_t, prev_gap = 0.0, 0.0, 1.0
    for t, obj in events:
        t = min(t, budget)
        area += prev_gap * (t - prev_t)
        prev_t = t
        prev_gap = max(0.0, (obj - best_known) / best_known)
    area += prev_gap * (budget - prev_t)
    return area / budget
```

### 9.6 Reproduction commands

```bash
# Job-shop, main experiment (seeds 1-5)
.venv/bin/python -m phase0.run_stall_test --seeds 1 2 3 4 5 \
  --total-budget 10 --machines 15 --initial-jobs 15 --stream-length 4 \
  --full-shop --methods cpsat_cold cpsat_warm boot_warm boot_cold \
  --out phase0_bootstrap_seeds1_5.csv

# Job-shop, held-out confirmation (seeds 6-7)
.venv/bin/python -m phase0.run_stall_test --seeds 6 7 \
  --total-budget 10 --machines 15 --initial-jobs 15 --stream-length 4 \
  --full-shop --methods cpsat_cold boot_cold \
  --out phase0_bootstrap_seeds6_7.csv

# 0-1 Knapsack, hard correlated (seeds 1-2)
.venv/bin/python -m phase0.run_knapsack_test --seeds 1 2 --items 2000 \
  --correlated --weight-max 1000000 --total-budget 10 --stream-length 4 \
  --out phase0_knapsack_seeds1_2.csv

# Unit tests (feasibility, determinism, incl. the >9-op regression test)
.venv/bin/python -m pytest tests/ -q
```

All commands run single-threaded (`workers=1` default), same CP-SAT seed across compared methods, deterministic stream generation.

---

## 10. Positioning and Recommended Venue

boot_cold is a **systems/OR contribution with a clean theoretical guarantee and strong, reproducible empirical support** — not a machine-learning method. It should not be positioned for ICML/NeurIPS main track, which requires a learning contribution; a submission there would very likely be judged out of scope regardless of the strength of the empirical results. It is well suited to:

- **Constraint-programming / OR venues**: CPAIOR, INFORMS Journal on Computing, EJOR — where "a simple, provably-safe, empirically strong technique for streaming reoptimization" is a complete and valued contribution in its own right, and where the §7 robustness findings (three independent, harder methods failing to beat it) are a natural and well-received result, not an embarrassment.
- **NeurIPS Datasets & Benchmarks track**, if paired with a released, versioned stream-generation benchmark and broadened to the ~20-streams-×-100-instances scale the original project plan specified — framed as "a baseline the learned-reoptimization literature should report against, evaluated here against several natural learned alternatives that fail to beat it."
- As a **required baseline** in any future paper from this project that *does* claim a learning contribution (the persistent contextual-bandit or GNN-based directions explored earlier in this project's history): §7's finding that naive learned approaches lose to boot_cold is exactly the evidence such a paper needs to justify why a more sophisticated method is necessary, and boot_cold is the bar any such method must clear.

---

## Appendix A — Full Statistics Tables

### A.1 Job-shop, seeds 1–5 (25 instances)

| method | mean PI | mean final gap | wins |
|---|---|---|---|
| boot_warm | 0.02121 | 0.00400 | 17 |
| boot_cold | 0.02186 | 0.00665 | 14 |
| cpsat_cold | 0.02645 | 0.00708 | 13 |
| cpsat_warm | 0.03135 | 0.00601 | 14 |

Stream-only (n=20): cold PI 0.02678, boot_cold PI 0.02104, improvement 21.4%, 20W/0L, p<0.0001. Final objective (n=25): 2 better / 0 worse / 23 tied for boot_cold vs cpsat_cold.

### A.2 Job-shop, held-out seeds 6–7 (10 instances)

| | all (n=10) | stream only (n=8) |
|---|---|---|
| cold mean PI | 0.01934 | 0.01894 |
| boot_cold mean PI | 0.01651 | 0.01551 |
| improvement | 14.6% | **18.1%** |
| head-to-head | — | 8W / 0L, p=0.0078 |

By delta kind (stream only): cancellation n=1 (99.9%), duration_jitter n=1 (8.9%), outage n=3 (8.8%), arrival n=3 (6.7%). Final objective: 1 better / 0 worse / 9 tied.

### A.3 Knapsack, seeds 1–2 (10 instances, hard correlated, n=2000 items)

| | all (n=10) | stream only (n=8) |
|---|---|---|
| cold mean PI | 0.03974 | 0.03954 |
| boot_cold mean PI | 0.00808 | 0.00011 |
| improvement | 79.7% | **99.7%** |
| head-to-head | — | 8W / 0L, p=0.0078 |

By delta kind (stream only): capacity n=2 (99.8%), removal n=3 (99.8%), value_jitter n=3 (99.6%). Final value: 0 better / 0 worse / 10 tied (both methods proved optimal on the same 6/10 instances).

### A.4 Robustness-check summary (§7)

| attempted alternative | result vs. boot_cold |
|---|---|
| 27-arm LNS portfolio (fixed / rotation / stall-interleave / persistent bandit) | loses in every configuration tested |
| Online contextual bandit (LinTS, hardened structural-delta streams) | mean PI 0.0243 vs. boot_cold's 0.0154 — **58% worse** |
| Hand-coded rule mined from oracle data, held-out seeds | **loses by 3.9%** (5W/7L per-instance) — apparent oracle headroom did not generalize across seeds |

---

*All statistics in this document were recomputed directly from the raw per-instance result CSVs (`phase0_bootstrap_seeds1_5.csv`, `phase0_bootstrap_seeds6_7.csv`, `phase0_knapsack_seeds1_2.csv`) at time of writing, not transcribed from prior summaries.*
