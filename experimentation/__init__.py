"""M10 parameter-sweep design and comparative analysis."""

from experimentation.analysis import analyze_results, run_parameter_sweep
from experimentation.grid import generate_parameter_grid
from experimentation.models import (
    AnalysisReport, CategoryCount, FactorLevelSummary, FactorSummary,
    GridFactor, MetricDelta, MetricSummary, VariantSummary,
)
from experimentation.serialization import (
    AnalysisSerializationError, dumps_report, export_summary_csv,
    fingerprint_report, load_report, loads_report, report_to_dict, save_report,
)

__all__ = [
    "AnalysisReport", "AnalysisSerializationError", "CategoryCount",
    "FactorLevelSummary", "FactorSummary", "GridFactor", "MetricDelta",
    "MetricSummary", "VariantSummary", "analyze_results", "dumps_report",
    "export_summary_csv", "fingerprint_report", "generate_parameter_grid",
    "load_report", "loads_report", "report_to_dict", "run_parameter_sweep",
    "save_report",
]
