from simulations.abm.model import AgentStateIs, BehaviourRule, SetState
from simulations.abm.pipeline import run_agent_prompt


def valid_data():
    return {
        "name": "Small disease spread",
        "agents": [
            {"reference": "infected_person", "agent_type": "person", "state": "infected", "attributes": {}},
            {"reference": "susceptible_person", "agent_type": "person", "state": "susceptible", "attributes": {}},
        ],
        "relationships": [
            {"source": "infected_person", "target": "susceptible_person", "relation_type": "contact", "directed": False}
        ],
        "behaviours": [
            {
                "rule_id": "infection",
                "agent_type": "person",
                "condition": {"type": "agent_state_is", "state": "susceptible"},
                "actions": [{"type": "set_state", "state": "infected"}],
                "probability": 1.0,
            }
        ],
        "termination": {"type": "max_steps", "value": 2},
    }


def test_pipeline_compiles_valid_model_and_executes_backend():
    result = run_agent_prompt("A person transmits infection to a connected susceptible person.", generate_fn=lambda _: valid_data())

    assert result.is_ready
    assert result.agent_model is not None
    assert result.execution_result.paradigm.value == "agent_based"
    assert result.simulation_result.steps_completed == 2
    assert result.simulation_result.final_state_counts == {"infected": 2}


def test_pipeline_returns_incomplete_model_without_running_it():
    data = valid_data()
    data["termination"]["value"] = None

    result = run_agent_prompt("A disease spread model", generate_fn=lambda _: data)

    assert not result.is_ready
    assert result.agent_model is None
    assert result.execution_result is None
    assert result.validation_report.errors[0].path == "termination.value"


def test_pipeline_asks_and_refines_missing_max_steps():
    data = valid_data()
    data["termination"]["value"] = None
    answers = []
    refinements = []

    def clarify(questions):
        answers.append(questions[0])
        return "Run it for 4 steps."

    def refine(original_request, current_data, history):
        refinements.append(history)
        revised = valid_data()
        revised["termination"]["value"] = 4
        return revised

    result = run_agent_prompt(
        "Simulate disease spread.",
        clarification_handler=clarify,
        generate_fn=lambda _: data,
        refine_fn=refine,
    )

    assert result.is_ready
    assert result.agent_model.termination.value == 4
    assert len(answers) == 1
    assert answers[0].path == "termination.value"
    assert len(result.clarification_history) == 1
    assert len(refinements) == 1


def test_pipeline_does_not_run_semantically_invalid_model():
    data = valid_data()
    data["behaviours"][0]["condition"] = {
        "type": "agent_attribute_comparison",
        "attribute": "age",
        "operator": "gt",
        "value": 18,
    }

    result = run_agent_prompt("Disease spread", generate_fn=lambda _: data)

    assert not result.is_ready
    assert result.execution_result is None
    assert any(issue.code == "MISSING_AGENT_ATTRIBUTE" for issue in result.validation_report.errors)


def test_pipeline_rejects_empty_request_before_ai_call():
    called = []
    try:
        run_agent_prompt("  ", generate_fn=lambda _: called.append(True))
    except ValueError as error:
        assert "non-empty" in str(error)
    else:
        raise AssertionError("Expected empty request to be rejected")

    assert called == []
