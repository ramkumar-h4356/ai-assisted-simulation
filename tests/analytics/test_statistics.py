from __future__ import annotations

import pytest

from analytics.statistics import (
    effect_magnitude, holm_adjust, mean_confidence_interval,
    student_t_critical, student_t_cdf, welch_comparison,
)


def test_student_t_quantile_matches_known_value():
    assert student_t_critical(0.975, 9) == pytest.approx(2.262157, abs=1e-5)
    assert student_t_cdf(0.0, 9) == 0.5


def test_group_mean_confidence_interval_uses_t_distribution():
    interval = mean_confidence_interval(10.0, 2.0, 10, 0.95)
    assert interval == pytest.approx((8.569, 11.431), abs=0.002)


def test_welch_detects_large_difference_and_reports_effect_size():
    result = welch_comparison(10.0, 1.0, 20, 13.0, 1.2, 20, 0.95)
    assert result is not None
    assert result["p_value"] < 0.001
    assert result["confidence_lower"] > 0
    assert result["hedges_g"] > 2
    assert effect_magnitude(result["hedges_g"]) == "large"


def test_welch_refuses_non_estimable_constant_groups():
    assert welch_comparison(2.0, 0.0, 10, 2.0, 0.0, 10, 0.95) is None


def test_holm_adjustment_is_monotonic_and_restores_original_order():
    adjusted = holm_adjust([0.04, 0.001, 0.03])
    assert adjusted == pytest.approx([0.06, 0.003, 0.06])
    assert adjusted[1] <= adjusted[0] <= 1
