from simulations import pipeline
from simulations.scenario_understanding import FactOrigin
from simulations.scenario_understanding import FactOrigin


def known(value):
    return {
        "value": value,
        "origin": "explicit",
    }


def incomplete_clinic():
    return {
        "scenario_name": {
            "value": "Clinic",
            "origin": "inferred",
        },
        "resources": [
            {
                "name": known("Doctor"),
                "capacity": known(1),
            },
        ],
        "jobs": [
            {
                "entity_id": known("Patient-1"),
                "arrival_time": None,
                "stages": [
                    {
                        "resource_name": known("Doctor"),
                        "service_duration": known(5),
                    },
                ],
            },
        ],
        "uncertainties": [
            {
                "name": "jobs[0].arrival_time",
                "type": "missing",
                "description": "Arrival time is not specified.",
            },
        ],
    }


def completed_clinic():
    return {
        "scenario_name": {
            "value": "Clinic",
            "origin": "inferred",
        },
        "resources": [
            {
                "name": known("Doctor"),
                "capacity": known(1),
            },
        ],
        "jobs": [
            {
                "entity_id": known("Patient-1"),
                "arrival_time": known(0),
                "stages": [
                    {
                        "resource_name": known("Doctor"),
                        "service_duration": known(5),
                    },
                ],
            },
        ],
        "uncertainties": [],
    }


def test_clarification_resolves_missing_arrival_time(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: incomplete_clinic(),
    )

    monkeypatch.setattr(
        pipeline,
        "refine_model",
        lambda original_request, current_model_data, clarification_history:
            completed_clinic(),
    )

    received_questions = []

    def answer_questions(questions):
        received_questions.extend(questions)
        return "Patient 1 arrives at time 0 minutes."

    result = pipeline.run_prompt(
        "Simulate a clinic.",
        clarification_handler=answer_questions,
    )

    assert result.validation_report.is_ready
    assert result.simulation_result is not None
    assert len(result.clarification_history) == 1
    assert any(
        question.path == "jobs[0].arrival_time"
        for question in received_questions
    )


def test_clarification_preserves_existing_facts(monkeypatch):
    initial = incomplete_clinic()

    revised = {
        "scenario_name": initial["scenario_name"],
        "jobs": [
            {
                "entity_id": known("Patient-1"),
                "arrival_time": known(0),
                "stages": initial["jobs"][0]["stages"],
            },
        ],
        "uncertainties": [],
    }

    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: initial,
    )

    monkeypatch.setattr(
        pipeline,
        "refine_model",
        lambda original_request, current_model_data, clarification_history:
            revised,
    )

    result = pipeline.run_prompt(
        "Simulate a clinic.",
        clarification_handler=lambda questions: (
            "Patient 1 arrives at time 0."
        ),
    )

    assert result.simulation_result is not None
    assert result.understanding.resources[0].name.value == "Doctor"
    assert result.understanding.resources[0].capacity.value == 1


def test_blank_clarification_does_not_call_refinement(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: incomplete_clinic(),
    )

    refinement_calls = []

    def fake_refine(*args, **kwargs):
        refinement_calls.append(True)
        return completed_clinic()

    monkeypatch.setattr(pipeline, "refine_model", fake_refine)

    result = pipeline.run_prompt(
        "Simulate a clinic.",
        clarification_handler=lambda questions: "",
    )

    assert refinement_calls == []
    assert result.simulation_result is None
    assert result.validation_report.readiness.value == "incomplete"


def test_clarification_loop_stops_after_maximum_rounds(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: incomplete_clinic(),
    )

    monkeypatch.setattr(
        pipeline,
        "refine_model",
        lambda original_request, current_model_data, clarification_history:
            current_model_data,
    )

    rounds = []

    def answer_questions(questions):
        rounds.append(questions)
        return "I am not sure yet."

    result = pipeline.run_prompt(
        "Simulate a clinic.",
        clarification_handler=answer_questions,
        max_clarification_rounds=3,
    )

    assert len(rounds) == 3
    assert len(result.clarification_history) == 3
    assert result.simulation_result is None

def test_entity_id_is_regenerated_after_ai_refinement(monkeypatch):
    initial = incomplete_clinic()
    initial["jobs"][0]["entity_id"] = None

    revised = completed_clinic()
    revised["jobs"][0]["entity_id"] = None

    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: initial,
    )

    monkeypatch.setattr(
        pipeline,
        "refine_model",
        lambda original_request, current_model_data, clarification_history:
            revised,
    )

    result = pipeline.run_prompt(
        "Simulate a clinic.",
        clarification_handler=lambda questions: (
            "Patient arrives at time 0."
        ),
    )

    assert result.simulation_result is not None
    assert result.understanding.jobs[0].entity_id.value == "entity-1"
    assert (
        result.understanding.jobs[0].entity_id.origin == FactOrigin.SYSTEM_GENERATED
    )
    assert len(result.clarification_history) == 1