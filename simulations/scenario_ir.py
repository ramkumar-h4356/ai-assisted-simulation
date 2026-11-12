"""Backend-neutral intermediate representation of simulation scenarios."""

from dataclasses import dataclass
from typing import Any

from simulations.scenario_understanding import FactOrigin, ScenarioUncertainty


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