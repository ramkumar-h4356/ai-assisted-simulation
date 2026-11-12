"""Deterministic validation of hierarchical simulation scenarios."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from simulations.scenario_ir import (
    JobUnderstanding,
    KnownValue,
    ResourceUnderstanding,
    ScenarioIR,
    StageUnderstanding,
)
from simulations.scenario_understanding import UncertaintyType


DEFAULT_VALUES = {
    "resource.capacity": 1,
}


class RequirementStatus(Enum):
    """Describe the outcome of an individual validation."""

    SATISFIED = "satisfied"
    MISSING = "missing"
    DEFAULT_AVAILABLE = "default_available"
    INVALID = "invalid"
    NEEDS_CLARIFICATION = "needs_clarification"


class ScenarioReadiness(Enum):
    """Describe whether a scenario can proceed."""

    INCOMPLETE = "incomplete"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID = "invalid"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class RequirementResult:
    """Store one validation finding."""

    path: str
    status: RequirementStatus
    message: str
    actual_value: Any = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Collect all findings and the resulting readiness decision."""

    results: tuple[RequirementResult, ...]
    readiness: ScenarioReadiness

    @property
    def is_ready(self) -> bool:
        return self.readiness == ScenarioReadiness.READY

    @property
    def has_errors(self) -> bool:
        return any(
            result.status == RequirementStatus.INVALID
            for result in self.results
        )


def _add(
    results: list[RequirementResult],
    path: str,
    status: RequirementStatus,
    message: str,
    value: Any = None,
) -> None:
    results.append(RequirementResult(path, status, message, value))


def _require_string(
    path: str,
    field: KnownValue | None,
    results: list[RequirementResult],
) -> str | None:
    if field is None:
        _add(results, path, RequirementStatus.MISSING, "Value is missing.")
        return None

    if not isinstance(field, KnownValue):
        _add(results, path, RequirementStatus.INVALID, "Expected a KnownValue.")
        return None

    value = field.value

    if not isinstance(value, str) or not value.strip():
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Expected a non-empty string.",
            value,
        )
        return None

    _add(results, path, RequirementStatus.SATISFIED, "Valid string.", value)
    return value


def _require_number(
    path: str,
    field: KnownValue | None,
    results: list[RequirementResult],
    *,
    integer: bool = False,
    positive: bool = False,
    default: Any = None,
) -> int | float | None:
    if field is None:
        if default is not None:
            _add(
                results,
                path,
                RequirementStatus.DEFAULT_AVAILABLE,
                f"Missing value; documented default available: {default}.",
            )
        else:
            _add(
                results,
                path,
                RequirementStatus.MISSING,
                "Numeric value is missing.",
            )
        return None

    if not isinstance(field, KnownValue):
        _add(results, path, RequirementStatus.INVALID, "Expected a KnownValue.")
        return None

    value = field.value

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Expected a numeric value.",
            value,
        )
        return None

    if not isfinite(value):
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Value must be finite.",
            value,
        )
        return None

    if integer and not isinstance(value, int):
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Value must be an integer.",
            value,
        )
        return None

    if positive and value <= 0:
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Value must be greater than zero.",
            value,
        )
        return None

    if not positive and value < 0:
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Value must be non-negative.",
            value,
        )
        return None

    _add(results, path, RequirementStatus.SATISFIED, "Valid numeric value.", value)
    return value


def _check_collection(
    path: str,
    value: Any,
    results: list[RequirementResult],
) -> tuple | None:
    if value is None:
        _add(results, path, RequirementStatus.MISSING, "Collection is unknown.")
        return None

    if not isinstance(value, tuple):
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Collection must be a tuple.",
            value,
        )
        return None

    if not value:
        _add(
            results,
            path,
            RequirementStatus.INVALID,
            "Collection must contain at least one item.",
        )
        return None

    _add(results, path, RequirementStatus.SATISFIED, "Collection is populated.")
    return value


def evaluate_requirements(scenario: ScenarioIR) -> ValidationReport:
    """Validate every scenario field and relationship."""

    if not isinstance(scenario, ScenarioIR):
        raise TypeError("scenario must be a ScenarioIR instance")

    results: list[RequirementResult] = []

    _require_string("scenario.name", scenario.scenario_name, results)

    resources = _check_collection(
        "resources",
        scenario.resources,
        results,
    )

    resource_names: set[str] = set()
    all_resource_names_known = resources is not None

    if resources is not None:
        for index, resource in enumerate(resources):
            path = f"resources[{index}]"

            if not isinstance(resource, ResourceUnderstanding):
                _add(
                    results,
                    path,
                    RequirementStatus.INVALID,
                    "Expected a ResourceUnderstanding instance.",
                )
                all_resource_names_known = False
                continue

            name = _require_string(f"{path}.name", resource.name, results)

            if name is None:
                all_resource_names_known = False
            elif name in resource_names:
                _add(
                    results,
                    f"{path}.name",
                    RequirementStatus.INVALID,
                    f"Duplicate resource name: {name}.",
                    name,
                )
            else:
                resource_names.add(name)

            _require_number(
                f"{path}.capacity",
                resource.capacity,
                results,
                integer=True,
                positive=True,
                default=DEFAULT_VALUES["resource.capacity"],
            )

    jobs = _check_collection("jobs", scenario.jobs, results)
    job_ids: set[str] = set()

    if jobs is not None:
        for job_index, job in enumerate(jobs):
            job_path = f"jobs[{job_index}]"

            if not isinstance(job, JobUnderstanding):
                _add(
                    results,
                    job_path,
                    RequirementStatus.INVALID,
                    "Expected a JobUnderstanding instance.",
                )
                continue

            entity_id = _require_string(
                f"{job_path}.entity_id",
                job.entity_id,
                results,
            )

            if entity_id is not None:
                if entity_id in job_ids:
                    _add(
                        results,
                        f"{job_path}.entity_id",
                        RequirementStatus.INVALID,
                        f"Duplicate job identifier: {entity_id}.",
                        entity_id,
                    )
                else:
                    job_ids.add(entity_id)

            _require_number(
                f"{job_path}.arrival_time",
                job.arrival_time,
                results,
            )

            stages = _check_collection(
                f"{job_path}.stages",
                job.stages,
                results,
            )

            if stages is None:
                continue

            for stage_index, stage in enumerate(stages):
                stage_path = f"{job_path}.stages[{stage_index}]"

                if not isinstance(stage, StageUnderstanding):
                    _add(
                        results,
                        stage_path,
                        RequirementStatus.INVALID,
                        "Expected a StageUnderstanding instance.",
                    )
                    continue

                resource_name = _require_string(
                    f"{stage_path}.resource_name",
                    stage.resource_name,
                    results,
                )

                _require_number(
                    f"{stage_path}.service_duration",
                    stage.service_duration,
                    results,
                )

                if (
                    resource_name is not None
                    and all_resource_names_known
                    and resource_name not in resource_names
                ):
                    _add(
                        results,
                        f"{stage_path}.resource_reference",
                        RequirementStatus.INVALID,
                        f"Unknown resource reference: {resource_name}.",
                        resource_name,
                    )

    if not isinstance(scenario.uncertainties, tuple):
        _add(
            results,
            "uncertainties",
            RequirementStatus.INVALID,
            "Uncertainties must be stored in a tuple.",
        )
    else:
        for uncertainty in scenario.uncertainties:
            if not hasattr(uncertainty, "uncertainty_type"):
                _add(
                    results,
                    "uncertainties",
                    RequirementStatus.INVALID,
                    "Invalid uncertainty object.",
                )
                continue

            if uncertainty.uncertainty_type == UncertaintyType.MISSING:
                status = RequirementStatus.MISSING
            elif uncertainty.uncertainty_type in (
                UncertaintyType.AMBIGUOUS,
                UncertaintyType.CONTRADICTORY,
            ):
                status = RequirementStatus.NEEDS_CLARIFICATION
            else:
                _add(
                    results,
                    uncertainty.name,
                    RequirementStatus.INVALID,
                    "Unknown uncertainty type.",
                )
                continue

            _add(
                results,
                uncertainty.name,
                status,
                uncertainty.description,
            )

    statuses = {result.status for result in results}

    if RequirementStatus.INVALID in statuses:
        readiness = ScenarioReadiness.INVALID
    elif RequirementStatus.NEEDS_CLARIFICATION in statuses:
        readiness = ScenarioReadiness.NEEDS_CLARIFICATION
    elif statuses.intersection({
        RequirementStatus.MISSING,
        RequirementStatus.DEFAULT_AVAILABLE,
    }):
        readiness = ScenarioReadiness.INCOMPLETE
    else:
        readiness = ScenarioReadiness.READY

    return ValidationReport(tuple(results), readiness)