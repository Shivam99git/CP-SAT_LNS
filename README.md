# CP-SAT LNS

This project is about making Google OR-Tools CP-SAT solve a stream of related
scheduling problems more efficiently.

Think of a factory schedule. New jobs may arrive, some jobs may be cancelled,
task durations may change, or a machine may become unavailable. Instead of
solving every changed schedule from zero, this project tries to reuse the
previous solution and improve only the parts that need attention.

## Main idea

The project uses Large Neighborhood Search (LNS):

1. Start with a CP-SAT solution.
2. Keep most of that solution fixed.
3. Open up a small part of the solution.
4. Ask CP-SAT to repair or improve that part.
5. Repeat this many times.

There are many possible ways to choose which part of the solution to open up.
For example, the system can relax random tasks, tasks on one machine, critical
tasks, or tasks affected by the latest change.

The research goal is to make a learning policy choose these LNS strategies
better over time. Since the scheduling problems come as a stream, the policy
should remember what worked on earlier problems and adapt when the stream
changes.

## What is built now

Phase 0 is implemented. It includes:

- a generator for dynamic job-shop scheduling streams
- a CP-SAT model builder
- an LNS solving loop
- simple policies such as random and epsilon-greedy
- baseline comparisons against normal CP-SAT and warm-start CP-SAT
- an oracle experiment that checks how much improvement is possible if the best
  LNS move is known in hindsight

The current important next step is to fix a budget-allocation issue in Phase 0
and rerun the experiments. After that, the results will show whether there is
enough benefit to continue with the learned policy.

## How to run

```bash
python -m pytest tests/ -q
python -m phase0.run_phase0 --quick
```

For more details, see `IMPLEMENTATION_PLAN.md` and `phase0/README.md`.
