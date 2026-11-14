import pytest

from simulations.abm.engine import run_agent_model
from simulations.abm.model import (
    BoundaryMode, ComparisonOperator, MoveBy, MoveTo, Position,
    SpatialNeighbourStateCount, SpatialSpace,
)
from simulations.abm.schema import ABMModelDataError, agent_model_from_dict
from simulations.abm.validation import validate_agent_model


def _model_data(*, boundary="clamp", positions=None, behaviours=None):
    positions = positions or [{"x": 1, "y": 1}, {"x": 8, "y": 8}]
    return {
        "name": "Spatial test",
        "space": {"width": 10, "height": 10, "boundary": boundary},
        "agents": [
            {"reference": "a", "agent_type": "person", "state": "active", "attributes": {}, "position": positions[0]},
            {"reference": "b", "agent_type": "person", "state": "susceptible", "attributes": {}, "position": positions[1]},
        ],
        "environment": {"attributes": {}},
        "relationships": [],
        "behaviours": behaviours or [],
        "activation": {"mode": "sequential", "order": "declaration"},
        "termination": {"type": "max_steps", "value": 1},
        "random_seed": 13,
    }


def test_spatial_schema_parses_space_positions_neighbour_condition_and_movement():
    data = _model_data(behaviours=[
        {
            "rule_id": "move",
            "agent_type": "person",
            "condition": {"type": "agent_state_is", "state": "active"},
            "actions": [{"type": "move_by", "dx": 1.5, "dy": -0.5}],
            "probability": 1.0,
        },
        {
            "rule_id": "nearby",
            "agent_type": "person",
            "condition": {
                "type": "spatial_neighbour_state_count",
                "radius": 2,
                "state": "active",
                "operator": "gt",
                "count": 0,
            },
            "actions": [{"type": "set_state", "state": "aware"}],
            "probability": 1.0,
        },
    ])
    model = agent_model_from_dict(data)
    assert model.space == SpatialSpace(10, 10, BoundaryMode.CLAMP)
    assert model.agents[0].position == Position(1, 1)
    assert model.behaviours[1].condition == SpatialNeighbourStateCount(
        2, "active", ComparisonOperator.GREATER_THAN, 0
    )
    assert isinstance(model.behaviours[0].actions[0], MoveBy)


def test_move_by_clamps_to_closed_world_bounds_and_records_trajectory():
    data = _model_data(
        positions=[{"x": 9, "y": 9}, {"x": 8, "y": 8}],
        behaviours=[{
            "rule_id": "move-outward",
            "agent_type": "person",
            "condition": {"type": "agent_state_is", "state": "active"},
            "actions": [{"type": "move_by", "dx": 5, "dy": 4}],
            "probability": 1.0,
        }],
    )
    result = run_agent_model(agent_model_from_dict(data))
    assert result.history[0].agent("agent-1").position == Position(9, 9)
    assert result.history[1].agent("agent-1").position == Position(10, 10)
    assert result.trajectory("agent-1")[-1].position == Position(10, 10)


def test_move_to_wraps_across_opposite_world_edges():
    data = _model_data(
        boundary="wrap",
        positions=[{"x": 9.5, "y": 1}, {"x": 4, "y": 4}],
        behaviours=[{
            "rule_id": "move-across-edge",
            "agent_type": "person",
            "condition": {"type": "agent_state_is", "state": "active"},
            "actions": [{"type": "move_to", "x": 12.5, "y": -2}],
            "probability": 1.0,
        }],
    )
    model = agent_model_from_dict(data)
    assert isinstance(model.behaviours[0].actions[0], MoveTo)
    result = run_agent_model(model)
    assert result.history[1].agent("agent-1").position == Position(2.5, 8)


def test_later_agent_sees_earlier_agents_committed_movement_for_neighbourhood():
    data = _model_data(
        positions=[{"x": 0, "y": 0}, {"x": 6, "y": 5}],
        behaviours=[
            {
                "rule_id": "move-first-agent",
                "agent_type": "mover",
                "condition": {"type": "agent_state_is", "state": "active"},
                "actions": [{"type": "move_to", "x": 5, "y": 5}],
                "probability": 1.0,
            },
            {
                "rule_id": "notice-neighbour",
                "agent_type": "observer",
                "condition": {
                    "type": "spatial_neighbour_state_count",
                    "radius": 2,
                    "state": "active",
                    "operator": "gt",
                    "count": 0,
                },
                "actions": [{"type": "set_state", "state": "aware"}],
                "probability": 1.0,
            },
        ],
    )
    data["agents"][0]["agent_type"] = "mover"
    data["agents"][1]["agent_type"] = "observer"
    result = run_agent_model(agent_model_from_dict(data))
    assert result.history[1].agent("agent-1").position == Position(5, 5)
    assert result.history[1].agent("agent-2").state == "aware"


def test_wrapped_neighbourhood_uses_shortest_distance_across_edges():
    data = _model_data(
        boundary="wrap",
        positions=[{"x": 0.2, "y": 5}, {"x": 9.8, "y": 5}],
        behaviours=[{
            "rule_id": "detect-nearby-infected",
            "agent_type": "person",
            "condition": {
                "type": "spatial_neighbour_state_count",
                "radius": 0.5,
                "state": "infected",
                "operator": "gt",
                "count": 0,
            },
            "actions": [{"type": "set_state", "state": "infected"}],
            "probability": 1.0,
        }],
    )
    data["agents"][1]["state"] = "infected"
    result = run_agent_model(agent_model_from_dict(data))
    assert result.history[1].agent("agent-1").state == "infected"


def test_schema_rejects_spatial_model_with_missing_agent_position():
    data = _model_data()
    data["agents"][1].pop("position")
    with pytest.raises(ValueError, match="initial position"):
        # A position is not syntactically required by the parser; semantic
        # validation catches the missing position after construction.
        model = agent_model_from_dict(data)
        report = validate_agent_model(model)
        report.raise_for_errors()


def test_non_spatial_model_cannot_use_movement_action():
    data = _model_data(behaviours=[{
        "rule_id": "invalid-move",
        "agent_type": "person",
        "condition": {"type": "agent_state_is", "state": "active"},
        "actions": [{"type": "move_by", "dx": 1, "dy": 0}],
        "probability": 1.0,
    }])
    data.pop("space")
    for agent in data["agents"]:
        agent.pop("position")
    model = agent_model_from_dict(data)
    codes = {issue.code for issue in validate_agent_model(model).errors}
    assert "MOVEMENT_WITHOUT_SPACE" in codes


def test_spatial_space_rejects_out_of_bounds_initial_position():
    data = _model_data(positions=[{"x": 10.1, "y": 2}, {"x": 2, "y": 2}])
    model = agent_model_from_dict(data)
    codes = {issue.code for issue in validate_agent_model(model).errors}
    assert "POSITION_OUT_OF_BOUNDS" in codes


def test_spatial_neighbour_condition_requires_a_spatial_world():
    data = _model_data(behaviours=[{
        "rule_id": "detect",
        "agent_type": "person",
        "condition": {
            "type": "spatial_neighbour_state_count",
            "radius": 1,
            "state": "infected",
            "operator": "gt",
            "count": 0,
        },
        "actions": [{"type": "set_state", "state": "infected"}],
        "probability": 1.0,
    }])
    data.pop("space")
    for agent in data["agents"]:
        agent.pop("position")
    model = agent_model_from_dict(data)
    codes = {issue.code for issue in validate_agent_model(model).errors}
    assert "SPATIAL_CONDITION_WITHOUT_SPACE" in codes


def test_move_action_batch_does_not_commit_position_after_later_action_fails():
    from simulations.abm.engine import AgentBasedSimulationEngine, SimulationExecutionError, _RuntimeAgent
    from simulations.abm.model import BehaviourRule, AgentStateIs, IncrementAttribute

    runtime = _RuntimeAgent("a", "person", "active", {"score": "invalid"}, Position(2, 3))
    rule = BehaviourRule(
        "atomic-move",
        AgentStateIs("active"),
        (MoveBy(4, 0), IncrementAttribute("score", 1)),
    )
    with pytest.raises(SimulationExecutionError):
        AgentBasedSimulationEngine()._apply_actions(runtime, rule, step=1, space=SpatialSpace(10, 10))
    assert runtime.position == Position(2, 3)
    assert runtime.attributes["score"] == "invalid"


def test_wrapped_initial_coordinate_at_world_width_is_invalid():
    data = _model_data(
        boundary="wrap",
        positions=[{"x": 10, "y": 2}, {"x": 2, "y": 2}],
    )
    model = agent_model_from_dict(data)
    codes = {issue.code for issue in validate_agent_model(model).errors}
    assert "POSITION_OUT_OF_BOUNDS" in codes


def test_included_spatial_scenario_executes_with_expected_neighbour_response():
    import json
    from pathlib import Path
    from simulations.abm.engine import run_agent_model

    scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "spatial_neighbour_movement_abm.json"
    model = agent_model_from_dict(json.loads(scenario_path.read_text(encoding="utf-8")))
    result = run_agent_model(model)
    assert result.history[1].agent("agent-1").position == Position(12, 50)
    assert result.history[1].agent("agent-2").state == "aware"
    assert result.history[1].agent("agent-3").state == "unaware"
    assert result.final_agents[0].position == Position(20, 50)
