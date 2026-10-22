
"""Parse structured simulation data into validated scenarios."""

from __future__ import annotations

import json
from typing import Any

from simulations.scenario import (
    Scenario,
    ScenarioResource,
    ServiceJob,
    ServiceStage,
)


def scenario_from_dict(data: dict[str, Any]) -> Scenario:
    """Convert a dictionary into a validated Scenario."""
    if not isinstance(data, dict):
        raise TypeError("Simulation model must be a JSON object")

    expected_keys = {"name", "resources", "jobs"}
    if set(data) != expected_keys:
        raise ValueError(
            f"Model must contain exactly these fields: "
            f"{sorted(expected_keys)}"
        )

    if not isinstance(data["resources"], list):
        raise TypeError("'resources' must be a list")

    if not isinstance(data["jobs"], list):
        raise TypeError("'jobs' must be a list")

    resources = tuple(
        _parse_resource(item) for item in data["resources"]
    )
    jobs = tuple(
        _parse_job(item) for item in data["jobs"]
    )

    return Scenario(
        name=data["name"],
        resources=resources,
        jobs=jobs,
    )


def _parse_resource(data: Any) -> ScenarioResource:
    """Parse one resource definition."""
    if not isinstance(data, dict):
        raise TypeError("Each resource must be a JSON object")

    if set(data) != {"name", "capacity"}:
        raise ValueError(
            "Each resource must contain exactly 'name' and 'capacity'"
        )

    return ScenarioResource(
        name=data["name"],
        capacity=data["capacity"],
    )


def _parse_job(data: Any) -> ServiceJob:
    """Parse one job and its ordered service stages."""
    if not isinstance(data, dict):
        raise TypeError("Each job must be a JSON object")

    if set(data) != {"entity_id", "arrival_time", "stages"}:
        raise ValueError(
            "Each job must contain exactly "
            "'entity_id', 'arrival_time', and 'stages'"
        )

    if not isinstance(data["stages"], list):
        raise TypeError("'stages' must be a list")

    stages = tuple(
        _parse_stage(item) for item in data["stages"]
    )

    return ServiceJob(
        entity_id=data["entity_id"],
        arrival_time=data["arrival_time"],
        stages=stages,
    )


def _parse_stage(data: Any) -> ServiceStage:
    """Parse one service stage."""
    if not isinstance(data, dict):
        raise TypeError("Each stage must be a JSON object")

    if set(data) != {"resource_name", "service_duration"}:
        raise ValueError(
            "Each stage must contain exactly "
            "'resource_name' and 'service_duration'"
        )

    return ServiceStage(
        resource_name=data["resource_name"],
        service_duration=data["service_duration"],
    )


def scenario_from_json(json_text: str) -> Scenario:
    """Parse JSON text and convert it into a validated Scenario."""
    if not isinstance(json_text, str):
        raise TypeError("JSON input must be a string")

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON input") from exc

    return scenario_from_dict(data)
