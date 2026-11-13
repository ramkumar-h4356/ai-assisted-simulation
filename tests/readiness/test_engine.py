from dataclasses import replace

import pytest

from conceptual import (
    Concept, ConceptKind, DefinitionStatus, OpenQuestion, Property, PropertyType,
    QuestionStatus,
)
from readiness import (
    BackendStatus, FitLevel, Paradigm, ReadinessStatus, assess_readiness,
)
from tests.readiness.helpers import (
    abm_project, data_project, des_project, make_project, mathematical_project,
)


def test_evaluates_all_four_paradigms_and_reports_backend_availability():
    report = assess_readiness(des_project())
    assert {item.paradigm for item in report.paradigm_assessments} == set(Paradigm)
    assert report.assessment_for(Paradigm.DISCRETE_EVENT).backend_status is BackendStatus.IMPLEMENTED
    assert report.assessment_for(Paradigm.AGENT_BASED).backend_status is BackendStatus.IMPLEMENTED
    assert report.assessment_for(Paradigm.MATHEMATICAL).backend_status is BackendStatus.ASSESSMENT_ONLY
    assert report.assessment_for(Paradigm.DATA_DRIVEN).backend_status is BackendStatus.ASSESSMENT_ONLY


def test_des_evaluator_recognizes_process_resource_and_operational_event_rule():
    report = assess_readiness(des_project())
    assessment = report.assessment_for(Paradigm.DISCRETE_EVENT)
    assert assessment.fit is FitLevel.STRONG
    assert any(item.code == "DES_EVENT_MECHANISM" for item in assessment.supporting_findings)


def test_abm_evaluator_recognizes_agents_interactions_and_behaviour():
    assessment = assess_readiness(abm_project()).assessment_for(Paradigm.AGENT_BASED)
    assert assessment.fit is FitLevel.STRONG
    assert any(item.code == "ABM_BEHAVIOUR_MECHANISM" for item in assessment.supporting_findings)


def test_mathematical_evaluator_requires_variables_and_quantitative_relation():
    assessment = assess_readiness(mathematical_project()).assessment_for(Paradigm.MATHEMATICAL)
    assert assessment.fit is FitLevel.STRONG
    assert any(item.code == "MATH_QUANTITATIVE_RELATIONS" for item in assessment.supporting_findings)


def test_data_driven_evaluator_requires_dataset_reference_and_measurable_temporal_fields():
    assessment = assess_readiness(data_project()).assessment_for(Paradigm.DATA_DRIVEN)
    assert assessment.fit is FitLevel.STRONG
    assert any(item.code == "DATA_FILE_NOT_VERIFIED" for item in assessment.limitations)


def test_data_citation_is_not_misrepresented_as_verified_dataset_access():
    assessment = assess_readiness(data_project()).assessment_for(Paradigm.DATA_DRIVEN)
    assert any("not verified" in item.title.lower() for item in assessment.limitations)


def test_conceptual_project_is_never_mutated_by_assessment():
    project = des_project()
    before = project
    report = assess_readiness(project)
    assert project is before
    assert project.current_revision.id == report.revision_id
    assert len(project.revisions) == 2


def test_report_is_bound_to_exact_revision():
    project = des_project()
    report = assess_readiness(project)
    assert report.project_id == project.id
    assert report.revision_id == project.current_revision.id
    assert report.revision_version == project.current_revision.version


def test_projects_with_no_concepts_need_clarification_and_have_no_recommendation():
    report = assess_readiness(make_project())
    assert report.status is ReadinessStatus.NEEDS_CLARIFICATION
    assert report.recommended_paradigms == ()


def test_open_blocking_questions_keep_project_in_clarification_status():
    question = OpenQuestion("q1", "What determines allocation?", (), True, QuestionStatus.OPEN, "")
    report = assess_readiness(des_project_with_question(question))
    assert report.status is ReadinessStatus.NEEDS_CLARIFICATION
    assert any(item.id == "q1" for item in report.clarification_items)


def des_project_with_question(question):
    project = des_project()
    from conceptual import revise_idea_project
    return revise_idea_project(
        project, change_summary="Add an unresolved question.",
        open_questions=(question,),
    )


def test_invalid_project_is_not_assessable():
    project = des_project()
    from conceptual import revise_idea_project
    broken = revise_idea_project(
        project, change_summary="Introduce an invalid concept reference.",
        properties=project.current_revision.properties + (
            Property("bad-owner", "unknown-concept", "Unknown field", PropertyType.TEXT),
        ),
    )
    report = assess_readiness(broken)
    assert report.status is ReadinessStatus.NOT_ASSESSABLE
    assert report.validation_errors


def test_partial_concept_and_unknown_property_type_create_traceable_questions():
    project = make_project(
        concepts=(Concept("x", "Unclear concept", ConceptKind.ABSTRACT, definition="", status=DefinitionStatus.PARTIAL),),
        properties=(Property("p", "x", "Unclear property", PropertyType.UNKNOWN),),
    )
    report = assess_readiness(project)
    ids = {item.id for item in report.clarification_items}
    assert "m7-concept-x" in ids
    assert "m7-property-type-p" in ids


def test_multiple_strong_paradigms_are_not_forced_into_one_winner():
    project = des_project()
    from conceptual import revise_idea_project
    current = project.current_revision
    both = revise_idea_project(
        project, change_summary="Add agent behaviour to the same system.",
        concepts=current.concepts + (
            Concept("worker", "Worker", ConceptKind.ACTOR, definition="An autonomous worker.", status=DefinitionStatus.DEFINED),
        ),
        relationships=current.relationships + (
            __import__("conceptual").Relationship("worker-machine", "worker", "machine", "operates", "A worker operates a machine.", True, DefinitionStatus.DEFINED),
        ),
        mechanisms=current.mechanisms + (
            __import__("conceptual").Mechanism("worker-action", "Worker decision", "A worker chooses a task.", ("worker",), ("machine",), "When a task is available.", "The worker starts the task.", "If idle and a task is available, choose the first queued task.", DefinitionStatus.DEFINED),
        ),
    )
    report = assess_readiness(both)
    assert Paradigm.DISCRETE_EVENT in report.recommended_paradigms
    assert Paradigm.AGENT_BASED in report.recommended_paradigms


def test_selected_paradigm_is_recorded_without_claiming_unsupported_backend():
    report = assess_readiness(mathematical_project(), selected_paradigm=Paradigm.MATHEMATICAL)
    assert report.selected_paradigm is Paradigm.MATHEMATICAL
    assert report.status is not ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING
    assert report.assessment_for(Paradigm.MATHEMATICAL).backend_status is BackendStatus.ASSESSMENT_ONLY


def test_ready_for_implementation_planning_requires_strong_fit_and_implemented_backend():
    project = des_project()
    report = assess_readiness(project, selected_paradigm=Paradigm.DISCRETE_EVENT)
    assert report.status is ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING


def test_selected_poor_fit_is_downgraded_to_needs_clarification():
    report = assess_readiness(abm_project(), selected_paradigm=Paradigm.DATA_DRIVEN)
    assert report.status is ReadinessStatus.NEEDS_CLARIFICATION


def test_invalid_selected_paradigm_is_rejected():
    with pytest.raises(ValueError, match="Unsupported paradigm"):
        assess_readiness(des_project(), selected_paradigm="quantum")
