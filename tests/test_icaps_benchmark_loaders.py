"""Tests for phase0/benchmark_loaders.py.

Most tests use small synthetic fixture files (tests/fixtures/) in the
documented formats. `test_real_instances_match_published_optima` (marked
`slow`, excluded from the default run -- see pytest.ini) additionally
validates against 10 real OR-Library instances in
tests/fixtures/benchmarks_real/ (provenance: PROVENANCE.md in that
directory) -- run it explicitly with:

    .venv/bin/python -m pytest tests/test_icaps_benchmark_loaders.py -m slow -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phase0.benchmark_loaders import (
    load_benchmark_dir,
    load_benchmark_file,
    load_json_instance,
    load_taillard_style,
    save_json_instance,
)
from phase0.model_builder import build_model, solve, validate_solution
from phase0.streams import StreamConfig, generate_stream

FIXTURES = Path(__file__).parent / "fixtures"
REAL_FIXTURES = FIXTURES / "benchmarks_real"


def test_load_taillard_style_0indexed():
    inst = load_taillard_style(FIXTURES / "tiny_taillard_0idx.txt")
    assert inst.num_machines == 3
    assert len(inst.jobs) == 3
    assert len(inst.all_ops) == 9
    machines = {op.machine for op in inst.all_ops}
    assert machines == {0, 1, 2}
    # first job: (0,5)(1,3)(2,6)
    j0 = inst.jobs[0]
    assert [(op.machine, op.duration) for op in j0.ops] == [(0, 5), (1, 3), (2, 6)]


def test_load_taillard_style_1indexed_normalizes_to_0indexed():
    inst0 = load_taillard_style(FIXTURES / "tiny_taillard_0idx.txt")
    inst1 = load_taillard_style(FIXTURES / "tiny_taillard_1idx.txt")
    # after normalization both files encode the SAME instance
    for j0, j1 in zip(inst0.jobs, inst1.jobs):
        assert [(op.machine, op.duration) for op in j0.ops] == \
               [(op.machine, op.duration) for op in j1.ops]


def test_load_json_instance():
    inst = load_json_instance(FIXTURES / "tiny_instance.json")
    assert inst.num_machines == 3
    assert len(inst.jobs) == 2
    assert inst.jobs[0].job_id == "custom_j0"
    assert [(op.machine, op.duration) for op in inst.jobs[0].ops] == [(0, 5), (1, 3)]


def test_load_benchmark_file_auto_detect():
    a = load_benchmark_file(FIXTURES / "tiny_taillard_0idx.txt")
    b = load_benchmark_file(FIXTURES / "tiny_instance.json")
    assert len(a.jobs) == 3
    assert len(b.jobs) == 2


def test_load_benchmark_dir():
    instances = load_benchmark_dir(FIXTURES)
    assert len(instances) == 3  # 2 taillard-style + 1 json
    capped = load_benchmark_dir(FIXTURES, max_files=1)
    assert len(capped) == 1


def test_loaded_instance_is_solvable_and_valid():
    inst = load_taillard_style(FIXTURES / "tiny_taillard_0idx.txt")
    solution, objective, status = solve(build_model(inst), time_limit=3.0)
    assert solution is not None
    makespan = validate_solution(inst, solution)
    assert makespan == objective


def test_loaded_instance_can_become_a_dynamic_stream():
    """A static benchmark instance, turned into a stream via
    generate_stream(base_instance=...), gets deltas applied on top of it
    exactly like a randomly-generated base instance would."""
    inst = load_taillard_style(FIXTURES / "tiny_taillard_0idx.txt")
    cfg = StreamConfig(num_machines=inst.num_machines, stream_length=3, seed=4,
                       p_arrival=0.5, p_cancellation=0, p_duration_jitter=0.5, p_outage=0)
    stream = generate_stream(cfg, base_instance=inst)
    assert len(stream) == 4
    assert stream[0].jobs == inst.jobs  # base preserved verbatim
    for later in stream[1:]:
        solution, objective, status = solve(build_model(later), time_limit=3.0)
        assert solution is not None
        assert validate_solution(later, solution) == objective


_KNOWN_OPTIMAL = {
    "ft06": 55, "ft10": 930, "ft20": 1165,
    "la01": 666, "la02": 655, "la03": 597, "la04": 590, "la05": 593,
    "abz5": 1234, "abz6": 943,
}
# per-instance budget: enough to reach (and for smaller ones, prove) the
# published optimum. ft20 (20x5) needs the most; see PROVENANCE.md.
_BUDGET_S = {"ft20": 60.0, "ft10": 20.0, "abz5": 20.0, "abz6": 20.0}


@pytest.mark.slow
@pytest.mark.parametrize("name,known_optimal", sorted(_KNOWN_OPTIMAL.items()))
def test_real_instances_match_published_optima(name, known_optimal):
    """The strongest available correctness check for benchmark_loaders.py:
    load a real OR-Library instance and confirm CP-SAT reaches the exact
    published optimal makespan, with an independently-validated solution.
    """
    inst = load_taillard_style(REAL_FIXTURES / f"{name}.txt", name=name)
    budget = _BUDGET_S.get(name, 10.0)
    solution, objective, status = solve(build_model(inst), time_limit=budget)
    assert solution is not None
    assert validate_solution(inst, solution) == objective
    assert objective == known_optimal, (
        f"{name}: got {objective}, published optimum is {known_optimal} "
        f"(status={status}, budget={budget}s)"
    )


def test_save_json_instance_round_trip(tmp_path):
    inst = load_taillard_style(FIXTURES / "tiny_taillard_0idx.txt")
    out = tmp_path / "roundtrip.json"
    save_json_instance(inst, out)
    reloaded = load_json_instance(out)
    assert len(reloaded.jobs) == len(inst.jobs)
    for a, b in zip(inst.jobs, reloaded.jobs):
        assert [(op.machine, op.duration) for op in a.ops] == \
               [(op.machine, op.duration) for op in b.ops]
