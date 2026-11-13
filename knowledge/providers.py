"""Protocols for swapping retrieval strategies without changing the model layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from knowledge.models import SearchHit
from knowledge.retrieval import RetrievalFilters


@runtime_checkable
class KnowledgeSearchProvider(Protocol):
    """A retrieval backend that searches the current corpus document contract.

    The included implementation is lexical BM25-style retrieval. A future
    semantic/vector or external-index provider can implement this protocol and
    return SearchHit objects backed by documents already ingested in the same
    KnowledgeBase. The conceptual model and mapping-review API remain unchanged.
    """

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> tuple[SearchHit, ...]: ...
