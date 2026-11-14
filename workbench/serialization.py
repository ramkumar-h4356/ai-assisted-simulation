"""Strict JSON serialization for M13 workspace manifests."""

from __future__ import annotations

import json
from typing import Any

from workbench.models import ActivityEvent, ArtifactRecord, WorkspaceManifest


class WorkspaceSerializationError(ValueError):
    """Raised when a workspace manifest is malformed or incompatible."""


def manifest_to_dict(manifest: WorkspaceManifest) -> dict[str, Any]:
    if not isinstance(manifest, WorkspaceManifest):
        raise TypeError("manifest must be a WorkspaceManifest")
    return {
        "schema_version": manifest.schema_version,
        "workspace_id": manifest.workspace_id,
        "title": manifest.title,
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
        "original_idea": manifest.original_idea,
        "idea_project_id": manifest.idea_project_id,
        "artifacts": [
            {
                "artifact_id": item.artifact_id,
                "artifact_type": item.artifact_type,
                "display_name": item.display_name,
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
                "created_at": item.created_at,
                "metadata": item.metadata,
            }
            for item in manifest.artifacts
        ],
        "activity": [
            {"event_id": item.event_id, "occurred_at": item.occurred_at,
             "action": item.action, "detail": item.detail}
            for item in manifest.activity
        ],
    }


def dumps_manifest(manifest: WorkspaceManifest, *, indent: int = 2) -> str:
    return json.dumps(manifest_to_dict(manifest), ensure_ascii=False, indent=indent, allow_nan=False)


def _object(raw: Any, required: set[str], path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise WorkspaceSerializationError(f"{path} must be a JSON object")
    missing = required - set(raw)
    unknown = set(raw) - required
    if missing:
        raise WorkspaceSerializationError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
    if unknown:
        raise WorkspaceSerializationError(f"{path} contains unknown field(s): {', '.join(sorted(unknown))}")
    return raw


def manifest_from_dict(raw: Any) -> WorkspaceManifest:
    keys = {"schema_version", "workspace_id", "title", "created_at", "updated_at",
            "original_idea", "idea_project_id", "artifacts", "activity"}
    raw = _object(raw, keys, "workspace_manifest")
    if not isinstance(raw["artifacts"], list) or not isinstance(raw["activity"], list):
        raise WorkspaceSerializationError("artifacts and activity must be arrays")
    artifacts = []
    artifact_keys = {"artifact_id", "artifact_type", "display_name", "relative_path", "sha256", "size_bytes", "created_at", "metadata"}
    for index, item in enumerate(raw["artifacts"]):
        item = _object(item, artifact_keys, f"artifacts[{index}]")
        try:
            artifacts.append(ArtifactRecord(**item))
        except (TypeError, ValueError) as error:
            raise WorkspaceSerializationError(f"artifacts[{index}] is invalid: {error}") from error
    activity = []
    activity_keys = {"event_id", "occurred_at", "action", "detail"}
    for index, item in enumerate(raw["activity"]):
        item = _object(item, activity_keys, f"activity[{index}]")
        try:
            activity.append(ActivityEvent(**item))
        except (TypeError, ValueError) as error:
            raise WorkspaceSerializationError(f"activity[{index}] is invalid: {error}") from error
    try:
        return WorkspaceManifest(
            schema_version=raw["schema_version"], workspace_id=raw["workspace_id"],
            title=raw["title"], created_at=raw["created_at"], updated_at=raw["updated_at"],
            original_idea=raw["original_idea"], idea_project_id=raw["idea_project_id"],
            artifacts=tuple(artifacts), activity=tuple(activity),
        )
    except (TypeError, ValueError) as error:
        raise WorkspaceSerializationError(f"workspace manifest is invalid: {error}") from error


def loads_manifest(content: str) -> WorkspaceManifest:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise WorkspaceSerializationError(f"Invalid workspace JSON: {error}") from error
    return manifest_from_dict(raw)
