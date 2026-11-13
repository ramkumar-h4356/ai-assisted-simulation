"""Strict parser for the M6 interpreter's declarative JSON contract."""

from __future__ import annotations

from typing import Any

from conceptual.model import ConceptKind, DefinitionStatus, PropertyType
from idea_assistant.models import ClarificationQuestion, IdeaDraft


class IdeaInterpretationError(ValueError):
    """Raised when an AI response does not satisfy the M6 interpretation contract."""


_TOP_LEVEL = {
    "title", "working_statement", "summary", "concepts", "properties",
    "relationships", "mechanisms", "hypotheses", "assumptions", "constraints",
    "clarification_questions", "uncertainties", "retrieval_queries",
}
_SOURCE_VALUES = {"explicit", "inferred", "suggested"}


def _object(value: Any, path: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IdeaInterpretationError(f"{path} must be a JSON object")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise IdeaInterpretationError(f"{path} has unsupported field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise IdeaInterpretationError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
    return value


def _text(value: Any, path: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise IdeaInterpretationError(f"{path} must be {'a string' if empty else 'a non-empty string'}")
    return value.strip() if not empty else value


def _strings(value: Any, path: str, *, max_items: int = 100) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > max_items:
        raise IdeaInterpretationError(f"{path} must be an array with at most {max_items} items")
    result = tuple(_text(item, f"{path}[{i}]") for i, item in enumerate(value))
    return result


def _enum(value: Any, enum_type, path: str, default):
    raw = default if value is None else value
    try:
        return enum_type(raw).value
    except (TypeError, ValueError) as error:
        allowed = ", ".join(item.value for item in enum_type)
        raise IdeaInterpretationError(f"{path} must be one of: {allowed}") from error


def _source_fields(item: dict[str, Any], path: str) -> dict[str, str]:
    source = item.get("source", "inferred")
    if source not in _SOURCE_VALUES:
        raise IdeaInterpretationError(f"{path}.source must be one of: explicit, inferred, suggested")
    return {"source": source, "excerpt": _text(item.get("excerpt", ""), f"{path}.excerpt", empty=True)}


def _parse_group(raw: Any, path: str, allowed: set[str], required: set[str], limit: int = 100) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw, list) or len(raw) > limit:
        raise IdeaInterpretationError(f"{path} must be an array with at most {limit} items")
    return tuple(_object(item, f"{path}[{i}]", allowed, required) for i, item in enumerate(raw))


def parse_idea_draft(raw: Any) -> IdeaDraft:
    root = _object(raw, "response", _TOP_LEVEL, {"title", "working_statement", "summary", "concepts", "clarification_questions"})
    concepts_raw = _parse_group(
        root["concepts"], "concepts",
        {"name", "kind", "definition", "status", "source", "excerpt"},
        {"name", "kind", "definition"}, 80,
    )
    concepts = []
    concept_names: dict[str, str] = {}
    for i, item in enumerate(concepts_raw):
        path = f"concepts[{i}]"
        name = _text(item["name"], f"{path}.name")
        if name.casefold() in concept_names:
            raise IdeaInterpretationError(f"Duplicate concept name {name!r}")
        concept_names[name.casefold()] = name
        definition = _text(item["definition"], f"{path}.definition", empty=True)
        status = _enum(item.get("status"), DefinitionStatus, f"{path}.status", DefinitionStatus.PARTIAL.value)
        if status == DefinitionStatus.DEFINED.value and not definition.strip():
            status = DefinitionStatus.PROPOSED.value
        concepts.append({
            "name": name,
            "kind": _enum(item.get("kind"), ConceptKind, f"{path}.kind", ConceptKind.ABSTRACT.value),
            "definition": definition,
            "status": status,
            **_source_fields(item, path),
        })

    properties_raw = _parse_group(
        root.get("properties", []), "properties",
        {"concept", "name", "data_type", "unit", "definition", "status", "source", "excerpt"},
        {"concept", "name"},
    )
    properties = []
    for i, item in enumerate(properties_raw):
        path = f"properties[{i}]"
        concept = _text(item["concept"], f"{path}.concept")
        if concept.casefold() not in concept_names:
            raise IdeaInterpretationError(f"{path}.concept refers to unknown concept {concept!r}")
        definition = _text(item.get("definition", ""), f"{path}.definition", empty=True)
        status = _enum(item.get("status"), DefinitionStatus, f"{path}.status", DefinitionStatus.PROPOSED.value)
        if status == DefinitionStatus.DEFINED.value and not definition.strip():
            status = DefinitionStatus.PROPOSED.value
        properties.append({
            "concept": concept_names[concept.casefold()],
            "name": _text(item["name"], f"{path}.name"),
            "data_type": _enum(item.get("data_type"), PropertyType, f"{path}.data_type", PropertyType.UNKNOWN.value),
            "unit": _text(item.get("unit", ""), f"{path}.unit", empty=True) or None,
            "definition": definition,
            "status": status,
            **_source_fields(item, path),
        })

    relationships_raw = _parse_group(
        root.get("relationships", []), "relationships",
        {"source_concept", "target_concept", "label", "description", "directed", "status", "source", "excerpt"},
        {"source_concept", "target_concept", "label"},
    )
    relationships = []
    for i, item in enumerate(relationships_raw):
        path = f"relationships[{i}]"
        source = _text(item["source_concept"], f"{path}.source_concept")
        target = _text(item["target_concept"], f"{path}.target_concept")
        if source.casefold() not in concept_names or target.casefold() not in concept_names:
            raise IdeaInterpretationError(f"{path} references a concept that was not declared")
        directed = item.get("directed", True)
        if not isinstance(directed, bool):
            raise IdeaInterpretationError(f"{path}.directed must be a boolean")
        relationships.append({
            "source_concept": concept_names[source.casefold()],
            "target_concept": concept_names[target.casefold()],
            "label": _text(item["label"], f"{path}.label"),
            "description": _text(item.get("description", ""), f"{path}.description", empty=True),
            "directed": directed,
            "status": _enum(item.get("status"), DefinitionStatus, f"{path}.status", DefinitionStatus.PROPOSED.value),
            **_source_fields(item, path),
        })

    mechanisms_raw = _parse_group(
        root.get("mechanisms", []), "mechanisms",
        {"name", "description", "inputs", "outputs", "trigger", "effect", "operational_definition", "status", "source", "excerpt"},
        {"name"},
    )
    mechanisms = []
    for i, item in enumerate(mechanisms_raw):
        path = f"mechanisms[{i}]"
        inputs = _strings(item.get("inputs", []), f"{path}.inputs")
        outputs = _strings(item.get("outputs", []), f"{path}.outputs")
        refs = inputs + outputs
        if any(ref.casefold() not in concept_names for ref in refs):
            raise IdeaInterpretationError(f"{path} references a concept that was not declared")
        mechanisms.append({
            "name": _text(item["name"], f"{path}.name"),
            "description": _text(item.get("description", ""), f"{path}.description", empty=True),
            "inputs": tuple(concept_names[ref.casefold()] for ref in inputs),
            "outputs": tuple(concept_names[ref.casefold()] for ref in outputs),
            "trigger": _text(item.get("trigger", ""), f"{path}.trigger", empty=True),
            "effect": _text(item.get("effect", ""), f"{path}.effect", empty=True),
            "operational_definition": _text(item.get("operational_definition", ""), f"{path}.operational_definition", empty=True),
            "status": _enum(item.get("status"), DefinitionStatus, f"{path}.status", DefinitionStatus.PROPOSED.value),
            **_source_fields(item, path),
        })

    statement_groups = {}
    for group_name in ("hypotheses", "assumptions", "constraints"):
        required = {"statement"}
        allowed = {"statement", "scope", "source", "excerpt"}
        if group_name in {"assumptions", "constraints"}:
            allowed.add("rationale")
        group_raw = _parse_group(root.get(group_name, []), group_name, allowed, required)
        items = []
        for i, item in enumerate(group_raw):
            path = f"{group_name}[{i}]"
            normalized = {
                "statement": _text(item["statement"], f"{path}.statement"),
                "scope": _text(item.get("scope", ""), f"{path}.scope", empty=True),
                **_source_fields(item, path),
            }
            if group_name in {"assumptions", "constraints"}:
                normalized["rationale"] = _text(item.get("rationale", ""), f"{path}.rationale", empty=True)
            items.append(normalized)
        statement_groups[group_name] = tuple(items)

    questions_raw = _parse_group(
        root["clarification_questions"], "clarification_questions",
        {"question", "reason", "related_concepts", "blocking", "priority"}, {"question"}, 20,
    )
    questions = []
    for i, item in enumerate(questions_raw):
        path = f"clarification_questions[{i}]"
        related = _strings(item.get("related_concepts", []), f"{path}.related_concepts", max_items=20)
        if any(name.casefold() not in concept_names for name in related):
            raise IdeaInterpretationError(f"{path}.related_concepts contains an undeclared concept")
        blocking = item.get("blocking", True)
        priority = item.get("priority", "medium")
        if not isinstance(blocking, bool):
            raise IdeaInterpretationError(f"{path}.blocking must be a boolean")
        if priority not in {"high", "medium", "low"}:
            raise IdeaInterpretationError(f"{path}.priority must be high, medium or low")
        questions.append(ClarificationQuestion(
            id=f"clarification-{i + 1}",
            question=_text(item["question"], f"{path}.question"),
            reason=_text(item.get("reason", ""), f"{path}.reason", empty=True),
            related_concepts=tuple(concept_names[name.casefold()] for name in related),
            blocking=blocking,
            priority=priority,
        ))

    return IdeaDraft(
        title=_text(root["title"], "title"),
        working_statement=_text(root["working_statement"], "working_statement"),
        summary=_text(root["summary"], "summary", empty=True),
        concepts=tuple(concepts), properties=tuple(properties), relationships=tuple(relationships),
        mechanisms=tuple(mechanisms), hypotheses=statement_groups["hypotheses"],
        assumptions=statement_groups["assumptions"], constraints=statement_groups["constraints"],
        clarification_questions=tuple(questions),
        uncertainties=_strings(root.get("uncertainties", []), "uncertainties", max_items=50),
        retrieval_queries=_strings(root.get("retrieval_queries", []), "retrieval_queries", max_items=10),
    )
