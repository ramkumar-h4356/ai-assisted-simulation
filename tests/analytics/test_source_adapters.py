from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from analytics import AnalyticsPlan, AnalyticsSource, MetricDefinition, analyze_reports
from optimization.models import (
    CandidateSummary, OptimizationObjective, OptimizationPlan, OptimizationReport,
    SearchParameter,
)
from optimization.serialization import fingerprint_report as m23_fingerprint, save_report as save_m23
from orchestration.models import (
    ExperimentSuitePlan, ExperimentSuiteReport, MetricAggregate, SuiteMember,
    SuiteMemberSummary,
)
from orchestration.serialization import fingerprint_report as m24_fingerprint, save_report as save_m24
from uncertainty.models import (
    MetricDistribution, RobustnessSummary, UncertainParameter, UncertaintyReport,
)
from uncertainty.serialization import fingerprint_report as m11_fingerprint, save_report as save_m11


def _base_metadata():
    return {
        "artifact_id": "artifact-x", "artifact_fingerprint": "a" * 64,
        "project_id": "project-x", "project_title": "Analytics source fixture",
        "revision_id": "revision-x", "revision_version": 1,
        "paradigm": "agent_based", "backend_name": "abm_v1",
    }


def test_m11_uncertainty_report_adapter(tmp_path: Path):
    metadata = _base_metadata()
    pending = UncertaintyReport(
        schema_version=1, report_id="m11-fixture", created_at="2026-11-15T00:00:00+00:00",
        **metadata, experiment_id="m9-m11", experiment_fingerprint="b" * 64,
        sample_count=8, sampling_seed=10,
        parameters=(UncertainParameter("agents[0].attributes.rate", "uniform", 1.0, 2.0),),
        criteria=(), metric_distributions=(MetricDistribution(
            "average_waiting_time", "time units", 8, 4.0, 1.0, 4.0, 2.5, 5.5, 2.0, 6.0,
        ),), sensitivity=(),
        robustness=RobustnessSummary(8, 8, 1.0, ()), failed_runs=0,
        warnings=(), report_fingerprint="pending",
    )
    report = replace(pending, report_fingerprint=m11_fingerprint(pending))
    save_m11(report, tmp_path / "m11.json")
    plan = AnalyticsPlan(
        schema_version=1, analysis_name="M11 source import",
        sources=(AnalyticsSource("uncertainty", "m11", "m11.json"),),
        metrics=(MetricDefinition("average_waiting_time", "time units", "Mean time entities wait before service.", "minimize"),),
    )
    analytics_report = analyze_reports(plan, source_root=tmp_path)
    assert len(analytics_report.groups) == 1
    group = analytics_report.groups[0]
    assert group.group_label == "uncertainty sample"
    assert group.sample_size == 8
    assert group.confidence_lower < group.mean < group.confidence_upper
    assert any("M11 uncertainty samples can combine" in warning for warning in analytics_report.warnings)


def test_m23_optimization_report_adapter(tmp_path: Path):
    metadata = _base_metadata()
    optimization_plan = OptimizationPlan(
        search_parameters=(SearchParameter("agents[0].attributes.rate", 0.0, 1.0),),
        objective=OptimizationObjective("service_quality", "maximize"),
        candidate_count=2, replications=4, search_seed=13, include_baseline=False,
    )
    candidates = (
        CandidateSummary("candidate_1", {"rate": 0.2}, 4, 4, 0, 0.7, 0.1, 4, True, "complete", ()),
        CandidateSummary("candidate_2", {"rate": 0.8}, 4, 4, 0, 0.9, 0.12, 4, True, "complete", ()),
    )
    pending = OptimizationReport(
        schema_version=1, optimization_id="m23-fixture", created_at="2026-11-15T00:00:00+00:00",
        **metadata, algorithm="random_search_v1", plan=optimization_plan,
        experiment_id="m9-opt", experiment_fingerprint="c" * 64,
        candidates=candidates, baseline_parameter_set=None, best_parameter_set="candidate_2",
        objective_improvement=None, warnings=(), report_fingerprint="pending",
    )
    report = replace(pending, report_fingerprint=m23_fingerprint(pending))
    save_m23(report, tmp_path / "m23.json")
    plan = AnalyticsPlan(
        schema_version=1, analysis_name="M23 source import",
        sources=(AnalyticsSource("optimization", "m23", "m23.json"),),
        metrics=(MetricDefinition("service_quality", None, "Mean simulated service quality outcome.", "maximize"),),
    )
    analytics_report = analyze_reports(plan, source_root=tmp_path)
    assert len(analytics_report.groups) == 2
    assert {item.mean for item in analytics_report.groups} == {0.7, 0.9}
    assert len(analytics_report.comparisons) == 1


def test_m24_suite_report_adapter(tmp_path: Path):
    suite_plan = ExperimentSuitePlan(
        schema_version=1, suite_name="M24 suite fixture",
        members=(
            SuiteMember("one", "Model One", "artifacts/one.json", runs=6),
            SuiteMember("two", "Model Two", "artifacts/two.json", runs=6),
        ), comparison=None,
    )
    members = (
        SuiteMemberSummary(
            member_id="one", label="Model One", artifact_path="artifacts/one.json",
            artifact_id="artifact-one", artifact_fingerprint="d" * 64,
            project_id="project-one", project_title="One", revision_id="revision-one", revision_version=1,
            paradigm="mathematical", backend_name="math_v1", experiment_id="exp-one",
            experiment_fingerprint="e" * 64, result_file="one.json", status="completed",
            total_runs=6, successful_runs=6, failed_runs=0,
            metrics=(MetricAggregate("one", "Model One", "default", "average_waiting_time", "time units", "numeric", 6, 10.0, 1.0, ()),),
        ),
        SuiteMemberSummary(
            member_id="two", label="Model Two", artifact_path="artifacts/two.json",
            artifact_id="artifact-two", artifact_fingerprint="f" * 64,
            project_id="project-two", project_title="Two", revision_id="revision-two", revision_version=1,
            paradigm="system_dynamics", backend_name="system_dynamics_v1", experiment_id="exp-two",
            experiment_fingerprint="1" * 64, result_file="two.json", status="completed",
            total_runs=6, successful_runs=6, failed_runs=0,
            metrics=(MetricAggregate("two", "Model Two", "default", "average_waiting_time", "time units", "numeric", 6, 8.0, 0.8, ()),),
        ),
    )
    pending = ExperimentSuiteReport(
        schema_version=1, suite_id="m24-fixture", created_at="2026-11-15T00:00:00+00:00",
        suite_name=suite_plan.suite_name, plan=suite_plan, status="completed", members=members,
        ranking=(), warnings=(), report_fingerprint="pending",
    )
    report = replace(pending, report_fingerprint=m24_fingerprint(pending))
    save_m24(report, tmp_path / "m24.json")
    plan = AnalyticsPlan(
        schema_version=1, analysis_name="M24 source import",
        sources=(AnalyticsSource("suite", "m24", "m24.json"),),
        metrics=(MetricDefinition("average_waiting_time", "time units", "Mean time entities wait before service.", "minimize"),),
    )
    analytics_report = analyze_reports(plan, source_root=tmp_path)
    assert len(analytics_report.groups) == 2
    assert len(analytics_report.comparisons) == 1
    assert analytics_report.sources[0].artifact_ids == ("artifact-one", "artifact-two")
    assert any("different simulation paradigms" in warning for warning in analytics_report.warnings)
