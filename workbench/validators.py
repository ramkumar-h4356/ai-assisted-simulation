"""M13 artifact validation adapters for existing milestone formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from workbench.models import ArtifactType


class ArtifactValidationError(ValueError):
    """Raised when an imported milestone artifact cannot be validated."""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactValidationError(f"Could not read valid UTF-8 JSON: {error}") from error


def _idea_project(path: Path) -> dict[str, Any]:
    from conceptual import load_idea_project, validate_idea_project
    project = load_idea_project(path)
    validation = validate_idea_project(project)
    return {
        "project_id": project.id, "project_title": project.title,
        "original_statement": project.original_statement,
        "revision_id": project.current_revision.id,
        "revision_version": project.current_revision.version,
        "revision_ids": [item.id for item in project.revisions],
        "revision_versions": [item.version for item in project.revisions],
        "mapping_count": len(project.current_revision.mappings),
        "evidence_reference_count": len(project.current_revision.evidence_references),
        "open_question_count": len(project.current_revision.open_questions),
        "validation_readiness": validation.readiness.value,
        "validation_error_count": len(validation.errors),
        "validation_warning_count": len(validation.warnings),
    }


def _idea_session(path: Path) -> dict[str, Any]:
    from idea_assistant import load_session
    session = load_session(path)
    return {"project_id": session.project_id, "session_id": session.id,
            "clarification_count": len(session.clarification_history)}



def _knowledge_base(path: Path) -> dict[str, Any]:
    from knowledge import load_knowledge_base
    base = load_knowledge_base(path)
    return {
        "knowledge_base_id": base.id,
        "knowledge_base_name": base.name,
        "document_count": len(base.documents),
    }


def _readiness(path: Path) -> dict[str, Any]:
    from readiness import load_report
    report = load_report(path)
    return {"project_id": report.project_id, "revision_id": report.revision_id,
            "revision_version": report.revision_version, "readiness_status": report.status.value,
            "selected_paradigm": report.selected_paradigm.value if report.selected_paradigm else None,
            "recommended_paradigms": [item.value for item in report.recommended_paradigms]}


def _profile(path: Path) -> dict[str, Any]:
    from compilation import load_profile
    profile = load_profile(path)
    return {"project_id": profile.project_id, "revision_id": profile.revision_id,
            "profile_id": profile.profile_id, "paradigm": profile.paradigm.value}


def _compilation(path: Path) -> dict[str, Any]:
    from compilation import load_artifact
    artifact = load_artifact(path)
    return {"project_id": artifact.project_id, "revision_id": artifact.revision_id,
            "revision_version": artifact.revision_version, "artifact_id": artifact.artifact_id,
            "artifact_fingerprint": artifact.artifact_fingerprint,
            "paradigm": artifact.paradigm.value, "backend_name": artifact.backend_name,
            "m7_readiness_status": artifact.m7_readiness_status}


def _execution(path: Path) -> dict[str, Any]:
    from execution import load_result
    result = load_result(path)
    return {"project_id": result.project_id, "revision_id": result.revision_id,
            "revision_version": result.revision_version, "experiment_id": result.experiment_id,
            "artifact_id": result.artifact_id, "artifact_fingerprint": result.artifact_fingerprint,
            "result_fingerprint": result.result_fingerprint, "paradigm": result.paradigm,
            "run_count": len(result.runs), "successful_run_count": sum(item.status.value == "completed" for item in result.runs)}


def _analysis(path: Path) -> dict[str, Any]:
    from experimentation import load_report
    report = load_report(path)
    return {"project_id": report.project_id, "revision_id": report.revision_id,
            "analysis_id": report.analysis_id, "artifact_id": report.artifact_id,
            "artifact_fingerprint": report.artifact_fingerprint,
            "input_experiment_ids": list(report.input_experiment_ids),
            "input_result_fingerprints": list(report.input_result_fingerprints)}


def _uncertainty_plan(path: Path) -> dict[str, Any]:
    from uncertainty.serialization import plan_from_dict
    plan = plan_from_dict(_json(path))
    return {"sample_count": plan.sample_count, "sampling_seed": plan.sampling_seed,
            "parameter_count": len(plan.parameters)}


def _uncertainty_report(path: Path) -> dict[str, Any]:
    from uncertainty import load_report
    report = load_report(path)
    return {"project_id": report.project_id, "revision_id": report.revision_id,
            "report_id": report.report_id, "artifact_id": report.artifact_id,
            "artifact_fingerprint": report.artifact_fingerprint,
            "experiment_id": report.experiment_id,
            "experiment_fingerprint": report.experiment_fingerprint,
            "sample_count": report.sample_count}


def _visualization_bundle(path: Path) -> dict[str, Any]:
    from visualization import load_bundle
    bundle = load_bundle(path)
    return {"project_id": bundle.project_id, "revision_id": bundle.revision_id,
            "bundle_id": bundle.bundle_id, "artifact_id": bundle.artifact_id,
            "artifact_fingerprint": bundle.artifact_fingerprint,
            "experiment_id": bundle.experiment_id,
            "experiment_fingerprint": bundle.experiment_fingerprint,
            "paradigm": bundle.paradigm}


def _visualization_html(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArtifactValidationError(f"Could not read HTML dashboard: {error}") from error
    lowered = content.lstrip().lower()
    if "<html" not in lowered or "</html>" not in lowered:
        raise ArtifactValidationError("File does not appear to contain a complete HTML document")
    return {"format": "standalone_html", "size_characters": len(content)}


_VALIDATORS: dict[ArtifactType, Callable[[Path], dict[str, Any]]] = {
    ArtifactType.IDEA_PROJECT: _idea_project,
    ArtifactType.IDEA_SESSION: _idea_session,
    ArtifactType.KNOWLEDGE_BASE: _knowledge_base,
    ArtifactType.READINESS_REPORT: _readiness,
    ArtifactType.COMPILATION_PROFILE: _profile,
    ArtifactType.COMPILATION_ARTIFACT: _compilation,
    ArtifactType.EXECUTION_RESULT: _execution,
    ArtifactType.ANALYSIS_REPORT: _analysis,
    ArtifactType.UNCERTAINTY_PLAN: _uncertainty_plan,
    ArtifactType.UNCERTAINTY_REPORT: _uncertainty_report,
    ArtifactType.VISUALIZATION_BUNDLE: _visualization_bundle,
    ArtifactType.VISUALIZATION_HTML: _visualization_html,
}


def validate_artifact(path: str | Path, artifact_type: ArtifactType | str) -> dict[str, Any]:
    source = Path(path)
    try:
        resolved_type = artifact_type if isinstance(artifact_type, ArtifactType) else ArtifactType(artifact_type)
    except ValueError as error:
        raise ArtifactValidationError(f"Unsupported artifact type: {artifact_type!r}") from error
    if not source.is_file():
        raise ArtifactValidationError(f"Artifact file does not exist: {source}")
    validator = _VALIDATORS.get(resolved_type)
    if validator is None:
        if resolved_type is ArtifactType.OTHER:
            return {"format": source.suffix.lstrip(".") or "unknown"}
        raise ArtifactValidationError(f"No validator is registered for artifact type {resolved_type.value!r}")
    try:
        return validator(source)
    except ArtifactValidationError:
        raise
    except Exception as error:
        raise ArtifactValidationError(f"{resolved_type.value} validation failed: {error}") from error
