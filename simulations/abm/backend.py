"""Backend adapter exposing the native ABM engine to the shared architecture."""

from __future__ import annotations

from collections.abc import Callable

from simulations.abm.engine import ABMSimulationResult, run_agent_model
from simulations.abm.model import AgentModel
from simulations.core.backend import SimulationExecutionResult, SimulationMetric
from simulations.core.specification import SimulationParadigm, SimulationSpecification


class AgentBasedBackend:
    """Execute AgentModel instances through the shared backend interface."""

    name = "Native Agent-Based Engine"
    paradigm = SimulationParadigm.AGENT_BASED

    def __init__(
        self,
        runner: Callable[[AgentModel], ABMSimulationResult] | None = None,
    ) -> None:
        self._runner = runner or run_agent_model

    def execute(self, specification: SimulationSpecification) -> SimulationExecutionResult:
        if not isinstance(specification, SimulationSpecification):
            raise TypeError("specification must be a SimulationSpecification")
        if specification.paradigm is not self.paradigm:
            raise ValueError("AgentBasedBackend only supports AGENT_BASED specifications")
        if not isinstance(specification.model, AgentModel):
            raise TypeError("AGENT_BASED specification model must be an AgentModel")

        result = self._runner(specification.model)
        if not isinstance(result, ABMSimulationResult):
            raise TypeError("ABM runner must return an ABMSimulationResult")

        metrics = [
            SimulationMetric("agents_total", len(result.final_agents), "agents"),
            SimulationMetric("steps_completed", result.steps_completed, "steps"),
        ]
        metrics.extend(
            SimulationMetric(f"agents_in_state:{state}", count, "agents")
            for state, count in result.final_state_counts.items()
        )
        return SimulationExecutionResult(
            specification_name=specification.name,
            paradigm=self.paradigm,
            backend_name=self.name,
            metrics=tuple(metrics),
            native_result=result,
        )
