from pathlib import Path

from conceptual import load_idea_project
from conceptual.model import EvidenceReference, ReferenceType
from knowledge import KnowledgeBase, KnowledgeDocument, SourceKind, load_knowledge_base

ROOT = Path(__file__).resolve().parents[2]


def sample_base():
    return load_knowledge_base(ROOT / "knowledge" / "sample_knowledge_base.json")


def sample_idea():
    return load_idea_project(ROOT / "scenarios" / "conceptual" / "decentralized_resource_cooperation.json")


def tiny_base():
    return KnowledgeBase(
        id="tiny", name="Tiny corpus", documents=(
            KnowledgeDocument(
                id="cooperation-doc", title="Cooperation in repeated interactions",
                content="Repeated interaction can support reciprocity and cooperation among individuals.",
                reference=EvidenceReference("ref-coop", "Cooperation reference", ReferenceType.ARTICLE,
                                            "https://example.org/cooperation", "Example Journal", 2020),
                domains=("social systems",), keywords=("cooperation", "reciprocity"),
                concept_labels=("reciprocal cooperation",), authors=("A. Author",),
                source_kind=SourceKind.USER_PROVIDED,
            ),
            KnowledgeDocument(
                id="queue-doc", title="Hospital queue operations",
                content="Patients arrive, wait in queues and receive service from limited resources.",
                reference=EvidenceReference("ref-queue", "Queue reference", ReferenceType.REPORT,
                                            "https://example.org/queues", "Example Institute", 2021),
                domains=("healthcare", "operations research"), keywords=("queue", "resource", "service"),
                concept_labels=("patient waiting line",), authors=("B. Author",),
            ),
        ),
    )
