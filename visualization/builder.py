"""Build engine-independent visualization data from verified M9/M10/M11 records."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import json
import math
import uuid
from typing import Any

from execution.models import ExperimentResult, RunStatus
from execution.serialization import fingerprint_result
from visualization.models import VisualizationBundle
from visualization.serialization import fingerprint_bundle

DEFAULT_POINT_LIMIT = 20_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, list):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    return value


def _downsample(items: list[Any], limit: int) -> tuple[list[Any], bool]:
    if len(items) <= limit:
        return items, False
    if limit < 2:
        return [items[-1]], True
    indices = sorted({round(index * (len(items) - 1) / (limit - 1)) for index in range(limit)})
    return [items[index] for index in indices], True


def _metrics_by_run(run: Any) -> dict[str, dict[str, Any]]:
    from experimentation.analysis import _metrics_for_run

    result: dict[str, dict[str, Any]] = {}
    for metric in _metrics_for_run(run):
        if metric.name in result:
            raise ValueError(f"Run {run.run_index} contains duplicate metric {metric.name!r}")
        value = metric.value
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Run {run.run_index} metric {metric.name!r} is not finite")
        result[metric.name] = {"value": value, "unit": metric.unit}
    return result


def _abm_view(run: Any, limit: int) -> tuple[dict[str, Any], bool]:
    history = run.trace.get("history", [])
    rule_evaluations = run.trace.get("rule_evaluations", [])
    rule_rows: dict[int, dict[str, int]] = {}
    for item in rule_evaluations if isinstance(rule_evaluations, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("step"), int):
            continue
        by_rule = rule_rows.setdefault(item["step"], {})
        name = str(item.get("rule_id", "unknown"))
        by_rule[name] = by_rule.get(name, 0) + 1
    snapshots = history if isinstance(history, list) else []
    sampled, downsampled = _downsample(snapshots, limit)
    steps: list[dict[str, Any]] = []
    for snapshot in sampled:
        if not isinstance(snapshot, dict):
            continue
        state_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        attributes: dict[str, list[float]] = {}
        for agent in snapshot.get("agents", []):
            if not isinstance(agent, dict):
                continue
            state = str(agent.get("state", "unknown"))
            agent_type = str(agent.get("agent_type", "unknown"))
            state_counts[state] = state_counts.get(state, 0) + 1
            type_counts[agent_type] = type_counts.get(agent_type, 0) + 1
            for name, value in (agent.get("attributes") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    attributes.setdefault(f"{agent_type}:{name}", []).append(float(value))
        steps.append({
            "step": snapshot.get("step", 0),
            "state_counts": state_counts,
            "type_counts": type_counts,
            "attribute_means": {name: sum(values) / len(values) for name, values in sorted(attributes.items()) if values},
            "rule_counts": rule_rows.get(snapshot.get("step"), {}),
        })
    return {"run_index": run.run_index, "kind": "abm", "steps": steps}, downsampled


def _des_view(run: Any, limit: int) -> tuple[dict[str, Any], bool]:
    trace = run.trace
    events = trace.get("events", []) if isinstance(trace.get("events", []), list) else []
    entities = trace.get("entities", []) if isinstance(trace.get("entities", []), list) else []
    resources = trace.get("resources", []) if isinstance(trace.get("resources", []), list) else []
    # Split the per-run budget between potentially large event and entity arrays.
    event_limit = max(1, limit * 2 // 3)
    entity_limit = max(1, limit - event_limit)
    events_kept, events_cut = _downsample(events, event_limit)
    entities_kept, entities_cut = _downsample(entities, entity_limit)
    return {
        "run_index": run.run_index, "kind": "des",
        "events": events_kept, "entities": entities_kept, "resources": resources,
    }, events_cut or entities_cut


def _m10_view(report: Any | None, result: ExperimentResult) -> dict[str, Any] | None:
    if report is None:
        return None
    from experimentation.serialization import fingerprint_report
    if fingerprint_report(report) != report.report_fingerprint:
        raise ValueError("M10 analysis report fingerprint verification failed")
    if (report.artifact_id, report.artifact_fingerprint, report.project_id, report.revision_id, report.revision_version, report.paradigm, report.backend_name) != (
        result.artifact_id, result.artifact_fingerprint, result.project_id, result.revision_id,
        result.revision_version, result.paradigm, result.backend_name,
    ):
        raise ValueError("M10 analysis provenance does not match the supplied M9 result")
    if result.experiment_id not in report.input_experiment_ids:
        raise ValueError("M10 report does not include the supplied M9 experiment")
    expected = report.input_result_fingerprints[report.input_experiment_ids.index(result.experiment_id)]
    if expected != result.result_fingerprint:
        raise ValueError("M10 report records a different fingerprint for the supplied M9 result")
    variants = []
    metric_map: dict[str, list[float]] = {}
    for variant in report.variants:
        metrics = []
        for metric in variant.metrics:
            value = metric.mean if metric.value_type == "numeric" else None
            metrics.append({"name": metric.metric_name, "unit": metric.unit, "value_type": metric.value_type, "mean": value, "minimum": metric.minimum, "maximum": metric.maximum, "sample_size": metric.sample_size})
            if value is not None:
                metric_map.setdefault(metric.metric_name, []).append(float(value))
        variants.append({
            "parameter_set": variant.parameter_set, "parameters": variant.parameters,
            "successful_runs": variant.successful_runs, "failed_runs": variant.failed_runs,
            "metrics": metrics,
        })
    for variant in variants:
        for delta in next((v.deltas_vs_baseline for v in report.variants if v.parameter_set == variant["parameter_set"]), ()):
            variant.setdefault("deltas", []).append({"metric_name": delta.metric_name, "absolute_change": delta.absolute_change, "percent_change": delta.percent_change})
    return {
        "analysis_id": report.analysis_id,
        "variants": variants,
        "metrics": [{"metric_name": name, "values": values} for name, values in sorted(metric_map.items())],
        "warnings": list(report.warnings),
    }


def _m11_view(report: Any | None, result: ExperimentResult) -> dict[str, Any] | None:
    if report is None:
        return None
    from uncertainty.serialization import fingerprint_report
    if fingerprint_report(report) != report.report_fingerprint:
        raise ValueError("M11 uncertainty report fingerprint verification failed")
    if (report.artifact_id, report.artifact_fingerprint, report.project_id, report.revision_id, report.revision_version, report.paradigm, report.backend_name) != (
        result.artifact_id, result.artifact_fingerprint, result.project_id, result.revision_id,
        result.revision_version, result.paradigm, result.backend_name,
    ):
        raise ValueError("M11 report provenance does not match the supplied M9 result")
    if report.experiment_id != result.experiment_id or report.experiment_fingerprint != result.result_fingerprint:
        raise ValueError("M11 report was generated from a different M9 experiment result")
    distributions = [_primitive(item) for item in report.metric_distributions]
    sensitivity = [_primitive(item) for item in report.sensitivity]
    return {
        "report_id": report.report_id,
        "sample_count": report.sample_count,
        "failed_runs": report.failed_runs,
        "distributions": distributions,
        "sensitivity": sensitivity,
        "robustness": _primitive(report.robustness),
        "warnings": list(report.warnings),
    }


def build_visualization_bundle(
    result: ExperimentResult,
    *,
    analysis_report: Any | None = None,
    uncertainty_report: Any | None = None,
    point_limit: int = DEFAULT_POINT_LIMIT,
) -> VisualizationBundle:
    """Create a compact visualization view from exact, integrity-checked records.

    The optional M10/M11 reports must explicitly reference the supplied M9
    execution result and exact M8 artifact provenance.
    """
    if not isinstance(result, ExperimentResult):
        raise TypeError("result must be an ExperimentResult")
    if fingerprint_result(result) != result.result_fingerprint:
        raise ValueError("M9 experiment result fingerprint verification failed")
    if isinstance(point_limit, bool) or not isinstance(point_limit, int) or point_limit < 10:
        raise ValueError("point_limit must be an integer of at least 10")

    warnings: list[str] = []
    completed = [run for run in result.runs if run.status is RunStatus.COMPLETED]
    if not completed:
        raise ValueError("Cannot build a visualization dashboard because the M9 result has no completed runs")
    minimum_budget = max(10, 2 * len(completed))
    if point_limit < minimum_budget:
        raise ValueError(f"point_limit must be at least {minimum_budget} for {len(completed)} completed run(s)")
    views: list[dict[str, Any]] = []
    per_run_limit = point_limit // len(completed)
    metrics_by_run: dict[int, dict[str, dict[str, Any]]] = {}
    for run in result.runs:
        if run.status is not RunStatus.COMPLETED:
            continue
        metrics_by_run[run.run_index] = _metrics_by_run(run)
        if result.paradigm == "agent_based":
            view, trimmed = _abm_view(run, per_run_limit)
        elif result.paradigm == "discrete_event":
            view, trimmed = _des_view(run, per_run_limit)
        else:
            raise ValueError(f"M12 does not implement visual trace adapters for {result.paradigm!r}")
        views.append(view)
        if trimmed:
            warnings.append(f"Run {run.run_index} trace was downsampled to fit the visualization point budget; original M9 records remain unchanged.")

    series_map: dict[str, dict[str, Any]] = {}
    run_rows: list[dict[str, Any]] = []
    for run in result.runs:
        metrics = metrics_by_run.get(run.run_index, {})
        run_rows.append({
            "run_index": run.run_index, "status": run.status.value, "seed": run.seed,
            "parameter_set": run.parameter_set, "parameters": run.parameters,
            "elapsed_seconds": run.elapsed_seconds, "metrics": metrics,
            "error_type": run.error_type, "error_message": run.error_message,
        })
        for name, item in metrics.items():
            value = item["value"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            slot = series_map.setdefault(name, {"name": name, "unit": item["unit"], "points": []})
            if slot["unit"] != item["unit"]:
                raise ValueError(f"Metric {name!r} has inconsistent units across completed executions")
            slot["points"].append({"run_index": run.run_index, "parameter_set": run.parameter_set, "seed": run.seed, "value": float(value)})

    data = {
        "runs": run_rows,
        "metric_series": [series_map[name] for name in sorted(series_map)],
        "trace_views": views,
        "m10": _m10_view(analysis_report, result),
        "m11": _m11_view(uncertainty_report, result),
    }
    warnings.append("Visualizations are descriptive views of recorded simulation outputs. They do not validate or prove the modeled theory.")
    if result.paradigm == "agent_based":
        warnings.append("ABM traces show recorded agent states, numeric attribute summaries and rule evaluations; no unrecorded spatial positions or interactions are inferred.")
    pending = VisualizationBundle(
        schema_version=1, bundle_id="m12-" + uuid.uuid4().hex,
        created_at=_now(), artifact_id=result.artifact_id,
        artifact_fingerprint=result.artifact_fingerprint, project_id=result.project_id,
        project_title=result.project_title, revision_id=result.revision_id,
        revision_version=result.revision_version, paradigm=result.paradigm,
        backend_name=result.backend_name, experiment_id=result.experiment_id,
        experiment_fingerprint=result.result_fingerprint, data=data,
        warnings=tuple(dict.fromkeys(warnings)), bundle_fingerprint="pending",
    )
    return replace(pending, bundle_fingerprint=fingerprint_bundle(pending))
