"""Load and adapt integrity-verified M10, M11, M23 and M24 reports."""

from __future__ import annotations

from pathlib import Path

from analytics.models import AnalyticsPlan, GroupStatistic, MetricDefinition, SourceEvidence
from experimentation.serialization import load_report as load_m10
from uncertainty.serialization import load_report as load_m11
from optimization.serialization import load_report as load_m23
from orchestration.serialization import load_report as load_m24
from analytics.statistics import mean_confidence_interval


def _resolve(root: Path, relative: str) -> Path:
    root = root.expanduser().resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"analytics source path escapes source root: {relative}") from error
    if not candidate.is_file():
        raise FileNotFoundError(f"analytics source does not exist or is not a file: {relative}")
    return candidate


def _group(
    *, source_id: str, report_type: str, group_key: str, group_label: str,
    artifact_id: str, project_id: str, revision_id: str, paradigm: str,
    experiment_ids: tuple[str, ...], metric: MetricDefinition,
    sample_size: int, mean: float, population_stddev: float,
    total_runs: int, confidence_level: float, randomization_key: str | None = None,
) -> GroupStatistic:
    if sample_size < 1:
        raise ValueError("source metric sample_size must be positive")
    if population_stddev < 0:
        raise ValueError("source metric population standard deviation cannot be negative")
    sample_stddev = population_stddev * ((sample_size / (sample_size - 1)) ** 0.5) if sample_size > 1 else None
    standard_error = sample_stddev / (sample_size ** 0.5) if sample_stddev is not None else None
    interval = mean_confidence_interval(mean, sample_stddev, sample_size, confidence_level)
    unobserved = max(0, total_runs - sample_size)
    cv = sample_stddev / abs(mean) if sample_stddev is not None and mean != 0 else None
    return GroupStatistic(
        group_id=group_key, source_id=source_id, group_label=group_label,
        report_type=report_type, artifact_id=artifact_id, project_id=project_id,
        revision_id=revision_id, paradigm=paradigm, experiment_ids=experiment_ids,
        metric_name=metric.metric_name, unit=metric.unit,
        semantic_definition=metric.semantic_definition, direction=metric.direction,
        sample_size=sample_size, mean=float(mean), population_stddev=float(population_stddev),
        sample_stddev=sample_stddev, standard_error=standard_error,
        confidence_lower=interval[0] if interval else None,
        confidence_upper=interval[1] if interval else None,
        total_runs=max(total_runs, sample_size), observed_runs=sample_size,
        unobserved_runs=unobserved, unobserved_fraction=(unobserved / max(total_runs, sample_size)),
        coefficient_of_variation=cv,
        status="sufficient" if sample_size >= 2 else "low_sample",
        randomization_key=randomization_key,
    )


def load_source(plan_source, metrics: tuple[MetricDefinition, ...], confidence_level: float, source_root: str | Path):
    path = _resolve(Path(source_root), plan_source.path)
    report_loaders = {"m10": load_m10, "m11": load_m11, "m23": load_m23, "m24": load_m24}
    report = report_loaders[plan_source.report_type](path)
    groups: list[GroupStatistic] = []
    warnings: list[str] = []
    source_metrics = {item.metric_name: item for item in metrics}

    if plan_source.report_type == "m10":
        meta = (report.analysis_id, report.report_fingerprint, report.artifact_id, report.artifact_fingerprint, report.project_id, report.revision_id, report.paradigm)
        experiment_ids = tuple(report.input_experiment_ids)
        for variant in report.variants:
            for value in variant.metrics:
                definition = source_metrics.get(value.metric_name)
                if definition is None:
                    continue
                if value.value_type != "numeric" or value.unit != definition.unit:
                    warnings.append(f"{plan_source.source_id}/{variant.parameter_set}/{value.metric_name}: skipped because metric is non-numeric or its unit differs from the declared definition")
                    continue
                groups.append(_group(
                    source_id=plan_source.source_id, report_type="m10",
                    group_key=f"{plan_source.source_id}/{variant.parameter_set}", group_label=variant.parameter_set,
                    artifact_id=report.artifact_id, project_id=report.project_id, revision_id=report.revision_id,
                    paradigm=report.paradigm, experiment_ids=experiment_ids, metric=definition,
                    sample_size=value.sample_size, mean=value.mean, population_stddev=value.population_stddev,
                    total_runs=variant.total_runs, confidence_level=confidence_level,
                ))
        evidence = SourceEvidence(
            plan_source.source_id, "m10", plan_source.path, report.analysis_id, report.report_fingerprint,
            (report.artifact_id,), (report.artifact_fingerprint,), (report.project_id,), (report.revision_id,), (report.paradigm,),
        )

    elif plan_source.report_type == "m11":
        for value in report.metric_distributions:
            definition = source_metrics.get(value.metric_name)
            if definition is None:
                continue
            if value.unit != definition.unit:
                warnings.append(f"{plan_source.source_id}/{value.metric_name}: skipped because its unit differs from the declared definition")
                continue
            groups.append(_group(
                source_id=plan_source.source_id, report_type="m11", group_key=f"{plan_source.source_id}/uncertainty",
                group_label="uncertainty sample", artifact_id=report.artifact_id, project_id=report.project_id,
                revision_id=report.revision_id, paradigm=report.paradigm, experiment_ids=(report.experiment_id,),
                metric=definition, sample_size=value.sample_size, mean=value.mean,
                population_stddev=value.population_stddev, total_runs=report.sample_count,
                confidence_level=confidence_level, randomization_key=f"m11-input-seed:{report.sampling_seed}",
            ))
        evidence = SourceEvidence(
            plan_source.source_id, "m11", plan_source.path, report.report_id, report.report_fingerprint,
            (report.artifact_id,), (report.artifact_fingerprint,), (report.project_id,), (report.revision_id,), (report.paradigm,),
        )

    elif plan_source.report_type == "m23":
        definition = source_metrics.get(report.plan.objective.metric_name)
        if definition is not None and definition.unit is not None:
            warnings.append(f"{plan_source.source_id}/{definition.metric_name}: M23 does not store objective units; declare unit=null or use a source with an explicit unit.")
            definition = None
        if definition is not None and definition.direction not in {"observe", report.plan.objective.direction}:
            warnings.append(f"{plan_source.source_id}/{definition.metric_name}: the M25 direction conflicts with the M23 optimization objective; source omitted for this metric.")
            definition = None
        if definition is not None:
            for candidate in report.candidates:
                if candidate.objective_mean is None or candidate.objective_population_stddev is None or candidate.objective_sample_size < 1:
                    warnings.append(f"{plan_source.source_id}/{candidate.parameter_set}: skipped because the objective has no usable numeric observations")
                    continue
                groups.append(_group(
                    source_id=plan_source.source_id, report_type="m23", group_key=f"{plan_source.source_id}/{candidate.parameter_set}",
                    group_label=candidate.parameter_set, artifact_id=report.artifact_id, project_id=report.project_id,
                    revision_id=report.revision_id, paradigm=report.paradigm, experiment_ids=(report.experiment_id,),
                    metric=definition, sample_size=candidate.objective_sample_size, mean=candidate.objective_mean,
                    population_stddev=candidate.objective_population_stddev, total_runs=candidate.total_runs,
                    confidence_level=confidence_level,
                ))
        evidence = SourceEvidence(
            plan_source.source_id, "m23", plan_source.path, report.optimization_id, report.report_fingerprint,
            (report.artifact_id,), (report.artifact_fingerprint,), (report.project_id,), (report.revision_id,), (report.paradigm,),
        )

    else:  # M24
        plan_members = {item.member_id: item for item in report.plan.members}
        artifact_ids: list[str] = []
        artifact_fingerprints: list[str] = []
        project_ids: list[str] = []
        revision_ids: list[str] = []
        paradigms: list[str] = []
        for member in report.members:
            if member.artifact_id and member.artifact_id not in artifact_ids:
                artifact_ids.append(member.artifact_id)
            if member.artifact_fingerprint and member.artifact_fingerprint not in artifact_fingerprints:
                artifact_fingerprints.append(member.artifact_fingerprint)
            if member.project_id and member.project_id not in project_ids:
                project_ids.append(member.project_id)
            if member.revision_id and member.revision_id not in revision_ids:
                revision_ids.append(member.revision_id)
            if member.paradigm and member.paradigm not in paradigms:
                paradigms.append(member.paradigm)
            requested_runs = plan_members[member.member_id].runs
            for value in member.metrics:
                definition = source_metrics.get(value.metric_name)
                if definition is None:
                    continue
                if value.value_type != "numeric" or value.unit != definition.unit:
                    warnings.append(f"{plan_source.source_id}/{member.member_id}/{value.metric_name}: skipped because metric is non-numeric or its unit differs from the declared definition")
                    continue
                groups.append(_group(
                    source_id=plan_source.source_id, report_type="m24",
                    group_key=f"{plan_source.source_id}/{member.member_id}/{value.parameter_set}",
                    group_label=f"{member.label} / {value.parameter_set}",
                    artifact_id=member.artifact_id or f"unavailable:{member.member_id}",
                    project_id=member.project_id or "unavailable", revision_id=member.revision_id or "unavailable",
                    paradigm=member.paradigm or "unavailable", experiment_ids=(member.experiment_id,) if member.experiment_id else (),
                    metric=definition, sample_size=value.sample_size, mean=value.mean,
                    population_stddev=value.population_stddev, total_runs=requested_runs,
                    confidence_level=confidence_level,
                    randomization_key=(f"m24-abm-base-seed:{plan_members[member.member_id].base_seed}"
                                       if member.paradigm == "agent_based" and plan_members[member.member_id].base_seed is not None else None),
                ))
        evidence = SourceEvidence(
            plan_source.source_id, "m24", plan_source.path, report.suite_id, report.report_fingerprint,
            tuple(artifact_ids), tuple(artifact_fingerprints), tuple(project_ids), tuple(revision_ids), tuple(paradigms),
        )

    return evidence, tuple(groups), tuple(warnings)


__all__ = ["load_source"]
