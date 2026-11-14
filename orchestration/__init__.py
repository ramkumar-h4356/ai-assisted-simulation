"""M24 cross-engine experiment orchestration."""

from orchestration.engine import execute_suite, execute_suite_file
from orchestration.models import (
    CategoryCount, ComparisonEntry, ExperimentSuitePlan, ExperimentSuiteReport,
    MetricAggregate, SuiteComparison, SuiteMember, SuiteMemberSummary,
)
from orchestration.serialization import (
    SuiteSerializationError, export_summary_csv, fingerprint_report, load_plan,
    load_report, loads_plan, loads_report, plan_to_dict, report_to_dict,
    save_report,
)

__all__ = [
    "CategoryCount", "ComparisonEntry", "ExperimentSuitePlan", "ExperimentSuiteReport",
    "MetricAggregate", "SuiteComparison", "SuiteMember", "SuiteMemberSummary",
    "SuiteSerializationError", "execute_suite", "execute_suite_file", "export_summary_csv",
    "fingerprint_report", "load_plan", "load_report", "loads_plan", "loads_report",
    "plan_to_dict", "report_to_dict", "save_report",
]
