import pytest

from simulations.des.processing import apply_documented_defaults
from simulations.des.validation import evaluate_requirements, ScenarioReadiness
from simulations.des.model import Scenario
from simulations.des.compiler import (
    ScenarioCompilationError,
    compile_scenario,
)
from simulations.des.representation import (
    JobUnderstanding,
    KnownValue,
    ResourceUnderstanding,
    ScenarioIR,
    StageUnderstanding,
)
from simulations.des.representation import (
    FactOrigin,
    ScenarioUncertainty,
    UncertaintyType,
)


def known(value):
    return KnownValue(value, FactOrigin.EXPLICIT)


def complete_scenario_ir(capacity=2):
    return ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(
            ResourceUnderstanding(known("Doctor"), known(capacity)),
            ResourceUnderstanding(known("Nurse"), known(1)),
        ),
        jobs=(
            JobUnderstanding(
                entity_id=known("Patient-1"),
                arrival_time=known(0),
                stages=(
                    StageUnderstanding(known("Doctor"), known(15)),
                    StageUnderstanding(known("Nurse"), known(10)),
                ),
            ),
        ),
    )


def test_defaults_are_proposed_without_modifying_scenario():
    scenario = complete_scenario_ir()
    scenario = ScenarioIR(
        scenario_name=scenario.scenario_name,
        resources=(
            ResourceUnderstanding(known("Doctor")),
            scenario.resources[1],
        ),
        jobs=scenario.jobs,
    )

    resolution = apply_documented_defaults(scenario)

    assert len(resolution.proposed) == 1
    assert resolution.applied == ()
    assert resolution.scenario is scenario
    assert scenario.resources[0].capacity is None


def test_approved_defaults_are_recorded():
    scenario = complete_scenario_ir()
    scenario = ScenarioIR(
        scenario_name=scenario.scenario_name,
        resources=(
            ResourceUnderstanding(known("Doctor")),
            scenario.resources[1],
        ),
        jobs=scenario.jobs,
    )

    resolution = apply_documented_defaults(
        scenario,
        approve=True,
    )

    capacity = resolution.scenario.resources[0].capacity

    assert capacity.value == 1
    assert capacity.origin == FactOrigin.DEFAULTED
    assert len(resolution.applied) == 1
    assert evaluate_requirements(resolution.scenario).is_ready


def test_compiler_creates_executable_scenario():
    scenario = compile_scenario(complete_scenario_ir())

    assert isinstance(scenario, Scenario)
    assert scenario.name == "Hospital"
    assert len(scenario.resources) == 2
    assert len(scenario.jobs) == 1


def test_compiler_preserves_multiple_service_stages():
    scenario = compile_scenario(complete_scenario_ir())

    job = scenario.jobs[0]

    assert len(job.stages) == 2
    assert job.stages[0].resource_name == "Doctor"
    assert job.stages[0].service_duration == 15
    assert job.stages[1].resource_name == "Nurse"
    assert job.stages[1].service_duration == 10


def test_compiler_rejects_incomplete_scenario():
    scenario = complete_scenario_ir()
    scenario = ScenarioIR(
        scenario_name=scenario.scenario_name,
        resources=scenario.resources,
        jobs=(
            JobUnderstanding(
                entity_id=known("Patient-1"),
                arrival_time=None,
                stages=scenario.jobs[0].stages,
            ),
        ),
    )

    with pytest.raises(ScenarioCompilationError):
        compile_scenario(scenario)


def test_compiler_rejects_ambiguous_scenario():
    scenario = complete_scenario_ir()

    scenario = ScenarioIR(
        scenario_name=scenario.scenario_name,
        resources=scenario.resources,
        jobs=scenario.jobs,
        uncertainties=(
            ScenarioUncertainty(
                "jobs[0].arrival_time",
                UncertaintyType.AMBIGUOUS,
                "Arrival time is unclear.",
            ),
        ),
    )

    with pytest.raises(ScenarioCompilationError):
        compile_scenario(scenario)


def test_compiled_scenario_can_run_in_existing_engine():
    from simulations.des.backend import run_scenario

    scenario = compile_scenario(complete_scenario_ir())
    result = run_scenario(scenario)

    assert result.scenario_name == "Hospital"
    assert len(result.entity_metrics) == 1
    assert len(result.resource_metrics) == 2