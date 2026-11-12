"""Compile a validated ScenarioIR into an executable Scenario."""

from simulations.requirements import (
    RequirementStatus,
    ValidationReport,
    evaluate_requirements,
)
from simulations.scenario import (
    Scenario,
    ScenarioResource,
    ServiceJob,
    ServiceStage,
)
from simulations.scenario_ir import KnownValue, ScenarioIR


class ScenarioCompilationError(ValueError):
    """Raised when an intermediate scenario is not executable."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report

        problems = [
            f"{result.path}: {result.message}"
            for result in report.results
            if result.status != RequirementStatus.SATISFIED
        ]

        super().__init__(
            f"Scenario is not ready: {report.readiness.value}. "
            + "; ".join(problems)
        )


def _unwrap(field: KnownValue | None, path: str):
    """Extract a value that has already passed validation."""

    if field is None:
        raise RuntimeError(
            f"Validated field unexpectedly missing: {path}"
        )

    return field.value


def compile_scenario(scenario_ir: ScenarioIR) -> Scenario:
    """Convert a ready ScenarioIR into the executable Scenario model."""

    report = evaluate_requirements(scenario_ir)

    if not report.is_ready:
        raise ScenarioCompilationError(report)

    resources = tuple(
        ScenarioResource(
            name=_unwrap(resource.name, f"resources[{index}].name"),
            capacity=_unwrap(
                resource.capacity,
                f"resources[{index}].capacity",
            ),
        )
        for index, resource in enumerate(scenario_ir.resources)
    )

    jobs = tuple(
        ServiceJob(
            entity_id=_unwrap(
                job.entity_id,
                f"jobs[{job_index}].entity_id",
            ),
            arrival_time=_unwrap(
                job.arrival_time,
                f"jobs[{job_index}].arrival_time",
            ),
            stages=tuple(
                ServiceStage(
                    resource_name=_unwrap(
                        stage.resource_name,
                        f"jobs[{job_index}].stages[{stage_index}].resource_name",
                    ),
                    service_duration=_unwrap(
                        stage.service_duration,
                        f"jobs[{job_index}].stages[{stage_index}].service_duration",
                    ),
                )
                for stage_index, stage in enumerate(job.stages)
            ),
        )
        for job_index, job in enumerate(scenario_ir.jobs)
    )

    return Scenario(
        name=_unwrap(scenario_ir.scenario_name, "scenario.name"),
        resources=resources,
        jobs=jobs,
    )