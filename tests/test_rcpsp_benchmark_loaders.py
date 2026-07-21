"""Tests for phase0/rcpsp/benchmark_loaders.py -- the real PSPLIB/.rcp
(Patterson format) RCPSP instance loader, and the base_instance wiring in
generate_rcpsp_stream that lets a loaded instance become a dynamic stream.

Real fixture files in tests/fixtures/rcpsp_real/ are downloaded from
https://github.com/ScheduleOpt/benchmarks (rcpsp/instances/{j30,j60,j90,j120})
-- see tests/fixtures/rcpsp_real/PROVENANCE.md. optalcp_bks_reference.json in
the same directory holds proven-optimal objectives for all 40 fixtures,
extracted from https://optalcp.com/benchmarks/rcpsp/main.html.

    .venv/bin/python -m pytest tests/test_rcpsp_benchmark_loaders.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phase0.rcpsp.benchmark_loaders import load_rcp_dir, load_rcp_instance
from phase0.rcpsp.model_builder import build_rcpsp_model, solve_rcpsp, validate_rcpsp_solution
from phase0.rcpsp.streams import RStreamConfig, generate_rcpsp_stream

FIXTURES = Path(__file__).parent / "fixtures" / "rcpsp_real"
OPTALCP_BKS = json.loads((FIXTURES / "optalcp_bks_reference.json").read_text())


def test_load_rcp_instance_shape():
    inst = load_rcp_instance(FIXTURES / "j30_1_1.rcp")
    assert len(inst.activities) == 32
    assert inst.resources == {"r0": 12, "r1": 13, "r2": 4, "r3": 12}
    # dummy source (file's activity 1 -> 0-indexed "a0"): zero duration/usage
    src = inst.activity_by_id["a0"]
    assert src.duration == 0
    assert src.resource_usage == {}
    assert src.predecessors == ()  # nothing precedes the source


def test_load_rcp_instance_ids_are_0_indexed_matching_synthetic_convention():
    """IDs must be 0-indexed ("a0".."a{n-1}"), exactly matching
    generate_rcpsp_instance's synthetic-activity naming -- required so
    generate_rcpsp_stream(base_instance=...)'s activity_insertion delta
    (which names new activities f"a{len(activities)}") can never collide
    with an existing real activity's id (regression: 2026-07-12, a prior
    1-indexed version collided on the last activity, corrupting the
    precedence graph on any real instance that got an insertion delta)."""
    inst = load_rcp_instance(FIXTURES / "j30_1_1.rcp")
    assert len(inst.activities) == 32
    assert {a.activity_id for a in inst.activities} == {f"a{i}" for i in range(32)}


def test_load_rcp_instance_predecessors_inverted_from_successors_correctly():
    """File encodes successors; loader must invert to predecessors such that
    every precedence edge is preserved (a is a predecessor of b in the
    loaded instance iff b was listed as a's successor in the file)."""
    inst = load_rcp_instance(FIXTURES / "j30_1_1.rcp")
    # from the raw file: activity 1 (0-indexed "a0") lists successors 2, 3, 4
    # (0-indexed "a1", "a2", "a3")
    for succ_id in ("a1", "a2", "a3"):
        assert "a0" in inst.activity_by_id[succ_id].predecessors


def test_generate_rcpsp_stream_activity_insertion_never_collides_with_real_ids():
    """Direct regression test for the 2026-07-12 bug: force activity_insertion
    on every step and confirm no duplicate activity_id is ever introduced,
    across all four real instance sizes (j30/j60/j90/j120 -- the bug only
    manifested on larger instances in practice, but this checks all sizes)."""
    for name in ("j30_1_1", "j60_1_1", "j90_1_1", "j120_1_1"):
        inst = load_rcp_instance(FIXTURES / f"{name}.rcp")
        cfg = RStreamConfig(
            stream_length=6, seed=1, severity="high",
            p_duration_jitter=0, p_resource_capacity_reduction=0,
            p_activity_insertion=1.0, p_activity_cancellation=0,
        )
        stream = generate_rcpsp_stream(cfg, base_instance=inst)
        for step_inst in stream:
            ids = [a.activity_id for a in step_inst.activities]
            assert len(ids) == len(set(ids)), f"{name} step {step_inst.index}: duplicate ids"


def test_load_rcp_instance_solvable_and_validated():
    inst = load_rcp_instance(FIXTURES / "j30_1_1.rcp")
    sol, obj, status = solve_rcpsp(build_rcpsp_model(inst), time_limit=15.0)
    assert sol is not None
    assert validate_rcpsp_solution(inst, sol) == obj


def test_load_rcp_instance_malformed_token_count_raises(tmp_path):
    bad = tmp_path / "bad.rcp"
    bad.write_text("3 1\n5\n0 0 1 2\n")  # declares 3 activities, gives only 1
    with pytest.raises((ValueError, IndexError)):
        load_rcp_instance(bad)


def test_load_rcp_dir():
    instances = load_rcp_dir(FIXTURES, max_files=5)
    assert len(instances) == 5
    names = [name for name, _ in instances]
    assert names == sorted(names)  # deterministic ordering


def test_rcpsp_stream_from_real_base_instance():
    """A real loaded instance, turned into a dynamic stream via
    generate_rcpsp_stream(base_instance=...), gets deltas applied on top of
    it exactly like a randomly-generated base would -- every resulting
    instance in the stream must remain solvable and independently valid."""
    inst = load_rcp_instance(FIXTURES / "j30_2_1.rcp")
    cfg = RStreamConfig(stream_length=3, seed=11, severity="medium")
    stream = generate_rcpsp_stream(cfg, base_instance=inst)
    assert len(stream) == 4
    assert stream[0].activities == inst.activities  # base preserved verbatim
    for later in stream[1:]:
        sol, obj, _status = solve_rcpsp(build_rcpsp_model(later), time_limit=5.0)
        assert sol is not None
        assert validate_rcpsp_solution(later, sol) == obj


@pytest.mark.slow
@pytest.mark.parametrize("name", ["j30_1_1", "j30_1_2", "j30_2_1", "j30_2_2", "j30_3_1"])
def test_real_j30_instances_solve_to_proven_optimality(name):
    """Self-certifying correctness check: CP-SAT's OPTIMAL status is itself a
    machine-checked proof (branch-and-bound closing the gap), independent of
    any external reference. j30 instances (32 activities incl. 2 dummies)
    are small enough to prove within budget. Also cross-checked against the
    external optalcp.com reference below (independent of CP-SAT's own proof).
    """
    from ortools.sat.python import cp_model
    inst = load_rcp_instance(FIXTURES / f"{name}.rcp")
    sol, obj, status = solve_rcpsp(build_rcpsp_model(inst), time_limit=30.0)
    assert status == cp_model.OPTIMAL, f"{name}: expected proven optimal, got {status}"
    assert sol is not None
    assert validate_rcpsp_solution(inst, sol) == obj
    assert obj == OPTALCP_BKS[name], (
        f"{name}: CP-SAT proved optimal={obj} but external reference (OptalCP + "
        f"CP Optimizer, both proof=true) says {OPTALCP_BKS[name]} -- a genuine "
        f"disagreement between two independently-proved optima would indicate a "
        f"modeling bug, not just a search-quality difference."
    )


def test_optalcp_bks_reference_covers_every_fixture():
    """optalcp_bks_reference.json (see PROVENANCE.md for extraction details --
    pulled from https://optalcp.com/benchmarks/rcpsp/main.html, where OptalCP
    and IBM CP Optimizer independently proved the same optimal objective for
    every one of our 40 fixture instances) must have exactly one positive-int
    entry per .rcp file here, keyed by our {fam}_{set}_{inst} naming."""
    rcp_names = {p.stem for p in FIXTURES.glob("*.rcp")}
    assert set(OPTALCP_BKS) == rcp_names
    assert all(isinstance(v, int) and v > 0 for v in OPTALCP_BKS.values())


@pytest.mark.slow
def test_real_instances_match_external_optalcp_bks_no_better_than_optimal():
    """Solve every fixture at a modest budget and assert we never report an
    objective *better* than the external proven optimum -- a basic
    correctness sanity check (finding better-than-optimal would indicate a
    model or validator bug, not a search-quality issue). We do not require
    matching the optimum exactly here (larger instances like j120 are not
    reliably provable in a short per-test budget -- see the 8s-budget
    production campaign in results/icaps/rcpsp/rcpsp_real_benchmarks.csv,
    where 222/240 base-instance runs matched exactly and 0/240 beat it)."""
    for name, bks in sorted(OPTALCP_BKS.items()):
        inst = load_rcp_instance(FIXTURES / f"{name}.rcp")
        sol, obj, _status = solve_rcpsp(build_rcpsp_model(inst), time_limit=10.0)
        assert sol is not None
        assert obj >= bks, f"{name}: found objective {obj} better than external optimum {bks}"


def test_rcpsp_stream_from_real_base_is_deterministic():
    inst = load_rcp_instance(FIXTURES / "j60_1_1.rcp")
    cfg = RStreamConfig(stream_length=4, seed=3, severity="high")
    s1 = generate_rcpsp_stream(cfg, base_instance=inst)
    s2 = generate_rcpsp_stream(cfg, base_instance=inst)
    assert s1 == s2
