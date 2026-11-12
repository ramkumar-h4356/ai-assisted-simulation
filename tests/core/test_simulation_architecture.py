import pytest

from simulations.core.registry import BackendRegistry
from simulations.core.backend import (
    SimulationExecutionResult,
    SimulationMetric,
)
from simulations.core.specification import (
    SimulationParadigm,
    SimulationSpecification,
)


class FakeBackend:
    name = "Fake DES Backend"
    paradigm = SimulationParadigm.DISCRETE_EVENT

    def execute(self, specification):
        return SimulationExecutionResult(
            specification_name=specification.name,
            paradigm=self.paradigm,
            backend_name=self.name,
            metrics=(
                SimulationMetric(
                    "completion_time",
                    10,
                    "minutes",
                ),
            ),
            native_result={"events": 5},
        )


def test_creates_discrete_event_specification():
    specification = SimulationSpecification(
        "Hospital",
        SimulationParadigm.DISCRETE_EVENT,
        {"example": "model"},
    )

    assert specification.name == "Hospital"
    assert specification.paradigm == SimulationParadigm.DISCRETE_EVENT


def test_rejects_empty_simulation_name():
    with pytest.raises(ValueError):
        SimulationSpecification(
            "",
            SimulationParadigm.DISCRETE_EVENT,
            {},
        )


def test_rejects_invalid_paradigm():
    with pytest.raises(TypeError):
        SimulationSpecification(
            "Hospital",
            "discrete_event",
            {},
        )


def test_rejects_missing_model():
    with pytest.raises(ValueError):
        SimulationSpecification(
            "Hospital",
            SimulationParadigm.DISCRETE_EVENT,
            None,
        )


def test_registers_and_retrieves_backend():
    registry = BackendRegistry()
    backend = FakeBackend()

    registry.register(backend)

    assert registry.get(
        SimulationParadigm.DISCRETE_EVENT
    ) is backend


def test_rejects_duplicate_backend_registration():
    registry = BackendRegistry()
    registry.register(FakeBackend())

    with pytest.raises(ValueError):
        registry.register(FakeBackend())


def test_rejects_unregistered_paradigm():
    registry = BackendRegistry()

    with pytest.raises(LookupError):
        registry.get(SimulationParadigm.AGENT_BASED)


def test_reports_only_registered_paradigms():
    registry = BackendRegistry()
    registry.register(FakeBackend())

    assert registry.supported_paradigms == (
        SimulationParadigm.DISCRETE_EVENT,
    )


def test_backend_executes_specification():
    backend = FakeBackend()

    specification = SimulationSpecification(
        "Hospital",
        SimulationParadigm.DISCRETE_EVENT,
        {"example": "model"},
    )

    result = backend.execute(specification)

    assert result.specification_name == "Hospital"
    assert result.backend_name == "Fake DES Backend"
    assert result.metrics[0].value == 10
    assert result.native_result == {"events": 5}