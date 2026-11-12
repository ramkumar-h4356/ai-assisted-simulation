from simulations.scenario_ir import (
    JobUnderstanding,
    KnownValue,
    ScenarioIR,
)
from simulations.scenario_normalizer import normalize_scenario_ir
from simulations.scenario_understanding import FactOrigin


def known(value):
    return KnownValue(value, FactOrigin.EXPLICIT)


def test_generates_missing_entity_identifier():
    scenario = ScenarioIR(
        scenario_name=known("Clinic"),
        jobs=(
            JobUnderstanding(
                arrival_time=known(0),
            ),
        ),
    )

    normalized = normalize_scenario_ir(scenario)

    identifier = normalized.jobs[0].entity_id

    assert identifier.value == "entity-1"
    assert identifier.origin == FactOrigin.SYSTEM_GENERATED


def test_generates_unique_identifiers_for_multiple_jobs():
    scenario = ScenarioIR(
        jobs=(
            JobUnderstanding(),
            JobUnderstanding(),
            JobUnderstanding(),
        ),
    )

    normalized = normalize_scenario_ir(scenario)

    identifiers = [
        job.entity_id.value
        for job in normalized.jobs
    ]

    assert identifiers == ["entity-1", "entity-2", "entity-3"]


def test_preserves_existing_identifiers():
    scenario = ScenarioIR(
        jobs=(
            JobUnderstanding(entity_id=known("Patient-A")),
            JobUnderstanding(),
        ),
    )

    normalized = normalize_scenario_ir(scenario)

    assert normalized.jobs[0].entity_id.value == "Patient-A"
    assert normalized.jobs[1].entity_id.value == "entity-1"


def test_avoids_collision_with_existing_identifier():
    scenario = ScenarioIR(
        jobs=(
            JobUnderstanding(entity_id=known("entity-1")),
            JobUnderstanding(),
        ),
    )

    normalized = normalize_scenario_ir(scenario)

    assert normalized.jobs[1].entity_id.value == "entity-2"


def test_does_not_modify_original_scenario():
    scenario = ScenarioIR(
        jobs=(JobUnderstanding(),),
    )

    normalized = normalize_scenario_ir(scenario)

    assert scenario.jobs[0].entity_id is None
    assert normalized.jobs[0].entity_id is not None


def test_unknown_job_collection_remains_unknown():
    scenario = ScenarioIR(jobs=None)

    normalized = normalize_scenario_ir(scenario)

    assert normalized.jobs is None