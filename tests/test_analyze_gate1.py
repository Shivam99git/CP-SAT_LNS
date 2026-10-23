"""Hand-computed checks of the primal-integral integration used by Gate 1."""
import pytest

from phase0.analyze_gate1 import cluster_bootstrap, holm, integrate_gap, sign_test


def test_no_incumbent_is_gap_one():
    assert integrate_gap([], 100, 8, 0, 8) == 1.0


def test_single_event():
    # gap 1 on [0,2), then (110-100)/100 = 0.1 on [2,8): (2*1 + 6*0.1)/8
    assert integrate_gap([(2.0, 110, "s")], 100, 8, 0, 8) == pytest.approx((2 + 0.6) / 8)


def test_windows_partition_the_full_integral():
    ev = [(0.5, 150, "s"), (3.0, 105, "s"), (6.0, 100, "s")]
    full = integrate_gap(ev, 100, 8, 0, 8)
    early, late = integrate_gap(ev, 100, 8, 0, 1), integrate_gap(ev, 100, 8, 1, 8)
    assert full == pytest.approx((early * 1 + late * 7) / 8)
    # early: [0,.5) gap 1, [.5,1) gap .5
    assert early == pytest.approx(0.5 * 1 + 0.5 * 0.5)


def test_cap_and_events_after_deadline():
    ev = [(1.0, 400, "s"), (9.0, 100, "s")]  # second event after B=8 must not count
    assert integrate_gap(ev, 100, 8, 0, 8) == pytest.approx((1 + 7 * 3.0) / 8)
    assert integrate_gap(ev, 100, 8, 0, 8, cap=True) == pytest.approx(1.0)


def test_unsorted_events_are_sorted():
    a = integrate_gap([(3.0, 105, "s"), (1.0, 120, "s")], 100, 8, 0, 8)
    b = integrate_gap([(1.0, 120, "s"), (3.0, 105, "s")], 100, 8, 0, 8)
    assert a == b


def test_stats_helpers():
    assert sign_test(0, 0) == 1.0
    assert sign_test(10, 0) == pytest.approx(2 / 2 ** 10)
    h = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h == {"a": 0.03, "c": 0.06, "b": 0.06}
    import numpy as np
    lo, hi = cluster_bootstrap(np.array([1.0, 1.0, 1.0]))
    assert lo == hi == 1.0
