from __future__ import annotations

import pytest

from validation import InvariantSpec, ValidationPlan
from validation.engine import _evaluate_invariant


def test_plan_rejects_parent_traversal_and_invalid_execution_settings():
    with pytest.raises(ValueError, match="relative path"):
        ValidationPlan(1, "Unsafe", "../outside/artifact.json")
    with pytest.raises(ValueError, match="between 1 and 20"):
        ValidationPlan(1, "Too many", "artifact.json", execution_runs=21)
    with pytest.raises(ValueError, match="Provide execution_result_path"):
        ValidationPlan(1, "No execution", "artifact.json", execute_if_missing=False)


def test_invariant_conserved_sum_checks_nested_trace_series():
    spec = InvariantSpec(
        "population", "conserved_sum", "time_series[].stocks",
        fields=("susceptible", "infected", "recovered"), expected_value=1000.0, tolerance=1e-8,
    )
    trace = {"time_series": [
        {"stocks": {"susceptible": 990.0, "infected": 10.0, "recovered": 0.0}},
        {"stocks": {"susceptible": 800.0, "infected": 150.0, "recovered": 50.0}},
    ]}
    check = _evaluate_invariant(spec, trace, 1)
    assert check.status == "passed"
    assert check.details["sample_count"] == 2


def test_invariant_detects_conservation_violation():
    spec = InvariantSpec(
        "population", "conserved_sum", "time_series[].stocks",
        fields=("susceptible", "infected", "recovered"), expected_value=1000.0, tolerance=1e-8,
    )
    trace = {"time_series": [{"stocks": {"susceptible": 900.0, "infected": 50.0, "recovered": 40.0}}]}
    check = _evaluate_invariant(spec, trace, 1)
    assert check.status == "failed"
    assert check.details["maximum_absolute_deviation"] == 10.0


def test_invariants_support_nonnegative_bounds_and_monotonic_series():
    trace = {"series": [0.0, 0.5, 1.0, 1.5]}
    assert _evaluate_invariant(InvariantSpec("nn", "non_negative", "series"), trace, 1).status == "passed"
    assert _evaluate_invariant(InvariantSpec("bounds", "bounds", "series", minimum=0, maximum=2), trace, 1).status == "passed"
    assert _evaluate_invariant(InvariantSpec("mono", "monotonic", "series", direction="increasing"), trace, 1).status == "passed"
    assert _evaluate_invariant(InvariantSpec("bad", "monotonic", "series", direction="decreasing"), trace, 1).status == "failed"


def test_invariant_missing_path_fails_closed():
    spec = InvariantSpec("missing", "non_negative", "missing[].value")
    check = _evaluate_invariant(spec, {"other": []}, 1)
    assert check.status == "failed"
    assert "missing key" in check.message
