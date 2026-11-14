from copy import deepcopy
import json
from pathlib import Path

import pytest

from simulations.abm.engine import run_agent_model
from simulations.abm.model import Position
from simulations.abm.schema import ABMModelDataError, agent_model_from_dict
from simulations.abm.validation import validate_agent_model


def _data(*, agents=None, space=None, actions=None, steps=1):
    agents = agents or [{
        "reference": "walker", "agent_type": "person", "state": "active",
        "attributes": {}, "position": {"x": 2, "y": 5},
    }]
    behaviours = [] if actions is None else [{
        "rule_id": "move", "agent_type": "person",
        "condition": {"type": "agent_state_is", "state": "active"},
        "actions": actions, "probability": 1.0,
    }]
    return {
        "name": "M17 spatial mechanics test",
        "space": space or {"width": 12, "height": 12, "boundary": "clamp"},
        "agents": agents,
        "environment": {"attributes": {}},
        "relationships": [],
        "behaviours": behaviours,
        "activation": {"mode": "sequential", "order": "declaration"},
        "termination": {"type": "max_steps", "value": steps},
        "random_seed": 11,
    }


def _run(data):
    model = agent_model_from_dict(data)
    report = validate_agent_model(model)
    assert report.is_valid, report.errors
    return run_agent_model(model)


def test_rectangle_obstacle_blocks_move_by_and_records_collision_event():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [{"id": "wall", "type": "rectangle", "x": 4, "y": 0, "width": 2, "height": 10}],
        },
        actions=[{"type": "move_by", "dx": 6, "dy": 0}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(2, 5)
    event = result.movement_events[0]
    assert event.status == "blocked"
    assert event.reason == "obstacle:wall"
    assert event.distance_travelled == 0


def test_circle_obstacle_blocks_direct_move():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [{"id": "rock", "type": "circle", "x": 5, "y": 5, "radius": 1}],
        },
        actions=[{"type": "move_to", "x": 9, "y": 5}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(2, 5)
    assert result.movement_events[0].reason == "obstacle:rock"


def test_slide_resolution_uses_deterministic_x_then_y_axis_fallback():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "collision_resolution": "slide",
            "obstacles": [{"id": "wall", "type": "rectangle", "x": 4, "y": 3, "width": 2, "height": 4}],
        },
        agents=[{
            "reference": "walker", "agent_type": "person", "state": "active",
            "attributes": {}, "position": {"x": 2, "y": 5}, "radius": 0.5,
        }],
        actions=[{"type": "move_by", "dx": 4, "dy": 4}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(2, 9)
    assert result.movement_events[0].status == "slid"
    assert result.movement_events[0].distance_travelled == pytest.approx(4.0)


def test_agent_collision_blocks_path_when_bodies_overlap():
    data = _data(
        agents=[
            {"reference": "walker", "agent_type": "person", "state": "active", "attributes": {},
             "position": {"x": 2, "y": 5}, "radius": 0.5},
            {"reference": "obstacle-person", "agent_type": "person", "state": "idle", "attributes": {},
             "position": {"x": 5, "y": 5}, "radius": 0.5},
        ],
        actions=[{"type": "move_to", "x": 8, "y": 5}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(2, 5)
    assert result.movement_events[0].reason == "agent:agent-2"


def test_per_step_movement_budget_is_shared_across_actions_and_resets_each_step():
    data = _data(
        agents=[{
            "reference": "walker", "agent_type": "person", "state": "active", "attributes": {},
            "position": {"x": 1, "y": 1}, "max_step_distance": 3,
        }],
        actions=[
            {"type": "move_by", "dx": 2, "dy": 0},
            {"type": "move_by", "dx": 2, "dy": 0},
        ],
        steps=2,
    )
    result = _run(data)
    assert result.history[1].agent("agent-1").position == Position(4, 1)
    assert result.history[2].agent("agent-1").position == Position(7, 1)
    assert result.movement_events[1].distance_travelled == pytest.approx(1.0)
    assert result.movement_events[1].distance_limit_reached is True
    assert result.movement_events[3].distance_travelled == pytest.approx(1.0)


def test_astar_move_towards_routes_around_rectangle_and_records_waypoints():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [{"id": "barrier", "type": "rectangle", "x": 5, "y": 2, "width": 2, "height": 8}],
        },
        agents=[{
            "reference": "walker", "agent_type": "person", "state": "active", "attributes": {},
            "position": {"x": 2, "y": 6}, "radius": 0.25,
        }],
        actions=[{"type": "move_towards", "x": 10, "y": 6, "max_distance": 30, "pathfinding": "astar", "grid_cell_size": 1}],
    )
    result = _run(data)
    event = result.movement_events[0]
    assert event.status == "moved"
    assert result.final_agents[0].position == Position(10, 6)
    assert len(event.path) > 3
    assert any(point.y < 2 or point.y > 10 for point in event.path)


def test_astar_move_towards_obeys_distance_limit_along_route():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [{"id": "barrier", "type": "rectangle", "x": 5, "y": 2, "width": 2, "height": 8}],
        },
        actions=[{"type": "move_towards", "x": 10, "y": 6, "max_distance": 1.25, "pathfinding": "astar", "grid_cell_size": 1}],
    )
    result = _run(data)
    event = result.movement_events[0]
    assert event.distance_travelled == pytest.approx(1.25)
    assert event.distance_limit_reached is True
    assert result.final_agents[0].position != Position(2, 5)


def test_astar_reports_no_path_when_rectangle_spans_entire_world():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [{"id": "wall", "type": "rectangle", "x": 5, "y": 0, "width": 2, "height": 12}],
        },
        actions=[{"type": "move_towards", "x": 10, "y": 5, "max_distance": 20, "pathfinding": "astar", "grid_cell_size": 1}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(2, 5)
    assert result.movement_events[0].status == "no_path"
    assert result.movement_events[0].reason == "path_not_found"



def test_wrapped_move_to_checks_periodic_obstacles_on_the_shortest_edge_route():
    data = _data(
        space={
            "width": 10, "height": 10, "boundary": "wrap",
            "obstacles": [{"id": "edge-rock", "type": "circle", "x": 0.5, "y": 5, "radius": 0.5}],
        },
        agents=[{"reference": "walker", "agent_type": "person", "state": "active",
                 "attributes": {}, "position": {"x": 9, "y": 5}, "radius": 0.2}],
        actions=[{"type": "move_to", "x": 1, "y": 5}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(9, 5)
    assert result.movement_events[0].status == "blocked"
    assert result.movement_events[0].reason == "obstacle:edge-rock"


def test_agent_step_limit_is_enforced_for_move_to_by_advancing_part_way():
    data = _data(
        agents=[{"reference": "walker", "agent_type": "person", "state": "active",
                 "attributes": {}, "position": {"x": 1, "y": 1}, "max_step_distance": 2}],
        actions=[{"type": "move_to", "x": 10, "y": 1}],
    )
    result = _run(data)
    assert result.final_agents[0].position == Position(3, 1)
    assert result.movement_events[0].distance_limit_reached is True
    assert result.movement_events[0].distance_travelled == pytest.approx(2)

def test_spatial_schema_parses_obstacles_agent_body_and_step_constraint():
    data = _data(
        space={
            "width": 12, "height": 12, "boundary": "clamp",
            "obstacles": [
                {"id": "wall", "type": "rectangle", "x": 6, "y": 1, "width": 1, "height": 8},
                {"id": "rock", "type": "circle", "x": 9, "y": 9, "radius": 0.5},
            ],
            "agent_collisions": False,
            "collision_resolution": "slide",
        },
        agents=[{
            "reference": "walker", "agent_type": "person", "state": "active", "attributes": {},
            "position": {"x": 2, "y": 5}, "radius": 0.25, "max_step_distance": 2,
        }],
    )
    model = agent_model_from_dict(data)
    assert len(model.space.obstacles) == 2
    assert model.space.agent_collisions is False
    assert model.space.collision_resolution.value == "slide"
    assert model.agents[0].radius == 0.25
    assert model.agents[0].max_step_distance == 2


def test_initial_agent_overlap_is_rejected():
    data = _data(agents=[
        {"reference": "a", "agent_type": "person", "state": "active", "attributes": {},
         "position": {"x": 3, "y": 3}, "radius": 1},
        {"reference": "b", "agent_type": "person", "state": "active", "attributes": {},
         "position": {"x": 4, "y": 3}, "radius": 1},
    ])
    report = validate_agent_model(agent_model_from_dict(data))
    assert "INITIAL_AGENT_COLLISION" in {issue.code for issue in report.errors}


def test_agent_starting_inside_obstacle_is_rejected():
    data = _data(
        space={"width": 12, "height": 12, "boundary": "clamp",
                "obstacles": [{"id": "wall", "type": "rectangle", "x": 1, "y": 1, "width": 3, "height": 3}]},
        agents=[{"reference": "walker", "agent_type": "person", "state": "active",
                 "attributes": {}, "position": {"x": 2, "y": 2}}],
    )
    report = validate_agent_model(agent_model_from_dict(data))
    assert "INITIAL_AGENT_IN_OBSTACLE" in {issue.code for issue in report.errors}


def test_astar_is_rejected_for_wrap_boundary():
    data = _data(
        space={"width": 12, "height": 12, "boundary": "wrap"},
        actions=[{"type": "move_towards", "x": 10, "y": 10, "max_distance": 1}],
    )
    report = validate_agent_model(agent_model_from_dict(data))
    assert "ASTAR_REQUIRES_CLAMP_BOUNDARY" in {issue.code for issue in report.errors}


def test_astar_grid_safety_limit_is_validated():
    data = _data(
        space={"width": 1000, "height": 1000, "boundary": "clamp"},
        actions=[{"type": "move_towards", "x": 900, "y": 900, "max_distance": 1,
                  "pathfinding": "astar", "grid_cell_size": 0.1}],
    )
    report = validate_agent_model(agent_model_from_dict(data))
    assert "ASTAR_GRID_TOO_LARGE" in {issue.code for issue in report.errors}


def test_movement_events_are_json_serialized_into_m9_trace():
    from compilation import compile_profile
    from execution import ExperimentConfig, execute_artifact
    from tests.compilation.helpers import abm_profile
    from tests.readiness.helpers import abm_project
    from dataclasses import replace

    project = abm_project()
    profile = abm_profile(project)
    model_data = deepcopy(profile.model_data)
    model_data["space"] = {"width": 12, "height": 12, "boundary": "clamp",
                           "obstacles": [{"id": "wall", "type": "rectangle", "x": 5, "y": 0, "width": 1, "height": 10}]}
    for index, agent in enumerate(model_data["agents"]):
        agent["position"] = {"x": 2 + index * 6, "y": 5}
    model_data["behaviours"][0]["actions"].append({"type": "move_by", "dx": 5, "dy": 0})
    spatial_profile = replace(profile, model_data=model_data)
    compilation = compile_profile(project, spatial_profile).artifact
    result = execute_artifact(compilation, ExperimentConfig(runs=1, base_seed=13))
    events = result.runs[0].trace["movement_events"]
    assert events
    assert events[0]["action_type"] == "move_by"
    assert events[0]["status"] == "blocked"
    assert events[0]["reason"] == "obstacle:wall"

    from simulation_studio import build_abm_replay
    replay = build_abm_replay(result, compilation)
    assert replay["space"]["obstacles"][0]["id"] == "wall"
    recorded = [event for frame in replay["frames"] for event in frame["movement_events"]]
    assert recorded
    assert any(event["status"] == "blocked" for event in recorded)
