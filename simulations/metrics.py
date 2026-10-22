"""Calculate per-stage and per-entity metrics from a simulation event log."""

from __future__ import annotations

from dataclasses import dataclass

from simulations.engine import SimulationEvent


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
