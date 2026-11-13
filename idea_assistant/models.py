"""Data contracts for M6 AI-assisted idea interpretation and clarification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ClarificationQuestion:
    id: str
    question: str
    reason: str = ""
    related_concepts: tuple[str, ...] = ()
    blocking: bool = True
    priority: str = "medium"


@dataclass(frozen=True, slots=True)
class ClarificationExchange:
    question_id: str
    question: str
    answer: str
    round_number: int


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    document_id: str
    title: str
    summary: str
    uri: str | None
    relevance_score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdeaDraft:
    """Validated, normalized interpretation returned by an interpreter."""

    title: str
    working_statement: str
    summary: str
    concepts: tuple[dict[str, Any], ...]
    properties: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    mechanisms: tuple[dict[str, Any], ...]
    hypotheses: tuple[dict[str, Any], ...]
    assumptions: tuple[dict[str, Any], ...]
    constraints: tuple[dict[str, Any], ...]
    clarification_questions: tuple[ClarificationQuestion, ...]
    uncertainties: tuple[str, ...]
    retrieval_queries: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return model-facing fields without application-generated question IDs."""
        from dataclasses import asdict
        value = asdict(self)
        value["clarification_questions"] = [
            {key: item[key] for key in ("question", "reason", "related_concepts", "blocking", "priority")}
            for item in value["clarification_questions"]
        ]
        return value


@dataclass(frozen=True, slots=True)
class IdeaAssistantSession:
    id: str
    project_id: str
    created_at: str
    initial_request: str
    clarification_history: tuple[ClarificationExchange, ...]
    retrieved_context: tuple[RetrievedContext, ...]
    final_summary: str
    uncertainties: tuple[str, ...]


def new_session_id() -> str:
    return f"session-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
