"""Validated contracts for M25 statistical experiment analytics."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, isclose, sqrt
import ntpath


@dataclass(frozen=True, slots=True)
class AnalyticsSource:
    source_id: str
    report_type: str
    path: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip() or len(self.source_id) > 64:
            raise ValueError("source_id must contain 1-64 non-whitespace characters")
        if self.report_type not in {"m10", "m11", "m23", "m24"}:
            raise ValueError("report_type must be one of m10, m11, m23 or m24")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("source path must be non-empty")
        normalized = self.path.replace("\\", "/")
        if normalized.startswith("/") or ntpath.splitdrive(normalized)[0] or ":" in normalized or any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("source path must be a normalized relative path without '.', '..' or drive segments")


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_name: str
    unit: str | None
    semantic_definition: str
    direction: str = "observe"

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("metric unit must be a string or None")
        if not isinstance(self.semantic_definition, str) or len(self.semantic_definition.strip()) < 12:
            raise ValueError("semantic_definition must describe the observable in at least 12 characters")
        if self.direction not in {"minimize", "maximize", "observe"}:
            raise ValueError("direction must be minimize, maximize or observe")


@dataclass(frozen=True, slots=True)
class AnalyticsPlan:
    schema_version: int
    analysis_name: str
    sources: tuple[AnalyticsSource, ...]
    metrics: tuple[MetricDefinition, ...]
    alpha: float = 0.05
    confidence_level: float = 0.95
    minimum_sample_size: int = 5
    max_pairwise_comparisons: int = 200

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M25 analytics plan schema_version")
        if not isinstance(self.analysis_name, str) or not self.analysis_name.strip() or len(self.analysis_name) > 120:
            raise ValueError("analysis_name must contain 1-120 non-whitespace characters")
        if not isinstance(self.sources, tuple) or not 1 <= len(self.sources) <= 20 or any(not isinstance(item, AnalyticsSource) for item in self.sources):
            raise ValueError("sources must contain 1-20 AnalyticsSource values")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("source IDs must be unique")
        if len({item.path for item in self.sources}) != len(self.sources):
            raise ValueError("a report path cannot be included more than once")
        if not isinstance(self.metrics, tuple) or not 1 <= len(self.metrics) <= 10 or any(not isinstance(item, MetricDefinition) for item in self.metrics):
            raise ValueError("metrics must contain 1-10 MetricDefinition values")
        if len({item.metric_name for item in self.metrics}) != len(self.metrics):
            raise ValueError("metric names must be unique in an analytics plan")
        if isinstance(self.alpha, bool) or not isinstance(self.alpha, (int, float)) or not isfinite(self.alpha) or not 0.001 <= self.alpha <= 0.2:
            raise ValueError("alpha must be finite and between 0.001 and 0.2")
        if isinstance(self.confidence_level, bool) or not isinstance(self.confidence_level, (int, float)) or not isfinite(self.confidence_level) or not 0.8 <= self.confidence_level <= 0.999:
            raise ValueError("confidence_level must be between 0.8 and 0.999")
        if abs(self.confidence_level - (1 - self.alpha)) > 1e-9:
            raise ValueError("confidence_level must equal 1 - alpha")
        if isinstance(self.minimum_sample_size, bool) or not isinstance(self.minimum_sample_size, int) or not 2 <= self.minimum_sample_size <= 10000:
            raise ValueError("minimum_sample_size must be between 2 and 10000")
        if isinstance(self.max_pairwise_comparisons, bool) or not isinstance(self.max_pairwise_comparisons, int) or not 1 <= self.max_pairwise_comparisons <= 2000:
            raise ValueError("max_pairwise_comparisons must be between 1 and 2000")


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source_id: str
    report_type: str
    report_path: str
    report_id: str
    report_fingerprint: str
    artifact_ids: tuple[str, ...]
    artifact_fingerprints: tuple[str, ...]
    project_ids: tuple[str, ...]
    revision_ids: tuple[str, ...]
    paradigms: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("source_id", "report_type", "report_path", "report_id", "report_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        for name in ("artifact_ids", "artifact_fingerprints", "project_ids", "revision_ids", "paradigms"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(item, str) or not item.strip() for item in values):
                raise TypeError(f"{name} must be a tuple of non-empty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{name} values must be unique")


@dataclass(frozen=True, slots=True)
class GroupStatistic:
    group_id: str
    source_id: str
    group_label: str
    report_type: str
    artifact_id: str
    project_id: str
    revision_id: str
    paradigm: str
    experiment_ids: tuple[str, ...]
    metric_name: str
    unit: str | None
    semantic_definition: str
    direction: str
    sample_size: int
    mean: float
    population_stddev: float
    sample_stddev: float | None
    standard_error: float | None
    confidence_lower: float | None
    confidence_upper: float | None
    total_runs: int
    observed_runs: int
    unobserved_runs: int
    unobserved_fraction: float
    coefficient_of_variation: float | None
    status: str
    randomization_key: str | None = None

    def __post_init__(self) -> None:
        for name in ("group_id", "source_id", "group_label", "report_type", "artifact_id", "project_id", "revision_id", "paradigm", "metric_name", "semantic_definition"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.direction not in {"minimize", "maximize", "observe"}:
            raise ValueError("invalid metric direction")
        if not isinstance(self.experiment_ids, tuple) or any(not isinstance(item, str) or not item for item in self.experiment_ids):
            raise TypeError("experiment_ids must be a tuple of non-empty strings")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("unit must be a string or None")
        if self.randomization_key is not None and (not isinstance(self.randomization_key, str) or not self.randomization_key.strip()):
            raise TypeError("randomization_key must be a non-empty string or None")
        for name in ("sample_size", "total_runs", "observed_runs", "unobserved_runs"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1 and name == "sample_size" or value < 0 and name != "sample_size":
                raise ValueError(f"{name} has an invalid value")
        if self.observed_runs != self.sample_size or self.observed_runs + self.unobserved_runs != self.total_runs:
            raise ValueError("run counts must match sample and unobserved counts")
        if self.status not in {"sufficient", "low_sample"}:
            raise ValueError("invalid group status")
        expected_status = "sufficient" if self.sample_size >= 2 else "low_sample"
        if self.status != expected_status:
            raise ValueError(f"group status must be {expected_status} for the recorded sample size")
        for name in ("mean", "population_stddev", "unobserved_fraction"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.population_stddev < 0 or not 0 <= self.unobserved_fraction <= 1:
            raise ValueError("standard deviation or unobserved fraction is invalid")
        optional = (self.sample_stddev, self.standard_error, self.confidence_lower, self.confidence_upper, self.coefficient_of_variation)
        if any(value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)) for value in optional):
            raise ValueError("optional statistics must be finite or None")
        if self.sample_size == 1 and any(value is not None for value in optional[:4]):
            raise ValueError("single-observation group cannot report sample uncertainty or confidence interval")
        if self.sample_stddev is not None and self.sample_stddev < 0:
            raise ValueError("sample_stddev must be non-negative")
        if self.standard_error is not None and self.standard_error < 0:
            raise ValueError("standard_error must be non-negative")
        if (self.confidence_lower is None) != (self.confidence_upper is None):
            raise ValueError("confidence interval bounds must both be set or both be None")
        if self.confidence_lower is not None and not self.confidence_lower <= self.mean <= self.confidence_upper:
            raise ValueError("group mean must lie inside its confidence interval")
        if self.sample_size > 1:
            if self.sample_stddev is None or self.standard_error is None:
                raise ValueError("groups with multiple observations require sample standard deviation and standard error")
            if not isclose(self.standard_error, self.sample_stddev / sqrt(self.sample_size), rel_tol=1e-8, abs_tol=1e-12):
                raise ValueError("standard_error must equal sample_stddev/sqrt(sample_size)")
        if not isclose(self.unobserved_fraction, self.unobserved_runs / self.total_runs, rel_tol=1e-8, abs_tol=1e-12):
            raise ValueError("unobserved_fraction must equal unobserved_runs/total_runs")
        if self.coefficient_of_variation is not None and self.coefficient_of_variation < 0:
            raise ValueError("coefficient_of_variation must be non-negative")


@dataclass(frozen=True, slots=True)
class PairwiseComparison:
    metric_name: str
    group_a: str
    group_b: str
    mean_difference_b_minus_a: float
    welch_t: float
    degrees_freedom: float
    p_value: float
    holm_adjusted_p_value: float
    confidence_lower: float
    confidence_upper: float
    hedges_g: float | None
    effect_magnitude: str
    significant: bool

    def __post_init__(self) -> None:
        if not self.metric_name or not self.group_a or not self.group_b or self.group_a == self.group_b:
            raise ValueError("pairwise comparison identifiers are invalid")
        for name in ("mean_difference_b_minus_a", "welch_t", "degrees_freedom", "p_value", "holm_adjusted_p_value", "confidence_lower", "confidence_upper"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.degrees_freedom <= 0 or not 0 <= self.p_value <= 1 or not 0 <= self.holm_adjusted_p_value <= 1:
            raise ValueError("comparison degrees of freedom or p-value is invalid")
        if self.confidence_lower > self.confidence_upper:
            raise ValueError("comparison confidence interval is invalid")
        if self.hedges_g is not None and (isinstance(self.hedges_g, bool) or not isinstance(self.hedges_g, (int, float)) or not isfinite(self.hedges_g)):
            raise ValueError("hedges_g must be finite or None")
        if self.effect_magnitude not in {"negligible", "small", "medium", "large", "not_estimable"}:
            raise ValueError("invalid effect magnitude")
        if not isinstance(self.significant, bool):
            raise TypeError("significant must be a boolean")


@dataclass(frozen=True, slots=True)
class ObjectiveValue:
    metric_name: str
    unit: str | None
    direction: str
    value: float

    def __post_init__(self) -> None:
        if not self.metric_name or self.direction not in {"minimize", "maximize"}:
            raise ValueError("invalid Pareto objective")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("objective unit must be a string or None")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not isfinite(self.value):
            raise ValueError("objective value must be finite")


@dataclass(frozen=True, slots=True)
class ParetoEntry:
    group_id: str
    group_label: str
    objectives: tuple[ObjectiveValue, ...]
    pareto_optimal: bool
    dominated_by: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.group_id or not self.group_label:
            raise ValueError("Pareto group identifiers must be non-empty")
        if not isinstance(self.objectives, tuple) or len(self.objectives) < 2 or any(not isinstance(item, ObjectiveValue) for item in self.objectives):
            raise ValueError("Pareto entries require at least two objectives")
        if not isinstance(self.pareto_optimal, bool) or not isinstance(self.dominated_by, tuple):
            raise TypeError("invalid Pareto status or dominated_by")
        if self.pareto_optimal != (len(self.dominated_by) == 0):
            raise ValueError("Pareto status must match dominated_by")


@dataclass(frozen=True, slots=True)
class Insight:
    code: str
    severity: str
    metric_name: str | None
    group_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        if not self.code or self.severity not in {"info", "warning", "caution"} or not isinstance(self.group_ids, tuple):
            raise ValueError("invalid insight")
        if self.metric_name is not None and not isinstance(self.metric_name, str):
            raise TypeError("metric_name must be a string or None")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("insight message must be non-empty")


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    schema_version: int
    analysis_id: str
    created_at: str
    plan: AnalyticsPlan
    sources: tuple[SourceEvidence, ...]
    groups: tuple[GroupStatistic, ...]
    comparisons: tuple[PairwiseComparison, ...]
    pareto_frontier: tuple[ParetoEntry, ...]
    insights: tuple[Insight, ...]
    warnings: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M25 report schema_version")
        for name in ("analysis_id", "created_at", "report_fingerprint"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(self.plan, AnalyticsPlan):
            raise TypeError("plan must be AnalyticsPlan")
        for name, cls in (("sources", SourceEvidence), ("groups", GroupStatistic), ("comparisons", PairwiseComparison), ("pareto_frontier", ParetoEntry), ("insights", Insight)):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, cls) for item in value):
                raise TypeError(f"{name} must be a tuple of {cls.__name__}")
        if not self.sources or not self.groups:
            raise ValueError("M25 report requires at least one verified source and one metric group")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("M25 report source IDs must be unique")
        if tuple(item.source_id for item in self.sources) != tuple(item.source_id for item in self.plan.sources):
            raise ValueError("source evidence must preserve the analytics plan source order and IDs")
        if any(evidence.report_type != spec.report_type or evidence.report_path != spec.path for evidence, spec in zip(self.sources, self.plan.sources)):
            raise ValueError("source evidence report type/path must match the analytics plan")
        source_ids = {item.source_id for item in self.sources}
        definitions = {item.metric_name: item for item in self.plan.metrics}
        group_ids = {item.group_id for item in self.groups}
        group_keys = [(item.group_id, item.metric_name) for item in self.groups]
        if len(group_keys) != len(set(group_keys)):
            raise ValueError("metric group IDs must be unique within each metric")
        for group in self.groups:
            if group.source_id not in source_ids or group.metric_name not in definitions:
                raise ValueError("group statistic references an undeclared source or metric")
            definition = definitions[group.metric_name]
            if (group.unit, group.semantic_definition, group.direction) != (definition.unit, definition.semantic_definition, definition.direction):
                raise ValueError("group metric metadata must match its declared M25 metric definition")
        comparison_keys = [(item.metric_name, item.group_a, item.group_b) for item in self.comparisons]
        if len(comparison_keys) != len(set(comparison_keys)):
            raise ValueError("pairwise comparison definitions must be unique")
        group_by_metric = {(item.group_id, item.metric_name) for item in self.groups}
        for comparison in self.comparisons:
            if (comparison.group_a, comparison.metric_name) not in group_by_metric or (comparison.group_b, comparison.metric_name) not in group_by_metric:
                raise ValueError("pairwise comparison references an unknown metric group")
            if comparison.significant != (comparison.holm_adjusted_p_value < self.plan.alpha):
                raise ValueError("comparison significance must match the Holm-adjusted p-value and plan alpha")
        for item in self.pareto_frontier:
            if item.group_id not in group_ids:
                raise ValueError("Pareto entry references an unknown group")
        for item in self.insights:
            if any(group_id not in group_ids for group_id in item.group_ids):
                raise ValueError("insight references an unknown group")
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) for item in self.warnings):
            raise TypeError("warnings must be a tuple of strings")
