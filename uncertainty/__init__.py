"""M11 uncertainty propagation, sensitivity screening and robustness analysis."""

from uncertainty.analysis import analyze_uncertainty, run_uncertainty_analysis
from uncertainty.models import (
    CriterionResult, MetricDistribution, RobustnessCriterion, RobustnessSummary,
    SensitivityScore, UncertainParameter, UncertaintyPlan, UncertaintyReport,
)
from uncertainty.sampling import generate_parameter_samples
from uncertainty.serialization import (
    UncertaintySerializationError, export_summary_csv, fingerprint_report,
    load_plan, load_report, loads_report, plan_from_dict, report_to_dict,
    save_report,
)

__all__ = [
    "CriterionResult", "MetricDistribution", "RobustnessCriterion",
    "RobustnessSummary", "SensitivityScore", "UncertainParameter",
    "UncertaintyPlan", "UncertaintyReport", "UncertaintySerializationError",
    "analyze_uncertainty", "export_summary_csv", "fingerprint_report",
    "generate_parameter_samples", "load_plan", "load_report", "loads_report",
    "plan_from_dict", "report_to_dict", "run_uncertainty_analysis", "save_report",
]
