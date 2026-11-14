"""Validated contracts for M23 objective-driven simulation optimization."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


def _finite_number(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class SearchParameter:
    """A numeric M8 user parameter and its inclusive search bounds."""

    target_path: str
    lower: int | float
    upper: int | float

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("search parameter target_path must be non-empty")
        _finite_number(self.lower, "lower bound")
        _finite_number(self.upper, "upper bound")
        if type(self.lower) is not type(self.upper):
            raise TypeError("search parameter bounds must have the same numeric type")
        if self.lower >= self.upper:
            raise ValueError("search parameter lower bound must be less than upper bound")


@dataclass(frozen=True, slots=True)
class OptimizationObjective:
    metric_name: str
    direction: str = "minimize"

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("objective metric_name must be non-empty")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("objective direction must be 'minimize' or 'maximize'")


@dataclass(frozen=True, slots=True)
class MetricConstraint:
    """Constraint evaluated against the mean metric for each candidate."""

    metric_name: str
    operator: str
    threshold: float
    upper_threshold: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("constraint metric_name must be non-empty")
        if self.operator not in {"<=", ">=", "between"}:
            raise ValueError("constraint operator must be <=, >=, or between")
        _finite_number(self.threshold, "constraint threshold")
        if self.operator == "between":
            if self.upper_threshold is None:
                raise ValueError("between constraints require upper_threshold")
            _finite_number(self.upper_threshold, "constraint upper_threshold")
            if self.threshold > self.upper_threshold:
                raise ValueError("between constraint lower threshold must not exceed upper_threshold")
        elif self.upper_threshold is not None:
            raise ValueError("upper_threshold is only valid for between constraints")


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    """Reproducible random-search plan bounded by the M9 execution budget."""

    search_parameters: tuple[SearchParameter, ...]
    objective: OptimizationObjective
    candidate_count: int = 20
    replications: int = 1
    search_seed: int = 20261115
    include_baseline: bool = True
    constraints: tuple[MetricConstraint, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.search_parameters, tuple) or not self.search_parameters:
            raise ValueError("search_parameters must be a non-empty tuple")
        if any(not isinstance(item, SearchParameter) for item in self.search_parameters):
            raise TypeError("search_parameters must contain SearchParameter values")
        paths = [item.target_path for item in self.search_parameters]
        if len(paths) != len(set(paths)):
            raise ValueError("search parameter target paths must be unique")
        if not isinstance(self.objective, OptimizationObjective):
            raise TypeError("objective must be an OptimizationObjective")
        if isinstance(self.candidate_count, bool) or not isinstance(self.candidate_count, int) or not 1 <= self.candidate_count <= 99:
            raise ValueError("candidate_count must be between 1 and 99")
        if isinstance(self.replications, bool) or not isinstance(self.replications, int) or not 1 <= self.replications <= 100:
            raise ValueError("replications must be between 1 and 100")
        if isinstance(self.search_seed, bool) or not isinstance(self.search_seed, int) or self.search_seed < 0:
            raise ValueError("search_seed must be a non-negative integer")
        if not isinstance(self.include_baseline, bool):
            raise TypeError("include_baseline must be a boolean")
        if not isinstance(self.constraints, tuple) or any(not isinstance(item, MetricConstraint) for item in self.constraints):
            raise TypeError("constraints must contain MetricConstraint values")
        constraint_names = [item.metric_name for item in self.constraints]
        if len(constraint_names) != len(set(constraint_names)):
            raise ValueError("constraint metric names must be unique")
        total_candidates = self.candidate_count + (1 if self.include_baseline else 0)
        if total_candidates * self.replications > 100:
            raise ValueError("candidate_count plus baseline, multiplied by replications, must not exceed 100 M9 executions")


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation:
    metric_name: str
    operator: str
    threshold: float
    upper_threshold: float | None
    measured_mean: float | None
    satisfied: bool

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("constraint evaluation metric_name must be non-empty")
        if self.operator not in {"<=", ">=", "between"}:
            raise ValueError("invalid constraint evaluation operator")
        _finite_number(self.threshold, "constraint evaluation threshold")
        if self.upper_threshold is not None:
            _finite_number(self.upper_threshold, "constraint evaluation upper_threshold")
        if self.measured_mean is not None:
            _finite_number(self.measured_mean, "constraint measured_mean")
        if not isinstance(self.satisfied, bool):
            raise TypeError("constraint satisfied must be a boolean")
        if self.satisfied and self.measured_mean is None:
            raise ValueError("a satisfied constraint requires a measured mean")


@dataclass(frozen=True, slots=True)
class CandidateSummary:
    parameter_set: str
    parameters: dict[str, int | float]
    total_runs: int
    successful_runs: int
    failed_runs: int
    objective_mean: float | None
    objective_population_stddev: float | None
    objective_sample_size: int
    feasible: bool
    status: str
    constraints: tuple[ConstraintEvaluation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.parameter_set, str) or not self.parameter_set.strip():
            raise ValueError("candidate parameter_set must be non-empty")
        if not isinstance(self.parameters, dict) or any(not isinstance(key, str) for key in self.parameters):
            raise TypeError("candidate parameters must be a string-keyed object")
        for value in self.parameters.values():
            _finite_number(value, "candidate parameter")
        for name in ("total_runs", "successful_runs", "failed_runs", "objective_sample_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.successful_runs + self.failed_runs != self.total_runs:
            raise ValueError("candidate successful_runs plus failed_runs must equal total_runs")
        for name in ("objective_mean", "objective_population_stddev"):
            value = getattr(self, name)
            if value is not None:
                _finite_number(value, name)
        if self.objective_population_stddev is not None and self.objective_population_stddev < 0:
            raise ValueError("objective_population_stddev must be non-negative")
        if self.objective_sample_size > self.successful_runs:
            raise ValueError("objective_sample_size cannot exceed successful_runs")
        if self.feasible and (self.status != "complete" or self.objective_mean is None):
            raise ValueError("a feasible candidate must be complete and have an objective value")
        if self.status not in {"complete", "constraint_failed", "incomplete"}:
            raise ValueError("unsupported candidate status")
        if not isinstance(self.feasible, bool):
            raise TypeError("candidate feasible must be a boolean")
        if not isinstance(self.constraints, tuple) or any(not isinstance(item, ConstraintEvaluation) for item in self.constraints):
            raise TypeError("candidate constraints must contain ConstraintEvaluation values")


@dataclass(frozen=True, slots=True)
class OptimizationReport:
    schema_version: int
    optimization_id: str
    created_at: str
    artifact_id: str
    artifact_fingerprint: str
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    paradigm: str
    backend_name: str
    algorithm: str
    plan: OptimizationPlan
    experiment_id: str
    experiment_fingerprint: str
    candidates: tuple[CandidateSummary, ...]
    baseline_parameter_set: str | None
    best_parameter_set: str | None
    objective_improvement: float | None
    warnings: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M23 optimization report schema_version")
        for name in (
            "optimization_id", "created_at", "artifact_id", "artifact_fingerprint",
            "project_id", "project_title", "revision_id", "paradigm", "backend_name",
            "algorithm", "experiment_id", "experiment_fingerprint", "report_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if not isinstance(self.plan, OptimizationPlan):
            raise TypeError("plan must be an OptimizationPlan")
        if not isinstance(self.candidates, tuple) or not self.candidates or any(not isinstance(item, CandidateSummary) for item in self.candidates):
            raise ValueError("candidates must be a non-empty tuple of CandidateSummary values")
        names = [item.parameter_set for item in self.candidates]
        if len(names) != len(set(names)):
            raise ValueError("candidate parameter_set names must be unique")
        if self.baseline_parameter_set is not None and self.baseline_parameter_set not in names:
            raise ValueError("baseline_parameter_set must identify a candidate")
        if self.best_parameter_set is not None:
            best = next((item for item in self.candidates if item.parameter_set == self.best_parameter_set), None)
            if best is None or not best.feasible:
                raise ValueError("best_parameter_set must identify a feasible candidate")
        if self.objective_improvement is not None:
            _finite_number(self.objective_improvement, "objective_improvement")
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) for item in self.warnings):
            raise TypeError("warnings must be a tuple of strings")


__all__ = [
    "CandidateSummary", "ConstraintEvaluation", "MetricConstraint",
    "OptimizationObjective", "OptimizationPlan", "OptimizationReport",
    "SearchParameter",
]
