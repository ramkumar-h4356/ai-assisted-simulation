import json
from pathlib import Path

import pytest

from simulations.abm.engine import run_agent_model
from simulations.abm.environment import (
    SpatialIndex,
    environment_objects_near,
    navigation_cost_at,
    point_in_polygon,
    regions_at,
    zones_at,
)
from simulations.abm.model import GridSpec, Position
from simulations.abm.schema import ABMModelDataError, agent_model_from_dict
from simulations.abm.spatial import astar_path, path_is_clear
from simulations.abm.validation import validate_agent_model


def _polygon(x1, y1, x2, y2):
    return (
        Position(x1, y1), Position(x2, y1),
        Position(x2, y2), Position(x1, y2),
    )


def _base_data(space, *, agents=None, actions=None, steps=1):
    return {
        "name": "M18 spatial environment test",
        "space": space,
        "agents": agents or [{
            "reference": "walker", "agent_type": "person", "state": "active",
            "attributes": {}, "position": {"x": 2, "y": 5}, "radius": 0.25,
        }],
        "environment": {"attributes": {}},
        "relationships": [],
        "behaviours": [{
            "rule_id": "move", "agent_type": "person",
            "condition": {"type": "agent_state_is", "state": "active"},
            "actions": actions or [{"type": "move_to", "x": 8, "y": 5}],
            "probability": 1.0,
        }],
        "activation": {"mode": "sequential", "order": "declaration"},
        "termination": {"type": "max_steps", "value": steps},
        "random_seed": 7,
    }


def test_grid_spec_maps_positions_and_clips_edge_cells():
    grid = GridSpec(3)
    assert grid.columns(10) == 4
    assert grid.rows(7) == 3
    assert grid.cell_for(Position(10, 7), 10, 7) == (3, 2)
    assert grid.cell_bounds(3, 2, 10, 7) == (9, 6, 10, 7)
    assert grid.cell_center(3, 2, 10, 7) == Position(9.5, 6.5)
    with pytest.raises(IndexError):
        grid.cell_bounds(4, 0, 10, 7)


def test_spatial_index_radius_bounds_move_and_remove_are_deterministic():
    index = SpatialIndex(2)
    index.add("b", Position(2, 0))
    index.add("a", Position(0, 0))
    index.add("c", Position(7, 4))
    assert [identifier for identifier, _ in index.query_radius(Position(0, 0), 2)] == ["a", "b"]
    assert [identifier for identifier, _ in index.query_bounds(0, 0, 3, 1)] == ["a", "b"]
    index.move("c", Position(1, 1))
    assert index.position("c") == Position(1, 1)
    assert [identifier for identifier, _ in index.query_radius(Position(0, 0), 2)] == ["a", "b", "c"]
    assert index.remove("b") == Position(2, 0)
    assert len(index) == 2
    with pytest.raises(KeyError):
        index.move("missing", Position(1, 1))


def test_polygon_region_zone_and_environment_object_queries():
    data = _base_data({
        "width": 12, "height": 10, "grid": {"cell_size": 2},
        "regions": [{"id": "park", "polygon": [
            {"x": 0, "y": 0}, {"x": 12, "y": 0},
            {"x": 12, "y": 10}, {"x": 0, "y": 10},
        ], "attributes": {"kind": "public"}, "tags": ["green", "public"]}],
        "zones": [{"id": "rough", "polygon": [
            {"x": 4, "y": 3}, {"x": 8, "y": 3},
            {"x": 8, "y": 7}, {"x": 4, "y": 7},
        ], "navigation_cost": 3.5, "tags": ["terrain"]}],
        "objects": [{"id": "tree", "position": {"x": 5, "y": 5}, "radius": 0.75,
                     "attributes": {"species": "oak"}, "tags": ["tree"]}],
    })
    model = agent_model_from_dict(data)
    assert validate_agent_model(model).is_valid
    assert point_in_polygon(Position(6, 5), model.space.regions[0].polygon)
    assert len(regions_at(model.space, Position(1, 1))) == 1
    assert zones_at(model.space, Position(6, 5))[0].identifier == "rough"
    assert navigation_cost_at(model.space, Position(6, 5)) == pytest.approx(3.5)
    assert navigation_cost_at(model.space, Position(1, 1)) == 1.0
    assert [item.identifier for item in environment_objects_near(model.space, Position(4, 5), 0.5)] == ["tree"]


def test_blocking_environment_object_prevents_tunnelling():
    data = _base_data({
        "width": 12, "height": 10,
        "objects": [{"id": "tree", "position": {"x": 5, "y": 5}, "radius": 0.75,
                     "blocks_movement": True}],
    })
    result = run_agent_model(agent_model_from_dict(data))
    assert result.final_agents[0].position == Position(2, 5)
    assert result.movement_events[0].status == "blocked"
    assert result.movement_events[0].reason == "object:tree"


def test_impassable_zone_blocks_direct_route_but_astar_finds_a_way_around():
    space_data = {
        "width": 12, "height": 12,
        "zones": [{"id": "lake", "passable": False, "polygon": [
            {"x": 5, "y": 0}, {"x": 7, "y": 0},
            {"x": 7, "y": 8}, {"x": 5, "y": 8},
        ]}],
    }
    model_data = _base_data(space_data, actions=[{
        "type": "move_towards", "x": 10, "y": 5, "max_distance": 30,
        "pathfinding": "astar", "grid_cell_size": 1,
    }])
    model = agent_model_from_dict(model_data)
    route = astar_path(model.space, Position(2, 5), Position(10, 5), 0.25, 1)
    assert route is not None
    assert any(point.y > 8 for point in route)
    assert all(path_is_clear(model.space, left, right, 0.25)[0] for left, right in zip(route, route[1:]))
    result = run_agent_model(model)
    assert result.final_agents[0].position == Position(10, 5)


def test_weighted_zone_makes_astar_prefer_a_longer_lower_cost_route():
    model = agent_model_from_dict(_base_data({
        "width": 12, "height": 12,
        "zones": [{"id": "mud", "navigation_cost": 12, "polygon": [
            {"x": 4, "y": 4}, {"x": 8, "y": 4},
            {"x": 8, "y": 7}, {"x": 4, "y": 7},
        ]}],
    }))
    route = astar_path(model.space, Position(1, 5), Position(11, 5), 0, 1)
    assert route is not None
    assert all(not (4 <= point.x <= 8 and 4 <= point.y <= 7) for point in route)
    assert max(point.y for point in route) > 7 or min(point.y for point in route) < 4


def test_spatial_neighbour_condition_uses_grid_index_and_sees_committed_moves():
    data = _base_data(
        {"width": 12, "height": 10, "grid": {"cell_size": 1}},
        agents=[
            {"reference": "mover", "agent_type": "mover", "state": "active", "attributes": {},
             "position": {"x": 1, "y": 1}},
            {"reference": "observer", "agent_type": "observer", "state": "watching", "attributes": {},
             "position": {"x": 8, "y": 5}},
        ],
        actions=[{"type": "move_to", "x": 7, "y": 5}],
    )
    data["behaviours"] = [
        {"rule_id": "move-first", "agent_type": "mover",
         "condition": {"type": "agent_state_is", "state": "active"},
         "actions": [{"type": "move_to", "x": 7, "y": 5}], "probability": 1.0},
        {"rule_id": "notice", "agent_type": "observer",
         "condition": {"type": "spatial_neighbour_state_count", "radius": 2, "state": "active", "operator": "gt", "count": 0},
         "actions": [{"type": "set_state", "state": "aware"}], "probability": 1.0},
    ]
    result = run_agent_model(agent_model_from_dict(data))
    assert result.final_agents[1].state == "aware"


def test_m18_scenario_runs_end_to_end():
    path = Path(__file__).resolve().parents[2] / "scenarios" / "spatial_environment_navigation_m18.json"
    model = agent_model_from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert validate_agent_model(model).is_valid
    result = run_agent_model(model)
    assert result.final_agents[0].position == Position(11, 5)
    assert all(event.status in {"moved", "unchanged"} for event in result.movement_events)


def test_schema_rejects_self_intersecting_polygon_and_duplicate_environment_ids():
    bad_polygon = _base_data({
        "width": 12, "height": 10,
        "regions": [{"id": "region", "polygon": [
            {"x": 1, "y": 1}, {"x": 8, "y": 8},
            {"x": 1, "y": 8}, {"x": 8, "y": 1},
        ]}],
    })
    with pytest.raises(ABMModelDataError, match="non-zero area|simple polygon"):
        agent_model_from_dict(bad_polygon)

    duplicate_ids = _base_data({
        "width": 12, "height": 10,
        "regions": [{"id": "shared", "polygon": [
            {"x": 0, "y": 0}, {"x": 2, "y": 0}, {"x": 2, "y": 2},
        ]}],
        "zones": [{"id": "shared", "polygon": [
            {"x": 3, "y": 3}, {"x": 5, "y": 3}, {"x": 5, "y": 5},
        ]}],
    })
    with pytest.raises(ABMModelDataError, match="identifiers must be unique"):
        agent_model_from_dict(duplicate_ids)


def test_direct_movement_is_blocked_when_crossing_an_impassable_zone():
    data = _base_data({
        "width": 12, "height": 10,
        "zones": [{"id": "restricted", "passable": False, "polygon": [
            {"x": 4, "y": 2}, {"x": 6, "y": 2},
            {"x": 6, "y": 8}, {"x": 4, "y": 8},
        ]}],
    })
    result = run_agent_model(agent_model_from_dict(data))
    assert result.final_agents[0].position == Position(2, 5)
    assert result.movement_events[0].status == "blocked"
    assert result.movement_events[0].reason == "zone:restricted"


def test_wrap_world_spatial_index_finds_neighbours_across_the_boundary():
    data = _base_data(
        {"width": 10, "height": 10, "boundary": "wrap", "grid": {"cell_size": 1}},
        agents=[
            {"reference": "left", "agent_type": "observer", "state": "watching", "attributes": {},
             "position": {"x": 0.2, "y": 5}},
            {"reference": "right", "agent_type": "person", "state": "active", "attributes": {},
             "position": {"x": 9.8, "y": 5}},
        ],
    )
    data["behaviours"] = [{
        "rule_id": "notice-wrapped-neighbour", "agent_type": "observer",
        "condition": {"type": "spatial_neighbour_state_count", "radius": 0.5,
                      "state": "active", "operator": "gt", "count": 0},
        "actions": [{"type": "set_state", "state": "aware"}], "probability": 1.0,
    }]
    result = run_agent_model(agent_model_from_dict(data))
    assert result.final_agents[0].state == "aware"
