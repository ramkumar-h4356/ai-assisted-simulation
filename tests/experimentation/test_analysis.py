from dataclasses import replace

import pytest

from execution import ExperimentConfig, execute_artifact
from experimentation import GridFactor, analyze_results, run_parameter_sweep
from tests.execution.helpers import abm_artifact


def test_parameter_sweep_generates_runs_and_baseline_deltas():
    artifact = abm_artifact()
    result, report = run_parameter_sweep(
        artifact,
        (GridFactor("termination.value", (2, 4)),),
        runs=2,
        base_seed=500,
    )

    assert len(result.runs) == 6
    assert report.baseline_parameter_set == "baseline"
    variants = {item.parameter_set: item for item in report.variants}
    assert variants["baseline"].metrics[0].metric_name == "agents_in_state:active" or variants["baseline"].metrics[0].metric_name == "agents_total"
    assert variants["baseline"].metrics[1].sample_size == 2
    factor = report.factors[0]
    level_by_value = {item.value: item for item in factor.levels}
    assert factor.baseline_value == 10
    steps_delta = next(item for item in level_by_value[2].deltas_vs_baseline if item.metric_name == "steps_completed")
    assert steps_delta.absolute_change == -8.0
    assert steps_delta.percent_change == -80.0
    assert any("not paired" in warning for warning in report.warnings)


def test_analysis_rejects_results_from_different_compilation_artifacts():
    first_artifact = abm_artifact()
    first = execute_artifact(first_artifact, ExperimentConfig(runs=1, base_seed=1))
    second_artifact = abm_artifact(probability=0.5)
    second = execute_artifact(second_artifact, ExperimentConfig(runs=1, base_seed=2))
    with pytest.raises(ValueError, match="same exact M8 artifact"):
        analyze_results((first, second))


def test_analysis_rejects_duplicate_experiment_result():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=1))
    with pytest.raises(ValueError, match="Duplicate M9 experiment IDs"):
        analyze_results((result, result))


def test_analysis_rejects_unknown_baseline_name():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=1))
    with pytest.raises(ValueError, match="was not found"):
        analyze_results((result,), baseline_parameter_set="missing")


def test_analysis_reports_failed_runs_and_summarizes_successes(monkeypatch):
    import execution.runner as runner

    calls = {"count": 0}

    def sometimes_fails(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated run failure")
        return (), {"history": [], "rule_evaluations": [], "final_state_counts": {}}

    monkeypatch.setattr(runner, "_execute_once", sometimes_fails)
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=10))
    report = analyze_results((result,))

    assert report.variants[0].failed_runs == 1
    assert report.variants[0].successful_runs == 1
    assert any("failed run" in warning for warning in report.warnings)


def test_analysis_rejects_inconsistent_parameters_for_same_variant():
    artifact = abm_artifact()
    result = execute_artifact(
        artifact,
        ExperimentConfig(runs=2, base_seed=30),
    )
    first, second = result.runs
    second = replace(second, parameters={"different": 1})
    altered = replace(result, runs=(first, second), result_fingerprint="pending")
    from execution.serialization import fingerprint_result
    altered = replace(altered, result_fingerprint=fingerprint_result(altered))
    with pytest.raises(ValueError, match="conflicting parameter values"):
        analyze_results((altered,))


def test_analysis_aggregates_multiple_verified_results_from_same_artifact():
    artifact = abm_artifact()
    first = execute_artifact(artifact, ExperimentConfig(runs=2, base_seed=100))
    second = execute_artifact(artifact, ExperimentConfig(runs=3, base_seed=200))
    report = analyze_results((first, second))
    baseline = report.variants[0]
    assert baseline.total_runs == 5
    assert baseline.successful_runs == 5
    assert next(item for item in baseline.metrics if item.metric_name == "steps_completed").sample_size == 5


def test_analysis_warns_when_baseline_has_no_value_for_varied_factor():
    from execution import ParameterOverride, ParameterSet

    artifact = abm_artifact()
    baseline = execute_artifact(artifact, ExperimentConfig(runs=1, base_seed=10))
    variant = execute_artifact(
        artifact,
        ExperimentConfig(
            runs=1,
            base_seed=11,
            parameter_sets=(ParameterSet("short-horizon", (ParameterOverride("termination.value", 3),)),),
        ),
    )
    report = analyze_results((baseline, variant))
    factor = report.factors[0]
    assert factor.baseline_value is None
    assert any("No baseline value" in item for item in report.warnings)
    assert not next(level for level in factor.levels if level.value == 3).deltas_vs_baseline


def test_analysis_rejects_metric_contract_changes_across_variants():
    from dataclasses import replace
    from execution import MetricRecord
    from execution.serialization import fingerprint_result

    artifact = abm_artifact()
    first = execute_artifact(artifact, ExperimentConfig(runs=1, base_seed=10))
    second = execute_artifact(artifact, ExperimentConfig(runs=1, base_seed=11))
    first_run = replace(first.runs[0], metrics=(MetricRecord("shared_metric", 3, "steps"),))
    second_run = replace(second.runs[0], metrics=(MetricRecord("shared_metric", 3, "agents"),))
    first = replace(first, runs=(first_run,), result_fingerprint="pending")
    first = replace(first, result_fingerprint=fingerprint_result(first))
    second = replace(second, runs=(second_run,), result_fingerprint="pending")
    second = replace(second, result_fingerprint=fingerprint_result(second))
    with pytest.raises(ValueError, match="inconsistent units or value types"):
        analyze_results((first, second))


def test_analysis_summarizes_categorical_metrics_as_counts():
    from dataclasses import replace
    from execution import MetricRecord
    from execution.serialization import fingerprint_result

    artifact = abm_artifact()
    result = execute_artifact(artifact, ExperimentConfig(runs=2, base_seed=10))
    runs = tuple(
        replace(run, metrics=(MetricRecord("outcome", "stable" if index == 0 else "changed"),))
        for index, run in enumerate(result.runs)
    )
    result = replace(result, runs=runs, result_fingerprint="pending")
    result = replace(result, result_fingerprint=fingerprint_result(result))
    report = analyze_results((result,))
    metric = next(item for item in report.variants[0].metrics if item.metric_name == "outcome")
    assert metric.value_type == "categorical"
    assert {item.value: item.count for item in metric.categories} == {"changed": 1, "stable": 1}


def test_analysis_derives_final_agent_attribute_metrics_from_abm_trace():
    artifact = abm_artifact()
    factors = (GridFactor("agents[0].attributes.trust", (0.2, 0.8)),)
    result, report = run_parameter_sweep(artifact, factors, runs=1, base_seed=700)
    variants = {item.parameter_set: item for item in report.variants}
    baseline = variants["baseline"]
    changed = next(item for name, item in variants.items() if name != "baseline")
    metric_name = "derived:abm:Person:contributions:sum"
    baseline_value = next(item for item in baseline.metrics if item.metric_name == metric_name).mean
    changed_value = next(item for item in changed.metrics if item.metric_name == metric_name).mean
    assert baseline_value > changed_value


def test_analysis_derives_des_entity_and_resource_metrics_from_trace():
    from dataclasses import replace
    from execution.serialization import fingerprint_result

    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=80))
    native_trace = {
        "events": [],
        "entities": [
            {"entity_id": "a", "waiting_time": 2.0, "service_time": 4.0, "time_in_system": 6.0},
            {"entity_id": "b", "waiting_time": 4.0, "service_time": 6.0, "time_in_system": 10.0},
        ],
        "resources": [
            {"resource_name": "machine", "completed_services": 2,
             "average_waiting_time": 3.0, "average_service_time": 5.0, "utilization": 80.0}
        ],
    }
    run = replace(result.runs[0], trace=native_trace)
    result = replace(result, runs=(run,), result_fingerprint="pending")
    result = replace(result, result_fingerprint=fingerprint_result(result))
    report = analyze_results((result,))
    metrics = {item.metric_name: item.mean for item in report.variants[0].metrics}
    assert metrics["derived:des:entities:mean_waiting_time"] == 3.0
    assert metrics["derived:des:entities:mean_service_time"] == 5.0
    assert metrics["derived:des:entities:mean_time_in_system"] == 8.0
    assert metrics["derived:des:resource:machine:utilization"] == 80.0
