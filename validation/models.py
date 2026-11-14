"""Typed contracts for M26 simulation model verification and validation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import ntpath
import json


_CHECK_TYPES = {"non_negative", "bounds", "monotonic", "conserved_sum"}
_DIRECTIONS = {"increasing", "decreasing", "nondecreasing", "nonincreasing"}


def _relative_path(value: str, name: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or ntpath.splitdrive(normalized)[0] or ":" in normalized:
        raise ValueError(f"{name} must be a relative path")
    parts = normalized.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{name} must be a normalized relative path without empty, '.' or '..' segments")


@dataclass(frozen=True, slots=True)
class InvariantSpec:
    """Declarative, non-executable assertion over a saved M9 trace.

    Path grammar uses dotted object keys and ``[]`` to expand list entries,
    e.g. ``time_series[].stocks.susceptible``. No expression evaluation occurs.
    """

    check_id: str
    check_type: str
    trace_path: str
    fields: tuple[str, ...] = ()
    expected_value: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    direction: str = "increasing"
    tolerance: float = 1e-8

    def __post_init__(self) -> None:
        for name in ("check_id", "check_type", "trace_path"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if len(self.check_id) > 64:
            raise ValueError("check_id must not exceed 64 characters")
        if self.check_type not in _CHECK_TYPES:
            raise ValueError(f"check_type must be one of {', '.join(sorted(_CHECK_TYPES))}")
        if not isinstance(self.fields, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.fields):
            raise TypeError("fields must be a tuple of non-empty strings")
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("fields must not contain duplicates")
        for name in ("expected_value", "minimum", "maximum", "tolerance"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
                raise ValueError(f"{name} must be finite numeric data")
        if self.tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        if self.check_type == "bounds":
            if self.minimum is None and self.maximum is None:
                raise ValueError("bounds check requires minimum and/or maximum")
            if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
                raise ValueError("minimum must not exceed maximum")
        if self.check_type == "monotonic" and self.direction not in _DIRECTIONS:
            raise ValueError(f"direction must be one of {', '.join(sorted(_DIRECTIONS))}")
        if self.check_type == "conserved_sum":
            if not self.fields:
                raise ValueError("conserved_sum requires one or more field names")
            if self.expected_value is None:
                raise ValueError("conserved_sum requires expected_value")


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    schema_version: int
    validation_name: str
    artifact_path: str
    execution_result_path: str | None = None
    execute_if_missing: bool = True
    execution_runs: int = 1
    execution_base_seed: int | None = None
    repeatability_check: bool = False
    repeatability_tolerance: float = 1e-12
    invariants: tuple[InvariantSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M26 validation plan schema_version")
        if not isinstance(self.validation_name, str) or not self.validation_name.strip() or len(self.validation_name) > 120:
            raise ValueError("validation_name must contain 1-120 non-whitespace characters")
        _relative_path(self.artifact_path, "artifact_path")
        _relative_path(self.execution_result_path, "execution_result_path", optional=True)
        if not isinstance(self.execute_if_missing, bool) or not isinstance(self.repeatability_check, bool):
            raise TypeError("execute_if_missing and repeatability_check must be booleans")
        if isinstance(self.execution_runs, bool) or not isinstance(self.execution_runs, int) or not 1 <= self.execution_runs <= 20:
            raise ValueError("execution_runs must be between 1 and 20")
        if self.execution_base_seed is not None:
            if isinstance(self.execution_base_seed, bool) or not isinstance(self.execution_base_seed, int) or self.execution_base_seed < 0:
                raise ValueError("execution_base_seed must be a non-negative integer or None")
        if isinstance(self.repeatability_tolerance, bool) or not isinstance(self.repeatability_tolerance, (int, float)) or not isfinite(self.repeatability_tolerance) or self.repeatability_tolerance < 0:
            raise ValueError("repeatability_tolerance must be finite and non-negative")
        if not isinstance(self.invariants, tuple) or len(self.invariants) > 50 or any(not isinstance(item, InvariantSpec) for item in self.invariants):
            raise ValueError("invariants must be a tuple of at most 50 InvariantSpec values")
        if len({item.check_id for item in self.invariants}) != len(self.invariants):
            raise ValueError("invariant check IDs must be unique")
        if self.execution_result_path is None and not self.execute_if_missing:
            raise ValueError("Provide execution_result_path or enable execute_if_missing")
        if self.execution_result_path is not None and self.execute_if_missing:
            # Explicit result inputs are read-only; rerunning must be an explicit
            # repeatability check, not an accidental replacement of evidence.
            object.__setattr__(self, "execute_if_missing", False)


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    check_id: str
    category: str
    status: str
    message: str
    details: dict

    def __post_init__(self) -> None:
        for name in ("check_id", "category", "status", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.status not in {"passed", "failed", "warning", "skipped"}:
            raise ValueError("status must be passed, failed, warning or skipped")
        if not isinstance(self.details, dict):
            raise TypeError("details must be an object")
        try:
            copied = json.loads(json.dumps(self.details, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"details must be finite JSON data: {error}") from error
        object.__setattr__(self, "details", copied)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    schema_version: int
    validation_id: str
    created_at: str
    validation_name: str
    overall_status: str
    artifact_id: str
    artifact_fingerprint: str
    model_fingerprint: str
    project_id: str
    revision_id: str
    paradigm: str
    backend_name: str
    experiment_id: str | None
    result_fingerprint: str | None
    repeatability_experiment_id: str | None
    repeatability_result_fingerprint: str | None
    checks: tuple[ValidationCheck, ...]
    interpretation_limits: tuple[str, ...]
    report_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported M26 validation report schema_version")
        for name in ("validation_id", "created_at", "validation_name", "overall_status", "artifact_id",
                     "artifact_fingerprint", "model_fingerprint", "project_id", "revision_id", "paradigm",
                     "backend_name", "report_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.overall_status not in {"passed", "passed_with_warnings", "failed"}:
            raise ValueError("overall_status must be passed, passed_with_warnings or failed")
        for name in ("experiment_id", "result_fingerprint", "repeatability_experiment_id", "repeatability_result_fingerprint"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")
        if not isinstance(self.checks, tuple) or any(not isinstance(item, ValidationCheck) for item in self.checks):
            raise TypeError("checks must be a tuple of ValidationCheck values")
        if not self.checks:
            raise ValueError("validation report must contain at least one check")
        if not isinstance(self.interpretation_limits, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.interpretation_limits):
            raise TypeError("interpretation_limits must be a tuple of non-empty strings")
