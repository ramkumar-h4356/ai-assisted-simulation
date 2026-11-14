"""Orchestrate natural-language interpretation, clarification, validation and ABM execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from simulations.abm.backend import AgentBasedBackend
from simulations.abm.interpreter import generate_agent_model, refine_agent_model
from simulations.abm.model import AgentModel
from simulations.abm.schema import ABMModelDataError, agent_model_from_dict, normalize_agent_model_data
from simulations.abm.validation import ValidationIssue, ValidationReport, validate_agent_model
from simulations.core.backend import SimulationExecutionResult
from simulations.core.registry import BackendRegistry
from simulations.core.specification import SimulationParadigm, SimulationSpecification


@dataclass(frozen=True, slots=True)
class ABMClarificationQuestion:
    path: str
    question: str


@dataclass(frozen=True, slots=True)
class ABMPipelineResult:
    model_data: dict[str, Any]
    agent_model: AgentModel | None
    validation_report: ValidationReport
    clarification_history: tuple[dict[str, Any], ...]
    specification: SimulationSpecification | None
    execution_result: SimulationExecutionResult | None

    @property
    def simulation_result(self):
        return None if self.execution_result is None else self.execution_result.native_result

    @property
    def is_ready(self) -> bool:
        return self.execution_result is not None


ClarificationHandler = Callable[[tuple[ABMClarificationQuestion, ...]], str]
ModelGenerator = Callable[[str], dict[str, Any]]
ModelRefiner = Callable[[str, dict[str, Any], list[dict[str, Any]]], dict[str, Any]]


def _question_for(issue: ValidationIssue) -> str:
    path = issue.path
    if path == "agents":
        return "ABM V1 currently requires an explicit list of individual agents (up to 100). Describe a smaller group, with each agent type and initial state."
    if path == "relationships":
        return "Which agents are connected, and what kind of relationship connects them? Say explicitly when there are no relationships."
    if path == "space" or path.startswith("space."):
        return "What are the 2D world width and height, what units are used, and should agents clamp at the edges or wrap to the opposite side?"
    if path.endswith(".position"):
        return "What are this agent's initial x and y coordinates inside the declared 2D world?"
    if path == "behaviours":
        return "What behaviour rules should agents follow? Describe each rule's condition and resulting action, or confirm that agents do not change."
    if path.endswith(".agent_type"):
        return "What type or role does this agent represent?"
    if path.endswith(".state"):
        return "What is this agent's initial state? Use the state terminology from your scenario."
    if path == "termination" or path.startswith("termination."):
        return "How many simulation steps should the model run? Provide a positive integer."
    if path.endswith(".probability"):
        return "Is this behaviour certain, or what is its probability (between 0 and 1 or as a percentage)?"
    if ".condition" in path:
        return "What condition must be true for this behaviour rule to execute? Describe it in terms of the active agent or its connected neighbours."
    if ".actions" in path:
        return "What should the agent do when this behaviour condition is satisfied?"
    if ".source" in path or ".target" in path:
        return "Which two agent references should this relationship connect?"
    return f"Please clarify {path}: {issue.message}"


def _invalid_result(
    model_data: dict[str, Any],
    issue: ValidationIssue,
    history: list[dict[str, Any]],
) -> ABMPipelineResult:
    return ABMPipelineResult(
        model_data=model_data,
        agent_model=None,
        validation_report=ValidationReport((issue,)),
        clarification_history=tuple(history),
        specification=None,
        execution_result=None,
    )


def run_agent_prompt(
    request: str,
    *,
    clarification_handler: ClarificationHandler | None = None,
    max_clarification_rounds: int = 3,
    generate_fn: ModelGenerator | None = None,
    refine_fn: ModelRefiner | None = None,
) -> ABMPipelineResult:
    """Interpret a request, clarify missing facts, validate, then execute ABM.

    Generator and refiner injection keeps tests deterministic and avoids making
    network calls during validation or unit testing.
    """
    if not isinstance(request, str) or not request.strip():
        raise ValueError("Request must be a non-empty string.")
    if (
        isinstance(max_clarification_rounds, bool)
        or not isinstance(max_clarification_rounds, int)
        or max_clarification_rounds < 0
    ):
        raise ValueError("max_clarification_rounds must be a non-negative integer.")

    generate = generate_fn or generate_agent_model
    refine = refine_fn or refine_agent_model
    raw_data = generate(request.strip())
    if not isinstance(raw_data, dict):
        raise TypeError("AI model output must be a JSON object.")
    model_data = normalize_agent_model_data(raw_data)
    history: list[dict[str, Any]] = []

    for round_number in range(max_clarification_rounds + 1):
        try:
            model = agent_model_from_dict(model_data)
        except ABMModelDataError as error:
            issue = ValidationIssue(error.path, "MODEL_DATA_INCOMPLETE", error.message)
            if clarification_handler is None or round_number >= max_clarification_rounds:
                return _invalid_result(model_data, issue, history)

            question = ABMClarificationQuestion(error.path, _question_for(issue))
            answer = clarification_handler((question,))
            if not isinstance(answer, str):
                raise TypeError("Clarification response must be a string.")
            if not answer.strip():
                return _invalid_result(model_data, issue, history)

            history.append({
                "round": round_number + 1,
                "path": error.path,
                "question": question.question,
                "answer": answer.strip(),
            })
            revised = refine(request, model_data, history)
            if not isinstance(revised, dict):
                raise TypeError("AI refinement must return a JSON object.")
            model_data = normalize_agent_model_data(revised)
            continue

        report = validate_agent_model(model)
        if not report.is_valid:
            first_issue = report.errors[0]
            if clarification_handler is None or round_number >= max_clarification_rounds:
                return ABMPipelineResult(
                    model_data, model, report, tuple(history), None, None
                )
            question = ABMClarificationQuestion(first_issue.path, _question_for(first_issue))
            answer = clarification_handler((question,))
            if not isinstance(answer, str):
                raise TypeError("Clarification response must be a string.")
            if not answer.strip():
                return ABMPipelineResult(
                    model_data, model, report, tuple(history), None, None
                )
            history.append({
                "round": round_number + 1,
                "path": first_issue.path,
                "question": question.question,
                "answer": answer.strip(),
            })
            revised = refine(request, model_data, history)
            if not isinstance(revised, dict):
                raise TypeError("AI refinement must return a JSON object.")
            model_data = normalize_agent_model_data(revised)
            continue

        specification = SimulationSpecification(
            name=model.name,
            paradigm=SimulationParadigm.AGENT_BASED,
            model=model,
        )
        registry = BackendRegistry()
        registry.register(AgentBasedBackend())
        execution_result = registry.get(SimulationParadigm.AGENT_BASED).execute(specification)
        return ABMPipelineResult(
            model_data=model_data,
            agent_model=model,
            validation_report=report,
            clarification_history=tuple(history),
            specification=specification,
            execution_result=execution_result,
        )

    raise RuntimeError("ABM clarification loop ended unexpectedly.")
