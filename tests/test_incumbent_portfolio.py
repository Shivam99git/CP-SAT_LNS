"""Tests for phase0/incumbent_portfolio.py."""

import time

from phase0.incumbent_portfolio import PORTFOLIOS, build_portfolio
from phase0.model_builder import build_model, solve
from phase0.schedule_validator import check_schedule
from phase0.streams import StreamConfig, generate_stream


def _stream(seed=1, m=6):
    cfg = StreamConfig(num_machines=m, initial_jobs=m, stream_length=5, seed=seed)
    cfg.ops_per_job, cfg.duration_range = (m, m), (5, 50)
    return generate_stream(cfg)


def test_selection_is_min_of_valid_members_and_deterministic():
    stream = _stream()
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.3)
    for inst in stream[1:]:
        for name, members in PORTFOLIOS.items():
            r1 = build_portfolio(inst, prev, members, construction_budget=1.0)
            r2 = build_portfolio(inst, prev, members, construction_budget=1.0)
            assert r1.chosen == r2.chosen and r1.objective == r2.objective
            valid = [c for c in r1.candidates if c.valid]
            assert r1.objective == min(c.objective for c in valid)
            assert check_schedule(inst, r1.solution) == r1.objective
            assert {c.name for c in r1.candidates} <= set(members)
        prev, _, _ = solve(build_model(inst), time_limit=0.3)


def test_history_members_skipped_without_predecessor():
    inst = _stream()[0]
    r = build_portfolio(inst, None, PORTFOLIOS["full"], construction_budget=1.0)
    assert {c.name for c in r.candidates} == {"spt", "mwkr", "lpt", "fifo"}
    assert build_portfolio(inst, None, PORTFOLIOS["hist"], 1.0).solution is None


def test_fresh_portfolio_never_reads_history():
    stream = _stream()
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.3)
    a = build_portfolio(stream[1], prev, PORTFOLIOS["fresh"], 1.0)
    b = build_portfolio(stream[1], None, PORTFOLIOS["fresh"], 1.0)
    assert a.objective == b.objective and a.chosen == b.chosen


def test_budget_and_deadline_skip_members():
    stream = _stream()
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.3)
    r = build_portfolio(stream[1], prev, PORTFOLIOS["full"], construction_budget=0.0)
    assert r.solution is None and len(r.skipped_for_budget) == len(PORTFOLIOS["full"])
    r = build_portfolio(stream[1], prev, PORTFOLIOS["full"], 1.0, deadline=time.monotonic() - 1)
    assert r.solution is None


def test_duplicates_detected():
    stream = _stream()
    prev, _, _ = solve(build_model(stream[0]), time_limit=0.3)
    # for a cancellation/jitter step, hist and elr build identical schedules
    for inst in stream[1:]:
        r = build_portfolio(inst, prev, ("hist", "elr"), 1.0)
        if inst.delta_kind in ("cancellation", "duration_jitter"):
            elr = next(c for c in r.candidates if c.name == "elr")
            assert elr.duplicate_of == "hist"
        prev, _, _ = solve(build_model(inst), time_limit=0.3)
