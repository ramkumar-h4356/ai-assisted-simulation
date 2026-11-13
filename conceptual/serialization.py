"""Strict JSON serialization and persistence for conceptual idea projects."""

from __future__ import annotations

import json
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from conceptual.model import (
    Assumption, Concept, ConceptKind, ConceptOrigin, Constraint, DefinitionStatus,
    EvidenceReference, Hypothesis, HypothesisStatus, IdeaProject, IdeaRevision,
    MappingClaim, MappingType, Mechanism, OpenQuestion, Property, PropertyType,
    QuestionStatus, ReferenceType, Relationship, ReviewStatus,
)

T = TypeVar("T")


class IdeaSerializationError(ValueError):
    """Raised when a conceptual project cannot be decoded from its JSON form."""


_ENUM_FIELDS = {
    Concept: {"kind": ConceptKind, "origin": ConceptOrigin, "status": DefinitionStatus},
    Property: {"data_type": PropertyType, "status": DefinitionStatus},
    Relationship: {"status": DefinitionStatus},
    Mechanism: {"status": DefinitionStatus},
    Hypothesis: {"status": HypothesisStatus},
    EvidenceReference: {"reference_type": ReferenceType},
    MappingClaim: {"mapping_type": MappingType, "review_status": ReviewStatus},
    OpenQuestion: {"status": QuestionStatus},
}
_TUPLE_FIELDS = {
    Mechanism: {"input_concept_ids", "output_concept_ids"},
    Hypothesis: {"evidence_reference_ids"},
    MappingClaim: {"evidence_reference_ids"},
    OpenQuestion: {"related_element_ids"},
    IdeaRevision: {
        "concepts", "properties", "relationships", "mechanisms", "hypotheses",
        "assumptions", "constraints", "evidence_references", "mappings", "open_questions",
    },
    IdeaProject: {"revisions"},
}
_NESTED_FIELDS = {
    IdeaRevision: {
        "concepts": Concept,
        "properties": Property,
        "relationships": Relationship,
        "mechanisms": Mechanism,
        "hypotheses": Hypothesis,
        "assumptions": Assumption,
        "constraints": Constraint,
        "evidence_references": EvidenceReference,
        "mappings": MappingClaim,
        "open_questions": OpenQuestion,
    },
    IdeaProject: {"revisions": IdeaRevision},
}


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _to_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_to_primitive(item) for item in value]
    if isinstance(value, list):
        return [_to_primitive(item) for item in value]
    return value


def idea_project_to_dict(project: IdeaProject) -> dict[str, Any]:
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    return _to_primitive(project)


def _decode_dataclass(cls: type[T], raw: Any, path: str) -> T:
    if not isinstance(raw, dict):
        raise IdeaSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    unknown = set(raw) - allowed
    missing = {
        item.name for item in fields(cls)
        if item.name not in raw
        and item.default is MISSING
        and item.default_factory is MISSING
    }
    if unknown:
        raise IdeaSerializationError(f"{path} contains unsupported field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise IdeaSerializationError(f"{path} is missing required field(s): {', '.join(sorted(missing))}")

    values: dict[str, Any] = {}
    for name, value in raw.items():
        enum_type = _ENUM_FIELDS.get(cls, {}).get(name)
        if enum_type is not None:
            try:
                values[name] = enum_type(value)
            except (TypeError, ValueError) as error:
                raise IdeaSerializationError(f"{path}.{name} has invalid value {value!r}") from error
            continue

        nested_type = _NESTED_FIELDS.get(cls, {}).get(name)
        if nested_type is not None:
            if not isinstance(value, list):
                raise IdeaSerializationError(f"{path}.{name} must be a JSON array")
            values[name] = tuple(
                _decode_dataclass(nested_type, item, f"{path}.{name}[{index}]")
                for index, item in enumerate(value)
            )
            continue

        if name in _TUPLE_FIELDS.get(cls, set()):
            if not isinstance(value, list):
                raise IdeaSerializationError(f"{path}.{name} must be a JSON array")
            if any(not isinstance(item, str) for item in value):
                raise IdeaSerializationError(f"{path}.{name} must contain only strings")
            values[name] = tuple(value)
            continue

        values[name] = value
    try:
        return cls(**values)
    except (TypeError, ValueError) as error:
        raise IdeaSerializationError(f"{path} contains invalid data: {error}") from error


def idea_project_from_dict(data: Any) -> IdeaProject:
    return _decode_dataclass(IdeaProject, data, "idea_project")


def dumps_idea_project(project: IdeaProject, *, indent: int = 2) -> str:
    return json.dumps(idea_project_to_dict(project), ensure_ascii=False, indent=indent, allow_nan=False)


def loads_idea_project(content: str) -> IdeaProject:
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise IdeaSerializationError(f"Invalid JSON document: {error}") from error
    return idea_project_from_dict(data)


def save_idea_project(project: IdeaProject, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_idea_project(project), encoding="utf-8")
    return destination


def load_idea_project(path: str | Path) -> IdeaProject:
    source = Path(path)
    try:
        content = source.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(f"Could not read conceptual project at {source}: {error}") from error
    return loads_idea_project(content)
