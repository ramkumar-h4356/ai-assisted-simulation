from __future__ import annotations

from pathlib import Path

import pytest

from analytics import AnalyticsPlan, AnalyticsSource, MetricDefinition, analyze_reports
from analytics.serialization import export_summary_csv, load_report, save_report
from experimentation.models import AnalysisReport, MetricSummary, VariantSummary
from experimentation.serialization import fingerprint_report as m10_fingerprint, save_report as save_m10


def _make_m10_report():
    variants = (
        VariantSummary(
            parameter_set="baseline", parameters={"capacity": 1}, total_runs=12,
            successful_runs=12, failed_runs=0,
            metrics=(MetricSummary(
                metric_name="average_waiting_time", unit="time units", value_type="numeric",
                sample_size=12, mean=10.0, population_stddev=1.0, median=10.0,
                minimum=8.0, maximum=12.0, categories=(),
            ),),
        ),
        VariantSummary(
            parameter_set="higher_capacity", parameters={"capacity": 2}, total_runs=12,
            successful_runs=12, failed_runs=0,
            metrics=(MetricSummary(
                metric_name="average_waiting_time", unit="time units", value_type="numeric",
                sample_size=12, mean=7.0, population_stddev=1.1, median=7.0,
                minimum=5.0, maximum=9.0, categories=(),
            ),),
        ),
    )
    pending = AnalysisReport(
        schema_version=1, analysis_id="m10-test", created_at="2026-11-15T00:00:00+00:00",
        artifact_id="artifact-1", artifact_fingerprint="a" * 64, project_id="project-1",
        project_title="Test project", revision_id="revision-1", revision_version=1,
        paradigm="discrete_event", backend_name="simpy_des_v1", baseline_parameter_set="baseline",
        input_experiment_ids=("experiment-1",), input_result_fingerprints=("b" * 64,),
        variants=variants, factors=(), warnings=(), report_fingerprint="pending",
    )
    from dataclasses import replace
    return replace(pending, report_fingerprint=m10_fingerprint(pending))


def _plan() -> AnalyticsPlan:
    return AnalyticsPlan(
        schema_version=1, analysis_name="waiting time comparison",
        sources=(AnalyticsSource("grid", "m10", "m10.json"),),
        metrics=(MetricDefinition(
            "average_waiting_time", "time units",
            "Mean time an entity waits before service starts.", "minimize",
        ),),
    )


def test_m10_adapter_welch_report_fingerprint_and_csv(tmp_path: Path):
    save_m10(_make_m10_report(), tmp_path / "m10.json")
    report = analyze_reports(_plan(), source_root=tmp_path)

    assert len(report.groups) == 2
    assert len(report.comparisons) == 1
    comparison = report.comparisons[0]
    assert comparison.group_b.endswith("higher_capacity")
    assert comparison.mean_difference_b_minus_a == pytest.approx(-3.0)
    assert comparison.significant is True
    assert comparison.holm_adjusted_p_value < 0.05
    assert report.pareto_frontier == ()

    target = save_report(report, tmp_path / "m25.json")
    loaded = load_report(target)
    assert loaded.report_fingerprint == report.report_fingerprint
    csv_path = export_summary_csv(loaded, tmp_path / "m25.csv")
    assert csv_path.read_text(encoding="utf-8").count("group") >= 2


def test_source_path_cannot_escape_root(tmp_path: Path):
    # The source path is rejected at contract construction, before filesystem access.
    with pytest.raises(ValueError, match="relative path"):
        AnalyticsSource("bad", "m10", "../outside.json")


def test_duplicate_report_sources_are_not_double_counted(tmp_path: Path):
    save_m10(_make_m10_report(), tmp_path / "m10.json")
    plan = AnalyticsPlan(
        schema_version=1, analysis_name="duplicate report test",
        sources=(
            AnalyticsSource("grid_a", "m10", "m10.json"),
            AnalyticsSource("grid_b", "m10", "m10_copy.json"),
        ),
        metrics=(MetricDefinition("average_waiting_time", "time units", "Mean time an entity waits before service starts.", "minimize"),),
    )
    (tmp_path / "m10_copy.json").write_text((tmp_path / "m10.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicates a report"):
        analyze_reports(plan, source_root=tmp_path)


def test_plan_requires_explicit_metric_semantics():
    with pytest.raises(ValueError, match="semantic_definition"):
        MetricDefinition("wait", "minutes", "short", "minimize")
