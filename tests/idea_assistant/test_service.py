from conceptual import dumps_idea_project, loads_idea_project, validate_idea_project
from conceptual.model import ConceptOrigin, ProvenanceKind
from idea_assistant.models import RetrievedContext
from idea_assistant.service import IdeaAssistantService
from idea_assistant.session import dumps_session, loads_session
from knowledge.models import KnowledgeBase, KnowledgeDocument
from conceptual.model import EvidenceReference, ReferenceType
from tests.idea_assistant.helpers import draft_copy


class StubInterpreter:
    def __init__(self):
        self.refine_calls = []
        self.initial_context = None

    def interpret(self, request, *, knowledge_context=()):
        self.initial_context = tuple(knowledge_context)
        return draft_copy()

    def refine(self, request, current_draft, clarification_history, *, knowledge_context=()):
        self.refine_calls.append((request, current_draft, list(clarification_history), tuple(knowledge_context)))
        revised = draft_copy()
        revised["working_statement"] = "Community members coordinate access to a shared water resource."
        revised["concepts"][1]["name"] = "Water resource"
        revised["concepts"][1]["definition"] = "Water made available for shared use."
        revised["concepts"][1]["source"] = "explicit"
        revised["concepts"][1]["excerpt"] = "water"
        revised["properties"][0]["concept"] = "Water resource"
        revised["relationships"][0]["target_concept"] = "Water resource"
        revised["mechanisms"][0]["inputs"][1] = "Water resource"
        revised["mechanisms"][0]["outputs"][0] = "Water resource"
        revised["clarification_questions"] = []
        revised["uncertainties"] = ["Allocation rules remain unspecified."]
        return revised


def sample_knowledge_base():
    document = KnowledgeDocument(
        id="doc-commons", title="Commons governance summary",
        content="Community institutions and shared resource governance. Cooperation and rules.",
        reference=EvidenceReference(
            id="ref-commons", title="Governing the Commons", reference_type=ReferenceType.BOOK,
            uri="https://example.org/commons", publisher="Example Press", published_year=1990,
        ),
        domains=("commons",), keywords=("community", "resource", "cooperation"),
        concept_labels=("shared resource",),
    )
    return KnowledgeBase("kb-test", "Test knowledge", (document,))


def answer_once(questions):
    return {questions[0].id: "The resource is water."}


def test_clarification_workflow_builds_valid_append_only_project_and_session():
    interpreter = StubInterpreter()
    service = IdeaAssistantService(interpreter, knowledge_base=sample_knowledge_base())
    result = service.build(
        "The community members access a shared resource.",
        clarification_handler=answer_once,
        max_clarification_rounds=2,
    )

    assert len(interpreter.refine_calls) == 1
    assert result.project.original_statement == "The community members access a shared resource."
    assert len(result.project.revisions) == 2
    assert result.project.revisions[0].working_statement == result.project.original_statement
    assert result.project.current_revision.working_statement.endswith("shared water resource.")
    assert len(result.session.clarification_history) == 1
    assert result.session.clarification_history[0].answer == "The resource is water."
    assert result.session.retrieved_context
    assert result.validation_report.is_valid
    assert validate_idea_project(result.project).is_valid

    provenance = {item.element_id: item for item in result.project.current_revision.provenance_records}
    concepts = {item.name: item for item in result.project.current_revision.concepts}
    assert provenance[concepts["Community member"].id].kind is ProvenanceKind.USER_EXPLICIT
    assert provenance[concepts["Water resource"].id].kind is ProvenanceKind.USER_EXPLICIT
    assert concepts["Water resource"].origin is ConceptOrigin.AI_PROPOSED

    loaded_project = loads_idea_project(dumps_idea_project(result.project))
    assert loaded_project == result.project
    loaded_session = loads_session(dumps_session(result.session))
    assert loaded_session == result.session


def test_no_handler_leaves_clarification_questions_open():
    service = IdeaAssistantService(StubInterpreter())
    result = service.build("A community shares something.")
    assert len(result.project.current_revision.open_questions) == 1
    assert not result.session.clarification_history
    assert result.validation_report.is_valid


def test_false_explicit_attribution_is_downgraded_to_ai_inference():
    raw = draft_copy()
    raw["concepts"][0]["excerpt"] = "This phrase is not in the user request."
    class ExplicitInterpreter(StubInterpreter):
        def interpret(self, request, *, knowledge_context=()):
            return raw
    result = IdeaAssistantService(ExplicitInterpreter()).build("The community accesses water.")
    concept = result.project.current_revision.concepts[0]
    record = next(item for item in result.project.current_revision.provenance_records if item.element_id == concept.id)
    assert record.kind is ProvenanceKind.AI_INFERRED
    assert concept.origin is ConceptOrigin.AI_PROPOSED
    assert "downgraded" in record.note


def test_retrieval_context_is_passed_to_interpreter_as_lead_not_evidence():
    interpreter = StubInterpreter()
    service = IdeaAssistantService(interpreter, knowledge_base=sample_knowledge_base())
    result = service.build("community resource cooperation")
    assert interpreter.initial_context
    assert "lexical_relevance_score_not_confidence" in interpreter.initial_context[0]
    assert result.session.retrieved_context[0].title == "Governing the Commons"


def test_unanswered_question_is_retained_after_partial_refinement():
    class TwoQuestionInterpreter(StubInterpreter):
        def interpret(self, request, *, knowledge_context=()):
            raw = draft_copy()
            raw["clarification_questions"].append({
                "question": "Who decides the allocation?", "reason": "Governance is not specified.",
                "related_concepts": ["Community member"], "blocking": True, "priority": "medium",
            })
            return raw

    def answer_first(questions):
        return {questions[0].id: "The resource is water."}

    result = IdeaAssistantService(TwoQuestionInterpreter()).build(
        "The community members access a shared resource.",
        clarification_handler=answer_first,
        max_clarification_rounds=1,
    )
    open_texts = {item.question for item in result.project.current_revision.open_questions}
    assert "Who decides the allocation?" in open_texts
    assert len(result.session.clarification_history) == 1
