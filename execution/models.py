"""Validated contracts for controlled, traceable simulation experiments (M9)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
import json
from typing import Any


class RunStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ParameterOverride:
    """One explicit experiment value override on a bound native-model path."""

    target_path: str
    value: str | int | float | bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("parameter target_path must be non-empty")
        if not isinstance(self.value, (str, int, float, bool, type(None))):
            raise TypeError("parameter override values must be JSON-compatible scalars")
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("parameter override values must be finite")


@dataclass(frozen=True, slots=True)
class ParameterSet:
    """Named combination of explicitly approved experiment parameter values."""

    name: str
    overrides: tuple[ParameterOverride, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("parameter set name must be non-empty")
        if not isinstance(self.overrides, tuple) or any(not isinstance(item, ParameterOverride) for item in self.overrides):
            raise TypeError("overrides must be a tuple of ParameterOverride values")
        paths = [item.target_path for item in self.overrides]
        if len(paths) != len(set(paths)):
            raise ValueError("a parameter set cannot override the same target path more than once")


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Execution controls. ABM runs use consecutive seeds from the base seed."""

    runs: int = 1
    base_seed: int | None = None
    continue_on_error: bool = True
    parameter_sets: tuple[ParameterSet, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.runs, bool) or not isinstance(self.runs, int):
            raise TypeError("runs must be an integer")
        if not 1 <= self.runs <= 100:
            raise ValueError("runs must be between 1 and 100")
        if self.base_seed is not None:
            if isinstance(self.base_seed, bool) or not isinstance(self.base_seed, int):
                raise TypeError("base_seed must be an integer or None")
            if self.base_seed < 0:
                raise ValueError("base_seed must be non-negative")
        if not isinstance(self.continue_on_error, bool):
            raise TypeError("continue_on_error must be a boolean")
        if not isinstance(self.parameter_sets, tuple) or any(not isinstance(item, ParameterSet) for item in self.parameter_sets):
            raise TypeError("parameter_sets must be a tuple of ParameterSet values")
        names = [item.name for item in self.parameter_sets]
        if len(names) != len(set(names)):
            raise ValueError("parameter set names must be unique")
        if self.total_runs > 100:
            raise ValueError("runs multiplied by parameter sets must not exceed 100 total executions")

    @property
    def total_runs(self) -> int:
        return self.runs * max(1, len(self.parameter_sets))


@dataclass(frozen=True, slots=True)
class MetricRecord:
    name: str
    value: str | int | float | bool
    unit: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("metric name must be non-empty")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("metric unit must be a string or None")
        if not isinstance(self.value, (str, int, float, bool)):
            raise TypeError("metric value must be a string, number or boolean")
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("metric value must be finite")


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_index: int
    status: RunStatus
    seed: int | None
    parameter_set: str
    parameters: dict[str, str | int | float | bool | None]
    started_at: str
    finished_at: str
    elapsed_seconds: float
    metrics: tuple[MetricRecord, ...]
    trace: dict[str, Any]
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.run_index, bool) or not isinstance(self.run_index, int) or self.run_index < 1:
            raise ValueError("run_index must be a positive integer")
        if not isinstance(self.status, RunStatus):
            raise TypeError("status must be a RunStatus")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0):
            raise ValueError("seed must be a non-negative integer or None")
        if not isinstance(self.parameter_set, str) or not self.parameter_set.strip():
            raise ValueError("parameter_set must be a non-empty string")
        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a JSON object")
        if any(not isinstance(key, str) for key in self.parameters):
            raise TypeError("parameter keys must be strings")
        try:
            parameters_copy = json.loads(json.dumps(self.parameters, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"parameters must contain finite JSON data: {error}") from error
        if any(not isinstance(value, (str, int, float, bool, type(None))) for value in parameters_copy.values()):
            raise TypeError("parameter values must be JSON-compatible scalars")
        object.__setattr__(self, "parameters", parameters_copy)
        for name in ("started_at", "finished_at"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.elapsed_seconds, bool) or not isinstance(self.elapsed_seconds, (int, float)) or not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and non-negative")
        if not isinstance(self.metrics, tuple) or any(not isinstance(item, MetricRecord) for item in self.metrics):
            raise TypeError("metrics must be a tuple of MetricRecord values")
        if not isinstance(self.trace, dict):
            raise TypeError("trace must be a JSON object")
        try:
            frozen_trace = json.loads(json.dumps(self.trace, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"trace must contain finite JSON data: {error}") from error
        object.__setattr__(self, "trace", frozen_trace)
        if self.status is RunStatus.COMPLETED and (self.error_type is not None or self.error_message is not None):
            raise ValueError("completed runs must not contain error details")
        if self.status is RunStatus.FAILED and (not self.error_type or not self.error_message):
            raise ValueError("failed runs require error_type and error_message")


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    schema_version: int
    experiment_id: str
    created_at: str
    artifact_id: str
    artifact_fingerprint: str
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    paradigm: str
    backend_name: str
    config: ExperimentConfig
    status: ExperimentStatus
    runs: tuple[RunRecord, ...]
    result_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported experiment result schema_version")
        for name in (
            "experiment_id", "created_at", "artifact_id", "artifact_fingerprint",
            "project_id", "project_title", "revision_id", "paradigm", "backend_name",
            "result_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if not isinstance(self.config, ExperimentConfig):
            raise TypeError("config must be an ExperimentConfig")
        if not isinstance(self.status, ExperimentStatus):
            raise TypeError("status must be an ExperimentStatus")
        if not isinstance(self.runs, tuple) or any(not isinstance(item, RunRecord) for item in self.runs):
            raise TypeError("runs must be a tuple of RunRecord values")
        if not self.runs or len(self.runs) > self.config.total_runs:
            raise ValueError("runs must contain at least one record and not exceed configured total runs")
        if tuple(item.run_index for item in self.runs) != tuple(range(1, len(self.runs) + 1)):
            raise ValueError("run_index values must be sequential and start at 1")
        successful = sum(item.status is RunStatus.COMPLETED for item in self.runs)
        expected_status = (
            ExperimentStatus.COMPLETED
            if successful == len(self.runs) == self.config.total_runs
            else ExperimentStatus.FAILED
            if successful == 0
            else ExperimentStatus.PARTIAL
        )
        if self.status is not expected_status:
            raise ValueError(f"experiment status must be {expected_status.value} for its recorded runs")
