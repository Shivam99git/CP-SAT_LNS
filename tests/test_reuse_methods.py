"""Tests for the strict validator and the deadline-correct reuse methods.

    .venv/bin/python -m pytest tests/test_reuse_methods.py -q
"""

from dataclasses import replace

import pytest

from phase0.reuse_methods import GATE1_METHODS, run_method
from phase0.schedule_validator import ScheduleError, check_schedule
from phase0.streams import Instance, Job, Operation, Outage, StreamConfig, generate_stream


def _two_job_instance(**kw) -> Instance:
    jobs = (
        Job("j0", (Operation("j0_o0", 0, 3), Operation("j0_o1", 1, 2))),
        Job("j1", (Operation("j1_o0", 1, 4), Operation("j1_o1", 0, 1))),
    )
    return Instance(index=0, num_machines=2, jobs=jobs, **kw)


GOOD = {"j0_o0": 0, "j0_o1": 4, "j1_o0": 0, "j1_o1": 4}


def test_validator_accepts_feasible_schedule():
    assert check_schedule(_two_job_instance(), GOOD) == 6


@pytest.mark.parametrize("bad, msg", [
    ({**GOOD, "j0_o1": 2}, "precedence"),           # j0_o1 before j0_o0 ends (3)
    ({**GOOD, "j0_o1": 3}, "machine 1"),            # overlaps j1_o0 [0,4) on machine 1
    ({k: v for k, v in GOOD.items() if k != "j1_o1"}, "coverage"),
    ({**GOOD, "ghost": 0}, "coverage"),             # cancelled / unknown op present
    ({**GOOD, "j0_o0": -1}, "negative"),
    ({**GOOD, "j0_o0": 0.0}, "not an int"),
])
def test_validator_rejects(bad, msg):
    with pytest.raises(ScheduleError, match=msg):
        check_schedule(_two_job_instance(), bad)


def test_validator_outage_release_and_commitment():
    inst = _two_job_instance(outages=(Outage(0, 4, 6),))
    with pytest.raises(ScheduleError, match="outage"):
        check_schedule(inst, GOOD)  # j1_o1 on machine 0 at [4,5) hits outage [4,6)
    rel = replace(_two_job_instance(), jobs=(replace(_two_job_instance().jobs[0], release_date=1),
                                             _two_job_instance().jobs[1]))
    with pytest.raises(ScheduleError, match="release"):
        check_schedule(rel, GOOD)
    frozen = _two_job_instance(frozen_ops=frozenset({"j0_o1"}), frozen_starts={"j0_o1": 5})
    with pytest.raises(ScheduleError, match="commitment"):
        check_schedule(frozen, GOOD)


def test_validator_zero_length_interval_does_not_occupy_machine():
    jobs = (Job("j0", (Operation("j0_o0", 0, 0),)), Job("j1", (Operation("j1_o0", 0, 3),)))
    assert check_schedule(Instance(0, 1, jobs), {"j0_o0": 1, "j1_o0": 0}) == 3


def _stream():
    cfg = StreamConfig(num_machines=5, initial_jobs=5, stream_length=3, seed=7)
    cfg.ops_per_job, cfg.duration_range = (5, 5), (5, 50)
    return generate_stream(cfg)


@pytest.mark.parametrize("method", GATE1_METHODS)
def test_methods_return_validated_schedules_within_deadline(method):
    stream = _stream()
    prev = None
    for inst in stream:
        res = run_method(method, inst, prev, budget=0.5, seed=0)
        assert res.solution is not None and res.validated
        assert check_schedule(inst, res.solution) == res.objective
        # trajectory: strictly improving, time-ordered, ends at the returned objective
        ts = [e[0] for e in res.events]
        objs = [e[1] for e in res.events]
        assert ts == sorted(ts) and all(a > b for a, b in zip(objs, objs[1:]))
        assert objs[-1] == res.objective
        assert res.total_s <= 0.5 + 0.25  # solver overshoot is recorded, never hidden
        assert abs(res.overrun_s - max(0.0, res.total_s - 0.5)) < 1e-9
        prev = res.solution


def test_constructed_incumbent_is_timestamped_after_construction():
    stream = _stream()
    first = run_method("cold", stream[0], None, budget=0.5)
    for method, src in [("floor", "repair"), ("spt_cold", "spt"), ("mwkr_cold", "mwkr")]:
        res = run_method(method, stream[1], first.solution, budget=0.5)
        assert res.events[0][2] == src
        assert 0.0 < res.events[0][0] and res.events[0][0] >= res.construction_s


def test_history_methods_without_predecessor_match_cold_call():
    inst = _stream()[0]
    for method in ("hint", "floor", "floor_hint", "repaired_hint_only"):
        res = run_method(method, inst, None, budget=0.3)
        assert res.construction_source == "" and res.construction_s == 0.0
        assert all(e[2] == "cpsat" for e in res.events)


def test_repaired_hint_only_never_reports_the_repair_as_incumbent():
    stream = _stream()
    first = run_method("cold", stream[0], None, budget=0.5)
    res = run_method("repaired_hint_only", stream[1], first.solution, budget=0.5)
    assert all(e[2] == "cpsat" for e in res.events)
    assert res.construction_s > 0.0
