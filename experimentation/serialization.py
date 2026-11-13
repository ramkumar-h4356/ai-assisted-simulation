"""Strict JSON persistence and integrity verification for M10 reports."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from experimentation.models import (
    AnalysisReport, CategoryCount, FactorLevelSummary, FactorSummary,
    MetricDelta, MetricSummary, VariantSummary,
)


class AnalysisSerializationError(ValueError):
    """Raised for invalid or tampered M10 analysis JSON."""


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


def report_to_dict(report: AnalysisReport) -> dict[str, Any]:
    if not isinstance(report, AnalysisReport):
        raise TypeError("report must be an AnalysisReport")
    return _primitive(report)


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint_report(report: AnalysisReport) -> str:
    data = report_to_dict(report)
    data.pop("report_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_report(report: AnalysisReport, *, indent: int = 2) -> str:
    data = report_to_dict(report)
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalysisSerializationError("M10 report fingerprint does not match its content")
    return json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AnalysisSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    if missing:
        raise AnalysisSerializationError(f"{path} missing field(s): {', '.join(sorted(missing))}")
    if unknown:
        raise AnalysisSerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    return raw


def _array(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise AnalysisSerializationError(f"{path} must be an array")
    return value


def _metric(raw: Any, path: str) -> MetricSummary:
    raw = _strict(raw, MetricSummary, path)
    categories = tuple(
        CategoryCount(**_strict(item, CategoryCount, f"{path}.categories[{index}]"))
        for index, item in enumerate(_array(raw["categories"], f"{path}.categories"))
    )
    try:
        return MetricSummary(
            metric_name=raw["metric_name"], unit=raw["unit"], value_type=raw["value_type"],
            sample_size=raw["sample_size"], mean=raw["mean"],
            population_stddev=raw["population_stddev"], median=raw["median"],
            minimum=raw["minimum"], maximum=raw["maximum"], categories=categories,
        )
    except (TypeError, ValueError) as error:
        raise AnalysisSerializationError(f"{path} is invalid: {error}") from error


def _delta(raw: Any, path: str) -> MetricDelta:
    try:
        return MetricDelta(**_strict(raw, MetricDelta, path))
    except (TypeError, ValueError) as error:
        raise AnalysisSerializationError(f"{path} is invalid: {error}") from error


def _variant(raw: Any, path: str) -> VariantSummary:
    raw = _strict(raw, VariantSummary, path)
    metrics = tuple(_metric(item, f"{path}.metrics[{index}]") for index, item in enumerate(_array(raw["metrics"], f"{path}.metrics")))
    deltas = tuple(_delta(item, f"{path}.deltas_vs_baseline[{index}]") for index, item in enumerate(_array(raw["deltas_vs_baseline"], f"{path}.deltas_vs_baseline")))
    try:
        return VariantSummary(
            parameter_set=raw["parameter_set"], parameters=raw["parameters"],
            total_runs=raw["total_runs"], successful_runs=raw["successful_runs"],
            failed_runs=raw["failed_runs"], metrics=metrics, deltas_vs_baseline=deltas,
        )
    except (TypeError, ValueError) as error:
        raise AnalysisSerializationError(f"{path} is invalid: {error}") from error


def _factor(raw: Any, path: str) -> FactorSummary:
    raw = _strict(raw, FactorSummary, path)
    levels: list[FactorLevelSummary] = []
    for index, item in enumerate(_array(raw["levels"], f"{path}.levels")):
        item = _strict(item, FactorLevelSummary, f"{path}.levels[{index}]")
        metrics = tuple(_metric(value, f"{path}.levels[{index}].metrics[{metric_index}]") for metric_index, value in enumerate(_array(item["metrics"], f"{path}.levels[{index}].metrics")))
        deltas = tuple(_delta(value, f"{path}.levels[{index}].deltas_vs_baseline[{delta_index}]") for delta_index, value in enumerate(_array(item["deltas_vs_baseline"], f"{path}.levels[{index}].deltas_vs_baseline")))
        try:
            levels.append(FactorLevelSummary(
                value=item["value"], successful_runs=item["successful_runs"],
                metrics=metrics, deltas_vs_baseline=deltas,
            ))
        except (TypeError, ValueError) as error:
            raise AnalysisSerializationError(f"{path}.levels[{index}] is invalid: {error}") from error
    try:
        return FactorSummary(target_path=raw["target_path"], baseline_value=raw["baseline_value"], levels=tuple(levels))
    except (TypeError, ValueError) as error:
        raise AnalysisSerializationError(f"{path} is invalid: {error}") from error


def report_from_dict(raw: Any) -> AnalysisReport:
    raw = _strict(raw, AnalysisReport, "analysis_report")
    variants = tuple(_variant(item, f"variants[{index}]") for index, item in enumerate(_array(raw["variants"], "variants")))
    factors = tuple(_factor(item, f"factors[{index}]") for index, item in enumerate(_array(raw["factors"], "factors")))
    for name in ("input_experiment_ids", "input_result_fingerprints", "warnings"):
        if not isinstance(raw[name], list) or any(not isinstance(item, str) for item in raw[name]):
            raise AnalysisSerializationError(f"{name} must be an array of strings")
    try:
        report = AnalysisReport(
            schema_version=raw["schema_version"], analysis_id=raw["analysis_id"],
            created_at=raw["created_at"], artifact_id=raw["artifact_id"],
            artifact_fingerprint=raw["artifact_fingerprint"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], paradigm=raw["paradigm"],
            backend_name=raw["backend_name"], baseline_parameter_set=raw["baseline_parameter_set"],
            input_experiment_ids=tuple(raw["input_experiment_ids"]),
            input_result_fingerprints=tuple(raw["input_result_fingerprints"]),
            variants=variants, factors=factors, warnings=tuple(raw["warnings"]),
            report_fingerprint=raw["report_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise AnalysisSerializationError(f"M10 report is invalid: {error}") from error
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalysisSerializationError("M10 report fingerprint does not match its stored content")
    return report


def loads_report(content: str) -> AnalysisReport:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise AnalysisSerializationError(f"Invalid M10 analysis JSON: {error}") from error
    return report_from_dict(raw)


def save_report(report: AnalysisReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_report(report), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_report(path: str | Path) -> AnalysisReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read M10 analysis at {source}: {error}") from error


def export_summary_csv(report: AnalysisReport, path: str | Path) -> Path:
    """Export one row per parameter-set/metric summary for spreadsheet review."""
    if fingerprint_report(report) != report.report_fingerprint:
        raise AnalysisSerializationError("M10 report fingerprint does not match its content")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "parameter_set", "parameters_json", "total_runs", "successful_runs", "failed_runs",
        "metric_name", "unit", "value_type", "sample_size", "mean", "population_stddev",
        "median", "minimum", "maximum", "categories_json", "delta_vs_baseline", "percent_change",
    )
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for variant in report.variants:
            deltas = {item.metric_name: item for item in variant.deltas_vs_baseline}
            for metric in variant.metrics:
                delta = deltas.get(metric.metric_name)
                writer.writerow({
                    "parameter_set": variant.parameter_set,
                    "parameters_json": json.dumps(variant.parameters, ensure_ascii=False, sort_keys=True),
                    "total_runs": variant.total_runs,
                    "successful_runs": variant.successful_runs,
                    "failed_runs": variant.failed_runs,
                    "metric_name": metric.metric_name,
                    "unit": metric.unit or "",
                    "value_type": metric.value_type,
                    "sample_size": metric.sample_size,
                    "mean": metric.mean if metric.mean is not None else "",
                    "population_stddev": metric.population_stddev if metric.population_stddev is not None else "",
                    "median": metric.median if metric.median is not None else "",
                    "minimum": metric.minimum if metric.minimum is not None else "",
                    "maximum": metric.maximum if metric.maximum is not None else "",
                    "categories_json": json.dumps([_primitive(item) for item in metric.categories], ensure_ascii=False),
                    "delta_vs_baseline": delta.absolute_change if delta else "",
                    "percent_change": delta.percent_change if delta and delta.percent_change is not None else "",
                })
    os.replace(temporary, destination)
    return destination
