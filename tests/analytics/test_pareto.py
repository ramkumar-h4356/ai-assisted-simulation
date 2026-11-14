from __future__ import annotations

from analytics.analysis import _pareto
from analytics.models import AnalyticsPlan, AnalyticsSource, GroupStatistic, MetricDefinition


def _group(gid: str, metric: str, mean: float, direction: str) -> GroupStatistic:
    return GroupStatistic(
        group_id=gid, source_id="one", group_label=gid, report_type="m10", artifact_id="a",
        project_id="p", revision_id="r", paradigm="abm", experiment_ids=("e",),
        metric_name=metric, unit="unit", semantic_definition="Clearly defined observable metric.", direction=direction,
        sample_size=4, mean=mean, population_stddev=1.0, sample_stddev=1.154700538,
        standard_error=0.577350269, confidence_lower=mean - 1, confidence_upper=mean + 1,
        total_runs=4, observed_runs=4, unobserved_runs=0, unobserved_fraction=0.0,
        coefficient_of_variation=0.1, status="sufficient",
    )


def test_pareto_frontier_detects_dominated_groups():
    plan = AnalyticsPlan(
        schema_version=1, analysis_name="tradeoff",
        sources=(AnalyticsSource("one", "m10", "report.json"),),
        metrics=(
            MetricDefinition("cost", "unit", "Total simulated resource cost metric.", "minimize"),
            MetricDefinition("quality", "unit", "Simulated service quality output metric.", "maximize"),
        ),
    )
    groups = (
        _group("g1", "cost", 10, "minimize"), _group("g1", "quality", 80, "maximize"),
        _group("g2", "cost", 12, "minimize"), _group("g2", "quality", 70, "maximize"),
        _group("g3", "cost", 8, "minimize"), _group("g3", "quality", 75, "maximize"),
    )
    warnings: list[str] = []
    result = _pareto(groups, plan, warnings)
    by_id = {item.group_id: item for item in result}
    assert by_id["g1"].pareto_optimal
    assert not by_id["g2"].pareto_optimal
    assert "g1" in by_id["g2"].dominated_by
    assert by_id["g3"].pareto_optimal
