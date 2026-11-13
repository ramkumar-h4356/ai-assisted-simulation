"""Descriptive, provenance-aware analysis of M9 execution results."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import json
import statistics
import uuid
from typing import Iterable

from execution.models import ExperimentResult, MetricRecord, RunRecord, RunStatus
from execution.serialization import fingerprint_result
from experimentation.models import (
    AnalysisReport, CategoryCount, FactorLevelSummary, FactorSummary,
    MetricDelta, MetricSummary, VariantSummary,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _metrics_for_run(run: RunRecord) -> tuple[MetricRecord, ...]:
    """Combine backend metrics with deterministic summaries derived from traces."""
    metrics = list(run.metrics)
    trace = run.trace

    if isinstance(trace.get("history"), list) and trace["history"]:
        final_snapshot = trace["history"][-1]
        agents = final_snapshot.get("agents", []) if isinstance(final_snapshot, dict) else []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for agent in agents if isinstance(agents, list) else []:
            if isinstance(agent, dict) and isinstance(agent.get("agent_type"), str) and isinstance(agent.get("attributes"), dict):
                grouped[agent["agent_type"]].append(agent["attributes"])
        for agent_type, attribute_sets in grouped.items():
            attribute_names = sorted({name for attributes in attribute_sets for name in attributes if isinstance(name, str)})
            for attribute in attribute_names:
                values = [
                    attributes[attribute]
                    for attributes in attribute_sets
                    if isinstance(attributes.get(attribute), (int, float))
                    and not isinstance(attributes.get(attribute), bool)
                ]
                if not values:
                    continue
                prefix = f"derived:abm:{agent_type}:{attribute}"
                metrics.extend((
                    MetricRecord(f"{prefix}:mean", statistics.fmean(values)),
                    MetricRecord(f"{prefix}:sum", sum(values)),
                    MetricRecord(f"{prefix}:minimum", min(values)),
                    MetricRecord(f"{prefix}:maximum", max(values)),
                ))

    entities = trace.get("entities")
    if isinstance(entities, list) and entities:
        fields = (
            ("waiting_time", "derived:des:entities:mean_waiting_time"),
            ("service_time", "derived:des:entities:mean_service_time"),
            ("time_in_system", "derived:des:entities:mean_time_in_system"),
        )
        for field, metric_name in fields:
            values = [
                item[field] for item in entities
                if isinstance(item, dict)
                and isinstance(item.get(field), (int, float))
                and not isinstance(item.get(field), bool)
            ]
            if values:
                metrics.append(MetricRecord(metric_name, statistics.fmean(values), "simulation_time"))

    resources = trace.get("resources")
    if isinstance(resources, list):
        for resource in resources:
            if not isinstance(resource, dict) or not isinstance(resource.get("resource_name"), str):
                continue
            resource_name = resource["resource_name"]
            for field, label, unit in (
                ("utilization", "utilization", "%"),
                ("average_waiting_time", "mean_waiting_time", "simulation_time"),
                ("average_service_time", "mean_service_time", "simulation_time"),
            ):
                value = resource.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    metrics.append(MetricRecord(f"derived:des:resource:{resource_name}:{label}", value, unit))
    return tuple(metrics)


def _metric_summaries(runs: Iterable[RunRecord]) -> tuple[MetricSummary, ...]:
    rows: dict[str, list[tuple[object, str | None]]] = defaultdict(list)
    for run in runs:
        if run.status is not RunStatus.COMPLETED:
            continue
        seen: set[str] = set()
        for metric in _metrics_for_run(run):
            if metric.name in seen:
                raise ValueError(f"Run {run.run_index} contains duplicate metric {metric.name!r}")
            seen.add(metric.name)
            rows[metric.name].append((metric.value, metric.unit))

    summaries: list[MetricSummary] = []
    for name in sorted(rows):
        values = [value for value, _ in rows[name]]
        units = {unit for _, unit in rows[name]}
        if len(units) != 1:
            raise ValueError(f"Metric {name!r} has inconsistent units across input runs")
        unit = next(iter(units))
        numeric = all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)
        if numeric:
            numbers = [float(value) for value in values]
            summaries.append(MetricSummary(
                metric_name=name,
                unit=unit,
                value_type="numeric",
                sample_size=len(numbers),
                mean=statistics.fmean(numbers),
                population_stddev=statistics.pstdev(numbers),
                median=statistics.median(numbers),
                minimum=min(numbers),
                maximum=max(numbers),
            ))
        else:
            if any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                raise ValueError(f"Metric {name!r} mixes numeric and categorical values")
            counts = Counter(_canonical(value) for value in values)
            by_key = {_canonical(value): value for value in values}
            categories = tuple(
                CategoryCount(by_key[key], counts[key])
                for key in sorted(counts)
            )
            summaries.append(MetricSummary(
                metric_name=name,
                unit=unit,
                value_type="categorical",
                sample_size=len(values),
                categories=categories,
            ))
    return tuple(summaries)


def _summary_map(summaries: tuple[MetricSummary, ...]) -> dict[str, MetricSummary]:
    return {item.metric_name: item for item in summaries}


def _deltas(
    baseline: tuple[MetricSummary, ...],
    comparison: tuple[MetricSummary, ...],
) -> tuple[MetricDelta, ...]:
    base_map = _summary_map(baseline)
    deltas: list[MetricDelta] = []
    for current in comparison:
        base = base_map.get(current.metric_name)
        if base is None or base.value_type != "numeric" or current.value_type != "numeric":
            continue
        assert base.mean is not None and current.mean is not None
        difference = current.mean - base.mean
        percent = (difference / abs(base.mean) * 100.0) if base.mean != 0 else None
        deltas.append(MetricDelta(
            metric_name=current.metric_name,
            baseline_mean=base.mean,
            comparison_mean=current.mean,
            absolute_change=difference,
            percent_change=percent,
            baseline_sample_size=base.sample_size,
            comparison_sample_size=current.sample_size,
        ))
    return tuple(deltas)


def analyze_results(
    results: tuple[ExperimentResult, ...],
    *,
    baseline_parameter_set: str | None = None,
) -> AnalysisReport:
    """Compare one or more M9 results from exactly the same M8 artifact.

    Numeric summaries are descriptive: mean, population standard deviation,
    median, minimum and maximum. No hypothesis tests or causal claims are made.
    """
    if not isinstance(results, tuple) or not results or any(not isinstance(item, ExperimentResult) for item in results):
        raise ValueError("results must be a non-empty tuple of ExperimentResult values")

    provenance_fields = (
        "artifact_id", "artifact_fingerprint", "project_id", "project_title",
        "revision_id", "revision_version", "paradigm", "backend_name",
    )
    first = results[0]
    for result in results:
        if fingerprint_result(result) != result.result_fingerprint:
            raise ValueError(f"M9 result {result.experiment_id!r} failed integrity verification")
        if any(getattr(result, field) != getattr(first, field) for field in provenance_fields):
            raise ValueError("All M9 results must come from the same exact M8 artifact and conceptual revision")
    experiment_ids = tuple(item.experiment_id for item in results)
    if len(experiment_ids) != len(set(experiment_ids)):
        raise ValueError("Duplicate M9 experiment IDs were supplied; do not count the same result twice")

    grouped: dict[str, list[RunRecord]] = {}
    parameters_by_variant: dict[str, dict[str, object]] = {}
    for result in results:
        for run in result.runs:
            if run.parameter_set not in grouped:
                grouped[run.parameter_set] = []
                parameters_by_variant[run.parameter_set] = dict(run.parameters)
            elif _canonical(parameters_by_variant[run.parameter_set]) != _canonical(run.parameters):
                raise ValueError(
                    f"Parameter set {run.parameter_set!r} has conflicting parameter values across input results"
                )
            grouped[run.parameter_set].append(run)

    if baseline_parameter_set is None:
        baseline_name = "baseline" if "baseline" in grouped else next(iter(grouped))
    else:
        if not isinstance(baseline_parameter_set, str) or baseline_parameter_set not in grouped:
            raise ValueError(f"Baseline parameter set {baseline_parameter_set!r} was not found")
        baseline_name = baseline_parameter_set

    metric_contracts: dict[str, tuple[str | None, str]] = {}
    for variant_runs in grouped.values():
        for run in variant_runs:
            if run.status is not RunStatus.COMPLETED:
                continue
            for metric in _metrics_for_run(run):
                kind = "numeric" if isinstance(metric.value, (int, float)) and not isinstance(metric.value, bool) else "categorical"
                contract = (metric.unit, kind)
                previous = metric_contracts.setdefault(metric.name, contract)
                if previous != contract:
                    raise ValueError(
                        f"Metric {metric.name!r} has inconsistent units or value types across variants"
                    )

    raw_summaries: dict[str, tuple[MetricSummary, ...]] = {
        name: _metric_summaries(runs)
        for name, runs in grouped.items()
    }
    baseline_metrics = raw_summaries[baseline_name]

    variants: list[VariantSummary] = []
    warnings: list[str] = []
    for name, runs in grouped.items():
        successful = sum(run.status is RunStatus.COMPLETED for run in runs)
        failed = len(runs) - successful
        deltas = () if name == baseline_name else _deltas(baseline_metrics, raw_summaries[name])
        variants.append(VariantSummary(
            parameter_set=name,
            parameters=parameters_by_variant[name],
            total_runs=len(runs),
            successful_runs=successful,
            failed_runs=failed,
            metrics=raw_summaries[name],
            deltas_vs_baseline=deltas,
        ))
        if failed:
            warnings.append(f"Parameter set {name!r} contains {failed} failed run(s); summaries use successful runs only.")

    factor_paths = sorted({path for values in parameters_by_variant.values() for path in values})
    factor_types: dict[str, type] = {}
    for values in parameters_by_variant.values():
        for path, value in values.items():
            previous_type = factor_types.setdefault(path, type(value))
            if previous_type is not type(value):
                raise ValueError(f"Parameter {path!r} has inconsistent scalar types across variants")
    factors: list[FactorSummary] = []
    for path in factor_paths:
        baseline_value = parameters_by_variant[baseline_name].get(path)
        by_level: dict[str, tuple[object, list[RunRecord]]] = {}
        for runs in grouped.values():
            for run in runs:
                if path not in run.parameters or run.status is not RunStatus.COMPLETED:
                    continue
                value = run.parameters[path]
                key = _canonical(value)
                if key not in by_level:
                    by_level[key] = (value, [])
                by_level[key][1].append(run)
        levels: list[FactorLevelSummary] = []
        baseline_level_metrics: tuple[MetricSummary, ...] | None = None
        if baseline_value is not None or path in parameters_by_variant[baseline_name]:
            baseline_level_metrics = next(
                (metrics for value, runs in by_level.values() if _canonical(value) == _canonical(baseline_value)
                 for metrics in (_metric_summaries(runs),)),
                None,
            )
        for key in sorted(by_level):
            value, level_runs = by_level[key]
            metrics = _metric_summaries(level_runs)
            deltas = _deltas(baseline_level_metrics, metrics) if baseline_level_metrics and key != _canonical(baseline_value) else ()
            levels.append(FactorLevelSummary(
                value=value,
                successful_runs=len(level_runs),
                metrics=metrics,
                deltas_vs_baseline=deltas,
            ))
        if levels:
            factors.append(FactorSummary(path, baseline_value, tuple(levels)))
        if path not in parameters_by_variant[baseline_name]:
            warnings.append(f"No baseline value for parameter {path!r}; factor-level deltas are unavailable.")

    if len(factor_paths) > 1:
        warnings.append(
            "Factor-level summaries are marginal means across the other varied factors; "
            "interactions are not separately estimated."
        )
    if first.paradigm == "agent_based" and len(grouped) > 1:
        warnings.append(
            "M9 assigns consecutive seeds across all variants, so ABM variant replications are not paired "
            "with common random numbers. Treat between-variant differences as descriptive."
        )
    if not any(summary.metrics for summary in variants):
        warnings.append("No successful numeric or categorical metrics were available for aggregation.")

    report = AnalysisReport(
        schema_version=1,
        analysis_id="m10-" + uuid.uuid4().hex,
        created_at=_now(),
        artifact_id=first.artifact_id,
        artifact_fingerprint=first.artifact_fingerprint,
        project_id=first.project_id,
        project_title=first.project_title,
        revision_id=first.revision_id,
        revision_version=first.revision_version,
        paradigm=first.paradigm,
        backend_name=first.backend_name,
        baseline_parameter_set=baseline_name,
        input_experiment_ids=experiment_ids,
        input_result_fingerprints=tuple(item.result_fingerprint for item in results),
        variants=tuple(variants),
        factors=tuple(factors),
        warnings=tuple(warnings),
        report_fingerprint="pending",
    )
    from experimentation.serialization import fingerprint_report
    return replace(report, report_fingerprint=fingerprint_report(report))


def run_parameter_sweep(
    artifact,
    factors,
    *,
    runs: int = 1,
    base_seed: int | None = None,
    include_baseline: bool = True,
):
    """Generate and execute a bounded M9 sweep, then return its M10 analysis."""
    from execution import ExperimentConfig, execute_artifact
    from experimentation.grid import generate_parameter_grid

    if isinstance(runs, bool) or not isinstance(runs, int) or not 1 <= runs <= 100:
        raise ValueError("runs must be between 1 and 100")
    max_variants = 100 // runs
    parameter_sets = generate_parameter_grid(
        artifact, factors, include_baseline=include_baseline, max_variants=max_variants
    )
    config = ExperimentConfig(
        runs=runs,
        base_seed=base_seed,
        continue_on_error=True,
        parameter_sets=parameter_sets,
    )
    result = execute_artifact(artifact, config)
    report = analyze_results((result,), baseline_parameter_set="baseline" if include_baseline else None)
    return result, report
