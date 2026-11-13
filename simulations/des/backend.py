"""Discrete-event scenario execution and SimPy backend adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .model import Resource, Scenario
from .runtime import (
    EntityMetrics,
    ResourceMetrics,
    SimulationEvent,
    SimulationEngine,
    calculate_entity_metrics,
    calculate_resource_metrics,
)

from simulations.core.backend import SimulationExecutionResult, SimulationMetric

from simulations.core.specification import SimulationParadigm, SimulationSpecification

@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Summarize the outcomes of one completed DES scenario."""

    scenario_name: str
    entity_metrics: tuple[EntityMetrics, ...]
    average_waiting_time: float
    completion_time: float
    resource_metrics: tuple[ResourceMetrics, ...]
    events: tuple[SimulationEvent, ...] = ()

def run_scenario(scenario: Scenario) -> ScenarioResult:
    """Run a scenario and calculate its performance metrics."""
    engine = SimulationEngine()

    for resource in scenario.resources:
        engine.add_resource(Resource(resource.name, resource.capacity))

    for job in scenario.jobs:
        stages = scenario._job_stages(job)

        if len(stages) == 1:
            engine.schedule_service(
                entity_id=job.entity_id,
                resource_name=stages[0].resource_name,
                arrival_time=job.arrival_time,
                duration=stages[0].service_duration,
            )
        else:
            engine.schedule_route(
                entity_id=job.entity_id,
                arrival_time=job.arrival_time,
                stages=[
                    (stage.resource_name, stage.service_duration)
                    for stage in stages
                ],
            )

    events = engine.run()
    entity_metrics = calculate_entity_metrics(events)
    resource_metrics = calculate_resource_metrics(
        events,
        resource_capacities=engine.resource_capacities,
    )

    average_waiting_time = sum(
        item.waiting_time for item in entity_metrics
    ) / len(entity_metrics)

    completion_time = max(
        item.completion_time for item in entity_metrics
    )

    return ScenarioResult(
        scenario_name=scenario.name,
        entity_metrics=tuple(entity_metrics),
        average_waiting_time=average_waiting_time,
        completion_time=completion_time,
        resource_metrics=tuple(resource_metrics),
        events=tuple(events),
    )

def compare_scenarios(
    scenarios: tuple[Scenario, ...],
) -> tuple[ScenarioResult, ...]:
    """Run multiple configurations and return their results."""
    if not scenarios:
        raise ValueError("At least one scenario is required")

    return tuple(run_scenario(scenario) for scenario in scenarios)

class SimPyBackend:
    """Execute discrete-event scenarios using SimPy."""

    name = "SimPy"
    paradigm = SimulationParadigm.DISCRETE_EVENT

    def __init__(
        self,
        runner: Callable[[Scenario], ScenarioResult] | None = None,
    ) -> None:
        self._runner = runner or run_scenario

    def execute(
        self,
        specification: SimulationSpecification,
    ) -> SimulationExecutionResult:
        """Execute a compiled Scenario and normalize its key metrics."""

        if not isinstance(specification, SimulationSpecification):
            raise TypeError(
                "specification must be a SimulationSpecification"
            )

        if specification.paradigm != self.paradigm:
            raise ValueError(
                f"SimPy does not support {specification.paradigm.value}"
            )

        if not isinstance(specification.model, Scenario):
            raise TypeError(
                "SimPyBackend requires a compiled Scenario model"
            )

        native_result = self._runner(specification.model)

        metrics = (
            SimulationMetric(
                name="average_waiting_time",
                value=native_result.average_waiting_time,
                unit="simulation_time",
            ),
            SimulationMetric(
                name="completion_time",
                value=native_result.completion_time,
                unit="simulation_time",
            ),
            SimulationMetric(
                name="entities_completed",
                value=len(native_result.entity_metrics),
                unit="entities",
            ),
        )

        return SimulationExecutionResult(
            specification_name=specification.name,
            paradigm=self.paradigm,
            backend_name=self.name,
            metrics=metrics,
            native_result=native_result,
        )
