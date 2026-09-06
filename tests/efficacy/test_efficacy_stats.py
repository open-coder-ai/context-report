"""Intervals behave: they bracket the estimate, shrink with evidence, and admit ignorance at n=0."""

import pytest

from context_report.efficacy.stats import newcombe_diff, trials_for_halfwidth, wilson


def test_no_observations_means_no_knowledge():
    assert wilson(0, 0) == (0.0, 1.0)
    assert newcombe_diff(0, 0, 0, 0) == (-1.0, 1.0)


def test_interval_brackets_the_point_estimate():
    lo, hi = wilson(7, 10)
    assert lo < 0.7 < hi


def test_interval_shrinks_as_evidence_grows():
    narrow = wilson(70, 100)
    wide = wilson(7, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_bounds_stay_in_range_at_the_extremes():
    lo, hi = wilson(0, 5)
    assert lo == 0.0
    assert 0.0 < hi < 1.0
    lo, hi = wilson(5, 5)
    assert hi == 1.0
    assert 0.0 < lo < 1.0


def test_small_samples_cannot_confirm_a_perfect_split():
    lo, _ = newcombe_diff(4, 4, 0, 4)
    assert lo < 0.5, "4 runs per arm must not prove a large lift"
    lo_big, _ = newcombe_diff(40, 40, 0, 40)
    assert lo_big > 0.8


def test_diff_interval_contains_zero_when_arms_agree():
    lo, hi = newcombe_diff(8, 10, 8, 10)
    assert lo < 0 < hi


def test_trials_for_halfwidth_is_monotonic():
    assert trials_for_halfwidth(0.1) > trials_for_halfwidth(0.2)
    with pytest.raises(ValueError):
        trials_for_halfwidth(0)
