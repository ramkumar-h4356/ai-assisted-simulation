"""Strict, integrity-checked persistence for M11 plans and reports."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from uncertainty.models import (
    CriterionResult, MetricDistribution, RobustnessCriterion, RobustnessSummary,
    SensitivityScore, UncertainParameter, UncertaintyPlan, UncertaintyReport,
)


class UncertaintySerializationError(ValueError):
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


def report_to_dict(report: UncertaintyReport) -> dict[str, Any]:
    if not isinstance(report, UncertaintyReport):
        raise TypeError("report must be an UncertaintyReport")
    return _primitive(report)


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint_report(report: UncertaintyReport) -> str:
    data = report_to_dict(report)
    data.pop("report_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_report(report: UncertaintyReport, *, indent: int = 2) -> str:
    data = report_to_dict(report)
    if fingerprint_report(report) != report.report_fingerprint:
        raise UncertaintySerializationError("M11 report fingerprint does not match its content")
    return json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise UncertaintySerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    if missing:
        raise UncertaintySerializationError(f"{path} missing field(s): {', '.join(sorted(missing))}")
    if unknown:
        raise UncertaintySerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    return raw


def _array(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise UncertaintySerializationError(f"{path} must be an array")
    return value


def plan_from_dict(raw: Any) -> UncertaintyPlan:
    if not isinstance(raw, dict):
        raise UncertaintySerializationError("uncertainty_plan must be a JSON object")
    required = {"sample_count", "sampling_seed", "parameters"}
    allowed = required | {"criteria"}
    missing, unknown = required - set(raw), set(raw) - allowed
    if missing or unknown:
        details = []
        if missing:
            details.append("missing field(s): " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown field(s): " + ", ".join(sorted(unknown)))
        raise UncertaintySerializationError("uncertainty_plan " + "; ".join(details))

    parameters_list = []
    for index, item in enumerate(_array(raw["parameters"], "parameters")):
        if not isinstance(item, dict):
            raise UncertaintySerializationError(f"parameters[{index}] must be a JSON object")
        param_required = {"target_path", "distribution", "lower", "upper"}
        param_allowed = param_required | {"mode"}
        param_missing, param_unknown = param_required - set(item), set(item) - param_allowed
        if param_missing or param_unknown:
            raise UncertaintySerializationError(f"parameters[{index}] has missing or unknown fields")
        parameters_list.append(UncertainParameter(
            target_path=item["target_path"], distribution=item["distribution"],
            lower=item["lower"], upper=item["upper"], mode=item.get("mode"),
        ))

    criteria_list = []
    for index, item in enumerate(_array(raw.get("criteria", []), "criteria")):
        if not isinstance(item, dict):
            raise UncertaintySerializationError(f"criteria[{index}] must be a JSON object")
        criterion_required = {"metric_name", "operator", "threshold"}
        criterion_allowed = criterion_required | {"upper_threshold"}
        criterion_missing, criterion_unknown = criterion_required - set(item), set(item) - criterion_allowed
        if criterion_missing or criterion_unknown:
            raise UncertaintySerializationError(f"criteria[{index}] has missing or unknown fields")
        criteria_list.append(RobustnessCriterion(
            metric_name=item["metric_name"], operator=item["operator"],
            threshold=item["threshold"], upper_threshold=item.get("upper_threshold"),
        ))

    try:
        return UncertaintyPlan(
            sample_count=raw["sample_count"], sampling_seed=raw["sampling_seed"],
            parameters=tuple(parameters_list), criteria=tuple(criteria_list),
        )
    except (TypeError, ValueError) as error:
        raise UncertaintySerializationError(f"uncertainty_plan is invalid: {error}") from error


def load_plan(path: str | Path) -> UncertaintyPlan:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M11 plan at {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise UncertaintySerializationError(f"Invalid M11 plan JSON: {error}") from error
    return plan_from_dict(raw)


def report_from_dict(raw: Any) -> UncertaintyReport:
    raw = _strict(raw, UncertaintyReport, "uncertainty_report")
    parameters = tuple(
        UncertainParameter(**_strict(item, UncertainParameter, f"parameters[{index}]"))
        for index, item in enumerate(_array(raw["parameters"], "parameters"))
    )
    criteria = tuple(
        RobustnessCriterion(**_strict(item, RobustnessCriterion, f"criteria[{index}]"))
        for index, item in enumerate(_array(raw["criteria"], "criteria"))
    )
    distributions = tuple(
        MetricDistribution(**_strict(item, MetricDistribution, f"metric_distributions[{index}]"))
        for index, item in enumerate(_array(raw["metric_distributions"], "metric_distributions"))
    )
    sensitivity = tuple(
        SensitivityScore(**_strict(item, SensitivityScore, f"sensitivity[{index}]"))
        for index, item in enumerate(_array(raw["sensitivity"], "sensitivity"))
    )
    robustness_raw = _strict(raw["robustness"], RobustnessSummary, "robustness")
    criterion_results = tuple(
        CriterionResult(**_strict(item, CriterionResult, f"robustness.criteria[{index}]"))
        for index, item in enumerate(_array(robustness_raw["criteria"], "robustness.criteria"))
    )
    robustness = RobustnessSummary(
        evaluated_runs=robustness_raw["evaluated_runs"],
        passing_runs=robustness_raw["passing_runs"],
        observed_fraction=robustness_raw["observed_fraction"],
        criteria=criterion_results,
    )
    if not isinstance(raw["warnings"], list) or any(not isinstance(item, str) for item in raw["warnings"]):
        raise UncertaintySerializationError("warnings must be an array of strings")
    try:
        report = UncertaintyReport(
            schema_version=raw["schema_version"], report_id=raw["report_id"],
            created_at=raw["created_at"], artifact_id=raw["artifact_id"],
            artifact_fingerprint=raw["artifact_fingerprint"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], paradigm=raw["paradigm"],
            backend_name=raw["backend_name"], experiment_id=raw["experiment_id"],
            experiment_fingerprint=raw["experiment_fingerprint"], sample_count=raw["sample_count"],
            sampling_seed=raw["sampling_seed"], parameters=parameters, criteria=criteria,
            metric_distributions=distributions, sensitivity=sensitivity, robustness=robustness,
            failed_runs=raw["failed_runs"], warnings=tuple(raw["warnings"]),
            report_fingerprint=raw["report_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise UncertaintySerializationError(f"M11 report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise UncertaintySerializationError("M11 report fingerprint does not match its stored content")
    return report


def loads_report(content: str) -> UncertaintyReport:
    try:
        return report_from_dict(json.loads(content))
    except json.JSONDecodeError as error:
        raise UncertaintySerializationError(f"Invalid M11 report JSON: {error}") from error


def save_report(report: UncertaintyReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_report(report), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_report(path: str | Path) -> UncertaintyReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M11 report at {source}: {error}") from error


def export_summary_csv(report: UncertaintyReport, path: str | Path) -> Path:
    if fingerprint_report(report) != report.report_fingerprint:
        raise UncertaintySerializationError("M11 report fingerprint does not match its content")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "record_type", "parameter_path", "metric_name", "unit", "sample_size",
            "mean", "population_stddev", "median", "percentile_05", "percentile_95",
            "minimum", "maximum", "spearman_rho", "absolute_rho", "direction", "rank",
            "criterion_operator", "threshold", "upper_threshold", "evaluated_runs",
            "passing_runs", "observed_fraction",
        ))
        writer.writeheader()
        for metric in report.metric_distributions:
            writer.writerow({"record_type": "metric_distribution", "metric_name": metric.metric_name, "unit": metric.unit or "", "sample_size": metric.sample_size, "mean": metric.mean, "population_stddev": metric.population_stddev, "median": metric.median, "percentile_05": metric.percentile_05, "percentile_95": metric.percentile_95, "minimum": metric.minimum, "maximum": metric.maximum})
        for score in report.sensitivity:
            writer.writerow({"record_type": "sensitivity", "parameter_path": score.parameter_path, "metric_name": score.metric_name, "sample_size": score.sample_size, "spearman_rho": score.spearman_rho if score.spearman_rho is not None else "", "absolute_rho": score.absolute_rho if score.absolute_rho is not None else "", "direction": score.direction, "rank": score.rank if score.rank is not None else ""})
        for criterion in report.robustness.criteria:
            writer.writerow({"record_type": "robustness_criterion", "metric_name": criterion.metric_name, "criterion_operator": criterion.operator, "threshold": criterion.threshold, "upper_threshold": criterion.upper_threshold if criterion.upper_threshold is not None else "", "evaluated_runs": criterion.evaluated_runs, "passing_runs": criterion.passing_runs, "observed_fraction": criterion.observed_fraction if criterion.observed_fraction is not None else ""})
        writer.writerow({"record_type": "robustness_all_criteria", "evaluated_runs": report.robustness.evaluated_runs, "passing_runs": report.robustness.passing_runs, "observed_fraction": report.robustness.observed_fraction if report.robustness.observed_fraction is not None else ""})
    os.replace(temporary, destination)
    return destination
