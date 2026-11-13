"""Validated contracts for M11 uncertainty and robustness analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any
import json


@dataclass(frozen=True, slots=True)
class UncertainParameter:
    """A numeric M8 user parameter and its declared input distribution."""

    target_path: str
    distribution: str
    lower: int | float
    upper: int | float
    mode: int | float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("uncertain parameter target_path must be non-empty")
        if self.distribution not in {"uniform", "triangular"}:
            raise ValueError("distribution must be 'uniform' or 'triangular'")
        for name, value in (("lower", self.lower), ("upper", self.upper)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if type(self.lower) is not type(self.upper):
            raise TypeError("lower and upper must have the same numeric type")
        if self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        if self.distribution == "uniform" and self.mode is not None:
            raise ValueError("uniform distributions must not define mode")
        if self.distribution == "triangular":
            if isinstance(self.mode, bool) or not isinstance(self.mode, (int, float)) or not isfinite(self.mode):
                raise ValueError("triangular distributions require a finite numeric mode")
            if type(self.mode) is not type(self.lower):
                raise TypeError("triangular mode must use the same numeric type as bounds")
            if not self.lower <= self.mode <= self.upper:
                raise ValueError("triangular mode must lie between lower and upper")


@dataclass(frozen=True, slots=True)
class RobustnessCriterion:
    """A user-defined acceptable range for one numeric outcome metric."""

    metric_name: str
    operator: str
    threshold: float
    upper_threshold: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("criterion metric_name must be non-empty")
        if self.operator not in {"<=", ">=", "between"}:
            raise ValueError("criterion operator must be <=, >=, or between")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)) or not isfinite(self.threshold):
            raise ValueError("criterion threshold must be a finite number")
        if self.operator == "between":
            if isinstance(self.upper_threshold, bool) or not isinstance(self.upper_threshold, (int, float)) or not isfinite(self.upper_threshold):
                raise ValueError("between criteria require a finite upper_threshold")
            if self.threshold > self.upper_threshold:
                raise ValueError("between lower threshold must not exceed upper_threshold")
        elif self.upper_threshold is not None:
            raise ValueError("upper_threshold is only valid for between criteria")


@dataclass(frozen=True, slots=True)
class UncertaintyPlan:
    """Reproducible Monte Carlo sampling plan for one M8 artifact."""

    sample_count: int
    sampling_seed: int
    parameters: tuple[UncertainParameter, ...]
    criteria: tuple[RobustnessCriterion, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.sample_count, bool) or not isinstance(self.sample_count, int) or not 3 <= self.sample_count <= 100:
            raise ValueError("sample_count must be between 3 and 100")
        if isinstance(self.sampling_seed, bool) or not isinstance(self.sampling_seed, int) or self.sampling_seed < 0:
            raise ValueError("sampling_seed must be a non-negative integer")
        if not isinstance(self.parameters, tuple) or not self.parameters or any(not isinstance(item, UncertainParameter) for item in self.parameters):
            raise ValueError("parameters must be a non-empty tuple of UncertainParameter values")
        if not isinstance(self.criteria, tuple) or any(not isinstance(item, RobustnessCriterion) for item in self.criteria):
            raise TypeError("criteria must be a tuple of RobustnessCriterion values")
        paths = [item.target_path for item in self.parameters]
        if len(paths) != len(set(paths)):
            raise ValueError("uncertain parameter paths must be unique")
        metrics = [item.metric_name for item in self.criteria]
        if len(metrics) != len(set(metrics)):
            raise ValueError("robustness criterion metric names must be unique")


@dataclass(frozen=True, slots=True)
class MetricDistribution:
    metric_name: str
    unit: str | None
    sample_size: int
    mean: float
    population_stddev: float
    median: float
    percentile_05: float
    percentile_95: float
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("unit must be a string or None")
        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int) or self.sample_size < 1:
            raise ValueError("sample_size must be a positive integer")
        numbers = (self.mean, self.population_stddev, self.median, self.percentile_05, self.percentile_95, self.minimum, self.maximum)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in numbers):
            raise ValueError("distribution statistics must be finite numbers")
        if self.population_stddev < 0 or not self.minimum <= self.percentile_05 <= self.median <= self.percentile_95 <= self.maximum:
            raise ValueError("distribution range is invalid")
        if not self.minimum <= self.mean <= self.maximum:
            raise ValueError("mean must lie within minimum and maximum")


@dataclass(frozen=True, slots=True)
class SensitivityScore:
    parameter_path: str
    metric_name: str
    sample_size: int
    spearman_rho: float | None
    absolute_rho: float | None
    direction: str
    rank: int | None

    def __post_init__(self) -> None:
        if not self.parameter_path or not self.metric_name:
            raise ValueError("sensitivity parameter_path and metric_name must be non-empty")
        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int) or self.sample_size < 0:
            raise ValueError("sample_size must be a non-negative integer")
        if self.spearman_rho is None:
            if self.absolute_rho is not None or self.rank is not None or self.direction != "not_estimable":
                raise ValueError("non-estimable sensitivity score must not contain rank values")
        else:
            if not isfinite(self.spearman_rho) or not -1.0 <= self.spearman_rho <= 1.0:
                raise ValueError("spearman_rho must be between -1 and 1")
            if self.absolute_rho is None or not isfinite(self.absolute_rho) or not 0 <= self.absolute_rho <= 1:
                raise ValueError("absolute_rho must be between 0 and 1")
            if self.direction not in {"positive", "negative", "no_monotonic_association"}:
                raise ValueError("invalid sensitivity direction")
            if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
                raise ValueError("estimable sensitivity rank must be positive")


@dataclass(frozen=True, slots=True)
class CriterionResult:
    metric_name: str
    operator: str
    threshold: float
    upper_threshold: float | None
    evaluated_runs: int
    passing_runs: int
    observed_fraction: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip() or self.operator not in {"<=", ">=", "between"}:
            raise ValueError("invalid criterion result")
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)) or not isfinite(self.threshold):
            raise ValueError("criterion result threshold must be finite")
        if self.operator == "between":
            if isinstance(self.upper_threshold, bool) or not isinstance(self.upper_threshold, (int, float)) or not isfinite(self.upper_threshold):
                raise ValueError("between criterion result requires a finite upper threshold")
            if self.threshold > self.upper_threshold:
                raise ValueError("criterion result lower threshold must not exceed upper threshold")
        elif self.upper_threshold is not None:
            raise ValueError("upper threshold is only valid for between criterion results")
        if isinstance(self.evaluated_runs, bool) or not isinstance(self.evaluated_runs, int) or self.evaluated_runs < 0:
            raise ValueError("evaluated_runs must be non-negative")
        if isinstance(self.passing_runs, bool) or not isinstance(self.passing_runs, int) or not 0 <= self.passing_runs <= self.evaluated_runs:
            raise ValueError("passing_runs must be between zero and evaluated_runs")
        expected = self.passing_runs / self.evaluated_runs if self.evaluated_runs else None
        if self.observed_fraction != expected:
            raise ValueError("observed_fraction must equal passing_runs/evaluated_runs or None")


@dataclass(frozen=True, slots=True)
class RobustnessSummary:
    evaluated_runs: int
    passing_runs: int
    observed_fraction: float | None
    criteria: tuple[CriterionResult, ...]

    def __post_init__(self) -> None:
        if isinstance(self.evaluated_runs, bool) or not isinstance(self.evaluated_runs, int) or self.evaluated_runs < 0:
            raise ValueError("evaluated_runs must be non-negative")
        if isinstance(self.passing_runs, bool) or not isinstance(self.passing_runs, int) or not 0 <= self.passing_runs <= self.evaluated_runs:
            raise ValueError("passing_runs must be between zero and evaluated_runs")
        expected = self.passing_runs / self.evaluated_runs if self.evaluated_runs else None
        if self.observed_fraction != expected:
            raise ValueError("observed_fraction must equal passing_runs/evaluated_runs or None")
        if not isinstance(self.criteria, tuple) or any(not isinstance(item, CriterionResult) for item in self.criteria):
            raise TypeError("criteria must contain CriterionResult values")


@dataclass(frozen=True, slots=True)
class UncertaintyReport:
    schema_version: int
    report_id: str
    created_at: str
    artifact_id: str
    artifact_fingerprint: str
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    paradigm: str
    backend_name: str
    experiment_id: str
    experiment_fingerprint: str
    sample_count: int
    sampling_seed: int
    parameters: tuple[UncertainParameter, ...]
    criteria: tuple[RobustnessCriterion, ...]
    metric_distributions: tuple[MetricDistribution, ...]
    sensitivity: tuple[SensitivityScore, ...]
    robustness: RobustnessSummary
    failed_runs: int
    warnings: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M11 report schema_version")
        for name in ("report_id", "created_at", "artifact_id", "artifact_fingerprint", "project_id", "project_title", "revision_id", "paradigm", "backend_name", "experiment_id", "experiment_fingerprint", "report_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if isinstance(self.sample_count, bool) or not isinstance(self.sample_count, int) or not 3 <= self.sample_count <= 100:
            raise ValueError("sample_count must be between 3 and 100")
        if isinstance(self.sampling_seed, bool) or not isinstance(self.sampling_seed, int) or self.sampling_seed < 0:
            raise ValueError("sampling_seed must be a non-negative integer")
        if not isinstance(self.parameters, tuple) or not self.parameters or any(not isinstance(item, UncertainParameter) for item in self.parameters):
            raise TypeError("parameters must be a non-empty tuple")
        if not isinstance(self.criteria, tuple) or any(not isinstance(item, RobustnessCriterion) for item in self.criteria):
            raise TypeError("criteria must be a tuple")
        if not isinstance(self.metric_distributions, tuple) or any(not isinstance(item, MetricDistribution) for item in self.metric_distributions):
            raise TypeError("metric_distributions must be a tuple")
        if not isinstance(self.sensitivity, tuple) or any(not isinstance(item, SensitivityScore) for item in self.sensitivity):
            raise TypeError("sensitivity must be a tuple")
        if not isinstance(self.robustness, RobustnessSummary):
            raise TypeError("robustness must be a RobustnessSummary")
        if isinstance(self.failed_runs, bool) or not isinstance(self.failed_runs, int) or not 0 <= self.failed_runs <= self.sample_count:
            raise ValueError("failed_runs must be between zero and sample_count")
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) for item in self.warnings):
            raise TypeError("warnings must be a tuple of strings")
