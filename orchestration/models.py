"""Validated contracts for M24 cross-engine experiment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
import ntpath

from execution.models import ParameterSet

_MEMBER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


@dataclass(frozen=True, slots=True)
class SuiteMember:
    """One M8 artifact and its M9 execution settings within a suite."""

    member_id: str
    label: str
    artifact_path: str
    runs: int = 1
    base_seed: int | None = None
    continue_on_error: bool = True
    parameter_sets: tuple[ParameterSet, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.member_id, str) or not _MEMBER_ID.fullmatch(self.member_id):
            raise ValueError("member_id must be 1-40 letters, digits, '_' or '-' and start with a letter or digit")
        if not isinstance(self.label, str) or not self.label.strip() or len(self.label) > 120:
            raise ValueError("member label must contain 1-120 non-whitespace characters")
        if not isinstance(self.artifact_path, str) or not self.artifact_path.strip():
            raise ValueError("artifact_path must be a non-empty relative path")
        normalized = self.artifact_path.replace("\\", "/")
        pieces = normalized.split("/")
        if normalized.startswith("/") or ntpath.splitdrive(normalized)[0] or any(piece in {"", ".", ".."} for piece in pieces):
            raise ValueError("artifact_path must be a normalized relative path without '.' or '..' segments")
        if isinstance(self.runs, bool) or not isinstance(self.runs, int) or not 1 <= self.runs <= 100:
            raise ValueError("runs must be an integer between 1 and 100")
        if self.base_seed is not None:
            if isinstance(self.base_seed, bool) or not isinstance(self.base_seed, int) or self.base_seed < 0:
                raise ValueError("base_seed must be a non-negative integer or None")
        if not isinstance(self.continue_on_error, bool):
            raise TypeError("continue_on_error must be a boolean")
        if not isinstance(self.parameter_sets, tuple) or any(not isinstance(item, ParameterSet) for item in self.parameter_sets):
            raise TypeError("parameter_sets must contain ParameterSet values")
        names = [item.name for item in self.parameter_sets]
        if len(names) != len(set(names)):
            raise ValueError("parameter set names must be unique within a suite member")
        total = self.runs * max(1, len(self.parameter_sets))
        if total > 100:
            raise ValueError("one suite member cannot request more than 100 M9 executions")

    @property
    def total_executions(self) -> int:
        return self.runs * max(1, len(self.parameter_sets))


@dataclass(frozen=True, slots=True)
class SuiteComparison:
    """An explicit user assertion that the same observable is comparable."""

    metric_name: str
    unit: str | None
    semantic_definition: str
    direction: str = "minimize"

    def __post_init__(self) -> None:
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("comparison metric_name must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("comparison unit must be a string or None")
        if not isinstance(self.semantic_definition, str) or len(self.semantic_definition.strip()) < 12:
            raise ValueError("semantic_definition must explain the shared observable in at least 12 characters")
        if self.direction not in {"minimize", "maximize"}:
            raise ValueError("comparison direction must be 'minimize' or 'maximize'")


@dataclass(frozen=True, slots=True)
class ExperimentSuitePlan:
    """A bounded set of independent M8 artifacts to execute and compare."""

    schema_version: int
    suite_name: str
    members: tuple[SuiteMember, ...]
    comparison: SuiteComparison | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M24 suite plan schema_version")
        if not isinstance(self.suite_name, str) or not self.suite_name.strip() or len(self.suite_name) > 120:
            raise ValueError("suite_name must contain 1-120 non-whitespace characters")
        if not isinstance(self.members, tuple) or not 2 <= len(self.members) <= 20:
            raise ValueError("members must contain between 2 and 20 suite members")
        if any(not isinstance(item, SuiteMember) for item in self.members):
            raise TypeError("members must contain SuiteMember values")
        ids = [item.member_id for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("suite member IDs must be unique")
        if self.total_executions > 100:
            raise ValueError("suite plan exceeds the global M9 budget of 100 executions")
        if self.comparison is not None and not isinstance(self.comparison, SuiteComparison):
            raise TypeError("comparison must be a SuiteComparison or None")

    @property
    def total_executions(self) -> int:
        return sum(item.total_executions for item in self.members)


@dataclass(frozen=True, slots=True)
class CategoryCount:
    value: str
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("category value must be a string")
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 1:
            raise ValueError("category count must be a positive integer")


@dataclass(frozen=True, slots=True)
class MetricAggregate:
    member_id: str
    member_label: str
    parameter_set: str
    metric_name: str
    unit: str | None
    value_type: str
    sample_size: int
    mean: float | None = None
    population_stddev: float | None = None
    categories: tuple[CategoryCount, ...] = ()

    def __post_init__(self) -> None:
        for name in ("member_id", "member_label", "parameter_set", "metric_name"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("unit must be a string or None")
        if self.value_type not in {"numeric", "categorical"}:
            raise ValueError("value_type must be numeric or categorical")
        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int) or self.sample_size < 1:
            raise ValueError("sample_size must be a positive integer")
        if not isinstance(self.categories, tuple) or any(not isinstance(item, CategoryCount) for item in self.categories):
            raise TypeError("categories must contain CategoryCount values")
        for name in ("mean", "population_stddev"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
                raise ValueError(f"{name} must be finite or None")
        if self.value_type == "numeric":
            if self.mean is None or self.population_stddev is None or self.population_stddev < 0 or self.categories:
                raise ValueError("numeric aggregates require mean/stddev and no categories")
        else:
            if self.mean is not None or self.population_stddev is not None or not self.categories:
                raise ValueError("categorical aggregates require categories and no mean/stddev")
            if sum(item.count for item in self.categories) != self.sample_size:
                raise ValueError("category counts must sum to sample_size")


@dataclass(frozen=True, slots=True)
class SuiteMemberSummary:
    member_id: str
    label: str
    artifact_path: str
    artifact_id: str | None
    artifact_fingerprint: str | None
    project_id: str | None
    project_title: str | None
    revision_id: str | None
    revision_version: int | None
    paradigm: str | None
    backend_name: str | None
    experiment_id: str | None
    experiment_fingerprint: str | None
    result_file: str | None
    status: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    metrics: tuple[MetricAggregate, ...] = ()
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        for name in ("member_id", "label", "artifact_path"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.status not in {"completed", "partial", "failed"}:
            raise ValueError("unsupported member status")
        for name in ("total_runs", "successful_runs", "failed_runs"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.successful_runs + self.failed_runs != self.total_runs:
            raise ValueError("successful_runs plus failed_runs must equal total_runs")
        if not isinstance(self.metrics, tuple) or any(not isinstance(item, MetricAggregate) for item in self.metrics):
            raise TypeError("metrics must contain MetricAggregate values")
        if self.status == "failed" and self.successful_runs:
            raise ValueError("failed member cannot have successful runs")
        if self.error_type is not None and not isinstance(self.error_type, str):
            raise TypeError("error_type must be a string or None")
        if self.error_message is not None and not isinstance(self.error_message, str):
            raise TypeError("error_message must be a string or None")


@dataclass(frozen=True, slots=True)
class ComparisonEntry:
    rank: int
    member_id: str
    member_label: str
    parameter_set: str
    metric_name: str
    unit: str | None
    mean: float
    population_stddev: float
    sample_size: int

    def __post_init__(self) -> None:
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        for name in ("member_id", "member_label", "parameter_set", "metric_name"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        for name in ("mean", "population_stddev"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.population_stddev < 0:
            raise ValueError("population_stddev must be non-negative")
        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int) or self.sample_size < 1:
            raise ValueError("sample_size must be positive")


@dataclass(frozen=True, slots=True)
class ExperimentSuiteReport:
    schema_version: int
    suite_id: str
    created_at: str
    suite_name: str
    plan: ExperimentSuitePlan
    status: str
    members: tuple[SuiteMemberSummary, ...]
    ranking: tuple[ComparisonEntry, ...]
    warnings: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M24 report schema_version")
        for name in ("suite_id", "created_at", "suite_name", "report_fingerprint"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(self.plan, ExperimentSuitePlan):
            raise TypeError("plan must be an ExperimentSuitePlan")
        if self.status not in {"completed", "partial", "failed"}:
            raise ValueError("unsupported suite report status")
        if not isinstance(self.members, tuple) or len(self.members) != len(self.plan.members):
            raise ValueError("report must contain one summary for every plan member")
        if any(not isinstance(item, SuiteMemberSummary) for item in self.members):
            raise TypeError("members must contain SuiteMemberSummary values")
        if tuple(item.member_id for item in self.members) != tuple(item.member_id for item in self.plan.members):
            raise ValueError("member summaries must preserve plan order and IDs")
        expected_status = (
            "completed" if all(item.status == "completed" for item in self.members)
            else "partial" if any(item.status in {"completed", "partial"} for item in self.members)
            else "failed"
        )
        if self.status != expected_status:
            raise ValueError(f"suite status must be {expected_status} for the recorded members")
        if not isinstance(self.ranking, tuple) or any(not isinstance(item, ComparisonEntry) for item in self.ranking):
            raise TypeError("ranking must contain ComparisonEntry values")
        if self.plan.comparison is None and self.ranking:
            raise ValueError("ranking cannot be present when the plan has no comparison contract")
        if self.plan.comparison is not None:
            if any(item.metric_name != self.plan.comparison.metric_name or item.unit != self.plan.comparison.unit for item in self.ranking):
                raise ValueError("ranking entries must match the plan comparison metric and unit")
            if tuple(item.rank for item in self.ranking) != tuple(range(1, len(self.ranking) + 1)):
                raise ValueError("comparison ranks must be sequential and start at 1")
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) for item in self.warnings):
            raise TypeError("warnings must contain strings")
