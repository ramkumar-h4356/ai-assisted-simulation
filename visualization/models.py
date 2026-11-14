"""Validated, engine-independent dashboard data contracts (M12)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualizationBundle:
    schema_version: int
    bundle_id: str
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
    data: dict[str, Any]
    warnings: tuple[str, ...]
    bundle_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported visualization bundle schema_version")
        for name in (
            "bundle_id", "created_at", "artifact_id", "artifact_fingerprint",
            "project_id", "project_title", "revision_id", "paradigm",
            "backend_name", "experiment_id", "experiment_fingerprint",
            "bundle_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if not isinstance(self.data, dict):
            raise TypeError("data must be a JSON object")
        required = {"runs", "metric_series", "trace_views", "m10", "m11"}
        if set(self.data) != required:
            raise ValueError("data must contain exactly runs, metric_series, trace_views, m10 and m11")
        for name in ("runs", "metric_series", "trace_views"):
            if not isinstance(self.data[name], list):
                raise TypeError(f"data.{name} must be an array")
        if self.data["m10"] is not None and not isinstance(self.data["m10"], dict):
            raise TypeError("data.m10 must be an object or None")
        if self.data["m11"] is not None and not isinstance(self.data["m11"], dict):
            raise TypeError("data.m11 must be an object or None")
        try:
            copied = json.loads(json.dumps(self.data, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise ValueError(f"data must contain finite JSON-compatible values: {error}") from error
        object.__setattr__(self, "data", copied)
        if not isinstance(self.warnings, tuple) or any(not isinstance(item, str) for item in self.warnings):
            raise TypeError("warnings must be a tuple of strings")
