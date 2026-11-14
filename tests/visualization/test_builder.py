from dataclasses import replace

import pytest

from execution import ExperimentConfig, execute_artifact
from execution.serialization import fingerprint_result
from experimentation import GridFactor, run_parameter_sweep
from tests.execution.helpers import abm_artifact
from uncertainty import UncertainParameter, UncertaintyPlan, run_uncertainty_analysis
from visualization import build_visualization_bundle, render_html


def test_builds_abm_dashboard_with_metric_series_and_aggregated_history():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=3, base_seed=120))
    bundle = build_visualization_bundle(result)

    assert bundle.paradigm == "agent_based"
    assert bundle.experiment_id == result.experiment_id
    assert len(bundle.data["runs"]) == 3
    assert len(bundle.data["trace_views"]) == 3
    first_view = bundle.data["trace_views"][0]
    assert first_view["kind"] == "abm"
    assert first_view["steps"]
    assert "active" in first_view["steps"][-1]["state_counts"] or first_view["steps"][-1]["state_counts"]
    assert any(item["name"].startswith("derived:abm:") for item in bundle.data["metric_series"])


def test_builds_dashboard_with_matching_m10_report():
    artifact = abm_artifact()
    result, report = run_parameter_sweep(
        artifact, (GridFactor("termination.value", (5, 8)),),
        runs=1, base_seed=40,
    )
    bundle = build_visualization_bundle(result, analysis_report=report)
    assert bundle.data["m10"]["analysis_id"] == report.analysis_id
    assert bundle.data["m10"]["variants"]


def test_builds_dashboard_with_matching_m11_report():
    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=5,
        sampling_seed=55,
        parameters=(UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),),
    )
    result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=70)
    bundle = build_visualization_bundle(result, uncertainty_report=report)
    assert bundle.data["m11"]["report_id"] == report.report_id
    assert bundle.data["m11"]["distributions"]
    assert bundle.data["m11"]["sensitivity"]


def test_rejects_mismatched_m10_or_m11_provenance():
    artifact = abm_artifact()
    result, m10 = run_parameter_sweep(
        artifact, (GridFactor("termination.value", (4, 6)),), runs=1, base_seed=20,
    )
    other_artifact = abm_artifact(probability=0.3)
    _other_result, m11 = run_uncertainty_analysis(
        other_artifact,
        UncertaintyPlan(3, 12, (UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),)),
        execution_base_seed=90,
    )
    with pytest.raises(ValueError, match="does not match"):
        build_visualization_bundle(result, uncertainty_report=m11)
    # An M10 report that omits this exact M9 result must not be attached.
    other_result = execute_artifact(artifact, ExperimentConfig(runs=1, base_seed=101))
    from experimentation import analyze_results
    unrelated_report = analyze_results((other_result,))
    with pytest.raises(ValueError, match="does not include"):
        build_visualization_bundle(result, analysis_report=unrelated_report)
    assert m10.analysis_id


def test_rejects_tampered_execution_result():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=3))
    tampered = replace(result, project_title="edited without re-fingerprinting")
    with pytest.raises(ValueError, match="fingerprint verification failed"):
        build_visualization_bundle(tampered)


def test_des_trace_adapter_downsamples_and_preserves_resource_records():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=3))
    trace = {
        "events": [
            {"time": float(i), "entity_id": f"job-{i}", "event_type": "arrived" if i % 2 == 0 else "service_completed", "resource_name": "machine"}
            for i in range(40)
        ],
        "entities": [
            {"entity_id": f"job-{i}", "arrival_time": float(i), "completion_time": float(i + 5), "waiting_time": 1.0, "service_time": 4.0, "time_in_system": 5.0}
            for i in range(20)
        ],
        "resources": [{"resource_name": "machine", "completed_services": 20, "average_waiting_time": 1.0, "average_service_time": 4.0, "utilization": 80.0}],
    }
    run = replace(result.runs[0], trace=trace)
    changed = replace(result, paradigm="discrete_event", backend_name="DES V1 / SimPy backend", runs=(run,), result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    bundle = build_visualization_bundle(changed, point_limit=10)
    view = bundle.data["trace_views"][0]
    assert view["kind"] == "des"
    assert len(view["events"]) <= 7
    assert len(view["entities"]) <= 5
    assert view["resources"][0]["utilization"] == 80.0
    assert any("downsampled" in warning for warning in bundle.warnings)


def test_html_is_standalone_and_escapes_script_terminators():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=8))
    changed = replace(result, project_title="A </script><script>alert(1)</script> label", result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    bundle = build_visualization_bundle(changed)
    html = render_html(bundle)
    assert "<script src=" not in html
    assert "https://" not in html
    assert "\\u003c/script\\u003e" in html


def test_combines_m10_and_m11_when_both_match_the_same_m9_result():
    from experimentation import analyze_results

    artifact = abm_artifact()
    plan = UncertaintyPlan(
        sample_count=5,
        sampling_seed=87,
        parameters=(UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),),
    )
    result, m11 = run_uncertainty_analysis(artifact, plan, execution_base_seed=110)
    m10 = analyze_results((result,))
    bundle = build_visualization_bundle(result, analysis_report=m10, uncertainty_report=m11)
    assert bundle.data["m10"]["analysis_id"] == m10.analysis_id
    assert bundle.data["m11"]["report_id"] == m11.report_id
