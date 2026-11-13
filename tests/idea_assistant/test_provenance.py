from dataclasses import replace

from conceptual import create_idea_project, revise_idea_project, validate_idea_project
from conceptual.model import ProvenanceKind, ProvenanceRecord
from idea_assistant.models import ClarificationQuestion, IdeaDraft


def test_provenance_must_reference_a_real_element():
    project = create_idea_project("Idea", "The user idea.")
    updated = revise_idea_project(
        project,
        change_summary="Add intentionally invalid provenance for validation test.",
        provenance_records=(ProvenanceRecord(
            id="prov-bad", element_id="missing-element", kind=ProvenanceKind.AI_INFERRED,
        ),),
    )
    report = validate_idea_project(updated)
    assert any(issue.code == "UNKNOWN_PROVENANCE_ELEMENT" for issue in report.errors)


def test_refinement_payload_hides_application_generated_question_id():
    draft = IdeaDraft(
        title="An idea", working_statement="A working statement.", summary="",
        concepts=(), properties=(), relationships=(), mechanisms=(), hypotheses=(),
        assumptions=(), constraints=(),
        clarification_questions=(ClarificationQuestion(
            id="clarification-1", question="What does X mean?", reason="It matters.",
        ),),
        uncertainties=(), retrieval_queries=(),
    )
    payload = draft.to_dict()
    assert payload["clarification_questions"] == [
        {"question": "What does X mean?", "reason": "It matters.", "related_concepts": (), "blocking": True, "priority": "medium"}
    ]
    assert "id" not in payload["clarification_questions"][0]
