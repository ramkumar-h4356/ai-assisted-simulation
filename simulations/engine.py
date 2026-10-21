"""Minimal discrete-event simulation runtime using SimPy."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import simpy

from .resource import Resource


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

        first_resource_name = stages[0][0]
        self._record(entity_id, "arrived", first_resource_name)

        for resource_name, duration in stages:
            resource = self._runtime_resources[resource_name]

            with resource.request() as request:
                yield request
                self._record(entity_id, "service_started", resource_name)

                yield self.env.timeout(duration)
                self._record(entity_id, "service_completed", resource_name)

    def run(self) -> list[SimulationEvent]:
        """Run the simulation once and return the event log."""
        if self._has_run:
            raise RuntimeError("Simulation engine has already run")

        self._has_run = True
        self.env.run()
        return list(self.events)