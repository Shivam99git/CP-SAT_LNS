# Cross-solver model equivalence (Tasks 4.3, 4.4, 8.2, 8.3)

All solvers receive the same physical instance (`phase0/streams.Instance`, canonical JSON + SHA-256 hash, `phase0/solver_independent_model.py`) and the same start-time domains: `lb_i` = release + job predecessors (or the committed time), `ub_i` = H − (remaining job work), H = `Instance.horizon`, the domain the CP-SAT research model already uses.

## Three formulations

| Family | Engines | Formulation |
|---|---|---|
| CP-SAT interval model | CP-SAT | `reuse_methods.build_research_model` unchanged: interval per operation, `AddNoOverlap` per machine with fixed outage intervals, releases, exact commitments, `C = max end` |
| CP Optimizer interval model | CP Optimizer (CE) | `interval_var` per operation, `end_before_start`, `no_overlap` per machine with fixed outage intervals, start bounds for releases/commitments |
| MiniZinc model | Gecode, Chuffed | `phase0/solver_adapters/mzn/jobshop.mzn`: integer starts in [lb, ub], `disjunctive` per machine over operations and outage blocks |
| Disjunctive MILP | Gurobi, CPLEX, SCIP, HiGHS, CBC, GLPK | `phase0/jobshop_milp.py`, built once, translated verbatim to each API |

Optional additions identical across all four: strict-improvement cutoff `C <= U − 1` and kept machine-order arcs `s_v >= s_u + p_u` (restricted neighbourhoods).

## MILP big-M values (derived, not arbitrary)

For operations i < j on one machine with binary y (y = 1 ⇔ i before j):
`s_j − s_i − M_ij y >= p_i − M_ij` and `s_i − s_j + M_ji y >= p_j`, with `M_ij = ub_i + p_i − lb_j`, `M_ji = ub_j + p_j − lb_i`. With y = 0 the first row reads `s_j >= s_i + p_i − M_ij >= lb_j` (redundant), so no schedule within the bounds is cut. Pairs whose order is implied by the bounds get no binary. Outages: if neither side is implied, binary z with `s_i + p_i <= o.start + (ub_i + p_i − o.start)(1 − z)` and `s_i >= o.end − (o.end − lb_i) z`; if only one side is possible the corresponding single inequality is added. `test_milp_big_m_never_cuts_the_optimum` substitutes an oracle-optimal schedule into every row.

## Verification

`tests/multisolver/test_equivalence.py` (183 tests): every engine reproduces the exhaustive-oracle optimum (`exhaustive_optimum`: enumerates all machine orders, earliest schedule per order set, no solver code) on 16 instances covering plain shops, release dates, outages, commitments, and real arrival/cancellation/duration/outage deltas; every engine returns INFEASIBLE exactly when the cutoff is below the optimum; kept arcs are enforced and restricted optima agree with CP-SAT; canonical serialization round-trips with a stable hash. `scripts/multisolver/run_smoke.py`: 624 method-level runs (10 engines × all supported methods S0–S5 × 8 feature classes, including generator-produced frozen starts), 0 failures. `scripts/multisolver/validate_results.py` re-validates every stored final schedule of the campaigns against the archived, hash-checked instance.

## Scope limits

Positive durations only: campaign instances always have durations >= 5. With zero-length operations, CP-SAT forbids a zero-length operation strictly inside an outage while the validator, the MILP and the MiniZinc model allow it (documented in `tests/cobar/test_certificates.py`). Commitments are exact equalities in every model.
