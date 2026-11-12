"""Deterministic and seeded-stochastic execution for ABM V1."""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Mapping

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
    RelatedAgentStateCount,
    Scalar,
    SetAttribute,
    SetState,
)
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_scalar_mapping(self.attributes))


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
class AgentTrajectoryPoint:
    """One agent's state and attributes at a recorded simulation step."""

    step: int
    state: str
    attributes: Mapping[str, Scalar]

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

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "final_state_counts",
            MappingProxyType(dict(self.final_state_counts)),
        )
        expected_history_length = self.steps_completed + 1
        if len(self.history) != expected_history_length:
            raise ValueError("history must contain the initial state and every completed step")

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


class AgentBasedSimulationEngine:
    """Execute ABM V1 using sequential, declaration-order activation.

    Agents activate in their original model order. For each agent, behaviour
    rules are evaluated in declaration order. Actions from a successful rule
    are applied immediately and are visible to later rules and later agents in
    the same step. Each rule is evaluated at most once per agent per step.

    For directed relationships, the source agent sees the target as an
    outgoing neighbour. Undirected relationships are visible from both ends.
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
            )
            for agent in model.agents
        }
        neighbours = self._build_neighbour_index(model.agents, model.relationships)
        rng = random.Random(model.random_seed)

        history: list[SimulationSnapshot] = [self._snapshot(0, runtime_agents, model.agents)]
        evaluations: list[RuleEvaluation] = []

        for step in range(1, model.termination.value + 1):
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
                        self._apply_actions(active, rule, step)

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

        if isinstance(condition, AllOf):
            return all(
                self._evaluate_condition(child, active, agents, neighbours, step, rule)
                for child in condition.conditions
            )

        if isinstance(condition, AnyOf):
            return any(
                self._evaluate_condition(child, active, agents, neighbours, step, rule)
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
    ) -> None:
        # Apply to temporary values first so an invalid action cannot leave a
        # partially updated agent state for this rule.
        new_state = active.state
        new_attributes = dict(active.attributes)
        try:
            for action in rule.actions:
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

        active.state = new_state
        active.attributes = new_attributes

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
