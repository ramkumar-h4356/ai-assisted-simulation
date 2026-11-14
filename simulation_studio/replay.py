"""Validated ABM replay scene construction from M8 and M9 artifacts.

Spatial models use recorded model-space coordinates; non-spatial models
use a deterministic presentation layout which does not alter model semantics.
"""

from __future__ import annotations

import math
from typing import Any

from compilation.compiler import verify_artifact
from compilation.models import CompilationArtifact, CompilationParadigm
from execution.models import ExperimentResult, RunRecord, RunStatus
from execution.serialization import fingerprint_result
from simulations.abm.schema import agent_model_from_dict


class ReplayError(ValueError):
    """Raised when a recorded execution cannot be represented as a valid replay."""


def _layout(agent_ids: list[str]) -> dict[str, dict[str, float]]:
    count = len(agent_ids)
    positions: dict[str, dict[str, float]] = {}
    if count == 1:
        return {agent_ids[0]: {"x": 0.5, "y": 0.5}}
    # A stable circular layout ensures that non-spatial replays are identical.
    radius = 0.39
    for index, agent_id in enumerate(agent_ids):
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        positions[agent_id] = {
            "x": round(0.5 + radius * math.cos(angle), 6),
            "y": round(0.5 + radius * math.sin(angle), 6),
        }
    return positions


def _validate_run(
    run: RunRecord,
    expected_agents: dict[str, str],
    expected_steps: int,
    *,
    spatial_space: dict[str, Any] | None = None,
    expected_radii: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    if run.status is not RunStatus.COMPLETED:
        raise ReplayError(f"Run {run.run_index} did not complete and cannot be replayed")
    history = run.trace.get("history")
    if not isinstance(history, list) or not history:
        raise ReplayError("Selected ABM run does not contain a population history")
    if len(history) > 100_001:
        raise ReplayError("Selected ABM history is too large for interactive replay")
    if len(history) != expected_steps + 1:
        raise ReplayError("Recorded ABM history length does not match the M8 termination horizon")

    expected_ids = set(expected_agents)
    validated: list[dict[str, Any]] = []
    for index, snapshot in enumerate(history):
        if not isinstance(snapshot, dict):
            raise ReplayError(f"History snapshot {index} must be an object")
        step = snapshot.get("step")
        if isinstance(step, bool) or not isinstance(step, int) or step != index:
            raise ReplayError("ABM snapshots must be sequential and begin at step 0")
        agents = snapshot.get("agents")
        if not isinstance(agents, list):
            raise ReplayError(f"History snapshot {index} must contain an agents array")
        rows: dict[str, dict[str, Any]] = {}
        for item in agents:
            if not isinstance(item, dict):
                raise ReplayError(f"History snapshot {index} contains an invalid agent")
            identifier = item.get("id")
            state = item.get("state")
            agent_type = item.get("agent_type")
            attributes = item.get("attributes")
            if not isinstance(identifier, str) or not identifier:
                raise ReplayError(f"History snapshot {index} contains an agent without an ID")
            if identifier in rows:
                raise ReplayError(f"History snapshot {index} contains duplicate agent {identifier!r}")
            if not isinstance(state, str) or not isinstance(agent_type, str) or not isinstance(attributes, dict):
                raise ReplayError(f"Agent {identifier!r} in snapshot {index} has invalid state data")
            if agent_type != expected_agents.get(identifier):
                raise ReplayError(f"Agent {identifier!r} changed agent_type in snapshot {index}")
            if any(not isinstance(key, str) for key in attributes):
                raise ReplayError(f"Agent {identifier!r} has a non-text attribute key in snapshot {index}")
            if any(
                not isinstance(value, (str, int, float, bool, type(None)))
                or (isinstance(value, float) and not math.isfinite(value))
                for value in attributes.values()
            ):
                raise ReplayError(f"Agent {identifier!r} has a non-scalar attribute in snapshot {index}")
            raw_position = item.get("position")
            position = None
            if raw_position is not None:
                if not isinstance(raw_position, dict):
                    raise ReplayError(f"Agent {identifier!r} has an invalid position in snapshot {index}")
                x, y = raw_position.get("x"), raw_position.get("y")
                if (
                    isinstance(x, bool) or not isinstance(x, (int, float))
                    or isinstance(y, bool) or not isinstance(y, (int, float))
                    or not math.isfinite(x) or not math.isfinite(y)
                ):
                    raise ReplayError(f"Agent {identifier!r} has non-finite coordinates in snapshot {index}")
                if spatial_space is not None:
                    width, height = spatial_space["width"], spatial_space["height"]
                    boundary = spatial_space["boundary"]
                    upper_invalid = x > width or y > height if boundary == "clamp" else x >= width or y >= height
                    if x < 0 or y < 0 or upper_invalid:
                        raise ReplayError(f"Agent {identifier!r} leaves the configured spatial space in snapshot {index}")
                position = {"x": float(x), "y": float(y)}
            elif spatial_space is not None:
                raise ReplayError(f"Spatial agent {identifier!r} has no recorded position in snapshot {index}")
            radius = item.get("radius", 0.0)
            if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius < 0:
                raise ReplayError(f"Agent {identifier!r} has an invalid body radius in snapshot {index}")
            if expected_radii is not None and not math.isclose(float(radius), expected_radii[identifier], rel_tol=0.0, abs_tol=1e-10):
                raise ReplayError(f"Agent {identifier!r} changed collision radius in snapshot {index}")
            rows[identifier] = {
                "id": identifier,
                "agent_type": agent_type,
                "state": state,
                "attributes": attributes,
                "position": position,
                "radius": float(radius),
            }
        if set(rows) != expected_ids:
            raise ReplayError(f"Agent population changed unexpectedly in snapshot {index}")
        validated.append({"step": step, "agents": [rows[agent_id] for agent_id in sorted(rows)]})
    return validated


def _rule_evaluations(
    run: RunRecord,
    total_steps: int,
    expected_agent_ids: set[str],
    expected_rule_ids: set[str],
) -> dict[int, list[dict[str, Any]]]:
    raw = run.trace.get("rule_evaluations", [])
    if not isinstance(raw, list):
        raise ReplayError("ABM rule_evaluations must be an array")
    result: dict[int, list[dict[str, Any]]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ReplayError(f"Rule evaluation {index} must be an object")
        step = item.get("step")
        agent_id = item.get("agent_id")
        rule_id = item.get("rule_id")
        if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= total_steps:
            raise ReplayError(f"Rule evaluation {index} has an invalid step")
        if not isinstance(agent_id, str) or agent_id not in expected_agent_ids:
            raise ReplayError(f"Rule evaluation {index} references an unknown agent")
        if not isinstance(rule_id, str) or rule_id not in expected_rule_ids:
            raise ReplayError(f"Rule evaluation {index} references an unknown rule")
        condition_matched = item.get("condition_matched")
        probability_passed = item.get("probability_passed")
        actions_applied = item.get("actions_applied")
        state_before = item.get("state_before")
        state_after = item.get("state_after")
        if not isinstance(condition_matched, bool) or not isinstance(actions_applied, bool):
            raise ReplayError(f"Rule evaluation {index} has invalid outcome flags")
        if probability_passed is not None and not isinstance(probability_passed, bool):
            raise ReplayError(f"Rule evaluation {index} has an invalid probability outcome")
        if not isinstance(state_before, str) or not isinstance(state_after, str):
            raise ReplayError(f"Rule evaluation {index} has invalid state values")
        result.setdefault(step, []).append({
            "agent_id": agent_id,
            "rule_id": rule_id,
            "condition_matched": condition_matched,
            "probability_passed": probability_passed,
            "actions_applied": actions_applied,
            "state_before": state_before,
            "state_after": state_after,
        })
    return result


def _movement_events(
    run: RunRecord,
    total_steps: int,
    expected_agent_ids: set[str],
    expected_rule_ids: set[str],
) -> dict[int, list[dict[str, Any]]]:
    raw = run.trace.get("movement_events", [])
    if not isinstance(raw, list):
        raise ReplayError("ABM movement_events must be an array")
    if len(raw) > 500_000:
        raise ReplayError("ABM movement event trace is too large for interactive replay")
    result: dict[int, list[dict[str, Any]]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ReplayError(f"Movement event {index} must be an object")
        step = item.get("step")
        agent_id = item.get("agent_id")
        rule_id = item.get("rule_id")
        if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= total_steps:
            raise ReplayError(f"Movement event {index} has an invalid step")
        if not isinstance(agent_id, str) or agent_id not in expected_agent_ids:
            raise ReplayError(f"Movement event {index} references an unknown agent")
        if not isinstance(rule_id, str) or rule_id not in expected_rule_ids:
            raise ReplayError(f"Movement event {index} references an unknown rule")
        action_type = item.get("action_type")
        status = item.get("status")
        if not isinstance(action_type, str) or action_type not in {"move_by", "move_to", "move_towards"}:
            raise ReplayError(f"Movement event {index} has an unsupported action type")
        if not isinstance(status, str) or status not in {"moved", "blocked", "slid", "no_path", "unchanged"}:
            raise ReplayError(f"Movement event {index} has an unsupported status")
        def parse_position(value, field_name):
            if not isinstance(value, dict):
                raise ReplayError(f"Movement event {index} has an invalid {field_name}")
            x, y = value.get("x"), value.get("y")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (x, y)):
                raise ReplayError(f"Movement event {index} has invalid coordinates in {field_name}")
            return {"x": float(x), "y": float(y)}
        path = item.get("path", [])
        if not isinstance(path, list) or len(path) > 100_000:
            raise ReplayError(f"Movement event {index} has an invalid path")
        normalized_path = [parse_position(point, "path") for point in path]
        row = {
            "agent_id": agent_id,
            "rule_id": rule_id,
            "action_index": item.get("action_index"),
            "action_type": action_type,
            "requested_target": parse_position(item.get("requested_target"), "requested_target"),
            "actual_position": parse_position(item.get("actual_position"), "actual_position"),
            "status": status,
            "reason": item.get("reason"),
            "path": normalized_path,
            "distance_travelled": item.get("distance_travelled", 0.0),
            "distance_limit_reached": item.get("distance_limit_reached", False),
        }
        if isinstance(row["action_index"], bool) or not isinstance(row["action_index"], int) or row["action_index"] < 0:
            raise ReplayError(f"Movement event {index} has an invalid action index")
        distance = row["distance_travelled"]
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
            raise ReplayError(f"Movement event {index} has an invalid travelled distance")
        if not isinstance(row["distance_limit_reached"], bool):
            raise ReplayError(f"Movement event {index} has an invalid distance-limit flag")
        if row["reason"] is not None and not isinstance(row["reason"], str):
            raise ReplayError(f"Movement event {index} has an invalid reason")
        result.setdefault(step, []).append(row)
    return result


def build_abm_replay(
    result: ExperimentResult,
    compilation: CompilationArtifact,
    *,
    run_index: int = 1,
) -> dict[str, Any]:
    """Build a safe, JSON-ready replay scene from exact matching M8/M9 records."""
    if not isinstance(result, ExperimentResult):
        raise TypeError("result must be an ExperimentResult")
    if not isinstance(compilation, CompilationArtifact):
        raise TypeError("compilation must be a CompilationArtifact")
    if fingerprint_result(result) != result.result_fingerprint:
        raise ReplayError("M9 execution fingerprint verification failed")
    if not verify_artifact(compilation):
        raise ReplayError("M8 compilation artifact fingerprint verification failed")
    if result.paradigm != CompilationParadigm.AGENT_BASED.value:
        raise ReplayError("Interactive 2D replay currently supports ABM execution results only")
    if compilation.paradigm is not CompilationParadigm.AGENT_BASED:
        raise ReplayError("The linked M8 artifact is not an ABM specification")
    if (result.artifact_id, result.artifact_fingerprint, result.project_id, result.revision_id, result.revision_version) != (
        compilation.artifact_id,
        compilation.artifact_fingerprint,
        compilation.project_id,
        compilation.revision_id,
        compilation.revision_version,
    ):
        raise ReplayError("M9 result and M8 compilation provenance do not match")
    if isinstance(run_index, bool) or not isinstance(run_index, int) or run_index < 1:
        raise ReplayError("run_index must be a positive integer")
    run = next((item for item in result.runs if item.run_index == run_index), None)
    if run is None:
        raise ReplayError(f"Run {run_index} does not exist in this execution result")

    try:
        model = agent_model_from_dict(compilation.model_data)
    except Exception as error:
        raise ReplayError(f"Linked M8 ABM model is invalid: {error}") from error
    expected_agents = {agent.identifier: agent.agent_type for agent in model.agents}
    expected_ids = set(expected_agents)
    if len(expected_ids) != len(model.agents):
        raise ReplayError("Linked M8 ABM model contains duplicate agent identifiers")

    expected_steps = model.termination.value
    space_data = None
    if model.space is not None:
        space_data = {
            "width": model.space.width,
            "height": model.space.height,
            "boundary": model.space.boundary.value,
        }
        if model.space.obstacles:
            space_data["obstacles"] = [
                (
                    {"id": item.identifier, "type": "rectangle", "x": item.x, "y": item.y,
                     "width": item.width, "height": item.height}
                    if hasattr(item, "width")
                    else {"id": item.identifier, "type": "circle", "x": item.x, "y": item.y,
                          "radius": item.radius}
                )
                for item in model.space.obstacles
            ]
        if not model.space.agent_collisions:
            space_data["agent_collisions"] = False
        if model.space.collision_resolution.value != "block":
            space_data["collision_resolution"] = model.space.collision_resolution.value
    expected_radii = {agent.identifier: agent.radius for agent in model.agents}
    snapshots = _validate_run(
        run, expected_agents, expected_steps, spatial_space=space_data,
        expected_radii=expected_radii,
    )
    model_agents = {agent.identifier: agent for agent in model.agents}
    for row in snapshots[0]["agents"]:
        initial = model_agents[row["id"]]
        expected_position = (
            None
            if initial.position is None
            else {"x": initial.position.x, "y": initial.position.y}
        )
        if row["state"] != initial.state or row["attributes"] != dict(initial.attributes):
            raise ReplayError(f"Initial M9 state for agent {row['id']!r} does not match the linked M8 model")
        if row.get("position") != expected_position:
            raise ReplayError(f"Initial M9 position for agent {row['id']!r} does not match the linked M8 model")
    if model.space is None:
        positions = _layout(sorted(expected_ids))
    else:
        positions = {
            agent.identifier: {
                "x": round(agent.position.x / model.space.width, 6),
                "y": round(agent.position.y / model.space.height, 6),
            }
            for agent in model.agents
        }
    agents = [
        {
            "id": agent.identifier,
            "agent_type": agent.agent_type,
            "radius": agent.radius,
            "x": positions[agent.identifier]["x"],
            "y": positions[agent.identifier]["y"],
        }
        for agent in sorted(model.agents, key=lambda value: value.identifier)
    ]
    edges = [
        {
            "source": edge.source_agent_id,
            "target": edge.target_agent_id,
            "relation_type": edge.relation_type,
            "directed": edge.directed,
        }
        for edge in model.relationships
    ]

    expected_rule_ids = {rule.rule_id for rule in model.behaviours}
    evaluations = _rule_evaluations(run, len(snapshots) - 1, expected_ids, expected_rule_ids)
    movement_events = _movement_events(run, len(snapshots) - 1, expected_ids, expected_rule_ids)
    # The last movement action for an agent in a step must agree with the
    # final recorded position for that step. This catches internally
    # inconsistent trace data before it reaches the browser.
    for step, events in movement_events.items():
        last_by_agent: dict[str, dict[str, Any]] = {}
        for event in events:
            last_by_agent[event["agent_id"]] = event
        snapshot_rows = {row["id"]: row for row in snapshots[step]["agents"]}
        for agent_id, event in last_by_agent.items():
            recorded = snapshot_rows[agent_id].get("position")
            actual = event["actual_position"]
            if recorded is not None and space_data is not None and space_data.get("boundary") == "clamp":
                if not math.isclose(recorded["x"], actual["x"], rel_tol=0.0, abs_tol=1e-9) or not math.isclose(recorded["y"], actual["y"], rel_tol=0.0, abs_tol=1e-9):
                    raise ReplayError(f"Movement event for agent {agent_id!r} does not match its recorded step position")
    frames: list[dict[str, Any]] = []
    previous: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        rows = snapshot["agents"]
        changed: list[dict[str, Any]] = []
        state_counts: dict[str, int] = {}
        for row in rows:
            state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
            prior = previous.get(row["id"])
            if prior is not None:
                changed_attributes = sorted(
                    key for key in set(prior["attributes"]) | set(row["attributes"])
                    if prior["attributes"].get(key) != row["attributes"].get(key)
                )
                position_changed = prior.get("position") != row.get("position")
                if prior["state"] != row["state"] or changed_attributes or position_changed:
                    changed.append({
                        "agent_id": row["id"],
                        "state_changed": prior["state"] != row["state"],
                        "state_before": prior["state"],
                        "state_after": row["state"],
                        "changed_attributes": changed_attributes,
                        "position_changed": position_changed,
                    })
            previous[row["id"]] = row
        frames.append({
            "step": snapshot["step"],
            "agents": rows,
            "state_counts": dict(sorted(state_counts.items())),
            "changed_agents": changed,
            "rule_evaluations": evaluations.get(snapshot["step"], []),
            "movement_events": movement_events.get(snapshot["step"], []),
        })

    return {
        "schema_version": 1,
        "experiment_id": result.experiment_id,
        "execution_artifact_id": result.artifact_id,
        "execution_fingerprint": result.result_fingerprint,
        "compilation_artifact_id": compilation.artifact_id,
        "project_id": result.project_id,
        "revision_id": result.revision_id,
        "model_name": model.name,
        "run_index": run.run_index,
        "seed": run.seed,
        "total_steps": len(frames) - 1,
        "agent_count": len(agents),
        "relationship_count": len(edges),
        "agents": agents,
        "relationships": edges,
        "space": space_data,
        "frames": frames,
        "display_semantics": {
            "layout": "model_space" if model.space is not None else "deterministic_circle",
            "positions_are_physical": model.space is not None,
            "coordinate_space": "model_defined" if model.space is not None else "display_only",
            "real_world_units_assumed": False,
            "movement_is_simulated": model.space is not None,
            "explanation": (
                "Agent coordinates and movement are part of the ABM model and were recorded at every step."
                if model.space is not None
                else "Agent positions are a deterministic 2D layout for readability. This model does not define physical coordinates or movement."
            ),
        },
    }
