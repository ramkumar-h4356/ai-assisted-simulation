import pytest

from simulations.abm.model import (
    Agent,
    AgentAttributeComparison,
    AgentModel,
    AgentRelationship,
    AgentStateIs,
    AllOf,
    AnyOf,
    BehaviourRule,
    ComparisonOperator,
    Condition,
    IncrementAttribute,
    MaxSteps,
    RelatedAgentStateCount,
    SetState,
)
from simulations.abm.validation import (
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
    validate_agent_model,
)


def make_agent(identifier, *, agent_type="person", state="susceptible", attributes=None):
    return Agent(
        identifier=identifier,
        agent_type=agent_type,
        state=state,
        attributes=attributes or {},
    )


def make_model(**overrides):
    values = {
        "name": "Disease transmission",
        "agents": (
            make_agent("person-1"),
            make_agent("person-2", state="infected"),
        ),
        "termination": MaxSteps(5),
        "relationships": (AgentRelationship("person-1", "person-2", "contact"),),
        "behaviours": (
            BehaviourRule(
                "infection-rule",
                AllOf(
                    (
                        AgentStateIs("susceptible"),
                        RelatedAgentStateCount(
                            "contact", "infected", ComparisonOperator.GREATER_THAN, 0
                        ),
                    )
                ),
                (SetState("infected"),),
                agent_type="person",
            ),
        ),
    }
    values.update(overrides)
    return AgentModel(**values)


def issue_codes(report):
    return {issue.code for issue in report.issues}


def test_valid_infection_model_passes_validation():
    report = validate_agent_model(make_model())

    assert report.is_valid
    assert report.errors == ()


def test_validator_requires_agent_model_instance():
    with pytest.raises(TypeError):
        validate_agent_model({"name": "not a model"})


def test_validator_rejects_model_without_agents():
    report = validate_agent_model(make_model(agents=()))

    assert not report.is_valid
    assert "NO_AGENTS" in issue_codes(report)


def test_validator_detects_duplicate_agent_identifiers():
    report = validate_agent_model(
        make_model(agents=(make_agent("same"), make_agent("same")))
    )

    assert "DUPLICATE_AGENT_ID" in issue_codes(report)


def test_validator_detects_unknown_relationship_source():
    report = validate_agent_model(
        make_model(relationships=(AgentRelationship("missing", "person-2", "contact"),))
    )

    assert "UNKNOWN_RELATIONSHIP_SOURCE" in issue_codes(report)


def test_validator_detects_unknown_relationship_target():
    report = validate_agent_model(
        make_model(relationships=(AgentRelationship("person-1", "missing", "contact"),))
    )

    assert "UNKNOWN_RELATIONSHIP_TARGET" in issue_codes(report)


def test_validator_detects_duplicate_undirected_relationship_in_reverse_order():
    relationships = (
        AgentRelationship("person-1", "person-2", "contact"),
        AgentRelationship("person-2", "person-1", "contact"),
    )
    report = validate_agent_model(make_model(relationships=relationships))

    assert "DUPLICATE_RELATIONSHIP" in issue_codes(report)


def test_validator_allows_distinct_relationship_types():
    relationships = (
        AgentRelationship("person-1", "person-2", "contact"),
        AgentRelationship("person-1", "person-2", "friend"),
    )
    report = validate_agent_model(make_model(relationships=relationships))

    assert report.is_valid


def test_validator_allows_reverse_directed_relationships_as_distinct_edges():
    relationships = (
        AgentRelationship("person-1", "person-2", "follows", directed=True),
        AgentRelationship("person-2", "person-1", "follows", directed=True),
    )
    report = validate_agent_model(make_model(relationships=relationships))

    assert report.is_valid


def test_validator_detects_duplicate_behaviour_rule_ids():
    rule = BehaviourRule("same", AgentStateIs("susceptible"), (SetState("infected"),))
    report = validate_agent_model(make_model(behaviours=(rule, rule)))

    assert "DUPLICATE_RULE_ID" in issue_codes(report)


def test_validator_detects_rule_for_unknown_agent_type():
    rule = BehaviourRule(
        "rule", AgentStateIs("susceptible"), (SetState("infected"),), agent_type="vehicle"
    )
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "UNKNOWN_AGENT_TYPE" in issue_codes(report)


def test_validator_checks_ordered_attribute_comparison_value_type():
    condition = AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, "adult")
    rule = BehaviourRule("rule", condition, (SetState("adult"),))
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "NON_NUMERIC_ORDERED_COMPARISON" in issue_codes(report)


def test_validator_allows_equality_comparison_with_string_value():
    agents = (
        make_agent("person-1", attributes={"category": "A"}),
        make_agent("person-2", attributes={"category": "B"}),
    )
    condition = AgentAttributeComparison("category", ComparisonOperator.EQUAL, "A")
    rule = BehaviourRule("rule", condition, (SetState("matched"),))
    report = validate_agent_model(
        make_model(agents=agents, behaviours=(rule,))
    )

    assert report.is_valid


def test_validator_recursively_checks_nested_conditions():
    invalid_nested = AgentAttributeComparison("age", ComparisonOperator.LESS_THAN, False)
    condition = AnyOf((AgentStateIs("susceptible"), AllOf((invalid_nested,))))
    rule = BehaviourRule("rule", condition, (SetState("infected"),))
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "NON_NUMERIC_ORDERED_COMPARISON" in issue_codes(report)
    assert any("conditions[1].conditions[0]" in issue.path for issue in report.issues)


def test_validator_detects_unknown_condition_type():
    class CustomCondition(Condition):
        pass

    rule = BehaviourRule("rule", CustomCondition(), (SetState("infected"),))
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "UNSUPPORTED_CONDITION" in issue_codes(report)


def test_validator_detects_unknown_action_type():
    from simulations.abm.model import Action

    class CustomAction(Action):
        pass

    rule = BehaviourRule("rule", AgentStateIs("susceptible"), (CustomAction(),))
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "UNSUPPORTED_ACTION" in issue_codes(report)


def test_validator_requires_condition_attributes_on_applicable_agents():
    condition = AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 18)
    rule = BehaviourRule("rule", condition, (SetState("adult"),), agent_type="person")
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "MISSING_AGENT_ATTRIBUTE" in issue_codes(report)


def test_validator_checks_condition_attribute_for_every_target_agent():
    agents = (
        make_agent("person-1", attributes={"age": 25}),
        make_agent("person-2", attributes={}),
    )
    rule = BehaviourRule(
        "rule",
        AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 18),
        (SetState("adult"),),
    )
    report = validate_agent_model(make_model(agents=agents, behaviours=(rule,)))

    assert "MISSING_AGENT_ATTRIBUTE" in issue_codes(report)


def test_validator_accepts_attribute_condition_when_attribute_exists():
    agents = (
        make_agent("person-1", attributes={"age": 25}),
        make_agent("person-2", attributes={"age": 17}),
    )
    rule = BehaviourRule(
        "rule",
        AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 18),
        (SetState("adult"),),
        agent_type="person",
    )
    report = validate_agent_model(make_model(agents=agents, behaviours=(rule,)))

    assert report.is_valid


def test_validator_rejects_ordered_comparison_on_non_numeric_agent_attribute():
    agent = make_agent("person-1", attributes={"category": "A"})
    rule = BehaviourRule(
        "rule",
        AgentAttributeComparison("category", ComparisonOperator.GREATER_THAN, 1),
        (SetState("matched"),),
    )
    report = validate_agent_model(make_model(agents=(agent,), behaviours=(rule,)))

    assert "NON_NUMERIC_AGENT_ATTRIBUTE" in issue_codes(report)


def test_validator_rejects_increment_of_missing_attribute():
    rule = BehaviourRule(
        "rule",
        AgentStateIs("susceptible"),
        (IncrementAttribute("contacts", 1),),
    )
    report = validate_agent_model(make_model(behaviours=(rule,)))

    assert "MISSING_INCREMENT_ATTRIBUTE" in issue_codes(report)


def test_validator_rejects_increment_of_non_numeric_attribute():
    agent = make_agent("person-1", attributes={"contacts": "zero"})
    rule = BehaviourRule(
        "rule",
        AgentStateIs("susceptible"),
        (IncrementAttribute("contacts", 1),),
    )
    report = validate_agent_model(make_model(agents=(agent,), behaviours=(rule,)))

    assert "NON_NUMERIC_INCREMENT_ATTRIBUTE" in issue_codes(report)


def test_validator_accepts_increment_of_existing_numeric_attribute():
    agent = make_agent("person-1", attributes={"contacts": 0})
    rule = BehaviourRule(
        "rule",
        AgentStateIs("susceptible"),
        (IncrementAttribute("contacts", 1),),
    )
    report = validate_agent_model(
        make_model(agents=(agent,), relationships=(), behaviours=(rule,))
    )

    assert report.is_valid


def test_validator_does_not_reject_absent_relation_type_for_zero_neighbour_checks():
    condition = RelatedAgentStateCount(
        "missing-relation", "infected", ComparisonOperator.EQUAL, 0
    )
    rule = BehaviourRule("rule", condition, (SetState("isolated"),))
    report = validate_agent_model(make_model(relationships=(), behaviours=(rule,)))

    assert report.is_valid


def test_validation_report_separates_errors_and_warnings():
    report = ValidationReport(
        (
            ValidationIssue("agents", "NO_AGENTS", "At least one agent is required."),
            ValidationIssue(
                "behaviours",
                "NO_BEHAVIOURS",
                "No behaviour rules were supplied.",
                IssueSeverity.WARNING,
            ),
        )
    )

    assert len(report.errors) == 1
    assert len(report.warnings) == 1
    assert not report.is_valid
    with pytest.raises(ValueError, match="Invalid agent-based model"):
        report.raise_for_errors()


def test_validation_report_raise_for_errors_is_noop_when_valid():
    report = validate_agent_model(make_model())
    report.raise_for_errors()


def test_model_with_no_behaviours_is_valid_but_static():
    report = validate_agent_model(make_model(behaviours=()))

    assert report.is_valid
    # A rule-free model can still be used to inspect an initial population.
    assert report.warnings == ()
