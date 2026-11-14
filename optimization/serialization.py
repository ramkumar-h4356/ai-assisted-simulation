"""Strict JSON persistence and CSV export for M23 optimization reports."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from optimization.models import (
    CandidateSummary, ConstraintEvaluation, MetricConstraint,
    OptimizationObjective, OptimizationPlan, OptimizationReport, SearchParameter,
)


class OptimizationSerializationError(ValueError):
    """Raised for malformed or tampered M23 optimization data."""


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


def plan_to_dict(plan: OptimizationPlan) -> dict[str, Any]:
    if not isinstance(plan, OptimizationPlan):
        raise TypeError("plan must be an OptimizationPlan")
    return _primitive(plan)


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def plan_from_dict(raw: Any) -> OptimizationPlan:
    if not isinstance(raw, dict):
        raise OptimizationSerializationError("optimization_plan must be a JSON object")
    allowed = {item.name for item in fields(OptimizationPlan)}
    required = {"search_parameters", "objective"}
    missing, unknown = required - set(raw), set(raw) - allowed
    if missing or unknown:
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown: " + ", ".join(sorted(unknown)))
        raise OptimizationSerializationError("optimization_plan fields invalid (" + "; ".join(details) + ")")
    try:
        search_parameters_raw = raw["search_parameters"]
        constraints_raw = raw.get("constraints", [])
        if not isinstance(search_parameters_raw, list) or not isinstance(constraints_raw, list):
            raise OptimizationSerializationError("search_parameters and constraints must be arrays")
        parameters = []
        for index, item in enumerate(search_parameters_raw):
            if not isinstance(item, dict) or set(item) != {"target_path", "lower", "upper"}:
                raise OptimizationSerializationError(f"search_parameters[{index}] has invalid fields")
            parameters.append(SearchParameter(**item))
        objective_raw = raw["objective"]
        if not isinstance(objective_raw, dict) or set(objective_raw) - {"metric_name", "direction"} or "metric_name" not in objective_raw:
            raise OptimizationSerializationError("objective has invalid fields")
        objective = OptimizationObjective(
            metric_name=objective_raw["metric_name"],
            direction=objective_raw.get("direction", "minimize"),
        )
        constraints = []
        for index, item in enumerate(constraints_raw):
            required_constraint = {"metric_name", "operator", "threshold"}
            if not isinstance(item, dict) or required_constraint - set(item) or set(item) - required_constraint - {"upper_threshold"}:
                raise OptimizationSerializationError(f"constraints[{index}] has invalid fields")
            constraints.append(MetricConstraint(
                metric_name=item["metric_name"], operator=item["operator"],
                threshold=item["threshold"], upper_threshold=item.get("upper_threshold"),
            ))
        return OptimizationPlan(
            search_parameters=tuple(parameters), objective=objective,
            candidate_count=raw.get("candidate_count", 20),
            replications=raw.get("replications", 1),
            search_seed=raw.get("search_seed", 20261115),
            include_baseline=raw.get("include_baseline", True),
            constraints=tuple(constraints),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, OptimizationSerializationError):
            raise
        raise OptimizationSerializationError(f"optimization_plan is invalid: {error}") from error


def loads_plan(content: str) -> OptimizationPlan:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise OptimizationSerializationError(f"Invalid M23 optimization plan JSON: {error}") from error
    return plan_from_dict(raw)


def load_plan(path: str | Path) -> OptimizationPlan:
    source = Path(path)
    try:
        return loads_plan(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M23 optimization plan at {source}: {error}") from error


def report_to_dict(report: OptimizationReport) -> dict[str, Any]:
    if not isinstance(report, OptimizationReport):
        raise TypeError("report must be an OptimizationReport")
    return _primitive(report)


def fingerprint_report(report: OptimizationReport) -> str:
    data = report_to_dict(report)
    data.pop("report_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_report(report: OptimizationReport, *, indent: int = 2) -> str:
    if fingerprint_report(report) != report.report_fingerprint:
        raise OptimizationSerializationError("M23 report fingerprint does not match its content")
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=indent, allow_nan=False)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise OptimizationSerializationError(f"{path} must be an object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown " + ", ".join(sorted(unknown)))
        raise OptimizationSerializationError(f"{path} has invalid fields: {'; '.join(details)}")
    return raw


def report_from_dict(raw: Any) -> OptimizationReport:
    raw = _strict(raw, OptimizationReport, "optimization_report")
    if not isinstance(raw["candidates"], list) or not isinstance(raw["warnings"], list):
        raise OptimizationSerializationError("candidates and warnings must be arrays")
    if any(not isinstance(item, str) for item in raw["warnings"]):
        raise OptimizationSerializationError("warnings must contain strings")
    candidates = []
    for index, item in enumerate(raw["candidates"]):
        item = _strict(item, CandidateSummary, f"candidates[{index}]")
        if not isinstance(item["constraints"], list):
            raise OptimizationSerializationError(f"candidates[{index}].constraints must be an array")
        constraints = []
        for constraint_index, constraint in enumerate(item["constraints"]):
            try:
                constraints.append(ConstraintEvaluation(**_strict(
                    constraint, ConstraintEvaluation, f"candidates[{index}].constraints[{constraint_index}]"
                )))
            except (TypeError, ValueError) as error:
                raise OptimizationSerializationError(f"candidate constraint is invalid: {error}") from error
        try:
            candidates.append(CandidateSummary(
                parameter_set=item["parameter_set"], parameters=item["parameters"],
                total_runs=item["total_runs"], successful_runs=item["successful_runs"],
                failed_runs=item["failed_runs"], objective_mean=item["objective_mean"],
                objective_population_stddev=item["objective_population_stddev"],
                objective_sample_size=item["objective_sample_size"], feasible=item["feasible"],
                status=item["status"], constraints=tuple(constraints),
            ))
        except (TypeError, ValueError) as error:
            raise OptimizationSerializationError(f"candidate {index} is invalid: {error}") from error
    try:
        report = OptimizationReport(
            schema_version=raw["schema_version"], optimization_id=raw["optimization_id"],
            created_at=raw["created_at"], artifact_id=raw["artifact_id"],
            artifact_fingerprint=raw["artifact_fingerprint"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], paradigm=raw["paradigm"],
            backend_name=raw["backend_name"], algorithm=raw["algorithm"],
            plan=plan_from_dict(raw["plan"]), experiment_id=raw["experiment_id"],
            experiment_fingerprint=raw["experiment_fingerprint"], candidates=tuple(candidates),
            baseline_parameter_set=raw["baseline_parameter_set"], best_parameter_set=raw["best_parameter_set"],
            objective_improvement=raw["objective_improvement"], warnings=tuple(raw["warnings"]),
            report_fingerprint=raw["report_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, OptimizationSerializationError):
            raise
        raise OptimizationSerializationError(f"M23 report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise OptimizationSerializationError("M23 report fingerprint does not match its stored content")
    return report


def loads_report(content: str) -> OptimizationReport:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise OptimizationSerializationError(f"Invalid M23 optimization report JSON: {error}") from error
    return report_from_dict(raw)


def save_report(report: OptimizationReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_report(report), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_report(path: str | Path) -> OptimizationReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M23 report at {source}: {error}") from error


def export_summary_csv(report: OptimizationReport, path: str | Path) -> Path:
    if fingerprint_report(report) != report.report_fingerprint:
        raise OptimizationSerializationError("M23 report fingerprint does not match its content")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    fields = (
        "parameter_set", "parameters_json", "total_runs", "successful_runs", "failed_runs",
        "objective_metric", "objective_mean", "objective_population_stddev", "objective_sample_size",
        "feasible", "status", "constraints_json",
    )
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for candidate in report.candidates:
            writer.writerow({
                "parameter_set": candidate.parameter_set,
                "parameters_json": json.dumps(candidate.parameters, sort_keys=True, allow_nan=False),
                "total_runs": candidate.total_runs,
                "successful_runs": candidate.successful_runs,
                "failed_runs": candidate.failed_runs,
                "objective_metric": report.plan.objective.metric_name,
                "objective_mean": candidate.objective_mean,
                "objective_population_stddev": candidate.objective_population_stddev,
                "objective_sample_size": candidate.objective_sample_size,
                "feasible": candidate.feasible,
                "status": candidate.status,
                "constraints_json": json.dumps(_primitive(candidate.constraints), sort_keys=True, allow_nan=False),
            })
    os.replace(temporary, destination)
    return destination


__all__ = [
    "OptimizationSerializationError", "dumps_report", "export_summary_csv",
    "fingerprint_report", "load_plan", "load_report", "loads_plan",
    "loads_report", "plan_from_dict", "plan_to_dict", "report_from_dict",
    "report_to_dict", "save_report",
]
