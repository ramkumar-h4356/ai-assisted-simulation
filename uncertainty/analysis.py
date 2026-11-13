"""M11 uncertainty propagation, screening sensitivity and robustness analysis."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import statistics
import uuid
from typing import Any

from compilation import CompilationArtifact
from execution import ExperimentResult, RunStatus
from execution.serialization import fingerprint_result
from experimentation.analysis import _metrics_for_run
from uncertainty.models import (
    CriterionResult, MetricDistribution, RobustnessCriterion,
    RobustnessSummary, SensitivityScore, UncertaintyPlan, UncertaintyReport,
)
from uncertainty.sampling import generate_parameter_samples


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _average_ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = ((index + 1) + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average
        index = end
    return ranks


def _spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left_ranks, right_ranks))
    left_ss = sum((x - left_mean) ** 2 for x in left_ranks)
    right_ss = sum((y - right_mean) ** 2 for y in right_ranks)
    denominator = math.sqrt(left_ss * right_ss)
    if denominator == 0:
        return None
    value = numerator / denominator
    return max(-1.0, min(1.0, value))


def _criterion_passes(value: float, criterion: RobustnessCriterion) -> bool:
    if criterion.operator == "<=":
        return value <= criterion.threshold
    if criterion.operator == ">=":
        return value >= criterion.threshold
    return criterion.threshold <= value <= criterion.upper_threshold


def analyze_uncertainty(
    artifact: CompilationArtifact,
    plan: UncertaintyPlan,
    result: ExperimentResult,
) -> UncertaintyReport:
    """Analyze one verified M9 run per sampled parameter vector.

    Results summarize the declared input distributions propagated through
    the selected model. For ABM, the observed output spread also includes
    the changing M9 random seeds; it does not separate input and process
    uncertainty without a more elaborate replicated design.
    """
    from compilation import verify_artifact

    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed")
    if not isinstance(plan, UncertaintyPlan):
        raise TypeError("plan must be an UncertaintyPlan")
    if not isinstance(result, ExperimentResult):
        raise TypeError("result must be an ExperimentResult")
    if fingerprint_result(result) != result.result_fingerprint:
        raise ValueError("M9 experiment result integrity verification failed")
    if (result.artifact_id, result.artifact_fingerprint) != (artifact.artifact_id, artifact.artifact_fingerprint):
        raise ValueError("M9 result does not belong to the supplied exact M8 artifact")
    if result.config.runs != 1 or len(result.runs) != plan.sample_count or len(result.config.parameter_sets) != plan.sample_count:
        raise ValueError("M11 requires exactly one M9 execution for each planned Monte Carlo sample")

    expected_samples = generate_parameter_samples(artifact, plan)
    expected = {
        item.name: {override.target_path: override.value for override in item.overrides}
        for item in expected_samples
    }
    actual_sets = {item.name: {override.target_path: override.value for override in item.overrides} for item in result.config.parameter_sets}
    if actual_sets != expected or len(actual_sets) != len(expected):
        raise ValueError("M9 parameter sets do not match the exact M11 plan samples")

    if (result.project_id, result.project_title, result.revision_id, result.revision_version, result.paradigm, result.backend_name) != (
        artifact.project_id, artifact.project_title, artifact.revision_id, artifact.revision_version,
        artifact.paradigm.value, artifact.backend_name,
    ):
        raise ValueError("M9 result provenance does not match the supplied M8 artifact")

    run_by_sample = {run.parameter_set: run for run in result.runs}
    if set(run_by_sample) != set(expected):
        raise ValueError("M9 result must contain exactly one run for every M11 sample")
    for sample_name, run in run_by_sample.items():
        if run.parameters != expected[sample_name]:
            raise ValueError(f"M9 run parameters for {sample_name!r} do not match the planned sample vector")
    successful = [run_by_sample[name] for name in expected if run_by_sample[name].status is RunStatus.COMPLETED]
    failed = plan.sample_count - len(successful)
    warnings: list[str] = []
    if failed:
        warnings.append(f"{failed} of {plan.sample_count} sampled executions failed and were excluded from outcome analysis.")
    if result.paradigm == "agent_based":
        warnings.append("ABM output distributions include both sampled parameter variation and stochastic run-to-run variation; these uncertainty sources are not separated in M11 V1.")
    warnings.append("Spearman scores are monotonic association screening statistics, not causal effects. Interactions and non-monotonic effects may be missed.")
    warnings.append("Robustness fractions are observed proportions under this finite sampling design, not calibrated real-world probabilities or proof that the theory is true.")

    metric_rows: dict[str, list[tuple[float, str | None, str]]] = defaultdict(list)
    sample_parameter_values = {
        item.name: {override.target_path: override.value for override in item.overrides}
        for item in result.config.parameter_sets
    }
    for run in successful:
        per_run: dict[str, tuple[Any, str | None]] = {}
        for metric in _metrics_for_run(run):
            if metric.name in per_run:
                raise ValueError(f"M9 run {run.run_index} contains duplicate metric {metric.name!r}")
            per_run[metric.name] = (metric.value, metric.unit)
        for name, (value, unit) in per_run.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                raise ValueError(f"M9 metric {name!r} contains a non-finite numeric value")
            metric_rows[name].append((float(value), unit, run.parameter_set))

    distributions: list[MetricDistribution] = []
    for metric_name in sorted(metric_rows):
        rows = metric_rows[metric_name]
        units = {item[1] for item in rows}
        if len(units) != 1:
            raise ValueError(f"Metric {metric_name!r} has inconsistent units across M11 samples")
        values = [item[0] for item in rows]
        minimum = min(values)
        maximum = max(values)
        median = statistics.median(values)
        # Clamp floating-point interpolation round-off to mathematically valid bounds.
        mean = min(maximum, max(minimum, statistics.fmean(values)))
        percentile_05 = min(median, max(minimum, _percentile(values, 0.05)))
        percentile_95 = max(median, min(maximum, _percentile(values, 0.95)))
        if len(values) < len(successful):
            warnings.append(
                f"Metric {metric_name!r} is available for {len(values)} of {len(successful)} successful runs; "
                "its summaries use only available observations."
            )
        distributions.append(MetricDistribution(
            metric_name=metric_name,
            unit=next(iter(units)),
            sample_size=len(values),
            mean=mean,
            population_stddev=statistics.pstdev(values),
            median=median,
            percentile_05=percentile_05,
            percentile_95=percentile_95,
            minimum=minimum,
            maximum=maximum,
        ))

    sensitivity_raw: list[tuple[str, str, int, float | None]] = []
    for parameter in plan.parameters:
        for metric_name in sorted(metric_rows):
            rows = metric_rows[metric_name]
            x: list[float] = []
            y: list[float] = []
            for metric_value, _unit, sample_name in rows:
                value = sample_parameter_values[sample_name][parameter.target_path]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    x.append(float(value))
                    y.append(metric_value)
            rho = _spearman(x, y)
            sensitivity_raw.append((parameter.target_path, metric_name, len(x), rho))

    by_metric: dict[str, list[tuple[str, int, float | None]]] = defaultdict(list)
    for path, metric_name, count, rho in sensitivity_raw:
        by_metric[metric_name].append((path, count, rho))
    sensitivity: list[SensitivityScore] = []
    for metric_name in sorted(by_metric):
        estimable = sorted(
            ((path, count, rho) for path, count, rho in by_metric[metric_name] if rho is not None),
            key=lambda item: abs(item[2]), reverse=True,
        )
        rank_by_path = {path: index for index, (path, _count, _rho) in enumerate(estimable, start=1)}
        for path, count, rho in sorted(by_metric[metric_name], key=lambda item: item[0]):
            if rho is None:
                sensitivity.append(SensitivityScore(path, metric_name, count, None, None, "not_estimable", None))
            else:
                direction = "positive" if rho > 0 else "negative" if rho < 0 else "no_monotonic_association"
                sensitivity.append(SensitivityScore(path, metric_name, count, rho, abs(rho), direction, rank_by_path[path]))

    metric_values_by_run: dict[str, dict[str, float]] = {}
    for metric_name, rows in metric_rows.items():
        for value, _unit, sample_name in rows:
            metric_values_by_run.setdefault(sample_name, {})[metric_name] = value

    criterion_results: list[CriterionResult] = []
    combined_passes = 0
    combined_evaluated = 0
    if plan.criteria:
        for criterion in plan.criteria:
            evaluated = [
                metric_values_by_run[name][criterion.metric_name]
                for name in expected
                if name in metric_values_by_run and criterion.metric_name in metric_values_by_run[name]
            ]
            missing = plan.sample_count - len(evaluated)
            if missing:
                warnings.append(f"Robustness criterion {criterion.metric_name!r} could not be evaluated for {missing} samples (failed run or metric unavailable).")
            passing = sum(_criterion_passes(value, criterion) for value in evaluated)
            criterion_results.append(CriterionResult(
                metric_name=criterion.metric_name, operator=criterion.operator,
                threshold=float(criterion.threshold),
                upper_threshold=float(criterion.upper_threshold) if criterion.upper_threshold is not None else None,
                evaluated_runs=len(evaluated), passing_runs=passing,
                observed_fraction=passing / len(evaluated) if evaluated else None,
            ))
        for name in expected:
            if name not in metric_values_by_run or any(item.metric_name not in metric_values_by_run[name] for item in plan.criteria):
                continue
            combined_evaluated += 1
            if all(_criterion_passes(metric_values_by_run[name][item.metric_name], item) for item in plan.criteria):
                combined_passes += 1
    robustness = RobustnessSummary(
        evaluated_runs=combined_evaluated,
        passing_runs=combined_passes,
        observed_fraction=combined_passes / combined_evaluated if combined_evaluated else None,
        criteria=tuple(criterion_results),
    )
    if not distributions:
        warnings.append("No numeric metrics were available from successful runs; uncertainty summaries and sensitivity scores are empty.")
    if plan.sample_count < 20:
        warnings.append("The sample count is small for global sensitivity screening; increase it for more stable exploratory estimates when execution cost permits.")

    from uncertainty.serialization import fingerprint_report
    pending = UncertaintyReport(
        schema_version=1,
        report_id="m11-" + uuid.uuid4().hex,
        created_at=_now(),
        artifact_id=artifact.artifact_id,
        artifact_fingerprint=artifact.artifact_fingerprint,
        project_id=artifact.project_id,
        project_title=artifact.project_title,
        revision_id=artifact.revision_id,
        revision_version=artifact.revision_version,
        paradigm=artifact.paradigm.value,
        backend_name=artifact.backend_name,
        experiment_id=result.experiment_id,
        experiment_fingerprint=result.result_fingerprint,
        sample_count=plan.sample_count,
        sampling_seed=plan.sampling_seed,
        parameters=plan.parameters,
        criteria=plan.criteria,
        metric_distributions=tuple(distributions),
        sensitivity=tuple(sensitivity),
        robustness=robustness,
        failed_runs=failed,
        warnings=tuple(dict.fromkeys(warnings)),
        report_fingerprint="pending",
    )
    from dataclasses import replace
    return replace(pending, report_fingerprint=fingerprint_report(pending))


def run_uncertainty_analysis(
    artifact: CompilationArtifact,
    plan: UncertaintyPlan,
    *,
    execution_base_seed: int | None = None,
) -> tuple[ExperimentResult, UncertaintyReport]:
    """Generate M11 input samples, execute them through M9, and analyze the result."""
    from execution import ExperimentConfig, execute_artifact

    samples = generate_parameter_samples(artifact, plan)
    config = ExperimentConfig(
        runs=1,
        base_seed=execution_base_seed,
        continue_on_error=True,
        parameter_sets=samples,
    )
    result = execute_artifact(artifact, config)
    return result, analyze_uncertainty(artifact, plan, result)
