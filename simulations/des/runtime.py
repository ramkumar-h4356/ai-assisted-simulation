"""Minimal discrete-event simulation runtime using SimPy."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import simpy

from .model import Resource

@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """A recorded event on the simulation timeline."""

    time: float
    entity_id: str
    event_type: str
    resource_name: str

class SimulationEngine:
    """Execute single-service tasks and multi-stage routes."""

    def __init__(self) -> None:
        self.env = simpy.Environment()
        self._resource_configs: dict[str, Resource] = {}
        self._runtime_resources: dict[str, simpy.Resource] = {}
        self.events: list[SimulationEvent] = []
        self._has_run = False
        self._scheduled_entity_ids: set[str] = set()

    @property
    def resource_capacities(self) -> dict[str, int]:
        """Return the configured capacity of each resource."""
        return {
            name: resource.capacity
            for name, resource in self._resource_configs.items()
        }

    def add_resource(self, resource: Resource) -> None:
        """Register a resource before scheduling tasks."""
        if self._has_run:
            raise RuntimeError(
                "Cannot add resources after the simulation has run"
            )

        if resource.name in self._resource_configs:
            raise ValueError(f"Resource already exists: {resource.name}")

        self._resource_configs[resource.name] = resource
        self._runtime_resources[resource.name] = simpy.Resource(
            self.env, capacity=resource.capacity
        )

    def schedule_service(
        self,
        entity_id: str,
        resource_name: str,
        arrival_time: float,
        duration: float,
    ) -> None:
        """Schedule an entity to arrive and request one resource."""
        if self._has_run:
            raise RuntimeError(
                "Cannot schedule services after the simulation has run"
            )

        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string")

        if entity_id in self._scheduled_entity_ids:
            raise ValueError(f"Entity already scheduled: {entity_id}")

        for name, value in (
            ("arrival_time", arrival_time),
            ("duration", duration),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a finite number")

            if not isfinite(value) or value < 0:
                raise ValueError(
                    f"{name} must be finite and non-negative"
                )

        if resource_name not in self._runtime_resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        # Register the ID only after validation succeeds.
        self._scheduled_entity_ids.add(entity_id)

        self.env.process(
            self._serve(
                entity_id,
                resource_name,
                float(arrival_time),
                float(duration),
            )
        )

    def schedule_route(
        self,
        entity_id: str,
        arrival_time: float,
        stages: list[tuple[str, float]],
    ) -> None:
        """Schedule an entity to visit multiple resources in sequence."""
        if self._has_run:
            raise RuntimeError(
                "Cannot schedule routes after the simulation has run"
            )

        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string")

        if entity_id in self._scheduled_entity_ids:
            raise ValueError(f"Entity already scheduled: {entity_id}")

        if isinstance(arrival_time, bool) or not isinstance(
            arrival_time, (int, float)
        ):
            raise TypeError("arrival_time must be a finite number")

        if not isfinite(arrival_time) or arrival_time < 0:
            raise ValueError(
                "arrival_time must be finite and non-negative"
            )

        if not isinstance(stages, list) or not stages:
            raise ValueError("A route must contain at least one stage")

        # Validate every stage before scheduling any process.
        for stage in stages:
            if not isinstance(stage, tuple) or len(stage) != 2:
                raise TypeError(
                    "Each stage must be a (resource_name, duration) tuple"
                )

            resource_name, duration = stage

            if not isinstance(resource_name, str) or not resource_name.strip():
                raise ValueError(
                    "Stage resource name must be a non-empty string"
                )

            if resource_name not in self._runtime_resources:
                raise ValueError(f"Unknown resource: {resource_name}")

            if isinstance(duration, bool) or not isinstance(
                duration, (int, float)
            ):
                raise TypeError("Stage duration must be a finite number")

            if not isfinite(duration) or duration < 0:
                raise ValueError(
                    "Stage duration must be finite and non-negative"
                )

        # Schedule exactly one process after all validation succeeds.
        normalized_stages = [
            (resource_name, float(duration))
            for resource_name, duration in stages
        ]
        self._scheduled_entity_ids.add(entity_id)

        self.env.process(
            self._serve_route(
                entity_id,
                float(arrival_time),
                normalized_stages,
            )
        )

    def _record(
        self,
        entity_id: str,
        event_type: str,
        resource_name: str,
    ) -> None:
        """Record an event at the current simulation time."""
        self.events.append(
            SimulationEvent(
                time=self.env.now,
                entity_id=entity_id,
                event_type=event_type,
                resource_name=resource_name,
            )
        )

    def _serve(
        self,
        entity_id: str,
        resource_name: str,
        arrival_time: float,
        duration: float,
    ):
        """SimPy process for one entity's service."""
        yield self.env.timeout(arrival_time)

        self._record(entity_id, "arrived", resource_name)

        resource = self._runtime_resources[resource_name]

        with resource.request() as request:
            yield request
            self._record(entity_id, "service_started", resource_name)

            yield self.env.timeout(duration)
            self._record(entity_id, "service_completed", resource_name)

    def _serve_route(
        self,
        entity_id: str,
        arrival_time: float,
        stages: list[tuple[str, float]],
    ):
        """Execute each stage of an entity's route in order."""
        yield self.env.timeout(arrival_time)

        for resource_name, duration in stages:
            # Record when the entity reaches each stage.
            self._record(entity_id, "arrived", resource_name)

            resource = self._runtime_resources[resource_name]

            with resource.request() as request:
                yield request
                self._record(
                    entity_id, "service_started", resource_name
                )

                yield self.env.timeout(duration)
                self._record(
                    entity_id, "service_completed", resource_name
                )

    def run(self) -> list[SimulationEvent]:
        """Run the simulation once and return the event log."""
        if self._has_run:
            raise RuntimeError("Simulation engine has already run")

        self._has_run = True
        self.env.run()
        return list(self.events)

@dataclass(frozen=True, slots=True)
class StageMetrics:
    """Performance measurements for one stage of an entity's journey."""

    entity_id: str
    resource_name: str
    arrival_time: float
    service_start_time: float
    completion_time: float
    waiting_time: float
    service_time: float

@dataclass(frozen=True, slots=True)
class EntityMetrics:
    """Performance measurements for an entity's complete journey."""

    entity_id: str
    arrival_time: float
    completion_time: float
    waiting_time: float
    service_time: float
    time_in_system: float

@dataclass(frozen=True, slots=True)
class SimulationSummary:
    """Aggregated performance metrics for completed entities."""

    completed_entities: int
    average_waiting_time: float
    average_service_time: float
    average_time_in_system: float

@dataclass(frozen=True, slots=True)
class ResourceMetrics:
    """Performance measurements for a resource."""

    resource_name: str
    completed_services: int
    average_waiting_time: float
    average_service_time: float
    utilization: float = 0.0

def _group_stage_events(
    events: list[SimulationEvent],
) -> dict[str, list[StageMetrics]]:
    """Validate events and calculate metrics for each completed stage."""
    grouped: dict[str, dict[str, list[SimulationEvent]]] = {}
    expected_types = {"arrived", "service_started", "service_completed"}

    for event in events:
        if event.event_type not in expected_types:
            raise ValueError(f"Unknown event type: {event.event_type}")

        entity_stages = grouped.setdefault(event.entity_id, {})
        stage_events = entity_stages.setdefault(event.resource_name, [])

        stage_events.append(event)

    results: dict[str, list[StageMetrics]] = {}

    for entity_id, stages in grouped.items():
        entity_results: list[StageMetrics] = []

        for resource_name, stage_events in stages.items():
            by_type: dict[str, list[SimulationEvent]] = {
                event_type: []
                for event_type in expected_types
            }

            for event in stage_events:
                by_type[event.event_type].append(event)

            if any(len(by_type[event_type]) != 1 for event_type in expected_types):
                raise ValueError(
                    f"Incomplete or duplicate event history for "
                    f"{entity_id} at {resource_name}"
                )

            arrival = by_type["arrived"][0]
            start = by_type["service_started"][0]
            completion = by_type["service_completed"][0]

            if not arrival.time <= start.time <= completion.time:
                raise ValueError(
                    f"Invalid event timeline for {entity_id} "
                    f"at {resource_name}"
                )

            entity_results.append(
                StageMetrics(
                    entity_id=entity_id,
                    resource_name=resource_name,
                    arrival_time=arrival.time,
                    service_start_time=start.time,
                    completion_time=completion.time,
                    waiting_time=start.time - arrival.time,
                    service_time=completion.time - start.time,
                )
            )

        results[entity_id] = sorted(
            entity_results,
            key=lambda stage: (stage.arrival_time, stage.service_start_time),
        )

    return results

def calculate_stage_metrics(
    events: list[SimulationEvent],
) -> list[StageMetrics]:
    """Calculate waiting and service time for every entity at every stage."""
    grouped = _group_stage_events(events)

    return sorted(
        (stage for stages in grouped.values() for stage in stages),
        key=lambda stage: (
            stage.arrival_time,
            stage.entity_id,
            stage.service_start_time,
        ),
    )

def calculate_entity_metrics(
    events: list[SimulationEvent],
) -> list[EntityMetrics]:
    """Calculate total waiting, service, and system time per entity."""
    grouped = _group_stage_events(events)
    results: list[EntityMetrics] = []

    for entity_id, stages in grouped.items():
        if not stages:
            continue

        results.append(
            EntityMetrics(
                entity_id=entity_id,
                arrival_time=stages[0].arrival_time,
                completion_time=stages[-1].completion_time,
                waiting_time=sum(stage.waiting_time for stage in stages),
                service_time=sum(stage.service_time for stage in stages),
                time_in_system=(
                    stages[-1].completion_time - stages[0].arrival_time
                ),
            )
        )

    return sorted(
        results,
        key=lambda result: (result.arrival_time, result.entity_id),
    )

def calculate_simulation_summary(
    events: list[SimulationEvent],
) -> SimulationSummary:
    """Calculate aggregate performance metrics for completed entities."""
    entities = calculate_entity_metrics(events)
    count = len(entities)

    if count == 0:
        return SimulationSummary(
            completed_entities=0,
            average_waiting_time=0.0,
            average_service_time=0.0,
            average_time_in_system=0.0,
        )

    return SimulationSummary(
        completed_entities=count,
        average_waiting_time=(
            sum(entity.waiting_time for entity in entities) / count
        ),
        average_service_time=(
            sum(entity.service_time for entity in entities) / count
        ),
        average_time_in_system=(
            sum(entity.time_in_system for entity in entities) / count
        ),
    )

def calculate_resource_metrics(
    events: list[SimulationEvent],
    resource_capacities: dict[str, int] | None = None,
) -> list[ResourceMetrics]:
    """Calculate aggregated performance metrics for each resource."""
    stages = calculate_stage_metrics(events)

    if not stages:
        return []

    simulation_start = min(stage.arrival_time for stage in stages)
    simulation_end = max(stage.completion_time for stage in stages)
    simulation_duration = simulation_end - simulation_start

    grouped: dict[str, list[StageMetrics]] = {}

    for stage in stages:
        grouped.setdefault(stage.resource_name, []).append(stage)

    capacities = resource_capacities or {}
    results: list[ResourceMetrics] = []

    for resource_name, resource_stages in grouped.items():
        count = len(resource_stages)
        total_service_time = sum(
            stage.service_time for stage in resource_stages
        )
        capacity = capacities.get(resource_name, 1)

        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("Resource capacities must be integers")
        if capacity <= 0:
            raise ValueError("Resource capacities must be positive")

        available_capacity_time = simulation_duration * capacity
        utilization = (
            total_service_time / available_capacity_time * 100.0
            if available_capacity_time > 0
            else 0.0
        )

        results.append(
            ResourceMetrics(
                resource_name=resource_name,
                completed_services=count,
                average_waiting_time=(
                    sum(stage.waiting_time for stage in resource_stages)
                    / count
                ),
                average_service_time=total_service_time / count,
                utilization=utilization,
            )
        )

    return sorted(results, key=lambda result: result.resource_name)

def identify_potential_bottlenecks(
    resource_metrics: list[ResourceMetrics],
) -> list[ResourceMetrics]:
    """Return resources with the highest positive average waiting time."""

    if not resource_metrics:
        return []

    highest_waiting_time = max(
        item.average_waiting_time
        for item in resource_metrics
    )

    if highest_waiting_time <= 0:
        return []

    bottlenecks = [
        item
        for item in resource_metrics
        if item.average_waiting_time == highest_waiting_time
    ]

    return sorted(
        bottlenecks,
        key=lambda item: item.resource_name,
    )
