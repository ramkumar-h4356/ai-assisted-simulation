"""Data contracts for the local knowledge corpus and mapping suggestions.

The knowledge layer stores traceable source material. Search relevance is not
interpreted as scientific confidence or proof of a proposed correspondence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable

from conceptual.model import EvidenceReference


class SourceKind(str, Enum):
    CURATED = "curated"
    USER_PROVIDED = "user_provided"
    IMPORTED = "imported"


def _text(value: object, name: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be empty")


def _strings(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list of strings")
    result = tuple(values)
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-empty strings")
    return result


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A searchable knowledge item linked to its bibliographic evidence record."""

    id: str
    title: str
    content: str
    reference: EvidenceReference
    domains: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    concept_labels: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    source_kind: SourceKind = SourceKind.CURATED
    language: str = "en"
    notes: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "knowledge document id")
        _text(self.title, "knowledge document title")
        _text(self.content, "knowledge document content")
        _text(self.language, "knowledge document language")
        _text(self.notes, "knowledge document notes", allow_empty=True)
        if not isinstance(self.reference, EvidenceReference):
            raise TypeError("knowledge document reference must be an EvidenceReference")
        year = self.reference.published_year
        if year is not None and not 1000 <= year <= 9999:
            raise ValueError("reference published_year must be a four-digit year")
        for name in ("domains", "keywords", "concept_labels", "authors"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source_kind must be a SourceKind")


@dataclass(frozen=True, slots=True)
class KnowledgeBase:
    """Immutable collection of documents; mutations return a new instance."""

    id: str
    name: str
    documents: tuple[KnowledgeDocument, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        _text(self.id, "knowledge base id")
        _text(self.name, "knowledge base name")
        _text(self.description, "knowledge base description", allow_empty=True)
        if not isinstance(self.documents, (tuple, list)):
            raise TypeError("documents must be a tuple or list")
        documents = tuple(self.documents)
        if any(not isinstance(item, KnowledgeDocument) for item in documents):
            raise TypeError("documents must contain only KnowledgeDocument objects")
        ids = [item.id for item in documents]
        if len(ids) != len(set(ids)):
            raise ValueError("knowledge document IDs must be unique within a knowledge base")
        object.__setattr__(self, "documents", documents)

    def get(self, document_id: str) -> KnowledgeDocument:
        for document in self.documents:
            if document.id == document_id:
                return document
        raise KeyError(f"Knowledge document {document_id!r} was not found")

    def add(self, document: KnowledgeDocument) -> "KnowledgeBase":
        if not isinstance(document, KnowledgeDocument):
            raise TypeError("document must be a KnowledgeDocument")
        if any(item.id == document.id for item in self.documents):
            raise ValueError(f"Knowledge document ID {document.id!r} already exists")
        return KnowledgeBase(self.id, self.name, self.documents + (document,), self.description)

    def remove(self, document_id: str) -> "KnowledgeBase":
        if not any(item.id == document_id for item in self.documents):
            raise KeyError(f"Knowledge document {document_id!r} was not found")
        return KnowledgeBase(
            self.id, self.name,
            tuple(item for item in self.documents if item.id != document_id),
            self.description,
        )


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked corpus result. The score is lexical relevance, not confidence."""

    document: KnowledgeDocument
    score: float
    matched_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.document, KnowledgeDocument):
            raise TypeError("document must be a KnowledgeDocument")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)) or not isfinite(self.score) or self.score < 0:
            raise ValueError("search score must be a finite non-negative number")
        object.__setattr__(self, "matched_terms", _strings(self.matched_terms, "matched_terms"))


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    """A human-reviewable possible correspondence between a concept and a source.

    ``relevance_score`` measures lexical retrieval relevance only. It is not a
    probability that the concepts are equivalent or that the source proves a claim.
    """

    id: str
    source_concept_id: str
    document_id: str
    target_label: str
    target_description: str
    rationale: str
    relevance_score: float
    matched_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("id", "source_concept_id", "document_id", "target_label", "rationale"):
            _text(getattr(self, name), f"mapping candidate {name}")
        _text(self.target_description, "mapping candidate target_description", allow_empty=True)
        if isinstance(self.relevance_score, bool) or not isinstance(self.relevance_score, (int, float)) or not isfinite(self.relevance_score) or self.relevance_score <= 0:
            raise ValueError("relevance_score must be a finite positive number")
        object.__setattr__(self, "matched_terms", _strings(self.matched_terms, "matched_terms"))
