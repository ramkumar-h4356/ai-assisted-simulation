"""Strict conversion from AI-generated ABM JSON data into executable models.

The language model is restricted to this declarative schema. It cannot provide
Python source, callbacks, or arbitrary expressions for agent behaviour.
"""

from __future__ import annotations

from typing import Any

from simulations.abm.model import (
    ActivationMode,
    ActivationOrder,
    ActivationPolicy,
    Agent,
    AgentAttributeComparison,
    AgentModel,
    AgentRelationship,
    AgentStateIs,
    AllOf,
    AnyOf,
    BoundaryMode,
    BehaviourRule,
    CircleObstacle,
    CollisionResolution,
    ComparisonOperator,
    Environment,
    EnvironmentalObject,
    GridSpec,
    IncrementAttribute,
    MaxSteps,
    MoveBy,
    MoveTo,
    MoveTowards,
    PathfindingAlgorithm,
    Position,
    RectangleObstacle,
    RelatedAgentStateCount,
    SetAttribute,
    SetState,
    SpatialNeighbourStateCount,
    SpatialRegion,
    SpatialSpace,
    SpatialZone,
)


class ABMModelDataError(ValueError):
    """A schema error with a user-facing field path."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ABMModelDataError(path, "Expected a JSON object.")
    return value


def _check_keys(data: dict[str, Any], allowed: set[str], path: str) -> None:
    unexpected = set(data) - allowed
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ABMModelDataError(path, f"Unsupported field(s): {names}.")


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ABMModelDataError(path, "Expected a JSON array.")
    return value


def _required_text(data: dict[str, Any], key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ABMModelDataError(f"{path}.{key}", "A non-empty value is required.")
    return value.strip()


def _parse_operator(value: Any, path: str) -> ComparisonOperator:
    try:
        return ComparisonOperator(value)
    except (TypeError, ValueError) as error:
        supported = ", ".join(item.value for item in ComparisonOperator)
        raise ABMModelDataError(path, f"Use one of these comparison operators: {supported}.") from error


def _parse_condition(value: Any, path: str):
    data = _object(value, path)
    condition_type = data.get("type")

    if condition_type == "agent_state_is":
        _check_keys(data, {"type", "state"}, path)
        return AgentStateIs(_required_text(data, "state", path))

    if condition_type == "agent_attribute_comparison":
        _check_keys(data, {"type", "attribute", "operator", "value"}, path)
        attribute = _required_text(data, "attribute", path)
        operator = _parse_operator(data.get("operator"), f"{path}.operator")
        if "value" not in data or data["value"] is None:
            raise ABMModelDataError(f"{path}.value", "A comparison value is required.")
        try:
            return AgentAttributeComparison(attribute, operator, data["value"])
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(f"{path}.value", str(error)) from error

    if condition_type == "related_agent_state_count":
        _check_keys(data, {"type", "relation_type", "state", "operator", "count"}, path)
        relation_type = _required_text(data, "relation_type", path)
        state = _required_text(data, "state", path)
        operator = _parse_operator(data.get("operator"), f"{path}.operator")
        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ABMModelDataError(f"{path}.count", "Count must be a non-negative integer.")
        return RelatedAgentStateCount(relation_type, state, operator, count)

    if condition_type == "spatial_neighbour_state_count":
        _check_keys(data, {"type", "radius", "state", "operator", "count"}, path)
        radius = data.get("radius")
        if isinstance(radius, bool) or not isinstance(radius, (int, float)):
            raise ABMModelDataError(f"{path}.radius", "Radius must be a finite non-negative number.")
        state = _required_text(data, "state", path)
        operator = _parse_operator(data.get("operator"), f"{path}.operator")
        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ABMModelDataError(f"{path}.count", "Count must be a non-negative integer.")
        try:
            return SpatialNeighbourStateCount(radius, state, operator, count)
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    if condition_type in {"all_of", "any_of"}:
        _check_keys(data, {"type", "conditions"}, path)
        children = _array(data.get("conditions"), f"{path}.conditions")
        if not children:
            raise ABMModelDataError(f"{path}.conditions", "At least one nested condition is required.")
        parsed = tuple(
            _parse_condition(child, f"{path}.conditions[{index}]")
            for index, child in enumerate(children)
        )
        return AllOf(parsed) if condition_type == "all_of" else AnyOf(parsed)

    raise ABMModelDataError(
        f"{path}.type",
        "Unsupported condition type. Use agent_state_is, agent_attribute_comparison, "
        "related_agent_state_count, spatial_neighbour_state_count, all_of, or any_of.",
    )


def _parse_action(value: Any, path: str):
    data = _object(value, path)
    action_type = data.get("type")

    if action_type == "set_state":
        _check_keys(data, {"type", "state"}, path)
        return SetState(_required_text(data, "state", path))

    if action_type == "set_attribute":
        _check_keys(data, {"type", "attribute", "value"}, path)
        attribute = _required_text(data, "attribute", path)
        if "value" not in data:
            raise ABMModelDataError(f"{path}.value", "An attribute value is required.")
        try:
            return SetAttribute(attribute, data["value"])
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(f"{path}.value", str(error)) from error

    if action_type == "increment_attribute":
        _check_keys(data, {"type", "attribute", "amount"}, path)
        attribute = _required_text(data, "attribute", path)
        amount = data.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ABMModelDataError(f"{path}.amount", "Increment amount must be numeric.")
        try:
            return IncrementAttribute(attribute, amount)
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(f"{path}.amount", str(error)) from error

    if action_type == "move_by":
        _check_keys(data, {"type", "dx", "dy"}, path)
        dx, dy = data.get("dx"), data.get("dy")
        try:
            return MoveBy(dx, dy)
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    if action_type == "move_to":
        _check_keys(data, {"type", "x", "y"}, path)
        x, y = data.get("x"), data.get("y")
        try:
            return MoveTo(x, y)
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    if action_type == "move_towards":
        _check_keys(data, {"type", "x", "y", "max_distance", "pathfinding", "grid_cell_size"}, path)
        try:
            return MoveTowards(
                data.get("x"), data.get("y"), data.get("max_distance"),
                PathfindingAlgorithm(data.get("pathfinding", "astar")),
                data.get("grid_cell_size", 1.0),
            )
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    raise ABMModelDataError(
        f"{path}.type",
        "Unsupported action type. Use set_state, set_attribute, increment_attribute, move_by, or move_to.",
    )


def normalize_agent_model_data(data: dict[str, Any]) -> dict[str, Any]:
    """Fill metadata-only and structurally optional fields, never model facts.

    Agent references and rule IDs are internal aliases generated by Python;
    the AI is not asked to invent final execution identifiers.
    """
    if not isinstance(data, dict):
        raise ABMModelDataError("model", "AI output must be a JSON object.")

    normalized = dict(data)
    normalized.setdefault("name", "Agent-Based Simulation")
    normalized.setdefault("environment", {})
    normalized.setdefault("activation", {"mode": "sequential", "order": "declaration"})
    normalized.setdefault("random_seed", None)

    agents = normalized.get("agents")
    if isinstance(agents, list):
        updated_agents = []
        for index, item in enumerate(agents, start=1):
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("reference", f"agent_ref_{index}")
                item.setdefault("attributes", {})
            updated_agents.append(item)
        normalized["agents"] = updated_agents

    behaviours = normalized.get("behaviours")
    if isinstance(behaviours, list):
        updated_rules = []
        for index, item in enumerate(behaviours, start=1):
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("rule_id", f"rule_{index}")
            updated_rules.append(item)
        normalized["behaviours"] = updated_rules

    return normalized


def agent_model_from_dict(data: dict[str, Any]) -> AgentModel:
    """Compile a complete, normalized JSON object into an ``AgentModel``."""
    data = normalize_agent_model_data(data)
    _check_keys(
        data,
        {"name", "agents", "environment", "relationships", "behaviours", "activation", "termination", "random_seed", "space"},
        "model",
    )
    name = _required_text(data, "name", "model")
    for required_collection in ("agents", "relationships", "behaviours"):
        if required_collection not in data:
            raise ABMModelDataError(required_collection, "The AI must explicitly provide this collection (use [] only when it is known to be empty).")

    raw_agents = _array(data.get("agents"), "agents")
    if not raw_agents:
        raise ABMModelDataError("agents", "At least one agent is required.")

    agents: list[Agent] = []
    references: dict[str, str] = {}
    for index, raw in enumerate(raw_agents):
        path = f"agents[{index}]"
        item = _object(raw, path)
        _check_keys(item, {"reference", "agent_type", "state", "attributes", "position", "radius", "max_step_distance"}, path)
        reference = _required_text(item, "reference", path)
        if reference in references:
            raise ABMModelDataError(f"{path}.reference", f"Duplicate agent reference {reference!r}.")
        agent_type = _required_text(item, "agent_type", path)
        state = _required_text(item, "state", path)
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ABMModelDataError(f"{path}.attributes", "Attributes must be a JSON object.")
        position = None
        if item.get("position") is not None:
            raw_position = _object(item.get("position"), f"{path}.position")
            _check_keys(raw_position, {"x", "y"}, f"{path}.position")
            if "x" not in raw_position or "y" not in raw_position:
                raise ABMModelDataError(f"{path}.position", "Both x and y coordinates are required.")
            try:
                position = Position(raw_position["x"], raw_position["y"])
            except (TypeError, ValueError) as error:
                raise ABMModelDataError(f"{path}.position", str(error)) from error
        identifier = f"agent-{index + 1}"
        references[reference] = identifier
        try:
            agents.append(Agent(
                identifier, agent_type, state, attributes, position,
                item.get("radius", 0.0), item.get("max_step_distance"),
            ))
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    raw_environment = _object(data.get("environment", {}), "environment")
    _check_keys(raw_environment, {"attributes"}, "environment")
    environment_attributes = raw_environment.get("attributes", {})
    if not isinstance(environment_attributes, dict):
        raise ABMModelDataError("environment.attributes", "Environment attributes must be an object.")
    try:
        environment = Environment(environment_attributes)
    except (TypeError, ValueError) as error:
        raise ABMModelDataError("environment.attributes", str(error)) from error

    raw_relationships = _array(data.get("relationships", []), "relationships")
    relationships: list[AgentRelationship] = []
    for index, raw in enumerate(raw_relationships):
        path = f"relationships[{index}]"
        item = _object(raw, path)
        _check_keys(item, {"source", "target", "relation_type", "directed"}, path)
        source = _required_text(item, "source", path)
        target = _required_text(item, "target", path)
        if source not in references:
            raise ABMModelDataError(f"{path}.source", f"Unknown agent reference {source!r}.")
        if target not in references:
            raise ABMModelDataError(f"{path}.target", f"Unknown agent reference {target!r}.")
        relation_type = _required_text(item, "relation_type", path)
        if "directed" not in item:
            raise ABMModelDataError(f"{path}.directed", "Specify whether this relationship is directed.")
        directed = item.get("directed")
        if not isinstance(directed, bool):
            raise ABMModelDataError(f"{path}.directed", "Directed must be true or false.")
        relationships.append(
            AgentRelationship(references[source], references[target], relation_type, directed)
        )

    raw_behaviours = _array(data.get("behaviours", []), "behaviours")
    behaviours: list[BehaviourRule] = []
    for index, raw in enumerate(raw_behaviours):
        path = f"behaviours[{index}]"
        item = _object(raw, path)
        _check_keys(item, {"rule_id", "agent_type", "condition", "actions", "probability"}, path)
        rule_id = _required_text(item, "rule_id", path)
        raw_condition = item.get("condition")
        condition = _parse_condition(raw_condition, f"{path}.condition")
        raw_actions = _array(item.get("actions"), f"{path}.actions")
        if not raw_actions:
            raise ABMModelDataError(f"{path}.actions", "At least one action is required.")
        actions = tuple(
            _parse_action(action, f"{path}.actions[{action_index}]")
            for action_index, action in enumerate(raw_actions)
        )
        agent_type = item.get("agent_type")
        if agent_type is not None and (not isinstance(agent_type, str) or not agent_type.strip()):
            raise ABMModelDataError(f"{path}.agent_type", "Agent type filter must be a non-empty string or null.")
        probability = item.get("probability")
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            raise ABMModelDataError(f"{path}.probability", "Probability must be numeric between 0 and 1.")
        try:
            behaviours.append(
                BehaviourRule(rule_id, condition, actions, agent_type, float(probability))
            )
        except (TypeError, ValueError) as error:
            raise ABMModelDataError(path, str(error)) from error

    raw_activation = _object(data.get("activation", {}), "activation")
    _check_keys(raw_activation, {"mode", "order"}, "activation")
    try:
        activation = ActivationPolicy(
            mode=ActivationMode(raw_activation.get("mode", "sequential")),
            order=ActivationOrder(raw_activation.get("order", "declaration")),
        )
    except (TypeError, ValueError) as error:
        raise ABMModelDataError("activation", "V1 supports sequential activation in declaration order only.") from error

    raw_termination = _object(data.get("termination"), "termination")
    _check_keys(raw_termination, {"type", "value"}, "termination")
    if raw_termination.get("type") != "max_steps":
        raise ABMModelDataError("termination.type", "V1 supports max_steps termination only.")
    max_steps = raw_termination.get("value")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
        raise ABMModelDataError("termination.value", "Maximum steps must be a positive integer.")

    random_seed = data.get("random_seed")
    if random_seed is not None and (
        isinstance(random_seed, bool) or not isinstance(random_seed, int) or random_seed < 0
    ):
        raise ABMModelDataError("random_seed", "Random seed must be a non-negative integer or null.")

    raw_space = data.get("space")
    space = None
    if raw_space is not None:
        raw_space = _object(raw_space, "space")
        _check_keys(
            raw_space,
            {"width", "height", "boundary", "obstacles", "agent_collisions", "collision_resolution",
             "grid", "regions", "zones", "objects"},
            "space",
        )
        if "width" not in raw_space or "height" not in raw_space:
            raise ABMModelDataError("space", "Both width and height are required.")
        try:
            boundary = BoundaryMode(raw_space.get("boundary", "clamp"))
            collision_resolution = CollisionResolution(raw_space.get("collision_resolution", "block"))
            raw_obstacles = _array(raw_space.get("obstacles", []), "space.obstacles")
            obstacles = []
            for obstacle_index, raw_obstacle in enumerate(raw_obstacles):
                obstacle_path = f"space.obstacles[{obstacle_index}]"
                obstacle = _object(raw_obstacle, obstacle_path)
                obstacle_type = obstacle.get("type")
                if obstacle_type == "rectangle":
                    _check_keys(obstacle, {"id", "type", "x", "y", "width", "height"}, obstacle_path)
                    obstacles.append(RectangleObstacle(
                        _required_text(obstacle, "id", obstacle_path),
                        obstacle.get("x"), obstacle.get("y"),
                        obstacle.get("width"), obstacle.get("height"),
                    ))
                elif obstacle_type == "circle":
                    _check_keys(obstacle, {"id", "type", "x", "y", "radius"}, obstacle_path)
                    obstacles.append(CircleObstacle(
                        _required_text(obstacle, "id", obstacle_path),
                        obstacle.get("x"), obstacle.get("y"), obstacle.get("radius"),
                    ))
                else:
                    raise ABMModelDataError(
                        f"{obstacle_path}.type", "Obstacle type must be rectangle or circle."
                    )
            agent_collisions = raw_space.get("agent_collisions", True)
            if not isinstance(agent_collisions, bool):
                raise ABMModelDataError("space.agent_collisions", "agent_collisions must be true or false.")

            grid = None
            if raw_space.get("grid") is not None:
                raw_grid = _object(raw_space["grid"], "space.grid")
                _check_keys(raw_grid, {"cell_size"}, "space.grid")
                if "cell_size" not in raw_grid:
                    raise ABMModelDataError("space.grid.cell_size", "A grid cell_size is required.")
                try:
                    grid = GridSpec(raw_grid["cell_size"])
                except (TypeError, ValueError) as error:
                    raise ABMModelDataError("space.grid", str(error)) from error

            def parse_polygon(raw_polygon: Any, polygon_path: str) -> tuple[Position, ...]:
                points = _array(raw_polygon, polygon_path)
                parsed: list[Position] = []
                for point_index, raw_point in enumerate(points):
                    point_path = f"{polygon_path}[{point_index}]"
                    point_data = _object(raw_point, point_path)
                    _check_keys(point_data, {"x", "y"}, point_path)
                    if "x" not in point_data or "y" not in point_data:
                        raise ABMModelDataError(point_path, "Both x and y coordinates are required.")
                    try:
                        parsed.append(Position(point_data["x"], point_data["y"]))
                    except (TypeError, ValueError) as error:
                        raise ABMModelDataError(point_path, str(error)) from error
                return tuple(parsed)

            def parse_tags(raw_tags: Any, tags_path: str) -> tuple[str, ...]:
                if raw_tags is None:
                    return ()
                tags = _array(raw_tags, tags_path)
                if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                    raise ABMModelDataError(tags_path, "Tags must be non-empty strings.")
                return tuple(tag.strip() for tag in tags)

            regions: list[SpatialRegion] = []
            for region_index, raw_region in enumerate(_array(raw_space.get("regions", []), "space.regions")):
                region_path = f"space.regions[{region_index}]"
                region_data = _object(raw_region, region_path)
                _check_keys(region_data, {"id", "polygon", "attributes", "tags"}, region_path)
                region_id = _required_text(region_data, "id", region_path)
                attributes = region_data.get("attributes", {})
                if not isinstance(attributes, dict):
                    raise ABMModelDataError(f"{region_path}.attributes", "Attributes must be a JSON object.")
                try:
                    regions.append(SpatialRegion(
                        region_id, parse_polygon(region_data.get("polygon"), f"{region_path}.polygon"),
                        attributes, parse_tags(region_data.get("tags", []), f"{region_path}.tags"),
                    ))
                except (TypeError, ValueError) as error:
                    raise ABMModelDataError(region_path, str(error)) from error

            zones: list[SpatialZone] = []
            for zone_index, raw_zone in enumerate(_array(raw_space.get("zones", []), "space.zones")):
                zone_path = f"space.zones[{zone_index}]"
                zone_data = _object(raw_zone, zone_path)
                _check_keys(zone_data, {"id", "polygon", "passable", "navigation_cost", "tags"}, zone_path)
                zone_id = _required_text(zone_data, "id", zone_path)
                passable = zone_data.get("passable", True)
                if not isinstance(passable, bool):
                    raise ABMModelDataError(f"{zone_path}.passable", "Passable must be true or false.")
                try:
                    zones.append(SpatialZone(
                        zone_id, parse_polygon(zone_data.get("polygon"), f"{zone_path}.polygon"),
                        passable, zone_data.get("navigation_cost", 1.0),
                        parse_tags(zone_data.get("tags", []), f"{zone_path}.tags"),
                    ))
                except (TypeError, ValueError) as error:
                    raise ABMModelDataError(zone_path, str(error)) from error

            objects: list[EnvironmentalObject] = []
            for object_index, raw_object in enumerate(_array(raw_space.get("objects", []), "space.objects")):
                object_path = f"space.objects[{object_index}]"
                object_data = _object(raw_object, object_path)
                _check_keys(object_data, {"id", "position", "radius", "blocks_movement", "attributes", "tags"}, object_path)
                object_id = _required_text(object_data, "id", object_path)
                raw_position = _object(object_data.get("position"), f"{object_path}.position")
                _check_keys(raw_position, {"x", "y"}, f"{object_path}.position")
                if "x" not in raw_position or "y" not in raw_position:
                    raise ABMModelDataError(f"{object_path}.position", "Both x and y coordinates are required.")
                try:
                    object_position = Position(raw_position["x"], raw_position["y"])
                except (TypeError, ValueError) as error:
                    raise ABMModelDataError(f"{object_path}.position", str(error)) from error
                attributes = object_data.get("attributes", {})
                if not isinstance(attributes, dict):
                    raise ABMModelDataError(f"{object_path}.attributes", "Attributes must be a JSON object.")
                blocks_movement = object_data.get("blocks_movement", False)
                if not isinstance(blocks_movement, bool):
                    raise ABMModelDataError(f"{object_path}.blocks_movement", "blocks_movement must be true or false.")
                try:
                    objects.append(EnvironmentalObject(
                        object_id, object_position, object_data.get("radius", 0.0),
                        blocks_movement, attributes,
                        parse_tags(object_data.get("tags", []), f"{object_path}.tags"),
                    ))
                except (TypeError, ValueError) as error:
                    raise ABMModelDataError(object_path, str(error)) from error

            space = SpatialSpace(
                raw_space["width"], raw_space["height"], boundary,
                tuple(obstacles), agent_collisions, collision_resolution,
                grid=grid, regions=tuple(regions), zones=tuple(zones), objects=tuple(objects),
            )
        except ABMModelDataError:
            raise
        except (TypeError, ValueError) as error:
            raise ABMModelDataError("space", str(error)) from error

    try:
        return AgentModel(
            name=name,
            agents=tuple(agents),
            environment=environment,
            relationships=tuple(relationships),
            behaviours=tuple(behaviours),
            activation=activation,
            termination=MaxSteps(max_steps),
            random_seed=random_seed,
            space=space,
        )
    except (TypeError, ValueError) as error:
        raise ABMModelDataError("model", str(error)) from error
