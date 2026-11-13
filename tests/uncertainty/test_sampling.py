from dataclasses import replace

import pytest

from uncertainty import (
    RobustnessCriterion, UncertainParameter, UncertaintyPlan,
    generate_parameter_samples,
)
from tests.execution.helpers import abm_artifact


def test_monte_carlo_samples_are_reproducible_bounded_and_typed():
    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=12,
        sampling_seed=2026,
        parameters=(
            UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),
            UncertainParameter("termination.value", "triangular", 4, 12, 8),
        ),
    )
    first = generate_parameter_samples(artifact, plan)
    second = generate_parameter_samples(artifact, plan)
    assert first == second
    assert len(first) == 12
    trust = [item.overrides[0].value for item in first]
    steps = [item.overrides[1].value for item in first]
    assert all(isinstance(value, float) and 0.0 <= value <= 1.0 for value in trust)
    assert all(isinstance(value, int) and 4 <= value <= 12 for value in steps)
    assert [item.name for item in first] == [f"sample_{index:03d}" for index in range(1, 13)]


def test_sampler_rejects_paths_not_explicitly_bound_as_user_parameters():
    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=5,
        sampling_seed=1,
        parameters=(UncertainParameter("agents[0].state", "uniform", 0, 1),),
    )
    with pytest.raises(ValueError, match="not an explicitly bound"):
        generate_parameter_samples(artifact, plan)


def test_sampler_rejects_boolean_target_fields_even_when_artifact_is_refingerprinted():
    from compilation.compiler import fingerprint_artifact, fingerprint_model

    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=5,
        sampling_seed=1,
        parameters=(UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),),
    )
    altered_data = dict(artifact.model_data)
    altered_agents = [dict(item) for item in altered_data["agents"]]
    altered_agents[0]["attributes"] = {"trust": True, "contributions": 0}
    altered_data["agents"] = altered_agents
    altered = replace(
        artifact, model_data=altered_data,
        model_fingerprint=fingerprint_model(artifact.paradigm, altered_data),
        artifact_fingerprint="pending",
    )
    altered = replace(altered, artifact_fingerprint=fingerprint_artifact(altered))
    with pytest.raises(ValueError, match="must refer to a numeric model value"):
        generate_parameter_samples(altered, plan)


def test_uncertainty_contracts_reject_bad_ranges_and_duplicate_paths():
    with pytest.raises(ValueError, match="lower must be less than upper"):
        UncertainParameter("x", "uniform", 2.0, 2.0)
    with pytest.raises(ValueError, match="mode must lie"):
        UncertainParameter("x", "triangular", 0.0, 1.0, 2.0)
    with pytest.raises(ValueError, match="sample_count"):
        UncertaintyPlan(2, 1, (UncertainParameter("x", "uniform", 0.0, 1.0),))
    with pytest.raises(ValueError, match="paths must be unique"):
        UncertaintyPlan(5, 1, (
            UncertainParameter("x", "uniform", 0.0, 1.0),
            UncertainParameter("x", "uniform", 0.0, 2.0),
        ))


def test_robustness_criteria_validate_operator_bounds():
    with pytest.raises(ValueError, match="between criteria require"):
        RobustnessCriterion("metric", "between", 1.0)
    with pytest.raises(ValueError, match="must not exceed"):
        RobustnessCriterion("metric", "between", 5.0, 2.0)
