"""Immutable, paradigm-independent representations of human ideas and theories.

The conceptual layer records what a person means before deciding how (or whether)
that idea can be operationalised by a simulation paradigm.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class ConceptKind(str, Enum):
    ACTOR = "actor"
    ENTITY = "entity"
    RESOURCE = "resource"
    PROCESS = "process"
    STATE = "state"
    VARIABLE = "variable"
    ABSTRACT = "abstract"


class ConceptOrigin(str, Enum):
    USER_DEFINED = "user_defined"
    AI_PROPOSED = "ai_proposed"
    REAL_WORLD_MAPPED = "real_world_mapped"


class DefinitionStatus(str, Enum):
    PROPOSED = "proposed"
    PARTIAL = "partial"
    DEFINED = "defined"


class PropertyType(str, Enum):
    UNKNOWN = "unknown"
    NUMBER = "number"
    INTEGER = "integer"
    TEXT = "text"
    BOOLEAN = "boolean"
    CATEGORY = "category"
    DATE_TIME = "date_time"


class ReferenceType(str, Enum):
    ARTICLE = "article"
    BOOK = "book"
    DATASET = "dataset"
    WEBSITE = "website"
    REPORT = "report"
    STANDARD = "standard"
    OTHER = "other"


class MappingType(str, Enum):
    EQUIVALENT = "equivalent"
    ANALOGOUS = "analogous"
    INSPIRED_BY = "inspired_by"
    EVIDENCE_SUPPORTED = "evidence_supported"
    CONTRADICTED_BY = "contradicted_by"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class HypothesisStatus(str, Enum):
    UNTESTED = "untested"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    INCONCLUSIVE = "inconclusive"


class QuestionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class ProvenanceKind(str, Enum):
    USER_EXPLICIT = "user_explicit"
    AI_INFERRED = "ai_inferred"
    AI_SUGGESTED = "ai_suggested"
    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"


def _text(value: object, name: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be empty")


def _enum(value: object, enum_type: type[Enum], name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{name} must be a {enum_type.__name__}")


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list of strings")
    result = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-empty strings")
    return result


def _object_tuple(value: object, expected_type: type, name: str) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    result = tuple(value)
    if any(not isinstance(item, expected_type) for item in result):
        raise TypeError(f"{name} must contain only {expected_type.__name__} objects")
    return result


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    name: str
    kind: ConceptKind = ConceptKind.ABSTRACT
    origin: ConceptOrigin = ConceptOrigin.USER_DEFINED
    definition: str = ""
    status: DefinitionStatus = DefinitionStatus.PROPOSED
    source_note: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "concept id")
        _text(self.name, "concept name")
        _text(self.definition, "concept definition", allow_empty=True)
        _text(self.source_note, "concept source_note", allow_empty=True)
        _enum(self.kind, ConceptKind, "concept kind")
        _enum(self.origin, ConceptOrigin, "concept origin")
        _enum(self.status, DefinitionStatus, "concept status")


@dataclass(frozen=True, slots=True)
class Property:
    id: str
    concept_id: str
    name: str
    data_type: PropertyType = PropertyType.UNKNOWN
    unit: str | None = None
    definition: str = ""
    status: DefinitionStatus = DefinitionStatus.PROPOSED

    def __post_init__(self) -> None:
        for name in ("id", "concept_id", "name"):
            _text(getattr(self, name), f"property {name}")
        _text(self.definition, "property definition", allow_empty=True)
        if self.unit is not None:
            _text(self.unit, "property unit", allow_empty=True)
        _enum(self.data_type, PropertyType, "property data_type")
        _enum(self.status, DefinitionStatus, "property status")


@dataclass(frozen=True, slots=True)
class Relationship:
    id: str
    source_concept_id: str
    target_concept_id: str
    label: str
    description: str = ""
    directed: bool = True
    status: DefinitionStatus = DefinitionStatus.PROPOSED

    def __post_init__(self) -> None:
        for name in ("id", "source_concept_id", "target_concept_id", "label"):
            _text(getattr(self, name), f"relationship {name}")
        _text(self.description, "relationship description", allow_empty=True)
        if not isinstance(self.directed, bool):
            raise TypeError("relationship directed must be a boolean")
        _enum(self.status, DefinitionStatus, "relationship status")


@dataclass(frozen=True, slots=True)
class Mechanism:
    id: str
    name: str
    description: str = ""
    input_concept_ids: tuple[str, ...] = ()
    output_concept_ids: tuple[str, ...] = ()
    trigger_description: str = ""
    effect_description: str = ""
    operational_definition: str = ""
    status: DefinitionStatus = DefinitionStatus.PROPOSED

    def __post_init__(self) -> None:
        _text(self.id, "mechanism id")
        _text(self.name, "mechanism name")
        for name in ("description", "trigger_description", "effect_description", "operational_definition"):
            _text(getattr(self, name), f"mechanism {name}", allow_empty=True)
        object.__setattr__(self, "input_concept_ids", _string_tuple(self.input_concept_ids, "input_concept_ids"))
        object.__setattr__(self, "output_concept_ids", _string_tuple(self.output_concept_ids, "output_concept_ids"))
        _enum(self.status, DefinitionStatus, "mechanism status")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    statement: str
    scope: str = ""
    evidence_reference_ids: tuple[str, ...] = ()
    status: HypothesisStatus = HypothesisStatus.UNTESTED

    def __post_init__(self) -> None:
        _text(self.id, "hypothesis id")
        _text(self.statement, "hypothesis statement")
        _text(self.scope, "hypothesis scope", allow_empty=True)
        object.__setattr__(self, "evidence_reference_ids", _string_tuple(self.evidence_reference_ids, "evidence_reference_ids"))
        _enum(self.status, HypothesisStatus, "hypothesis status")


@dataclass(frozen=True, slots=True)
class Assumption:
    id: str
    statement: str
    scope: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        for name in ("id", "statement"):
            _text(getattr(self, name), f"assumption {name}")
        _text(self.scope, "assumption scope", allow_empty=True)
        _text(self.rationale, "assumption rationale", allow_empty=True)


@dataclass(frozen=True, slots=True)
class Constraint:
    id: str
    statement: str
    scope: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        for name in ("id", "statement"):
            _text(getattr(self, name), f"constraint {name}")
        _text(self.scope, "constraint scope", allow_empty=True)
        _text(self.rationale, "constraint rationale", allow_empty=True)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    id: str
    title: str
    reference_type: ReferenceType = ReferenceType.OTHER
    uri: str | None = None
    publisher: str = ""
    published_year: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "evidence reference id")
        _text(self.title, "evidence reference title")
        if self.uri is not None:
            _text(self.uri, "evidence reference uri", allow_empty=True)
        _text(self.publisher, "evidence reference publisher", allow_empty=True)
        _text(self.notes, "evidence reference notes", allow_empty=True)
        if self.published_year is not None and (isinstance(self.published_year, bool) or not isinstance(self.published_year, int)):
            raise TypeError("published_year must be an integer or None")
        _enum(self.reference_type, ReferenceType, "reference_type")


@dataclass(frozen=True, slots=True)
class MappingClaim:
    id: str
    source_concept_id: str
    target_label: str
    mapping_type: MappingType
    rationale: str
    target_description: str = ""
    evidence_reference_ids: tuple[str, ...] = ()
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    def __post_init__(self) -> None:
        for name in ("id", "source_concept_id", "target_label", "rationale"):
            _text(getattr(self, name), f"mapping {name}")
        _text(self.target_description, "mapping target_description", allow_empty=True)
        object.__setattr__(self, "evidence_reference_ids", _string_tuple(self.evidence_reference_ids, "evidence_reference_ids"))
        _enum(self.mapping_type, MappingType, "mapping_type")
        _enum(self.review_status, ReviewStatus, "review_status")


@dataclass(frozen=True, slots=True)
class OpenQuestion:
    id: str
    question: str
    related_element_ids: tuple[str, ...] = ()
    blocking: bool = True
    status: QuestionStatus = QuestionStatus.OPEN
    resolution: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "question id")
        _text(self.question, "question")
        object.__setattr__(self, "related_element_ids", _string_tuple(self.related_element_ids, "related_element_ids"))
        if not isinstance(self.blocking, bool):
            raise TypeError("question blocking must be a boolean")
        _enum(self.status, QuestionStatus, "question status")
        _text(self.resolution, "question resolution", allow_empty=True)


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Trace why a conceptual element exists and which input informed it."""

    id: str
    element_id: str
    kind: ProvenanceKind
    source_label: str = ""
    source_excerpt: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        for name in ("id", "element_id"):
            _text(getattr(self, name), f"provenance {name}")
        for name in ("source_label", "source_excerpt", "note"):
            _text(getattr(self, name), f"provenance {name}", allow_empty=True)
        _enum(self.kind, ProvenanceKind, "provenance kind")


@dataclass(frozen=True, slots=True)
class IdeaRevision:
    """A complete, immutable snapshot of the conceptual model at one revision."""

    id: str
    version: int
    created_at: str
    change_summary: str
    working_statement: str = ""
    parent_revision_id: str | None = None
    concepts: tuple[Concept, ...] = ()
    properties: tuple[Property, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    mechanisms: tuple[Mechanism, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()
    mappings: tuple[MappingClaim, ...] = ()
    open_questions: tuple[OpenQuestion, ...] = ()
    provenance_records: tuple[ProvenanceRecord, ...] = ()

    def __post_init__(self) -> None:
        _text(self.id, "revision id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("revision version must be a positive integer")
        _text(self.created_at, "revision created_at")
        _text(self.change_summary, "revision change_summary")
        _text(self.working_statement, "revision working_statement", allow_empty=True)
        if self.parent_revision_id is not None:
            _text(self.parent_revision_id, "revision parent_revision_id")
        expected = {
            "concepts": Concept, "properties": Property, "relationships": Relationship,
            "mechanisms": Mechanism, "hypotheses": Hypothesis, "assumptions": Assumption,
            "constraints": Constraint, "evidence_references": EvidenceReference,
            "mappings": MappingClaim, "open_questions": OpenQuestion,
            "provenance_records": ProvenanceRecord,
        }
        for name, expected_type in expected.items():
            object.__setattr__(self, name, _object_tuple(getattr(self, name), expected_type, name))


@dataclass(frozen=True, slots=True)
class IdeaProject:
    """Project envelope that preserves the original idea and every revision."""

    id: str
    title: str
    original_statement: str
    current_revision_id: str
    revisions: tuple[IdeaRevision, ...]

    def __post_init__(self) -> None:
        _text(self.id, "project id")
        _text(self.title, "project title")
        _text(self.original_statement, "original statement")
        _text(self.current_revision_id, "current revision id")
        object.__setattr__(self, "revisions", _object_tuple(self.revisions, IdeaRevision, "revisions"))

    @property
    def current_revision(self) -> IdeaRevision:
        for revision in self.revisions:
            if revision.id == self.current_revision_id:
                return revision
        raise LookupError(
            f"Current revision {self.current_revision_id!r} does not exist"
        )


ConceptualElement: TypeAlias = (
    Concept | Property | Relationship | Mechanism | Hypothesis | Assumption |
    Constraint | EvidenceReference | MappingClaim | OpenQuestion
)
