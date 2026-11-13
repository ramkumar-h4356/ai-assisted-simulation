"""Paradigm-independent conceptual modeling core."""

from conceptual.model import (
    Assumption, Concept, ConceptKind, ConceptOrigin, Constraint, DefinitionStatus,
    EvidenceReference, Hypothesis, HypothesisStatus, IdeaProject, IdeaRevision,
    MappingClaim, MappingType, Mechanism, OpenQuestion, Property, PropertyType,
    QuestionStatus, ReferenceType, Relationship, ReviewStatus, ProvenanceRecord, ProvenanceKind,
)
from conceptual.revision import append_revision, create_idea_project, revise_idea_project
from conceptual.serialization import (
    IdeaSerializationError, dumps_idea_project, idea_project_from_dict,
    idea_project_to_dict, load_idea_project, loads_idea_project, save_idea_project,
)
from conceptual.validation import (
    IssueSeverity, Readiness, ValidationIssue, ValidationReport, validate_idea_project,
)

__all__ = [
    "Assumption", "Concept", "ConceptKind", "ConceptOrigin", "Constraint",
    "DefinitionStatus", "EvidenceReference", "Hypothesis", "HypothesisStatus",
    "IdeaProject", "IdeaRevision", "IdeaSerializationError", "IssueSeverity",
    "MappingClaim", "MappingType", "Mechanism", "OpenQuestion", "Property",
    "PropertyType", "QuestionStatus", "Readiness", "ReferenceType", "Relationship",
    "ReviewStatus", "ProvenanceKind", "ProvenanceRecord", "ValidationIssue", "ValidationReport", "append_revision",
    "create_idea_project", "dumps_idea_project", "idea_project_from_dict",
    "idea_project_to_dict", "load_idea_project", "loads_idea_project",
    "revise_idea_project", "save_idea_project", "validate_idea_project",
]
