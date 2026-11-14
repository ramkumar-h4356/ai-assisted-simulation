"""Typed contracts for M13 project workspaces and their artifact ledger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any


class ArtifactType(str, Enum):
    IDEA_PROJECT = "idea_project"
    IDEA_SESSION = "idea_session"
    KNOWLEDGE_BASE = "knowledge_base"
    READINESS_REPORT = "readiness_report"
    COMPILATION_PROFILE = "compilation_profile"
    COMPILATION_ARTIFACT = "compilation_artifact"
    EXECUTION_RESULT = "execution_result"
    ANALYSIS_REPORT = "analysis_report"
    UNCERTAINTY_PLAN = "uncertainty_plan"
    UNCERTAINTY_REPORT = "uncertainty_report"
    VISUALIZATION_BUNDLE = "visualization_bundle"
    VISUALIZATION_HTML = "visualization_html"
    OTHER = "other"


class StageStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NOT_STARTED = "not_started"


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    display_name: str
    relative_path: str
    sha256: str
    size_bytes: int
    created_at: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        for name in ("artifact_id", "artifact_type", "display_name", "relative_path", "sha256", "created_at"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("sha256 must be a lowercase hexadecimal SHA-256 digest")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dictionary")
        try:
            json.dumps(self.metadata, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError(f"metadata must be finite JSON-compatible data: {error}") from error


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    event_id: str
    occurred_at: str
    action: str
    detail: str

    def __post_init__(self) -> None:
        for name in ("event_id", "occurred_at", "action", "detail"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    schema_version: int
    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    original_idea: str
    idea_project_id: str | None
    artifacts: tuple[ArtifactRecord, ...]
    activity: tuple[ActivityEvent, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported workspace manifest schema_version")
        for name in ("workspace_id", "title", "created_at", "updated_at", "original_idea"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.idea_project_id is not None and (not isinstance(self.idea_project_id, str) or not self.idea_project_id.strip()):
            raise ValueError("idea_project_id must be a non-empty string or None")
        if not isinstance(self.artifacts, tuple) or any(not isinstance(item, ArtifactRecord) for item in self.artifacts):
            raise TypeError("artifacts must be a tuple of ArtifactRecord values")
        ids = [item.artifact_id for item in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("artifact IDs must be unique")
        if not isinstance(self.activity, tuple) or any(not isinstance(item, ActivityEvent) for item in self.activity):
            raise TypeError("activity must be a tuple of ActivityEvent values")


@dataclass(frozen=True, slots=True)
class WorkflowStage:
    key: str
    title: str
    status: StageStatus
    artifact_count: int
    explanation: str


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    artifact_id: str
    relative_path: str
    valid: bool
    message: str


@dataclass(frozen=True, slots=True)
class WorkspaceOverview:
    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    idea_project_id: str | None
    artifact_count: int
    stages: tuple[WorkflowStage, ...]
    recent_activity: tuple[ActivityEvent, ...]
