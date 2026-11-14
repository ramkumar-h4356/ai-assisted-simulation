"""Strict JSON/CSV persistence for M26 validation plans and reports."""

from __future__ import annotations

from dataclasses import fields
import csv
import json
import os
from pathlib import Path
from typing import Any

from validation.engine import fingerprint_report, report_to_dict
from validation.models import InvariantSpec, ValidationCheck, ValidationPlan, ValidationReport


class ValidationSerializationError(ValueError):
    pass


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    unknown, missing = set(raw) - allowed, allowed - set(raw)
    if unknown:
        raise ValidationSerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ValidationSerializationError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
    return raw


def plan_from_dict(raw: Any) -> ValidationPlan:
    raw = _strict(raw, ValidationPlan, "validation_plan")
    if not isinstance(raw["invariants"], list):
        raise ValidationSerializationError("invariants must be an array")
    invariants = []
    for index, item in enumerate(raw["invariants"]):
        data = _strict(item, InvariantSpec, f"invariants[{index}]")
        if not isinstance(data["fields"], list):
            raise ValidationSerializationError(f"invariants[{index}].fields must be an array")
        data["fields"] = tuple(data["fields"])
        invariants.append(InvariantSpec(**data))
    raw = dict(raw)
    raw["invariants"] = tuple(invariants)
    try:
        return ValidationPlan(**raw)
    except (TypeError, ValueError) as error:
        raise ValidationSerializationError(f"Validation plan is invalid: {error}") from error


def loads_plan(content: str) -> ValidationPlan:
    try:
        return plan_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationSerializationError(f"Invalid validation plan JSON: {error}") from error


def load_plan(path: str | Path) -> ValidationPlan:
    source = Path(path)
    try:
        return loads_plan(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M26 validation plan at {source}: {error}") from error


def save_plan(plan: ValidationPlan, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": plan.schema_version,
        "validation_name": plan.validation_name,
        "artifact_path": plan.artifact_path,
        "execution_result_path": plan.execution_result_path,
        "execute_if_missing": plan.execute_if_missing,
        "execution_runs": plan.execution_runs,
        "execution_base_seed": plan.execution_base_seed,
        "repeatability_check": plan.repeatability_check,
        "repeatability_tolerance": plan.repeatability_tolerance,
        "invariants": [{
            "check_id": item.check_id, "check_type": item.check_type, "trace_path": item.trace_path,
            "fields": list(item.fields), "expected_value": item.expected_value,
            "minimum": item.minimum, "maximum": item.maximum,
            "direction": item.direction, "tolerance": item.tolerance,
        } for item in plan.invariants],
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return destination


def report_from_dict(raw: Any) -> ValidationReport:
    raw = _strict(raw, ValidationReport, "validation_report")
    if not isinstance(raw["checks"], list) or not isinstance(raw["interpretation_limits"], list):
        raise ValidationSerializationError("checks and interpretation_limits must be arrays")
    checks = []
    for index, item in enumerate(raw["checks"]):
        checks.append(ValidationCheck(**_strict(item, ValidationCheck, f"checks[{index}]")))
    data = dict(raw)
    data["checks"] = tuple(checks)
    data["interpretation_limits"] = tuple(raw["interpretation_limits"])
    try:
        report = ValidationReport(**data)
    except (TypeError, ValueError) as error:
        raise ValidationSerializationError(f"Validation report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise ValidationSerializationError("M26 validation report fingerprint does not match its stored content")
    return report


def loads_report(content: str) -> ValidationReport:
    try:
        return report_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationSerializationError(f"Invalid M26 validation report JSON: {error}") from error


def load_report(path: str | Path) -> ValidationReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M26 validation report at {source}: {error}") from error


def save_report(report: ValidationReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, allow_nan=False)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def export_check_csv(report: ValidationReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("check_id", "category", "status", "message", "details_json"))
        writer.writeheader()
        for item in report.checks:
            writer.writerow({
                "check_id": item.check_id, "category": item.category, "status": item.status,
                "message": item.message,
                "details_json": json.dumps(item.details, ensure_ascii=False, sort_keys=True, allow_nan=False),
            })
    return destination
