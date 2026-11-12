"""Parse structured JSON into executable DES models and scenario IR."""

from __future__ import annotations

import json

from typing import Any

from .model import Scenario, ScenarioResource, ServiceJob, ServiceStage

from .representation import (

    FactOrigin, JobUnderstanding, KnownValue, ResourceUnderstanding,

    ScenarioIR, ScenarioUncertainty, StageUnderstanding, UncertaintyType,

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

def _parse_known(value: Any, path: str) -> KnownValue | None:
    """Parse a value and its origin."""

    if value is None:
        return None

    if isinstance(value, dict) and (
        "value" in value or "origin" in value
    ):
        if set(value) != {"value", "origin"}:
            raise ValueError(
                f"{path} must contain exactly 'value' and 'origin'"
            )

        try:
            origin = FactOrigin(value["origin"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid origin at {path}") from exc

        if origin not in (
            FactOrigin.EXPLICIT,
            FactOrigin.INFERRED,
        ):
            raise ValueError(
                "AI can only declare explicit or inferred values. "
                "The application manages defaults and generated values."
            )

        if value["value"] is None:
            return None

        return KnownValue(value["value"], origin)

    # Compatibility with the older JSON format.
    return KnownValue(value, FactOrigin.INFERRED)

def _parse_ir_resource(data: Any, index: int):
    path = f"resources[{index}]"

    if not isinstance(data, dict):
        return data

    unexpected = set(data) - {"name", "capacity"}
    if unexpected:
        raise ValueError(f"Unexpected fields in {path}: {unexpected}")

    return ResourceUnderstanding(
        name=_parse_known(data.get("name"), f"{path}.name"),
        capacity=_parse_known(data.get("capacity"), f"{path}.capacity"),
    )

def _parse_ir_stage(data: Any, path: str):
    if not isinstance(data, dict):
        return data

    unexpected = set(data) - {"resource_name", "service_duration"}
    if unexpected:
        raise ValueError(f"Unexpected fields in {path}: {unexpected}")

    return StageUnderstanding(
        resource_name=_parse_known(
            data.get("resource_name"),
            f"{path}.resource_name",
        ),
        service_duration=_parse_known(
            data.get("service_duration"),
            f"{path}.service_duration",
        ),
    )

def _parse_ir_stages(data: Any, job_index: int):
    if data is None:
        return None

    if not isinstance(data, list):
        return data

    return tuple(
        _parse_ir_stage(
            stage,
            f"jobs[{job_index}].stages[{stage_index}]",
        )
        for stage_index, stage in enumerate(data)
    )

def _parse_ir_job(data: Any, index: int):
    path = f"jobs[{index}]"

    if not isinstance(data, dict):
        return data

    unexpected = set(data) - {"entity_id", "arrival_time", "stages"}
    if unexpected:
        raise ValueError(f"Unexpected fields in {path}: {unexpected}")

    return JobUnderstanding(
        entity_id=_parse_known(
            data.get("entity_id"),
            f"{path}.entity_id",
        ),
        arrival_time=_parse_known(
            data.get("arrival_time"),
            f"{path}.arrival_time",
        ),
        stages=_parse_ir_stages(data.get("stages"), index),
    )

def _parse_collection(data: dict, key: str, parser):
    """Preserve the distinction between unknown and empty collections."""

    if key not in data or data[key] is None:
        return None

    value = data[key]

    if not isinstance(value, list):
        return value

    return tuple(
        parser(item, index)
        for index, item in enumerate(value)
    )

def _parse_uncertainties(data: Any) -> tuple[ScenarioUncertainty, ...]:
    if data is None:
        return ()

    if not isinstance(data, list):
        raise TypeError("'uncertainties' must be a list")

    uncertainties = []

    for item in data:
        if not isinstance(item, dict):
            raise TypeError("Each uncertainty must be an object")

        if set(item) != {"name", "type", "description"}:
            raise ValueError(
                "Each uncertainty must contain exactly "
                "'name', 'type', and 'description'"
            )

        try:
            uncertainty_type = UncertaintyType(item["type"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid uncertainty type") from exc

        uncertainties.append(
            ScenarioUncertainty(
                name=item["name"],
                uncertainty_type=uncertainty_type,
                description=item["description"],
            )
        )

    return tuple(uncertainties)

def scenario_ir_from_dict(data: dict[str, Any]) -> ScenarioIR:
    """Convert AI-generated JSON data into ScenarioIR."""

    if not isinstance(data, dict):
        raise TypeError("AI output must be a JSON object")

    legacy_format = "name" in data and "scenario_name" not in data

    if legacy_format:
        allowed = {"name", "resources", "jobs"}
        scenario_name = data.get("name")
    else:
        allowed = {
            "scenario_name",
            "resources",
            "jobs",
            "uncertainties",
        }
        scenario_name = data.get("scenario_name")

    unexpected = set(data) - allowed
    if unexpected:
        raise ValueError(f"Unexpected top-level fields: {unexpected}")

    return ScenarioIR(
        scenario_name=_parse_known(
            scenario_name,
            "scenario_name",
        ),
        resources=_parse_collection(
            data,
            "resources",
            _parse_ir_resource,
        ),
        jobs=_parse_collection(
            data,
            "jobs",
            _parse_ir_job,
        ),
        uncertainties=_parse_uncertainties(
            data.get("uncertainties", [])
        ),
    )
