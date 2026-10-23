# Project Documentation: `boot_cold` — A Near-Zero-Cost Floor for Streaming CP-SAT Reoptimization

This document explains the entire project from first principles — what problem it solves, why it exists, how it evolved, exactly what was built, and what was found. It assumes no prior background in optimization, constraint programming, or the specific jargon this field uses. Where the project uses a term of art, it is defined the first time it appears and again in the glossary (Part X).

This is a **teaching document**, not the paper. The paper (`BOOT_COLD_PAPER.md`) is the precise, citation-ready writeup for a research audience that already knows the field. This document exists so that anyone — including a future version of you, or a collaborator joining cold — can understand the whole project without already knowing what "primal integral" or "CP-SAT" means.

---

## Table of Contents

- **Part I — Background: the concepts, from scratch**
- **Part II — The project's story, start to end**
- **Part III — The method itself, explained in depth**
- **Part IV — The codebase, file by file**
- **Part V — Experimental methodology**
- **Part VI — Results, all of them, organized**
- **Part VII — How to reproduce everything**
- **Part VIII — Honest limitations**
- **Part IX — Where this stands: venue, status, next steps**
- **Part X — Glossary**

---

## Part I — Background: the concepts, from scratch

### I.1 What is a combinatorial optimization problem?

A combinatorial optimization problem asks you to choose the *best* option out of a huge, finite set of possible options, where "best" means minimizing or maximizing some number (a cost, a profit, a completion time), subject to rules ("constraints") the choice must obey.

Concrete example: you have 10 jobs and 3 machines. Every job must run on every machine, in some order, for some duration, and no machine can run two jobs at once. You want the schedule that finishes as early as possible. There are astronomically many valid schedules (the number of ways to order jobs on machines grows combinatorially — hence the name), and you cannot just try them all; a modest-sized instance already has more possible schedules than atoms in the observable universe. This is the **job-shop scheduling problem**, one of the two main problems this project works on (the other being knapsack, below).

These problems are typically **NP-hard**: in the worst case, no known algorithm can guarantee finding the true best answer in a reasonable amount of time as the problem grows. In practice we don't need a guarantee — we need a *good enough* answer *fast enough*, and specialized software called **solvers** are built to search these enormous spaces intelligently rather than exhaustively.

### I.2 What is a solver, and what is CP-SAT?

A **solver** is a piece of software you hand a precise mathematical description of your problem (variables, constraints, an objective), and it searches for the best (or a good) solution. This project is built around three solvers:

- **CP-SAT** — Google's open-source **Constraint Programming** solver, part of the OR-Tools library. "Constraint programming" (CP) models a problem directly in terms of the real-world objects involved (e.g. "this operation's *interval* on the machine timeline") and uses specialized reasoning ("propagation") about those objects — e.g. a built-in `no_overlap` rule that understands "these time intervals on this machine cannot overlap" natively, without you having to hand-encode that idea as raw algebra. CP-SAT actually blends CP with SAT (Boolean satisfiability) and MIP-style techniques internally, but the modeling interface is CP-flavored. **This project's whole method is built and validated primarily on CP-SAT.**
- **Gurobi** and **IBM CPLEX** — the two dominant commercial **Mixed-Integer Programming (MIP)** solvers. MIP models a problem as linear algebra: variables (some restricted to integers, often 0/1), linear constraints (`a·x ≤ b` style inequalities), and a linear objective. MIP solvers use **branch-and-bound** (systematically split the problem into smaller sub-problems and prune ones that provably can't beat the best answer found so far) combined with decades of engineering on "cutting planes" (extra inequalities that tighten the search without excluding any real solution). Gurobi and CPLEX are industry-standard, extremely well-engineered, and normally require paid licenses; this project used their **free, size-limited** tiers (explained in Part I.6).

A crucial shared property: **all three of these solvers are *anytime* algorithms** (see I.7) — if you stop them early, they can still hand you the best feasible answer found *so far*, even if they haven't proven it's optimal.

### I.3 Job-shop scheduling, precisely

- You have a set of **jobs**. Each job is a sequence of **operations** that must run in order (operation 2 can't start before operation 1 finishes).
- Each operation must run on a specific **machine**, for a specific **duration**.
- Each machine can run only one operation at a time (**no overlap**).
- **Objective**: minimize the **makespan** — the time the last operation of the last job finishes.

This project's CP-SAT model (`phase0/model_builder.py`) encodes this almost literally: one time-interval variable per operation, a precedence constraint chaining each job's operations, and a `no_overlap` constraint per machine. This is the natural, idiomatic CP-SAT encoding, and it is very good at this specific structure (see Part II.8 for just how good, relative to MIP).

### I.4 0-1 Knapsack, precisely

You have a set of **items**, each with a **weight** and a **value**, and a **capacity**. You must choose a subset of items whose total weight does not exceed the capacity, maximizing total value. ("0-1" means each item is either fully taken or not — no fractional items, no duplicates.) This is one of the most-studied combinatorial problems in existence, and — importantly for this project — **it behaves very differently depending on which solver you throw at it** (see Part II.8).

### I.5 RCPSP, precisely

**Resource-Constrained Project Scheduling Problem.** Like job-shop, but instead of one machine per operation, each **activity** consumes some amount of one or more shared, capacity-limited **resources** (e.g. "activity 7 needs 3 units of resource A and 2 units of resource B for its whole duration"), and activities have arbitrary **precedence** relationships (not just "chain within a job" — any activity can depend on any other). This is the standard formalism for project scheduling (construction projects, R&D pipelines) and is the project's third domain, added to test whether the method generalizes beyond scheduling-on-machines.

### I.6 Why licensing matters for Gurobi/CPLEX (a real, hard constraint this project ran into)

Gurobi and CPLEX are commercial products. Without a paid or academic license, you can still `pip install` them for free — but the bundled license is not a time-limited trial, it is a **problem-size-limited** license:

- `gurobipy`'s free "size-limited" license **rejects any model with more than 2000 variables or more than 2000 constraints** — verified in this project by binary search: a 2000-variable model solves, a 2001-variable model raises `GurobiError`.
- `cplex`/`docplex`'s free "Community Edition" **rejects anything over exactly 1000 variables or 1000 constraints** — same verification method, same result.

This is a hard, external constraint that shaped a real chunk of this project's engineering (Part II.9): every experiment using Gurobi or CPLEX had to use instances small enough to survive both caps, chosen and *verified* (not assumed) to still be computationally non-trivial.

### I.7 Anytime algorithms and the primal integral

An **anytime algorithm** can be interrupted at any point in time and still hand you its best answer *so far* — the answer typically gets better and better the longer you let it run, but you're never left with nothing. CP-SAT, Gurobi, and CPLEX are all anytime solvers when run with a time budget: they report a sequence of improving solutions ("incumbents") as the search progresses.

This matters because in most real deployments, you have a **fixed time budget** (e.g. "re-plan the factory schedule in 10 seconds"), and you care about the quality of the answer *at the moment the budget runs out* — and, if you can be interrupted early, the quality of the answer at *every* moment along the way, not just the final one.

The project's primary metric, the **primal integral (PI)**, captures exactly this "quality over time" idea:

1. At every moment `t` during the solve, compute the **relative gap**: `(current_best - true_best) / true_best` (0 = you have the best possible answer; larger = worse). Before any solution is found, the gap is defined to be 1 (maximally bad).
2. Plot gap vs. time. This traces a step-function curve that starts at 1 and (ideally) drops toward 0.
3. The primal integral is the **area under that curve**, normalized by the total budget so it's a number between 0 and 1.

**Lower PI is better.** A method that finds a near-optimal answer almost instantly and holds it has a tiny PI. A method that starts at gap=1 and only reaches a good answer at the very last second has a PI close to 1 for most of that time and a poor overall score, *even if its final answer at the deadline is identical* to the fast method's. **This is the whole point of `boot_cold`**: two methods can tie on the final answer and still differ enormously in primal integral, because PI rewards being good *throughout*, not just at the end.

### I.8 The statistical tools used to check "is this real, or noise?"

Every claim in this project ("method X beats method Y") is backed by a specific statistical test, not just "the average looks better." Four tools recur throughout:

- **Sign test**: the simplest possible test. Given `n` paired comparisons (same instance, two methods), count how many times method A won vs. lost (ties are dropped). Under the null hypothesis "no real difference," wins/losses should be roughly a 50/50 coin flip; the sign test computes the exact probability (`p`-value) of seeing a split at least as lopsided as the one observed, by chance, from a fair coin. A tiny `p`-value (e.g. `p < 0.0001`) means the observed lopsidedness is extremely unlikely to be a fluke.
- **Wilcoxon signed-rank test**: like the sign test, but also uses *how big* each win/loss margin was, not just whether it was a win or loss — a more statistically powerful test when the magnitudes carry information. Used throughout as a cross-check against the sign test; the project treats an effect as solid when both agree.
- **Bootstrap confidence interval (CI)**: to report a range of plausible values for "the true average improvement," this project resamples the observed paired differences (with replacement) thousands of times, recomputes the mean improvement each time, and reports the 2.5th–97.5th percentile of that distribution as a 95% CI. If the interval excludes 0, the improvement is unlikely to be pure noise.
- **Holm-Bonferroni correction**: whenever multiple comparisons are made at once (e.g. testing 3 solvers × 2 domains = 6 comparisons simultaneously), the chance that *at least one* looks significant purely by luck goes up. Holm correction adjusts the `p`-value threshold to control for this, so that a result reported as "significant after Holm correction" is not an artifact of testing many things at once.

All four are implemented once, centrally, in `phase0/analyze_icaps_results.py` and reused by every later analysis script in the project (never re-implemented ad hoc), specifically to avoid a class of bug this project actually hit once (see Part II.10).

---

## Part II — The project's story, start to end

This section tells the project chronologically. Understanding the story matters because the project's final shape (a systems/OR paper about a simple mechanism) is the *result* of an earlier, more ambitious idea not panning out — and that negative result is itself load-bearing evidence in the final paper, not a discarded false start.

### II.1 The original idea (where this started)

The project began as `IMPLEMENTATION_PLAN.md` describes it: **"Persistent Contextual-Bandit LNS for CP-SAT over Agent-Generated Problem Streams,"** targeted at a machine-learning venue (ICML/NeurIPS). The idea:

- Real deployments don't solve one scheduling problem once — they solve a **stream** of related problems as the world changes (a job arrives, a machine breaks).
- Instead of re-solving each one from scratch, use **Large Neighborhood Search (LNS)**: keep most of the previous solution fixed ("frozen"), unfreeze ("destroy") a small chosen subset of decisions, and ask CP-SAT to repair/improve just that subset. Repeat.
- The novel idea: use a **contextual multi-armed bandit** (a lightweight reinforcement-learning technique) to *learn*, online, which part of the solution to unfreeze at each step, with the bandit's knowledge **persisting across the whole stream** — a gap the project identified in two closest prior works, BALANS (IJCAI'25, learns online but resets per instance) and a lot-sizing GNN paper (transfers across instances but is frozen after offline training, needing labels 600× more expensive than the deployment budget).

### II.2 Phase 0: the ceiling experiment (the honest gate before building the hard part)

Before building the full learned bandit, the plan called for a cheap sanity check first, called **Phase 0**: *is there even headroom for a learned policy to exploit?* Concretely — build a stream generator, a CP-SAT model, an LNS harness with a fixed menu of "destroy strategies" (arms: random, machine-based, critical-path-based, delta-touched, at several sizes), and simple baseline policies (uniform-random arm choice, epsilon-greedy). Then compute an **oracle**: at every LNS round, actually try *every* arm and keep whichever one helped most, in hindsight. If the oracle only modestly beats naive CP-SAT, or if the oracle's best-arm choice doesn't depend on context, there is nothing for a learned policy to learn, and the whole plan should be killed cheaply — *before* investing in the expensive bandit machinery.

This is documented in `phase0/README.md` and `IMPLEMENTATION_PLAN.md` §5–6. Along the way, a real bug was found and fixed: `lns_solve` and `oracle_solve` were capping the *first* incumbent solve's time budget too tightly compared to the `cpsat_cold` baseline's full budget, unfairly starting LNS-based methods from a worse position — fixed by giving the initial solve `total_budget - slice_budget` instead.

### II.3 The pivot: `reopt/` and the discovery that a learned policy loses

The Phase 0 ceiling experiment (and the deeper follow-up work in the separate `reopt/` module, `reopt/README.md`) tried, systematically and fairly, to build something smarter than the simplest possible idea — and **could not beat it**. Three separate, well-powered attempts:

1. **A 27-arm learned LNS bandit** (random, machine, critical-path, delta-touched, plus five "schedule-aware" strategies — bottleneck-machine targeting, critical-block expansion, etc.), tried as fixed arms, round-robin rotation, stall-triggered interleaving, and a persistent contextual epsilon-greedy bandit. Every variant underperformed the simple baseline.
2. **An online contextual bandit** (linear Thompson sampling over 4 reuse strategies — unhinted continuation, hinted continuation, two variable-freezing strategies — conditioned on delta features) on a deliberately *hardened* stream designed to create maximal headroom for learning. The learned policy's mean primal integral was **58% worse** than simply always doing the simple thing.
3. **A hand-coded rule mined directly from oracle (best-action-in-hindsight) data** — given every advantage a learned policy would need to discover — still **lost by 3.9%** on held-out seeds, because the apparent oracle headroom on development seeds did not generalize: the best action per delta-kind was not stable across random seeds.

The "simple thing" that kept winning against all this engineering effort is exactly `boot_cold` (next section) — at the time, this was almost dismissed as a trivial placeholder baseline. It turned out to be the actual finding.

### II.4 The discovery: `boot_cold`

Buried inside the Phase 0/`reopt` baseline menu was the simplest possible idea for reusing the previous solution: spend about **one millisecond** turning yesterday's solution into a legal (feasible) solution for today's slightly-changed problem, using pure Python, no solver call at all — then keep that as a safety-net floor while running the exact same, completely unmodified CP-SAT search you would have run anyway, and at the end report whichever is better. This idea (formalized in Part III) turned out to be a **structurally strong, hard-to-beat baseline** — not a strawman. Recognizing that this "throwaway baseline" was actually the paper is the pivot point of the whole project: it converts a failed ML idea (no learned policy could beat this) into a positive result (this simple, provably-safe mechanism is itself worth reporting).

### II.5 Turning `boot_cold` into a full technical paper (6 phases, A–F)

Once `boot_cold` was identified as the actual contribution, the project re-scoped from an ML paper to a **systems/OR paper**, and a 6-phase plan (`docs/icaps_full_paper_plan.md`) was executed to bring the pilot-scale finding up to full-paper rigor:

- **Phase A — Related work.** Positioned against both the ML-for-CO literature (BALANS, the lot-sizing GNN paper) *and*, once an ICAPS submission was decided on, the decades-older **reactive/dynamic scheduling** literature (match-up scheduling, Herroelen & Leus's robust project scheduling, the MIP Workshop 2023 Reoptimization Competition).
- **Phase B — Real benchmark instances.** The original pilot used only synthetically generated instances. Phase B validated on 10 real OR-Library job-shop instances (`ft06`, `ft10`, `ft20`, `la01`–`la05`, `abz5`, `abz6`) as stream *bases* (deltas layered on top were still synthetic).
- **Phase C — Scaled campaign.** Moved from a handful of pilot seeds to an "ICAPS-preset" scale (multiple seeds × sizes × budgets × worker counts), including a **C.0 sub-phase**: parallelizing the experiment runner (`--parallel N`, multiprocessing at stream-config granularity) plus crash-safe incremental checkpointing, since campaigns now took long enough that a crash partway through needed to not lose all completed work.
- **Phase D — RCPSP at scale.** Added the RCPSP domain (Part II.7) as a second scheduling domain, at real scale, to test cross-domain generalization.
- **Phase E — Figures.** Built a two-step trajectory-capture-then-plot pipeline (`phase0/make_paper_figures.py`) producing the anytime-quality curves, worker-scaling plots, and other figures.
- **Phase F — Paper draft.** Wrote the full technical writeup, both as a living Markdown document (`BOOT_COLD_PAPER.md`, the source of truth) and a submission-ready LaTeX draft (`paper/boot_cold_icaps.tex`).

Along the way, a genuine overclaim was caught and fixed: an earlier draft stated the method was "provably never worse than cold-solving," which is too strong. The precise theorem (Part III.4) only guarantees non-domination against the method's *own* unmodified continuation, not against a *separately invoked* cold run — because wall-clock timing isn't perfectly reproducible run-to-run. At scale, a small but real fraction of instances (7.6% at n=1547) *do* show boot_cold's final answer being slightly worse than an independent cold run. The paper was corrected everywhere this was stated (abstract, theorem, limitations, README) to say this precisely, and the correction is treated as important enough to be documented as its own finding.

Also found and fixed during this phase, as a real software bug (not a documentation issue): `sign_test()`'s p-value computation used `2 ** n` where `n` could be a NumPy `int64`, which silently overflows (wraps around) instead of raising an error, corrupting p-values for large sample counts. Fixed with an explicit `int()` cast, and 20 new tests added — the module computing every p-value in the project previously had zero test coverage.

### II.6 Real-benchmark validation, extended to six independent published sources

After a user question ("have we validated on real benchmarks beyond OR-Library?"), and being pointed at `optalcp.com`'s benchmark comparison site (backed by the `ScheduleOpt/benchmarks` GitHub repository), the real-instance validation was extended from one source (OR-Library) to **six**:

- **Job-shop**: OR-Library (10 instances), **Taillard** 1993 (`ta01`–`ta20`, 15×15/20×15), **Demirkol** (`dmu01`–`dmu05`, 20×15), **Storer-Wu** (`swv01`–`swv05`, 20×10), **Yamada-Nakano** (`yn1`–`yn4`, 20×20).
- **RCPSP**: **PSPLIB**, the standard project-scheduling benchmark library (`j30`/`j60`/`j90`/`j120` sets, 10 instances each), obtained in the compact "Patterson" `.rcp` text format.

Every family showed the same effect, in a tight 83.9–89.3% primal-integral win-rate band, regardless of domain, family, or instance size — pooled across all six sources: **1566/1792 wins (87.4%)**, all statistically significant.

**A real bug was found and fixed during this phase**, illustrating a recurring lesson in this project (fix at the function boundary, not just the call site): the RCPSP `.rcp` file loader originally assigned activity IDs starting from 1 (`a1`..`a{n}`), while the stream generator's "insert a new activity" logic computed the next free ID as `len(existing activities)` and named it `f"a{next_num}"`. On a real 122-activity instance, this silently produced **two different activities both named `"a122"`** — a duplicate ID that corrupted the precedence graph and crashed a production run with an assertion failure deep inside the solver harness. Fixed at both ends: the loader now uses 0-indexed IDs matching the synthetic generator's own convention exactly, *and* the stream generator was hardened to compute the next free ID by scanning for the actual maximum existing numeric suffix (rather than trusting a length-based shortcut that silently assumes a dense, gap-free ID range) — plus a fail-fast assertion added right after every stream step, so any future collision of this kind crashes loudly and immediately instead of corrupting data silently.

### II.7 RCPSP: cross-validated against an independent, external solver comparison

Beyond self-certifying correctness (checking that CP-SAT's own `OPTIMAL` status is a valid branch-and-bound proof), the RCPSP results were cross-checked against **`optalcp.com/benchmarks/rcpsp/main.html`**, a public leaderboard comparing OptalCP against IBM CP Optimizer (a different member of the CPLEX family) on the full official PSPLIB set (2040 instances). The page's data isn't exposed through an API — it's embedded directly as inline JSON in the page's HTML, extracted by fetching the raw HTML and bracket-matching the JSON array manually. All 40 of this project's RCPSP fixture instances appear in that dataset, and on every one, **both external solvers independently proved the identical optimal value** — a genuine external ground truth the project didn't previously have.

Cross-checking against this project's own 8-second-budget production runs: **222 of 240 base-instance runs matched the external optimum exactly**, and **zero ever reported a value better than the external optimum** (an important sanity check — finding a "better than truly optimal" answer would indicate a bug). The 18 shortfalls were confined to the 3 hardest instances in the set, under a time budget ~75× shorter than the reference runs' — expected, not a correctness concern.

### II.8 Cross-solver validation: does the mechanism generalize beyond CP-SAT?

The most recent major addition asked a different kind of question from "does it work on more instances" — **does the mechanism work with a completely different solver family, not just CP-SAT?** Gurobi and IBM CPLEX were added as two more backends.

This immediately ran into the licensing constraint from Part I.6, which shaped the entire sub-project:

- **Job-shop had to be re-modeled from scratch** for Gurobi/CPLEX, since they can't use CP-SAT's specialized `no_overlap` constraint. The standard textbook encoding — the **disjunctive big-M MIP formulation** — was built: continuous start-time variables, one binary "which order" variable per pair of operations sharing a machine, and "big-M" inequalities (a large constant M used to switch a constraint on/off depending on a binary variable) enforcing that exactly one ordering holds. This formulation has a famously weak LP relaxation (the continuous "loosened" version of the problem that branch-and-bound uses for bounding), so it stays genuinely hard for a generic MIP solver even at tiny sizes — confirmed directly: on one small instance, **Gurobi took 3.1 seconds and CPLEX did not finish in 10 seconds** to prove optimal what **CP-SAT proved in 33 milliseconds**.
- **Knapsack was tried and found to be a near-null domain for Gurobi/CPLEX specifically.** Both solvers have extremely strong, decades-refined "cover cut" theory purpose-built for 0-1 knapsack; even an adversarially hard instance (900 items, weight = value, capacity exactly half the total — the classic hard case for generic branch-and-bound symmetry) solved in ~20 milliseconds. This was verified empirically (not assumed) before committing further compute to it, and is reported honestly as a real property of the domain-solver pairing, not hidden or worked around.
- **Instance sizes were chosen and validated, not guessed**: a small job-shop configuration (6 machines, 10 initial jobs, 4–6 operations per job) was checked across many random seeds to confirm it always stays safely under CPLEX's 1000-variable/constraint cap even after stream deltas (job arrivals) grow it, while still being large enough to take real, non-trivial solve time.
- **Result: 6 out of 6 solver-domain combinations** (CP-SAT / Gurobi / CPLEX, each on job-shop and knapsack) showed a **statistically significant** primal-integral improvement from the floor/pocket mechanism over that solver's own unmodified cold run (every comparison significant after Holm correction, `p ≤ 0.0014`). The mechanism is not a CP-SAT-specific artifact.
- **A correctness check**: on all 30 job-shop instances, three *independently written* model formulations (CP-SAT's interval model, and two separately hand-derived big-M MIP encodings for Gurobi and CPLEX) returned the exact same final makespan. On knapsack they agree only to within 1e-4 (relative), because Gurobi and CPLEX stop at their default MIP gap tolerance. (Corrected 2026-10-06 after re-deriving every number from the raw CSVs; see `paper/icaps27/README.md`, section "Errors found in earlier drafts".)
- **A striking secondary finding, orthogonal to the paper's main claim**: the raw comparison of "cold" solves (no floor at all) revealed an almost complete inversion between domains — CP-SAT beats Gurobi/CPLEX by roughly 7–9× on job-shop, while Gurobi/CPLEX beat CP-SAT by up to 40× on knapsack. Neither solver is "better" in general; each dominates the problem structure its internal search machinery specializes for. This is a known qualitative fact in the field, but measuring it directly, under one consistent harness, on the project's own instances, is new to this work.

### II.9 Where the project stands now

As of this writing, the project has:

- A precise theorem (Part III.4) with an honestly-scoped proof and an explicit correction of an earlier overclaim.
- Validation across **three problem domains** (job-shop, knapsack, RCPSP).
- Validation across **six independent published real-benchmark sources**.
- Validation across **three independent solver backends** (CP-SAT, Gurobi, CPLEX).
- A documented, reproducible negative result (Part II.3) showing three different attempts at a *smarter* method all failed to beat the simple one — used as load-bearing evidence, not hidden.
- A complete statistical apparatus (sign test, Wilcoxon, bootstrap CI, Holm correction) applied uniformly to every claim.
- A living technical writeup (`BOOT_COLD_PAPER.md`) and a submission-ready LaTeX draft (`paper/boot_cold_icaps.tex`), both current as of the cross-solver validation.
- An explicit, discussed decision to target **ICAPS** (the flagship AI-planning-and-scheduling conference) specifically, along with an honest risk assessment of that target and a concrete plan to strengthen the submission (reframing around plan-repair literature and the floor-vs-hint robustness finding, adding an established reoptimization baseline, adding schedule-stability metrics, adding at least one non-synthetic delta stream) — see Part IX.

### II.10 Two recurring engineering lessons worth naming explicitly

Two bugs surfaced independently in this project, months apart, in unrelated code — and both taught the same lesson, which is worth stating once, generally:

**Fix defensively at the function/module boundary, not just at the one call site that happened to break.** The `sign_test` overflow bug (II.5) was fixed with an `int()` cast *inside the function itself*, even though the one production call site at the time already happened to cast explicitly — because a future caller might not. The RCPSP activity-ID collision (II.6) was fixed both in the specific loader that caused it *and* by hardening the general stream-generation logic to never trust a fragile assumption (dense, gap-free IDs) again, plus adding a fail-fast assertion that would catch any *future* variant of the same mistake immediately rather than after silent corruption. In both cases, patching only the one broken call site would have "fixed" the reported symptom while leaving the same landmine for the next caller.

---

## Part III — The method itself, explained in depth

### III.1 The setting, restated formally but simply

You face a **sequence** of related problem instances `I₀, I₁, I₂, …` — a "stream." Each `I_{t+1}` is `I_t` with one small, structured change applied (a "delta"): a job arrives, an item's value changes, a machine breaks, an activity is inserted or removed. You must produce a solution to each `I_t` within a fixed wall-clock time budget `B` (e.g. 8 or 10 seconds), and you're allowed to use the solution you produced for `I_{t-1}` when solving `I_t`.

### III.2 The baseline everyone actually runs, and exactly what it wastes

Call `cpsat_cold` the obvious thing to do: hand `I_t` to CP-SAT, let it run for the full budget `B`, keep the best answer found. This is a **strong** baseline — CP-SAT's internal search (LP relaxation reasoning, learned "no-good" clauses, its own internal large-neighborhood search) is the product of years of engineering, and this project's own history (Part II.3) is direct evidence that trying to out-search it with a hand-built destroy/repair loop is a losing proposition.

But `cpsat_cold` has one specific, structural blind spot: it is **stateless across the stream**. Every time `I_{t+1}` arrives, it starts from *nothing*, even though `I_{t+1}` might be 95% identical to `I_t`, whose near-optimal solution is sitting right there, unused. Its first several seconds are typically spent re-discovering structure it already had a moment ago.

### III.3 The idea, in one sentence

**Before doing anything expensive, spend about one millisecond turning yesterday's answer into a legal answer for today's problem, and keep that answer as a safety net underneath an otherwise completely unmodified continuation of the normal solve.**

Broken into two separate pieces:

**Piece 1 — the bootstrap ("the floor").** A **pure-Python, solver-free** function, specific to each problem domain but following the same principle: *replay the previous decision order, repaired minimally for feasibility.*

- **Job-shop** (`list_schedule_bootstrap`): take every operation that still exists in the new instance, order them by their *previous* start time (brand-new operations from a job arrival are appended, ordered by position within their own job — not by sorting the text of their ID, a real bug this project caught: string-sorting puts `"o10"` before `"o2"`, silently misordering any job with more than 9 operations), then do a single greedy left-to-right pass: each operation starts at the earliest time consistent with (a) its job's predecessor having finished and (b) its machine being free, pushed past any machine outage it would otherwise collide with. This produces a complete, feasible schedule by construction, for every kind of delta, in about a millisecond, with **zero** calls to any solver.
- **Knapsack** (`knapsack_bootstrap`): start from the previous chosen set, restricted to items that still exist; if it's now over capacity, drop the worst value-per-weight items until it fits; then greedily add any not-yet-chosen items, best value-per-weight first, while they still fit.
- **RCPSP** (`serial_sgs_bootstrap`): the standard "serial schedule generation scheme" from the project-scheduling literature, replaying the previous activity order.

**Piece 2 — the pocket (the "keep the better of two" wrapper).**

1. Build the floor (≈1ms). Record its objective value at time ≈0.
2. Run the underlying solver **completely normally** on the new instance — same model, same random seed, **no hint, no extra constraints** — for the rest of the time budget. This step is, byte-for-byte, exactly the same call `cpsat_cold` would make; nothing about the solver's own search is touched or biased in any way.
3. At every reported moment, and at the very end, report **whichever is better: the floor, or wherever the solver's own search has gotten to.**

The name `boot_cold` refers to this combination: a **boot**strap floor, kept beside a **cold** (unhinted, unbiased) continuation of the normal solve.

(A close variant, `boot_warm`, feeds the floor *into* the solver as a hint instead of keeping it beside the solver as a separate floor. This project measured this too and found it is **less robust**: hinting can help but can also actively mislead the solver's own search away from where it would otherwise have gone, and across campaigns the effect of hinting changes sign — e.g. `boot_warm` loses badly after job arrivals but wins on published-benchmark streams — whereas `boot_cold`, which never touches the solver's search, helps in every campaign. (Corrected 2026-10-06 after re-deriving every number from the raw CSVs; see `paper/icaps27/README.md`, section "Errors found in earlier drafts".))

### III.4 The domination guarantee — stated precisely, including the part that is *not* claimed

**Claim.** For any budget large enough for the ~1ms bootstrap to complete, `boot_cold`'s final reported value is **≤** the final value of **its own unmodified continuation solve** — i.e., ≤ whatever a `cpsat_cold` call with the *exact same* model, seed, and (budget-minus-bootstrap-time) would itself have returned. Its primal integral is likewise ≤ that same continuation's.

*Why this is true.* Step 3 above takes the pointwise minimum, at every moment, of the floor's (constant) value and the solver's own trajectory. Taking a pointwise minimum of a curve against a constant can only ever lower or match that curve — never raise it. So the final reported value can only be ≤ the solver's own final value, and the reported anytime curve can only be ≤ the solver's own curve, at every point. This is a straightforward, almost mechanical consequence of "keep the better of two," not a deep result — and the paper (Part IX) is explicit that this simplicity is itself a fair point a reviewer might raise.

**What this is *not* a guarantee of** (an important, hard-won correction — see Part II.5): it is **not** an exact guarantee against a *separately, independently invoked* `cpsat_cold` run on the same instance. Wall-clock timing isn't perfectly reproducible from run to run — background system jitter, OS scheduler noise, and CP-SAT's own internal timing-sensitive heuristics mean two "identical" runs can end at slightly different points in their search. At large scale (n=1547 paired instances), `boot_cold`'s final answer was strictly *worse* than an independently-run `cpsat_cold` on **7.6%** of instances (median excess 0.63%, max 3.63%) — small, and expected given the above, but real. The correct, precise statement is: *the guarantee holds against the method's own continuation; against an independent cold run, it holds empirically 92.4% of the time, which is a strong but not absolute finding.* An earlier draft of this paper said "provably never worse than cold-solving," which overstates this, and was corrected everywhere it appeared.

### III.5 Why the benefit size varies so much across cases — the one governing idea

Everywhere in this project's results, the size of `boot_cold`'s improvement is explained by **one quantity**: *how close does the ~1ms floor land to the eventual final answer?*

- **Subtractive / in-place deltas** (an item removed, a job cancelled, a value nudged, a duration jittered, a machine outage) leave most of the previous structure still valid. The floor is a near-lossless reuse of already-good decisions and lands within a fraction of a percent of the final answer. `cpsat_cold`, having no floor at all, spends real time re-discovering structure the floor already had — this is where the *largest* gains appear (up to ~99.9% primal-integral improvement in the strongest cases).
- **Additive deltas** (a new job arrives) are a harder case *for job-shop specifically*, because the simple floor policy just appends new work to the end of the schedule rather than intelligently slotting it into existing idle gaps — a real, identified, and explicitly *not yet solved* weakness (a smarter "gap insertion" floor was tried and did not show a statistically significant improvement; an honest null result, reported as such). Interestingly, this weakness does **not** generalize to RCPSP, whose floor construction happens to handle newly-inserted activities much more gracefully — a genuine, only-partially-understood cross-domain contrast the paper flags rather than smooths over.
- **Domains/solvers where the underlying solve is already near-instant** (e.g. knapsack for Gurobi/CPLEX, Part II.8) leave almost no anytime curve for any floor to improve on — the benefit shrinks toward (but does not vanish below) zero, honestly, because there's genuinely very little curve left to shape.

### III.6 What does *not* change — the honest scope of the benefit

The underlying solver's own search is completely untouched — `boot_cold`'s continuation call is byte-identical to `cpsat_cold`'s. This means **`boot_cold` does not make the solver reach the optimum faster, and does not prove optimality sooner**: both methods' best-found and best-*proven* curves meet at the same wall-clock moment. The entire, and only, benefit is in **what you can report if you are forced to stop early** — which describes essentially every real, budget-constrained, streaming deployment.

---

## Part IV — The codebase, file by file

The repository has grown across several distinct phases (Part II). This section maps the current structure to what each piece is for.

### IV.1 Top level

| File | What it is |
|---|---|
| `BOOT_COLD_PAPER.md` | The living, source-of-truth technical writeup — every number in it is traceable to a raw CSV. Read this for the precise, citation-grade version of everything summarized here. |
| `paper/boot_cold_icaps.tex` | Submission-ready LaTeX draft derived from the above, with a `paper/README.md` build/submission checklist. |
| `README.md` | The original, short project README from the Phase 0 era — describes the *original* LNS framing, now superseded by `boot_cold` but kept for history. |
| `README_ICAPS_EXPERIMENTS.md` | Practical how-to-run guide for the ICAPS-scale experiment campaigns. |
| `IMPLEMENTATION_PLAN.md` | The **original** project plan (the ICML/NeurIPS-targeted learned-bandit idea, Part II.1) — historical, superseded, kept as the record of where this started. |
| `docs/icaps_full_paper_plan.md` | The 6-phase (A–F) plan executed in Part II.5, with an in-place progress log. |
| `docs/icaps_experiment_plan.md` (+ `.pdf`) | An earlier, more detailed experiment-design document from the same phase. |
| `pytest.ini` | Test configuration — a `slow` marker excludes long-running tests (real-instance proofs, actual Gurobi/CPLEX solves) from the default fast run. |
| `phase0_*.csv` (top level) | Raw output from the very first Phase 0 / pilot experiments (job-shop, knapsack, "smart arms" sweeps) — the earliest data in the project. |

### IV.2 `phase0/` — the main package (despite the name, this holds essentially everything)

Core, domain-agnostic pieces:

| File | What it is |
|---|---|
| `streams.py` | Job-shop instance/stream generator: `Operation`, `Job`, `Instance` dataclasses; delta functions (`arrival`, `cancellation`, `duration_jitter`, `outage`, plus several later ICAPS-era additions like `batch_arrival`, `rush_job`); fully seeded and deterministic. |
| `model_builder.py` | The CP-SAT job-shop model (interval variables, precedence, `no_overlap`, outages as fixed intervals, makespan objective) plus a completely solver-independent `validate_solution` used to double-check every result. |
| `harness.py` | The core solving logic: `list_schedule_bootstrap` (the floor, Part III.3), `warm_bootstrap_solve` (the pocket wrapper — `use_hint=False` is `boot_cold`, `use_hint=True` is `boot_warm`), `cpsat_default_solve` (plain `cpsat_cold`/`cpsat_warm`), plus the older LNS/oracle machinery from the Phase 0 era (kept because it's still exercised by the robustness-check results). |
| `metrics.py` | `primal_integral`, `final_gap`, plus schedule-stability metrics (`fraction_moved_operations`, `machine_order_distance`, etc.) used in the ICAPS-readiness stability analysis. |
| `policies.py` | The Phase 0-era LNS arm-selection policies (uniform-random, epsilon-greedy). |
| `baselines.py` | Dispatch-rule baselines (e.g. most-work-remaining) added for the ICAPS baseline menu. |
| `bootstrap_policies.py` | Arrival-specific alternative floor constructions (`gap_insert`, `regret_insert`, `beam_insert`) tried as a fix for the additive-delta weakness (Part III.5) — tested, found not statistically significant, kept as an honest documented attempt. |
| `benchmark_loaders.py` | Loaders for real job-shop benchmark files: OR-Library/Taillard-style plain text format (auto-detecting 0- vs 1-indexing), plus JSON. |

Real-benchmark instance sets are recorded and analyzed by:

| File | What it is |
|---|---|
| `run_icaps_jssp_suite.py` | The main ICAPS-scale experiment runner — preset configurations (`paper_main`, `real_benchmarks`, `taillard_benchmarks`, `dmu_benchmarks`, `swv_benchmarks`, `yn_benchmarks`, etc.), `--parallel N` multiprocessing, crash-safe incremental checkpointing (`--resume --skip-existing`). |
| `analyze_icaps_results.py` | The **central statistics module** — `sign_test`, `bootstrap_ci_mean`, `wilcoxon_p`, `holm_correction`, `pairwise_vs_baseline`, `write_latex_table`, plot generation. Every later analysis script in the project imports from here rather than re-implementing these. |
| `make_paper_figures.py` | Two-step `capture` (record full solver trajectories on a held-out seed grid) → `plot` (generate the anytime-curve, worker-scaling, budget-sensitivity, RCPSP-summary figures) pipeline. |
| `run_knapsack_test.py` | The knapsack domain: `KInstance`/`KConfig`/stream generator, `knapsack_bootstrap`, `kcold`/`kboot_cold` solvers, `k_primal_integral` (the maximization-domain version of the metric). |
| `run_stall_test.py`, `run_budget_sweep.py` | Earlier experiment variants (stall-triggered interleaved solving; budget-sensitivity sweeps). |

Cross-solver validation (Part II.8):

| File | What it is |
|---|---|
| `mip_jssp.py` | The disjunctive big-M MIP job-shop formulation, with independent Gurobi and CPLEX backends (`gurobi_cold_solve`/`gurobi_boot_cold_solve`, `cplex_cold_solve`/`cplex_boot_cold_solve`), plus `jssp_mip_size` (a pre-flight variable/constraint counter used to stay under the license caps). |
| `mip_knapsack.py` | The same idea for knapsack — trivial single-constraint MIP models for both solvers. |
| `run_multisolver_test.py` | Experiment runner producing the 6-method (cpsat/gurobi/cplex × cold/boot_cold) comparison CSVs for both domains. |
| `analyze_multisolver_results.py` | Statistics for the cross-solver comparison, reusing `analyze_icaps_results.py`'s functions; also emits the LaTeX tables. |
| `make_multisolver_figures.py` | Anytime-curve and primal-integral bar-chart figures for the cross-solver comparison. |

### IV.3 `phase0/rcpsp/` — the RCPSP domain

Mirrors the top-level `phase0/` package's structure for the third domain: `instances.py` (dataclasses), `streams.py` (stream generator, including the `base_instance=` parameter that lets a *real* loaded instance become a dynamic stream), `model_builder.py` (CP-SAT RCPSP model), `harness.py` (the RCPSP `boot_cold`/`cpsat_cold` solvers, independently re-implemented and verified equivalent to the job-shop version's monotonicity logic), `benchmark_loaders.py` (the PSPLIB `.rcp`/"Patterson"-format loader, Part II.6), `run_rcpsp_test.py` (experiment runner).

### IV.4 `reopt/` — the negative-result exploration

The separate module documented in Part II.3: `hardened_streams.py` (a stream generator with more structurally severe deltas, scaled by a severity knob), `actions.py` (the 4 reuse strategies compared), `policy.py` (the contextual bandit that ultimately lost), `run_gate.py`/`run_learned.py` (the staged decision-rule experiments). Kept as the documented record of the negative result that is itself evidence for the final paper (Part II.9). This directory is intentionally excluded from `.gitignore`'s tracking in some configurations, per its own README — check current status if working in it.

### IV.5 `tests/`

One test file roughly per module above (`test_phase0.py`, `test_icaps_streams.py`, `test_icaps_baselines.py`, `test_icaps_benchmark_loaders.py`, `test_icaps_bootstrap_policies.py`, `test_icaps_runner_parallel.py`, `test_analyze_icaps_results.py`, `test_rcpsp.py`, `test_rcpsp_benchmark_loaders.py`, `test_mip_solvers.py`), plus `tests/fixtures/` holding every downloaded real-benchmark instance file (OR-Library, Taillard, dmu, swv, yn, PSPLIB RCPSP `.rcp` files) and their provenance records (`PROVENANCE.md` in each fixture subdirectory, documenting exactly where each file came from and what validation was performed against it). Tests marked `@pytest.mark.slow` (real-instance proofs to optimality, actual Gurobi/CPLEX solves) are excluded from the default `pytest` run and must be run explicitly with `-m slow`.

### IV.6 `scripts/`

Thin shell-script wrappers around the Python runners for each named experiment campaign (`run_icaps_pilot.sh`, `run_icaps_main.sh`, `run_icaps_taillard.sh`, `run_rcpsp_real.sh`, etc.), sharing common setup via `_common.sh`. These are what actually got launched (often in the background, for campaigns taking many minutes) throughout the project's later phases.

### IV.7 `results/`

All raw experiment output: `results/icaps/runs/*.csv` (per-campaign raw rows), `results/icaps/rcpsp/*.csv` (RCPSP campaigns), `results/icaps/analysis_*/`  (per-benchmark-family statistical analysis: report, tables, figures), `results/multisolver/` (the Gurobi/CPLEX cross-solver campaign and its analysis). Every number quoted anywhere in `BOOT_COLD_PAPER.md` traces back to a specific file in this tree.

---

## Part V — Experimental methodology

### V.1 Domains and stream generators

All three domains (job-shop, knapsack, RCPSP) follow the same shape: a **base instance**, followed by a sequence of **deltas**, each drawn from a weighted random choice among domain-specific delta kinds, fully seeded so any stream can be regenerated byte-for-byte from its seed. Base-instance sizes were, in every domain, deliberately chosen to be *hard enough that the solver cannot trivially close the gap within the budget* — this was verified empirically before committing compute, every time, because a too-easy configuration gives every method a tie and measures nothing.

### V.2 The fairness protocol

Every method being compared on a given instance receives: the same total wall-clock budget, the same solver random seed, `num_workers = 1` (single-threaded, so parallelism differences can't confound the comparison — multi-worker scaling was tested separately, Part VI), and a shared `best_known` reference (the best value *any* compared method found on that instance), so every method is scored against the same target. Every returned solution is **independently re-validated** — feasibility re-checked from scratch by code that does not trust the solver's own claim, catching model-construction bugs a solver's own "feasible" flag could not.

### V.3 Metrics

- **Primal integral (PI)** — Part I.7. The primary metric.
- **Final gap** — the standard end-of-budget relative distance from the best-known value.
- **Significance** — because final quality is *expected* to tie exactly (by the domination guarantee, Part III.4), and primal integral is the metric of real interest, the project reports exact two-sided sign-test p-values on the head-to-head win/loss count, which makes no assumption about the distribution of primal-integral values, cross-checked by the Wilcoxon signed-rank test and a bootstrap confidence interval on the mean improvement.

---

## Part VI — Results, all of them, organized

*(Every number below is sourced from `BOOT_COLD_PAPER.md`; see that document for full tables, breakdowns by delta kind, and exact CSV provenance.)*

### VI.1 Original pilot (job-shop + knapsack, small scale)

- Job-shop, main experiment: 20/20 primal-integral wins on stream instances, 21.4% mean improvement, `p < 0.0001`.
- Job-shop, held-out confirmation (seeds never used during development): 8/8 wins, 18.1% improvement, `p = 0.0078` — replicates the main result, no sign of overfitting to development seeds.
- Knapsack, domain transfer: 8/8 wins, **99.7%** mean improvement (the floor lands within a quarter of a percent of the final answer on this domain).
- Final objective across the whole pilot: **36/36 primal-integral wins where a floor was available, 0 losses.**

### VI.2 RCPSP, real scale

90 instances (10 base + 80 stream): 83 wins / 0 ties / 7 losses overall, and on stream instances specifically, **80/80 wins**, `p = 1.65e-24`, 72.3% mean improvement. Notably, RCPSP's additive delta (`activity_insertion`) is *not* a weak case here (56% improvement) — a genuine, only-partially-explained contrast with job-shop's additive-delta weakness.

### VI.3 ICAPS-preset scale (job-shop, pooled across six separate experiments)

n = 1547 paired instances: **84.9%** primal-integral win rate (`p ≈ 4.1e-182` sign test, `p ≈ 1.6e-152` Wilcoxon — both agree), and **92.4%** final-objective non-loss rate against an *independently invoked* cold run (117/1547 real losses, median excess 0.63%, max 3.63% — the precise, honestly-scoped version of the domination claim, Part III.4). This advantage **holds across CP-SAT's multi-worker portfolio search** (tested at 1, 4, 8, 16 workers on a small campaign of 28 paired instances per level; 75–100% win rate at every level). The earlier statement that `boot_warm` loses single-threaded (36%) was an artifact of pooling only the earliest campaigns; the verified finding is that hint-based reuse changes sign across campaigns. (Corrected 2026-10-06 after re-deriving every number from the raw CSVs; see `paper/icaps27/README.md`, section "Errors found in earlier drafts".)

### VI.4 Real published benchmark instances (six sources)

| Source | Domain | n (paired) | Win rate |
|---|---|---|---|
| OR-Library | job-shop | 540 | 89.3% |
| Taillard | job-shop | 560 | 88.2% |
| Demirkol (dmu) | job-shop | 140 | 86.4% |
| Storer-Wu (swv) | job-shop | 140 | 89.3% |
| Yamada-Nakano (yn) | job-shop | 112 | 83.9% |
| PSPLIB | RCPSP | 840 | 87.1% |

Pooled: **1566/1792 (87.4%)**, all statistically significant, all in an 83.9–89.3% band regardless of domain or size — the effect is not an artifact of any one source.

### VI.5 Cross-solver validation (Gurobi, CPLEX)

| Domain | Solver | n | Win/tie/loss | Holm-corrected `p` |
|---|---|---|---|---|
| job-shop | CP-SAT | 30 | 24/0/6 | 0.0014 |
| job-shop | Gurobi | 30 | 28/0/2 | 2.6e-6 |
| job-shop | CPLEX | 30 | 25/0/5 | 6.5e-4 |
| knapsack | CP-SAT | 30 | 29/0/1 | 1.2e-7 |
| knapsack | Gurobi | 30 | 30/0/0 | 5.6e-9 |
| knapsack | CPLEX | 30 | 29/0/1 | 1.2e-7 |

6/6 significant. Cross-solver "cold" comparison: CP-SAT beats Gurobi/CPLEX by 7–9× on job-shop; Gurobi/CPLEX beat CP-SAT by up to 40× on knapsack (Part II.8).

### VI.6 The robustness check (what failed to beat the simple method)

Three independent, well-powered attempts at something smarter all lost to `boot_cold` (Part II.3) — a 27-arm learned LNS bandit, an online contextual bandit (58% worse), and an oracle-mined hand-coded rule (3.9% worse on held-out seeds due to non-generalizing oracle choices).

---

## Part VII — How to reproduce everything

```bash
# Set up
.venv/bin/python -m pip install -r <whatever the project's requirements are>

# Fast unit tests (feasibility, determinism, statistics correctness)
.venv/bin/python -m pytest tests/ -q

# Slow tests too (real-instance proofs, actual Gurobi/CPLEX solves)
.venv/bin/python -m pytest tests/ -q -m slow

# Original pilot
.venv/bin/python -m phase0.run_stall_test --seeds 1 2 3 4 5 \
  --total-budget 10 --machines 15 --initial-jobs 15 --stream-length 4 \
  --full-shop --methods cpsat_cold boot_cold --out phase0_bootstrap_seeds1_5.csv
.venv/bin/python -m phase0.run_knapsack_test --seeds 1 2 --items 2000 \
  --correlated --weight-max 1000000 --total-budget 10 --stream-length 4 \
  --out phase0_knapsack_seeds1_2.csv

# ICAPS-scale campaigns (see scripts/ for the full set)
bash scripts/run_icaps_pilot.sh
bash scripts/run_icaps_taillard.sh
bash scripts/run_rcpsp_real.sh

# Statistical analysis + figures
.venv/bin/python -m phase0.analyze_icaps_results --csv <campaign.csv> --out-dir <dir>
.venv/bin/python -m phase0.make_paper_figures capture ...
.venv/bin/python -m phase0.make_paper_figures plot ...

# Cross-solver validation (requires `pip install gurobipy cplex docplex` — free tiers, see Part I.6)
.venv/bin/python -m phase0.run_multisolver_test --domain jssp --seeds 1 2 3 4 5 6 \
  --budget 8 --stream-length 4 --out results/multisolver/jssp_results.csv
.venv/bin/python -m phase0.run_multisolver_test --domain knapsack --seeds 1 2 3 4 5 6 \
  --budget 5 --stream-length 4 --items 700 --out results/multisolver/knapsack_results.csv
.venv/bin/python -m phase0.analyze_multisolver_results \
  --jssp results/multisolver/jssp_results.csv \
  --knapsack results/multisolver/knapsack_results.csv \
  --out-dir results/multisolver/analysis
.venv/bin/python -m phase0.make_multisolver_figures
```

`BOOT_COLD_PAPER.md` §9.6 has the authoritative, complete reproduction command list; the above is a representative subset.

---

## Part VIII — Honest limitations

Carried over faithfully from `BOOT_COLD_PAPER.md` §8, because a documentation file that hides them would be misleading:

- **No learning contribution.** `boot_cold` is a deterministic heuristic plus a monotone "keep the better of two" wrapper — no trained model, no adaptive component. This is a systems/OR contribution, not a machine-learning one.
- **The domination guarantee is precise, not absolute** (Part III.4) — exact against the method's own continuation; empirically 92.4% (not 100%) against an independently-invoked cold run at scale.
- **Each domain's bootstrap heuristic is hand-designed**; porting to a new problem class needs a new (typically straightforward) constructive rule, not a generic recipe.
- **Additive-delta weakness in job-shop specifically** (Part III.5); a proposed fix (smarter insertion) was tested and found not statistically significant — an honest, unresolved null result, not smoothed over.
- **Deltas are still synthetic in every domain**, even though base instances are now real in all six benchmark sources (Part II.6) — no source here is an actual recorded deployment trace of sequential re-solves.
- **Gurobi/CPLEX validation is at much smaller scale than CP-SAT's**, forced by the free license's hard size cap (Part I.6, II.8) — not yet known whether the effect holds at the scale of the six real-benchmark sources for these two solvers specifically, since that would require a paid or academic license this project does not have access to.
- **Knapsack is a near-null domain for Gurobi/CPLEX specifically** (Part II.8) — a real property of that domain-solver pairing, not a scale artifact.

---

## Part IX — Where this stands: venue, status, next steps

The user has directed this project at **ICAPS** specifically (not CPAIOR or a journal, despite the paper's own §10 originally suggesting those as a better fit). An honest risk assessment was given and accepted: the core theorem is close to a restatement of "report your incumbent," and the strongest reviewer-facing angle is not the theorem but the **empirical floor-vs-hint robustness finding** (`boot_cold` never hurts; `boot_warm`'s hinting can and does, asymmetrically by worker count) reframed in the language of the decades-old **plan-repair / reactive-scheduling** literature (match-up scheduling, Herroelen & Leus, plan stability) rather than the MIP/OR framing the paper currently leads with. Concrete, agreed next steps to strengthen the ICAPS submission specifically:

1. Reframe the introduction and related work around plan repair / reactive scheduling, demoting the domination theorem from headline claim to a supporting remark.
2. Promote the floor-vs-hint robustness result to the paper's central thesis.
3. Add at least one established reoptimization baseline beyond naive cold/warm (the existing fix-and-optimize freeze-fraction methods already in the baseline menu are the natural candidate to elevate).
4. Add a schedule-stability analysis (the metrics are already logged — `fraction_moved_ops`, `machine_order_distance` — just not yet featured as a headline result).
5. Add at least one delta stream grounded in a real, cited disruption model (e.g. literature-sourced arrival/failure rates) rather than purely synthetic weighted-random choice.

None of this is done yet as of this document; it is the agreed forward plan, tracked in memory for continuity across future sessions.

---

## Part X — Glossary

- **Anytime algorithm** — an algorithm that can be stopped at any time and still return its best answer so far, generally improving the longer it runs. (I.7)
- **Bootstrap (in this project's sense)** — the ~1ms, solver-free constructive repair that turns yesterday's solution into a feasible solution for today's problem. Not to be confused with "bootstrap" in the statistical-resampling sense (also used in this project, for confidence intervals — context disambiguates).
- **`boot_cold`** — this project's method: bootstrap floor + unmodified ("cold") solver continuation + report-the-better-of-two. (Part III)
- **`boot_warm`** — the variant that feeds the floor into the solver as a *hint* instead of keeping it separate; found less robust. (III.3)
- **Branch-and-bound** — the core search strategy of MIP solvers: recursively split the problem into sub-problems, and discard (prune) any sub-problem provably unable to beat the best solution found so far.
- **CP-SAT** — Google OR-Tools' constraint programming solver; this project's primary solver. (I.2)
- **CPLEX** — IBM's commercial MIP solver; one of the two cross-solver validation targets. (I.2, I.6)
- **Delta** — the small, structured change that turns instance `I_t` into `I_{t+1}` in a stream (e.g. a job arrival, a value change). (III.1)
- **Domination guarantee** — the theorem that `boot_cold`'s result is never worse than its own unmodified continuation. See the precise scope in III.4 — do not conflate with a guarantee against an independent cold run.
- **Final gap** — the relative distance between a method's final answer and the best-known value. (V.3)
- **Gurobi** — a commercial MIP solver; the other cross-solver validation target. (I.2, I.6)
- **Holm-Bonferroni correction** — adjusts significance thresholds when testing multiple comparisons at once, to control the chance of a false positive from multiple testing. (I.8)
- **Job-shop scheduling** — the problem of sequencing job operations onto machines to minimize completion time. (I.3)
- **Knapsack (0-1)** — the problem of choosing a value-maximizing subset of items under a weight limit. (I.4)
- **LNS (Large Neighborhood Search)** — an optimization technique: fix most of a solution, "destroy" (unfix) a small part, ask a solver to repair/improve just that part, repeat. Central to the project's original (pre-pivot) idea. (II.1–II.3)
- **MIP (Mixed-Integer Programming)** — a modeling style using linear constraints over continuous and integer variables, solved by branch-and-bound; Gurobi's and CPLEX's native paradigm. (I.2)
- **Primal integral (PI)** — the project's primary metric: the area under the relative-gap-vs-time curve; lower is better. Rewards being good throughout a solve, not just at the end. (I.7)
- **RCPSP** — Resource-Constrained Project Scheduling Problem; the project's third domain. (I.5)
- **Sign test** — an exact statistical test on the win/loss count of paired comparisons. (I.8)
- **Stream** — a sequence of related problem instances, each a small delta away from the last. (III.1)
- **Wilcoxon signed-rank test** — a statistical test that additionally weighs the *magnitude* of paired differences, not just their sign. (I.8)
