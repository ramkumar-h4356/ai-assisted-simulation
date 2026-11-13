"""Orchestrate M6 interpretation, clarification, retrieval context and M4 integration."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from conceptual.model import (
    Assumption, Concept, ConceptKind, ConceptOrigin, Constraint, DefinitionStatus,
    Hypothesis, IdeaProject, Mechanism, OpenQuestion, Property, PropertyType,
    ProvenanceKind, ProvenanceRecord, QuestionStatus, Relationship,
)
from conceptual.revision import create_idea_project, revise_idea_project
from conceptual.validation import ValidationReport, validate_idea_project
from idea_assistant.interpreter import IdeaInterpreter
from idea_assistant.models import (
    ClarificationExchange, ClarificationQuestion, IdeaAssistantSession, IdeaDraft,
    RetrievedContext, new_session_id, utc_now,
)
from idea_assistant.schema import parse_idea_draft
from knowledge.models import KnowledgeBase
from knowledge.retrieval import KnowledgeRetriever


ClarificationHandler = Callable[[tuple[ClarificationQuestion, ...]], Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class IdeaAssistantResult:
    project: IdeaProject
    draft: IdeaDraft
    session: IdeaAssistantSession
    validation_report: ValidationReport


class IdeaAssistantService:
    """Build a traceable conceptual draft without selecting or running a simulator."""

    def __init__(self, interpreter: IdeaInterpreter, *, knowledge_base: KnowledgeBase | None = None) -> None:
        if not hasattr(interpreter, "interpret") or not hasattr(interpreter, "refine"):
            raise TypeError("interpreter must implement interpret() and refine()")
        if knowledge_base is not None and not isinstance(knowledge_base, KnowledgeBase):
            raise TypeError("knowledge_base must be a KnowledgeBase or None")
        self.interpreter = interpreter
        self.knowledge_base = knowledge_base
        self.retriever = KnowledgeRetriever(knowledge_base) if knowledge_base is not None else None

    def _retrieve_context(self, request: str) -> tuple[RetrievedContext, ...]:
        if self.retriever is None or not self.knowledge_base or not self.knowledge_base.documents:
            return ()
        try:
            hits = self.retriever.search(request, limit=4)
        except ValueError:
            return ()
        return tuple(
            RetrievedContext(
                document_id=hit.document.id,
                title=hit.document.reference.title,
                summary=hit.document.content[:1200],
                uri=hit.document.reference.uri,
                relevance_score=hit.score,
                matched_terms=hit.matched_terms,
            )
            for hit in hits
        )

    @staticmethod
    def _context_payload(context: Sequence[RetrievedContext]) -> list[dict[str, Any]]:
        return [
            {
                "document_id": item.document_id,
                "title": item.title,
                "summary": item.summary,
                "uri": item.uri,
                "lexical_relevance_score_not_confidence": item.relevance_score,
                "matched_terms": list(item.matched_terms),
            }
            for item in context
        ]

    def build(
        self,
        request: str,
        *,
        clarification_handler: ClarificationHandler | None = None,
        max_clarification_rounds: int = 3,
        max_questions_per_round: int = 3,
    ) -> IdeaAssistantResult:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("The idea description must be a non-empty string")
        if isinstance(max_clarification_rounds, bool) or not isinstance(max_clarification_rounds, int) or max_clarification_rounds < 0:
            raise ValueError("max_clarification_rounds must be a non-negative integer")
        if isinstance(max_questions_per_round, bool) or not isinstance(max_questions_per_round, int) or max_questions_per_round < 1:
            raise ValueError("max_questions_per_round must be a positive integer")

        initial_request = request.strip()
        retrieved_context = self._retrieve_context(initial_request)
        context_payload = self._context_payload(retrieved_context)
        raw = self.interpreter.interpret(initial_request, knowledge_context=context_payload)
        draft = parse_idea_draft(raw)
        exchanges: list[ClarificationExchange] = []

        for round_number in range(1, max_clarification_rounds + 1):
            if not draft.clarification_questions or clarification_handler is None:
                break
            questions = draft.clarification_questions[:max_questions_per_round]
            answers = clarification_handler(questions)
            if not isinstance(answers, Mapping):
                raise TypeError("clarification_handler must return a mapping of question IDs to answers")
            question_lookup = {item.id: item for item in questions}
            accepted_answers: dict[str, str] = {}
            for question_id, answer in answers.items():
                if question_id not in question_lookup:
                    raise ValueError(f"Clarification handler returned unknown question ID {question_id!r}")
                if not isinstance(answer, str):
                    raise TypeError("Clarification answers must be strings")
                answer = answer.strip()
                if answer:
                    accepted_answers[question_id] = answer
                    question = question_lookup[question_id]
                    exchanges.append(ClarificationExchange(
                        question_id=question_id, question=question.question,
                        answer=answer, round_number=round_number,
                    ))
            if not accepted_answers:
                break
            history_payload = [
                {
                    "question_id": item.question_id,
                    "question": item.question,
                    "answer": item.answer,
                    "round_number": item.round_number,
                }
                for item in exchanges
            ]
            unanswered_questions = tuple(
                question for question in draft.clarification_questions
                if question.id not in accepted_answers
            )
            raw = self.interpreter.refine(
                initial_request, draft.to_dict(), history_payload,
                knowledge_context=context_payload,
            )
            refined_draft = parse_idea_draft(raw)
            retained = list(refined_draft.clarification_questions)
            retained_text = {item.question.casefold().strip() for item in retained}
            for index, question in enumerate(unanswered_questions, start=1):
                if question.question.casefold().strip() not in retained_text:
                    retained.append(replace(
                        question,
                        id=f"carry-forward-{round_number}-{index}",
                    ))
                    retained_text.add(question.question.casefold().strip())
            draft = replace(refined_draft, clarification_questions=tuple(retained))

        project = apply_idea_draft(initial_request, draft, tuple(exchanges))
        report = validate_idea_project(project)
        session = IdeaAssistantSession(
            id=new_session_id(), project_id=project.id, created_at=utc_now(),
            initial_request=initial_request, clarification_history=tuple(exchanges),
            retrieved_context=retrieved_context, final_summary=draft.summary,
            uncertainties=draft.uncertainties,
        )
        return IdeaAssistantResult(project, draft, session, report)


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return value[:48] or "item"


def _allocate(prefix: str, label: str, used: set[str]) -> str:
    base = f"{prefix}-{_slug(label)}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _provenance(
    element_id: str,
    source: str,
    excerpt: str,
    initial_request: str,
    exchanges: tuple[ClarificationExchange, ...],
    used_ids: set[str],
) -> ProvenanceRecord:
    matched_label = ""
    exact_match = False
    if excerpt:
        if excerpt in initial_request:
            exact_match = True
            matched_label = "initial user request"
        else:
            for exchange in exchanges:
                if excerpt in exchange.answer:
                    exact_match = True
                    matched_label = f"clarification answer {exchange.round_number}"
                    break
    if source == "suggested":
        exact_match = False
        matched_label = "AI suggestion"
        kind = ProvenanceKind.AI_SUGGESTED
        note = "Optional AI-generated suggestion; not stated by the user."
    elif source == "explicit" and exact_match:
        kind = ProvenanceKind.USER_EXPLICIT
        note = "The supplied excerpt was matched verbatim against user-provided text."
    else:
        kind = ProvenanceKind.AI_INFERRED
        if source == "explicit" and not exact_match:
            note = "AI labelled this explicit, but its excerpt did not match user text; downgraded to an inference."
        else:
            note = "AI interpretation or inference; requires user review."
        matched_label = matched_label or "AI interpretation"
    if not matched_label:
        matched_label = "AI suggestion" if kind is ProvenanceKind.AI_SUGGESTED else "AI interpretation"
    identifier = _allocate("provenance", element_id, used_ids)
    return ProvenanceRecord(
        id=identifier, element_id=element_id, kind=kind,
        source_label=matched_label, source_excerpt=excerpt if exact_match else "", note=note,
    )


def apply_idea_draft(
    original_request: str,
    draft: IdeaDraft,
    clarification_history: tuple[ClarificationExchange, ...] = (),
) -> IdeaProject:
    """Translate a validated AI draft into one append-only M4 revision."""
    project = create_idea_project(draft.title, original_request)
    used_ids: set[str] = set()
    concept_ids: dict[str, str] = {}
    concepts: list[Concept] = []
    properties: list[Property] = []
    relationships: list[Relationship] = []
    mechanisms: list[Mechanism] = []
    hypotheses: list[Hypothesis] = []
    assumptions: list[Assumption] = []
    constraints: list[Constraint] = []
    questions: list[OpenQuestion] = []
    provenance: list[ProvenanceRecord] = []

    def add_provenance(element_id: str, item: dict[str, Any]) -> ProvenanceRecord:
        record = _provenance(
            element_id, item.get("source", "inferred"), item.get("excerpt", ""),
            original_request, clarification_history, used_ids,
        )
        provenance.append(record)
        return record

    for item in draft.concepts:
        element_id = _allocate("concept", item["name"], used_ids)
        source_record = add_provenance(element_id, item)
        concept_ids[item["name"].casefold()] = element_id
        concepts.append(Concept(
            id=element_id, name=item["name"], kind=ConceptKind(item["kind"]),
            origin=ConceptOrigin.AI_PROPOSED,
            definition=item["definition"], status=DefinitionStatus(item["status"]),
            source_note=("AI-structured concept. " + source_record.note),
        ))

    for item in draft.properties:
        element_id = _allocate("property", item["name"], used_ids)
        properties.append(Property(
            id=element_id, concept_id=concept_ids[item["concept"].casefold()],
            name=item["name"], data_type=PropertyType(item["data_type"]), unit=item["unit"],
            definition=item["definition"], status=DefinitionStatus(item["status"]),
        ))
        add_provenance(element_id, item)

    for item in draft.relationships:
        label = f"{item['source_concept']}-{item['label']}-{item['target_concept']}"
        element_id = _allocate("relationship", label, used_ids)
        relationships.append(Relationship(
            id=element_id,
            source_concept_id=concept_ids[item["source_concept"].casefold()],
            target_concept_id=concept_ids[item["target_concept"].casefold()],
            label=item["label"], description=item["description"], directed=item["directed"],
            status=DefinitionStatus(item["status"]),
        ))
        add_provenance(element_id, item)

    for item in draft.mechanisms:
        element_id = _allocate("mechanism", item["name"], used_ids)
        mechanisms.append(Mechanism(
            id=element_id, name=item["name"], description=item["description"],
            input_concept_ids=tuple(concept_ids[name.casefold()] for name in item["inputs"]),
            output_concept_ids=tuple(concept_ids[name.casefold()] for name in item["outputs"]),
            trigger_description=item["trigger"], effect_description=item["effect"],
            operational_definition=item["operational_definition"], status=DefinitionStatus(item["status"]),
        ))
        add_provenance(element_id, item)

    for group_name, cls, target in (
        ("hypotheses", Hypothesis, hypotheses),
        ("assumptions", Assumption, assumptions),
        ("constraints", Constraint, constraints),
    ):
        for item in getattr(draft, group_name):
            element_id = _allocate(group_name[:-1], item["statement"], used_ids)
            if cls is Hypothesis:
                obj = Hypothesis(id=element_id, statement=item["statement"], scope=item["scope"])
            else:
                obj = cls(
                    id=element_id, statement=item["statement"], scope=item["scope"],
                    rationale=item["rationale"],
                )
            target.append(obj)
            add_provenance(element_id, item)

    for item in draft.clarification_questions:
        element_id = _allocate("question", item.question, used_ids)
        related_ids = tuple(concept_ids[name.casefold()] for name in item.related_concepts)
        questions.append(OpenQuestion(
            id=element_id, question=item.question, related_element_ids=related_ids,
            blocking=item.blocking, status=QuestionStatus.OPEN,
        ))
        provenance.append(ProvenanceRecord(
            id=_allocate("provenance", element_id, used_ids), element_id=element_id,
            kind=ProvenanceKind.AI_INFERRED, source_label="AI clarification analysis",
            note=f"Priority {item.priority}: {item.reason}".strip(),
        ))

    updated = revise_idea_project(
        project,
        change_summary=(
            "Created an AI-assisted conceptual interpretation"
            + (f" after {len(clarification_history)} clarification answer(s)." if clarification_history else ".")
        ),
        working_statement=draft.working_statement,
        concepts=tuple(concepts), properties=tuple(properties), relationships=tuple(relationships),
        mechanisms=tuple(mechanisms), hypotheses=tuple(hypotheses), assumptions=tuple(assumptions),
        constraints=tuple(constraints), open_questions=tuple(questions),
        provenance_records=tuple(provenance),
    )
    return updated
