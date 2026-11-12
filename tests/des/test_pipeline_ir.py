from simulations.des import pipeline
from simulations.des.representation import FactOrigin


def known(value):
    return {
        "value": value,
        "origin": "explicit",
    }


def hospital_payload(capacity=2, arrival_time=0):
    return {
        "scenario_name": known("Hospital"),
        "resources": [
            {
                "name": known("Doctor"),
                "capacity": (
                    None if capacity is None else known(capacity)
                ),
            },
        ],
        "jobs": [
            {
                "entity_id": known("Patient-1"),
                "arrival_time": (
                    None if arrival_time is None else known(arrival_time)
                ),
                "stages": [
                    {
                        "resource_name": known("Doctor"),
                        "service_duration": known(15),
                    },
                ],
            },
        ],
        "uncertainties": [],
    }


def test_new_ai_format_runs_through_complete_pipeline(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: hospital_payload(),
    )

    result = pipeline.run_prompt("Simulate a hospital.")

    assert result.validation_report.is_ready
    assert result.scenario is not None
    assert result.simulation_result.scenario_name == "Hospital"


def test_missing_information_prevents_execution(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: hospital_payload(arrival_time=None),
    )

    result = pipeline.run_prompt("Simulate a hospital.")

    assert not result.validation_report.is_ready
    assert result.simulation_result is None
    assert result.scenario is None


def test_approved_default_allows_execution(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: hospital_payload(capacity=None),
    )

    result = pipeline.run_prompt(
        "Simulate a hospital.",
        approve_defaults=lambda proposed: True,
    )

    assert result.validation_report.is_ready
    assert result.simulation_result is not None
    assert result.understanding.resources[0].capacity.value == 1
    assert (
        result.understanding.resources[0].capacity.origin
        == FactOrigin.DEFAULTED
    )
    assert len(result.default_resolution.applied) == 1


def test_unapproved_default_prevents_execution(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: hospital_payload(capacity=None),
    )

    result = pipeline.run_prompt("Simulate a hospital.")

    assert result.simulation_result is None
    assert not result.validation_report.is_ready
    assert len(result.default_resolution.proposed) == 1
    assert result.default_resolution.applied == ()
    
def test_pipeline_returns_backend_execution_metadata(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "generate_model",
        lambda request: hospital_payload(),
    )

    result = pipeline.run_prompt("Simulate a hospital.")

    assert result.specification is not None
    assert result.execution_result is not None
    assert result.execution_result.backend_name == "SimPy"
    assert (
        result.execution_result.paradigm
        == result.specification.paradigm
    )
    assert result.execution_result.native_result is result.simulation_result