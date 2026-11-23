"""Cross-solver model equivalence against an exhaustive oracle (Tasks 4.4,
8.2, 8.3). Every registered adapter must reproduce the oracle optimum on
tiny instances covering each supported feature; the strict-improvement cutoff
must make every solver report INFEASIBLE exactly when the cutoff is below the
optimum; kept machine-order arcs must be enforced. Positive durations only
(campaign instances always have durations >= 5; zero-length semantics differ
between CP-SAT and the validator, documented in tests/cobar/test_certificates).

Run with the multisolver environment:
    .venv_ms/bin/python -m pytest tests/multisolver -q
"""

import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cobar"))
from test_certificates import random_feasible_schedule, random_instance, with_commitments  # noqa: E402

from phase0.jobshop_milp import build_milp  # noqa: E402
from phase0.schedule_validator import check_schedule  # noqa: E402
from phase0.solver_adapters import ADAPTERS, SolveRequest, run_adapter  # noqa: E402
from phase0.solver_independent_model import (  # noqa: E402
    exhaustive_optimum, from_canonical_dict, instance_hash, to_canonical_dict,
)
from phase0.streams import StreamConfig, generate_stream  # noqa: E402

SOLVERS = sorted(ADAPTERS)


def _solve(name, inst, budget=10.0, **kw):
    t0 = time.monotonic()
    return run_adapter(ADAPTERS[name], SolveRequest(instance=inst, t0=t0, deadline=t0 + budget, **kw))


def _feature_instances():
    rng = random.Random(2027)
    cases = []
    for feature in ("plain", "releases", "outages", "commitments"):
        made = 0
        while made < 3:
            inst = random_instance(rng, n_jobs=3, n_mach=3, dur=(1, 5),
                                   outages=feature in ("outages", "commitments"),
                                   releases=feature in ("releases", "commitments"))
            if feature == "commitments":
                try:
                    S = random_feasible_schedule(rng, inst, slack=2)
                except RuntimeError:
                    continue
                inst = with_commitments(rng, inst, S)
                if not inst.frozen_starts:
                    continue
            cases.append((f"{feature}{made}", inst))
            made += 1
    # dynamic deltas from the real stream generator: arrival, cancellation,
    # duration change, outage (tiny 3x3 shops so enumeration stays exact)
    seen = set()
    for seed in range(60):
        cfg = StreamConfig(num_machines=3, initial_jobs=2, ops_per_job=(2, 3), duration_range=(2, 9),
                           stream_length=3, seed=seed)
        for inst in generate_stream(cfg)[1:]:
            per_m = {}
            for o in inst.all_ops:
                per_m[o.machine] = per_m.get(o.machine, 0) + 1
            if inst.delta_kind not in seen and max(per_m.values()) <= 4:
                seen.add(inst.delta_kind)
                cases.append((f"delta_{inst.delta_kind}", inst))
        if len(seen) == 4:
            break
    return cases


CASES = _feature_instances()


def test_feature_coverage():
    names = {n.rstrip("0123456789") for n, _ in CASES}
    assert {"plain", "releases", "outages", "commitments"} <= names
    assert {"delta_arrival", "delta_cancellation", "delta_duration_jitter", "delta_outage"} <= names


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("solver", SOLVERS)
def test_solver_matches_exhaustive_oracle(solver, case):
    _, inst = case
    opt, S = exhaustive_optimum(inst)
    assert check_schedule(inst, S) == opt
    r = _solve(solver, inst)
    assert r.status in ("OPTIMAL", "FEASIBLE"), (r.status, r.error)
    assert r.validated
    assert r.objective >= opt, "a solver reported a schedule better than the proven optimum"
    if r.proven_optimal:
        assert r.objective == opt, "OPTIMAL status with a worse objective"
    assert r.objective == opt  # tiny instances: every engine closes them within the budget


@pytest.mark.parametrize("solver", SOLVERS)
def test_strict_improvement_cutoff_semantics(solver):
    for _, inst in CASES[:6]:
        opt, _ = exhaustive_optimum(inst)
        r = _solve(solver, inst, cutoff=opt - 1)
        assert r.status == "INFEASIBLE" and r.schedule is None, (r.status, r.objective)
        r = _solve(solver, inst, cutoff=opt)
        assert r.objective == opt


@pytest.mark.parametrize("solver", SOLVERS)
def test_kept_arcs_are_enforced(solver):
    rng = random.Random(11)
    for _, inst in CASES[:6]:
        opt, S = exhaustive_optimum(inst)
        by_m = {}
        for o in inst.all_ops:
            by_m.setdefault(o.machine, []).append(o.op_id)
        # force the REVERSE of the optimal order on one machine with >= 2 ops
        m = next((m for m, ids in by_m.items() if len(ids) >= 2), None)
        if m is None:
            continue
        seq = sorted(by_m[m], key=lambda v: S[v])
        arcs = [(seq[-1], seq[0])]
        r = _solve(solver, inst, kept_arcs=arcs)
        dur = {o.op_id: o.duration for o in inst.all_ops}
        if r.schedule is not None:
            assert r.schedule[seq[0]] >= r.schedule[seq[-1]] + dur[seq[-1]]
        # agreement with CP-SAT on the restricted optimum
        ref = _solve("cpsat", inst, kept_arcs=arcs)
        assert r.status == ref.status and r.objective == ref.objective


def test_canonical_roundtrip_and_hash_stability():
    for _, inst in CASES:
        d = to_canonical_dict(inst)
        back = from_canonical_dict(d)
        assert instance_hash(back) == instance_hash(inst)
        assert to_canonical_dict(back) == d


def test_milp_big_m_never_cuts_the_optimum():
    """The MILP with derived big-M values, with every start fixed to an
    optimal schedule, must stay feasible (CP-SAT used only as the LP/IP
    checker of the fixed assignment)."""
    for _, inst in CASES:
        opt, S = exhaustive_optimum(inst)
        lm = build_milp(inst)
        x = lm.start_vector(S)
        for coefs, sense, rhs in lm.rows:
            assert all(x[k] is not None for k in coefs)
            lhs = sum(c * x[k] for k, c in coefs.items())
            assert (lhs >= rhs - 1e-9) if sense == ">=" else (lhs <= rhs + 1e-9) if sense == "<=" else abs(lhs - rhs) < 1e-9
        for k, v in enumerate(x):
            assert lm.lb[k] - 1e-9 <= v <= lm.ub[k] + 1e-9
