"""Generate explainable, human-reviewable real-world mapping candidates."""

from __future__ import annotations

from hashlib import sha256

from conceptual.model import Concept
from knowledge.models import KnowledgeBase, MappingCandidate
from knowledge.retrieval import KnowledgeRetriever, RetrievalFilters
from knowledge.providers import KnowledgeSearchProvider
from knowledge.tokenizer import tokenize


def suggest_mapping_candidates(
    concept: Concept,
    base: KnowledgeBase,
    *,
    query: str | None = None,
    limit: int = 5,
    min_matched_terms: int = 2,
    filters: RetrievalFilters | None = None,
    retriever: KnowledgeSearchProvider | None = None,
) -> tuple[MappingCandidate, ...]:
    """Suggest source analogies from lexical retrieval; never auto-approve them.

    One label is selected per source document: the indexed target label with the
    greatest token overlap against the query. The label-selection step remains
    lexical and is exposed in the explanation.
    """
    if not isinstance(concept, Concept):
        raise TypeError("concept must be a Concept")
    if not isinstance(base, KnowledgeBase):
        raise TypeError("base must be a KnowledgeBase")
    search_text = query if query is not None else " ".join(
        part for part in (concept.name, concept.definition, concept.source_note) if part.strip()
    )
    if not isinstance(search_text, str) or not search_text.strip():
        raise ValueError("concept or query must provide searchable text")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if isinstance(min_matched_terms, bool) or not isinstance(min_matched_terms, int) or min_matched_terms < 1:
        raise ValueError("min_matched_terms must be a positive integer")

    query_tokens = set(tokenize(search_text))
    search_provider = retriever or KnowledgeRetriever(base)
    # Retrieve enough of the local corpus to apply the stricter match-count
    # gate without silently discarding stronger matches just below a weak hit.
    hits = search_provider.search(search_text, limit=max(limit, len(base.documents)), filters=filters)
    candidates: list[MappingCandidate] = []
    for hit in hits:
        if len(hit.matched_terms) < min_matched_terms:
            continue
        document = hit.document
        labels = document.concept_labels or (document.title,)
        label = max(
            enumerate(labels),
            key=lambda pair: (len(query_tokens.intersection(tokenize(pair[1]))), -pair[0]),
        )[1]
        candidate_key = f"{concept.id}|{document.id}|{label.casefold()}"
        candidate_id = "cand-" + sha256(candidate_key.encode("utf-8")).hexdigest()[:16]
        terms = ", ".join(hit.matched_terms)
        rationale = (
            f"Lexical retrieval matched these terms: {terms}. The selected target label "
            "is the source's indexed label with the strongest token overlap. This is a "
            "possible analogy or comparison lead only. Review the source scope and "
            "limitations; retrieval similarity does not establish equivalence or prove the theory."
        )
        candidates.append(MappingCandidate(
            id=candidate_id,
            source_concept_id=concept.id,
            document_id=document.id,
            target_label=label,
            target_description=document.content,
            rationale=rationale,
            relevance_score=hit.score,
            matched_terms=hit.matched_terms,
        ))
    return tuple(candidates[:limit])
