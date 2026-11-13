from dataclasses import replace

import pytest

from conceptual import (
    Assumption, Concept, ConceptKind, ConceptOrigin, Constraint, DefinitionStatus,
    EvidenceReference, Hypothesis, HypothesisStatus, MappingClaim, MappingType,
    Mechanism, OpenQuestion, Property, PropertyType, QuestionStatus, ReferenceType,
    Relationship, ReviewStatus, Readiness, validate_idea_project,
)
from tests.conceptual.helpers import make_project


def codes(report):
    return {issue.code for issue in report.issues}


def test_valid_minimal_project_is_review_ready():
    report = validate_idea_project(make_project())
    assert report.is_valid
    assert report.readiness is Readiness.REVIEW_READY


def test_unresolved_blocking_question_is_warning_not_error():
    project = make_project()
    updated = replace(
        project,
        revisions=(project.revisions[0], replace(
            project.current_revision,
            open_questions=(OpenQuestion("q1", "How does it work?", ("participant",), True),),
        )),
    )
    report = validate_idea_project(updated)
    assert report.is_valid
    assert "BLOCKING_OPEN_QUESTION" in codes(report)
    assert report.readiness is Readiness.IN_PROGRESS


def test_partial_mechanism_is_allowed_but_warned():
    project = make_project()
    current = project.current_revision
    mechanism = Mechanism("m1", "Cooperation", input_concept_ids=("participant",))
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, mechanisms=(mechanism,)),))
    report = validate_idea_project(project)
    assert report.is_valid
    assert "MECHANISM_ENDPOINTS_INCOMPLETE" in codes(report)
    assert "MECHANISM_NOT_OPERATIONALIZED" in codes(report)


def test_unknown_property_owner_is_error():
    project = make_project()
    current = project.current_revision
    prop = Property("p1", "missing-concept", "Trust", PropertyType.NUMBER)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, properties=(prop,)),))
    report = validate_idea_project(project)
    assert "UNKNOWN_CONCEPT" in codes(report)
    assert not report.is_valid


def test_unknown_relationship_endpoint_is_error():
    project = make_project()
    current = project.current_revision
    relationship = Relationship("r1", "participant", "missing", "connected to")
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, relationships=(relationship,)),))
    assert "UNKNOWN_CONCEPT" in codes(validate_idea_project(project))


def test_defined_concept_without_definition_is_error():
    project = make_project()
    current = project.current_revision
    concept = Concept("empty-definition", "Incomplete", status=DefinitionStatus.DEFINED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, concepts=current.concepts + (concept,)),))
    assert "DEFINED_CONCEPT_WITHOUT_DEFINITION" in codes(validate_idea_project(project))


def test_real_world_mapped_concept_requires_mapping_claim_warning():
    project = make_project()
    current = project.current_revision
    mapped = Concept("mapped", "Mapped concept", origin=ConceptOrigin.REAL_WORLD_MAPPED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, concepts=current.concepts + (mapped,)),))
    report = validate_idea_project(project)
    assert "MISSING_MAPPING_CLAIM" in codes(report)
    assert report.is_valid


def test_ai_proposed_concept_without_provenance_note_is_warned():
    project = make_project()
    current = project.current_revision
    concept = Concept("ai", "AI concept", origin=ConceptOrigin.AI_PROPOSED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, concepts=current.concepts + (concept,)),))
    assert "MISSING_AI_PROVENANCE_NOTE" in codes(validate_idea_project(project))


def test_mapping_unknown_source_and_evidence_are_errors():
    project = make_project()
    current = project.current_revision
    mapping = MappingClaim("map", "missing", "Analogy", MappingType.ANALOGOUS, "Reason", evidence_reference_ids=("missing-ref",))
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, mappings=(mapping,)),))
    report = validate_idea_project(project)
    assert "UNKNOWN_CONCEPT" in codes(report)
    assert "UNKNOWN_REFERENCE" in codes(report)
    assert not report.is_valid


def test_accepted_equivalence_without_evidence_is_warned():
    project = make_project()
    current = project.current_revision
    mapping = MappingClaim("map", "participant", "Person", MappingType.EQUIVALENT, "Similar definitions", review_status=ReviewStatus.ACCEPTED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, mappings=(mapping,)),))
    report = validate_idea_project(project)
    assert "ACCEPTED_MAPPING_WITHOUT_EVIDENCE" in codes(report)
    assert report.is_valid


def test_hypothesis_with_unknown_evidence_reference_is_error():
    project = make_project()
    current = project.current_revision
    hypothesis = Hypothesis("h", "Cooperation increases efficiency", evidence_reference_ids=("missing",))
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, hypotheses=(hypothesis,)),))
    assert "UNKNOWN_REFERENCE" in codes(validate_idea_project(project))


def test_untested_hypothesis_without_evidence_is_warned_not_rejected():
    project = make_project()
    current = project.current_revision
    hypothesis = Hypothesis("h", "A proposed relationship", status=HypothesisStatus.UNTESTED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, hypotheses=(hypothesis,)),))
    report = validate_idea_project(project)
    assert report.is_valid
    assert "UNTESTED_HYPOTHESIS" in codes(report)


def test_question_must_reference_existing_model_element():
    project = make_project()
    current = project.current_revision
    question = OpenQuestion("q", "What does this mean?", ("nonexistent",))
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, open_questions=(question,)),))
    assert "UNKNOWN_REFERENCE" in codes(validate_idea_project(project))


def test_resolved_question_requires_resolution_text():
    project = make_project()
    current = project.current_revision
    question = OpenQuestion("q", "How?", status=QuestionStatus.RESOLVED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, open_questions=(question,)),))
    assert "MISSING_QUESTION_RESOLUTION" in codes(validate_idea_project(project))


def test_duplicate_ids_across_element_types_are_error():
    project = make_project()
    current = project.current_revision
    prop = Property("participant", "participant", "A property")
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, properties=(prop,)),))
    assert "DUPLICATE_GLOBAL_ID" in codes(validate_idea_project(project))


def test_broken_revision_chain_is_error():
    project = make_project()
    latest = replace(project.current_revision, parent_revision_id="unknown-parent")
    project = replace(project, revisions=project.revisions[:-1] + (latest,))
    assert "BROKEN_REVISION_CHAIN" in codes(validate_idea_project(project))


def test_current_revision_must_be_latest():
    project = make_project()
    project = replace(project, current_revision_id=project.revisions[0].id)
    assert "CURRENT_REVISION_NOT_LATEST" in codes(validate_idea_project(project))


def test_non_sequential_revision_versions_are_error():
    project = make_project()
    second = replace(project.current_revision, version=3)
    project = replace(project, revisions=(project.revisions[0], second))
    assert "NON_SEQUENTIAL_VERSIONS" in codes(validate_idea_project(project))


def test_invalid_evidence_year_is_error():
    project = make_project()
    current = project.current_revision
    evidence = EvidenceReference("e1", "A source", ReferenceType.ARTICLE, published_year=15000)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, evidence_references=(evidence,)),))
    assert "INVALID_PUBLICATION_YEAR" in codes(validate_idea_project(project))


def test_validation_rejects_non_project_input():
    with pytest.raises(TypeError):
        validate_idea_project({})


def test_empty_current_revision_is_valid_but_in_progress():
    from conceptual import create_idea_project
    project = create_idea_project("New", "An initial unstructured idea", project_id="p", revision_id="r1", created_at="2026-11-13T00:00:00+00:00")
    report = validate_idea_project(project)
    assert report.is_valid
    assert report.readiness is Readiness.IN_PROGRESS
    assert "NO_CONCEPTS" in codes(report)


def test_unreviewed_mapping_is_explicitly_warned():
    project = make_project()
    current = project.current_revision
    mapping = MappingClaim("map", "participant", "Community member", MappingType.ANALOGOUS, "Candidate analogy")
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, mappings=(mapping,)),))
    report = validate_idea_project(project)
    assert "UNREVIEWED_MAPPING_CLAIM" in codes(report)
    assert report.is_valid


def test_hypothesis_status_without_evidence_is_warned():
    project = make_project()
    current = project.current_revision
    hypothesis = Hypothesis("h", "A claim", status=HypothesisStatus.SUPPORTED)
    project = replace(project, revisions=project.revisions[:-1] + (replace(current, hypotheses=(hypothesis,)),))
    assert "HYPOTHESIS_STATUS_WITHOUT_EVIDENCE" in codes(validate_idea_project(project))
