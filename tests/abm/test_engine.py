import pytest

from simulations.abm.engine import (
    ABMSimulationResult,
    AgentBasedSimulationEngine,
    SimulationExecutionError,
    run_agent_model,
)
from simulations.abm.model import (
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
    IncrementAttribute,
    MaxSteps,
    RelatedAgentStateCount,
    SetAttribute,
    SetState,
)


def agent(identifier, state="susceptible", attributes=None, agent_type="person"):
    return Agent(identifier, agent_type, state, attributes or {})


def infection_rule(probability=1.0, agent_type="person"):
    return BehaviourRule(
        "infection",
        AllOf(
            (
                AgentStateIs("susceptible"),
                RelatedAgentStateCount(
                    "contact", "infected", ComparisonOperator.GREATER_THAN, 0
                ),
            )
        ),
        (SetState("infected"),),
        agent_type=agent_type,
        probability=probability,
    )


def make_model(agents=None, relationships=(), behaviours=None, steps=1, seed=7, **kwargs):
    return AgentModel(
        name="ABM test",
        agents=tuple((agent("p1", "infected"), agent("p2"), agent("p3")) if agents is None else agents),
        relationships=tuple(relationships),
        behaviours=tuple((infection_rule(),) if behaviours is None else behaviours),
        termination=MaxSteps(steps),
        random_seed=seed,
        **kwargs,
    )


def state_map(result):
    return {item.identifier: item.state for item in result.final_agents}


def test_engine_returns_initial_snapshot_and_one_snapshot_per_step():
    result = run_agent_model(make_model(steps=3, behaviours=()))

    assert isinstance(result, ABMSimulationResult)
    assert [item.step for item in result.history] == [0, 1, 2, 3]
    assert result.steps_completed == 3


def test_initial_snapshot_preserves_model_state_and_attributes():
    model = make_model(
        agents=(agent("p1", "susceptible", {"age": 25}),),
        behaviours=(),
    )
    result = run_agent_model(model)

    snapshot = result.history[0].agent("p1")
    assert snapshot.state == "susceptible"
    assert snapshot.attributes["age"] == 25
    with pytest.raises(TypeError):
        snapshot.attributes["age"] = 30


def test_agent_state_condition_and_set_state_action_execute():
    rule = BehaviourRule("activate", AgentStateIs("susceptible"), (SetState("active"),))
    result = run_agent_model(make_model(agents=(agent("p1"),), behaviours=(rule,)))

    assert state_map(result) == {"p1": "active"}
    assert result.rule_evaluations[0].actions_applied


def test_rules_execute_in_declaration_order_and_see_prior_rule_updates():
    rules = (
        BehaviourRule("expose", AgentStateIs("susceptible"), (SetState("exposed"),)),
        BehaviourRule("infect", AgentStateIs("exposed"), (SetState("infected"),)),
    )
    result = run_agent_model(make_model(agents=(agent("p1"),), behaviours=rules))

    assert state_map(result) == {"p1": "infected"}
    assert [event.rule_id for event in result.rule_evaluations] == ["expose", "infect"]
    assert result.rule_evaluations[1].state_before == "exposed"


def test_later_agents_observe_immediate_updates_from_earlier_agents():
    model = make_model(
        agents=(agent("p1", "infected"), agent("p2"), agent("p3")),
        relationships=(
            AgentRelationship("p1", "p2", "contact"),
            AgentRelationship("p2", "p3", "contact"),
        ),
    )
    result = run_agent_model(model)

    assert state_map(result) == {
        "p1": "infected",
        "p2": "infected",
        "p3": "infected",
    }


def test_activation_order_effect_is_visible_across_steps():
    model = make_model(
        agents=(agent("p3"), agent("p2"), agent("p1", "infected")),
        relationships=(
            AgentRelationship("p1", "p2", "contact"),
            AgentRelationship("p2", "p3", "contact"),
        ),
        steps=2,
    )
    result = run_agent_model(model)

    assert result.history[1].agent("p3").state == "susceptible"
    assert result.history[1].agent("p2").state == "infected"
    assert result.history[2].agent("p3").state == "infected"


def test_undirected_relationships_are_visible_from_both_endpoints():
    model = make_model(
        agents=(agent("p1", "infected"), agent("p2")),
        relationships=(AgentRelationship("p1", "p2", "contact"),),
    )
    result = run_agent_model(model)

    assert state_map(result)["p2"] == "infected"


def test_directed_relationships_are_visible_from_source_to_target():
    # The source agent can inspect the target as an outgoing neighbour.
    model = make_model(
        agents=(agent("p1"), agent("p2", "infected")),
        relationships=(
            AgentRelationship("p1", "p2", "contact", directed=True),
        ),
    )
    result = run_agent_model(model)

    assert state_map(result)["p1"] == "infected"

    # Reversing the edge means p1 is now only a target, not an observer of p2.
    reverse_model = make_model(
        agents=(agent("p1"), agent("p2", "infected")),
        relationships=(
            AgentRelationship("p2", "p1", "contact", directed=True),
        ),
    )
    reverse_result = run_agent_model(reverse_model)
    assert state_map(reverse_result)["p1"] == "susceptible"


def test_attribute_comparison_and_increment_action():
    rule = BehaviourRule(
        "age-update",
        AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN_OR_EQUAL, 18),
        (IncrementAttribute("visits", 2),),
    )
    model = make_model(
        agents=(agent("p1", attributes={"age": 20, "visits": 1}),),
        behaviours=(rule,),
    )
    result = run_agent_model(model)

    assert result.final_agents[0].attributes["visits"] == 3


def test_set_attribute_can_create_an_attribute():
    rule = BehaviourRule(
        "add-score", AgentStateIs("susceptible"), (SetAttribute("score", 10),)
    )
    result = run_agent_model(make_model(agents=(agent("p1"),), behaviours=(rule,)))

    assert result.final_agents[0].attributes["score"] == 10


def test_all_of_and_any_of_conditions_are_evaluated():
    condition = AnyOf(
        (
            AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 30),
            AllOf(
                (
                    AgentStateIs("susceptible"),
                    AgentAttributeComparison("age", ComparisonOperator.EQUAL, 20),
                )
            ),
        )
    )
    rule = BehaviourRule("condition-test", condition, (SetState("matched"),))
    result = run_agent_model(
        make_model(agents=(agent("p1", attributes={"age": 20}),), behaviours=(rule,))
    )

    assert state_map(result)["p1"] == "matched"


@pytest.mark.parametrize("probability,expected", [(0.0, "susceptible"), (1.0, "infected")])
def test_zero_and_one_probabilities_are_deterministic(probability, expected):
    model = make_model(
        agents=(agent("p1", "infected"), agent("p2")),
        relationships=(AgentRelationship("p1", "p2", "contact"),),
        behaviours=(infection_rule(probability=probability),),
    )
    result = run_agent_model(model)

    assert state_map(result)["p2"] == expected


def test_seeded_probabilistic_execution_is_reproducible():
    agents = (agent("source", "infected"),) + tuple(
        agent(f"p{i}") for i in range(30)
    )
    relationships = tuple(
        AgentRelationship("source", f"p{i}", "contact") for i in range(30)
    )
    rule = infection_rule(probability=0.4)
    model = make_model(
        agents=agents,
        relationships=relationships,
        behaviours=(rule,),
        seed=12345,
    )

    first = run_agent_model(model)
    second = run_agent_model(model)

    assert state_map(first) == state_map(second)
    assert first.final_state_counts == second.final_state_counts
    assert first.rule_evaluations == second.rule_evaluations


def test_rule_trace_records_non_matching_rules_without_probability_draw():
    rule = BehaviourRule("not-yet", AgentStateIs("infected"), (SetState("recovered"),), probability=0.5)
    result = run_agent_model(make_model(agents=(agent("p1"),), behaviours=(rule,)))
    event = result.rule_evaluations[0]

    assert not event.condition_matched
    assert event.probability_passed is None
    assert not event.actions_applied


def test_rule_type_filter_skips_agents_of_other_types():
    rule = BehaviourRule(
        "person-only", AgentStateIs("susceptible"), (SetState("active"),), agent_type="person"
    )
    result = run_agent_model(
        make_model(
            agents=(agent("p1", agent_type="person"), agent("v1", agent_type="vehicle")),
            behaviours=(rule,),
        )
    )

    assert state_map(result) == {"p1": "active", "v1": "susceptible"}
    assert [event.agent_id for event in result.rule_evaluations] == ["p1"]


def test_trajectory_returns_each_step_for_one_agent():
    rule = BehaviourRule("step", AgentStateIs("susceptible"), (SetState("infected"),))
    result = run_agent_model(make_model(agents=(agent("p1"),), behaviours=(rule,), steps=2))
    trajectory = result.trajectory("p1")

    assert [point.step for point in trajectory] == [0, 1, 2]
    assert [point.state for point in trajectory] == ["susceptible", "infected", "infected"]
    with pytest.raises(KeyError):
        result.trajectory("missing")


def test_final_state_counts_are_correct_and_immutable():
    rules = (BehaviourRule("infect", AgentStateIs("susceptible"), (SetState("infected"),)),)
    result = run_agent_model(make_model(agents=(agent("p1"), agent("p2", "infected")), behaviours=rules))

    assert dict(result.final_state_counts) == {"infected": 2}
    with pytest.raises(TypeError):
        result.final_state_counts["susceptible"] = 1


def test_invalid_model_is_rejected_before_execution():
    model = make_model(agents=(), behaviours=())
    with pytest.raises(ValueError, match="Invalid agent-based model"):
        run_agent_model(model)


def test_runtime_attribute_type_change_produces_contextual_error():
    rules = (
        BehaviourRule("change", AgentStateIs("susceptible"), (SetAttribute("age", "unknown"),)),
        BehaviourRule(
            "compare",
            AgentAttributeComparison("age", ComparisonOperator.GREATER_THAN, 18),
            (SetState("adult"),),
        ),
    )
    model = make_model(
        agents=(agent("p1", attributes={"age": 20}),),
        behaviours=rules,
    )
    with pytest.raises(SimulationExecutionError, match="ordered comparisons require finite numeric"):
        run_agent_model(model)


def test_rule_action_batch_does_not_partially_commit_on_runtime_error():
    from simulations.abm.engine import _RuntimeAgent

    rule = BehaviourRule(
        "bad-increment",
        AgentStateIs("susceptible"),
        (SetAttribute("visits", "many"), IncrementAttribute("visits", 1)),
    )
    runtime = _RuntimeAgent("p1", "person", "susceptible", {"visits": 0})

    with pytest.raises(SimulationExecutionError):
        AgentBasedSimulationEngine()._apply_actions(runtime, rule, step=1)

    assert runtime.state == "susceptible"
    assert runtime.attributes == {"visits": 0}


def test_execution_does_not_mutate_the_input_model():
    initial_agent = agent("p1", attributes={"visits": 0})
    rule = BehaviourRule(
        "increment", AgentStateIs("susceptible"), (IncrementAttribute("visits", 1),)
    )
    model = make_model(agents=(initial_agent,), behaviours=(rule,), steps=2)

    result = run_agent_model(model)

    assert model.agents[0].attributes["visits"] == 0
    assert result.final_agents[0].attributes["visits"] == 2


def test_engine_rejects_non_agent_model_input():
    with pytest.raises(TypeError, match="AgentModel"):
        AgentBasedSimulationEngine().run({"name": "invalid"})


def test_boolean_equality_is_not_treated_as_numeric_equality():
    rule = BehaviourRule(
        "bool-not-one",
        AgentAttributeComparison("flag", ComparisonOperator.EQUAL, 1),
        (SetState("matched"),),
    )
    result = run_agent_model(
        make_model(agents=(agent("p1", attributes={"flag": True}),), behaviours=(rule,))
    )

    assert state_map(result)["p1"] == "susceptible"
