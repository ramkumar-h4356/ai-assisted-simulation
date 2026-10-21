
"""Define and compare discrete-event simulation scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from simulations.engine import SimulationEngine
from simulations.metrics import EntityMetrics, calculate_entity_metrics
from simulations.resource import Resource


@dataclass(frozen=True, slots=True)
class ServiceJob:
    """Describe one job's arrival and service requirements."""

    entity_id: str
    arrival_time: float
    service_duration: float


@dataclass(frozen=True, slots=True)
class Scenario:
    """Configuration for one simulation experiment."""

    name: str
    resource_name: str
    resource_capacity: int
    jobs: tuple[ServiceJob, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Scenario name must be non-empty")

        if not isinstance(self.jobs, tuple) or not self.jobs:
            raise ValueError("Scenario must contain at least one job")

        job_ids = [job.entity_id for job in self.jobs]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError("Job identifiers must be unique")


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Summarize the outcomes of one completed scenario."""

    scenario_name: str
    entity_metrics: tuple[EntityMetrics, ...]
    average_waiting_time: float
    completion_time: float


def run_scenario(scenario: Scenario) -> ScenarioResult:
    """Run a scenario using the existing deterministic simulation engine."""

    engine = SimulationEngine()

    engine.add_resource(
        Resource(
            name=scenario.resource_name,
            capacity=scenario.resource_capacity,
        )
    )

    for job in scenario.jobs:
        engine.schedule_service(
            entity_id=job.entity_id,
            resource_name=scenario.resource_name,
            arrival_time=job.arrival_time,
            duration=job.service_duration,
        )

    events = engine.run()
    metrics = calculate_entity_metrics(events)

    average_waiting_time = sum(
        item.waiting_time for item in metrics
    ) / len(metrics)

    completion_time = max(
        item.completion_time for item in metrics
    )

    return ScenarioResult(
        scenario_name=scenario.name,
        entity_metrics=tuple(metrics),
        average_waiting_time=average_waiting_time,
        completion_time=completion_time,
    )


def compare_scenarios(
    scenarios: tuple[Scenario, ...],
) -> tuple[ScenarioResult, ...]:
    """Run multiple configurations and return their results."""

    if not scenarios:
        raise ValueError("At least one scenario is required")

    return tuple(run_scenario(scenario) for scenario in scenarios)
