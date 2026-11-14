from dataclasses import replace

import pytest

from optimization import (
    MetricConstraint, OptimizationObjective, OptimizationPlan,
    SearchParameter, generate_candidates,
)
from tests.execution.helpers import abm_artifact


def _plan(**overrides):
    values = {
        "search_parameters": (
            SearchParameter("agents[0].attributes.trust", 0.0, 1.0),
            SearchParameter("termination.value", 1, 10),
        ),
        "objective": OptimizationObjective("derived:abm:Person:contributions:sum", "maximize"),
        "candidate_count": 5,
        "replications": 2,
        "search_seed": 42,
        "include_baseline": True,
        "constraints": (MetricConstraint("derived:abm:Person:contributions:sum", ">=", 0.0),),
    }
    values.update(overrides)
    return OptimizationPlan(**values)


def test_search_candidate_generation_is_seeded_unique_and_includes_baseline():
    artifact = abm_artifact()
    plan = _plan()
    first = generate_candidates(artifact, plan)
    second = generate_candidates(artifact, plan)
    assert first == second
    assert len(first) == 6
    assert first[0].name == "baseline"
    assert first[0].overrides[0].value == 0.8
    assert len({tuple(item.value for item in candidate.overrides) for candidate in first}) == 6
    assert all(candidate.name.startswith(("baseline", "candidate_")) for candidate in first)


def test_search_can_omit_baseline_and_respects_integer_and_float_bounds():
    artifact = abm_artifact()
    plan = _plan(candidate_count=4, replications=1, include_baseline=False, constraints=())
    candidates = generate_candidates(artifact, plan)
    assert len(candidates) == 4
    for candidate in candidates:
        values = {item.target_path: item.value for item in candidate.overrides}
        assert 0.0 <= values["agents[0].attributes.trust"] <= 1.0
        assert isinstance(values["agents[0].attributes.trust"], float)
        assert 1 <= values["termination.value"] <= 10
        assert isinstance(values["termination.value"], int)


def test_search_rejects_unbound_paths_type_mismatches_and_bad_ranges():
    artifact = abm_artifact()
    with pytest.raises(ValueError, match="not an explicitly bound"):
        generate_candidates(artifact, _plan(search_parameters=(SearchParameter("agents[0].state", 1, 5),)))
    with pytest.raises(ValueError, match="expects float bounds"):
        generate_candidates(artifact, _plan(search_parameters=(SearchParameter("agents[0].attributes.trust", 0, 1),)))
    with pytest.raises(ValueError, match="outside the configured search bounds"):
        generate_candidates(artifact, _plan(search_parameters=(SearchParameter("agents[0].attributes.trust", 0.0, 0.5),)))


def test_search_rejects_overlapping_paths_tampered_artifacts_and_tiny_integer_space():
    artifact = abm_artifact()
    with pytest.raises(ValueError, match="overlap"):
        generate_candidates(artifact, _plan(search_parameters=(
            SearchParameter("agents[0]", 1, 2),
            SearchParameter("agents[0].attributes.trust", 0.0, 1.0),
        )))
    changed = replace(artifact, project_title="changed")
    with pytest.raises(ValueError, match="integrity verification failed"):
        generate_candidates(changed, _plan())
    with pytest.raises(ValueError, match="only 1 non-baseline integer combinations"):
        generate_candidates(artifact, _plan(
            search_parameters=(SearchParameter("termination.value", 9, 10),),
            candidate_count=2, replications=1,
        ))


def test_plan_enforces_m9_execution_budget():
    with pytest.raises(ValueError, match="must not exceed 100"):
        _plan(candidate_count=50, replications=2)


def test_objective_and_constraint_contracts_reject_invalid_values():
    with pytest.raises(ValueError, match="direction"):
        OptimizationObjective("metric", "sideways")
    with pytest.raises(ValueError, match="upper_threshold"):
        MetricConstraint("metric", "between", 2.0)
    with pytest.raises(ValueError, match="lower threshold"):
        MetricConstraint("metric", "between", 4.0, 3.0)
    with pytest.raises(ValueError, match="less than upper"):
        SearchParameter("x", 1.0, 1.0)
