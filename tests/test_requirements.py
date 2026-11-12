import pytest

from simulations.requirements import (
    RequirementStatus,
    ScenarioReadiness,
    evaluate_requirements,
)
from simulations.scenario_ir import (
    JobUnderstanding,
    KnownValue,
    ResourceUnderstanding,
    ScenarioIR,
    StageUnderstanding,
)
from simulations.scenario_understanding import (
    FactOrigin,
    ScenarioUncertainty,
    UncertaintyType,
)


def known(value):
    return KnownValue(value, FactOrigin.EXPLICIT)


def complete_scenario():
    return ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(
            ResourceUnderstanding(known("Doctor"), known(3)),
            ResourceUnderstanding(known("Nurse"), known(2)),
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
            JobUnderstanding(
                entity_id=known("Patient-2"),
                arrival_time=known(5),
                stages=(
                    StageUnderstanding(known("Doctor"), known(20)),
                ),
            ),
        ),
    )


def test_complete_scenario_is_ready():
    report = evaluate_requirements(complete_scenario())

    assert report.readiness == ScenarioReadiness.READY
    assert report.is_ready
    assert not report.has_errors


def test_missing_fields_are_all_reported():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(
            ResourceUnderstanding(name=known("Doctor")),
        ),
        jobs=(
            JobUnderstanding(
                entity_id=known("Patient-1"),
                arrival_time=None,
                stages=None,
            ),
        ),
    )

    report = evaluate_requirements(scenario)
    missing_paths = {
        result.path
        for result in report.results
        if result.status == RequirementStatus.MISSING
    }

    assert "jobs[0].arrival_time" in missing_paths
    assert "jobs[0].stages" in missing_paths
    assert report.readiness == ScenarioReadiness.INCOMPLETE


def test_missing_capacity_reports_available_default():
    scenario = complete_scenario()
    first_resource = scenario.resources[0]

    scenario = ScenarioIR(
        scenario_name=scenario.scenario_name,
        resources=(
            ResourceUnderstanding(first_resource.name, None),
            scenario.resources[1],
        ),
        jobs=scenario.jobs,
    )

    report = evaluate_requirements(scenario)
    result = next(
        item for item in report.results
        if item.path == "resources[0].capacity"
    )

    assert result.status == RequirementStatus.DEFAULT_AVAILABLE
    assert report.readiness == ScenarioReadiness.INCOMPLETE


def test_capacity_default_is_not_silently_applied():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(ResourceUnderstanding(name=known("Doctor")),),
        jobs=complete_scenario().jobs,
    )

    report = evaluate_requirements(scenario)

    result = next(
        item for item in report.results
        if item.path == "resources[0].capacity"
    )

    assert result.actual_value is None
    assert result.status == RequirementStatus.DEFAULT_AVAILABLE


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), "15", True])
def test_invalid_service_duration_is_rejected(duration):
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(ResourceUnderstanding(known("Doctor"), known(1)),),
        jobs=(
            JobUnderstanding(
                known("Patient-1"),
                known(0),
                (StageUnderstanding(known("Doctor"), known(duration)),),
            ),
        ),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.INVALID
    assert any(
        item.path == "jobs[0].stages[0].service_duration"
        and item.status == RequirementStatus.INVALID
        for item in report.results
    )


def test_unknown_resource_reference_is_rejected():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(ResourceUnderstanding(known("Doctor"), known(1)),),
        jobs=(
            JobUnderstanding(
                known("Patient-1"),
                known(0),
                (StageUnderstanding(known("Nurse"), known(15)),),
            ),
        ),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.INVALID
    assert any(
        item.path == "jobs[0].stages[0].resource_reference"
        for item in report.results
    )


def test_duplicate_job_ids_are_rejected():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(ResourceUnderstanding(known("Doctor"), known(1)),),
        jobs=(
            JobUnderstanding(
                known("Patient-1"),
                known(0),
                (StageUnderstanding(known("Doctor"), known(15)),),
            ),
            JobUnderstanding(
                known("Patient-1"),
                known(5),
                (StageUnderstanding(known("Doctor"), known(20)),),
            ),
        ),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.INVALID


def test_ambiguous_information_requires_clarification():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        uncertainties=(
            ScenarioUncertainty(
                "jobs[0].arrival_time",
                UncertaintyType.AMBIGUOUS,
                "The arrival time is unclear.",
            ),
        ),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.NEEDS_CLARIFICATION


def test_empty_resources_and_jobs_are_invalid():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(),
        jobs=(),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.INVALID
    assert report.has_errors


def test_zero_service_duration_is_valid():
    scenario = ScenarioIR(
        scenario_name=known("Hospital"),
        resources=(ResourceUnderstanding(known("Doctor"), known(1)),),
        jobs=(
            JobUnderstanding(
                known("Patient-1"),
                known(0),
                (StageUnderstanding(known("Doctor"), known(0)),),
            ),
        ),
    )

    report = evaluate_requirements(scenario)

    assert report.readiness == ScenarioReadiness.READY


def test_invalid_root_input_is_rejected():
    with pytest.raises(TypeError):
        evaluate_requirements("Hospital")