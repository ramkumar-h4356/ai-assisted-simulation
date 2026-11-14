import json
from pathlib import Path

from simulations.abm.engine import run_agent_model
from simulations.abm.model import Position
from simulations.abm.schema import agent_model_from_dict
from simulations.abm.validation import validate_agent_model


def test_obstacle_navigation_scenario_reaches_destination_with_recorded_path():
    path = Path(__file__).resolve().parents[2] / "scenarios" / "spatial_obstacles_pathfinding_abm.json"
    model = agent_model_from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert validate_agent_model(model).is_valid

    result = run_agent_model(model)

    assert result.final_agents[0].position == Position(18, 10)
    assert len(result.history) == 13
    assert len(result.movement_events) == 12
    assert all(event.status == "moved" for event in result.movement_events)
    assert any(len(event.path) > 2 for event in result.movement_events)
