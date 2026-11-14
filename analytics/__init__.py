"""M25 advanced statistical analytics and results intelligence."""

from analytics.analysis import analyze_reports
from analytics.models import (
    AnalyticsPlan, AnalyticsReport, AnalyticsSource, GroupStatistic, Insight,
    MetricDefinition, ObjectiveValue, PairwiseComparison, ParetoEntry, SourceEvidence,
)
from analytics.serialization import (
    export_summary_csv, load_plan, load_report, save_report,
)

__all__ = [
    "AnalyticsPlan", "AnalyticsReport", "AnalyticsSource", "GroupStatistic", "Insight",
    "MetricDefinition", "ObjectiveValue", "PairwiseComparison", "ParetoEntry", "SourceEvidence",
    "analyze_reports", "export_summary_csv", "load_plan", "load_report", "save_report",
]
