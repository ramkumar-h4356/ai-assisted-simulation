"""M19 tests for discrete-event replay projections and inspection helpers."""

from pathlib import Path

import pytest

from simulations.des.replay import (
    build_des_replay,
    get_des_event,
    get_entity_journey,
    get_resource_replay,
    query_des_events,
)
from simulations.des.schema import scenario_from_json


@pytest.fixture

def two_stage_events():
    rows = []

    def add(time, entity_id, event_type, resource_name):
        rows.append({
            "time": time,
            "entity_id": entity_id,
            "event_type": event_type,
            "resource_name": resource_name,
        })

    add(0, "A", "arrived", "Registration")
    add(0, "A", "service_started", "Registration")
    add(1, "B", "arrived", "Registration")
    add(2, "C", "arrived", "Registration")
    add(4, "A", "service_completed", "Registration")
    add(4, "A", "arrived", "Consultation")
    add(4, "A", "service_started", "Consultation")
    add(4, "B", "service_started", "Registration")
    add(6, "B", "service_completed", "Registration")
    add(6, "C", "service_started", "Registration")
    add(7, "A", "service_completed", "Consultation")
    add(7, "C", "service_completed", "Registration")
    add(7, "B", "arrived", "Consultation")
    add(7, "B", "service_started", "Consultation")
    add(7, "C", "arrived", "Consultation")
    add(9, "B", "service_completed", "Consultation")
    add(9, "C", "service_started", "Consultation")
    add(10, "C", "service_completed", "Consultation")
    return rows


def test_builds_stable_timeline_entity_journeys_and_summary(two_stage_events):
    replay = build_des_replay(
        two_stage_events,
        resource_capacities={"Registration": 1, "Consultation": 1},
    )

    assert replay["schema_version"] == 1
    assert replay["simulation_start"] == 0.0
    assert replay["simulation_end"] == 10.0
    assert replay["duration"] == 10.0
    assert [item["sequence"] for item in replay["timeline"]] == list(range(18))
    assert replay["summary"] == {
        "event_count": 18,
        "entity_count": 3,
        "completed_entity_count": 3,
        "resource_count": 2,
        "total_waiting_time": 9.0,
        "average_waiting_time": 3.0,
        "max_entity_waiting_time": 6.0,
        "average_service_time": 4.333333333333333,
        "average_time_in_system": 7.666666666666667,
    }

    entity_c = next(item for item in replay["entities"] if item["entity_id"] == "C")
    assert entity_c["arrival_time"] == 2.0
    assert entity_c["completion_time"] == 10.0
    assert entity_c["waiting_time"] == 6.0
    assert [item["resource_name"] for item in entity_c["stages"]] == ["Registration", "Consultation"]
    assert entity_c["stages"][0]["waiting_time"] == 4.0
    assert entity_c["stages"][1]["waiting_time"] == 2.0


def test_resource_queue_occupancy_and_utilization_are_calculated(two_stage_events):
    replay = build_des_replay(
        two_stage_events,
        resource_capacities={"Registration": 1, "Consultation": 1},
    )
    registration = next(item for item in replay["resources"] if item["resource_name"] == "Registration")
    consultation = next(item for item in replay["resources"] if item["resource_name"] == "Consultation")

    assert registration["busy_time"] == 7.0
    assert registration["utilization"] == 70.0
    assert registration["peak_concurrent"] == 1
    assert registration["average_waiting_time"] == pytest.approx(7 / 3)
    assert registration["max_waiting_time"] == 4.0
    assert registration["peak_queue_length"] == 2
    assert registration["queue_intervals"] == [
        {"entity_id": "B", "queue_enter": 1.0, "queue_leave": 4.0, "waiting_time": 3.0},
        {"entity_id": "C", "queue_enter": 2.0, "queue_leave": 6.0, "waiting_time": 4.0},
    ]
    assert consultation["busy_time"] == 6.0
    assert consultation["utilization"] == 60.0
    assert consultation["peak_queue_length"] == 1
    assert consultation["queue_intervals"] == [
        {"entity_id": "C", "queue_enter": 7.0, "queue_leave": 9.0, "waiting_time": 2.0},
    ]


def test_query_and_inspection_helpers_preserve_sequence_and_return_copies(two_stage_events):
    replay = build_des_replay(
        two_stage_events,
        resource_capacities={"Registration": 1, "Consultation": 1},
    )

    filtered = query_des_events(replay, entity_id="B", event_type="service_started")
    assert [(item["sequence"], item["time"]) for item in filtered] == [(7, 4.0), (13, 7.0)]
    consultation_events = query_des_events(replay, resource_name="Consultation", start_time=7, end_time=9, limit=2)
    assert [item["sequence"] for item in consultation_events] == [10, 12]
    assert get_des_event(replay, 12)["entity_id"] == "B"
    assert get_entity_journey(replay, "A")["time_in_system"] == 7.0
    assert get_resource_replay(replay, "Registration")["peak_queue_length"] == 2

    journey = get_entity_journey(replay, "A")
    journey["stages"].clear()
    assert len(get_entity_journey(replay, "A")["stages"]) == 2


def test_zero_duration_services_do_not_create_negative_resource_occupancy():
    events = []
    for entity_id in ("A", "B"):
        events.extend([
            {"time": 0, "entity_id": entity_id, "event_type": "arrived", "resource_name": "Gate"},
            {"time": 0, "entity_id": entity_id, "event_type": "service_started", "resource_name": "Gate"},
            {"time": 0, "entity_id": entity_id, "event_type": "service_completed", "resource_name": "Gate"},
        ])
    replay = build_des_replay(events, resource_capacities={"Gate": 1})
    gate = replay["resources"][0]
    assert gate["busy_time"] == 0.0
    assert gate["utilization"] == 0.0
    assert gate["peak_concurrent"] == 1
    assert replay["summary"]["completed_entity_count"] == 2


def test_capacity_two_resource_can_process_two_entities_concurrently():
    events = []
    for entity_id in ("A", "B"):
        events.extend([
            {"time": 0, "entity_id": entity_id, "event_type": "arrived", "resource_name": "Server"},
            {"time": 0, "entity_id": entity_id, "event_type": "service_started", "resource_name": "Server"},
        ])
    for entity_id in ("A", "B"):
        events.append({"time": 4, "entity_id": entity_id, "event_type": "service_completed", "resource_name": "Server"})

    replay = build_des_replay(events, resource_capacities={"Server": 2})
    server = replay["resources"][0]
    assert server["peak_concurrent"] == 2
    assert server["busy_time"] == 8.0
    assert server["utilization"] == 100.0


def test_empty_run_preserves_configured_idle_resources():
    replay = build_des_replay([], resource_capacities={"Idle": 3})
    assert replay["timeline"] == []
    assert replay["entities"] == []
    assert replay["summary"]["resource_count"] == 1
    assert replay["resources"][0]["capacity"] == 3
    assert replay["resources"][0]["utilization"] == 0.0


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_rejects_invalid_resource_capacity(capacity):
    with pytest.raises(ValueError, match="positive integer"):
        build_des_replay([], resource_capacities={"Machine": capacity})


def test_rejects_non_chronological_event_input(two_stage_events):
    events = list(two_stage_events)
    events[2], events[3] = events[3], events[2]
    with pytest.raises(ValueError, match="non-decreasing"):
        build_des_replay(events)


def test_rejects_unknown_event_types_and_incomplete_entity_stages():
    unknown = [{"time": 0, "entity_id": "A", "event_type": "cancelled", "resource_name": "R"}]
    incomplete = [{"time": 0, "entity_id": "A", "event_type": "arrived", "resource_name": "R"}]
    with pytest.raises(ValueError, match="Unsupported DES replay event type"):
        build_des_replay(unknown)
    with pytest.raises(ValueError, match="incomplete stage"):
        build_des_replay(incomplete)


def test_rejects_resource_occupancy_above_capacity():
    events = []
    for entity_id in ("A", "B"):
        events.extend([
            {"time": 0, "entity_id": entity_id, "event_type": "arrived", "resource_name": "R"},
            {"time": 0, "entity_id": entity_id, "event_type": "service_started", "resource_name": "R"},
        ])
    for entity_id in ("A", "B"):
        events.append({"time": 3, "entity_id": entity_id, "event_type": "service_completed", "resource_name": "R"})
    with pytest.raises(ValueError, match="exceeds configured capacity"):
        build_des_replay(events, resource_capacities={"R": 1})


def test_inspection_helpers_report_missing_ids_and_invalid_filters():
    replay = build_des_replay([])
    with pytest.raises(KeyError):
        get_des_event(replay, 5)
    with pytest.raises(KeyError):
        get_entity_journey(replay, "missing")
    with pytest.raises(KeyError):
        get_resource_replay(replay, "missing")
    with pytest.raises(ValueError, match="start_time"):
        query_des_events(replay, start_time=4, end_time=2)


def test_bundled_two_stage_scenario_is_valid():
    scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "des" / "two_stage_clinic_replay.json"
    scenario = scenario_from_json(scenario_path.read_text(encoding="utf-8"))
    assert scenario.name == "Two-stage clinic queue replay"
    assert [item.name for item in scenario.resources] == ["Registration", "Consultation"]
    assert len(scenario.jobs) == 3
    assert all(len(job.stages) == 2 for job in scenario.jobs)
