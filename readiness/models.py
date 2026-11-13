"""Immutable data contracts for M7 simulation-readiness assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReadinessStatus(str, Enum):
    NOT_ASSESSABLE = "not_assessable"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_EVALUATION = "ready_for_evaluation"
    READY_FOR_IMPLEMENTATION_PLANNING = "ready_for_implementation_planning"


class Paradigm(str, Enum):
    DISCRETE_EVENT = "discrete_event"
    AGENT_BASED = "agent_based"
    MATHEMATICAL = "mathematical"
    DATA_DRIVEN = "data_driven"


class FitLevel(str, Enum):
    STRONG = "strong_fit"
    POSSIBLE = "possible_fit"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    POOR = "poor_fit"


class BackendStatus(str, Enum):
    IMPLEMENTED = "implemented"
    ASSESSMENT_ONLY = "assessment_only"
    NOT_IMPLEMENTED = "not_implemented"


class QuestionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class AssessmentFinding:
    code: str
    title: str
    explanation: str
    element_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("code", "title", "explanation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.element_ids, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.element_ids):
            raise TypeError("element_ids must be a tuple of non-empty strings")


@dataclass(frozen=True, slots=True)
class ClarificationItem:
    id: str
    question: str
    reason: str
    priority: QuestionPriority
    related_element_ids: tuple[str, ...] = ()
    blocking: bool = True

    def __post_init__(self) -> None:
        for name in ("id", "question", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.priority, QuestionPriority):
            raise TypeError("priority must be a QuestionPriority")
        if not isinstance(self.related_element_ids, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.related_element_ids):
            raise TypeError("related_element_ids must be a tuple of non-empty strings")
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking must be a boolean")


@dataclass(frozen=True, slots=True)
class ParadigmAssessment:
    paradigm: Paradigm
    fit: FitLevel
    backend_status: BackendStatus
    supporting_findings: tuple[AssessmentFinding, ...] = ()
    limitations: tuple[AssessmentFinding, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.paradigm, Paradigm):
            raise TypeError("paradigm must be a Paradigm")
        if not isinstance(self.fit, FitLevel):
            raise TypeError("fit must be a FitLevel")
        if not isinstance(self.backend_status, BackendStatus):
            raise TypeError("backend_status must be a BackendStatus")
        for name in ("supporting_findings", "limitations"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, AssessmentFinding) for item in value):
                raise TypeError(f"{name} must be a tuple of AssessmentFinding values")
        if not isinstance(self.missing_requirements, tuple) or any(not isinstance(item, str) or not item.strip() for item in self.missing_requirements):
            raise TypeError("missing_requirements must be a tuple of non-empty strings")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string")


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    schema_version: int
    project_id: str
    project_title: str
    revision_id: str
    revision_version: int
    assessed_at: str
    status: ReadinessStatus
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]
    paradigm_assessments: tuple[ParadigmAssessment, ...]
    recommended_paradigms: tuple[Paradigm, ...]
    selected_paradigm: Paradigm | None
    clarification_items: tuple[ClarificationItem, ...]
    explanation: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported readiness report schema_version")
        for name in ("project_id", "project_title", "revision_id", "assessed_at", "explanation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.revision_version, bool) or not isinstance(self.revision_version, int) or self.revision_version < 1:
            raise ValueError("revision_version must be a positive integer")
        if not isinstance(self.status, ReadinessStatus):
            raise TypeError("status must be a ReadinessStatus")
        for name in ("validation_errors", "validation_warnings"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
                raise TypeError(f"{name} must be a tuple of strings")
        if not isinstance(self.paradigm_assessments, tuple) or any(not isinstance(item, ParadigmAssessment) for item in self.paradigm_assessments):
            raise TypeError("paradigm_assessments must be a tuple of ParadigmAssessment values")
        if not isinstance(self.recommended_paradigms, tuple) or any(not isinstance(item, Paradigm) for item in self.recommended_paradigms):
            raise TypeError("recommended_paradigms must be a tuple of Paradigm values")
        if self.selected_paradigm is not None and not isinstance(self.selected_paradigm, Paradigm):
            raise TypeError("selected_paradigm must be a Paradigm or None")
        if not isinstance(self.clarification_items, tuple) or any(not isinstance(item, ClarificationItem) for item in self.clarification_items):
            raise TypeError("clarification_items must be a tuple of ClarificationItem values")

    def assessment_for(self, paradigm: Paradigm) -> ParadigmAssessment:
        for item in self.paradigm_assessments:
            if item.paradigm is paradigm:
                return item
        raise LookupError(f"No assessment was produced for {paradigm.value}")

    @property
    def can_begin_implementation_planning(self) -> bool:
        return self.status is ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING
