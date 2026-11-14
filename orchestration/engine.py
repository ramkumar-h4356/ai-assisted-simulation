"""Execute bounded, provenance-aware suites of heterogeneous M8 artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
from pathlib import Path
import statistics
import uuid

from compilation import load_artifact
from execution import ExperimentConfig, ExperimentStatus, RunStatus, execute_artifact, save_result
from orchestration.models import (
    CategoryCount, ComparisonEntry, ExperimentSuitePlan, ExperimentSuiteReport,
    MetricAggregate, SuiteMemberSummary,
)
from orchestration.serialization import fingerprint_report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_artifact(root: Path, relative_path: str) -> Path:
    root_resolved = root.expanduser().resolve()
    candidate = (root_resolved / relative_path.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError(f"artifact path escapes the configured artifact root: {relative_path!r}") from error
    return candidate


def _aggregate_metrics(member_id: str, label: str, result) -> tuple[tuple[MetricAggregate, ...], tuple[str, ...]]:
    grouped: dict[str, list] = defaultdict(list)
    warnings: list[str] = []
    for run in result.runs:
        if run.status is RunStatus.COMPLETED:
            grouped[run.parameter_set].append(run)

    aggregates: list[MetricAggregate] = []
    for parameter_set, runs in grouped.items():
        by_name: dict[str, list[tuple[str | None, object]]] = defaultdict(list)
        for run in runs:
            seen: set[str] = set()
            for metric in run.metrics:
                if metric.name in seen:
                    warnings.append(f"{member_id}/{run.parameter_set}/{metric.name}: duplicate metric name in one M9 run; duplicate value ignored")
                    continue
                seen.add(metric.name)
                by_name[metric.name].append((metric.unit, metric.value))
        for metric_name, records in by_name.items():
            units = {unit for unit, _ in records}
            value_types = {"numeric" if isinstance(value, (int, float)) and not isinstance(value, bool) else "categorical" for _, value in records}
            if len(units) != 1 or len(value_types) != 1:
                warnings.append(f"{member_id}/{parameter_set}/{metric_name}: inconsistent metric units or value types across replications; aggregate omitted")
                continue
            unit = next(iter(units))
            value_type = next(iter(value_types))
            values = [value for _, value in records]
            if value_type == "numeric":
                numeric_values = [float(value) for value in values]
                aggregates.append(MetricAggregate(
                    member_id=member_id, member_label=label, parameter_set=parameter_set,
                    metric_name=metric_name, unit=unit, value_type="numeric", sample_size=len(values),
                    mean=statistics.fmean(numeric_values), population_stddev=statistics.pstdev(numeric_values),
                ))
            else:
                categories = Counter(str(value).lower() if isinstance(value, bool) else str(value) for value in values)
                aggregates.append(MetricAggregate(
                    member_id=member_id, member_label=label, parameter_set=parameter_set,
                    metric_name=metric_name, unit=unit, value_type="categorical", sample_size=len(values),
                    categories=tuple(CategoryCount(value=value, count=count) for value, count in sorted(categories.items())),
                ))
    return (
        tuple(sorted(aggregates, key=lambda item: (item.parameter_set, item.metric_name, item.unit or ""))),
        tuple(warnings),
    )


def execute_suite(
    plan: ExperimentSuitePlan,
    *,
    artifact_root: str | Path,
    output_dir: str | Path,
) -> ExperimentSuiteReport:
    """Execute each suite member through M9 and save each integrity-checked M9 result.

    Artifact paths are relative to ``artifact_root`` and cannot escape it. A
    member failure is retained in the suite report while later members run.
    The suite has a fixed maximum of 100 requested M9 executions.
    """
    if not isinstance(plan, ExperimentSuitePlan):
        raise TypeError("plan must be an ExperimentSuitePlan")
    if plan.total_executions > 100:
        raise ValueError("M24 suite exceeds the global budget of 100 M9 executions")
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    suite_id = "m24-" + uuid.uuid4().hex
    summaries: list[SuiteMemberSummary] = []
    warnings: list[str] = []

    for member in plan.members:
        artifact = None
        result = None
        result_file = None
        try:
            artifact_path = _resolve_artifact(Path(artifact_root), member.artifact_path)
            artifact = load_artifact(artifact_path)
            result = execute_artifact(artifact, ExperimentConfig(
                runs=member.runs,
                base_seed=member.base_seed,
                continue_on_error=member.continue_on_error,
                parameter_sets=member.parameter_sets,
            ))
            result_file_name = f"{suite_id}_{member.member_id}_m9_result.json"
            save_result(result, output / result_file_name)
            result_file = result_file_name
            metrics, aggregation_warnings = _aggregate_metrics(member.member_id, member.label, result)
            warnings.extend(aggregation_warnings)
            for metric in metrics:
                if metric.sample_size < member.runs:
                    warnings.append(
                        f"{member.member_id}/{metric.parameter_set}/{metric.metric_name}: metric observed in "
                        f"{metric.sample_size} of {member.runs} requested replications"
                    )
            summaries.append(SuiteMemberSummary(
                member_id=member.member_id, label=member.label, artifact_path=member.artifact_path,
                artifact_id=artifact.artifact_id, artifact_fingerprint=artifact.artifact_fingerprint,
                project_id=artifact.project_id, project_title=artifact.project_title,
                revision_id=artifact.revision_id, revision_version=artifact.revision_version,
                paradigm=artifact.paradigm.value, backend_name=artifact.backend_name,
                experiment_id=result.experiment_id, experiment_fingerprint=result.result_fingerprint,
                result_file=result_file, status=result.status.value, total_runs=len(result.runs),
                successful_runs=sum(item.status is RunStatus.COMPLETED for item in result.runs),
                failed_runs=sum(item.status is RunStatus.FAILED for item in result.runs), metrics=metrics,
            ))
            if result.status is not ExperimentStatus.COMPLETED:
                warnings.append(f"{member.member_id} completed with M9 status {result.status.value}")
        except Exception as error:
            if artifact is not None and result is not None:
                # Saving a result failure is fatal: do not claim its provenance was persisted.
                raise
            summaries.append(SuiteMemberSummary(
                member_id=member.member_id, label=member.label, artifact_path=member.artifact_path,
                artifact_id=artifact.artifact_id if artifact else None,
                artifact_fingerprint=artifact.artifact_fingerprint if artifact else None,
                project_id=artifact.project_id if artifact else None,
                project_title=artifact.project_title if artifact else None,
                revision_id=artifact.revision_id if artifact else None,
                revision_version=artifact.revision_version if artifact else None,
                paradigm=artifact.paradigm.value if artifact else None,
                backend_name=artifact.backend_name if artifact else None,
                experiment_id=None, experiment_fingerprint=None, result_file=None,
                status="failed", total_runs=member.total_executions, successful_runs=0,
                failed_runs=member.total_executions, metrics=(), error_type=type(error).__name__,
                error_message=str(error)[:2000] or type(error).__name__,
            ))
            warnings.append(f"{member.member_id} failed: {type(error).__name__}: {str(error)[:500]}")

    status_values = [item.status for item in summaries]
    if all(value == "completed" for value in status_values):
        suite_status = "completed"
    elif any(value in {"completed", "partial"} for value in status_values):
        suite_status = "partial"
    else:
        suite_status = "failed"

    ranking: list[ComparisonEntry] = []
    if plan.comparison is not None:
        comparison = plan.comparison
        expected_by_member = {item.member_id: item.runs for item in plan.members}
        eligible = []
        for summary in summaries:
            if summary.status != "completed":
                continue
            for metric in summary.metrics:
                if metric.metric_name != comparison.metric_name or metric.unit != comparison.unit:
                    continue
                if metric.value_type != "numeric" or metric.mean is None or metric.population_stddev is None:
                    continue
                if metric.sample_size != expected_by_member[summary.member_id]:
                    continue
                eligible.append((summary, metric))
        eligible.sort(
            key=lambda pair: pair[1].mean,
            reverse=(comparison.direction == "maximize"),
        )
        if len(eligible) < 2:
            warnings.append(
                f"Comparison '{comparison.metric_name}' produced fewer than two complete numeric groups "
                f"with exact unit {comparison.unit!r}; no ranking was produced"
            )
        else:
            ranking = [ComparisonEntry(
                rank=index, member_id=summary.member_id, member_label=summary.label,
                parameter_set=metric.parameter_set, metric_name=metric.metric_name,
                unit=metric.unit, mean=metric.mean, population_stddev=metric.population_stddev,
                sample_size=metric.sample_size,
            ) for index, (summary, metric) in enumerate(eligible, start=1)]
            warnings.append(
                "Cross-model comparison assumes the plan author's semantic_definition is equivalent "
                "across all compared members/configurations; matching metric names and units alone do not prove equivalence."
            )
    elif not ranking:
        warnings.append("No cross-member ranking requested; metrics are reported separately by model and parameter set.")

    pending = ExperimentSuiteReport(
        schema_version=1, suite_id=suite_id, created_at=_now(), suite_name=plan.suite_name,
        plan=plan, status=suite_status, members=tuple(summaries), ranking=tuple(ranking),
        warnings=tuple(warnings), report_fingerprint="pending",
    )
    from dataclasses import replace
    return replace(pending, report_fingerprint=fingerprint_report(pending))


def execute_suite_file(
    plan_path: str | Path,
    *,
    artifact_root: str | Path,
    output_dir: str | Path,
) -> ExperimentSuiteReport:
    from orchestration.serialization import load_plan
    return execute_suite(load_plan(plan_path), artifact_root=artifact_root, output_dir=output_dir)
