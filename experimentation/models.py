"""Validated contracts for parameter sweeps and comparative analysis (M10)."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import json
from typing import Any


Scalar = str | int | float | bool | None


def _validate_scalar(value: Any, name: str) -> None:
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise TypeError(f"{name} must be a JSON-compatible scalar")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class GridFactor:
    """A user-defined parameter path and the discrete values to evaluate."""

    target_path: str
    levels: tuple[Scalar, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("grid factor target_path must be non-empty")
        if not isinstance(self.levels, tuple) or not self.levels:
            raise ValueError("grid factor levels must be a non-empty tuple")
        for value in self.levels:
            _validate_scalar(value, "grid factor level")
        keys = [json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False) for item in self.levels]
        if len(keys) != len(set(keys)):
            raise ValueError("grid factor levels must be unique")


@dataclass(frozen=True, slots=True)
class CategoryCount:
    value: Scalar
    count: int

    def __post_init__(self) -> None:
        _validate_scalar(self.value, "category value")
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 1:
            raise ValueError("category count must be a positive integer")


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """Descriptive distribution summary for one metric."""

    metric_name: str
    unit: str | None
    value_type: str
    sample_size: int
    mean: float | None = None
    population_stddev: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    categories: tuple[CategoryCount, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("metric unit must be a string or None")
        if self.value_type not in {"numeric", "categorical"}:
            raise ValueError("value_type must be numeric or categorical")
        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int) or self.sample_size < 1:
            raise ValueError("sample_size must be a positive integer")
        numeric = (self.mean, self.population_stddev, self.median, self.minimum, self.maximum)
        if self.value_type == "numeric":
            if any(value is None for value in numeric):
                raise ValueError("numeric metric summaries require all numeric statistics")
            if self.categories:
                raise ValueError("numeric metric summaries cannot contain categories")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in numeric):
                raise ValueError("numeric metric statistics must be finite numbers")
            if self.population_stddev < 0 or not self.minimum <= self.median <= self.maximum:
                raise ValueError("numeric metric range or standard deviation is invalid")
            if not self.minimum <= self.mean <= self.maximum:
                raise ValueError("numeric metric mean must lie within its observed range")
        else:
            if any(value is not None for value in numeric):
                raise ValueError("categorical metric summaries cannot contain numeric statistics")
            if any(not isinstance(item, CategoryCount) for item in self.categories):
                raise TypeError("categories must contain CategoryCount values")
            if not self.categories or sum(item.count for item in self.categories) != self.sample_size:
                raise ValueError("categorical counts must sum to sample_size")


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric_name: str
    baseline_mean: float
    comparison_mean: float
    absolute_change: float
    percent_change: float | None
    baseline_sample_size: int
    comparison_sample_size: int

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be non-empty")
        values = (self.baseline_mean, self.comparison_mean, self.absolute_change)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in values):
            raise ValueError("metric delta values must be finite numbers")
        if self.percent_change is not None and (isinstance(self.percent_change, bool) or not isinstance(self.percent_change, (int, float)) or not isfinite(self.percent_change)):
            raise ValueError("percent_change must be finite or None")
        for value in (self.baseline_sample_size, self.comparison_sample_size):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("delta sample sizes must be positive integers")


@dataclass(frozen=True, slots=True)
class VariantSummary:
    parameter_set: str
    parameters: dict[str, Scalar]
    total_runs: int
    successful_runs: int
    failed_runs: int
    metrics: tuple[MetricSummary, ...]
    deltas_vs_baseline: tuple[MetricDelta, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.parameter_set, str) or not self.parameter_set.strip():
            raise ValueError("parameter_set must be non-empty")
        if not isinstance(self.parameters, dict) or any(not isinstance(key, str) for key in self.parameters):
            raise TypeError("parameters must be a string-keyed object")
        for value in self.parameters.values():
            _validate_scalar(value, "parameter value")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (self.total_runs, self.successful_runs, self.failed_runs)):
            raise ValueError("run counts must be non-negative integers")
        if self.successful_runs + self.failed_runs != self.total_runs:
            raise ValueError("successful_runs + failed_runs must equal total_runs")
        if not isinstance(self.metrics, tuple) or any(not isinstance(item, MetricSummary) for item in self.metrics):
            raise TypeError("metrics must be a tuple of MetricSummary values")
        if not isinstance(self.deltas_vs_baseline, tuple) or any(not isinstance(item, MetricDelta) for item in self.deltas_vs_baseline):
            raise TypeError("deltas_vs_baseline must be a tuple of MetricDelta values")
        try:
            copied = json.loads(json.dumps(self.parameters, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"parameters must be finite JSON data: {error}") from error
        object.__setattr__(self, "parameters", copied)


@dataclass(frozen=True, slots=True)
class FactorLevelSummary:
    value: Scalar
    successful_runs: int
    metrics: tuple[MetricSummary, ...]
    deltas_vs_baseline: tuple[MetricDelta, ...] = ()

    def __post_init__(self) -> None:
        _validate_scalar(self.value, "factor level value")
        if isinstance(self.successful_runs, bool) or not isinstance(self.successful_runs, int) or self.successful_runs < 1:
            raise ValueError("successful_runs must be a positive integer")
        if not isinstance(self.metrics, tuple) or any(not isinstance(item, MetricSummary) for item in self.metrics):
            raise TypeError("metrics must be a tuple of MetricSummary values")
        if not isinstance(self.deltas_vs_baseline, tuple) or any(not isinstance(item, MetricDelta) for item in self.deltas_vs_baseline):
            raise TypeError("deltas_vs_baseline must be a tuple of MetricDelta values")


@dataclass(frozen=True, slots=True)
class FactorSummary:
    target_path: str
    baseline_value: Scalar
    levels: tuple[FactorLevelSummary, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("factor target_path must be non-empty")
        _validate_scalar(self.baseline_value, "baseline factor value")
        if not isinstance(self.levels, tuple) or not self.levels or any(not isinstance(item, FactorLevelSummary) for item in self.levels):
            raise ValueError("factor levels must be a non-empty tuple of FactorLevelSummary values")
        level_keys = [json.dumps(item.value, sort_keys=True, separators=(",", ":"), allow_nan=False) for item in self.levels]
        if len(level_keys) != len(set(level_keys)):
            raise ValueError("factor summary levels must be unique")


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    schema_version: int
    analysis_id: str
    created_at: str
    artifact_id: str
    artifact_fingerprint: str
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    paradigm: str
    backend_name: str
    baseline_parameter_set: str
    input_experiment_ids: tuple[str, ...]
    input_result_fingerprints: tuple[str, ...]
    variants: tuple[VariantSummary, ...]
    factors: tuple[FactorSummary, ...]
    warnings: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported analysis report schema_version")
        for name in ("analysis_id", "created_at", "artifact_id", "artifact_fingerprint", "project_id", "project_title", "revision_id", "paradigm", "backend_name", "baseline_parameter_set", "report_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        for name in ("input_experiment_ids", "input_result_fingerprints", "warnings"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(item, str) or not item.strip() for item in values):
                raise TypeError(f"{name} must be a tuple of non-empty strings")
        if not self.input_experiment_ids or len(self.input_experiment_ids) != len(self.input_result_fingerprints):
            raise ValueError("analysis requires matching input experiment IDs and result fingerprints")
        if len(set(self.input_experiment_ids)) != len(self.input_experiment_ids):
            raise ValueError("input experiment IDs must be unique")
        if not isinstance(self.variants, tuple) or not self.variants or any(not isinstance(item, VariantSummary) for item in self.variants):
            raise ValueError("variants must be a non-empty tuple of VariantSummary values")
        variant_names = [item.parameter_set for item in self.variants]
        if len(variant_names) != len(set(variant_names)):
            raise ValueError("analysis variant names must be unique")
        if not isinstance(self.factors, tuple) or any(not isinstance(item, FactorSummary) for item in self.factors):
            raise TypeError("factors must contain FactorSummary values")
