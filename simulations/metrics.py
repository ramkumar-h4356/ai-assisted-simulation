
"""Calculate per-entity metrics from a completed simulation event log."""

from __future__ import annotations

from dataclasses import dataclass

from simulations.engine import SimulationEvent


@dataclass(frozen=True, slots=True)
class EntityMetrics:
    """Performance measurements for one completed entity."""

    entity_id: str
    resource_name: str
    arrival_time: float
    service_start_time: float
    completion_time: float
    waiting_time: float
    service_time: float
    time_in_system: float


def calculate_entity_metrics(
    events: list[SimulationEvent],
) -> list[EntityMetrics]:
    """Calculate waiting, service, and total time for each entity.

    Each entity must have exactly one arrival, service start, and completion
    event. This matches the current engine's one-service-per-entity model.
    """
    grouped: dict[str, dict[str, SimulationEvent]] = {}
    expected_types = {"arrived", "service_started", "service_completed"}

    for event in events:
        if event.event_type not in expected_types:
            raise ValueError(f"Unknown event type: {event.event_type}")

        entity_events = grouped.setdefault(event.entity_id, {})

        if event.event_type in entity_events:
            raise ValueError(
                f"Duplicate {event.event_type} event for {event.entity_id}"
            )

        entity_events[event.event_type] = event

    results: list[EntityMetrics] = []

    for entity_id, entity_events in grouped.items():
        if set(entity_events) != expected_types:
            raise ValueError(
                f"Incomplete event history for entity {entity_id}"
            )

        arrival = entity_events["arrived"]
        start = entity_events["service_started"]
        completion = entity_events["service_completed"]

        if not (
            arrival.time <= start.time <= completion.time
        ):
            raise ValueError(
                f"Invalid event timeline for entity {entity_id}"
            )

        resource_names = {
            arrival.resource_name,
            start.resource_name,
            completion.resource_name,
        }
        if len(resource_names) != 1:
            raise ValueError(
                f"Inconsistent resource history for entity {entity_id}"
            )

        results.append(
            EntityMetrics(
                entity_id=entity_id,
                resource_name=arrival.resource_name,
                arrival_time=arrival.time,
                service_start_time=start.time,
                completion_time=completion.time,
                waiting_time=start.time - arrival.time,
                service_time=completion.time - start.time,
                time_in_system=completion.time - arrival.time,
            )
        )

    return sorted(results, key=lambda result: (result.arrival_time, result.entity_id))
