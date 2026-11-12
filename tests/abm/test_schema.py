import pytest

from simulations.abm.model import AllOf, RelatedAgentStateCount, SetState
from simulations.abm.schema import (
    ABMModelDataError,
    agent_model_from_dict,
    normalize_agent_model_data,
)


def base_data():
    return {
        "name": "Disease spread",
        "agents": [
            {"reference": "person_a", "agent_type": "person", "state": "infected", "attributes": {}},
            {"reference": "person_b", "agent_type": "person", "state": "susceptible", "attributes": {}},
        ],
        "environment": {"attributes": {"temperature": 25}},
        "relationships": [
            {"source": "person_a", "target": "person_b", "relation_type": "contact", "directed": False}
        ],
        "behaviours": [
            {
                "rule_id": "infect-neighbours",
                "agent_type": "person",
                "condition": {
                    "type": "all_of",
                    "conditions": [
                        {"type": "agent_state_is", "state": "susceptible"},
                        {
                            "type": "related_agent_state_count",
                            "relation_type": "contact",
                            "state": "infected",
                            "operator": "gt",
                            "count": 0,
                        },
                    ],
                },
                "actions": [{"type": "set_state", "state": "infected"}],
                "probability": 1.0,
            }
        ],
        "activation": {"mode": "sequential", "order": "declaration"},
        "termination": {"type": "max_steps", "value": 3},
        "random_seed": 17,
    }


def test_schema_compiles_agents_and_rewrites_relationship_aliases():
    model = agent_model_from_dict(base_data())

    assert [agent.identifier for agent in model.agents] == ["agent-1", "agent-2"]
    assert model.relationships[0].source_agent_id == "agent-1"
    assert model.relationships[0].target_agent_id == "agent-2"
    assert model.random_seed == 17


def test_schema_compiles_nested_conditions_and_actions():
    model = agent_model_from_dict(base_data())
    condition = model.behaviours[0].condition

    assert isinstance(condition, AllOf)
    assert isinstance(condition.conditions[1], RelatedAgentStateCount)
    assert isinstance(model.behaviours[0].actions[0], SetState)


def test_normalizer_generates_references_and_optional_metadata():
    normalized = normalize_agent_model_data({"agents": [{"agent_type": "person", "state": "well"}]})

    assert normalized["name"] == "Agent-Based Simulation"
    assert normalized["agents"][0]["reference"] == "agent_ref_1"
    assert normalized["agents"][0]["attributes"] == {}
    assert "relationships" not in normalized
    assert "behaviours" not in normalized


def test_schema_does_not_invent_missing_max_steps():
    data = base_data()
    data["termination"] = {"type": "max_steps", "value": None}

    with pytest.raises(ABMModelDataError, match="positive integer") as error:
        agent_model_from_dict(data)

    assert error.value.path == "termination.value"


def test_schema_rejects_unknown_relationship_reference():
    data = base_data()
    data["relationships"][0]["target"] = "missing"

    with pytest.raises(ABMModelDataError, match="Unknown agent reference"):
        agent_model_from_dict(data)


def test_schema_rejects_duplicate_agent_references():
    data = base_data()
    data["agents"][1]["reference"] = "person_a"

    with pytest.raises(ABMModelDataError, match="Duplicate agent reference"):
        agent_model_from_dict(data)


def test_schema_rejects_unsupported_activation_semantics():
    data = base_data()
    data["activation"] = {"mode": "random", "order": "random"}

    with pytest.raises(ABMModelDataError, match="sequential activation"):
        agent_model_from_dict(data)


def test_schema_rejects_unsupported_action_language():
    data = base_data()
    data["behaviours"][0]["actions"] = [{"type": "execute_python", "code": "x = 1"}]

    with pytest.raises(ABMModelDataError, match="Unsupported action type"):
        agent_model_from_dict(data)


def test_schema_requires_explicit_relationship_and_behaviour_collections():
    data = base_data()
    del data["relationships"]

    with pytest.raises(ABMModelDataError, match="explicitly provide this collection") as error:
        agent_model_from_dict(data)

    assert error.value.path == "relationships"


def test_schema_does_not_assume_unspecified_rule_probability_is_certain():
    data = base_data()
    data["behaviours"][0]["probability"] = None

    with pytest.raises(ABMModelDataError, match="Probability must be numeric") as error:
        agent_model_from_dict(data)

    assert error.value.path == "behaviours[0].probability"


def test_schema_rejects_arbitrary_top_level_fields():
    data = base_data()
    data["python_code"] = "print('unsafe')"

    with pytest.raises(ABMModelDataError, match="Unsupported field"):
        agent_model_from_dict(data)


def test_schema_wraps_invalid_agent_attribute_value_with_field_path():
    data = base_data()
    data["agents"][0]["attributes"] = {"profile": {"nested": True}}

    with pytest.raises(ABMModelDataError, match="JSON-compatible scalar") as error:
        agent_model_from_dict(data)

    assert error.value.path == "agents[0]"


def test_schema_wraps_invalid_environment_attribute_value_with_field_path():
    data = base_data()
    data["environment"]["attributes"] = {"profile": [1, 2]}

    with pytest.raises(ABMModelDataError, match="JSON-compatible scalar") as error:
        agent_model_from_dict(data)

    assert error.value.path == "environment.attributes"


def test_schema_wraps_invalid_action_value_with_field_path():
    data = base_data()
    data["behaviours"][0]["actions"] = [
        {"type": "set_attribute", "attribute": "profile", "value": [1, 2]}
    ]

    with pytest.raises(ABMModelDataError, match="JSON-compatible scalar") as error:
        agent_model_from_dict(data)

    assert error.value.path == "behaviours[0].actions[0].value"


def test_project_disease_transmission_example_is_parseable():
    import json
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    example = json.loads(
        (project_root / "scenarios" / "disease_transmission_abm.json").read_text(encoding="utf-8")
    )
    model = agent_model_from_dict(example)

    assert model.name == "Small Disease Transmission Network"
    assert len(model.agents) == 3
    assert len(model.relationships) == 3
