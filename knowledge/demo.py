"""Interactive M5 knowledge retrieval and reviewed-mapping workflow."""

from __future__ import annotations

from pathlib import Path
import re

from conceptual import load_idea_project, save_idea_project
from conceptual.model import MappingType, ReviewStatus
from knowledge import KnowledgeMappingService, load_knowledge_base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_IDEA = PROJECT_ROOT / "scenarios" / "conceptual" / "decentralized_resource_cooperation.json"
SAMPLE_KNOWLEDGE_BASE = Path(__file__).resolve().parent / "sample_knowledge_base.json"


def run_interactive_workflow() -> None:
    """Let a person search sources, inspect candidates and record a decision."""
    project = load_idea_project(SAMPLE_IDEA)
    base = load_knowledge_base(SAMPLE_KNOWLEDGE_BASE)
    service = KnowledgeMappingService(base)

    print("\n--- M5: Knowledge Retrieval and Real-World Mapping ---")
    print(f"Idea: {project.title}")
    print(f"Knowledge corpus: {base.name} ({len(base.documents)} documents)")
    print("\nConcepts in the current idea:")
    for concept in project.current_revision.concepts:
        definition = concept.definition or "No definition supplied yet."
        print(f"  {concept.id}: {concept.name} — {definition}")

    concept_id = input("\nEnter the concept ID to explore: ").strip()
    query = input("Search query (Enter uses the concept name and definition): ").strip() or None
    try:
        candidates = service.suggest_for_concept(project, concept_id, query=query, limit=5)
    except (ValueError, KeyError) as error:
        print(f"Could not generate mapping candidates: {error}")
        return

    if not candidates:
        print("No lexical matches were found. Try broader or different terms.")
        return

    print("\n--- Retrieved Mapping Candidates ---")
    for index, candidate in enumerate(candidates, start=1):
        document = base.get(candidate.document_id)
        print(f"\n{index}. {candidate.target_label}")
        print(f"   Source: {document.reference.title}")
        print(f"   Publisher: {document.reference.publisher or 'Not specified'} ({document.reference.published_year or 'Year unknown'})")
        print(f"   Retrieval relevance score: {candidate.relevance_score:.4f} (not a confidence score)")
        print(f"   Matched terms: {', '.join(candidate.matched_terms)}")
        print(f"   URI: {document.reference.uri or 'Not supplied'}")
        print(f"   Why retrieved: {candidate.rationale}")

    selection = input("\nSelect a candidate number to add to the idea (or press Enter to cancel): ").strip()
    if not selection:
        print("No mapping was recorded.")
        return
    try:
        selected_index = int(selection) - 1
        candidate = candidates[selected_index]
    except (ValueError, IndexError):
        print("Invalid candidate selection. No mapping was recorded.")
        return

    try:
        updated = service.record_candidate(
            project,
            candidate,
            review_status=ReviewStatus.UNREVIEWED,
            mapping_type=MappingType.ANALOGOUS,
            change_summary=f"Record retrieved analogy candidate for {concept_id}; awaiting human review.",
        )
    except ValueError as error:
        print(f"Could not record candidate: {error}")
        return

    decision = input("\nReview this analogy now? Enter 'a' to accept, 'r' to reject, or Enter to leave unreviewed: ").strip().lower()
    mapping_id = f"mapping-{candidate.id}"
    if decision == "a":
        updated = service.review_mapping(
            updated, mapping_id, ReviewStatus.ACCEPTED,
            reviewer_note="Accepted by the user in the M5 interactive workflow.",
        )
    elif decision == "r":
        updated = service.review_mapping(
            updated, mapping_id, ReviewStatus.REJECTED,
            reviewer_note="Rejected by the user in the M5 interactive workflow.",
        )
    elif decision:
        print("Unrecognized decision; candidate remains unreviewed.")

    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9_-]+", "_", project.id.casefold()).strip("_") or "idea"
    destination = output_dir / f"{stem}_with_m5_mapping.json"
    version = 2
    while destination.exists():
        destination = output_dir / f"{stem}_with_m5_mapping_v{version}.json"
        version += 1
    save_idea_project(updated, destination)
    final_mapping = next(item for item in updated.current_revision.mappings if item.id == mapping_id)
    print(f"\nRecorded status: {final_mapping.review_status.value}")
    print(f"Project with mapping history saved to: {destination}")
    print("The original idea and earlier revisions remain unchanged.")


def run_non_interactive_demo() -> tuple:
    """Return sample ranked results for automated checks and quick inspection."""
    project = load_idea_project(SAMPLE_IDEA)
    base = load_knowledge_base(SAMPLE_KNOWLEDGE_BASE)
    service = KnowledgeMappingService(base)
    concept = next((item for item in project.current_revision.concepts if item.id == "shared-resource"), None)
    if concept is None:
        concept = next((item for item in project.current_revision.concepts if "resource" in item.name.casefold()), project.current_revision.concepts[0])
    candidates = service.suggest_for_concept(project, concept.id, limit=5)
    print(f"Idea concept: {concept.name}")
    print(f"Retrieved {len(candidates)} candidate mappings from {len(base.documents)} source records.")
    for candidate in candidates:
        print(f"- {candidate.target_label}: {candidate.relevance_score:.4f}; terms={', '.join(candidate.matched_terms)}")
    return project, base, candidates


def main() -> None:
    run_interactive_workflow()


if __name__ == "__main__":
    main()
