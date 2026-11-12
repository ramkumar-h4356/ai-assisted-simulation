"""Orchestrate interpretation, clarification, validation, and simulation."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from simulations.ai_interpreter import generate_model, refine_model
from simulations.clarification_manager import (
    ClarificationQuestion,
    build_clarification_questions,
    merge_model_data,
)
from simulations.default_manager import (
    DefaultApplication,
    DefaultResolution,
    apply_documented_defaults,
)
from simulations.requirements import (
    RequirementStatus,
    ScenarioReadiness,
    ValidationReport,
    evaluate_requirements,
)
from simulations.scenario import Scenario, ScenarioResult, run_scenario
from simulations.scenario_compiler import compile_scenario
from simulations.scenario_ir import ScenarioIR
from simulations.scenario_ir_schema import scenario_ir_from_dict
from simulations.scenario_normalizer import normalize_scenario_ir

ClarificationHandler = Callable[
    [tuple[ClarificationQuestion, ...]],
    str,
]

DefaultApproval = Callable[
    [tuple[DefaultApplication, ...]],
    bool,
]


@dataclass(frozen=True)
class PipelineResult:
    """Store interpretation, validation, and execution results."""

    model_data: dict[str, Any]
    understanding: ScenarioIR
    validation_report: ValidationReport
    default_resolution: DefaultResolution
    scenario: Scenario | None
    simulation_result: ScenarioResult | None
    clarification_history: tuple[dict[str, Any], ...] = ()


def _ensure_scenario_name(model_data: dict[str, Any]) -> None:
    """Supply a non-operational fallback name when necessary."""

    # Preserve the older JSON representation.
    if "name" in model_data and "scenario_name" not in model_data:
        return

    value = model_data.get("scenario_name")

    if isinstance(value, dict):
        name = value.get("value")
    else:
        name = value

    if not isinstance(name, str) or not name.strip():
        model_data["scenario_name"] = {
            "value": "Generated Simulation",
            "origin": "inferred",
        }


def _scenario_to_model_data(scenario: Scenario) -> dict[str, Any]:
    """Convert the compiled scenario into a JSON-compatible dictionary."""

    return {
        "name": scenario.name,
        "resources": [
            {"name": resource.name, "capacity": resource.capacity}
            for resource in scenario.resources
        ],
        "jobs": [
            {
                "entity_id": job.entity_id,
                "arrival_time": job.arrival_time,
                "stages": [
                    {
                        "resource_name": stage.resource_name,
                        "service_duration": stage.service_duration,
                    }
                    for stage in scenario._job_stages(job)
                ],
            }
            for job in scenario.jobs
        ],
    }


def run_prompt(
    request: str,
    *,
    approve_defaults: DefaultApproval | None = None,
    clarification_handler: ClarificationHandler | None = None,
    max_clarification_rounds: int = 3,
) -> PipelineResult:
    """Interpret, clarify, validate, compile, and execute a prompt."""

    if not isinstance(request, str):
        raise TypeError("Request must be a string")

    if not request.strip():
        raise ValueError("Request must not be empty")

    if (
        isinstance(max_clarification_rounds, bool)
        or not isinstance(max_clarification_rounds, int)
        or max_clarification_rounds < 0
    ):
        raise ValueError("max_clarification_rounds must be a non-negative integer")

    # 1. Initial AI interpretation.
    model_data = generate_model(request)

    if not isinstance(model_data, dict):
        raise TypeError("AI model output must be a dictionary")

    _ensure_scenario_name(model_data)

    understanding = normalize_scenario_ir(
        scenario_ir_from_dict(model_data)
    )
    report = evaluate_requirements(understanding)

    if (
        report.readiness == ScenarioReadiness.INVALID
        and clarification_handler is None
    ):
        errors = [
            f"{item.path}: {item.message}"
            for item in report.results
            if item.status == RequirementStatus.INVALID
        ]

        raise ValueError(
            "AI generated an invalid scenario: " + "; ".join(errors)
        )

    history: list[dict[str, Any]] = []

    # 2. Conversational clarification loop.
    for round_number in range(1, max_clarification_rounds + 1):
        questions = build_clarification_questions(report)

        if not questions or clarification_handler is None:
            break

        answer = clarification_handler(questions)

        if not isinstance(answer, str):
            raise TypeError("Clarification response must be a string")

        if not answer.strip():
            break

        history.append(
            {
                "round": round_number,
                "questions": [
                    {
                        "path": question.path,
                        "status": question.status.value,
                        "question": question.question,
                    }
                    for question in questions
                ],
                "answer": answer.strip(),
            }
        )

        # 3. Ask AI to update the existing understanding.
        revised_data = refine_model(
            original_request=request,
            current_model_data=model_data,
            clarification_history=history,
        )

        if not isinstance(revised_data, dict):
            raise TypeError("AI refinement must return a dictionary")

        model_data = merge_model_data(model_data, revised_data)
        _ensure_scenario_name(model_data)

        understanding = normalize_scenario_ir(
            scenario_ir_from_dict(model_data)
        )

        report = evaluate_requirements(understanding)

        if report.is_ready:
            break

    # 4. Propose and, where approved, apply defaults.
    default_resolution = apply_documented_defaults(
        understanding,
        approve=False,
    )

    if default_resolution.proposed and approve_defaults is not None:
        approved = approve_defaults(default_resolution.proposed)

        if not isinstance(approved, bool):
            raise TypeError("Default approval must return a boolean")

        default_resolution = apply_documented_defaults(
            understanding,
            approve=approved,
        )

        understanding = default_resolution.scenario
        report = evaluate_requirements(understanding)

    # 5. Compile and execute only when validated as READY.
    scenario = None
    simulation_result = None

    if report.is_ready:
        scenario = compile_scenario(understanding)
        simulation_result = run_scenario(scenario)
        model_data = _scenario_to_model_data(scenario)

    return PipelineResult(
        model_data=model_data,
        understanding=understanding,
        validation_report=report,
        default_resolution=default_resolution,
        scenario=scenario,
        simulation_result=simulation_result,
        clarification_history=tuple(history),
    )