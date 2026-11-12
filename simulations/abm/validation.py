"""Deterministic structural and semantic validation for ABM V1 models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from simulations.abm.model import (
    Action,
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
    SetAttribute,
    SetState,
)


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.ERROR


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            details = "; ".join(
                f"{issue.path}: {issue.message}" for issue in self.errors
            )
            raise ValueError(f"Invalid agent-based model: {details}")


def _validate_condition(condition: Condition, path: str, issues: list[ValidationIssue]) -> None:
    if isinstance(condition, AgentStateIs):
        if not condition.state.strip():
            issues.append(ValidationIssue(path, "EMPTY_STATE", "Condition state must not be empty."))
        return

    if isinstance(condition, AgentAttributeComparison):
        if not condition.attribute.strip():
            issues.append(ValidationIssue(path, "EMPTY_ATTRIBUTE", "Condition attribute must not be empty."))
        if condition.operator in {
            ComparisonOperator.LESS_THAN,
            ComparisonOperator.LESS_THAN_OR_EQUAL,
            ComparisonOperator.GREATER_THAN,
            ComparisonOperator.GREATER_THAN_OR_EQUAL,
        }:
            if isinstance(condition.value, bool) or not isinstance(condition.value, (int, float)):
                issues.append(
                    ValidationIssue(
                        path,
                        "NON_NUMERIC_ORDERED_COMPARISON",
                        "Ordered attribute comparisons require a numeric comparison value.",
                    )
                )
            elif isinstance(condition.value, float) and not isfinite(condition.value):
                issues.append(ValidationIssue(path, "NON_FINITE_VALUE", "Comparison value must be finite."))
        return

    if isinstance(condition, RelatedAgentStateCount):
        if condition.count < 0:
            issues.append(ValidationIssue(path, "NEGATIVE_RELATED_COUNT", "Related-agent count cannot be negative."))
        return

    if isinstance(condition, (AllOf, AnyOf)):
        if not condition.conditions:
            issues.append(ValidationIssue(path, "EMPTY_COMPOSITE_CONDITION", "Composite conditions cannot be empty."))
            return
        for index, child in enumerate(condition.conditions):
            _validate_condition(child, f"{path}.conditions[{index}]", issues)
        return

    issues.append(
        ValidationIssue(path, "UNSUPPORTED_CONDITION", f"Unsupported condition type: {type(condition).__name__}.")
    )


def _validate_action(action: Action, path: str, issues: list[ValidationIssue]) -> None:
    if isinstance(action, SetState):
        if not action.state.strip():
            issues.append(ValidationIssue(path, "EMPTY_ACTION_STATE", "SetState requires a non-empty state."))
        return

    if isinstance(action, SetAttribute):
        if not action.attribute.strip():
            issues.append(ValidationIssue(path, "EMPTY_ACTION_ATTRIBUTE", "SetAttribute requires a non-empty attribute name."))
        return

    if isinstance(action, IncrementAttribute):
        if not action.attribute.strip():
            issues.append(ValidationIssue(path, "EMPTY_INCREMENT_ATTRIBUTE", "IncrementAttribute requires a non-empty attribute name."))
        if isinstance(action.amount, bool) or not isinstance(action.amount, (int, float)) or not isfinite(action.amount):
            issues.append(ValidationIssue(path, "INVALID_INCREMENT_AMOUNT", "Increment amount must be finite and numeric."))
        return

    issues.append(
        ValidationIssue(path, "UNSUPPORTED_ACTION", f"Unsupported action type: {type(action).__name__}.")
    )


def _condition_attribute_references(condition: Condition, path: str):
    """Yield each attribute comparison with its exact condition path."""
    if isinstance(condition, AgentAttributeComparison):
        yield path, condition
    elif isinstance(condition, (AllOf, AnyOf)):
        for index, child in enumerate(condition.conditions):
            yield from _condition_attribute_references(
                child,
                f"{path}.conditions[{index}]",
            )


def _validate_rule_attributes(
    model: AgentModel,
    rule: BehaviourRule,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    """Check that rule attributes exist and support their requested operations.

    ABM V1 requires attributes read by conditions and incremented by actions
    to be present in each applicable agent's initial attributes. SetAttribute
    may introduce or replace an attribute during execution.
    """
    targets = tuple(
        agent
        for agent in model.agents
        if rule.agent_type is None or agent.agent_type == rule.agent_type
    )

    for condition_path, comparison in _condition_attribute_references(
        rule.condition,
        f"{path}.condition",
    ):
        for agent in targets:
            if comparison.attribute not in agent.attributes:
                issues.append(
                    ValidationIssue(
                        condition_path,
                        "MISSING_AGENT_ATTRIBUTE",
                        f"Agent {agent.identifier!r} has no initial attribute "
                        f"{comparison.attribute!r} used by this condition.",
                    )
                )
                continue

            current_value = agent.attributes[comparison.attribute]
            ordered = comparison.operator in {
                ComparisonOperator.LESS_THAN,
                ComparisonOperator.LESS_THAN_OR_EQUAL,
                ComparisonOperator.GREATER_THAN,
                ComparisonOperator.GREATER_THAN_OR_EQUAL,
            }
            if ordered and (
                isinstance(current_value, bool)
                or not isinstance(current_value, (int, float))
            ):
                issues.append(
                    ValidationIssue(
                        condition_path,
                        "NON_NUMERIC_AGENT_ATTRIBUTE",
                        f"Agent {agent.identifier!r} has a non-numeric value for "
                        f"ordered comparison attribute {comparison.attribute!r}.",
                    )
                )

    for action_index, action in enumerate(rule.actions):
        if not isinstance(action, IncrementAttribute):
            continue
        action_path = f"{path}.actions[{action_index}]"
        for agent in targets:
            value = agent.attributes.get(action.attribute)
            if action.attribute not in agent.attributes:
                issues.append(
                    ValidationIssue(
                        action_path,
                        "MISSING_INCREMENT_ATTRIBUTE",
                        f"Agent {agent.identifier!r} must have an initial numeric "
                        f"attribute {action.attribute!r} to increment it.",
                    )
                )
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                issues.append(
                    ValidationIssue(
                        action_path,
                        "NON_NUMERIC_INCREMENT_ATTRIBUTE",
                        f"Agent {agent.identifier!r} has a non-numeric value for "
                        f"incremented attribute {action.attribute!r}.",
                    )
                )


def validate_agent_model(model: AgentModel) -> ValidationReport:
    """Return all detectable model issues without executing the model.

    V1 supports sequential activation in agent declaration order, static
    relationships, scalar attributes and max-step termination.
    """
    if not isinstance(model, AgentModel):
        raise TypeError("model must be an AgentModel instance")

    issues: list[ValidationIssue] = []

    if not model.agents:
        issues.append(ValidationIssue("agents", "NO_AGENTS", "At least one agent is required."))

    agent_ids = [agent.identifier for agent in model.agents]
    seen_ids: set[str] = set()
    for index, identifier in enumerate(agent_ids):
        if identifier in seen_ids:
            issues.append(
                ValidationIssue(
                    f"agents[{index}].identifier",
                    "DUPLICATE_AGENT_ID",
                    f"Agent identifier {identifier!r} is not unique.",
                )
            )
        seen_ids.add(identifier)

    known_ids = set(agent_ids)
    seen_relationships: set[tuple[str, str, str, bool]] = set()
    for index, relationship in enumerate(model.relationships):
        path = f"relationships[{index}]"
        if relationship.source_agent_id not in known_ids:
            issues.append(
                ValidationIssue(
                    f"{path}.source_agent_id",
                    "UNKNOWN_RELATIONSHIP_SOURCE",
                    f"Unknown agent {relationship.source_agent_id!r}.",
                )
            )
        if relationship.target_agent_id not in known_ids:
            issues.append(
                ValidationIssue(
                    f"{path}.target_agent_id",
                    "UNKNOWN_RELATIONSHIP_TARGET",
                    f"Unknown agent {relationship.target_agent_id!r}.",
                )
            )
        left, right = relationship.source_agent_id, relationship.target_agent_id
        if not relationship.directed and right < left:
            left, right = right, left
        key = (left, right, relationship.relation_type, relationship.directed)
        if key in seen_relationships:
            issues.append(
                ValidationIssue(path, "DUPLICATE_RELATIONSHIP", "This relationship is already defined.")
            )
        seen_relationships.add(key)

    seen_rule_ids: set[str] = set()
    agent_types = {agent.agent_type for agent in model.agents}
    for index, rule in enumerate(model.behaviours):
        path = f"behaviours[{index}]"
        if rule.rule_id in seen_rule_ids:
            issues.append(
                ValidationIssue(f"{path}.rule_id", "DUPLICATE_RULE_ID", f"Rule ID {rule.rule_id!r} is not unique.")
            )
        seen_rule_ids.add(rule.rule_id)

        if rule.agent_type is not None and rule.agent_type not in agent_types:
            issues.append(
                ValidationIssue(
                    f"{path}.agent_type",
                    "UNKNOWN_AGENT_TYPE",
                    f"No agents of type {rule.agent_type!r} exist in this model.",
                )
            )

        if not isfinite(rule.probability) or not 0 <= rule.probability <= 1:
            issues.append(
                ValidationIssue(
                    f"{path}.probability",
                    "INVALID_PROBABILITY",
                    "Probability must be finite and between 0 and 1.",
                )
            )

        _validate_condition(rule.condition, f"{path}.condition", issues)
        for action_index, action in enumerate(rule.actions):
            _validate_action(action, f"{path}.actions[{action_index}]", issues)
        _validate_rule_attributes(model, rule, path, issues)

    if not isinstance(model.termination, MaxSteps):
        issues.append(
            ValidationIssue(
                "termination",
                "UNSUPPORTED_TERMINATION",
                f"Unsupported termination type: {type(model.termination).__name__}.",
            )
        )
    elif model.termination.value <= 0:
        issues.append(
            ValidationIssue("termination.value", "INVALID_MAX_STEPS", "Maximum steps must be positive.")
        )

    if model.random_seed is not None and (
        isinstance(model.random_seed, bool)
        or not isinstance(model.random_seed, int)
        or model.random_seed < 0
    ):
        issues.append(
            ValidationIssue("random_seed", "INVALID_RANDOM_SEED", "Random seed must be a non-negative integer.")
        )

    # A condition may intentionally count zero neighbours, so a relation type
    # absent from the initial network is not automatically an error.
    return ValidationReport(tuple(issues))
