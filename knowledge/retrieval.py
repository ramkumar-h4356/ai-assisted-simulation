"""Deterministic BM25-style retrieval over a local knowledge base.

The retrieval engine is deliberately lexical and explainable. It does not claim
semantic understanding, source quality, or truth assessment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Iterable

from conceptual.model import ReferenceType
from knowledge.models import KnowledgeBase, KnowledgeDocument, SearchHit
from knowledge.tokenizer import tokenize


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    domains: tuple[str, ...] = ()
    reference_types: tuple[ReferenceType, ...] = ()
    source_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("domains", "source_kinds"):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"{name} must contain non-empty strings")
            object.__setattr__(self, name, tuple(item.casefold() for item in value))
        if not isinstance(self.reference_types, (tuple, list)) or any(not isinstance(item, ReferenceType) for item in self.reference_types):
            raise TypeError("reference_types must contain ReferenceType values")
        object.__setattr__(self, "reference_types", tuple(self.reference_types))


def _weighted_terms(document: KnowledgeDocument) -> Counter[str]:
    counts: Counter[str] = Counter()
    # Field weights are integer boosts so the index remains transparent.
    counts.update(tokenize(document.content))
    counts.update(token for value in (document.title,) for token in tokenize(value) for _ in range(3))
    counts.update(token for value in document.concept_labels for token in tokenize(value) for _ in range(3))
    counts.update(token for value in document.keywords for token in tokenize(value) for _ in range(2))
    counts.update(token for value in document.domains for token in tokenize(value) for _ in range(1))
    counts.update(token for value in document.authors for token in tokenize(value))
    return counts


def _eligible(document: KnowledgeDocument, filters: RetrievalFilters) -> bool:
    if filters.domains and not set(filters.domains).intersection(item.casefold() for item in document.domains):
        return False
    if filters.reference_types and document.reference.reference_type not in filters.reference_types:
        return False
    if filters.source_kinds and document.source_kind.value.casefold() not in filters.source_kinds:
        return False
    return True


class KnowledgeRetriever:
    """Search a corpus using BM25-style term relevance with field boosts."""

    def __init__(self, base: KnowledgeBase, *, k1: float = 1.5, b: float = 0.75) -> None:
        if not isinstance(base, KnowledgeBase):
            raise TypeError("base must be a KnowledgeBase")
        if not isinstance(k1, (int, float)) or isinstance(k1, bool) or k1 <= 0 or not math.isfinite(k1):
            raise ValueError("k1 must be a finite positive number")
        if not isinstance(b, (int, float)) or isinstance(b, bool) or not 0 <= b <= 1 or not math.isfinite(b):
            raise ValueError("b must be a finite number from 0 to 1")
        self.base = base
        self.k1 = float(k1)
        self.b = float(b)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
        filters: RetrievalFilters | None = None,
    ) -> tuple[SearchHit, ...]:
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or min_score < 0 or not math.isfinite(min_score):
            raise ValueError("min_score must be a finite non-negative number")
        if filters is None:
            filters = RetrievalFilters()
        if not isinstance(filters, RetrievalFilters):
            raise TypeError("filters must be RetrievalFilters or None")

        query_terms = tuple(dict.fromkeys(tokenize(query)))
        if not query_terms:
            raise ValueError("query contains no searchable terms after tokenization")

        documents = [item for item in self.base.documents if _eligible(item, filters)]
        if not documents:
            return ()
        term_counts = {item.id: _weighted_terms(item) for item in documents}
        lengths = {item.id: sum(counts.values()) for item, counts in ((item, term_counts[item.id]) for item in documents)}
        average_length = sum(lengths.values()) / len(lengths) or 1.0
        document_frequency: Counter[str] = Counter()
        for counts in term_counts.values():
            document_frequency.update(counts.keys())

        scored: list[SearchHit] = []
        for document in documents:
            counts = term_counts[document.id]
            length = lengths[document.id]
            score = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                df = document_frequency[term]
                inverse_frequency = math.log(1.0 + (len(documents) - df + 0.5) / (df + 0.5))
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * length / average_length)
                score += inverse_frequency * (frequency * (self.k1 + 1.0)) / denominator
            if score > 0 and score >= min_score:
                matched = tuple(term for term in query_terms if counts.get(term, 0) > 0)
                scored.append(SearchHit(document, score, matched))

        scored.sort(key=lambda hit: (-hit.score, hit.document.title.casefold(), hit.document.id))
        return tuple(scored[:limit])
