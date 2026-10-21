
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
    """Execute service tasks against capacity-limited resources."""

    def __init__(self) -> None:
        self.env = simpy.Environment()
        self._resource_configs: dict[str, Resource] = {}
        self._runtime_resources: dict[str, simpy.Resource] = {}
        self.events: list[SimulationEvent] = []
        self._has_run = False

    def add_resource(self, resource: Resource) -> None:
        """Register a resource before scheduling tasks."""
        if self._has_run:
            raise RuntimeError("Cannot add resources after the simulation has run")

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
        """Schedule an entity to arrive and request a resource."""
        if self._has_run:
            raise RuntimeError("Cannot schedule services after the simulation has run")

        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ValueError("entity_id must be a non-empty string")

        for name, value in (
            ("arrival_time", arrival_time),
            ("duration", duration),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a finite number")
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

        if resource_name not in self._runtime_resources:
            raise ValueError(f"Unknown resource: {resource_name}")

        self.env.process(
            self._serve(
                entity_id,
                resource_name,
                float(arrival_time),
                float(duration),
            )
        )

    def _record(
        self, entity_id: str, event_type: str, resource_name: str
    ) -> None:
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

    def run(self) -> list[SimulationEvent]:
        """Run the simulation once and return the event log."""
        if self._has_run:
            raise RuntimeError("Simulation engine has already run")

        self._has_run = True
        self.env.run()
        return list(self.events)
