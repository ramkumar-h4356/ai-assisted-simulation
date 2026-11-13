"""Structural and semantic validation for conceptual idea projects.

Validation checks internal consistency; it does not establish whether a theory
is true, whether a real-world analogy is scientifically valid, or whether a
model is ready to execute in a simulation backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from conceptual.model import (
    ConceptOrigin, DefinitionStatus, HypothesisStatus, IdeaProject, IdeaRevision,
    MappingType, ReviewStatus, QuestionStatus,
)


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class Readiness(str, Enum):
    INVALID = "invalid"
    IN_PROGRESS = "in_progress"
    REVIEW_READY = "review_ready"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    code: str
    message: str
    severity: IssueSeverity


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(item for item in self.issues if item.severity is IssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(item for item in self.issues if item.severity is IssueSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def readiness(self) -> Readiness:
        if self.errors:
            return Readiness.INVALID
        if self.warnings:
            return Readiness.IN_PROGRESS
        return Readiness.REVIEW_READY

    def raise_for_errors(self) -> None:
        if self.errors:
            detail = "; ".join(f"{item.path}: {item.message}" for item in self.errors)
            raise ValueError(f"Conceptual project validation failed: {detail}")


def _add(issues, path, code, message, severity=IssueSeverity.ERROR):
    issues.append(ValidationIssue(path, code, message, severity))


def _ids(items: Iterable, group_name: str, issues: list[ValidationIssue]) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        identifier = getattr(item, "id", None)
        path = f"{group_name}[{index}].id"
        if not isinstance(identifier, str) or not identifier.strip():
            _add(issues, path, "EMPTY_ID", "Element IDs must be non-empty strings.")
            continue
        if identifier in seen:
            _add(issues, path, "DUPLICATE_ID", f"Duplicate ID {identifier!r} in {group_name}.")
        seen.add(identifier)
    return seen


def _check_refs(refs, known: set[str], path: str, label: str, issues) -> None:
    local_seen: set[str] = set()
    for index, reference in enumerate(refs):
        if reference not in known:
            _add(issues, f"{path}[{index}]", "UNKNOWN_REFERENCE", f"Unknown {label} reference {reference!r}.")
        if reference in local_seen:
            _add(issues, f"{path}[{index}]", "DUPLICATE_REFERENCE", f"Duplicate {label} reference {reference!r}.", IssueSeverity.WARNING)
        local_seen.add(reference)


def _validate_revision(revision: IdeaRevision, path: str, issues: list[ValidationIssue], *, is_current: bool) -> None:
    try:
        parsed = datetime.fromisoformat(revision.created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            _add(issues, f"{path}.created_at", "NAIVE_TIMESTAMP", "Use an ISO-8601 timestamp with a timezone.", IssueSeverity.WARNING)
    except (AttributeError, TypeError, ValueError):
        _add(issues, f"{path}.created_at", "INVALID_TIMESTAMP", "created_at must be an ISO-8601 timestamp.")

    if is_current and not revision.working_statement.strip():
        _add(issues, f"{path}.working_statement", "MISSING_WORKING_STATEMENT", "The current revision should include the latest refined statement of the idea.", IssueSeverity.WARNING)

    if isinstance(revision.version, bool) or not isinstance(revision.version, int) or revision.version < 1:
        _add(issues, f"{path}.version", "INVALID_VERSION", "Revision version must be a positive integer.")

    groups = {
        "concepts": revision.concepts,
        "properties": revision.properties,
        "relationships": revision.relationships,
        "mechanisms": revision.mechanisms,
        "hypotheses": revision.hypotheses,
        "assumptions": revision.assumptions,
        "constraints": revision.constraints,
        "evidence_references": revision.evidence_references,
        "mappings": revision.mappings,
        "open_questions": revision.open_questions,
    }
    global_ids: set[str] = set()
    group_ids: dict[str, set[str]] = {}
    for group_name, items in groups.items():
        group_ids[group_name] = _ids(items, f"{path}.{group_name}", issues)
        for identifier in group_ids[group_name]:
            if identifier in global_ids:
                _add(issues, f"{path}.{group_name}", "DUPLICATE_GLOBAL_ID", f"ID {identifier!r} is reused across element types.")
            global_ids.add(identifier)

    concept_ids = group_ids["concepts"]
    evidence_ids = group_ids["evidence_references"]

    if is_current and not revision.concepts:
        _add(issues, f"{path}.concepts", "NO_CONCEPTS", "The current revision has no extracted concepts yet.", IssueSeverity.WARNING)

    for index, concept in enumerate(revision.concepts):
        item_path = f"{path}.concepts[{index}]"
        if not concept.name.strip():
            _add(issues, f"{item_path}.name", "EMPTY_CONCEPT_NAME", "Concept name must not be empty.")
        if concept.status is DefinitionStatus.DEFINED and not concept.definition.strip():
            _add(issues, f"{item_path}.definition", "DEFINED_CONCEPT_WITHOUT_DEFINITION", "A concept marked defined must include a definition.")
        if concept.origin is ConceptOrigin.REAL_WORLD_MAPPED and not any(m.source_concept_id == concept.id for m in revision.mappings):
            _add(issues, item_path, "MISSING_MAPPING_CLAIM", "A real-world-mapped concept needs an explicit mapping claim.", IssueSeverity.WARNING)
        if not concept.source_note.strip() and concept.origin is ConceptOrigin.AI_PROPOSED:
            _add(issues, f"{item_path}.source_note", "MISSING_AI_PROVENANCE_NOTE", "Record why or from which discussion the AI proposed this concept.", IssueSeverity.WARNING)

    for index, prop in enumerate(revision.properties):
        item_path = f"{path}.properties[{index}]"
        if prop.concept_id not in concept_ids:
            _add(issues, f"{item_path}.concept_id", "UNKNOWN_CONCEPT", f"Unknown owner concept {prop.concept_id!r}.")
        if not prop.name.strip():
            _add(issues, f"{item_path}.name", "EMPTY_PROPERTY_NAME", "Property name must not be empty.")
        if prop.status is DefinitionStatus.DEFINED and not prop.definition.strip():
            _add(issues, f"{item_path}.definition", "DEFINED_PROPERTY_WITHOUT_DEFINITION", "A property marked defined must include a definition.")

    for index, relationship in enumerate(revision.relationships):
        item_path = f"{path}.relationships[{index}]"
        for field_name, identifier in (("source_concept_id", relationship.source_concept_id), ("target_concept_id", relationship.target_concept_id)):
            if identifier not in concept_ids:
                _add(issues, f"{item_path}.{field_name}", "UNKNOWN_CONCEPT", f"Unknown concept {identifier!r}.")
        if not relationship.label.strip():
            _add(issues, f"{item_path}.label", "EMPTY_RELATIONSHIP_LABEL", "Relationship label must not be empty.")

    for index, mechanism in enumerate(revision.mechanisms):
        item_path = f"{path}.mechanisms[{index}]"
        _check_refs(mechanism.input_concept_ids, concept_ids, f"{item_path}.input_concept_ids", "concept", issues)
        _check_refs(mechanism.output_concept_ids, concept_ids, f"{item_path}.output_concept_ids", "concept", issues)
        if not mechanism.name.strip():
            _add(issues, f"{item_path}.name", "EMPTY_MECHANISM_NAME", "Mechanism name must not be empty.")
        if not mechanism.input_concept_ids or not mechanism.output_concept_ids:
            _add(issues, item_path, "MECHANISM_ENDPOINTS_INCOMPLETE", "Define at least one input and one output concept when the mechanism is sufficiently understood.", IssueSeverity.WARNING)
        if not mechanism.operational_definition.strip():
            _add(issues, f"{item_path}.operational_definition", "MECHANISM_NOT_OPERATIONALIZED", "The mechanism has no operational definition; it can remain conceptual but cannot yet be translated reliably into executable rules.", IssueSeverity.WARNING)

    for index, hypothesis in enumerate(revision.hypotheses):
        item_path = f"{path}.hypotheses[{index}]"
        if not hypothesis.statement.strip():
            _add(issues, f"{item_path}.statement", "EMPTY_HYPOTHESIS", "Hypothesis statement must not be empty.")
        _check_refs(hypothesis.evidence_reference_ids, evidence_ids, f"{item_path}.evidence_reference_ids", "evidence", issues)
        if hypothesis.status is HypothesisStatus.UNTESTED and not hypothesis.evidence_reference_ids:
            _add(issues, item_path, "UNTESTED_HYPOTHESIS", "This hypothesis has not been associated with evidence; this does not make it invalid.", IssueSeverity.WARNING)
        elif hypothesis.status is not HypothesisStatus.UNTESTED and not hypothesis.evidence_reference_ids:
            _add(issues, item_path, "HYPOTHESIS_STATUS_WITHOUT_EVIDENCE", "A non-untested hypothesis status should have supporting or challenging evidence references.", IssueSeverity.WARNING)

    for group_name in ("assumptions", "constraints"):
        for index, item in enumerate(groups[group_name]):
            if not item.statement.strip():
                _add(issues, f"{path}.{group_name}[{index}].statement", "EMPTY_STATEMENT", f"{group_name[:-1].capitalize()} statement must not be empty.")

    for index, reference in enumerate(revision.evidence_references):
        if not reference.title.strip():
            _add(issues, f"{path}.evidence_references[{index}].title", "EMPTY_REFERENCE_TITLE", "Evidence reference title must not be empty.")
        if reference.published_year is not None and (isinstance(reference.published_year, bool) or not isinstance(reference.published_year, int) or not 1000 <= reference.published_year <= 9999):
            _add(issues, f"{path}.evidence_references[{index}].published_year", "INVALID_PUBLICATION_YEAR", "Publication year must be a four-digit year.")

    for index, mapping in enumerate(revision.mappings):
        item_path = f"{path}.mappings[{index}]"
        if mapping.source_concept_id not in concept_ids:
            _add(issues, f"{item_path}.source_concept_id", "UNKNOWN_CONCEPT", f"Unknown source concept {mapping.source_concept_id!r}.")
        if not mapping.target_label.strip() or not mapping.rationale.strip():
            _add(issues, item_path, "INCOMPLETE_MAPPING_CLAIM", "A mapping needs a target label and a rationale.")
        _check_refs(mapping.evidence_reference_ids, evidence_ids, f"{item_path}.evidence_reference_ids", "evidence", issues)
        if mapping.review_status is ReviewStatus.UNREVIEWED:
            _add(issues, item_path, "UNREVIEWED_MAPPING_CLAIM", "This mapping is a proposal and should be reviewed before being treated as an accepted correspondence.", IssueSeverity.WARNING)
        if mapping.review_status is ReviewStatus.ACCEPTED and mapping.mapping_type in {MappingType.EQUIVALENT, MappingType.EVIDENCE_SUPPORTED, MappingType.CONTRADICTED_BY} and not mapping.evidence_reference_ids:
            _add(issues, item_path, "ACCEPTED_MAPPING_WITHOUT_EVIDENCE", "An accepted equivalence/evidence mapping should include at least one supporting reference.", IssueSeverity.WARNING)

    known_element_ids = global_ids
    for index, question in enumerate(revision.open_questions):
        item_path = f"{path}.open_questions[{index}]"
        if not question.question.strip():
            _add(issues, f"{item_path}.question", "EMPTY_QUESTION", "Open question text must not be empty.")
        _check_refs(question.related_element_ids, known_element_ids, f"{item_path}.related_element_ids", "element", issues)
        if question.status is QuestionStatus.RESOLVED and not question.resolution.strip():
            _add(issues, f"{item_path}.resolution", "MISSING_QUESTION_RESOLUTION", "A resolved question must record its resolution.")
        if question.status is QuestionStatus.OPEN and question.blocking:
            _add(issues, item_path, "BLOCKING_OPEN_QUESTION", "This question blocks a fully specified conceptual model.", IssueSeverity.WARNING)


def validate_idea_project(project: IdeaProject) -> ValidationReport:
    """Validate project identity, immutable revision chain and all snapshots."""
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    issues: list[ValidationIssue] = []
    if not project.id.strip():
        _add(issues, "id", "EMPTY_PROJECT_ID", "Project ID must not be empty.")
    if not project.title.strip():
        _add(issues, "title", "EMPTY_PROJECT_TITLE", "Project title must not be empty.")
    if not project.original_statement.strip():
        _add(issues, "original_statement", "EMPTY_ORIGINAL_STATEMENT", "The original idea must be preserved as non-empty text.")
    if not project.revisions:
        _add(issues, "revisions", "NO_REVISIONS", "A project must contain at least one revision.")
        return ValidationReport(tuple(issues))

    revision_ids: set[str] = set()
    versions: set[int] = set()
    previous: IdeaRevision | None = None
    current_found = False
    for index, revision in enumerate(project.revisions):
        path = f"revisions[{index}]"
        if not revision.id.strip():
            _add(issues, f"{path}.id", "EMPTY_REVISION_ID", "Revision ID must not be empty.")
        if revision.id in revision_ids:
            _add(issues, f"{path}.id", "DUPLICATE_REVISION_ID", f"Revision ID {revision.id!r} is duplicated.")
        revision_ids.add(revision.id)
        if revision.version in versions:
            _add(issues, f"{path}.version", "DUPLICATE_REVISION_VERSION", f"Revision version {revision.version!r} is duplicated.")
        versions.add(revision.version)
        expected_parent = previous.id if previous else None
        if revision.parent_revision_id != expected_parent:
            _add(issues, f"{path}.parent_revision_id", "BROKEN_REVISION_CHAIN", "Revision parent does not match the preceding snapshot.")
        _validate_revision(
            revision, path, issues, is_current=(revision.id == project.current_revision_id)
        )
        previous = revision
        current_found = current_found or revision.id == project.current_revision_id

    if not current_found:
        _add(issues, "current_revision_id", "UNKNOWN_CURRENT_REVISION", f"Current revision {project.current_revision_id!r} does not exist.")
    elif project.revisions[-1].id != project.current_revision_id:
        _add(issues, "current_revision_id", "CURRENT_REVISION_NOT_LATEST", "The current revision must point to the latest appended snapshot.")
    expected_versions = list(range(1, len(project.revisions) + 1))
    if sorted(versions) != expected_versions:
        _add(issues, "revisions", "NON_SEQUENTIAL_VERSIONS", "Revision versions must be sequential starting at 1.")
    return ValidationReport(tuple(issues))
