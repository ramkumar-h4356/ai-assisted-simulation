"""Data contracts for traceable conceptual-to-executable compilation (M8)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import json


class CompilationParadigm(str, Enum):
    DISCRETE_EVENT = "discrete_event"
    AGENT_BASED = "agent_based"
    MATHEMATICAL = "mathematical"
    DATA_DRIVEN = "data_driven"


class BindingSource(str, Enum):
    CONCEPTUAL_ELEMENT = "conceptual_element"
    USER_PARAMETER = "user_parameter"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ElementBinding:
    """Explain where one target-model field or subtree came from."""

    target_path: str
    source: BindingSource
    element_ids: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.target_path, str) or not self.target_path.strip():
            raise ValueError("target_path must be a non-empty string")
        if not isinstance(self.source, BindingSource):
            raise TypeError("source must be a BindingSource")
        if not isinstance(self.element_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.element_ids
        ):
            raise TypeError("element_ids must be a tuple of non-empty strings")
        if len(self.element_ids) != len(set(self.element_ids)):
            raise ValueError("element_ids must not contain duplicates")
        if not isinstance(self.note, str):
            raise TypeError("note must be a string")
        if self.source is BindingSource.CONCEPTUAL_ELEMENT and not self.element_ids:
            raise ValueError("conceptual_element bindings require at least one element_id")
        if self.source is BindingSource.USER_PARAMETER and self.element_ids:
            raise ValueError("user_parameter bindings must not contain element_ids")
        if self.source is BindingSource.USER_PARAMETER and not self.note.strip():
            raise ValueError("user_parameter bindings require a note explaining the parameter")


@dataclass(frozen=True, slots=True)
class CompilationProfile:
    """User-approved target model plus explicit conceptual provenance."""

    profile_id: str
    project_id: str
    revision_id: str
    paradigm: CompilationParadigm
    model_data: dict[str, Any]
    bindings: tuple[ElementBinding, ...]

    def __post_init__(self) -> None:
        for name in ("profile_id", "project_id", "revision_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.paradigm, CompilationParadigm):
            raise TypeError("paradigm must be a CompilationParadigm")
        if not isinstance(self.model_data, dict):
            raise TypeError("model_data must be a JSON object")
        try:
            # Reject NaN, infinity, custom Python objects and non-JSON data.
            canonical = json.dumps(self.model_data, ensure_ascii=False, allow_nan=False)
            copied = json.loads(canonical)
        except (TypeError, ValueError) as error:
            raise ValueError(f"model_data must contain finite JSON-compatible values: {error}") from error
        object.__setattr__(self, "model_data", copied)
        if not isinstance(self.bindings, tuple) or any(
            not isinstance(item, ElementBinding) for item in self.bindings
        ):
            raise TypeError("bindings must be a tuple of ElementBinding values")
        paths = [item.target_path for item in self.bindings]
        if len(paths) != len(set(paths)):
            raise ValueError("Only one binding may be declared for each target_path")


@dataclass(frozen=True, slots=True)
class CompilationIssue:
    code: str
    severity: IssueSeverity
    path: str
    message: str
    element_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("code", "path", "message"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.severity, IssueSeverity):
            raise TypeError("severity must be an IssueSeverity")
        if not isinstance(self.element_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.element_ids
        ):
            raise TypeError("element_ids must be a tuple of non-empty strings")


@dataclass(frozen=True, slots=True)
class CompilationArtifact:
    """Portable, revision-bound record of a validated target specification."""

    schema_version: int
    artifact_id: str
    created_at: str
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    profile_id: str
    paradigm: CompilationParadigm
    backend_name: str
    m7_readiness_status: str
    paradigm_fit: str
    model_data: dict[str, Any]
    bindings: tuple[ElementBinding, ...]
    model_fingerprint: str
    artifact_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported compilation artifact schema_version")
        for name in (
            "artifact_id", "created_at", "project_id", "project_title", "revision_id",
            "profile_id", "backend_name", "m7_readiness_status", "paradigm_fit", "model_fingerprint", "artifact_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if not isinstance(self.paradigm, CompilationParadigm):
            raise TypeError("paradigm must be a CompilationParadigm")
        if not isinstance(self.model_data, dict):
            raise TypeError("model_data must be an object")
        try:
            object.__setattr__(self, "model_data", json.loads(json.dumps(self.model_data, allow_nan=False)))
        except (TypeError, ValueError) as error:
            raise ValueError(f"model_data is not finite JSON data: {error}") from error
        if not isinstance(self.bindings, tuple) or any(not isinstance(item, ElementBinding) for item in self.bindings):
            raise TypeError("bindings must be a tuple of ElementBinding values")


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """Compilation outcome; native_specification is set only after full validation."""

    artifact: CompilationArtifact | None
    native_specification: Any | None
    issues: tuple[CompilationIssue, ...]

    @property
    def is_ready(self) -> bool:
        return self.artifact is not None and self.native_specification is not None and not any(
            item.severity is IssueSeverity.ERROR for item in self.issues
        )

    @property
    def errors(self) -> tuple[CompilationIssue, ...]:
        return tuple(item for item in self.issues if item.severity is IssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[CompilationIssue, ...]:
        return tuple(item for item in self.issues if item.severity is IssueSeverity.WARNING)
