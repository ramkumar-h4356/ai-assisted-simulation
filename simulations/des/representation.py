"""Intermediate representations and provenance for DES scenarios."""

from dataclasses import dataclass

from enum import Enum

from typing import Any

class FactOrigin(Enum):
    """Describe where a scenario fact came from."""

    EXPLICIT = "explicit"
    INFERRED = "inferred"
    DEFAULTED = "defaulted"
    SYSTEM_GENERATED = "system_generated"

class UncertaintyType(Enum):
    """Describe unresolved information in a scenario."""

    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"

class ReadinessStatus(Enum):
    """Describe whether a scenario can proceed to model generation."""

    INCOMPLETE = "incomplete"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY = "ready"

@dataclass(frozen=True, slots=True)
class ScenarioFact:
    """Represent one extracted fact about a simulation scenario."""

    name: str
    value: Any
    origin: FactOrigin

@dataclass(frozen=True, slots=True)
class ScenarioUncertainty:
    """Represent unresolved information in a simulation scenario."""

    name: str
    uncertainty_type: UncertaintyType
    description: str

@dataclass(frozen=True, slots=True)
class ScenarioUnderstanding:
    """Store the current understanding of a simulation scenario."""

    scenario_name: str
    facts: tuple[ScenarioFact, ...] = ()
    uncertainties: tuple[ScenarioUncertainty, ...] = ()
    readiness: ReadinessStatus = ReadinessStatus.INCOMPLETE

def evaluate_readiness(
    understanding: ScenarioUnderstanding,
) -> ReadinessStatus:
    """Determine scenario readiness from its unresolved uncertainties."""

    if not isinstance(understanding, ScenarioUnderstanding):
        raise TypeError(
            "understanding must be a ScenarioUnderstanding instance"
        )

    if not understanding.uncertainties:
        return ReadinessStatus.READY

    uncertainty_types = {
        uncertainty.uncertainty_type
        for uncertainty in understanding.uncertainties
    }

    if (
        UncertaintyType.AMBIGUOUS in uncertainty_types
        or UncertaintyType.CONTRADICTORY in uncertainty_types
    ):
        return ReadinessStatus.NEEDS_CLARIFICATION

    return ReadinessStatus.INCOMPLETE

def add_or_update_fact(
    understanding: ScenarioUnderstanding,
    fact: ScenarioFact,
) -> ScenarioUnderstanding:
    """Add a new fact or replace an existing fact with the same name."""

    if not isinstance(understanding, ScenarioUnderstanding):
        raise TypeError("Invalid scenario understanding")

    if not isinstance(fact, ScenarioFact):
        raise TypeError("fact must be a ScenarioFact instance")

    updated_facts = tuple(
        existing
        for existing in understanding.facts
        if existing.name != fact.name
    ) + (fact,)

    updated = ScenarioUnderstanding(
        scenario_name=understanding.scenario_name,
        facts=updated_facts,
        uncertainties=understanding.uncertainties,
    )

    return ScenarioUnderstanding(
        scenario_name=updated.scenario_name,
        facts=updated.facts,
        uncertainties=updated.uncertainties,
        readiness=evaluate_readiness(updated),
    )

def resolve_uncertainty(
    understanding: ScenarioUnderstanding,
    uncertainty_name: str,
) -> ScenarioUnderstanding:
    """Remove a resolved uncertainty and recalculate readiness."""

    if not isinstance(understanding, ScenarioUnderstanding):
        raise TypeError("Invalid scenario understanding")

    remaining = tuple(
        uncertainty
        for uncertainty in understanding.uncertainties
        if uncertainty.name != uncertainty_name
    )

    updated = ScenarioUnderstanding(
        scenario_name=understanding.scenario_name,
        facts=understanding.facts,
        uncertainties=remaining,
    )

    return ScenarioUnderstanding(
        scenario_name=updated.scenario_name,
        facts=updated.facts,
        uncertainties=updated.uncertainties,
        readiness=evaluate_readiness(updated),
    )

def update_scenario(
    understanding: ScenarioUnderstanding,
    fact: ScenarioFact,
) -> ScenarioUnderstanding:
    """Update a fact and resolve its matching missing uncertainty."""

    if not isinstance(understanding, ScenarioUnderstanding):
        raise TypeError("Invalid scenario understanding")

    if not isinstance(fact, ScenarioFact):
        raise TypeError("fact must be a ScenarioFact instance")

    updated_facts = tuple(
        existing
        for existing in understanding.facts
        if existing.name != fact.name
    ) + (fact,)

    remaining_uncertainties = tuple(
        uncertainty
        for uncertainty in understanding.uncertainties
        if not (
            uncertainty.name == fact.name
            and uncertainty.uncertainty_type == UncertaintyType.MISSING
        )
    )

    updated = ScenarioUnderstanding(
        scenario_name=understanding.scenario_name,
        facts=updated_facts,
        uncertainties=remaining_uncertainties,
    )

    return ScenarioUnderstanding(
        scenario_name=updated.scenario_name,
        facts=updated.facts,
        uncertainties=updated.uncertainties,
        readiness=evaluate_readiness(updated),
    )

@dataclass(frozen=True, slots=True)
class KnownValue:
    """Store a value together with its origin."""

    value: Any
    origin: FactOrigin

@dataclass(frozen=True, slots=True)
class ResourceUnderstanding:
    """Represent one resource and its known properties."""

    name: KnownValue | None = None
    capacity: KnownValue | None = None

@dataclass(frozen=True, slots=True)
class StageUnderstanding:
    """Represent one service stage."""

    resource_name: KnownValue | None = None
    service_duration: KnownValue | None = None

@dataclass(frozen=True, slots=True)
class JobUnderstanding:
    """Represent one job and its ordered service stages."""

    entity_id: KnownValue | None = None
    arrival_time: KnownValue | None = None
    stages: tuple[StageUnderstanding, ...] | None = None

@dataclass(frozen=True, slots=True)
class ScenarioIR:
    """Represent the complete structured understanding of a scenario."""

    scenario_name: KnownValue | None = None
    resources: tuple[ResourceUnderstanding, ...] | None = None
    jobs: tuple[JobUnderstanding, ...] | None = None
    uncertainties: tuple[ScenarioUncertainty, ...] = ()
