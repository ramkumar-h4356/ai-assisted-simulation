from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus, Mechanism, Property,
    PropertyType, Relationship,
)
from readiness import BackendStatus, FitLevel, Paradigm, ReadinessStatus, assess_readiness, dumps_report, loads_report
from tests.readiness.helpers import make_project


def system_dynamics_project():
    concepts = (
        Concept("susceptible", "Susceptible Stock", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "People who can become infected; an accumulated population level.", DefinitionStatus.DEFINED),
        Concept("infected", "Infected Stock", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "People currently infected; an accumulated population level.", DefinitionStatus.DEFINED),
        Concept("recovered", "Recovered Stock", ConceptKind.VARIABLE, ConceptOrigin.USER_DEFINED, "People who have recovered; an accumulated population level.", DefinitionStatus.DEFINED),
        Concept("infection-flow", "Infection Flow", ConceptKind.PROCESS, ConceptOrigin.USER_DEFINED, "Transfers people from susceptible to infected.", DefinitionStatus.DEFINED),
        Concept("recovery-flow", "Recovery Flow", ConceptKind.PROCESS, ConceptOrigin.USER_DEFINED, "Transfers people from infected to recovered.", DefinitionStatus.DEFINED),
    )
    properties = (
        Property("s0", "susceptible", "Initial susceptible population", PropertyType.NUMBER, "people", "Initial stock level.", DefinitionStatus.DEFINED),
        Property("i0", "infected", "Initial infected population", PropertyType.NUMBER, "people", "Initial stock level.", DefinitionStatus.DEFINED),
        Property("r0", "recovered", "Initial recovered population", PropertyType.NUMBER, "people", "Initial stock level.", DefinitionStatus.DEFINED),
        Property("time", "susceptible", "Simulation time", PropertyType.DATE_TIME, "days", "Temporal model basis.", DefinitionStatus.DEFINED),
    )
    relationships = (
        Relationship("infection-loop", "susceptible", "infected", "balancing feedback through infection flow", "Infection reduces susceptible stock and increases infected stock.", True, DefinitionStatus.DEFINED),
        Relationship("recovery-loop", "infected", "recovered", "recovery flow", "Recovery reduces infected stock and increases recovered stock.", True, DefinitionStatus.DEFINED),
    )
    mechanisms = (
        Mechanism("infection", "Infection flow", "People become infected through contact.", ("susceptible", "infected"), ("susceptible", "infected"), "When susceptible and infected people are present.", "Susceptible stock decreases and infected stock increases.", "Transfer population at rate beta times susceptible times infected divided by total population.", DefinitionStatus.DEFINED),
        Mechanism("recovery", "Recovery flow", "Infected people recover.", ("infected", "recovered"), ("infected", "recovered"), "When an infected person recovers.", "Infected stock decreases and recovered stock increases.", "Transfer population from infected to recovered at rate gamma times infected.", DefinitionStatus.DEFINED),
    )
    return make_project(concepts=concepts, properties=properties, relationships=relationships, mechanisms=mechanisms)


def test_m7_identifies_system_dynamics_stock_flow_and_feedback_structure():
    report = assess_readiness(system_dynamics_project(), selected_paradigm=Paradigm.SYSTEM_DYNAMICS)
    assessment = report.assessment_for(Paradigm.SYSTEM_DYNAMICS)
    assert assessment.fit is FitLevel.STRONG
    assert assessment.backend_status is BackendStatus.IMPLEMENTED
    assert report.status is ReadinessStatus.READY_FOR_IMPLEMENTATION_PLANNING
    assert not assessment.missing_requirements


def test_system_dynamics_readiness_report_round_trips():
    report = assess_readiness(system_dynamics_project(), selected_paradigm=Paradigm.SYSTEM_DYNAMICS)
    restored = loads_report(dumps_report(report))
    assert restored.selected_paradigm is Paradigm.SYSTEM_DYNAMICS
    assert restored.assessment_for(Paradigm.SYSTEM_DYNAMICS).backend_status is BackendStatus.IMPLEMENTED
