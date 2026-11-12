"""Normalize scenario IR using safe system-generated identifiers."""

from dataclasses import replace

from simulations.scenario_ir import (
    JobUnderstanding,
    KnownValue,
    ScenarioIR,
)
from simulations.scenario_understanding import FactOrigin


def normalize_scenario_ir(scenario: ScenarioIR) -> ScenarioIR:
    """Generate identifiers for jobs that do not have one."""

    if not isinstance(scenario, ScenarioIR):
        raise TypeError("scenario must be a ScenarioIR instance")

    if scenario.jobs is None:
        return scenario

    existing_ids = {
        job.entity_id.value
        for job in scenario.jobs
        if isinstance(job, JobUnderstanding)
        and isinstance(job.entity_id, KnownValue)
        and isinstance(job.entity_id.value, str)
        and job.entity_id.value.strip()
    }

    updated_jobs = []
    counter = 1

    for job in scenario.jobs:
        if not isinstance(job, JobUnderstanding):
            updated_jobs.append(job)
            continue

        if job.entity_id is None:
            while f"entity-{counter}" in existing_ids:
                counter += 1

            identifier = f"entity-{counter}"
            existing_ids.add(identifier)
            counter += 1

            job = replace(
                job,
                entity_id=KnownValue(
                    identifier,
                    FactOrigin.SYSTEM_GENERATED,
                ),
            )

        updated_jobs.append(job)

    return replace(
        scenario,
        jobs=tuple(updated_jobs),
    )