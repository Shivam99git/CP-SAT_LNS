"""Counterexamples C1, C6 and C8 of docs/cobar/03_certificate_theory.md, as
executable checks. (C3-C5 and C7 are covered in test_certificates.py and
test_neighborhood.py.)"""

import sys
from pathlib import Path

from phase0.cobar_certificates import certificate, global_certificate
from phase0.cobar_neighborhood import min_release_cut, obstruction, release_obstructions
from phase0.schedule_validator import check_schedule
from phase0.streams import Instance, Job, Operation, Outage

sys.path.insert(0, str(Path(__file__).parent))
from test_certificates import cpsat_optimum, independent_kept_arcs  # noqa: E402


def test_C1_observed_critical_path_with_idle_time_is_not_an_obstruction():
    jobs = (Job("a", (Operation("a0", 0, 2),)), Job("b", (Operation("b0", 0, 2),)))
    inst = Instance(index=1, num_machines=1, jobs=jobs)
    S = {"a0": 0, "b0": 5}
    cert = certificate(inst, S, set())
    assert check_schedule(inst, S) == 7 and cert.L_path == 4 and not cert.decisive
    assert cpsat_optimum(inst, independent_kept_arcs(inst, S, set(), set())) == 4


def test_C6_with_outages_one_cut_need_not_remove_the_obstruction():
    jobs = (Job("j1", (Operation("x", 0, 6),)),
            Job("j2", (Operation("u", 2, 3), Operation("v", 0, 4), Operation("w", 1, 3))))
    inst = Instance(index=1, num_machines=3, jobs=jobs, outages=(Outage(1, 7, 10),))
    S = {"x": 0, "u": 0, "v": 6, "w": 10}
    cert = certificate(inst, S, set())
    assert cert.U == cert.L == 13 and cert.path == ["x", "v", "w"]
    cut, _ = min_release_cut(obstruction(inst, S, set(), set(), cert.U))
    assert cut == {("x", "v")}
    assert certificate(inst, S, set(), cut).decisive          # w is now held by the outage
    assert release_obstructions(inst, S, set()).status == "unreleasable"
    assert cpsat_optimum(inst, independent_kept_arcs(inst, S, set(), cut)) == 13


def test_C8_local_certificate_says_nothing_about_the_unrestricted_problem():
    jobs = (Job("a", (Operation("a0", 0, 3), Operation("a1", 1, 1))),
            Job("b", (Operation("b0", 0, 1), Operation("b1", 1, 3))))
    inst = Instance(index=1, num_machines=2, jobs=jobs)
    S = {"a0": 0, "a1": 3, "b0": 3, "b1": 4}
    assert certificate(inst, S, set()).decisive and check_schedule(inst, S) == 7
    assert cpsat_optimum(inst, []) == 5
    assert not global_certificate(inst, S).decisive
