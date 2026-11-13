from dataclasses import replace

import pytest

from conceptual import validate_idea_project, dumps_idea_project, loads_idea_project
from conceptual.model import MappingType, ReviewStatus
from knowledge import (
    KnowledgeMappingError, KnowledgeMappingService, MappingCandidate,
)
from tests.knowledge.helpers import sample_base, sample_idea, tiny_base


def test_suggestions_for_shared_resource_retrieve_ostrom_and_hardin():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidates = service.suggest_for_concept(project, "shared-resource", limit=5)
    source_ids = {item.document_id for item in candidates}
    assert "ostrom-governing-commons-1990" in source_ids
    assert "hardin-tragedy-commons-1968" in source_ids
    assert all(item.source_concept_id == "shared-resource" for item in candidates)


def test_mapping_candidates_explain_matched_terms_and_are_not_claims():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidates = service.suggest_for_concept(project, "shared-resource")
    assert candidates
    for candidate in candidates:
        assert candidate.matched_terms
        assert "does not establish equivalence" in candidate.rationale
        assert candidate.relevance_score > 0


def test_unknown_concept_cannot_generate_suggestions():
    service = KnowledgeMappingService(sample_base())
    with pytest.raises(KnowledgeMappingError, match="does not exist"):
        service.suggest_for_concept(sample_idea(), "missing-concept")


def test_record_candidate_appends_unreviewed_mapping_and_evidence():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    updated = service.record_candidate(project, candidate, revision_id="m5-revision-3", created_at="2026-11-13T04:00:00+00:00")
    assert len(project.revisions) == 2
    assert len(updated.revisions) == 3
    claim = updated.current_revision.mappings[-1]
    assert claim.review_status is ReviewStatus.UNREVIEWED
    assert claim.mapping_type is MappingType.ANALOGOUS
    assert claim.evidence_reference_ids
    assert updated.current_revision.evidence_references
    assert validate_idea_project(updated).is_valid


def test_record_candidate_does_not_overwrite_original_statement_or_old_snapshot():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    updated = service.record_candidate(project, candidate)
    assert updated.original_statement == project.original_statement
    assert updated.revisions[1] == project.revisions[1]


def test_review_acceptance_creates_an_additional_revision():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    recorded = service.record_candidate(project, candidate, revision_id="m5-revision-3")
    mapping_id = recorded.current_revision.mappings[-1].id
    reviewed = service.review_mapping(
        recorded, mapping_id, ReviewStatus.ACCEPTED,
        reviewer_note="The source is relevant to the resource-governance analogy.",
        revision_id="m5-revision-4",
    )
    assert len(reviewed.revisions) == 4
    claim = reviewed.current_revision.mappings[-1]
    assert claim.review_status is ReviewStatus.ACCEPTED
    assert "Reviewer note:" in claim.rationale
    assert recorded.current_revision.mappings[-1].review_status is ReviewStatus.UNREVIEWED
    assert validate_idea_project(reviewed).is_valid


def test_review_rejection_is_preserved_in_revision_history():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    recorded = service.record_candidate(project, candidate)
    mapping_id = recorded.current_revision.mappings[-1].id
    reviewed = service.review_mapping(recorded, mapping_id, ReviewStatus.REJECTED)
    assert reviewed.current_revision.mappings[-1].review_status is ReviewStatus.REJECTED
    assert recorded.current_revision.mappings[-1].review_status is ReviewStatus.UNREVIEWED


def test_mapping_review_requires_accept_or_reject():
    service = KnowledgeMappingService(sample_base())
    with pytest.raises(ValueError, match="ACCEPTED or REJECTED"):
        service.review_mapping(sample_idea(), "mapping-x", ReviewStatus.UNREVIEWED)


def test_missing_mapping_cannot_be_reviewed():
    service = KnowledgeMappingService(sample_base())
    with pytest.raises(KnowledgeMappingError, match="not found"):
        service.review_mapping(sample_idea(), "missing", ReviewStatus.ACCEPTED)


def test_duplicate_candidate_cannot_be_recorded_twice():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    recorded = service.record_candidate(project, candidate)
    with pytest.raises(KnowledgeMappingError, match="already been recorded"):
        service.record_candidate(recorded, candidate)


def test_candidate_with_unknown_document_is_rejected():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = MappingCandidate(
        id="candidate-x", source_concept_id="shared-resource", document_id="missing",
        target_label="Target", target_description="", rationale="Rationale",
        relevance_score=1.0, matched_terms=("resource",),
    )
    with pytest.raises(KnowledgeMappingError, match="not found"):
        service.record_candidate(project, candidate)


def test_candidate_with_unknown_concept_is_rejected():
    service = KnowledgeMappingService(sample_base())
    candidate = MappingCandidate(
        id="candidate-x", source_concept_id="missing", document_id="ostrom-governing-commons-1990",
        target_label="Target", target_description="", rationale="Rationale",
        relevance_score=1.0, matched_terms=("resource",),
    )
    with pytest.raises(KnowledgeMappingError, match="not present"):
        service.record_candidate(sample_idea(), candidate)


def test_evidence_reference_id_collision_gets_safe_new_id():
    project = sample_idea()
    current = project.current_revision
    # The seed corpus' Ostrom reference uses ref-ostrom-governing-commons-1990.
    # Reserve that ID for a different model element to exercise collision handling.
    concept = replace(current.concepts[0], id="ref-ostrom-governing-commons-1990")
    altered = replace(current, concepts=(concept,) + current.concepts[1:])
    project = replace(project, revisions=project.revisions[:-1] + (altered,))
    # Map a different still-existing concept so the colliding ID is not the source concept.
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    updated = service.record_candidate(project, candidate)
    evidence = updated.current_revision.evidence_references[0]
    assert evidence.id != "ref-ostrom-governing-commons-1990"
    assert evidence.id.startswith("evidence-")


def test_same_source_uri_reuses_existing_evidence_reference():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    first = service.record_candidate(project, candidate)
    mapping_id = first.current_revision.mappings[-1].id
    # Construct another candidate to same source but different candidate ID.
    second_candidate = replace(candidate, id="cand-second-for-same-source")
    second = service.record_candidate(first, second_candidate)
    assert len(second.current_revision.evidence_references) == 1
    assert len(second.current_revision.mappings) == len(first.current_revision.mappings) + 1


def test_updated_project_survives_conceptual_json_round_trip():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    updated = service.record_candidate(project, candidate)
    restored = loads_idea_project(dumps_idea_project(updated))
    assert restored == updated
    assert restored.current_revision.mappings[-1].evidence_reference_ids


def test_mapping_type_can_be_overridden_but_default_is_analogy():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    updated = service.record_candidate(project, candidate, mapping_type=MappingType.INSPIRED_BY)
    assert updated.current_revision.mappings[-1].mapping_type is MappingType.INSPIRED_BY


def test_mapping_type_must_be_enum():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidate = service.suggest_for_concept(project, "shared-resource")[0]
    with pytest.raises(TypeError):
        service.record_candidate(project, candidate, mapping_type="equivalent")


def test_demo_corpus_returns_relevant_candidates_for_decentralized_resources():
    from knowledge.demo import run_non_interactive_demo
    _, _, candidates = run_non_interactive_demo()
    assert candidates
    assert any("resource" in item.target_label.casefold() or "commons" in item.target_label.casefold() for item in candidates)


def test_custom_search_provider_can_be_injected_without_changing_mapping_flow():
    from knowledge import KnowledgeRetriever, KnowledgeSearchProvider

    base = sample_base()
    default_retriever = KnowledgeRetriever(base)

    class CustomProvider:
        def search(self, query, *, limit=10, filters=None):
            return default_retriever.search(query, limit=limit, filters=filters)

    provider = CustomProvider()
    assert isinstance(provider, KnowledgeSearchProvider)
    service = KnowledgeMappingService(base, retriever=provider)
    candidates = service.suggest_for_concept(sample_idea(), "shared-resource")
    assert candidates


def test_invalid_custom_search_provider_is_rejected():
    with pytest.raises(TypeError, match="KnowledgeSearchProvider"):
        KnowledgeMappingService(sample_base(), retriever=object())


def test_mapping_candidates_require_two_matched_terms_by_default_but_can_be_relaxed():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    strict = service.suggest_for_concept(project, "shared-resource")
    relaxed = service.suggest_for_concept(project, "shared-resource", min_matched_terms=1)
    assert strict
    assert all(len(item.matched_terms) >= 2 for item in strict)
    assert len(relaxed) >= len(strict)


def test_mapping_candidate_limit_applies_after_match_quality_filter():
    project = sample_idea()
    service = KnowledgeMappingService(sample_base())
    candidates = service.suggest_for_concept(project, "shared-resource", limit=1)
    assert len(candidates) == 1
    assert len(candidates[0].matched_terms) >= 2
