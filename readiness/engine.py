"""Deterministic, explainable suitability and readiness evaluators for M7.

This module evaluates the structure supplied by the user/idea assistant. It does
not infer scientific truth, estimate probabilities, or compile executable code.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re

from conceptual.model import (
    ConceptKind, DefinitionStatus, IdeaProject, PropertyType, QuestionStatus,
    ReferenceType,
)
from conceptual.validation import validate_idea_project
from readiness.models import (
    AssessmentFinding, BackendStatus, ClarificationItem, FitLevel, Paradigm,
    ParadigmAssessment, QuestionPriority, ReadinessReport, ReadinessStatus,
)


_BACKENDS = {
    Paradigm.DISCRETE_EVENT: BackendStatus.IMPLEMENTED,
    Paradigm.AGENT_BASED: BackendStatus.IMPLEMENTED,
    Paradigm.MATHEMATICAL: BackendStatus.ASSESSMENT_ONLY,
    Paradigm.DATA_DRIVEN: BackendStatus.ASSESSMENT_ONLY,
}

_TIME_WORDS = re.compile(r"\b(time|duration|delay|arrival|departure|interval|rate|frequency|schedule|period|timestamp)\b", re.I)
_EVENT_WORDS = re.compile(r"\b(arriv|depart|request|trigger|start|begin|complete|finish|release|interrupt|occur|event|process|service|flow|queue)\w*\b", re.I)
_BEHAVIOUR_WORDS = re.compile(r"\b(behavio|decision|choose|select|respond|interact|cooperat|compete|move|act|strategy|rule|policy)\w*\b", re.I)
_QUANT_WORDS = re.compile(r"(?:\b(increas|decreas|proportion|linear|quadratic|exponential|rate|ratio|equation|formula|function|derivative|integral|differential)\w*\b|[=<>+*/^]|\b[a-z]\s*=)", re.I)


def _finding(code: str, title: str, explanation: str, *ids: str) -> AssessmentFinding:
    return AssessmentFinding(code, title, explanation, tuple(dict.fromkeys(item for item in ids if item)))


def _dedupe(values):
    return tuple(dict.fromkeys(values))


def _joined_mechanism_text(mechanism) -> str:
    return " ".join((mechanism.name, mechanism.description, mechanism.trigger_description,
                     mechanism.effect_description, mechanism.operational_definition))


def _evaluate_des(revision) -> ParadigmAssessment:
    concepts = revision.concepts
    processes = [item for item in concepts if item.kind is ConceptKind.PROCESS]
    resources = [item for item in concepts if item.kind is ConceptKind.RESOURCE]
    timed_properties = [item for item in revision.properties if item.data_type is PropertyType.DATE_TIME or _TIME_WORDS.search(item.name + " " + item.definition)]
    numeric_properties = [item for item in revision.properties if item.data_type in {PropertyType.NUMBER, PropertyType.INTEGER}]
    event_mechanisms = [item for item in revision.mechanisms if _EVENT_WORDS.search(_joined_mechanism_text(item))]
    operational = [item for item in event_mechanisms if item.operational_definition.strip() and item.trigger_description.strip() and item.effect_description.strip()]
    findings = []
    limits = []
    missing = []

    if processes:
        findings.append(_finding("DES_PROCESS_CONCEPTS", "Process concepts identified", f"The model contains {len(processes)} process concept(s), which can represent stages or activities in an event-driven flow.", *(item.id for item in processes)))
    if resources:
        findings.append(_finding("DES_RESOURCE_CONCEPTS", "Resource concepts identified", f"The model contains {len(resources)} resource concept(s), which can represent capacity-constrained servers or shared resources.", *(item.id for item in resources)))
    if event_mechanisms:
        findings.append(_finding("DES_EVENT_MECHANISM", "Event-like mechanism identified", "At least one mechanism describes event, request, service, arrival, completion or process behaviour.", *(item.id for item in event_mechanisms)))
    if timed_properties:
        findings.append(_finding("DES_TIME_PROPERTIES", "Time-related properties identified", "Time, duration, schedule or timestamp properties are represented in the conceptual model.", *(item.id for item in timed_properties)))
    if numeric_properties:
        findings.append(_finding("DES_NUMERIC_PARAMETERS", "Numeric parameters identified", "Numeric properties can provide candidate durations, rates, capacities or quantities; their meaning and units still need confirmation.", *(item.id for item in numeric_properties)))

    if not processes:
        missing.append("Identify the discrete activities or process stages, if the theory includes them.")
    if not event_mechanisms:
        missing.append("Define the events or triggers that cause the system to change.")
    if resources and not numeric_properties:
        missing.append("Specify how resource capacity or availability is represented.")
    if event_mechanisms and not operational:
        missing.append("Specify the event mechanism's operational rule, including trigger, conditions and resulting state change.")
    if not timed_properties:
        missing.append("Clarify whether time, duration, event ordering or scheduling is important to the theory.")
    if any(not item.unit for item in numeric_properties):
        missing.append("Specify units or scales for numeric properties where meaningful.")

    if processes and resources and operational:
        fit = FitLevel.STRONG
    elif processes or resources or event_mechanisms:
        fit = FitLevel.POSSIBLE
    elif any(item.kind in {ConceptKind.ACTOR, ConceptKind.ABSTRACT} for item in concepts):
        fit = FitLevel.INSUFFICIENT_INFORMATION
    else:
        fit = FitLevel.POOR
    if event_mechanisms and not operational:
        limits.append(_finding("DES_RULE_NOT_OPERATIONAL", "Event rule is not operationalized", "The model names an event-like mechanism but does not yet define a rule precise enough to translate into an event scheduler.", *(item.id for item in event_mechanisms)))
    if not timed_properties:
        limits.append(_finding("DES_TIME_SEMANTICS_UNKNOWN", "Time semantics are unknown", "No explicit time-related property was identified. DES may still be possible, but its event timing or ordering basis is not yet established."))
    summary = {
        FitLevel.STRONG: "Strong conceptual alignment: processes, resources and an operational event mechanism are present.",
        FitLevel.POSSIBLE: "Possible alignment: the model contains process, resource or event signals, but one or more DES foundations remain incomplete.",
        FitLevel.INSUFFICIENT_INFORMATION: "The current model does not yet establish event-driven process semantics.",
        FitLevel.POOR: "The current conceptual elements provide little indication of an event-driven system.",
    }[fit]
    return ParadigmAssessment(Paradigm.DISCRETE_EVENT, fit, _BACKENDS[Paradigm.DISCRETE_EVENT], tuple(findings), tuple(limits), _dedupe(missing), summary)


def _evaluate_abm(revision) -> ParadigmAssessment:
    concepts = revision.concepts
    actors = [item for item in concepts if item.kind in {ConceptKind.ACTOR, ConceptKind.ENTITY}]
    actor_ids = {item.id for item in actors}
    actor_relationships = [item for item in revision.relationships if item.source_concept_id in actor_ids or item.target_concept_id in actor_ids]
    behaviour_mechanisms = [item for item in revision.mechanisms if _BEHAVIOUR_WORDS.search(_joined_mechanism_text(item))]
    operational = [item for item in behaviour_mechanisms if item.operational_definition.strip() and item.trigger_description.strip() and item.effect_description.strip()]
    actor_properties = [item for item in revision.properties if item.concept_id in actor_ids]
    findings = []
    limits = []
    missing = []

    if actors:
        findings.append(_finding("ABM_ACTOR_CONCEPTS", "Agent-like concepts identified", f"The model contains {len(actors)} actor/entity concept(s) that could potentially be represented as agents.", *(item.id for item in actors)))
    if actor_relationships:
        findings.append(_finding("ABM_AGENT_RELATIONSHIPS", "Interactions or memberships identified", "Relationships connect an actor/entity to another conceptual element and may define interaction structure.", *(item.id for item in actor_relationships)))
    if behaviour_mechanisms:
        findings.append(_finding("ABM_BEHAVIOUR_MECHANISM", "Behaviour-like mechanism identified", "At least one mechanism refers to action, interaction, decision or behavioural rules.", *(item.id for item in behaviour_mechanisms)))
    if actor_properties:
        findings.append(_finding("ABM_AGENT_ATTRIBUTES", "Agent properties identified", "Properties are attached to actor/entity concepts and may represent agent attributes or state.", *(item.id for item in actor_properties)))

    if not actors:
        missing.append("Identify the autonomous individuals, organizations or entities whose behaviour matters.")
    if actors and not actor_relationships:
        missing.append("Define how agents interact with one another or with their environment.")
    if not behaviour_mechanisms:
        missing.append("Define the decisions or behavioural rules that govern agent actions.")
    elif not operational:
        missing.append("Operationalize agent behaviour: specify the conditions, action and resulting state change.")
    if actors and not actor_properties:
        missing.append("Identify relevant agent attributes or internal states, where applicable.")

    if actors and actor_relationships and operational:
        fit = FitLevel.STRONG
    elif actors and (actor_relationships or behaviour_mechanisms or actor_properties):
        fit = FitLevel.POSSIBLE
    elif actors:
        fit = FitLevel.INSUFFICIENT_INFORMATION
    elif revision.mechanisms or revision.relationships:
        fit = FitLevel.INSUFFICIENT_INFORMATION
    else:
        fit = FitLevel.POOR
    if behaviour_mechanisms and not operational:
        limits.append(_finding("ABM_BEHAVIOUR_UNDERSPECIFIED", "Agent behaviour is not operationalized", "Agent-based execution requires explicit per-agent behaviour or decision rules; the current mechanism remains descriptive.", *(item.id for item in behaviour_mechanisms)))
    if len(actors) == 1:
        limits.append(_finding("ABM_SINGLE_ACTOR_TYPE", "Only one agent/entity concept identified", "This may be valid, but the model should clarify whether multiple instances of this type exist and how they differ."))
    summary = {
        FitLevel.STRONG: "Strong conceptual alignment: agent-like entities, interaction structure and operationalized behaviour are present.",
        FitLevel.POSSIBLE: "Possible alignment: agents or interactions are represented, but behaviour/state details need refinement.",
        FitLevel.INSUFFICIENT_INFORMATION: "The model contains some agent-related structure, but autonomous behaviour is not established.",
        FitLevel.POOR: "The current conceptual elements provide little indication of autonomous interacting agents.",
    }[fit]
    return ParadigmAssessment(Paradigm.AGENT_BASED, fit, _BACKENDS[Paradigm.AGENT_BASED], tuple(findings), tuple(limits), _dedupe(missing), summary)


def _evaluate_mathematical(revision) -> ParadigmAssessment:
    numeric_properties = [item for item in revision.properties if item.data_type in {PropertyType.NUMBER, PropertyType.INTEGER}]
    variables = [item for item in revision.concepts if item.kind is ConceptKind.VARIABLE]
    quantitative_relationships = [item for item in revision.relationships if _QUANT_WORDS.search(item.label + " " + item.description)]
    quantitative_mechanisms = [item for item in revision.mechanisms if _QUANT_WORDS.search(_joined_mechanism_text(item))]
    operational_quantitative = [item for item in quantitative_mechanisms if item.operational_definition.strip()]
    findings = []
    limits = []
    missing = []
    if numeric_properties:
        findings.append(_finding("MATH_NUMERIC_PROPERTIES", "Numeric properties identified", f"The conceptual model contains {len(numeric_properties)} numeric/integer property value(s) that may become model variables or parameters.", *(item.id for item in numeric_properties)))
    if variables:
        findings.append(_finding("MATH_VARIABLE_CONCEPTS", "Variable concepts identified", "Explicit variable concepts are present.", *(item.id for item in variables)))
    if quantitative_relationships or quantitative_mechanisms:
        items = quantitative_relationships + quantitative_mechanisms
        findings.append(_finding("MATH_QUANTITATIVE_RELATIONS", "Quantitative or functional relation signals identified", "A relationship or mechanism contains formula/equation/functional language or mathematical operators.", *(item.id for item in items)))

    if len(numeric_properties) + len(variables) < 2:
        missing.append("Identify at least two relevant measurable or mathematical variables, if a quantitative model is intended.")
    if not quantitative_relationships and not quantitative_mechanisms:
        missing.append("Specify the quantitative relationship, equation, function or update rule connecting the variables.")
    if any(not item.unit for item in numeric_properties):
        missing.append("Define units, scales and parameter meanings for numeric variables.")
    if quantitative_mechanisms and not operational_quantitative:
        missing.append("Provide an explicit mathematical or computational rule for the quantitative mechanism.")

    if len(numeric_properties) >= 2 and (quantitative_relationships or operational_quantitative):
        fit = FitLevel.STRONG
    elif len(numeric_properties) + len(variables) >= 2:
        fit = FitLevel.POSSIBLE
    elif quantitative_relationships or quantitative_mechanisms:
        fit = FitLevel.POSSIBLE
    elif revision.concepts:
        fit = FitLevel.INSUFFICIENT_INFORMATION
    else:
        fit = FitLevel.POOR
    if numeric_properties and not (quantitative_relationships or quantitative_mechanisms):
        limits.append(_finding("MATH_NO_GOVERNING_RELATION", "No governing quantitative relationship found", "Numeric properties alone do not define a mathematical model; equations, functions or update rules are still needed.", *(item.id for item in numeric_properties)))
    summary = {
        FitLevel.STRONG: "Strong conceptual alignment: measurable variables and quantitative relationships are represented.",
        FitLevel.POSSIBLE: "Possible alignment: variables or quantitative signals exist, but the governing mathematics needs specification.",
        FitLevel.INSUFFICIENT_INFORMATION: "The current model is not yet expressed in sufficiently quantitative terms.",
        FitLevel.POOR: "The current conceptual elements provide little indication of a quantitative model.",
    }[fit]
    return ParadigmAssessment(Paradigm.MATHEMATICAL, fit, _BACKENDS[Paradigm.MATHEMATICAL], tuple(findings), tuple(limits), _dedupe(missing), summary)


def _evaluate_data_driven(revision) -> ParadigmAssessment:
    numeric_properties = [item for item in revision.properties if item.data_type in {PropertyType.NUMBER, PropertyType.INTEGER}]
    temporal_properties = [item for item in revision.properties if item.data_type is PropertyType.DATE_TIME or _TIME_WORDS.search(item.name + " " + item.definition)]
    datasets = [item for item in revision.evidence_references if item.reference_type is ReferenceType.DATASET]
    other_refs = list(revision.evidence_references)
    findings = []
    limits = []
    missing = []
    if datasets:
        findings.append(_finding("DATASET_REFERENCE_PRESENT", "Dataset reference recorded", "At least one evidence reference is typed as a dataset. A bibliographic reference does not by itself prove that the underlying file is accessible or usable.", *(item.id for item in datasets)))
    if numeric_properties:
        findings.append(_finding("DATA_NUMERIC_FIELDS", "Numeric data fields may be available", "Numeric/integer properties are present and may be measurable from observational data.", *(item.id for item in numeric_properties)))
    if temporal_properties:
        findings.append(_finding("DATA_TEMPORAL_FIELDS", "Temporal fields identified", "Time or date-time properties can support temporal observations if the source data actually contains them.", *(item.id for item in temporal_properties)))
    if other_refs and not datasets:
        limits.append(_finding("DATA_NON_DATASET_REFERENCES", "References are not typed as datasets", "The project includes evidence references, but none is identified as a dataset."))

    if not datasets:
        missing.append("Identify an observational dataset or explain how measurements will be collected; a source citation alone is not the data itself.")
    if not numeric_properties:
        missing.append("Identify measurable fields and their data types in the source data.")
    if len(numeric_properties) < 2:
        missing.append("Clarify the input variables and target/outcome variables available in the observations.")
    if not temporal_properties:
        missing.append("Clarify whether observations have timestamps, time intervals or another meaningful ordering.")
    if any(not item.unit for item in numeric_properties):
        missing.append("Document units, scales, missing-value conventions and measurement definitions.")

    if datasets and len(numeric_properties) >= 2 and temporal_properties:
        fit = FitLevel.STRONG
    elif datasets or len(numeric_properties) >= 2:
        fit = FitLevel.POSSIBLE
    elif revision.concepts or revision.hypotheses:
        fit = FitLevel.INSUFFICIENT_INFORMATION
    else:
        fit = FitLevel.POOR
    if datasets:
        limits.append(_finding("DATA_FILE_NOT_VERIFIED", "Dataset accessibility is not verified", "M7 sees dataset metadata in the conceptual model, but it has not opened, profiled or validated the referenced data file.", *(item.id for item in datasets)))
    summary = {
        FitLevel.STRONG: "Strong conceptual alignment: a dataset is referenced and measurable/temporal fields are represented; actual data quality remains unverified.",
        FitLevel.POSSIBLE: "Possible alignment: a dataset or measurable variables are identified, but coverage and target fields need clarification.",
        FitLevel.INSUFFICIENT_INFORMATION: "The model does not yet provide enough evidence of an observational data basis.",
        FitLevel.POOR: "The current conceptual elements provide little indication of a data-driven modelling task.",
    }[fit]
    return ParadigmAssessment(Paradigm.DATA_DRIVEN, fit, _BACKENDS[Paradigm.DATA_DRIVEN], tuple(findings), tuple(limits), _dedupe(missing), summary)


def _clarifications(revision, paradigm_assessments: tuple[ParadigmAssessment, ...], selected: Paradigm | None) -> tuple[ClarificationItem, ...]:
    questions: list[ClarificationItem] = []
    seen: set[str] = set()

    def add(identifier: str, question: str, reason: str, priority: QuestionPriority, ids=(), blocking=True):
        key = question.casefold().strip()
        if key in seen:
            return
        seen.add(key)
        questions.append(ClarificationItem(identifier, question, reason, priority, tuple(ids), blocking))

    for item in revision.open_questions:
        if item.status is QuestionStatus.OPEN:
            add(item.id, item.question, "This question is already recorded in the conceptual revision.",
                QuestionPriority.HIGH if item.blocking else QuestionPriority.MEDIUM,
                item.related_element_ids, item.blocking)

    for mechanism in revision.mechanisms:
        missing_parts = []
        if not mechanism.trigger_description.strip():
            missing_parts.append("trigger or condition")
        if not mechanism.effect_description.strip():
            missing_parts.append("resulting effect")
        if not mechanism.operational_definition.strip():
            missing_parts.append("operational rule")
        if missing_parts:
            add(
                f"m7-mechanism-{mechanism.id}",
                f"How does '{mechanism.name}' work in operational terms? Please define its {', '.join(missing_parts)}.",
                "A mechanism needs a sufficiently precise rule before a paradigm-specific implementation can be planned.",
                QuestionPriority.HIGH,
                (mechanism.id,),
            )

    for concept in revision.concepts:
        if not concept.definition.strip() or concept.status is not DefinitionStatus.DEFINED:
            add(
                f"m7-concept-{concept.id}",
                f"Can you clarify what '{concept.name}' means in this theory and what observable or conceptual boundaries define it?",
                "The concept is proposed or partially defined; a stable meaning is needed before operationalization.",
                QuestionPriority.MEDIUM,
                (concept.id,),
            )

    for prop in revision.properties:
        if prop.data_type is PropertyType.UNKNOWN:
            add(
                f"m7-property-type-{prop.id}",
                f"What type of value does '{prop.name}' take, and how is it represented or measured?",
                "The property data type is unknown, which prevents a reliable choice of numerical or categorical representation.",
                QuestionPriority.HIGH,
                (prop.id, prop.concept_id),
            )
        elif prop.data_type in {PropertyType.NUMBER, PropertyType.INTEGER} and not prop.unit:
            add(
                f"m7-property-unit-{prop.id}",
                f"What unit or scale should be used for '{prop.name}'?",
                "A numeric value without a unit or scale can be ambiguous when specifying model parameters.",
                QuestionPriority.MEDIUM,
                (prop.id, prop.concept_id),
            )

    candidates = (selected,) if selected is not None else tuple(item.paradigm for item in paradigm_assessments if item.fit in {FitLevel.STRONG, FitLevel.POSSIBLE})
    for paradigm in candidates:
        assessment = next(item for item in paradigm_assessments if item.paradigm is paradigm)
        if paradigm is Paradigm.DISCRETE_EVENT and assessment.fit in {FitLevel.STRONG, FitLevel.POSSIBLE}:
            if not any(item.kind is ConceptKind.PROCESS for item in revision.concepts):
                add("m7-des-process", "Which discrete activities or stages should occur in the system?", "A DES representation needs identifiable processes or event-driven activities.", QuestionPriority.MEDIUM)
        elif paradigm is Paradigm.AGENT_BASED and assessment.fit in {FitLevel.STRONG, FitLevel.POSSIBLE}:
            if not revision.mechanisms:
                add("m7-abm-rules", "What decisions or behavioural rules determine how agents act and interact?", "Agent-based models require explicit behaviour or decision mechanisms.", QuestionPriority.HIGH)
        elif paradigm is Paradigm.MATHEMATICAL and assessment.fit in {FitLevel.STRONG, FitLevel.POSSIBLE}:
            if not any(item.code == "MATH_QUANTITATIVE_RELATIONS" for item in assessment.supporting_findings):
                add("m7-math-equations", "What equations, functions or update rules connect the relevant variables?", "A set of variables alone does not specify a mathematical model.", QuestionPriority.HIGH)
        elif paradigm is Paradigm.DATA_DRIVEN and assessment.fit in {FitLevel.STRONG, FitLevel.POSSIBLE}:
            if not any(item.reference_type is ReferenceType.DATASET for item in revision.evidence_references):
                add("m7-data-source", "Which observational dataset will be used, and how can it be accessed?", "A data-driven model needs observations, not only a conceptual description.", QuestionPriority.HIGH)

    return tuple(questions)


def assess_readiness(project: IdeaProject, *, selected_paradigm: Paradigm | str | None = None) -> ReadinessReport:
    """Assess conceptual readiness and suitability for four simulation paradigms.

    The input project is never modified. If a paradigm is selected, the report
    separately records whether the model is sufficiently specified to begin
    implementation planning for that paradigm.
    """
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    if isinstance(selected_paradigm, str):
        try:
            selected_paradigm = Paradigm(selected_paradigm)
        except ValueError as error:
            raise ValueError(f"Unsupported paradigm: {selected_paradigm!r}") from error
    if selected_paradigm is not None and not isinstance(selected_paradigm, Paradigm):
        raise TypeError("selected_paradigm must be a Paradigm, string value or None")

    revision = project.current_revision
    validation = validate_idea_project(project)
    assessments = (
        _evaluate_des(revision),
        _evaluate_abm(revision),
        _evaluate_mathematical(revision),
        _evaluate_data_driven(revision),
    )
    best_fit = max((item.fit for item in assessments), key=lambda value: {
        FitLevel.STRONG: 4, FitLevel.POSSIBLE: 3,
        FitLevel.INSUFFICIENT_INFORMATION: 2, FitLevel.POOR: 1,
    }[value])
    recommended = tuple(item.paradigm for item in assessments if item.fit is best_fit and best_fit in {FitLevel.STRONG, FitLevel.POSSIBLE})
    clarification_items = _clarifications(revision, assessments, selected_paradigm)

    if validation.errors:
        status = ReadinessStatus.NOT_ASSESSABLE
        explanation = "Structural validation found errors. Resolve them before relying on paradigm suitability findings."
    elif not revision.concepts:
        status = ReadinessStatus.NEEDS_CLARIFICATION
        explanation = "The current revision contains no extracted concepts, so there is not yet a meaningful basis for evaluating simulation readiness."
    else:
        has_structure = bool(revision.mechanisms or revision.relationships)
        has_blocking_questions = any(item.status is QuestionStatus.OPEN and item.blocking for item in revision.open_questions)
        has_unoperational_mechanism = any(not item.operational_definition.strip() for item in revision.mechanisms)
        if not has_structure or has_blocking_questions or has_unoperational_mechanism:
            status = ReadinessStatus.NEEDS_CLARIFICATION
            reasons = []
            if not has_structure:
                reasons.append("no mechanism or relationship structure has been defined")
            if has_blocking_questions:
                reasons.append("blocking questions remain open")
            if has_unoperational_mechanism:
                reasons.append("one or more mechanisms lack an operational definition")
            explanation = "Further clarification is needed because " + ", ".join(reasons) + "."
        else:
            status = ReadinessStatus.READY_FOR_EVALUATION
            explanation = "The conceptual structure is sufficiently developed to compare simulation paradigms. This does not mean the theory is validated or ready to execute."

    if selected_paradigm is not None:
        chosen = next(item for item in assessments if item.paradigm is selected_paradigm)
        no_blockers = not any(item.blocking for item in clarification_items)
        mechanisms_operational = bool(revision.mechanisms) and all(
            item.operational_definition.strip() and item.trigger_description.strip() and item.effect_description.strip()
            for item in revision.mechanisms
        )
        implementation_specifics = not chosen.missing_requirements
        if (
            validation.is_valid and chosen.fit is FitLevel.STRONG
            and no_blockers and mechanisms_operational and implementation_specifics
            and chosen.backend_status is BackendStatus.IMPLEMENTED
        ):
            status = ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING
            explanation = (
                f"The selected {selected_paradigm.value} paradigm has a strong conceptual fit, required rules are operationalized, "
                "and an execution backend is implemented. The next step is paradigm-specific specification and verification; "
                "this assessment does not itself generate or execute a model."
            )
        elif validation.errors:
            status = ReadinessStatus.NOT_ASSESSABLE
        elif status is not ReadinessStatus.NEEDS_CLARIFICATION and (
            chosen.fit is FitLevel.INSUFFICIENT_INFORMATION or chosen.fit is FitLevel.POOR
        ):
            status = ReadinessStatus.NEEDS_CLARIFICATION
            explanation = f"The selected {selected_paradigm.value} paradigm is not adequately supported by the current conceptual structure. Review its missing requirements before proceeding."

    errors = tuple(f"{item.path} [{item.code}]: {item.message}" for item in validation.errors)
    warnings = tuple(f"{item.path} [{item.code}]: {item.message}" for item in validation.warnings)
    return ReadinessReport(
        schema_version=1,
        project_id=project.id,
        project_title=project.title,
        revision_id=revision.id,
        revision_version=revision.version,
        assessed_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        validation_errors=errors,
        validation_warnings=warnings,
        paradigm_assessments=assessments,
        recommended_paradigms=recommended,
        selected_paradigm=selected_paradigm,
        clarification_items=clarification_items,
        explanation=explanation,
    )
