
import pytest

from simulations.scenario_understanding import (
    FactOrigin,
    ReadinessStatus,
    ScenarioFact,
    ScenarioUnderstanding,
    ScenarioUncertainty,
    UncertaintyType,
    add_or_update_fact,
    evaluate_readiness,
    resolve_uncertainty,
    update_scenario,
)

def test_scenario_fact_creation():
    fact = ScenarioFact("doctor_capacity", 2, FactOrigin.EXPLICIT)

    assert fact.name == "doctor_capacity"
    assert fact.value == 2
    assert fact.origin == FactOrigin.EXPLICIT


def test_scenario_uncertainty_creation():
    uncertainty = ScenarioUncertainty(
        "consultation_duration",
        UncertaintyType.MISSING,
        "Duration not specified",
    )

    assert uncertainty.name == "consultation_duration"
    assert uncertainty.uncertainty_type == UncertaintyType.MISSING


def test_missing_information_makes_scenario_incomplete():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "duration",
                UncertaintyType.MISSING,
                "Duration not specified",
            ),
        ),
    )

    assert evaluate_readiness(scenario) == ReadinessStatus.INCOMPLETE


def test_ambiguous_information_needs_clarification():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "arrival_pattern",
                UncertaintyType.AMBIGUOUS,
                "Arrival pattern is unclear",
            ),
        ),
    )

    assert (
        evaluate_readiness(scenario)
        == ReadinessStatus.NEEDS_CLARIFICATION
    )


def test_no_uncertainties_means_ready():
    scenario = ScenarioUnderstanding("Hospital")

    assert evaluate_readiness(scenario) == ReadinessStatus.READY


def test_add_fact_preserves_existing_facts():
    scenario = ScenarioUnderstanding(
        "Hospital",
        facts=(
            ScenarioFact("entity_count", 5, FactOrigin.EXPLICIT),
        ),
    )

    updated = add_or_update_fact(
        scenario,
        ScenarioFact("doctor_capacity", 2, FactOrigin.EXPLICIT),
    )

    assert len(updated.facts) == 2
    assert updated.facts[0].name == "entity_count"
    assert updated.facts[1].name == "doctor_capacity"


def test_add_fact_replaces_existing_fact():
    scenario = ScenarioUnderstanding(
        "Hospital",
        facts=(
            ScenarioFact("doctor_capacity", 2, FactOrigin.EXPLICIT),
        ),
    )

    updated = add_or_update_fact(
        scenario,
        ScenarioFact("doctor_capacity", 3, FactOrigin.EXPLICIT),
    )

    assert len(updated.facts) == 1
    assert updated.facts[0].value == 3


def test_resolve_uncertainty_updates_readiness():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "duration",
                UncertaintyType.MISSING,
                "Duration not specified",
            ),
        ),
    )

    updated = resolve_uncertainty(scenario, "duration")

    assert updated.uncertainties == ()
    assert updated.readiness == ReadinessStatus.READY


def test_invalid_readiness_input():
    with pytest.raises(TypeError):
        evaluate_readiness("Hospital")

def test_atomic_update_adds_fact_and_resolves_missing_uncertainty():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "consultation_duration",
                UncertaintyType.MISSING,
                "Duration not specified",
            ),
        ),
    )

    updated = update_scenario(
        scenario,
        ScenarioFact("consultation_duration", 15, FactOrigin.EXPLICIT),
    )

    assert len(updated.facts) == 1
    assert updated.facts[0].value == 15
    assert updated.uncertainties == ()
    assert updated.readiness == ReadinessStatus.READY


def test_atomic_update_preserves_unrelated_uncertainties():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "consultation_duration",
                UncertaintyType.MISSING,
                "Duration missing",
            ),
            ScenarioUncertainty(
                "arrival_pattern",
                UncertaintyType.AMBIGUOUS,
                "Arrival pattern unclear",
            ),
        ),
    )

    updated = update_scenario(
        scenario,
        ScenarioFact("consultation_duration", 15, FactOrigin.EXPLICIT),
    )

    assert len(updated.uncertainties) == 1
    assert updated.uncertainties[0].name == "arrival_pattern"
    assert updated.readiness == ReadinessStatus.NEEDS_CLARIFICATION


def test_atomic_update_does_not_resolve_ambiguous_uncertainty():
    scenario = ScenarioUnderstanding(
        "Hospital",
        uncertainties=(
            ScenarioUncertainty(
                "arrival_pattern",
                UncertaintyType.AMBIGUOUS,
                "Arrival pattern unclear",
            ),
        ),
    )

    updated = update_scenario(
        scenario,
        ScenarioFact(
            "arrival_pattern",
            "every 10 minutes",
            FactOrigin.EXPLICIT,
        ),
    )

    assert len(updated.facts) == 1
    assert len(updated.uncertainties) == 1
    assert updated.readiness == ReadinessStatus.NEEDS_CLARIFICATION