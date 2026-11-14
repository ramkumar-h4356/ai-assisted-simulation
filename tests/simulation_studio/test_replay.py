from copy import deepcopy
from dataclasses import replace

import pytest

from compilation import compile_profile
from execution import ExperimentConfig, execute_artifact
from execution.serialization import fingerprint_result
from simulation_studio import ReplayError, build_abm_replay
from tests.compilation.helpers import abm_profile
from tests.readiness.helpers import abm_project


def _execution():
    project = abm_project()
    compilation = compile_profile(project, abm_profile(project))
    assert compilation.is_ready
    result = execute_artifact(compilation.artifact, ExperimentConfig(runs=1, base_seed=23))
    return result, compilation.artifact


def test_abm_replay_contains_relationships_frames_and_rule_evaluations():
    result, compilation = _execution()
    replay = build_abm_replay(result, compilation)

    assert replay["agent_count"] == 2
    assert replay["relationship_count"] == 1
    assert replay["total_steps"] == 10
    assert len(replay["frames"]) == 11
    assert replay["agents"][0]["x"] == replay["agents"][1]["x"]
    assert replay["relationships"][0]["relation_type"] == "peer"
    assert replay["display_semantics"]["positions_are_physical"] is False
    assert replay["frames"][1]["rule_evaluations"]
    assert replay["frames"][1]["changed_agents"][0]["agent_id"] == "agent-1"


def test_abm_replay_is_deterministic_for_same_recorded_run():
    result, compilation = _execution()
    first = build_abm_replay(result, compilation)
    second = build_abm_replay(result, compilation)
    assert first == second


def test_abm_replay_rejects_a_mismatched_compilation_artifact():
    result, compilation = _execution()
    project = abm_project()
    other_profile = replace(abm_profile(project), profile_id="different-profile")
    different = compile_profile(project, other_profile).artifact
    with pytest.raises(ReplayError, match="provenance do not match"):
        build_abm_replay(result, different)


def test_abm_replay_rejects_a_missing_run():
    result, compilation = _execution()
    with pytest.raises(ReplayError, match="does not exist"):
        build_abm_replay(result, compilation, run_index=2)


def test_abm_replay_rejects_non_abm_paradigm():
    result, compilation = _execution()
    changed = replace(result, paradigm="discrete_event", result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    with pytest.raises(ReplayError, match="ABM execution results only"):
        build_abm_replay(changed, compilation)


def test_spatial_abm_replay_uses_recorded_physical_coordinates():
    project = abm_project()
    profile = abm_profile(project)
    model_data = deepcopy(profile.model_data)
    model_data["space"] = {"width": 20, "height": 10, "boundary": "clamp"}
    model_data["agents"][0]["position"] = {"x": 2, "y": 3}
    model_data["agents"][1]["position"] = {"x": 18, "y": 7}
    model_data["behaviours"][0]["actions"].append(
        {"type": "move_by", "dx": 3, "dy": -1}
    )
    spatial_profile = replace(profile, model_data=model_data)
    compilation = compile_profile(project, spatial_profile).artifact
    result = execute_artifact(compilation, ExperimentConfig(runs=1, base_seed=23))

    replay = build_abm_replay(result, compilation)

    assert replay["space"] == {"width": 20.0, "height": 10.0, "boundary": "clamp"}
    assert replay["display_semantics"]["positions_are_physical"] is True
    assert replay["display_semantics"]["coordinate_space"] == "model_defined"
    assert replay["display_semantics"]["real_world_units_assumed"] is False
    assert replay["display_semantics"]["movement_is_simulated"] is True
    assert replay["frames"][0]["agents"][0]["position"] == {"x": 2.0, "y": 3.0}
    assert replay["frames"][1]["agents"][0]["position"] == {"x": 5.0, "y": 2.0}
    changed = {item["agent_id"]: item for item in replay["frames"][1]["changed_agents"]}
    assert changed["agent-1"]["position_changed"] is True
