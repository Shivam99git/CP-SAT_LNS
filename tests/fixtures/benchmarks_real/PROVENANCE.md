# Real JSSP benchmark instances

Extracted 2026-07-11 from the OR-Library concatenated instance file:

```
wget https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/jobshop1.txt
```

(82 instances total; contributed to OR-Library by Dirk C. Mattfeld and
Rob J.M. Vaessens). The 10 files here are individually extracted subsets in
`phase0.benchmark_loaders.load_taillard_style` format (`n m` header line,
then `n` lines of `machine duration` pairs per job, 0-indexed machines) via
`extract_orlib.py`-style parsing of the "instance <name> ... +++...+++"
delimited blocks.

| instance | jobs x machines | source | published optimal makespan |
|---|---|---|---|
| ft06 | 6x6 | Fisher & Thompson (1963) | 55 |
| ft10 | 10x10 | Fisher & Thompson (1963) | 930 |
| ft20 | 20x5 | Fisher & Thompson (1963) | 1165 |
| la01-la05 | 10x5 | Lawrence (1984) | 666 / 655 / 597 / 590 / 593 |
| abz5 | 10x10 | Adams, Balas & Zawack (1988) | 1234 |
| abz6 | 10x10 | Adams, Balas & Zawack (1988) | 943 |

## Validation performed

Every instance was loaded via `load_taillard_style` and solved with CP-SAT
to completion (`OPTIMAL` status, budgets 20-60s depending on size). **All
10/10 reached the exact published optimal makespan above**, and every
solution passed `validate_solution` independently. This is the first time
`benchmark_loaders.py` has been validated against real downloaded instances
(previously tested only against synthetic fixtures — see the module
docstring's now-resolved "KNOWN LIMITATION" note).
