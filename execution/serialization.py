"""Strict, integrity-checked JSON persistence for M9 experiment results."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from execution.models import (
    ExperimentConfig, ExperimentResult, ExperimentStatus, MetricRecord,
    ParameterOverride, ParameterSet, RunRecord, RunStatus,
)


class ExperimentSerializationError(ValueError):
    pass


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    return value


def result_to_dict(result: ExperimentResult) -> dict[str, Any]:
    if not isinstance(result, ExperimentResult):
        raise TypeError("result must be an ExperimentResult")
    return _primitive(result)


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint_result(result: ExperimentResult) -> str:
    data = result_to_dict(result)
    data.pop("result_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_result(result: ExperimentResult, *, indent: int = 2) -> str:
    data = result_to_dict(result)
    if fingerprint_result(result) != result.result_fingerprint:
        raise ExperimentSerializationError("Experiment result fingerprint does not match its content")
    return json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ExperimentSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    if missing:
        raise ExperimentSerializationError(f"{path} missing field(s): {', '.join(sorted(missing))}")
    if unknown:
        raise ExperimentSerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    return raw


def result_from_dict(raw: Any) -> ExperimentResult:
    raw = _strict(raw, ExperimentResult, "experiment_result")
    config_raw = _strict(raw["config"], ExperimentConfig, "config")
    try:
        if not isinstance(config_raw["parameter_sets"], list):
            raise ExperimentSerializationError("config.parameter_sets must be an array")
        parameter_sets = []
        for index, item in enumerate(config_raw["parameter_sets"]):
            item = _strict(item, ParameterSet, f"config.parameter_sets[{index}]")
            if not isinstance(item["overrides"], list):
                raise ExperimentSerializationError(f"config.parameter_sets[{index}].overrides must be an array")
            overrides = tuple(
                ParameterOverride(**_strict(value, ParameterOverride, f"config.parameter_sets[{index}].overrides[{override_index}]"))
                for override_index, value in enumerate(item["overrides"])
            )
            parameter_sets.append(ParameterSet(name=item["name"], overrides=overrides))
        config = ExperimentConfig(
            runs=config_raw["runs"], base_seed=config_raw["base_seed"],
            continue_on_error=config_raw["continue_on_error"], parameter_sets=tuple(parameter_sets),
        )
        if not isinstance(raw["runs"], list):
            raise ExperimentSerializationError("runs must be an array")
        records = []
        for index, item in enumerate(raw["runs"]):
            item = _strict(item, RunRecord, f"runs[{index}]")
            if not isinstance(item["metrics"], list):
                raise ExperimentSerializationError(f"runs[{index}].metrics must be an array")
            metrics = tuple(MetricRecord(**metric) for metric in item["metrics"])
            records.append(RunRecord(
                run_index=item["run_index"], status=RunStatus(item["status"]), seed=item["seed"],
                parameter_set=item["parameter_set"], parameters=item["parameters"],
                started_at=item["started_at"], finished_at=item["finished_at"],
                elapsed_seconds=item["elapsed_seconds"], metrics=metrics, trace=item["trace"],
                error_type=item["error_type"], error_message=item["error_message"],
            ))
        result = ExperimentResult(
            schema_version=raw["schema_version"], experiment_id=raw["experiment_id"],
            created_at=raw["created_at"], artifact_id=raw["artifact_id"],
            artifact_fingerprint=raw["artifact_fingerprint"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], paradigm=raw["paradigm"],
            backend_name=raw["backend_name"], config=config,
            status=ExperimentStatus(raw["status"]), runs=tuple(records),
            result_fingerprint=raw["result_fingerprint"],
        )
    except (TypeError, ValueError, KeyError) as error:
        if isinstance(error, ExperimentSerializationError):
            raise
        raise ExperimentSerializationError(f"Experiment result is invalid: {error}") from error
    if fingerprint_result(result) != result.result_fingerprint:
        raise ExperimentSerializationError("Experiment result fingerprint does not match its stored content")
    return result


def loads_result(content: str) -> ExperimentResult:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise ExperimentSerializationError(f"Invalid experiment JSON: {error}") from error
    return result_from_dict(raw)


def save_result(result: ExperimentResult, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = dumps_result(result)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_result(path: str | Path) -> ExperimentResult:
    source = Path(path)
    try:
        return loads_result(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read experiment result at {source}: {error}") from error
