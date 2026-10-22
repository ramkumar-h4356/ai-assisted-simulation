
"""Define and compare discrete-event simulation scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from simulations.engine import SimulationEngine
from simulations.metrics import (
    EntityMetrics,
    ResourceMetrics,
    calculate_entity_metrics,
    calculate_resource_metrics,
)
from simulations.resource import Resource


@dataclass(frozen=True, slots=True)
class ServiceStage:
    """Describe one stage in an entity's route."""

    resource_name: str
    service_duration: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.resource_name, str)
            or not self.resource_name.strip()
        ):
            raise ValueError("Resource name must be non-empty")

        value = self.service_duration
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("service_duration must be a number")

        if not isfinite(value) or value < 0:
            raise ValueError(
                "service_duration must be finite and non-negative"
            )


@dataclass(frozen=True, slots=True)
class ScenarioResource:
    """Describe a resource available to a scenario."""

    name: str
    capacity: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Resource name must be non-empty")

        if isinstance(self.capacity, bool) or not isinstance(
            self.capacity, int
        ):
            raise TypeError("Resource capacity must be an integer")

        if self.capacity <= 0:
            raise ValueError("Resource capacity must be positive")


@dataclass(frozen=True, slots=True)
class ServiceJob:
    """Describe one entity's arrival and service requirements."""

    entity_id: str
    arrival_time: float
    service_duration: float | None = None
    stages: tuple[ServiceStage, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id.strip():
            raise ValueError("Job identifier must be non-empty")

        for name, value in (("arrival_time", self.arrival_time),):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")

            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

        if self.stages:
            if self.service_duration is not None:
                raise ValueError(
                    "Specify service_duration or stages, not both"
                )

            if not isinstance(self.stages, tuple) or any(
                not isinstance(stage, ServiceStage) for stage in self.stages
            ):
                raise TypeError("stages must be a tuple of ServiceStage objects")

            if not self.stages:
                raise ValueError("A job must contain at least one stage")
        else:
            if self.service_duration is None:
                raise ValueError(
                    "A job needs a service_duration or at least one stage"
                )

            value = self.service_duration
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("service_duration must be a number")

            if not isfinite(value) or value < 0:
                raise ValueError(
                    "service_duration must be finite and non-negative"
                )


@dataclass(frozen=True, slots=True)
class Scenario:
    """Configuration for one simulation experiment."""

    name: str
    resource_name: str | None = None
    resource_capacity: int | None = None
    jobs: tuple[ServiceJob, ...] = ()
    resources: tuple[ScenarioResource, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Scenario name must be non-empty")

        # Support the old single-resource constructor.
        if self.resource_name is not None or self.resource_capacity is not None:
            if self.resources:
                raise ValueError(
                    "Use either legacy resource fields or resources, not both"
                )

            if (
                not isinstance(self.resource_name, str)
                or not self.resource_name.strip()
            ):
                raise ValueError("Resource name must be non-empty")

            if isinstance(self.resource_capacity, bool) or not isinstance(
                self.resource_capacity, int
            ):
                raise TypeError("Resource capacity must be an integer")

            if self.resource_capacity <= 0:
                raise ValueError("Resource capacity must be positive")

            object.__setattr__(
                self,
                "resources",
                (
                    ScenarioResource(
                        self.resource_name,
                        self.resource_capacity,
                    ),
                ),
            )

        if not isinstance(self.resources, tuple) or not self.resources:
            raise ValueError("Scenario must contain at least one resource")

        if any(
            not isinstance(resource, ScenarioResource)
            for resource in self.resources
        ):
            raise TypeError(
                "All resources must be ScenarioResource instances"
            )

        resource_names = [resource.name for resource in self.resources]
        if len(resource_names) != len(set(resource_names)):
            raise ValueError("Resource names must be unique")

        if not isinstance(self.jobs, tuple) or not self.jobs:
            raise ValueError("Scenario must contain at least one job")

        if any(not isinstance(job, ServiceJob) for job in self.jobs):
            raise TypeError("All jobs must be ServiceJob instances")

        job_ids = [job.entity_id for job in self.jobs]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError("Job identifiers must be unique")

        known_resources = set(resource_names)
        for job in self.jobs:
            for stage in self._job_stages(job):
                if stage.resource_name not in known_resources:
                    raise ValueError(
                        f"Job {job.entity_id} uses unknown resource: "
                        f"{stage.resource_name}"
                    )

    def _job_stages(self, job: ServiceJob) -> tuple[ServiceStage, ...]:
        """Return explicit stages or convert a legacy single service."""
        if job.stages:
            return job.stages

        # Legacy jobs use the first (and normally only) configured resource.
        return (
            ServiceStage(
                resource_name=self.resources[0].name,
                service_duration=job.service_duration,  # type: ignore[arg-type]
            ),
        )


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Summarize the outcomes of one completed scenario."""

    scenario_name: str
    entity_metrics: tuple[EntityMetrics, ...]
    average_waiting_time: float
    completion_time: float
    resource_metrics: tuple[ResourceMetrics, ...]


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
    )


def compare_scenarios(
    scenarios: tuple[Scenario, ...],
) -> tuple[ScenarioResult, ...]:
    """Run multiple configurations and return their results."""
    if not scenarios:
        raise ValueError("At least one scenario is required")

    return tuple(run_scenario(scenario) for scenario in scenarios)
