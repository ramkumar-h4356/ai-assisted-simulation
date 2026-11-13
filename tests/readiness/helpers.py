from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus, EvidenceReference,
    IdeaProject, Mechanism, Property, PropertyType, ReferenceType, Relationship,
    create_idea_project, revise_idea_project,
)


def make_project(*, concepts=None, properties=(), relationships=(), mechanisms=(), evidence_references=(), open_questions=(), assumptions=(), constraints=()):
    project = create_idea_project(
        "Assessment fixture",
        "The original concept is retained exactly.",
        project_id="idea-assessment",
        revision_id="revision-1",
        created_at="2026-11-13T10:00:00+00:00",
    )
    return revise_idea_project(
        project,
        change_summary="Create an assessment fixture.",
        revision_id="revision-2",
        created_at="2026-11-13T10:01:00+00:00",
        concepts=tuple(concepts or ()),
        properties=tuple(properties),
        relationships=tuple(relationships),
        mechanisms=tuple(mechanisms),
        evidence_references=tuple(evidence_references),
        open_questions=tuple(open_questions),
        assumptions=tuple(assumptions),
        constraints=tuple(constraints),
    )


def des_project():
    concepts = (
        Concept("queue", "Queue", ConceptKind.PROCESS, ConceptOrigin.USER_DEFINED, "A set of jobs waiting for service.", DefinitionStatus.DEFINED),
        Concept("machine", "Machine", ConceptKind.RESOURCE, ConceptOrigin.USER_DEFINED, "A server that processes jobs.", DefinitionStatus.DEFINED),
    )
    properties = (Property("duration", "machine", "Service duration", PropertyType.NUMBER, "minutes", "Time needed to process one job.", DefinitionStatus.DEFINED),)
    relationships = (Relationship("uses", "queue", "machine", "is served by", "Jobs receive service from the machine.", True, DefinitionStatus.DEFINED),)
    mechanisms = (Mechanism("service", "Service event", "A job receives service.", ("queue", "machine"), ("queue",), "When a job reaches the machine.", "The job completes and the machine becomes available.", "Select the first waiting job, process it for the specified service duration, then release the machine.", DefinitionStatus.DEFINED),)
    return make_project(concepts=concepts, properties=properties, relationships=relationships, mechanisms=mechanisms)


def abm_project():
    concepts = (
        Concept("person", "Person", ConceptKind.ACTOR, ConceptOrigin.USER_DEFINED, "An autonomous community participant.", DefinitionStatus.DEFINED),
        Concept("resource", "Shared resource", ConceptKind.RESOURCE, ConceptOrigin.USER_DEFINED, "A limited shared resource.", DefinitionStatus.DEFINED),
    )
    properties = (Property("trust", "person", "Trust level", PropertyType.NUMBER, "0-1 scale", "A participant's trust level.", DefinitionStatus.DEFINED),)
    relationships = (Relationship("cooperates", "person", "resource", "contributes to", "A person contributes to the shared resource.", True, DefinitionStatus.DEFINED),)
    mechanisms = (Mechanism("cooperation", "Agent cooperation", "A participant chooses whether to cooperate.", ("person", "resource"), ("resource",), "When a participant observes resource availability.", "The participant contributes or withholds a resource unit.", "If trust is above the threshold and a unit is available, contribute one unit; otherwise do not contribute.", DefinitionStatus.DEFINED),)
    return make_project(concepts=concepts, properties=properties, relationships=relationships, mechanisms=mechanisms)


def mathematical_project():
    concepts = (
        Concept("supply", "Supply", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "Available supply quantity.", DefinitionStatus.DEFINED),
        Concept("demand", "Demand", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "Requested quantity.", DefinitionStatus.DEFINED),
    )
    properties = (
        Property("supply-value", "supply", "Supply value", PropertyType.NUMBER, "units", "Available units.", DefinitionStatus.DEFINED),
        Property("demand-value", "demand", "Demand value", PropertyType.NUMBER, "units", "Requested units.", DefinitionStatus.DEFINED),
    )
    relationships = (Relationship("balance", "supply", "demand", "net availability = supply - demand", "The difference between supply and demand gives net availability.", True, DefinitionStatus.DEFINED),)
    return make_project(concepts=concepts, properties=properties, relationships=relationships)


def data_project():
    concepts = (
        Concept("rainfall", "Rainfall", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "Measured rainfall.", DefinitionStatus.DEFINED),
        Concept("temperature", "Temperature", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "Measured temperature.", DefinitionStatus.DEFINED),
    )
    properties = (
        Property("rain", "rainfall", "Rainfall", PropertyType.NUMBER, "mm", "Rainfall amount.", DefinitionStatus.DEFINED),
        Property("temp", "temperature", "Temperature", PropertyType.NUMBER, "C", "Air temperature.", DefinitionStatus.DEFINED),
        Property("timestamp", "rainfall", "Observation timestamp", PropertyType.DATE_TIME, None, "Time of observation.", DefinitionStatus.DEFINED),
    )
    references = (EvidenceReference("dataset-ref", "Sample weather observations", ReferenceType.DATASET, "https://example.invalid/data", "Example source", 2026, "Metadata only; actual file must be verified."),)
    return make_project(concepts=concepts, properties=properties, evidence_references=references)
