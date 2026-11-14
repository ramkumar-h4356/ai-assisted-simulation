"""Strict JSON, SHA-256 verification and CSV exports for M25 analytics."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from analytics.models import (
    AnalyticsPlan, AnalyticsReport, AnalyticsSource, GroupStatistic, Insight,
    MetricDefinition, ObjectiveValue, PairwiseComparison, ParetoEntry, SourceEvidence,
)


class AnalyticsSerializationError(ValueError):
    """Raised for malformed or fingerprint-mismatched M25 analytics data."""


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


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AnalyticsSerializationError(f"{path} must be an object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    details = []
    if missing:
        details.append("missing " + ", ".join(sorted(missing)))
    if unknown:
        details.append("unknown " + ", ".join(sorted(unknown)))
    if details:
        raise AnalyticsSerializationError(f"{path} has invalid fields: {'; '.join(details)}")
    return raw


def plan_to_dict(plan: AnalyticsPlan) -> dict[str, Any]:
    if not isinstance(plan, AnalyticsPlan):
        raise TypeError("plan must be an AnalyticsPlan")
    return _primitive(plan)


def plan_from_dict(raw: Any) -> AnalyticsPlan:
    raw = _strict(raw, AnalyticsPlan, "analytics_plan")
    if not isinstance(raw["sources"], list) or not isinstance(raw["metrics"], list):
        raise AnalyticsSerializationError("sources and metrics must be arrays")
    try:
        sources = tuple(AnalyticsSource(**_strict(item, AnalyticsSource, f"sources[{index}]")) for index, item in enumerate(raw["sources"]))
        metrics = tuple(MetricDefinition(**_strict(item, MetricDefinition, f"metrics[{index}]")) for index, item in enumerate(raw["metrics"]))
        return AnalyticsPlan(
            schema_version=raw["schema_version"], analysis_name=raw["analysis_name"],
            sources=sources, metrics=metrics, alpha=raw["alpha"],
            confidence_level=raw["confidence_level"], minimum_sample_size=raw["minimum_sample_size"],
            max_pairwise_comparisons=raw["max_pairwise_comparisons"],
        )
    except (TypeError, ValueError) as error:
        raise AnalyticsSerializationError(f"analytics plan is invalid: {error}") from error


def report_to_dict(report: AnalyticsReport) -> dict[str, Any]:
    if not isinstance(report, AnalyticsReport):
        raise TypeError("report must be an AnalyticsReport")
    return _primitive(report)


def fingerprint_report(report: AnalyticsReport) -> str:
    data = report_to_dict(report)
    data.pop("report_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_report(report: AnalyticsReport, *, indent: int = 2) -> str:
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalyticsSerializationError("M25 report fingerprint does not match its stored content")
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=indent, allow_nan=False)


def report_from_dict(raw: Any) -> AnalyticsReport:
    raw = _strict(raw, AnalyticsReport, "analytics_report")
    plan = plan_from_dict(raw["plan"])
    arrays = ("sources", "groups", "comparisons", "pareto_frontier", "insights", "warnings")
    if any(not isinstance(raw[name], list) for name in arrays):
        raise AnalyticsSerializationError("report collections must be arrays")
    source_values = []
    for index, item in enumerate(raw["sources"]):
        item = _strict(item, SourceEvidence, f"sources[{index}]")
        for key in ("artifact_ids", "artifact_fingerprints", "project_ids", "revision_ids", "paradigms"):
            if not isinstance(item[key], list) or any(not isinstance(value, str) for value in item[key]):
                raise AnalyticsSerializationError(f"sources[{index}].{key} must be an array of strings")
        source_values.append(SourceEvidence(**{**item, **{key: tuple(item[key]) for key in ("artifact_ids", "artifact_fingerprints", "project_ids", "revision_ids", "paradigms")}}))
    sources = tuple(source_values)
    group_values = []
    for index, item in enumerate(raw["groups"]):
        item = _strict(item, GroupStatistic, f"groups[{index}]")
        if not isinstance(item["experiment_ids"], list) or any(not isinstance(value, str) for value in item["experiment_ids"]):
            raise AnalyticsSerializationError(f"groups[{index}].experiment_ids must be an array of strings")
        group_values.append(GroupStatistic(**{**item, "experiment_ids": tuple(item["experiment_ids"])}))
    groups = tuple(group_values)
    comparisons = tuple(PairwiseComparison(**_strict(item, PairwiseComparison, f"comparisons[{index}]")) for index, item in enumerate(raw["comparisons"]))
    pareto = []
    for index, item in enumerate(raw["pareto_frontier"]):
        item = _strict(item, ParetoEntry, f"pareto_frontier[{index}]")
        if not isinstance(item["objectives"], list) or not isinstance(item["dominated_by"], list):
            raise AnalyticsSerializationError("Pareto objectives and dominated_by must be arrays")
        objectives = tuple(ObjectiveValue(**_strict(value, ObjectiveValue, f"pareto_frontier[{index}].objectives[{j}]")) for j, value in enumerate(item["objectives"]))
        if any(not isinstance(value, str) for value in item["dominated_by"]):
            raise AnalyticsSerializationError("Pareto dominated_by values must be strings")
        pareto.append(ParetoEntry(
            group_id=item["group_id"], group_label=item["group_label"],
            objectives=objectives, pareto_optimal=item["pareto_optimal"], dominated_by=tuple(item["dominated_by"]),
        ))
    insights = []
    for index, item in enumerate(raw["insights"]):
        item = _strict(item, Insight, f"insights[{index}]")
        if not isinstance(item["group_ids"], list) or any(not isinstance(value, str) for value in item["group_ids"]):
            raise AnalyticsSerializationError("insight group_ids must be an array of strings")
        insights.append(Insight(
            code=item["code"], severity=item["severity"], metric_name=item["metric_name"],
            group_ids=tuple(item["group_ids"]), message=item["message"],
        ))
    if any(not isinstance(item, str) for item in raw["warnings"]):
        raise AnalyticsSerializationError("warnings must be strings")
    try:
        report = AnalyticsReport(
            schema_version=raw["schema_version"], analysis_id=raw["analysis_id"],
            created_at=raw["created_at"], plan=plan, sources=sources, groups=groups,
            comparisons=comparisons, pareto_frontier=tuple(pareto), insights=tuple(insights),
            warnings=tuple(raw["warnings"]), report_fingerprint=raw["report_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise AnalyticsSerializationError(f"M25 report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalyticsSerializationError("M25 report fingerprint does not match its stored content")
    return report


def dumps_plan(plan: AnalyticsPlan, *, indent: int = 2) -> str:
    return json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=indent, allow_nan=False)


def loads_plan(content: str) -> AnalyticsPlan:
    try:
        return plan_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise AnalyticsSerializationError(f"Invalid M25 plan JSON: {error}") from error


def load_plan(path: str | Path) -> AnalyticsPlan:
    source = Path(path)
    try:
        return loads_plan(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M25 plan at {source}: {error}") from error


def loads_report(content: str) -> AnalyticsReport:
    try:
        return report_from_dict(json.loads(content))
    except (TypeError, json.JSONDecodeError) as error:
        raise AnalyticsSerializationError(f"Invalid M25 report JSON: {error}") from error


def save_report(report: AnalyticsReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_report(report), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_report(path: str | Path) -> AnalyticsReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M25 report at {source}: {error}") from error


def export_summary_csv(report: AnalyticsReport, path: str | Path) -> Path:
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalyticsSerializationError("M25 report fingerprint does not match its content")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "record_type", "group_id", "group_label", "source_id", "report_type", "metric_name", "unit",
            "sample_size", "mean", "sample_stddev", "standard_error", "confidence_lower", "confidence_upper",
            "total_runs", "observed_runs", "unobserved_runs", "unobserved_fraction", "coefficient_of_variation",
            "group_a", "group_b", "mean_difference_b_minus_a", "welch_t", "degrees_freedom", "p_value",
            "holm_adjusted_p_value", "hedges_g", "effect_magnitude", "significant", "pareto_optimal", "message",
        ))
        writer.writeheader()
        for item in report.groups:
            writer.writerow({
                "record_type": "group", "group_id": item.group_id, "group_label": item.group_label,
                "source_id": item.source_id, "report_type": item.report_type, "metric_name": item.metric_name,
                "unit": item.unit or "", "sample_size": item.sample_size, "mean": item.mean,
                "sample_stddev": "" if item.sample_stddev is None else item.sample_stddev,
                "standard_error": "" if item.standard_error is None else item.standard_error,
                "confidence_lower": "" if item.confidence_lower is None else item.confidence_lower,
                "confidence_upper": "" if item.confidence_upper is None else item.confidence_upper,
                "total_runs": item.total_runs, "observed_runs": item.observed_runs,
                "unobserved_runs": item.unobserved_runs, "unobserved_fraction": item.unobserved_fraction,
                "coefficient_of_variation": "" if item.coefficient_of_variation is None else item.coefficient_of_variation,
            })
        for item in report.comparisons:
            writer.writerow({
                "record_type": "comparison", "metric_name": item.metric_name,
                "group_a": item.group_a, "group_b": item.group_b,
                "mean_difference_b_minus_a": item.mean_difference_b_minus_a, "welch_t": item.welch_t,
                "degrees_freedom": item.degrees_freedom, "p_value": item.p_value,
                "holm_adjusted_p_value": item.holm_adjusted_p_value, "hedges_g": "" if item.hedges_g is None else item.hedges_g,
                "effect_magnitude": item.effect_magnitude, "significant": item.significant,
            })
        for item in report.pareto_frontier:
            writer.writerow({"record_type": "pareto", "group_id": item.group_id, "group_label": item.group_label, "pareto_optimal": item.pareto_optimal})
        for item in report.insights:
            writer.writerow({"record_type": "insight", "metric_name": item.metric_name or "", "message": item.message})
    os.replace(temporary, destination)
    return destination


__all__ = [
    "AnalyticsSerializationError", "dumps_plan", "dumps_report", "export_summary_csv",
    "fingerprint_report", "load_plan", "load_report", "loads_plan", "loads_report",
    "plan_from_dict", "plan_to_dict", "report_from_dict", "report_to_dict", "save_report",
]
