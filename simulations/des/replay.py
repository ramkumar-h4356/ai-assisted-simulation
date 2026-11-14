"""Deterministic, read-only replay projections for discrete-event runs (M19).

The input event log is canonical. This module never changes scheduling or
simulation outcomes; it validates the recorded sequence and derives timeline,
entity-journey, queue and resource-occupancy views from it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Iterable, Mapping


SUPPORTED_EVENT_TYPES = frozenset({"arrived", "service_started", "service_completed"})


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    """One event in the stable, recorded simulation order."""

    sequence: int
    time: float
    entity_id: str
    event_type: str
    resource_name: str


@dataclass(frozen=True, slots=True)
class EntityStageReplay:
    """One entity's visit to a single resource."""

    stage: int
    resource_name: str
    arrival_time: float
    service_start_time: float
    completion_time: float
    waiting_time: float
    service_time: float


@dataclass(frozen=True, slots=True)
class EntityReplay:
    """Aggregate journey and ordered resource stages for one entity."""

    entity_id: str
    arrival_time: float
    completion_time: float
    waiting_time: float
    service_time: float
    time_in_system: float
    stages: tuple[EntityStageReplay, ...]


@dataclass(frozen=True, slots=True)
class ResourceReplay:
    """Queue and resource occupancy history for one configured resource."""

    resource_name: str
    capacity: int
    busy_time: float
    utilization: float
    peak_concurrent: int
    average_waiting_time: float
    max_waiting_time: float
    peak_queue_length: int
    queue_intervals: tuple[dict[str, Any], ...]
    queue_length_intervals: tuple[dict[str, Any], ...]
    occupancy: tuple[dict[str, Any], ...]


def _value(event: Any, name: str) -> Any:
    if isinstance(event, Mapping):
        return event.get(name)
    return getattr(event, name, None)


def _finite_time(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite, non-negative number")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a finite, non-negative number")
    return float(value)


def _validate_capacities(resource_capacities: dict[str, int] | None) -> dict[str, int]:
    if resource_capacities is None:
        return {}
    if not isinstance(resource_capacities, dict):
        raise TypeError("resource_capacities must be a dictionary")
    capacities: dict[str, int] = {}
    for name, capacity in resource_capacities.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Resource names must be non-empty strings")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError(f"Resource {name!r} capacity must be a positive integer")
        capacities[name] = capacity
    return capacities


def _normalize_events(events: Iterable[Any]) -> list[ReplayEvent]:
    try:
        iterator = iter(events)
    except TypeError as error:
        raise TypeError("events must be an iterable of event records") from error

    normalized: list[ReplayEvent] = []
    for sequence, event in enumerate(iterator):
        if event is None:
            raise ValueError(f"Event {sequence} must be a record")
        time = _finite_time(_value(event, "time"), f"Event {sequence} time")
        entity_id = _value(event, "entity_id")
        event_type = _value(event, "event_type")
        resource_name = _value(event, "resource_name")
        if not all(isinstance(item, str) and item.strip() for item in (entity_id, event_type, resource_name)):
            raise ValueError(f"Event {sequence} requires non-empty entity_id, event_type and resource_name")
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"Unsupported DES replay event type: {event_type}")
        normalized.append(ReplayEvent(sequence, time, entity_id, event_type, resource_name))

    # Do not sort malformed traces: sequence order is provenance and tie order.
    if any(left.time > right.time for left, right in zip(normalized, normalized[1:])):
        raise ValueError("Replay events must be in non-decreasing simulation-time order")
    return normalized


def _build_entity_journeys(
    events: list[ReplayEvent],
) -> tuple[list[EntityReplay], dict[str, list[tuple[str, EntityStageReplay]]]]:
    by_entity: dict[str, list[ReplayEvent]] = {}
    for event in events:
        by_entity.setdefault(event.entity_id, []).append(event)

    entity_rows: list[EntityReplay] = []
    stages_by_resource: dict[str, list[tuple[str, EntityStageReplay]]] = {}
    for entity_id, entity_events in by_entity.items():
        stages: list[EntityStageReplay] = []
        pending: dict[str, Any] | None = None
        for event in entity_events:
            if event.event_type == "arrived":
                if pending is not None:
                    raise ValueError(
                        f"Entity {entity_id!r} arrived at a new stage before completing the previous stage"
                    )
                pending = {"resource_name": event.resource_name, "arrival_time": event.time}
            elif event.event_type == "service_started":
                if pending is None or pending["resource_name"] != event.resource_name or "service_start_time" in pending:
                    raise ValueError(f"Invalid service-start event for entity {entity_id!r}")
                if event.time < pending["arrival_time"]:
                    raise ValueError("Service cannot start before arrival")
                pending["service_start_time"] = event.time
            else:  # service_completed
                if pending is None or pending["resource_name"] != event.resource_name or "service_start_time" not in pending:
                    raise ValueError(f"Invalid service-completion event for entity {entity_id!r}")
                if event.time < pending["service_start_time"]:
                    raise ValueError("Service cannot complete before it starts")
                stage = EntityStageReplay(
                    stage=len(stages) + 1,
                    resource_name=event.resource_name,
                    arrival_time=pending["arrival_time"],
                    service_start_time=pending["service_start_time"],
                    completion_time=event.time,
                    waiting_time=pending["service_start_time"] - pending["arrival_time"],
                    service_time=event.time - pending["service_start_time"],
                )
                stages.append(stage)
                stages_by_resource.setdefault(event.resource_name, []).append((entity_id, stage))
                pending = None

        if pending is not None:
            raise ValueError(f"Entity {entity_id!r} has an incomplete stage in the event log")
        if stages:
            first, last = stages[0], stages[-1]
            entity_rows.append(EntityReplay(
                entity_id=entity_id,
                arrival_time=first.arrival_time,
                completion_time=last.completion_time,
                waiting_time=sum(item.waiting_time for item in stages),
                service_time=sum(item.service_time for item in stages),
                time_in_system=last.completion_time - first.arrival_time,
                stages=tuple(stages),
            ))

    entity_rows.sort(key=lambda item: (item.arrival_time, item.entity_id))
    return entity_rows, stages_by_resource


def _sweep_intervals(
    intervals: list[tuple[float, float]],
    *,
    start_time: float,
    end_time: float,
) -> tuple[list[dict[str, Any]], int]:
    """Return piecewise-constant queue length, aggregating same-time changes."""
    changes: dict[float, int] = {}
    for start, end in intervals:
        if end > start:
            changes[start] = changes.get(start, 0) + 1
            changes[end] = changes.get(end, 0) - 1
    times = sorted({start_time, end_time, *changes.keys()})
    current = peak = 0
    rows: list[dict[str, Any]] = []
    for index, time in enumerate(times[:-1]):
        current += changes.get(time, 0)
        next_time = times[index + 1]
        if current < 0:
            raise ValueError("Queue interval trace contains an invalid departure")
        peak = max(peak, current)
        if next_time > time:
            rows.append({"start": time, "end": next_time, "queue_length": current})
    if times:
        current += changes.get(times[-1], 0)
    if current != 0:
        raise ValueError("Queue interval trace does not return to an empty queue")
    return rows, peak


def _peak_resource_concurrency(
    events: list[ReplayEvent], capacities: dict[str, int]
) -> dict[str, int]:
    """Measure instantaneous concurrency in the original event sequence."""
    in_use = {name: 0 for name in capacities}
    peaks = {name: 0 for name in capacities}
    for event in events:
        if event.event_type == "service_started":
            in_use[event.resource_name] = in_use.get(event.resource_name, 0) + 1
            if in_use[event.resource_name] > capacities[event.resource_name]:
                raise ValueError(f"Resource {event.resource_name!r} occupancy exceeds configured capacity")
            peaks[event.resource_name] = max(peaks.get(event.resource_name, 0), in_use[event.resource_name])
        elif event.event_type == "service_completed":
            in_use[event.resource_name] = in_use.get(event.resource_name, 0) - 1
            if in_use[event.resource_name] < 0:
                raise ValueError(f"Resource {event.resource_name!r} has a completion without active service")
    if any(in_use.values()):
        raise ValueError("Resource event log contains active service that never completed")
    return peaks


def _resource_replays(
    stages_by_resource: dict[str, list[tuple[str, EntityStageReplay]]],
    capacities: dict[str, int],
    peak_concurrency: dict[str, int],
    *,
    simulation_start: float,
    simulation_end: float,
) -> list[ResourceReplay]:
    result: list[ResourceReplay] = []
    horizon = simulation_end - simulation_start

    for resource_name in sorted(capacities):
        capacity = capacities[resource_name]
        owned = stages_by_resource.get(resource_name, [])
        start_changes: dict[float, int] = {}
        queue_intervals: list[dict[str, Any]] = []
        queue_pairs: list[tuple[float, float]] = []
        waits: list[float] = []
        for entity_id, stage in owned:
            # Aggregate deltas at each timestamp. This correctly handles a
            # zero-duration service (start and completion at the same time)
            # without creating a negative transient occupancy.
            start_changes[stage.service_start_time] = start_changes.get(stage.service_start_time, 0) + 1
            start_changes[stage.completion_time] = start_changes.get(stage.completion_time, 0) - 1
            waits.append(stage.waiting_time)
            if stage.waiting_time > 0:
                queue_intervals.append({
                    "entity_id": entity_id,
                    "queue_enter": stage.arrival_time,
                    "queue_leave": stage.service_start_time,
                    "waiting_time": stage.waiting_time,
                })
                queue_pairs.append((stage.arrival_time, stage.service_start_time))

        occupancy: list[dict[str, Any]] = []
        busy_time = 0.0
        in_use = 0
        previous_time = simulation_start
        time_points = sorted({simulation_start, simulation_end, *start_changes.keys()})
        for time in time_points:
            if time > previous_time:
                occupancy.append({
                    "start": previous_time,
                    "end": time,
                    "in_use": in_use,
                    "capacity": capacity,
                })
                busy_time += (time - previous_time) * in_use
            in_use += start_changes.get(time, 0)
            if in_use < 0:
                raise ValueError(f"Resource {resource_name!r} has a completion without active service")
            if in_use > capacity:
                raise ValueError(f"Resource {resource_name!r} occupancy exceeds configured capacity")
            previous_time = time
        if in_use != 0:
            raise ValueError(f"Resource {resource_name!r} has service that never completes")

        queue_length_intervals, peak_queue_length = _sweep_intervals(
            queue_pairs, start_time=simulation_start, end_time=simulation_end
        )
        utilization = busy_time / (horizon * capacity) * 100.0 if horizon > 0 else 0.0
        average_wait = sum(waits) / len(waits) if waits else 0.0
        result.append(ResourceReplay(
            resource_name=resource_name,
            capacity=capacity,
            busy_time=busy_time,
            utilization=utilization,
            peak_concurrent=peak_concurrency.get(resource_name, 0),
            average_waiting_time=average_wait,
            max_waiting_time=max(waits, default=0.0),
            peak_queue_length=peak_queue_length,
            queue_intervals=tuple(queue_intervals),
            queue_length_intervals=tuple(queue_length_intervals),
            occupancy=tuple(occupancy),
        ))
    return result


def build_des_replay(
    events: Iterable[Any],
    *,
    resource_capacities: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a JSON-compatible replay from a canonical DES event log.

    Event order is retained exactly; equal timestamps use the original event
    sequence. Each stage must contain one arrival, service start and completion
    in that order. Resource utilization is calculated against the complete
    observed system horizon, normalized by configured resource capacity.
    """
    capacities = _validate_capacities(resource_capacities)
    normalized = _normalize_events(events)
    for event in normalized:
        capacities.setdefault(event.resource_name, 1)

    entities, stages_by_resource = _build_entity_journeys(normalized)
    start_time = min((row.arrival_time for row in entities), default=0.0)
    end_time = max((row.completion_time for row in entities), default=start_time)
    peak_concurrency = _peak_resource_concurrency(normalized, capacities)
    resource_rows = _resource_replays(
        stages_by_resource,
        capacities,
        peak_concurrency,
        simulation_start=start_time,
        simulation_end=end_time,
    )
    total_waiting = sum(row.waiting_time for row in entities)
    total_service = sum(row.service_time for row in entities)
    total_system = sum(row.time_in_system for row in entities)
    entity_count = len(entities)

    return {
        "schema_version": 1,
        "simulation_start": start_time,
        "simulation_end": end_time,
        "duration": end_time - start_time,
        "timeline": [asdict(event) for event in normalized],
        "summary": {
            "event_count": len(normalized),
            "entity_count": entity_count,
            "completed_entity_count": entity_count,
            "resource_count": len(resource_rows),
            "total_waiting_time": total_waiting,
            "average_waiting_time": total_waiting / entity_count if entity_count else 0.0,
            "max_entity_waiting_time": max((row.waiting_time for row in entities), default=0.0),
            "average_service_time": total_service / entity_count if entity_count else 0.0,
            "average_time_in_system": total_system / entity_count if entity_count else 0.0,
        },
        "entities": [
            {**asdict(row), "stages": [asdict(stage) for stage in row.stages]}
            for row in entities
        ],
        "resources": [
            {
                **asdict(row),
                "queue_intervals": list(row.queue_intervals),
                "queue_length_intervals": list(row.queue_length_intervals),
                "occupancy": list(row.occupancy),
            }
            for row in resource_rows
        ],
    }


def _replay_timeline(replay: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(replay, dict) or replay.get("schema_version") != 1:
        raise ValueError("replay must be a schema_version 1 DES replay object")
    timeline = replay.get("timeline")
    if not isinstance(timeline, list) or any(not isinstance(item, dict) for item in timeline):
        raise ValueError("replay.timeline must be an array of event objects")
    return timeline


def query_des_events(
    replay: dict[str, Any],
    *,
    entity_id: str | None = None,
    resource_name: str | None = None,
    event_type: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter events without changing their stable recorded sequence."""
    timeline = _replay_timeline(replay)
    for name, value in (("entity_id", entity_id), ("resource_name", resource_name)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{name} filter must be a non-empty string")
    if event_type is not None and event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"Unsupported event_type filter: {event_type}")
    lower = None if start_time is None else _finite_time(start_time, "start_time")
    upper = None if end_time is None else _finite_time(end_time, "end_time")
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("start_time must not be greater than end_time")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive integer or None")

    matched = []
    for event in timeline:
        if entity_id is not None and event.get("entity_id") != entity_id:
            continue
        if resource_name is not None and event.get("resource_name") != resource_name:
            continue
        if event_type is not None and event.get("event_type") != event_type:
            continue
        time = _finite_time(event.get("time"), "timeline event time")
        if lower is not None and time < lower:
            continue
        if upper is not None and time > upper:
            continue
        matched.append(deepcopy(event))
        if limit is not None and len(matched) >= limit:
            break
    return matched


def get_des_event(replay: dict[str, Any], sequence: int) -> dict[str, Any]:
    """Retrieve one event by its stable zero-based sequence number."""
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("sequence must be a non-negative integer")
    for event in _replay_timeline(replay):
        if event.get("sequence") == sequence:
            return deepcopy(event)
    raise KeyError(f"No DES replay event has sequence {sequence}")


def get_entity_journey(replay: dict[str, Any], entity_id: str) -> dict[str, Any]:
    """Retrieve the complete ordered journey for one entity."""
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError("entity_id must be a non-empty string")
    if not isinstance(replay, dict) or replay.get("schema_version") != 1:
        raise ValueError("replay must be a schema_version 1 DES replay object")
    for entity in replay.get("entities", []):
        if isinstance(entity, dict) and entity.get("entity_id") == entity_id:
            return deepcopy(entity)
    raise KeyError(f"No DES replay journey exists for entity {entity_id!r}")


def get_resource_replay(replay: dict[str, Any], resource_name: str) -> dict[str, Any]:
    """Retrieve queue and occupancy history for one resource."""
    if not isinstance(resource_name, str) or not resource_name.strip():
        raise ValueError("resource_name must be a non-empty string")
    if not isinstance(replay, dict) or replay.get("schema_version") != 1:
        raise ValueError("replay must be a schema_version 1 DES replay object")
    for resource in replay.get("resources", []):
        if isinstance(resource, dict) and resource.get("resource_name") == resource_name:
            return deepcopy(resource)
    raise KeyError(f"No DES replay resource exists for {resource_name!r}")
