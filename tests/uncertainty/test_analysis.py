from dataclasses import replace

import pytest

from execution.serialization import fingerprint_result
from tests.execution.helpers import abm_artifact
from uncertainty import (
    RobustnessCriterion, UncertainParameter, UncertaintyPlan,
    analyze_uncertainty, run_uncertainty_analysis,
)


def make_plan(sample_count=16):
    return UncertaintyPlan(
        sample_count=sample_count,
        sampling_seed=20261113,
        parameters=(UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),),
        criteria=(RobustnessCriterion("derived:abm:Person:contributions:sum", ">=", 10.0),),
    )


def test_end_to_end_uncertainty_sensitivity_and_robustness_analysis():
    artifact = abm_artifact()
    plan = make_plan()
    result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=800)

    assert len(result.runs) == plan.sample_count
    assert [run.seed for run in result.runs] == list(range(800, 800 + plan.sample_count))
    assert report.sample_count == plan.sample_count
    assert report.failed_runs == 0
    metric = next(item for item in report.metric_distributions if item.metric_name == "derived:abm:Person:contributions:sum")
    assert metric.sample_size == plan.sample_count
    assert metric.minimum == 0.0
    assert metric.maximum == 10.0
    sensitivity = next(item for item in report.sensitivity if item.metric_name == metric.metric_name)
    assert sensitivity.spearman_rho is not None
    assert sensitivity.spearman_rho > 0.0
    assert sensitivity.rank == 1
    constant_metric = next(item for item in report.sensitivity if item.metric_name == "steps_completed")
    assert constant_metric.spearman_rho is None
    assert report.robustness.evaluated_runs == plan.sample_count
    assert 0 < report.robustness.passing_runs < plan.sample_count
    assert report.robustness.observed_fraction == report.robustness.passing_runs / plan.sample_count
    assert any("not causal" in item for item in report.warnings)


def test_analysis_rejects_an_m9_result_from_a_different_m8_artifact():
    artifact = abm_artifact()
    other_artifact = abm_artifact(probability=0.5)
    plan = make_plan(5)
    other_result, _ = run_uncertainty_analysis(other_artifact, plan, execution_base_seed=3)
    with pytest.raises(ValueError, match="exact M8 artifact"):
        analyze_uncertainty(artifact, plan, other_result)


def test_analysis_rejects_tampered_m9_result():
    artifact = abm_artifact()
    plan = make_plan(5)
    result, _ = run_uncertainty_analysis(artifact, plan, execution_base_seed=3)
    tampered = replace(result, project_title="tampered")
    with pytest.raises(ValueError, match="integrity verification failed"):
        analyze_uncertainty(artifact, plan, tampered)


def test_analysis_rejects_result_that_does_not_match_plan_sample_vectors():
    artifact = abm_artifact()
    plan = make_plan(5)
    result, _ = run_uncertainty_analysis(artifact, plan, execution_base_seed=3)
    changed_run = replace(result.runs[0], parameters={"agents[0].attributes.trust": 0.123})
    changed = replace(result, runs=(changed_run,) + result.runs[1:], result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    with pytest.raises(ValueError, match="parameters.*do not match"):
        analyze_uncertainty(artifact, plan, changed)


def test_failed_samples_are_excluded_and_reported(monkeypatch):
    import execution.runner as runner

    original = runner._execute_once
    calls = {"value": 0}

    def fail_one(artifact, model, model_data, seed):
        calls["value"] += 1
        if calls["value"] == 1:
            raise RuntimeError("controlled failure")
        return original(artifact, model, model_data, seed)

    monkeypatch.setattr(runner, "_execute_once", fail_one)
    artifact = abm_artifact()
    plan = make_plan(6)
    result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=3)
    assert report.failed_runs == 1
    assert report.metric_distributions[0].sample_size == 5
    assert any("1 of 6" in item for item in report.warnings)


def test_robustness_between_and_less_equal_criteria_are_evaluated():
    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=6,
        sampling_seed=18,
        parameters=(UncertainParameter("termination.value", "uniform", 5, 10),),
        criteria=(
            RobustnessCriterion("steps_completed", "<=", 10.0),
            RobustnessCriterion("agents_total", "between", 2.0, 2.0),
        ),
    )
    _result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=20)
    checks = {item.metric_name: item for item in report.robustness.criteria}
    assert checks["steps_completed"].passing_runs == 6
    assert checks["agents_total"].passing_runs == 6
    assert report.robustness.passing_runs == 6
