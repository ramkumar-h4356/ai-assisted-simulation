import pytest

from simulations.abm.backend import AgentBasedBackend
from simulations.abm.engine import ABMSimulationResult
from simulations.abm.model import Agent, AgentModel, MaxSteps
from simulations.core.specification import SimulationParadigm, SimulationSpecification


def model():
    return AgentModel(
        name="Backend test",
        agents=(Agent("a1", "person", "susceptible"),),
        termination=MaxSteps(2),
    )


def test_backend_executes_agent_based_specification():
    specification = SimulationSpecification(
        "Backend test", SimulationParadigm.AGENT_BASED, model()
    )
    execution = AgentBasedBackend().execute(specification)

    assert execution.specification_name == "Backend test"
    assert execution.paradigm is SimulationParadigm.AGENT_BASED
    assert execution.backend_name == "Native Agent-Based Engine"
    assert isinstance(execution.native_result, ABMSimulationResult)
    assert [(metric.name, metric.value) for metric in execution.metrics] == [
        ("agents_total", 1),
        ("steps_completed", 2),
        ("agents_in_state:susceptible", 1),
    ]


def test_backend_rejects_non_specification_input():
    with pytest.raises(TypeError, match="SimulationSpecification"):
        AgentBasedBackend().execute({"model": model()})


def test_backend_rejects_wrong_paradigm():
    specification = SimulationSpecification(
        "Wrong paradigm", SimulationParadigm.DISCRETE_EVENT, model()
    )
    with pytest.raises(ValueError, match="only supports AGENT_BASED"):
        AgentBasedBackend().execute(specification)


def test_backend_rejects_wrong_model_type():
    specification = SimulationSpecification(
        "Wrong model", SimulationParadigm.AGENT_BASED, object()
    )
    with pytest.raises(TypeError, match="must be an AgentModel"):
        AgentBasedBackend().execute(specification)


def test_backend_supports_an_injected_runner():
    from simulations.abm.engine import run_agent_model

    calls = []

    def runner(agent_model):
        calls.append(agent_model.name)
        return run_agent_model(agent_model)

    specification = SimulationSpecification(
        "Injected", SimulationParadigm.AGENT_BASED, model()
    )
    execution = AgentBasedBackend(runner=runner).execute(specification)

    assert calls == ["Backend test"]
    assert execution.native_result.model_name == "Backend test"


def test_backend_rejects_runner_returning_wrong_result_type():
    specification = SimulationSpecification(
        "Injected", SimulationParadigm.AGENT_BASED, model()
    )
    backend = AgentBasedBackend(runner=lambda _: object())

    with pytest.raises(TypeError, match="ABMSimulationResult"):
        backend.execute(specification)


def test_backend_registers_with_shared_registry():
    from simulations.core.registry import BackendRegistry

    registry = BackendRegistry()
    backend = AgentBasedBackend()
    registry.register(backend)

    assert registry.get(SimulationParadigm.AGENT_BASED) is backend
    assert SimulationParadigm.AGENT_BASED in registry.supported_paradigms
