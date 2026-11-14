"""Typed model definitions for Agent-Based Simulation (ABM) V1.

This module defines declarative model data only. It does not execute agents
or evaluate behaviour rules; execution semantics are implemented by the ABM
engine in a later milestone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping, TypeAlias

Scalar: TypeAlias = str | int | float | bool | None


def _non_empty_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_scalar(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"{field_name} must be a JSON-compatible scalar")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{field_name} must be finite")


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{field_name} must be finite") from error
    if not isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _freeze_attributes(values: Mapping[str, Scalar], field_name: str) -> Mapping[str, Scalar]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping")

    copied: dict[str, Scalar] = {}
    for key, value in values.items():
        _non_empty_text(key, f"{field_name} key")
        _validate_scalar(value, f"{field_name}[{key!r}]")
        copied[key] = value
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class Position:
    """A 2D coordinate in the model's spatial coordinate system."""

    x: float
    y: float

    def __post_init__(self) -> None:
        for name, value in (("x", self.x), ("y", self.y)):
            object.__setattr__(self, name, _finite_float(value, f"position {name}"))


class BoundaryMode(str, Enum):
    """How movement beyond a spatial world's edge is handled."""

    CLAMP = "clamp"
    WRAP = "wrap"


class CollisionResolution(str, Enum):
    """Deterministic response when a movement path intersects an obstacle."""

    BLOCK = "block"
    SLIDE = "slide"


@dataclass(frozen=True, slots=True)
class RectangleObstacle:
    """Static axis-aligned rectangular obstacle in model-space units."""

    identifier: str
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        _non_empty_text(self.identifier, "obstacle identifier")
        for name, value in (("x", self.x), ("y", self.y), ("width", self.width), ("height", self.height)):
            number = _finite_float(value, f"rectangle obstacle {name}")
            if name in {"width", "height"} and number <= 0:
                raise ValueError(f"rectangle obstacle {name} must be positive")
            if name in {"x", "y"} and number < 0:
                raise ValueError(f"rectangle obstacle {name} cannot be negative")
            object.__setattr__(self, name, number)


@dataclass(frozen=True, slots=True)
class CircleObstacle:
    """Static circular obstacle, specified by centre and radius."""

    identifier: str
    x: float
    y: float
    radius: float

    def __post_init__(self) -> None:
        _non_empty_text(self.identifier, "obstacle identifier")
        for name, value in (("x", self.x), ("y", self.y), ("radius", self.radius)):
            number = _finite_float(value, f"circle obstacle {name}")
            if number < 0 or (name == "radius" and number == 0):
                raise ValueError(f"circle obstacle {name} must be positive" if name == "radius" else f"circle obstacle {name} cannot be negative")
            object.__setattr__(self, name, number)


SpatialObstacle: TypeAlias = RectangleObstacle | CircleObstacle


@dataclass(frozen=True, slots=True)
class SpatialSpace:
    """A 2D world measured in model-defined units.

    ``clamp`` keeps coordinates within the closed rectangle [0,width] ×
    [0,height]. ``wrap`` treats opposite edges as adjacent and uses a
    half-open rectangle [0,width) × [0,height).
    """

    width: float
    height: float
    boundary: BoundaryMode = BoundaryMode.CLAMP
    obstacles: tuple[SpatialObstacle, ...] = ()
    agent_collisions: bool = True
    collision_resolution: CollisionResolution = CollisionResolution.BLOCK

    def __post_init__(self) -> None:
        for name, value in (("width", self.width), ("height", self.height)):
            number = _finite_float(value, f"space {name}")
            if number <= 0:
                raise ValueError(f"space {name} must be positive and finite")
            object.__setattr__(self, name, number)
        if not isinstance(self.boundary, BoundaryMode):
            raise TypeError("boundary must be a BoundaryMode")
        if not isinstance(self.obstacles, tuple) or any(
            not isinstance(item, (RectangleObstacle, CircleObstacle)) for item in self.obstacles
        ):
            raise TypeError("obstacles must be a tuple of supported obstacle instances")
        if len({item.identifier for item in self.obstacles}) != len(self.obstacles):
            raise ValueError("obstacle identifiers must be unique")
        if not isinstance(self.agent_collisions, bool):
            raise TypeError("agent_collisions must be a boolean")
        if not isinstance(self.collision_resolution, CollisionResolution):
            raise TypeError("collision_resolution must be a CollisionResolution")
        for obstacle in self.obstacles:
            if isinstance(obstacle, RectangleObstacle):
                if obstacle.x + obstacle.width > self.width or obstacle.y + obstacle.height > self.height:
                    raise ValueError(f"rectangle obstacle {obstacle.identifier!r} must lie inside the spatial world")
            elif (
                obstacle.x - obstacle.radius < 0
                or obstacle.y - obstacle.radius < 0
                or obstacle.x + obstacle.radius > self.width
                or obstacle.y + obstacle.radius > self.height
            ):
                raise ValueError(f"circle obstacle {obstacle.identifier!r} must lie inside the spatial world")

    def normalize(self, position: Position) -> Position:
        """Apply the configured boundary policy to a proposed position."""
        if not isinstance(position, Position):
            raise TypeError("position must be a Position")
        if self.boundary is BoundaryMode.WRAP:
            return Position(position.x % self.width, position.y % self.height)
        return Position(
            min(self.width, max(0.0, position.x)),
            min(self.height, max(0.0, position.y)),
        )

    def distance(self, left: Position, right: Position) -> float:
        """Return Euclidean distance, using shortest wrapped deltas if needed."""
        dx = abs(left.x - right.x)
        dy = abs(left.y - right.y)
        if self.boundary is BoundaryMode.WRAP:
            dx = min(dx, self.width - dx)
            dy = min(dy, self.height - dy)
        return (dx * dx + dy * dy) ** 0.5


class ComparisonOperator(str, Enum):
    """Operators supported by declarative behaviour conditions."""

    EQUAL = "eq"
    NOT_EQUAL = "ne"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "le"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "ge"


class ActivationMode(str, Enum):
    """Agent activation strategy supported by ABM V1."""

    SEQUENTIAL = "sequential"


class ActivationOrder(str, Enum):
    """Ordering policy for sequential agent activation."""

    DECLARATION = "declaration"


@dataclass(frozen=True, slots=True)
class Agent:
    """One individual agent and its initial state."""

    identifier: str
    agent_type: str
    state: str
    attributes: Mapping[str, Scalar] = field(default_factory=dict)
    position: Position | None = None
    radius: float = 0.0
    max_step_distance: float | None = None

    def __post_init__(self) -> None:
        _non_empty_text(self.identifier, "agent identifier")
        _non_empty_text(self.agent_type, "agent type")
        _non_empty_text(self.state, "agent state")
        object.__setattr__(
            self, "attributes", _freeze_attributes(self.attributes, "agent attributes")
        )
        if self.position is not None and not isinstance(self.position, Position):
            raise TypeError("agent position must be a Position or None")
        radius = _finite_float(self.radius, "agent radius")
        if radius < 0:
            raise ValueError("agent radius must be non-negative")
        object.__setattr__(self, "radius", radius)
        if self.max_step_distance is not None:
            distance = _finite_float(self.max_step_distance, "agent max_step_distance")
            if distance <= 0:
                raise ValueError("agent max_step_distance must be positive when provided")
            object.__setattr__(self, "max_step_distance", distance)


@dataclass(frozen=True, slots=True)
class Environment:
    """Global scalar attributes shared by the simulated environment."""

    attributes: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attributes",
            _freeze_attributes(self.attributes, "environment attributes"),
        )


@dataclass(frozen=True, slots=True)
class AgentRelationship:
    """A static connection between two agents."""

    source_agent_id: str
    target_agent_id: str
    relation_type: str
    directed: bool = False

    def __post_init__(self) -> None:
        _non_empty_text(self.source_agent_id, "source_agent_id")
        _non_empty_text(self.target_agent_id, "target_agent_id")
        _non_empty_text(self.relation_type, "relation_type")
        if not isinstance(self.directed, bool):
            raise TypeError("directed must be a boolean")


class Condition:
    """Marker base class for declarative behaviour conditions."""


@dataclass(frozen=True, slots=True)
class AgentStateIs(Condition):
    """Match when the active agent has the specified state."""

    state: str

    def __post_init__(self) -> None:
        _non_empty_text(self.state, "condition state")


@dataclass(frozen=True, slots=True)
class AgentAttributeComparison(Condition):
    """Compare one attribute on the active agent with a scalar value."""

    attribute: str
    operator: ComparisonOperator
    value: Scalar

    def __post_init__(self) -> None:
        _non_empty_text(self.attribute, "condition attribute")
        if not isinstance(self.operator, ComparisonOperator):
            raise TypeError("operator must be a ComparisonOperator")
        _validate_scalar(self.value, "condition comparison value")


@dataclass(frozen=True, slots=True)
class RelatedAgentStateCount(Condition):
    """Compare the number of related agents in a particular state."""

    relation_type: str
    state: str
    operator: ComparisonOperator
    count: int

    def __post_init__(self) -> None:
        _non_empty_text(self.relation_type, "condition relation_type")
        _non_empty_text(self.state, "condition state")
        if not isinstance(self.operator, ComparisonOperator):
            raise TypeError("operator must be a ComparisonOperator")
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise TypeError("condition count must be an integer")
        if self.count < 0:
            raise ValueError("condition count must be non-negative")


@dataclass(frozen=True, slots=True)
class SpatialNeighbourStateCount(Condition):
    """Count other agents of a state within a Euclidean radius of the active agent."""

    radius: float
    state: str
    operator: ComparisonOperator
    count: int

    def __post_init__(self) -> None:
        radius = _finite_float(self.radius, "spatial neighbour radius")
        if radius < 0:
            raise ValueError("spatial neighbour radius must be finite and non-negative")
        object.__setattr__(self, "radius", radius)
        _non_empty_text(self.state, "spatial neighbour state")
        if not isinstance(self.operator, ComparisonOperator):
            raise TypeError("operator must be a ComparisonOperator")
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise TypeError("spatial neighbour count must be an integer")
        if self.count < 0:
            raise ValueError("spatial neighbour count must be non-negative")


@dataclass(frozen=True, slots=True)
class AllOf(Condition):
    """Match when every nested condition matches."""

    conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise ValueError("AllOf requires a non-empty tuple of conditions")
        if any(not isinstance(item, Condition) for item in self.conditions):
            raise TypeError("AllOf items must be Condition instances")


@dataclass(frozen=True, slots=True)
class AnyOf(Condition):
    """Match when at least one nested condition matches."""

    conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.conditions, tuple) or not self.conditions:
            raise ValueError("AnyOf requires a non-empty tuple of conditions")
        if any(not isinstance(item, Condition) for item in self.conditions):
            raise TypeError("AnyOf items must be Condition instances")


class Action:
    """Marker base class for declarative agent actions."""


@dataclass(frozen=True, slots=True)
class SetState(Action):
    """Replace the active agent's state."""

    state: str

    def __post_init__(self) -> None:
        _non_empty_text(self.state, "action state")


@dataclass(frozen=True, slots=True)
class SetAttribute(Action):
    """Set an agent attribute to a scalar value."""

    attribute: str
    value: Scalar

    def __post_init__(self) -> None:
        _non_empty_text(self.attribute, "action attribute")
        _validate_scalar(self.value, "action attribute value")


@dataclass(frozen=True, slots=True)
class IncrementAttribute(Action):
    """Add a finite numeric amount to an agent attribute."""

    attribute: str
    amount: int | float

    def __post_init__(self) -> None:
        _non_empty_text(self.attribute, "action attribute")
        if isinstance(self.amount, bool) or not isinstance(self.amount, (int, float)):
            raise TypeError("increment amount must be numeric")
        if not isfinite(self.amount):
            raise ValueError("increment amount must be finite")


@dataclass(frozen=True, slots=True)
class MoveBy(Action):
    """Move the active agent by a relative x/y displacement."""

    dx: float
    dy: float

    def __post_init__(self) -> None:
        for name, value in (("dx", self.dx), ("dy", self.dy)):
            object.__setattr__(self, name, _finite_float(value, f"movement {name}"))


@dataclass(frozen=True, slots=True)
class MoveTo(Action):
    """Move the active agent to an absolute x/y coordinate."""

    x: float
    y: float

    def __post_init__(self) -> None:
        for name, value in (("x", self.x), ("y", self.y)):
            object.__setattr__(self, name, _finite_float(value, f"movement target {name}"))


class PathfindingAlgorithm(str, Enum):
    """Route strategy for a bounded move-towards action."""

    DIRECT = "direct"
    ASTAR = "astar"


@dataclass(frozen=True, slots=True)
class MoveTowards(Action):
    """Advance toward a destination by a bounded distance, optionally via A*."""

    x: float
    y: float
    max_distance: float
    pathfinding: PathfindingAlgorithm = PathfindingAlgorithm.ASTAR
    grid_cell_size: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (("x", self.x), ("y", self.y)):
            object.__setattr__(self, name, _finite_float(value, f"movement target {name}"))
        max_distance = _finite_float(self.max_distance, "move_towards max_distance")
        grid_cell_size = _finite_float(self.grid_cell_size, "move_towards grid_cell_size")
        if max_distance <= 0:
            raise ValueError("move_towards max_distance must be positive")
        if grid_cell_size <= 0:
            raise ValueError("move_towards grid_cell_size must be positive")
        object.__setattr__(self, "max_distance", max_distance)
        object.__setattr__(self, "grid_cell_size", grid_cell_size)
        if not isinstance(self.pathfinding, PathfindingAlgorithm):
            raise TypeError("pathfinding must be a PathfindingAlgorithm")


@dataclass(frozen=True, slots=True)
class BehaviourRule:
    """Apply actions when a condition matches an eligible agent.

    Rules are stored in declaration order. ``probability`` is the chance
    that the actions are applied after the condition matches; the engine
    will use the model's random seed when stochastic execution is added.
    """

    rule_id: str
    condition: Condition
    actions: tuple[Action, ...]
    agent_type: str | None = None
    probability: float = 1.0

    def __post_init__(self) -> None:
        _non_empty_text(self.rule_id, "rule_id")
        if not isinstance(self.condition, Condition):
            raise TypeError("condition must be a Condition instance")
        if not isinstance(self.actions, tuple) or not self.actions:
            raise ValueError("a behaviour rule requires at least one action")
        if any(not isinstance(action, Action) for action in self.actions):
            raise TypeError("behaviour actions must be Action instances")
        if self.agent_type is not None:
            _non_empty_text(self.agent_type, "agent_type")
        if isinstance(self.probability, bool) or not isinstance(
            self.probability, (int, float)
        ):
            raise TypeError("probability must be numeric")
        if not isfinite(self.probability) or not 0 <= self.probability <= 1:
            raise ValueError("probability must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class ActivationPolicy:
    """Declare how agents are activated during each simulation step."""

    mode: ActivationMode = ActivationMode.SEQUENTIAL
    order: ActivationOrder = ActivationOrder.DECLARATION

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ActivationMode):
            raise TypeError("mode must be an ActivationMode")
        if not isinstance(self.order, ActivationOrder):
            raise TypeError("order must be an ActivationOrder")


class TerminationCondition:
    """Marker base class for ABM termination conditions."""


@dataclass(frozen=True, slots=True)
class MaxSteps(TerminationCondition):
    """Stop after a fixed number of simulation steps."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("max_steps must be an integer")
        if self.value <= 0:
            raise ValueError("max_steps must be positive")


@dataclass(frozen=True, slots=True)
class AgentModel:
    """Complete declarative ABM model definition for V1."""

    name: str
    agents: tuple[Agent, ...]
    termination: TerminationCondition
    environment: Environment = field(default_factory=Environment)
    relationships: tuple[AgentRelationship, ...] = ()
    behaviours: tuple[BehaviourRule, ...] = ()
    activation: ActivationPolicy = field(default_factory=ActivationPolicy)
    random_seed: int | None = None
    space: SpatialSpace | None = None

    def __post_init__(self) -> None:
        _non_empty_text(self.name, "model name")
        if not isinstance(self.agents, tuple) or any(
            not isinstance(agent, Agent) for agent in self.agents
        ):
            raise TypeError("agents must be a tuple of Agent instances")
        if not isinstance(self.relationships, tuple) or any(
            not isinstance(item, AgentRelationship) for item in self.relationships
        ):
            raise TypeError(
                "relationships must be a tuple of AgentRelationship instances"
            )
        if not isinstance(self.behaviours, tuple) or any(
            not isinstance(item, BehaviourRule) for item in self.behaviours
        ):
            raise TypeError("behaviours must be a tuple of BehaviourRule instances")
        if not isinstance(self.environment, Environment):
            raise TypeError("environment must be an Environment instance")
        if not isinstance(self.activation, ActivationPolicy):
            raise TypeError("activation must be an ActivationPolicy instance")
        if self.space is not None and not isinstance(self.space, SpatialSpace):
            raise TypeError("space must be a SpatialSpace or None")
        if not isinstance(self.termination, TerminationCondition):
            raise TypeError("termination must be a TerminationCondition instance")
        if self.random_seed is not None:
            if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
                raise TypeError("random_seed must be an integer or None")
            if self.random_seed < 0:
                raise ValueError("random_seed must be non-negative")
