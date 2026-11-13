"""Deterministic, provenance-aware compilation into existing DES and ABM models.

M8 deliberately requires an explicit CompilationProfile. It does not convert
natural-language descriptions into operational semantics or invent parameter
values. The profile is checked against the exact conceptual revision, M7's
implementation-planning gate, and the target backend's real model validators.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from conceptual.model import IdeaProject
from readiness.engine import assess_readiness
from readiness.models import Paradigm, ReadinessStatus
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.des.schema import scenario_from_dict
from simulations.abm.schema import agent_model_from_dict, normalize_agent_model_data
from simulations.abm.validation import validate_agent_model

from compilation.models import (
    BindingSource, CompilationArtifact, CompilationIssue, CompilationParadigm,
    CompilationProfile, CompilationResult, ElementBinding, IssueSeverity,
)


_BACKEND_NAMES = {
    CompilationParadigm.DISCRETE_EVENT: "DES V1 / SimPy backend",
    CompilationParadigm.AGENT_BASED: "ABM V1 backend",
}
_SIMULATION_PARADIGMS = {
    CompilationParadigm.DISCRETE_EVENT: SimulationParadigm.DISCRETE_EVENT,
    CompilationParadigm.AGENT_BASED: SimulationParadigm.AGENT_BASED,
}
_READINESS_PARADIGMS = {
    CompilationParadigm.DISCRETE_EVENT: Paradigm.DISCRETE_EVENT,
    CompilationParadigm.AGENT_BASED: Paradigm.AGENT_BASED,
    CompilationParadigm.MATHEMATICAL: Paradigm.MATHEMATICAL,
    CompilationParadigm.DATA_DRIVEN: Paradigm.DATA_DRIVEN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint_model(paradigm: CompilationParadigm, model_data: dict[str, Any]) -> str:
    payload = {"paradigm": paradigm.value, "model_data": model_data}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def fingerprint_artifact(artifact: CompilationArtifact) -> str:
    """Fingerprint every artifact field except the fingerprint itself."""
    payload = {
        "schema_version": artifact.schema_version,
        "artifact_id": artifact.artifact_id,
        "created_at": artifact.created_at,
        "project_id": artifact.project_id,
        "project_title": artifact.project_title,
        "revision_id": artifact.revision_id,
        "revision_version": artifact.revision_version,
        "profile_id": artifact.profile_id,
        "paradigm": artifact.paradigm.value,
        "backend_name": artifact.backend_name,
        "m7_readiness_status": artifact.m7_readiness_status,
        "paradigm_fit": artifact.paradigm_fit,
        "model_data": artifact.model_data,
        "bindings": [
            {"target_path": item.target_path, "source": item.source.value,
             "element_ids": list(item.element_ids), "note": item.note}
            for item in artifact.bindings
        ],
        "model_fingerprint": artifact.model_fingerprint,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _source_element_ids(project: IdeaProject) -> set[str]:
    revision = project.current_revision
    names = (
        "concepts", "properties", "relationships", "mechanisms", "hypotheses",
        "assumptions", "constraints", "evidence_references", "mappings",
        "open_questions", "provenance_records",
    )
    return {
        item.id
        for collection in names
        for item in getattr(revision, collection)
    }


def _source_concept_ids(project: IdeaProject) -> set[str]:
    return {item.id for item in project.current_revision.concepts}


def _path_tokens(path: str) -> list[str | int] | None:
    """Parse strict dotted keys and numeric list indexes, with no wildcards."""
    if not isinstance(path, str) or not path:
        return None
    tokens: list[str | int] = []
    cursor = 0
    pattern = re.compile(r"(?:^|\.)([A-Za-z_][A-Za-z0-9_-]*)|\[(0|[1-9][0-9]*)\]")
    for match in pattern.finditer(path):
        if match.start() != cursor:
            return None
        if match.group(1) is not None:
            tokens.append(match.group(1))
        else:
            tokens.append(int(match.group(2)))
        cursor = match.end()
    return tokens if cursor == len(path) and tokens else None


def _resolve_target_path(model_data: Any, path: str) -> tuple[bool, Any]:
    tokens = _path_tokens(path)
    if tokens is None:
        return False, None
    current = model_data
    try:
        for token in tokens:
            if isinstance(token, int):
                if not isinstance(current, list):
                    return False, None
                current = current[token]
            else:
                if not isinstance(current, dict) or token not in current:
                    return False, None
                current = current[token]
        return True, current
    except (IndexError, KeyError, TypeError):
        return False, None


def _issue(code: str, path: str, message: str, *, severity: IssueSeverity = IssueSeverity.ERROR, element_ids: tuple[str, ...] = ()) -> CompilationIssue:
    return CompilationIssue(code, severity, path, message, element_ids)


def _validate_bindings(project: IdeaProject, profile: CompilationProfile) -> list[CompilationIssue]:
    issues: list[CompilationIssue] = []
    source_ids = _source_element_ids(project)
    concept_ids = _source_concept_ids(project)
    seen_mechanisms: set[str] = set()
    bound_concepts: set[str] = set()
    conceptual_binding_count = 0

    for index, binding in enumerate(profile.bindings):
        path = f"bindings[{index}]"
        exists, _ = _resolve_target_path(profile.model_data, binding.target_path)
        if not exists:
            issues.append(_issue("M8_BINDING_TARGET_NOT_FOUND", f"{path}.target_path", f"Target path {binding.target_path!r} does not resolve inside model_data."))
        if binding.source is BindingSource.CONCEPTUAL_ELEMENT:
            conceptual_binding_count += 1
            for element_id in binding.element_ids:
                if element_id not in source_ids:
                    issues.append(_issue("M8_UNKNOWN_SOURCE_ELEMENT", f"{path}.element_ids", f"Element ID {element_id!r} does not exist in the selected revision.", element_ids=(element_id,)))
                if element_id in concept_ids:
                    bound_concepts.add(element_id)
                if any(item.id == element_id for item in project.current_revision.mechanisms):
                    seen_mechanisms.add(element_id)

    if conceptual_binding_count == 0:
        issues.append(_issue("M8_NO_CONCEPTUAL_BINDINGS", "bindings", "At least one target field must be traceably bound to a conceptual element."))
    if not seen_mechanisms:
        issues.append(_issue("M8_NO_MECHANISM_BINDING", "bindings", "At least one operational mechanism must be bound to a target-model field or subtree. This prevents compiling only nouns while losing the theory's causal rules."))
    for concept in project.current_revision.concepts:
        if concept.id not in bound_concepts:
            issues.append(_issue("M8_UNMAPPED_CONCEPT", "bindings", f"Concept {concept.name!r} ({concept.id}) is not mapped into this target profile.", severity=IssueSeverity.WARNING, element_ids=(concept.id,)))
    for mechanism in project.current_revision.mechanisms:
        if mechanism.id not in seen_mechanisms:
            issues.append(_issue("M8_UNMAPPED_MECHANISM", "bindings", f"Mechanism {mechanism.name!r} ({mechanism.id}) is not represented in the target profile.", severity=IssueSeverity.WARNING, element_ids=(mechanism.id,)))
    return issues


def compile_profile(project: IdeaProject, profile: CompilationProfile) -> CompilationResult:
    """Validate and compile an explicit profile into DES or ABM native model.

    No backend is executed. A valid result contains a SimulationSpecification
    whose model has already passed the actual target paradigm validator.
    """
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    if not isinstance(profile, CompilationProfile):
        raise TypeError("profile must be a CompilationProfile")

    issues: list[CompilationIssue] = []
    revision = project.current_revision
    if profile.project_id != project.id:
        issues.append(_issue("M8_PROJECT_MISMATCH", "project_id", "Compilation profile belongs to a different conceptual project."))
    if profile.revision_id != revision.id:
        issues.append(_issue("M8_STALE_REVISION", "revision_id", "Compilation profile targets a different revision. Rebuild or review the profile against the current revision."))
    if profile.paradigm not in _BACKEND_NAMES:
        issues.append(_issue("M8_BACKEND_NOT_IMPLEMENTED", "paradigm", f"No executable compiler/backend is implemented for {profile.paradigm.value}. M7 can assess it, but M8 supports only DES and ABM."))
        return CompilationResult(None, None, tuple(issues))

    readiness = assess_readiness(project, selected_paradigm=_READINESS_PARADIGMS[profile.paradigm])
    if readiness.status is not ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING:
        issues.append(_issue(
            "M8_READINESS_GATE_NOT_MET", "readiness",
            f"M7 readiness gate returned {readiness.status.value}: {readiness.explanation}",
        ))

    issues.extend(_validate_bindings(project, profile))
    if any(item.severity is IssueSeverity.ERROR for item in issues):
        return CompilationResult(None, None, tuple(issues))

    try:
        if profile.paradigm is CompilationParadigm.DISCRETE_EVENT:
            model_data = json.loads(json.dumps(profile.model_data, ensure_ascii=False, allow_nan=False))
            native_model = scenario_from_dict(model_data)
        else:
            model_data = normalize_agent_model_data(profile.model_data)
            native_model = agent_model_from_dict(model_data)
            validation = validate_agent_model(native_model)
            for item in validation.errors:
                issues.append(_issue(item.code, item.path, item.message))
            for item in validation.warnings:
                issues.append(_issue(item.code, item.path, item.message, severity=IssueSeverity.WARNING))
            if validation.errors:
                return CompilationResult(None, None, tuple(issues))
    except Exception as error:
        path = getattr(error, "path", "model_data")
        issues.append(_issue("M8_TARGET_MODEL_INVALID", str(path), str(error)))
        return CompilationResult(None, None, tuple(issues))

    # Persist the exact validated model. ABM metadata normalization is explicit
    # and deterministic; it does not fill scientific facts or experimental values.
    model_data = json.loads(json.dumps(model_data, ensure_ascii=False, allow_nan=False))
    fingerprint = fingerprint_model(profile.paradigm, model_data)
    binding_data = json.loads(json.dumps([
        {
            "target_path": item.target_path,
            "source": item.source.value,
            "element_ids": list(item.element_ids),
            "note": item.note,
        }
        for item in profile.bindings
    ], ensure_ascii=False))
    artifact_seed = _canonical({
        "project_id": project.id,
        "revision_id": revision.id,
        "profile_id": profile.profile_id,
        "fingerprint": fingerprint,
        "bindings": binding_data,
    })
    artifact_id = "m8-" + hashlib.sha256(artifact_seed.encode("utf-8")).hexdigest()[:16]
    artifact = CompilationArtifact(
        schema_version=1,
        artifact_id=artifact_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        project_id=project.id,
        project_title=project.title,
        revision_id=revision.id,
        revision_version=revision.version,
        profile_id=profile.profile_id,
        paradigm=profile.paradigm,
        backend_name=_BACKEND_NAMES[profile.paradigm],
        m7_readiness_status=readiness.status.value,
        paradigm_fit=readiness.assessment_for(_READINESS_PARADIGMS[profile.paradigm]).fit.value,
        model_data=model_data,
        bindings=profile.bindings,
        model_fingerprint=fingerprint,
        artifact_fingerprint="pending",
    )
    artifact = replace(artifact, artifact_fingerprint=fingerprint_artifact(artifact))
    native_specification = SimulationSpecification(
        name=str(model_data.get("name", project.title)),
        paradigm=_SIMULATION_PARADIGMS[profile.paradigm],
        model=native_model,
    )
    issues.append(_issue("M8_COMPILE_SUCCESS", "compilation", "Target model passed the native schema and semantic validator. The specification is ready for the execution milestone; this function did not run the simulation.", severity=IssueSeverity.INFO))
    return CompilationResult(artifact, native_specification, tuple(issues))


def verify_artifact(artifact: CompilationArtifact) -> bool:
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    return (
        fingerprint_model(artifact.paradigm, artifact.model_data) == artifact.model_fingerprint
        and fingerprint_artifact(artifact) == artifact.artifact_fingerprint
    )


def create_profile_template(project: IdeaProject, paradigm: CompilationParadigm) -> dict[str, Any]:
    """Create an intentionally incomplete edit-first profile for the CLI."""
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    if not isinstance(paradigm, CompilationParadigm):
        raise TypeError("paradigm must be a CompilationParadigm")
    if paradigm is CompilationParadigm.DISCRETE_EVENT:
        model_data: dict[str, Any] = {
            "name": project.title,
            "resources": [{"name": "<replace-with-resource-name>", "capacity": None}],
            "jobs": [{
                "entity_id": "<replace-with-entity-id>",
                "arrival_time": None,
                "stages": [{"resource_name": "<replace-with-resource-name>", "service_duration": None}],
            }],
        }
    elif paradigm is CompilationParadigm.AGENT_BASED:
        model_data = {
            "name": project.title,
            "agents": [{
                "reference": "<replace-with-agent-reference>",
                "agent_type": "<replace-with-agent-type>",
                "state": "<replace-with-initial-state>",
                "attributes": {},
            }],
            "environment": {"attributes": {}},
            "relationships": [],
            "behaviours": [],
            "activation": {"mode": "sequential", "order": "declaration"},
            "termination": {"type": "max_steps", "value": None},
            "random_seed": None,
        }
    else:
        raise ValueError("M8 templates are available only for executable DES and ABM paradigms")
    return {
        "profile_id": f"{project.id}-{paradigm.value}-profile",
        "project_id": project.id,
        "revision_id": project.current_revision_id,
        "paradigm": paradigm.value,
        "model_data": model_data,
        "bindings": [],
    }
