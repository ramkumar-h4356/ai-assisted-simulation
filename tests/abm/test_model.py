from types import MappingProxyType

import pytest

from simulations.abm.model import (
    Action,
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
    BehaviourRule,
    ComparisonOperator,
    Condition,
    Environment,
    IncrementAttribute,
    MaxSteps,
    RelatedAgentStateCount,
    SetAttribute,
    SetState,
    TerminationCondition,
)


def make_agent(**overrides):
    values = {
        "identifier": "person-1",
        "agent_type": "person",
        "state": "susceptible",
        "attributes": {"age": 25, "active": True},
    }
    values.update(overrides)
    return Agent(**values)


def make_rule(**overrides):
    values = {
        "rule_id": "infection-rule",
        "condition": AgentStateIs("susceptible"),
        "actions": (SetState("infected"),),
    }
    values.update(overrides)
    return BehaviourRule(**values)


def test_agent_copies_and_freezes_attributes():
    attributes = {"age": 25}
    agent = make_agent(attributes=attributes)

    attributes["age"] = 99

    assert agent.attributes["age"] == 25
    assert isinstance(agent.attributes, MappingProxyType)
    with pytest.raises(TypeError):
        agent.attributes["age"] = 30


@pytest.mark.parametrize(
    "field,value",
    [
        ("identifier", ""),
        ("identifier", "   "),
        ("agent_type", ""),
        ("state", ""),
    ],
)
def test_agent_requires_non_empty_identity_fields(field, value):
    with pytest.raises(ValueError):
        make_agent(**{field: value})


def test_agent_attributes_must_be_a_mapping():
    with pytest.raises(TypeError):
        make_agent(attributes=[("age", 25)])


@pytest.mark.parametrize("value", [[1, 2], {"nested": True}, object()])
def test_agent_attributes_only_accept_scalar_values(value):
    with pytest.raises(TypeError):
        make_agent(attributes={"invalid": value})


def test_agent_attributes_reject_non_finite_floats():
    with pytest.raises(ValueError):
        make_agent(attributes={"temperature": float("inf")})


def test_environment_copies_and_freezes_attributes():
    attributes = {"temperature": 25.0}
    environment = Environment(attributes)
    attributes["temperature"] = 0.0

    assert environment.attributes["temperature"] == 25.0
    with pytest.raises(TypeError):
        environment.attributes["temperature"] = 10.0


def test_relationship_accepts_directed_and_undirected_edges():
    directed = AgentRelationship("a", "b", "contact", directed=True)
    undirected = AgentRelationship("a", "b", "contact")

    assert directed.directed is True
    assert undirected.directed is False


def test_relationship_requires_non_empty_endpoints_and_type():
    with pytest.raises(ValueError):
        AgentRelationship("", "b", "contact")
    with pytest.raises(ValueError):
        AgentRelationship("a", "", "contact")
    with pytest.raises(ValueError):
        AgentRelationship("a", "b", "")


def test_relationship_directed_flag_must_be_boolean():
    with pytest.raises(TypeError):
        AgentRelationship("a", "b", "contact", directed=1)


def test_agent_state_condition():
    assert AgentStateIs("infected").state == "infected"


def test_agent_state_condition_rejects_empty_state():
    with pytest.raises(ValueError):
        AgentStateIs(" ")


def test_attribute_comparison_accepts_supported_operator():
    condition = AgentAttributeComparison(
        "age", ComparisonOperator.GREATER_THAN_OR_EQUAL, 18
    )

    assert condition.attribute == "age"
    assert condition.value == 18


def test_attribute_comparison_requires_operator_enum():
    with pytest.raises(TypeError):
        AgentAttributeComparison("age", "gt", 18)


def test_related_agent_state_count_accepts_zero():
    condition = RelatedAgentStateCount(
        "contact", "infected", ComparisonOperator.EQUAL, 0
    )

    assert condition.count == 0


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_related_agent_state_count_rejects_invalid_count(count):
    with pytest.raises((TypeError, ValueError)):
        RelatedAgentStateCount(
            "contact", "infected", ComparisonOperator.GREATER_THAN, count
        )


@pytest.mark.parametrize("condition_type", [AllOf, AnyOf])
def test_composite_conditions_require_non_empty_tuple(condition_type):
    with pytest.raises(ValueError):
        condition_type(())


@pytest.mark.parametrize("condition_type", [AllOf, AnyOf])
def test_composite_conditions_reject_non_condition_items(condition_type):
    with pytest.raises(TypeError):
        condition_type((AgentStateIs("ready"), "not-a-condition"))


def test_composite_conditions_preserve_nested_conditions():
    nested = AllOf(
        (
            AgentStateIs("susceptible"),
            AnyOf(
                (
                    AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 18),
                    RelatedAgentStateCount(
                        "contact", "infected", ComparisonOperator.GREATER_THAN, 0
                    ),
                )
            ),
        )
    )

    assert len(nested.conditions) == 2
    assert isinstance(nested.conditions[1], AnyOf)


def test_set_state_action():
    assert SetState("infected").state == "infected"


def test_set_attribute_action():
    action = SetAttribute("risk_score", 0.75)
    assert action.attribute == "risk_score"
    assert action.value == 0.75


def test_increment_attribute_requires_finite_numeric_amount():
    assert IncrementAttribute("contacts", 1).amount == 1
    with pytest.raises(TypeError):
        IncrementAttribute("contacts", True)
    with pytest.raises(ValueError):
        IncrementAttribute("contacts", float("nan"))


@pytest.mark.parametrize("probability", [0.0, 0.2, 1.0])
def test_behaviour_rule_accepts_probability_boundaries(probability):
    assert make_rule(probability=probability).probability == probability


@pytest.mark.parametrize("probability", [-0.01, 1.01, float("inf"), float("nan"), True])
def test_behaviour_rule_rejects_invalid_probability(probability):
    with pytest.raises((TypeError, ValueError)):
        make_rule(probability=probability)


def test_behaviour_rule_requires_at_least_one_action():
    with pytest.raises(ValueError):
        make_rule(actions=())


def test_behaviour_rule_rejects_non_action_items():
    with pytest.raises(TypeError):
        make_rule(actions=(SetState("infected"), "print('unsafe')"))


def test_behaviour_rule_accepts_optional_agent_type_filter():
    rule = make_rule(agent_type="person")
    assert rule.agent_type == "person"


def test_activation_policy_is_sequential_in_declaration_order():
    policy = ActivationPolicy()
    assert policy.mode is ActivationMode.SEQUENTIAL
    assert policy.order is ActivationOrder.DECLARATION


def test_activation_policy_rejects_unsupported_values():
    with pytest.raises(TypeError):
        ActivationPolicy(mode="random")
    with pytest.raises(TypeError):
        ActivationPolicy(order="random")


def test_max_steps_requires_positive_integer():
    assert MaxSteps(10).value == 10
    with pytest.raises(TypeError):
        MaxSteps(True)
    with pytest.raises(TypeError):
        MaxSteps(1.5)
    with pytest.raises(ValueError):
        MaxSteps(0)


def test_agent_model_defaults_and_seed():
    model = AgentModel(
        name="Disease transmission",
        agents=(make_agent(),),
        termination=MaxSteps(5),
        random_seed=42,
    )

    assert model.environment == Environment()
    assert model.relationships == ()
    assert model.behaviours == ()
    assert model.activation == ActivationPolicy()
    assert model.random_seed == 42


def test_agent_model_rejects_non_tuple_agents():
    with pytest.raises(TypeError):
        AgentModel("model", [make_agent()], MaxSteps(1))


def test_agent_model_rejects_invalid_agent_items():
    with pytest.raises(TypeError):
        AgentModel("model", ("agent",), MaxSteps(1))


def test_agent_model_rejects_invalid_relationships_and_behaviours():
    with pytest.raises(TypeError):
        AgentModel("model", (make_agent(),), MaxSteps(1), relationships=("edge",))
    with pytest.raises(TypeError):
        AgentModel("model", (make_agent(),), MaxSteps(1), behaviours=("rule",))


def test_agent_model_rejects_invalid_component_types():
    with pytest.raises(TypeError):
        AgentModel("model", (make_agent(),), MaxSteps(1), environment={})
    with pytest.raises(TypeError):
        AgentModel("model", (make_agent(),), MaxSteps(1), activation="sequential")
    with pytest.raises(TypeError):
        AgentModel("model", (make_agent(),), "max_steps")


@pytest.mark.parametrize("seed", [-1, True, 1.5, "42"])
def test_agent_model_rejects_invalid_random_seed(seed):
    with pytest.raises((TypeError, ValueError)):
        AgentModel("model", (make_agent(),), MaxSteps(1), random_seed=seed)


def test_agent_model_rejects_empty_name():
    with pytest.raises(ValueError):
        AgentModel(" ", (make_agent(),), MaxSteps(1))


def test_marker_base_classes_are_not_concrete_rule_types():
    model = AgentModel(
        "model",
        (make_agent(),),
        MaxSteps(1),
        behaviours=(make_rule(condition=Condition()),),
    )
    assert isinstance(model.behaviours[0].condition, Condition)
    assert isinstance(Action(), Action)
