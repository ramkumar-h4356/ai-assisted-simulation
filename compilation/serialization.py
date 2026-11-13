"""Strict JSON serialization for M8 compilation profiles and artifacts."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

from compilation.models import (
    BindingSource, CompilationArtifact, CompilationParadigm, CompilationProfile,
    ElementBinding,
)


class CompilationSerializationError(ValueError):
    pass


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    return value


def profile_to_dict(profile: CompilationProfile) -> dict[str, Any]:
    if not isinstance(profile, CompilationProfile):
        raise TypeError("profile must be a CompilationProfile")
    return _primitive(profile)


def dumps_profile(profile: CompilationProfile, *, indent: int = 2) -> str:
    return json.dumps(profile_to_dict(profile), ensure_ascii=False, indent=indent, allow_nan=False)


def _strict_object(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CompilationSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    unknown = set(raw) - allowed
    missing = allowed - set(raw)
    if unknown:
        raise CompilationSerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise CompilationSerializationError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
    return raw


def _string_list(raw: Any, path: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise CompilationSerializationError(f"{path} must be an array of strings")
    return tuple(raw)


def _binding(raw: Any, path: str) -> ElementBinding:
    raw = _strict_object(raw, ElementBinding, path)
    try:
        return ElementBinding(
            target_path=raw["target_path"],
            source=BindingSource(raw["source"]),
            element_ids=_string_list(raw["element_ids"], f"{path}.element_ids"),
            note=raw["note"],
        )
    except (TypeError, ValueError) as error:
        raise CompilationSerializationError(f"{path} is invalid: {error}") from error


def profile_from_dict(raw: Any) -> CompilationProfile:
    raw = _strict_object(raw, CompilationProfile, "compilation_profile")
    if not isinstance(raw["bindings"], list):
        raise CompilationSerializationError("bindings must be an array")
    try:
        return CompilationProfile(
            profile_id=raw["profile_id"], project_id=raw["project_id"], revision_id=raw["revision_id"],
            paradigm=CompilationParadigm(raw["paradigm"]), model_data=raw["model_data"],
            bindings=tuple(_binding(item, f"bindings[{index}]") for index, item in enumerate(raw["bindings"])),
        )
    except (TypeError, ValueError) as error:
        raise CompilationSerializationError(f"compilation profile is invalid: {error}") from error


def loads_profile(content: str) -> CompilationProfile:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise CompilationSerializationError(f"Invalid profile JSON: {error}") from error
    return profile_from_dict(raw)


def save_profile(profile: CompilationProfile, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_profile(profile), encoding="utf-8")
    return destination


def load_profile(path: str | Path) -> CompilationProfile:
    source = Path(path)
    try:
        return loads_profile(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read compilation profile at {source}: {error}") from error


def artifact_to_dict(artifact: CompilationArtifact) -> dict[str, Any]:
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    return _primitive(artifact)


def dumps_artifact(artifact: CompilationArtifact, *, indent: int = 2) -> str:
    return json.dumps(artifact_to_dict(artifact), ensure_ascii=False, indent=indent, allow_nan=False)


def artifact_from_dict(raw: Any) -> CompilationArtifact:
    raw = _strict_object(raw, CompilationArtifact, "compilation_artifact")
    if not isinstance(raw["bindings"], list):
        raise CompilationSerializationError("bindings must be an array")
    try:
        return CompilationArtifact(
            schema_version=raw["schema_version"], artifact_id=raw["artifact_id"], created_at=raw["created_at"],
            project_id=raw["project_id"], project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], profile_id=raw["profile_id"],
            paradigm=CompilationParadigm(raw["paradigm"]), backend_name=raw["backend_name"],
            m7_readiness_status=raw["m7_readiness_status"], paradigm_fit=raw["paradigm_fit"],
            model_data=raw["model_data"],
            bindings=tuple(_binding(item, f"bindings[{index}]") for index, item in enumerate(raw["bindings"])),
            model_fingerprint=raw["model_fingerprint"], artifact_fingerprint=raw["artifact_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise CompilationSerializationError(f"compilation artifact is invalid: {error}") from error


def loads_artifact(content: str) -> CompilationArtifact:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise CompilationSerializationError(f"Invalid artifact JSON: {error}") from error
    return artifact_from_dict(raw)


def save_artifact(artifact: CompilationArtifact, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_artifact(artifact), encoding="utf-8")
    return destination


def load_artifact(path: str | Path) -> CompilationArtifact:
    source = Path(path)
    try:
        artifact = loads_artifact(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read compilation artifact at {source}: {error}") from error
    from compilation.compiler import verify_artifact
    if not verify_artifact(artifact):
        raise CompilationSerializationError("Artifact integrity fingerprint does not match its stored content")
    return artifact
