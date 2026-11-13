import pytest

from conceptual.model import ReferenceType
from knowledge import KnowledgeRetriever, RetrievalFilters
from tests.knowledge.helpers import sample_base, tiny_base


def test_retrieval_ranks_matching_cooperation_document_first():
    hits = KnowledgeRetriever(tiny_base()).search("cooperation reciprocity", limit=2)
    assert hits
    assert hits[0].document.id == "cooperation-doc"
    assert set(hits[0].matched_terms) == {"cooperation", "reciprocity"}
    assert hits[0].score > 0


def test_retrieval_returns_no_results_for_unmatched_terms():
    assert KnowledgeRetriever(tiny_base()).search("quantum entanglement") == ()


def test_retrieval_raises_when_query_is_empty_or_only_stopwords():
    retriever = KnowledgeRetriever(tiny_base())
    with pytest.raises(ValueError, match="non-empty"):
        retriever.search(" ")
    with pytest.raises(ValueError, match="no searchable terms"):
        retriever.search("the and of")


def test_limit_and_min_score_are_applied():
    retriever = KnowledgeRetriever(sample_base())
    assert len(retriever.search("shared resource community cooperation", limit=1)) <= 1
    assert retriever.search("shared resource community cooperation", min_score=1000) == ()


def test_domain_filter_limits_results():
    retriever = KnowledgeRetriever(sample_base())
    hits = retriever.search(
        "shared resources collective action",
        filters=RetrievalFilters(domains=("economics",)),
    )
    assert hits
    assert all("economics" in {item.casefold() for item in hit.document.domains} for hit in hits)


def test_reference_type_filter_limits_results():
    retriever = KnowledgeRetriever(sample_base())
    hits = retriever.search(
        "shared resource commons",
        filters=RetrievalFilters(reference_types=(ReferenceType.BOOK,)),
    )
    assert hits
    assert all(hit.document.reference.reference_type is ReferenceType.BOOK for hit in hits)


def test_source_kind_filter_limits_results():
    retriever = KnowledgeRetriever(tiny_base())
    hits = retriever.search("cooperation", filters=RetrievalFilters(source_kinds=("user_provided",)))
    assert hits
    assert all(hit.document.source_kind.value == "user_provided" for hit in hits)


def test_search_score_is_relevance_not_probability_by_contract():
    hit = KnowledgeRetriever(tiny_base()).search("cooperation")[0]
    assert hit.score > 0
    assert hit.score != 1.0 or isinstance(hit.score, float)


def test_invalid_filter_types_are_rejected():
    with pytest.raises(TypeError):
        RetrievalFilters(reference_types=("book",))
    with pytest.raises(ValueError):
        RetrievalFilters(domains=("",))


def test_invalid_query_arguments_are_rejected():
    retriever = KnowledgeRetriever(tiny_base())
    with pytest.raises(ValueError):
        retriever.search("cooperation", limit=0)
    with pytest.raises(ValueError):
        retriever.search("cooperation", min_score=-1)
    with pytest.raises(TypeError):
        retriever.search(None)


def test_bm25_parameters_are_validated():
    with pytest.raises(ValueError):
        KnowledgeRetriever(tiny_base(), k1=0)
    with pytest.raises(ValueError):
        KnowledgeRetriever(tiny_base(), b=1.5)
