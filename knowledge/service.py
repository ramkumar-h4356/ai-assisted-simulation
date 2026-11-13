"""Application service joining retrieval, candidate generation and M4 revisions."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import Iterable

from conceptual.model import (
    EvidenceReference, IdeaProject, MappingClaim, MappingType, ReferenceType,
    ReviewStatus,
)
from conceptual.revision import revise_idea_project
from knowledge.mapping import suggest_mapping_candidates
from knowledge.models import KnowledgeBase, MappingCandidate, SearchHit
from knowledge.retrieval import KnowledgeRetriever, RetrievalFilters
from knowledge.providers import KnowledgeSearchProvider


class KnowledgeMappingError(ValueError):
    """Raised when a knowledge candidate cannot be safely applied to an idea."""


class KnowledgeMappingService:
    """Coordinate source search and explicit mapping-review operations."""

    def __init__(
        self, knowledge_base: KnowledgeBase,
        *, retriever: KnowledgeSearchProvider | None = None,
    ) -> None:
        if not isinstance(knowledge_base, KnowledgeBase):
            raise TypeError("knowledge_base must be a KnowledgeBase")
        self.knowledge_base = knowledge_base
        self.retriever = retriever or KnowledgeRetriever(knowledge_base)
        if not isinstance(self.retriever, KnowledgeSearchProvider):
            raise TypeError("retriever must implement KnowledgeSearchProvider")

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> tuple[SearchHit, ...]:
        return self.retriever.search(query, limit=limit, filters=filters)

    def suggest_for_concept(
        self,
        project: IdeaProject,
        concept_id: str,
        *,
        query: str | None = None,
        limit: int = 5,
        min_matched_terms: int = 2,
        filters: RetrievalFilters | None = None,
    ) -> tuple[MappingCandidate, ...]:
        if not isinstance(project, IdeaProject):
            raise TypeError("project must be an IdeaProject")
        concept = next((item for item in project.current_revision.concepts if item.id == concept_id), None)
        if concept is None:
            raise KnowledgeMappingError(f"Concept {concept_id!r} does not exist in the current revision")
        return suggest_mapping_candidates(
            concept, self.knowledge_base, query=query, limit=limit,
            min_matched_terms=min_matched_terms, filters=filters,
            retriever=self.retriever,
        )

    def record_candidate(
        self,
        project: IdeaProject,
        candidate: MappingCandidate,
        *,
        review_status: ReviewStatus = ReviewStatus.UNREVIEWED,
        mapping_type: MappingType = MappingType.ANALOGOUS,
        change_summary: str | None = None,
        revision_id: str | None = None,
        created_at: str | None = None,
    ) -> IdeaProject:
        """Append a mapping claim and source reference in a new project revision.

        The default action records an *unreviewed* proposal. The caller must make
        an explicit review decision before the mapping is treated as accepted.
        """
        if not isinstance(project, IdeaProject):
            raise TypeError("project must be an IdeaProject")
        if not isinstance(candidate, MappingCandidate):
            raise TypeError("candidate must be a MappingCandidate")
        if not isinstance(review_status, ReviewStatus):
            raise TypeError("review_status must be a ReviewStatus")
        if not isinstance(mapping_type, MappingType):
            raise TypeError("mapping_type must be a MappingType")

        revision = project.current_revision
        if candidate.source_concept_id not in {item.id for item in revision.concepts}:
            raise KnowledgeMappingError("Candidate source concept is not present in the current revision")
        try:
            document = self.knowledge_base.get(candidate.document_id)
        except KeyError as error:
            raise KnowledgeMappingError(str(error)) from error

        mapping_id = f"mapping-{candidate.id}"
        all_ids = _revision_element_ids(revision)
        if mapping_id in all_ids:
            raise KnowledgeMappingError(f"Mapping candidate {candidate.id!r} has already been recorded")

        evidence = _find_or_create_evidence(document.reference, revision, document.id)
        evidence_references = revision.evidence_references
        if all(item.id != evidence.id for item in evidence_references):
            evidence_references = evidence_references + (evidence,)

        claim = MappingClaim(
            id=mapping_id,
            source_concept_id=candidate.source_concept_id,
            target_label=candidate.target_label,
            mapping_type=mapping_type,
            rationale=candidate.rationale,
            target_description=candidate.target_description,
            evidence_reference_ids=(evidence.id,),
            review_status=review_status,
        )
        summary = change_summary or (
            f"Record mapping candidate {candidate.id} for concept "
            f"{candidate.source_concept_id} as {review_status.value}."
        )
        return revise_idea_project(
            project,
            change_summary=summary,
            revision_id=revision_id,
            created_at=created_at,
            evidence_references=evidence_references,
            mappings=revision.mappings + (claim,),
        )

    def review_mapping(
        self,
        project: IdeaProject,
        mapping_id: str,
        decision: ReviewStatus,
        *,
        reviewer_note: str = "",
        revision_id: str | None = None,
        created_at: str | None = None,
    ) -> IdeaProject:
        """Append a new revision containing an explicit accept/reject decision."""
        if not isinstance(project, IdeaProject):
            raise TypeError("project must be an IdeaProject")
        if decision not in {ReviewStatus.ACCEPTED, ReviewStatus.REJECTED}:
            raise ValueError("decision must be ACCEPTED or REJECTED")
        if not isinstance(reviewer_note, str):
            raise TypeError("reviewer_note must be a string")
        revision = project.current_revision
        found = False
        updated = []
        for claim in revision.mappings:
            if claim.id == mapping_id:
                found = True
                rationale = claim.rationale
                if reviewer_note.strip():
                    rationale = f"{rationale}\nReviewer note: {reviewer_note.strip()}"
                updated.append(replace(claim, review_status=decision, rationale=rationale))
            else:
                updated.append(claim)
        if not found:
            raise KnowledgeMappingError(f"Mapping claim {mapping_id!r} was not found")
        return revise_idea_project(
            project,
            change_summary=f"{decision.value.capitalize()} mapping {mapping_id}.",
            revision_id=revision_id,
            created_at=created_at,
            mappings=tuple(updated),
        )


def _revision_element_ids(revision) -> set[str]:
    group_names = (
        "concepts", "properties", "relationships", "mechanisms", "hypotheses",
        "assumptions", "constraints", "evidence_references", "mappings", "open_questions",
    )
    return {item.id for name in group_names for item in getattr(revision, name)}


def _find_or_create_evidence(reference: EvidenceReference, revision, document_id: str) -> EvidenceReference:
    for existing in revision.evidence_references:
        if existing.id == reference.id:
            if existing == reference:
                return existing
            # Same source metadata ID is already in use for different evidence.
            break
        if existing.uri and reference.uri and existing.uri == reference.uri:
            return existing
    used = _revision_element_ids(revision)
    identifier = reference.id
    if identifier in used:
        seed = f"{document_id}|{reference.title}|{reference.uri or ''}"
        identifier = "evidence-" + sha256(seed.encode("utf-8")).hexdigest()[:16]
        suffix = 2
        while identifier in used:
            identifier = f"evidence-{sha256(seed.encode('utf-8')).hexdigest()[:12]}-{suffix}"
            suffix += 1
    if identifier == reference.id:
        return reference
    return replace(reference, id=identifier)
