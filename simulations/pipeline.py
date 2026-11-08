
"""Orchestrate AI interpretation, validation, and simulation."""

from dataclasses import dataclass
from typing import Any

from simulations.ai_interpreter import generate_model
from simulations.model_schema import scenario_from_dict
from simulations.scenario import ScenarioResult, run_scenario


@dataclass(frozen=True)
class PipelineResult:
    """Store the generated model and its simulation results."""

    model_data: dict[str, Any]
    simulation_result: ScenarioResult


def run_prompt(request: str) -> PipelineResult:
    """Generate, validate, and execute a simulation from a prompt.

    The AI output is validated before it reaches the simulation engine.
    Errors are propagated to the caller for appropriate handling.
    """
    if not isinstance(request, str):
        raise TypeError("Request must be a string")

    if not request.strip():
        raise ValueError("Request must not be empty")

    model_data = generate_model(request)
    scenario = scenario_from_dict(model_data)
    result = run_scenario(scenario)

    return PipelineResult(
        model_data=model_data,
        simulation_result=result,
    )

