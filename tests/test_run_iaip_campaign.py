"""Tests for the stream options of phase0/run_iaip_campaign.py."""

import json
from pathlib import Path

from phase0.impact_aware_reoptimization import IAIPConfig, run_iaip
from phase0.run_gate1 import StreamSpec, instance_to_dict
from phase0.run_iaip_campaign import CampaignSpec, parse_iaip
from phase0.schedule_validator import check_schedule

TA = Path("tests/fixtures/benchmarks_real/taillard/ta01.txt")


def _dump(stream):
    return json.dumps([instance_to_dict(i) for i in stream], sort_keys=True)


def test_default_spec_reproduces_stream_spec_exactly():
    for m, s in ((15, 501), (20, 520), (10, 101)):
        a, b = StreamSpec(m, m, s, 10), CampaignSpec(m, m, s, 10)
        assert a.name == b.name
        assert _dump(a.build()) == _dump(b.build())


def test_default_spec_matches_saved_confirmatory_instances():
    p = Path("results/research_extension/confirmatory/instances/15x15_s501.json")
    if p.exists():
        saved = json.loads(p.read_text())
        assert json.loads(_dump(CampaignSpec(15, 15, 501, 10).build())) == json.loads(json.dumps(saved, sort_keys=True))


def test_mixes_and_severity_change_only_what_they_say():
    arr = CampaignSpec(15, 15, 601, 10, mix="arrival").build()
    out = CampaignSpec(15, 15, 601, 10, mix="outage").build()
    assert {i.delta_kind for i in arr[1:]} == {"arrival"}
    assert {i.delta_kind for i in out[1:]} == {"outage"}
    assert CampaignSpec(15, 15, 601, 10, mix="arrival").name == "15x15_s601_arrival"
    hi = CampaignSpec(15, 15, 601, 10, severity="high")
    assert hi.name == "15x15_s601_high" and all(i.severity == "high" for i in hi.build())


def test_benchmark_base_is_the_published_instance():
    from phase0.benchmark_loaders import load_benchmark_file
    base = load_benchmark_file(TA)
    spec = CampaignSpec(base.num_machines, len(base.jobs), 7, 4, base_path=str(TA))
    stream = spec.build()
    assert spec.name == "ta01_s7"
    assert [o.duration for j in stream[0].jobs for o in j.ops] == [o.duration for j in base.jobs for o in j.ops]
    for inst in stream[1:]:
        for j in inst.jobs:  # arriving jobs are full-length, durations in the base's range
            assert len(j.ops) == base.num_machines and all(1 <= o.duration <= 99 for o in j.ops)


def test_integrated_method_runs_valid_on_benchmark_stream():
    from phase0.benchmark_loaders import load_benchmark_file
    base = load_benchmark_file(TA)
    stream = CampaignSpec(base.num_machines, len(base.jobs), 3, 3, base_path=str(TA)).build()
    cfg = parse_iaip("iaip|portfolio=full|alpha=0.6|neighbourhood=N5|global_mode=hinted")
    assert isinstance(cfg, IAIPConfig)
    prev = prev_inst = None
    for inst in stream:
        res, _ = run_iaip(inst, prev, prev_inst, 0.6, cfg, 1, 0, "iaip_sr")
        assert res.validated and check_schedule(inst, res.solution) == res.objective
        prev, prev_inst = res.solution, inst
