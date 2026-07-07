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
