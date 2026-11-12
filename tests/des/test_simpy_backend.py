import pytest

from simulations.des.model import (
    Scenario,
    ScenarioResource,
    ServiceJob,
    ServiceStage,
)
from simulations.des.backend import SimPyBackend
from simulations.core.specification import (
    SimulationParadigm,
    SimulationSpecification,
)


def create_scenario():
    return Scenario(
        name="Clinic",
        resources=(
            ScenarioResource("Doctor", 1),
        ),
        jobs=(
            ServiceJob(
                entity_id="entity-1",
                arrival_time=0,
                stages=(
                    ServiceStage("Doctor", 5),
                ),
            ),
        ),
    )


def test_simpy_backend_executes_discrete_event_scenario():
    specification = SimulationSpecification(
        name="Clinic",
        paradigm=SimulationParadigm.DISCRETE_EVENT,
        model=create_scenario(),
    )

    result = SimPyBackend().execute(specification)

    assert result.backend_name == "SimPy"
    assert result.specification_name == "Clinic"
    assert result.paradigm == SimulationParadigm.DISCRETE_EVENT
    assert result.native_result.completion_time == 5
    assert len(result.native_result.entity_metrics) == 1


def test_simpy_backend_returns_standardized_metrics():
    specification = SimulationSpecification(
        name="Clinic",
        paradigm=SimulationParadigm.DISCRETE_EVENT,
        model=create_scenario(),
    )

    result = SimPyBackend().execute(specification)

    metrics = {
        metric.name: metric.value
        for metric in result.metrics
    }

    assert metrics["average_waiting_time"] == 0
    assert metrics["completion_time"] == 5
    assert metrics["entities_completed"] == 1


def test_simpy_backend_rejects_other_paradigms():
    specification = SimulationSpecification(
        name="Agent Model",
        paradigm=SimulationParadigm.AGENT_BASED,
        model=create_scenario(),
    )

    with pytest.raises(ValueError, match="does not support"):
        SimPyBackend().execute(specification)


def test_simpy_backend_rejects_uncompiled_models():
    specification = SimulationSpecification(
        name="Clinic",
        paradigm=SimulationParadigm.DISCRETE_EVENT,
        model={"jobs": []},
    )

    with pytest.raises(TypeError, match="compiled Scenario"):
        SimPyBackend().execute(specification)