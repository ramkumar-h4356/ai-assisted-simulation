"""Knowledge retrieval and human-reviewed real-world mapping layer."""

from knowledge.mapping import suggest_mapping_candidates
from knowledge.models import KnowledgeBase, KnowledgeDocument, MappingCandidate, SearchHit, SourceKind
from knowledge.repository import (
    KnowledgeBaseError, dumps_knowledge_base, knowledge_base_from_dict,
    knowledge_base_to_dict, load_knowledge_base, loads_knowledge_base,
    merge_knowledge_bases, save_knowledge_base,
)
from knowledge.retrieval import KnowledgeRetriever, RetrievalFilters
from knowledge.providers import KnowledgeSearchProvider
from knowledge.service import KnowledgeMappingError, KnowledgeMappingService

__all__ = [
    "KnowledgeBase", "KnowledgeBaseError", "KnowledgeDocument", "KnowledgeMappingError",
    "KnowledgeMappingService", "KnowledgeRetriever", "KnowledgeSearchProvider",
    "MappingCandidate", "RetrievalFilters",
    "SearchHit", "SourceKind", "dumps_knowledge_base", "knowledge_base_from_dict",
    "knowledge_base_to_dict", "load_knowledge_base", "loads_knowledge_base",
    "merge_knowledge_bases", "save_knowledge_base", "suggest_mapping_candidates",
]
