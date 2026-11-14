"""Deterministic and seeded-stochastic ABM execution, including M18 spatial environments."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import hypot, isfinite, sqrt
from types import MappingProxyType
from typing import Mapping

from simulations.abm.environment import SpatialIndex
from simulations.abm.model import (
    Action,
    Agent,
    AgentAttributeComparison,
    AgentModel,
    AgentStateIs,
    AllOf,
    AnyOf,
    BehaviourRule,
    ComparisonOperator,
    Condition,
    IncrementAttribute,
    MaxSteps,
    MoveBy,
    MoveTo,
    MoveTowards,
    PathfindingAlgorithm,
    Position,
    RelatedAgentStateCount,
    Scalar,
    SetAttribute,
    SetState,
    SpatialNeighbourStateCount,
    SpatialSpace,
)
from simulations.abm.spatial import advance_along_path, astar_path, path_is_clear
from simulations.abm.validation import validate_agent_model


class SimulationExecutionError(RuntimeError):
    """Raised when a validated ABM encounters an invalid runtime operation."""


def _freeze_scalar_mapping(values: Mapping[str, Scalar]) -> Mapping[str, Scalar]:
    return MappingProxyType(dict(values))


def _is_finite_number(value: object) -> bool:
    """Treat integers as finite without converting huge integers to float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or isfinite(value)


@dataclass(frozen=True, slots=True)
class AgentSnapshot:
    """Immutable view of one agent at a particular simulation step."""

    identifier: str
    agent_type: str
    state: str
    attributes: Mapping[str, Scalar]
    position: Position | None = None
    radius: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_scalar_mapping(self.attributes))
        if self.position is not None and not isinstance(self.position, Position):
            raise TypeError("snapshot position must be a Position or None")
        if isinstance(self.radius, bool) or not isinstance(self.radius, (int, float)) or not isfinite(self.radius) or self.radius < 0:
            raise ValueError("snapshot radius must be a finite non-negative number")


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    """Population state at the start (step 0) or end of a simulation step."""

    step: int
    agents: tuple[AgentSnapshot, ...]

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("snapshot step must be non-negative")
        if not isinstance(self.agents, tuple) or any(
            not isinstance(agent, AgentSnapshot) for agent in self.agents
        ):
            raise TypeError("snapshot agents must be a tuple of AgentSnapshot values")

    def agent(self, identifier: str) -> AgentSnapshot:
        """Return an agent snapshot by identifier."""
        for agent in self.agents:
            if agent.identifier == identifier:
                return agent
        raise KeyError(identifier)


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """Trace one applicable rule evaluation for one agent activation."""

    step: int
    agent_id: str
    rule_id: str
    condition_matched: bool
    probability_passed: bool | None
    actions_applied: bool
    state_before: str
    state_after: str


@dataclass(frozen=True, slots=True)
class MovementEvent:
    """Auditable result of one spatial movement action."""

    step: int
    agent_id: str
    rule_id: str
    action_index: int
    action_type: str
    requested_target: Position
    actual_position: Position
    status: str
    reason: str | None = None
    path: tuple[Position, ...] = ()
    distance_travelled: float = 0.0
    distance_limit_reached: bool = False

    def __post_init__(self) -> None:
        if self.step <= 0 or self.action_index < 0:
            raise ValueError("movement event step/action index is invalid")
        if not isinstance(self.requested_target, Position) or not isinstance(self.actual_position, Position):
            raise TypeError("movement event positions must be Position values")
        if self.status not in {"moved", "blocked", "slid", "no_path", "unchanged"}:
            raise ValueError("movement event status is unsupported")
        if self.distance_travelled < 0 or not isfinite(self.distance_travelled):
            raise ValueError("movement event distance must be finite and non-negative")
        if not isinstance(self.path, tuple) or any(not isinstance(point, Position) for point in self.path):
            raise TypeError("movement event path must be a tuple of Position values")
        if not isinstance(self.distance_limit_reached, bool):
            raise TypeError("movement event distance_limit_reached must be a boolean")


@dataclass(frozen=True, slots=True)
class AgentTrajectoryPoint:
    """One agent's state and attributes at a recorded simulation step."""

    step: int
    state: str
    attributes: Mapping[str, Scalar]
    position: Position | None = None
    radius: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_scalar_mapping(self.attributes))


@dataclass(frozen=True, slots=True)
class ABMSimulationResult:
    """Complete ABM execution result, including snapshots and rule trace."""

    model_name: str
    steps_completed: int
    random_seed: int | None
    history: tuple[SimulationSnapshot, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]
    final_state_counts: Mapping[str, int]
    movement_events: tuple[MovementEvent, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "final_state_counts",
            MappingProxyType(dict(self.final_state_counts)),
        )
        expected_history_length = self.steps_completed + 1
        if len(self.history) != expected_history_length:
            raise ValueError("history must contain the initial state and every completed step")
        if not isinstance(self.movement_events, tuple) or any(
            not isinstance(item, MovementEvent) for item in self.movement_events
        ):
            raise TypeError("movement_events must be a tuple of MovementEvent values")

    @property
    def final_agents(self) -> tuple[AgentSnapshot, ...]:
        """Return the final population snapshot."""
        return self.history[-1].agents

    def trajectory(self, agent_id: str) -> tuple[AgentTrajectoryPoint, ...]:
        """Return the recorded state and attributes of one agent over time."""
        if not self.history:
            return ()
        self.history[0].agent(agent_id)  # Validate the requested identifier.
        return tuple(
            AgentTrajectoryPoint(
                step=snapshot.step,
                state=agent.state,
                attributes=agent.attributes,
                position=agent.position,
                radius=agent.radius,
            )
            for snapshot in self.history
            for agent in (snapshot.agent(agent_id),)
        )


@dataclass(slots=True)
class _RuntimeAgent:
    identifier: str
    agent_type: str
    state: str
    attributes: dict[str, Scalar]
    position: Position | None = None
    radius: float = 0.0
    max_step_distance: float | None = None
    movement_used: float = 0.0


class AgentBasedSimulationEngine:
    """Execute ABM using sequential, declaration-order activation.

    Agents activate in their original model order. For each agent, behaviour
    rules are evaluated in declaration order. Actions from a successful rule
    are applied immediately and are visible to later rules and later agents in
    the same step. Each rule is evaluated at most once per agent per step.

    For directed relationships, the source agent sees the target as an
    outgoing neighbour. Undirected relationships are visible from both ends.
    Spatial neighbourhoods use current Euclidean positions; movement committed
    by an earlier agent is visible to agents activated later in the same step.
    """

    def run(self, model: AgentModel) -> ABMSimulationResult:
        """Validate and execute ``model`` for its configured maximum steps."""
        if not isinstance(model, AgentModel):
            raise TypeError("model must be an AgentModel instance")

        validation = validate_agent_model(model)
        validation.raise_for_errors()
        if not isinstance(model.termination, MaxSteps):
            raise SimulationExecutionError("Only MaxSteps termination is supported in ABM V1")

        runtime_agents = {
            agent.identifier: _RuntimeAgent(
                identifier=agent.identifier,
                agent_type=agent.agent_type,
                state=agent.state,
                attributes=dict(agent.attributes),
                position=agent.position,
                radius=agent.radius,
                max_step_distance=agent.max_step_distance,
            )
            for agent in model.agents
        }
        neighbours = self._build_neighbour_index(model.agents, model.relationships)
        spatial_index = None
        if model.space is not None:
            default_cell_size = max(1.0, sqrt(
                model.space.width * model.space.height / max(1, len(runtime_agents))
            ))
            cell_size = model.space.grid.cell_size if model.space.grid is not None else default_cell_size
            spatial_index = SpatialIndex.from_positions(
                {identifier: agent.position for identifier, agent in runtime_agents.items() if agent.position is not None},
                cell_size,
            )
        rng = random.Random(model.random_seed)

        history: list[SimulationSnapshot] = [self._snapshot(0, runtime_agents, model.agents)]
        evaluations: list[RuleEvaluation] = []
        movement_events: list[MovementEvent] = []

        for step in range(1, model.termination.value + 1):
            for runtime_agent in runtime_agents.values():
                runtime_agent.movement_used = 0.0
            for initial_agent in model.agents:
                active = runtime_agents[initial_agent.identifier]
                for rule in model.behaviours:
                    if rule.agent_type is not None and rule.agent_type != active.agent_type:
                        continue

                    state_before = active.state
                    matched = self._evaluate_condition(
                        rule.condition,
                        active,
                        runtime_agents,
                        neighbours,
                        step,
                        rule,
                        model.space,
                        spatial_index,
                    )
                    if not matched:
                        evaluations.append(
                            RuleEvaluation(
                                step=step,
                                agent_id=active.identifier,
                                rule_id=rule.rule_id,
                                condition_matched=False,
                                probability_passed=None,
                                actions_applied=False,
                                state_before=state_before,
                                state_after=active.state,
                            )
                        )
                        continue

                    probability_passed = self._probability_passes(rule, rng)
                    if probability_passed:
                        self._apply_actions(
                            active, rule, step, model.space,
                            agents=runtime_agents, movement_events=movement_events,
                            spatial_index=spatial_index,
                        )

                    evaluations.append(
                        RuleEvaluation(
                            step=step,
                            agent_id=active.identifier,
                            rule_id=rule.rule_id,
                            condition_matched=True,
                            probability_passed=probability_passed,
                            actions_applied=probability_passed,
                            state_before=state_before,
                            state_after=active.state,
                        )
                    )

            history.append(self._snapshot(step, runtime_agents, model.agents))

        final_counts: dict[str, int] = {}
        for runtime_agent in runtime_agents.values():
            final_counts[runtime_agent.state] = final_counts.get(runtime_agent.state, 0) + 1

        return ABMSimulationResult(
            model_name=model.name,
            steps_completed=model.termination.value,
            random_seed=model.random_seed,
            history=tuple(history),
            rule_evaluations=tuple(evaluations),
            final_state_counts=dict(sorted(final_counts.items())),
            movement_events=tuple(movement_events),
        )

    @staticmethod
    def _build_neighbour_index(agents, relationships) -> dict[tuple[str, str], tuple[str, ...]]:
        agent_ids = {agent.identifier for agent in agents}
        mutable: dict[tuple[str, str], list[str]] = {
            (identifier, relation_type): []
            for identifier in agent_ids
            for relation_type in {edge.relation_type for edge in relationships}
        }
        for edge in relationships:
            mutable.setdefault((edge.source_agent_id, edge.relation_type), []).append(
                edge.target_agent_id
            )
            if not edge.directed and edge.source_agent_id != edge.target_agent_id:
                mutable.setdefault((edge.target_agent_id, edge.relation_type), []).append(
                    edge.source_agent_id
                )
        return {key: tuple(value) for key, value in mutable.items()}

    @staticmethod
    def _snapshot(
        step: int,
        runtime_agents: Mapping[str, _RuntimeAgent],
        declaration_order: tuple[Agent, ...],
    ) -> SimulationSnapshot:
        return SimulationSnapshot(
            step=step,
            agents=tuple(
                AgentSnapshot(
                    identifier=initial.identifier,
                    agent_type=runtime_agents[initial.identifier].agent_type,
                    state=runtime_agents[initial.identifier].state,
                    attributes=runtime_agents[initial.identifier].attributes,
                    position=runtime_agents[initial.identifier].position,
                    radius=runtime_agents[initial.identifier].radius,
                )
                for initial in declaration_order
            ),
        )

    def _evaluate_condition(
        self,
        condition: Condition,
        active: _RuntimeAgent,
        agents: Mapping[str, _RuntimeAgent],
        neighbours: Mapping[tuple[str, str], tuple[str, ...]],
        step: int,
        rule: BehaviourRule,
        space: SpatialSpace | None,
        spatial_index: SpatialIndex | None = None,
    ) -> bool:
        if isinstance(condition, AgentStateIs):
            return active.state == condition.state

        if isinstance(condition, AgentAttributeComparison):
            if condition.attribute not in active.attributes:
                raise SimulationExecutionError(
                    self._runtime_context(step, active, rule)
                    + f"missing attribute {condition.attribute!r} during condition evaluation"
                )
            return self._compare(
                active.attributes[condition.attribute],
                condition.operator,
                condition.value,
                step,
                active,
                rule,
            )

        if isinstance(condition, RelatedAgentStateCount):
            related_ids = neighbours.get((active.identifier, condition.relation_type), ())
            matching_count = sum(
                1 for identifier in related_ids if agents[identifier].state == condition.state
            )
            return self._compare(
                matching_count,
                condition.operator,
                condition.count,
                step,
                active,
                rule,
            )

        if isinstance(condition, SpatialNeighbourStateCount):
            if space is None or active.position is None:
                raise SimulationExecutionError(
                    self._runtime_context(step, active, rule)
                    + "spatial neighbourhood condition requires a positioned agent and spatial space"
                )
            if spatial_index is not None:
                candidates: dict[str, Position] = {}
                offsets = (0.0,) if space.boundary.value != "wrap" else (-1.0, 0.0, 1.0)
                for offset_x in offsets:
                    for offset_y in offsets:
                        query_center = Position(
                            active.position.x + offset_x * space.width,
                            active.position.y + offset_y * space.height,
                        )
                        candidates.update(dict(spatial_index.query_radius(query_center, condition.radius)))
                candidate_ids = candidates
            else:
                candidate_ids = {
                    identifier: other.position
                    for identifier, other in agents.items()
                    if other.position is not None
                }
            matching_count = sum(
                1
                for identifier, position in candidate_ids.items()
                if identifier != active.identifier
                and agents[identifier].state == condition.state
                and space.distance(active.position, position) <= condition.radius
            )
            return self._compare(
                matching_count,
                condition.operator,
                condition.count,
                step,
                active,
                rule,
            )

        if isinstance(condition, AllOf):
            return all(
                self._evaluate_condition(child, active, agents, neighbours, step, rule, space, spatial_index)
                for child in condition.conditions
            )

        if isinstance(condition, AnyOf):
            return any(
                self._evaluate_condition(child, active, agents, neighbours, step, rule, space, spatial_index)
                for child in condition.conditions
            )

        raise SimulationExecutionError(
            self._runtime_context(step, active, rule)
            + f"unsupported condition type {type(condition).__name__}"
        )

    @staticmethod
    def _compare(
        left: Scalar,
        operator: ComparisonOperator,
        right: Scalar,
        step: int,
        active: _RuntimeAgent,
        rule: BehaviourRule,
    ) -> bool:
        if operator in {ComparisonOperator.EQUAL, ComparisonOperator.NOT_EQUAL}:
            if isinstance(left, bool) or isinstance(right, bool):
                equal = isinstance(left, bool) and isinstance(right, bool) and left == right
            elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                equal = left == right
            else:
                equal = type(left) is type(right) and left == right
            return equal if operator is ComparisonOperator.EQUAL else not equal

        if not _is_finite_number(left) or not _is_finite_number(right):
            raise SimulationExecutionError(
                f"Step {step}, agent {active.identifier!r}, rule {rule.rule_id!r}: "
                "ordered comparisons require finite numeric values at runtime"
            )

        if operator is ComparisonOperator.LESS_THAN:
            return left < right
        if operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
            return left <= right
        if operator is ComparisonOperator.GREATER_THAN:
            return left > right
        if operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return left >= right
        raise SimulationExecutionError(f"Unsupported comparison operator: {operator!r}")

    @staticmethod
    def _probability_passes(rule: BehaviourRule, rng: random.Random) -> bool:
        if rule.probability >= 1:
            return True
        if rule.probability <= 0:
            return False
        return rng.random() < rule.probability

    def _apply_actions(
        self,
        active: _RuntimeAgent,
        rule: BehaviourRule,
        step: int,
        space: SpatialSpace | None = None,
        *,
        agents: Mapping[str, _RuntimeAgent] | None = None,
        movement_events: list[MovementEvent] | None = None,
        spatial_index: SpatialIndex | None = None,
    ) -> None:
        # Apply to temporary values first so an invalid action cannot leave a
        # partially updated agent state, position, or movement budget.
        new_state = active.state
        new_attributes = dict(active.attributes)
        new_position = active.position
        new_movement_used = active.movement_used
        pending_events: list[MovementEvent] = []
        visible_agents = agents or {active.identifier: active}
        try:
            for action_index, action in enumerate(rule.actions):
                if isinstance(action, (MoveBy, MoveTo, MoveTowards)):
                    if space is None or new_position is None:
                        raise SimulationExecutionError(
                            self._runtime_context(step, active, rule)
                            + f"{type(action).__name__} requires a positioned agent and spatial space"
                        )
                    outcome = self._execute_movement(
                        active=active,
                        start=new_position,
                        action=action,
                        action_index=action_index,
                        rule=rule,
                        step=step,
                        space=space,
                        agents=visible_agents,
                        movement_used=new_movement_used,
                    )
                    new_position = outcome.actual_position
                    new_movement_used += outcome.distance_travelled
                    pending_events.append(outcome)
                else:
                    self._apply_action(action, new_attributes, step, active, rule)
                if isinstance(action, SetState):
                    new_state = action.state
        except SimulationExecutionError:
            raise
        except Exception as error:
            raise SimulationExecutionError(
                self._runtime_context(step, active, rule)
                + f"could not apply rule actions: {error}"
            ) from error

        if spatial_index is not None and new_position is not None and new_position != active.position:
            spatial_index.move(active.identifier, new_position)
        active.state = new_state
        active.attributes = new_attributes
        active.position = new_position
        active.movement_used = new_movement_used
        if movement_events is not None:
            movement_events.extend(pending_events)

    def _execute_movement(
        self,
        *,
        active: _RuntimeAgent,
        start: Position,
        action: MoveBy | MoveTo | MoveTowards,
        action_index: int,
        rule: BehaviourRule,
        step: int,
        space: SpatialSpace,
        agents: Mapping[str, _RuntimeAgent],
        movement_used: float,
    ) -> MovementEvent:
        if isinstance(action, MoveBy):
            raw_target = Position(start.x + action.dx, start.y + action.dy)
            target = space.normalize(raw_target)
            route = (start, raw_target if space.boundary.value == "wrap" else target)
            movement_cap = None
            action_type = "move_by"
        elif isinstance(action, MoveTo):
            target = space.normalize(Position(action.x, action.y))
            delta_x = target.x - start.x
            delta_y = target.y - start.y
            if space.boundary.value == "wrap":
                if delta_x > space.width / 2:
                    delta_x -= space.width
                elif delta_x < -space.width / 2:
                    delta_x += space.width
                if delta_y > space.height / 2:
                    delta_y -= space.height
                elif delta_y < -space.height / 2:
                    delta_y += space.height
            raw_target = Position(start.x + delta_x, start.y + delta_y)
            route = (start, raw_target)
            movement_cap = None
            action_type = "move_to"
        else:
            target = space.normalize(Position(action.x, action.y))
            if action.pathfinding is PathfindingAlgorithm.ASTAR:
                try:
                    route = astar_path(
                        space, start, target, active.radius, action.grid_cell_size,
                        tuple(agents.values()), active.identifier,
                    )
                except ValueError as error:
                    raise SimulationExecutionError(
                        self._runtime_context(step, active, rule) + str(error)
                    ) from error
                if route is None:
                    return MovementEvent(
                        step, active.identifier, rule.rule_id, action_index, "move_towards",
                        target, start, "no_path", "path_not_found", (start,), 0.0, False,
                    )
            else:
                raw_target = target
                if space.boundary.value == "wrap":
                    dx = target.x - start.x
                    dy = target.y - start.y
                    if dx > space.width / 2:
                        dx -= space.width
                    elif dx < -space.width / 2:
                        dx += space.width
                    if dy > space.height / 2:
                        dy -= space.height
                    elif dy < -space.height / 2:
                        dy += space.height
                    raw_target = Position(start.x + dx, start.y + dy)
                route = (start, raw_target)
            movement_cap = action.max_distance
            action_type = "move_towards"

        route_length = self._polyline_length(route)
        remaining_agent_budget = (
            float("inf") if active.max_step_distance is None
            else max(0.0, active.max_step_distance - movement_used)
        )
        effective_budget = remaining_agent_budget
        if movement_cap is not None:
            effective_budget = min(effective_budget, movement_cap)
        distance_limit_reached = effective_budget + 1e-10 < route_length
        candidate, travelled_path = advance_along_path(route, effective_budget)
        candidate_position = candidate
        if space.boundary.value != "wrap":
            candidate_position = space.normalize(candidate)

        clear = self._route_is_clear(
            travelled_path, space, active.radius, agents, active.identifier,
        )
        status = "moved"
        reason = None
        actual_path = travelled_path

        if not clear:
            if isinstance(action, MoveTowards) and action.pathfinding is PathfindingAlgorithm.ASTAR:
                status, reason = "no_path", "route_blocked"
                candidate_position = start
                actual_path = (start,)
            elif space.collision_resolution.value == "slide":
                slide_position, slide_path, blocker = self._slide_move(
                    start, candidate, space, active, agents,
                )
                candidate_position = slide_position
                actual_path = slide_path
                if self._polyline_length(slide_path) > 1e-10:
                    status = "slid"
                    reason = blocker
                else:
                    status = "blocked"
                    reason = blocker
            else:
                status, reason = "blocked", self._first_blocker(
                    travelled_path, space, active.radius, agents, active.identifier,
                )
                candidate_position = start
                actual_path = (start,)

        if space.boundary.value == "wrap":
            candidate_position = space.normalize(candidate_position)
        distance_travelled = self._polyline_length(actual_path)
        if distance_travelled <= 1e-10 and status == "moved":
            status = "unchanged"
        return MovementEvent(
            step=step,
            agent_id=active.identifier,
            rule_id=rule.rule_id,
            action_index=action_index,
            action_type=action_type,
            requested_target=target,
            actual_position=candidate_position,
            status=status,
            reason=reason or ("distance_limit" if distance_limit_reached else None),
            path=actual_path,
            distance_travelled=distance_travelled,
            distance_limit_reached=distance_limit_reached,
        )

    @staticmethod
    def _polyline_length(path: tuple[Position, ...]) -> float:
        return sum(hypot(right.x - left.x, right.y - left.y) for left, right in zip(path, path[1:]))

    @staticmethod
    def _route_is_clear(
        path: tuple[Position, ...],
        space: SpatialSpace,
        radius: float,
        agents: Mapping[str, _RuntimeAgent],
        active_id: str,
    ) -> bool:
        return all(
            path_is_clear(space, left, right, radius, tuple(agents.values()), active_id)[0]
            for left, right in zip(path, path[1:])
        )

    @staticmethod
    def _first_blocker(
        path: tuple[Position, ...],
        space: SpatialSpace,
        radius: float,
        agents: Mapping[str, _RuntimeAgent],
        active_id: str,
    ) -> str:
        for left, right in zip(path, path[1:]):
            clear, blocker = path_is_clear(space, left, right, radius, tuple(agents.values()), active_id)
            if not clear:
                return blocker or "collision"
        return "collision"

    def _slide_move(
        self,
        start: Position,
        target: Position,
        space: SpatialSpace,
        active: _RuntimeAgent,
        agents: Mapping[str, _RuntimeAgent],
    ) -> tuple[Position, tuple[Position, ...], str | None]:
        # Deterministic axis order: try X first, then Y. If X is blocked, try Y
        # from the original point. The policy is stable across platforms.
        x_candidate = Position(target.x, start.y)
        first_clear, first_blocker = path_is_clear(
            space, start, x_candidate, active.radius, tuple(agents.values()), active.identifier,
        )
        current = x_candidate if first_clear else start
        path = [start]
        blocker = first_blocker
        if first_clear and self._polyline_length((start, current)) > 1e-10:
            path.append(current)
        y_candidate = Position(current.x, target.y)
        second_clear, second_blocker = path_is_clear(
            space, current, y_candidate, active.radius, tuple(agents.values()), active.identifier,
        )
        if second_clear and self._polyline_length((current, y_candidate)) > 1e-10:
            path.append(y_candidate)
            current = y_candidate
        elif not second_clear:
            blocker = second_blocker or blocker
        return current, tuple(path), blocker

    def _apply_action(
        self,
        action: Action,
        attributes: dict[str, Scalar],
        step: int,
        active: _RuntimeAgent,
        rule: BehaviourRule,
    ) -> None:
        if isinstance(action, SetState):
            return

        if isinstance(action, SetAttribute):
            attributes[action.attribute] = action.value
            return

        if isinstance(action, IncrementAttribute):
            current = attributes.get(action.attribute)
            if not _is_finite_number(current):
                raise SimulationExecutionError(
                    self._runtime_context(step, active, rule)
                    + f"cannot increment non-numeric attribute {action.attribute!r}"
                )
            updated = current + action.amount
            if isinstance(updated, float) and not isfinite(updated):
                raise SimulationExecutionError(
                    self._runtime_context(step, active, rule)
                    + f"increment produced a non-finite value for {action.attribute!r}"
                )
            attributes[action.attribute] = updated
            return

        raise SimulationExecutionError(
            self._runtime_context(step, active, rule)
            + f"unsupported action type {type(action).__name__}"
        )

    @staticmethod
    def _runtime_context(step: int, active: _RuntimeAgent, rule: BehaviourRule) -> str:
        return f"Step {step}, agent {active.identifier!r}, rule {rule.rule_id!r}: "


def run_agent_model(model: AgentModel) -> ABMSimulationResult:
    """Convenience function for executing one validated ABM model."""
    return AgentBasedSimulationEngine().run(model)
