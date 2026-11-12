"""Domain models used by discrete-event simulations."""

from __future__ import annotations

from collections.abc import Mapping

from dataclasses import dataclass, field

from math import isfinite

from typing import Any

@dataclass(slots=True)
class Entity:
    """A uniquely identified item handled by a discrete-event simulation.

    ``created_at`` is measured in the simulation's own time unit. Attributes
    hold scenario-specific data, such as a customer's priority or an item's
    destination, without coupling the simulation engine to one domain.
    """

    identifier: str
    created_at: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("identifier must be a non-empty string")

        if isinstance(self.created_at, bool) or not isinstance(
            self.created_at, (int, float)
        ):
            raise TypeError("created_at must be a finite number")
        if not isfinite(self.created_at) or self.created_at < 0:
            raise ValueError("created_at must be a finite, non-negative number")

        if not isinstance(self.attributes, Mapping):
            raise TypeError("attributes must be a mapping")

        # Keep the entity independent from a caller-owned mapping.
        self.attributes = dict(self.attributes)

    def get(self, name: str, default: Any = None) -> Any:
        """Return an attribute value, or ``default`` when it has not been set."""
        return self.attributes.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Store scenario-specific data under a non-empty attribute name."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("attribute name must be a non-empty string")
        self.attributes[name] = value

    def update(self, values: Mapping[str, Any]) -> None:
        """Set several named attributes at once."""
        if not isinstance(values, Mapping):
            raise TypeError("values must be a mapping")
        for name, value in values.items():
            self.set(name, value)

@dataclass(slots=True)
class Resource:
    """Describe a resource that processes may request during a simulation.

    This stores the resource's name and capacity. SimPy will manage requests,
    waiting queues, and releases when we connect resources to the runtime.
    """

    name: str
    capacity: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        if isinstance(self.capacity, bool) or not isinstance(self.capacity, int):
            raise TypeError("capacity must be a positive integer")
        if self.capacity <= 0:
            raise ValueError("capacity must be a positive integer")

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

