"""Strict JSON, fingerprint and CSV persistence for M24 suite plans/reports."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from execution.models import ParameterOverride, ParameterSet
from orchestration.models import (
    CategoryCount, ComparisonEntry, ExperimentSuitePlan, ExperimentSuiteReport,
    MetricAggregate, SuiteComparison, SuiteMember, SuiteMemberSummary,
)


class SuiteSerializationError(ValueError):
    """Raised for malformed or tampered M24 suite data."""


def _primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    return value


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def plan_to_dict(plan: ExperimentSuitePlan) -> dict[str, Any]:
    if not isinstance(plan, ExperimentSuitePlan):
        raise TypeError("plan must be an ExperimentSuitePlan")
    return _primitive(plan)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SuiteSerializationError(f"{path} must be an object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    details = []
    if missing:
        details.append("missing " + ", ".join(sorted(missing)))
    if unknown:
        details.append("unknown " + ", ".join(sorted(unknown)))
    if details:
        raise SuiteSerializationError(f"{path} has invalid fields: {'; '.join(details)}")
    return raw


def _parameter_sets(raw: Any, path: str) -> tuple[ParameterSet, ...]:
    if not isinstance(raw, list):
        raise SuiteSerializationError(f"{path} must be an array")
    items = []
    for index, value in enumerate(raw):
        item = _strict(value, ParameterSet, f"{path}[{index}]")
        if not isinstance(item["overrides"], list):
            raise SuiteSerializationError(f"{path}[{index}].overrides must be an array")
        overrides = tuple(
            ParameterOverride(**_strict(override, ParameterOverride, f"{path}[{index}].overrides[{override_index}]"))
            for override_index, override in enumerate(item["overrides"])
        )
        items.append(ParameterSet(name=item["name"], overrides=overrides))
    return tuple(items)


def plan_from_dict(raw: Any) -> ExperimentSuitePlan:
    raw = _strict(raw, ExperimentSuitePlan, "experiment_suite_plan")
    if not isinstance(raw["members"], list):
        raise SuiteSerializationError("members must be an array")
    members = []
    for index, value in enumerate(raw["members"]):
        item = _strict(value, SuiteMember, f"members[{index}]")
        members.append(SuiteMember(
            member_id=item["member_id"], label=item["label"], artifact_path=item["artifact_path"],
            runs=item["runs"], base_seed=item["base_seed"], continue_on_error=item["continue_on_error"],
            parameter_sets=_parameter_sets(item["parameter_sets"], f"members[{index}].parameter_sets"),
        ))
    comparison_raw = raw["comparison"]
    comparison = None if comparison_raw is None else SuiteComparison(**_strict(comparison_raw, SuiteComparison, "comparison"))
    try:
        return ExperimentSuitePlan(
            schema_version=raw["schema_version"], suite_name=raw["suite_name"],
            members=tuple(members), comparison=comparison,
        )
    except (TypeError, ValueError) as error:
        raise SuiteSerializationError(f"experiment_suite_plan is invalid: {error}") from error


def loads_plan(content: str) -> ExperimentSuitePlan:
    try:
        return plan_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise SuiteSerializationError(f"Invalid M24 suite plan JSON: {error}") from error


def load_plan(path: str | Path) -> ExperimentSuitePlan:
    source = Path(path)
    try:
        return loads_plan(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M24 suite plan at {source}: {error}") from error


def report_to_dict(report: ExperimentSuiteReport) -> dict[str, Any]:
    if not isinstance(report, ExperimentSuiteReport):
        raise TypeError("report must be an ExperimentSuiteReport")
    return _primitive(report)


def fingerprint_report(report: ExperimentSuiteReport) -> str:
    data = report_to_dict(report)
    data.pop("report_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_report(report: ExperimentSuiteReport, *, indent: int = 2) -> str:
    if fingerprint_report(report) != report.report_fingerprint:
        raise SuiteSerializationError("M24 suite report fingerprint does not match its content")
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=indent, allow_nan=False)


def report_from_dict(raw: Any) -> ExperimentSuiteReport:
    raw = _strict(raw, ExperimentSuiteReport, "experiment_suite_report")
    plan = plan_from_dict(raw["plan"])
    if not isinstance(raw["members"], list) or not isinstance(raw["ranking"], list) or not isinstance(raw["warnings"], list):
        raise SuiteSerializationError("members, ranking and warnings must be arrays")
    members = []
    for index, value in enumerate(raw["members"]):
        item = _strict(value, SuiteMemberSummary, f"members[{index}]")
        if not isinstance(item["metrics"], list):
            raise SuiteSerializationError(f"members[{index}].metrics must be an array")
        metrics = []
        for metric_index, metric_raw in enumerate(item["metrics"]):
            metric = _strict(metric_raw, MetricAggregate, f"members[{index}].metrics[{metric_index}]")
            if not isinstance(metric["categories"], list):
                raise SuiteSerializationError("metric categories must be an array")
            categories = tuple(CategoryCount(**_strict(category, CategoryCount, "category")) for category in metric["categories"])
            metrics.append(MetricAggregate(**{**metric, "categories": categories}))
        members.append(SuiteMemberSummary(**{**item, "metrics": tuple(metrics)}))
    ranking = tuple(ComparisonEntry(**_strict(item, ComparisonEntry, f"ranking[{index}]")) for index, item in enumerate(raw["ranking"]))
    if any(not isinstance(item, str) for item in raw["warnings"]):
        raise SuiteSerializationError("warnings must contain strings")
    try:
        report = ExperimentSuiteReport(
            schema_version=raw["schema_version"], suite_id=raw["suite_id"], created_at=raw["created_at"],
            suite_name=raw["suite_name"], plan=plan, status=raw["status"], members=tuple(members),
            ranking=ranking, warnings=tuple(raw["warnings"]), report_fingerprint=raw["report_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise SuiteSerializationError(f"M24 suite report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise SuiteSerializationError("M24 suite report fingerprint does not match its stored content")
    return report


def loads_report(content: str) -> ExperimentSuiteReport:
    try:
        return report_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise SuiteSerializationError(f"Invalid M24 suite report JSON: {error}") from error


def save_report(report: ExperimentSuiteReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_report(report), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_report(path: str | Path) -> ExperimentSuiteReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M24 suite report at {source}: {error}") from error


def export_summary_csv(report: ExperimentSuiteReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "member_id", "member_label", "parameter_set", "metric_name", "unit",
            "value_type", "sample_size", "mean", "population_stddev", "categories",
        ])
        writer.writeheader()
        for member in report.members:
            for metric in member.metrics:
                writer.writerow({
                    "member_id": metric.member_id, "member_label": metric.member_label,
                    "parameter_set": metric.parameter_set, "metric_name": metric.metric_name,
                    "unit": metric.unit or "", "value_type": metric.value_type,
                    "sample_size": metric.sample_size,
                    "mean": "" if metric.mean is None else metric.mean,
                    "population_stddev": "" if metric.population_stddev is None else metric.population_stddev,
                    "categories": json.dumps(_primitive(metric.categories), ensure_ascii=False),
                })
    os.replace(temporary, destination)
    return destination
