# Phase 0 — ceiling experiment for learned LNS over CP-SAT

**Question:** on a stream of related dynamic job-shop instances, how much
headroom is there between naive CP-SAT / non-adaptive LNS and an oracle that
always picks the best destroy arm in hindsight? If the oracle's advantage is
small, or its arm choices are homogeneous (one arm always wins), a learned
arm-selection policy has nothing to learn and the idea dies cheaply here.

## Pieces

| file | contents |
|---|---|
| `streams.py` | seeded generator of instance streams: base job-shop + deltas (job arrival, cancellation, duration jitter, machine outage). Consecutive instances share most structure — the premise the learned LNS exploits. |
| `model_builder.py` | CP-SAT interval model (precedence, no_overlap with outages as fixed intervals, makespan objective) + a CP-SAT-free `validate_solution` used by tests and the runner. |
| `harness.py` | outer LNS loop: policy picks an arm (destroy strategy × size, 12 arms), non-destroyed ops keep their incumbent *machine order* (starts float, so the schedule can left-shift; exact-start pinning made repairs nearly impossible), CP-SAT repairs within a time slice, hill-climbing acceptance. Logs (arm, reward) per round. |
| `policies.py` | uniform-random and epsilon-greedy (reset-per-instance = BALANS-like, or persistent across the stream). |
| `metrics.py` | primal integral (normalized, gap=1 before first solution) and final gap. |
| `run_phase0.py` | the experiment: baselines a–e plus the oracle. |

## Methods compared

- `cpsat_cold` — one full-budget CP-SAT solve per instance
- `cpsat_warm` — same, hinted with the previous instance's solution
- `lns_uniform` — LNS, uniform-random arm
- `lns_eps_reset` — LNS + ε-greedy, stats reset each instance (BALANS-like)
- `lns_eps_persist` — LNS + ε-greedy, stats carried across the stream
- `oracle` — every round evaluates **all 12 arms** from the same incumbent and
  keeps the best; only the kept arm's time is charged to a virtual clock.
  Best-arm-in-hindsight ceiling; costs ~12× the budget in wall clock.

## Run

```bash
.venv/bin/python -m pytest tests/ -q          # sanity
.venv/bin/python -m phase0.run_phase0 --quick # smoke (~minutes)
.venv/bin/python -m phase0.run_phase0 --budget 10 --slice 2 --stream-length 20
```

Outputs a per-(method, instance) CSV and prints: mean/total primal integral,
mean final gap, wins per method, and the oracle's arm-choice distribution.

## Decision rule

Proceed past phase 0 only if **both** hold:

1. Oracle mean primal integral is meaningfully below the best non-oracle
   LNS baseline (there is headroom for smarter arm selection), and
2. the oracle's improving-round arm choices are spread over several arms
   and correlate with observable context (round index, delta kind, ...) —
   otherwise a static arm schedule would capture the gain without learning.

## Fixed bug: initial-incumbent budget (2026-07-08)

`lns_solve` and `oracle_solve` used to cap the *first* incumbent solve at
`slice_budget` regardless of `total_budget`, while `cpsat_cold` gets the
full `total_budget` as one continuous solve. Since CP-SAT is anytime, this
systematically started every LNS/oracle method from a worse incumbent than
`cpsat_cold` for the same nominal budget — verified directly (instance 0,
`--full-shop --machines 15 --initial-jobs 15`): 2s-initial gave 729, a fair
8s-initial gave 699, vs. `cpsat_cold`'s 701 at the full 10s. This was found
and fixed independently in two places (this session, and by a collaborator
who pushed a near-identical fix in parallel); the version that landed gives
the initial solve `total_budget - slice_budget`, reserving exactly one
slice's worth of time for at least one repair round.

**Result after the fix** (`--full-shop --machines 15 --initial-jobs 15
--stream-length 12 --seed 0 --budget 10 --slice 2`, single seed/stream):
the ranking flips. `oracle` now has the best mean primal integral (0.0216)
and mean final gap (0.36%), beating `cpsat_cold` (0.0233 / 0.90%) on 7/13
instances, tying on 3, losing on 3. The non-adaptive LNS baselines
(`lns_uniform`, `lns_eps_reset`, `lns_eps_persist`) still trail `cpsat_cold`
on mean primal integral — meaning naive/non-contextual arm selection
doesn't capture the headroom the oracle shows is available, which is
exactly the gap a learned, context-aware selector would need to close.
46 improving rounds spread across 7/12 distinct arms — heterogeneous, per
the printed diagnostic.

Both decision-rule conditions above look satisfied on this one seed/stream.
**Not yet a confirmed pass** — this is a single stream at a single seed;
the plan calls for ~20 streams × 100 instances before treating the gate as
cleared. Next step: repeat across multiple seeds/streams before committing
to Phase 1.
