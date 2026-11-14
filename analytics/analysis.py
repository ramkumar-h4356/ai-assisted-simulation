"""M25 statistical interpretation over integrity-checked milestone reports."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from math import sqrt
from pathlib import Path
import uuid

from analytics.models import (
    AnalyticsPlan, AnalyticsReport, GroupStatistic, Insight, ObjectiveValue,
    PairwiseComparison, ParetoEntry,
)
from analytics.sources import load_source
from analytics.statistics import effect_magnitude, holm_adjust, welch_comparison


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pareto(groups: tuple[GroupStatistic, ...], plan: AnalyticsPlan, warnings: list[str]) -> tuple[ParetoEntry, ...]:
    objectives = tuple(item for item in plan.metrics if item.direction in {"minimize", "maximize"})
    if len(objectives) < 2:
        return ()
    by_group: dict[str, dict[str, GroupStatistic]] = defaultdict(dict)
    for group in groups:
        by_group[group.group_id][group.metric_name] = group
    entries: list[ParetoEntry] = []
    for group_id, values in sorted(by_group.items()):
        if any(item.metric_name not in values for item in objectives):
            continue
        entries.append(ParetoEntry(
            group_id=group_id,
            group_label=values[objectives[0].metric_name].group_label,
            objectives=tuple(ObjectiveValue(
                metric_name=item.metric_name, unit=item.unit, direction=item.direction,
                value=values[item.metric_name].mean,
            ) for item in objectives),
            pareto_optimal=True,
            dominated_by=(),
        ))
    if len(entries) < 2:
        warnings.append("Pareto frontier was not produced: at least two complete groups with every declared objective are required.")
        return ()

    def dominates(left: ParetoEntry, right: ParetoEntry) -> bool:
        strictly_better = False
        for lvalue, rvalue in zip(left.objectives, right.objectives):
            if lvalue.direction == "minimize":
                if lvalue.value > rvalue.value:
                    return False
                strictly_better |= lvalue.value < rvalue.value
            else:
                if lvalue.value < rvalue.value:
                    return False
                strictly_better |= lvalue.value > rvalue.value
        return strictly_better

    output: list[ParetoEntry] = []
    for candidate in entries:
        dominators = tuple(other.group_id for other in entries if other.group_id != candidate.group_id and dominates(other, candidate))
        output.append(ParetoEntry(
            group_id=candidate.group_id, group_label=candidate.group_label,
            objectives=candidate.objectives, pareto_optimal=not dominators,
            dominated_by=dominators,
        ))
    return tuple(output)


def _findings(groups: tuple[GroupStatistic, ...], comparisons: tuple[PairwiseComparison, ...], pareto: tuple[ParetoEntry, ...], plan: AnalyticsPlan) -> tuple[Insight, ...]:
    findings: list[Insight] = []
    for group in groups:
        if group.sample_size < plan.minimum_sample_size:
            findings.append(Insight(
                code="low_sample_size", severity="warning", metric_name=group.metric_name,
                group_ids=(group.group_id,),
                message=f"{group.group_label} has {group.sample_size} observations for {group.metric_name}; the plan's preferred minimum is {plan.minimum_sample_size}.",
            ))
        if group.unobserved_runs:
            findings.append(Insight(
                code="incomplete_observations", severity="warning", metric_name=group.metric_name,
                group_ids=(group.group_id,),
                message=f"{group.group_label} has {group.unobserved_runs} unobserved run(s) out of {group.total_runs}; missing metrics and failed runs are not assumed to be the same cause.",
            ))
        if group.coefficient_of_variation is not None and group.coefficient_of_variation >= 1.0:
            findings.append(Insight(
                code="high_relative_variability", severity="caution", metric_name=group.metric_name,
                group_ids=(group.group_id,),
                message=f"{group.group_label} has a sample coefficient of variation of {group.coefficient_of_variation:.3g}; the sample standard deviation is at least as large as the absolute mean.",
            ))
    for definition in plan.metrics:
        selected = [item for item in groups if item.metric_name == definition.metric_name]
        if definition.direction in {"minimize", "maximize"} and selected:
            selected.sort(key=lambda item: item.mean, reverse=(definition.direction == "maximize"))
            best = selected[0]
            findings.append(Insight(
                code="best_observed_mean", severity="info", metric_name=definition.metric_name,
                group_ids=(best.group_id,),
                message=f"{best.group_label} has the best observed mean for {definition.metric_name} under the declared {definition.direction} direction; this is descriptive and not a guarantee of future performance.",
            ))
    for comparison in comparisons:
        if comparison.significant:
            findings.append(Insight(
                code="adjusted_significant_difference", severity="info", metric_name=comparison.metric_name,
                group_ids=(comparison.group_a, comparison.group_b),
                message=f"The estimated mean difference (group B minus group A) is {comparison.mean_difference_b_minus_a:.6g}; Holm-adjusted p={comparison.holm_adjusted_p_value:.4g} at alpha={plan.alpha:g}. The test assumes independent observations and approximate normality.",
            ))
        else:
            findings.append(Insight(
                code="difference_not_detected", severity="caution", metric_name=comparison.metric_name,
                group_ids=(comparison.group_a, comparison.group_b),
                message=f"The comparison did not meet the adjusted significance threshold (Holm-adjusted p={comparison.holm_adjusted_p_value:.4g}); this is not evidence that the groups are equivalent.",
            ))
    for item in pareto:
        if item.pareto_optimal:
            findings.append(Insight(
                code="pareto_optimal", severity="info", metric_name=None,
                group_ids=(item.group_id,),
                message=f"{item.group_label} is non-dominated across the declared objectives in its source group set.",
            ))
    return tuple(findings)


def analyze_reports(plan: AnalyticsPlan, *, source_root: str | Path) -> AnalyticsReport:
    """Read, verify and analyze M10/M11/M23/M24 reports without rerunning models."""
    if not isinstance(plan, AnalyticsPlan):
        raise TypeError("plan must be an AnalyticsPlan")
    source_evidence = []
    groups: list[GroupStatistic] = []
    warnings: list[str] = [
        "M25 reads aggregate statistics from prior reports; raw observations are not reconstructed.",
        "Welch tests assume independent observations and approximately normal sampling distributions; those assumptions cannot be verified from aggregate summaries alone.",
        "Semantic definitions and metric comparability are user assertions. Matching metric names and units do not prove that different models measured the same construct.",
        "Statistical differences between simulated groups are not causal estimates and do not establish real-world validity or theory truth.",
    ]
    seen_fingerprints: set[str] = set()
    for source in plan.sources:
        evidence, extracted, source_warnings = load_source(source, plan.metrics, plan.confidence_level, source_root)
        if evidence.report_fingerprint in seen_fingerprints:
            raise ValueError(f"source {source.source_id} duplicates a report already included; duplicate evidence is not analyzed twice")
        seen_fingerprints.add(evidence.report_fingerprint)
        source_evidence.append(evidence)
        groups.extend(extracted)
        warnings.extend(source_warnings)
        if not extracted:
            warnings.append(f"{source.source_id}: no numeric groups matched the metrics declared in the plan.")
    if not groups:
        raise ValueError("no numeric metric groups were found; check report types, metric names and exact units")
    if len(groups) > 1000:
        raise ValueError("M25 report exceeds the supported limit of 1000 metric groups")
    for metric in plan.metrics:
        if not any(item.metric_name == metric.metric_name for item in groups):
            warnings.append(f"No source produced numeric observations for declared metric {metric.metric_name!r} with unit {metric.unit!r}.")

    comparisons: list[PairwiseComparison] = []
    pairwise_by_metric: dict[str, list[tuple[tuple, dict[str, float]]]] = defaultdict(list)
    pair_count = 0
    for metric in plan.metrics:
        metric_groups = sorted((item for item in groups if item.metric_name == metric.metric_name), key=lambda item: item.group_id)
        pairs = list(combinations(metric_groups, 2))
        if pair_count + len(pairs) > plan.max_pairwise_comparisons:
            allowed = max(0, plan.max_pairwise_comparisons - pair_count)
            warnings.append(f"Pairwise comparison budget reached; only the first {allowed} candidate pair(s) for {metric.metric_name} were considered.")
            pairs = pairs[:allowed]
        pair_count += len(pairs)
        for left, right in pairs:
            if left.randomization_key is not None and left.randomization_key == right.randomization_key:
                warnings.append(f"Skipped {left.group_id} versus {right.group_id}: both groups share randomization key {left.randomization_key!r}; paired/common-random-number structure cannot be reconstructed from aggregate summaries.")
                continue
            if left.source_id != right.source_id and set(left.experiment_ids).intersection(right.experiment_ids):
                warnings.append(f"Skipped {left.group_id} versus {right.group_id}: reports share one or more M9 experiment IDs, so independent-group testing would double-count evidence.")
                continue
            if left.sample_stddev is None or right.sample_stddev is None:
                warnings.append(f"Skipped {left.group_id} versus {right.group_id}: each group needs at least two observations for Welch testing.")
                continue
            result = welch_comparison(
                left.mean, left.sample_stddev, left.sample_size,
                right.mean, right.sample_stddev, right.sample_size,
                plan.confidence_level,
            )
            if result is None:
                warnings.append(f"Skipped {left.group_id} versus {right.group_id}: pooled comparison uncertainty is zero or not estimable from the supplied summaries.")
                continue
            pairwise_by_metric[metric.metric_name].append(((left, right), result))

    for metric_name, values in pairwise_by_metric.items():
        adjusted = holm_adjust([item[1]["p_value"] for item in values])
        for index, ((left, right), result) in enumerate(values):
            adjusted_p = adjusted[index]
            hedges_g = result["hedges_g"]
            comparisons.append(PairwiseComparison(
                metric_name=metric_name, group_a=left.group_id, group_b=right.group_id,
                mean_difference_b_minus_a=result["mean_difference"], welch_t=result["welch_t"],
                degrees_freedom=result["degrees_freedom"], p_value=result["p_value"],
                holm_adjusted_p_value=adjusted_p,
                confidence_lower=result["confidence_lower"], confidence_upper=result["confidence_upper"],
                hedges_g=hedges_g, effect_magnitude=effect_magnitude(hedges_g),
                significant=adjusted_p < plan.alpha,
            ))
    comparisons.sort(key=lambda item: (item.metric_name, item.holm_adjusted_p_value, item.group_a, item.group_b))
    if not comparisons:
        warnings.append("No pairwise comparisons were estimable; groups may be single-observation, constant, overlapping or insufficiently populated.")

    groups_tuple = tuple(sorted(groups, key=lambda item: (item.metric_name, item.source_id, item.group_id)))
    pareto = _pareto(groups_tuple, plan, warnings)
    findings = _findings(groups_tuple, tuple(comparisons), pareto, plan)
    if any(item.report_type == "m11" for item in source_evidence):
        warnings.append("M11 uncertainty samples can combine input-distribution variation and stochastic simulation variation; M25 does not separate those components.")
    if any(item.report_type == "m24" for item in source_evidence):
        warnings.append("M24 groups may originate from different simulation paradigms; cross-paradigm interpretation depends on the plan's explicit semantic definitions.")
    from analytics.serialization import fingerprint_report
    from dataclasses import replace
    pending = AnalyticsReport(
        schema_version=1, analysis_id="m25-" + uuid.uuid4().hex, created_at=_now(),
        plan=plan, sources=tuple(source_evidence), groups=groups_tuple,
        comparisons=tuple(comparisons), pareto_frontier=pareto,
        insights=findings, warnings=tuple(dict.fromkeys(warnings)), report_fingerprint="pending",
    )
    return replace(pending, report_fingerprint=fingerprint_report(pending))


__all__ = ["analyze_reports"]
