"""M23 bounded objective-driven search using verified M9 execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import statistics
import uuid

from compilation import CompilationArtifact, verify_artifact
from execution import ExperimentConfig, ExperimentResult, execute_artifact
from execution.models import RunStatus
from execution.serialization import fingerprint_result
from experimentation.analysis import _metrics_for_run
from optimization.models import (
    CandidateSummary, ConstraintEvaluation, MetricConstraint,
    OptimizationPlan, OptimizationReport,
)
from optimization.search import generate_candidates
from optimization.serialization import fingerprint_report


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _numeric_metric_means(runs, metric_name: str) -> list[float]:
    values: list[float] = []
    for run in runs:
        if run.status is not RunStatus.COMPLETED:
            continue
        matches = [item for item in _metrics_for_run(run) if item.name == metric_name]
        if len(matches) > 1:
            raise ValueError(f"Run {run.run_index} contains duplicate metric {metric_name!r}")
        if matches:
            value = matches[0].value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Optimization metric {metric_name!r} must be numeric")
            values.append(float(value))
    return values


def _evaluate_constraint(constraint: MetricConstraint, mean: float | None) -> ConstraintEvaluation:
    if mean is None:
        satisfied = False
    elif constraint.operator == "<=":
        satisfied = mean <= constraint.threshold
    elif constraint.operator == ">=":
        satisfied = mean >= constraint.threshold
    else:
        assert constraint.upper_threshold is not None
        satisfied = constraint.threshold <= mean <= constraint.upper_threshold
    return ConstraintEvaluation(
        metric_name=constraint.metric_name,
        operator=constraint.operator,
        threshold=float(constraint.threshold),
        upper_threshold=(float(constraint.upper_threshold) if constraint.upper_threshold is not None else None),
        measured_mean=mean,
        satisfied=satisfied,
    )


def optimize_parameters(
    artifact: CompilationArtifact,
    plan: OptimizationPlan,
    *,
    execution_base_seed: int | None = None,
) -> tuple[ExperimentResult, OptimizationReport]:
    """Run a bounded random search and rank feasible candidates by one metric.

    Every candidate is executed by M9 against the same verified M8 artifact.
    The optimizer only varies explicit numeric ``user_parameter`` bindings.
    It does not infer parameter meanings, modify conceptual bindings, or make
    causal claims. A candidate is eligible only if all requested replications
    complete and every objective/constraint metric is available in each run.
    """
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed; optimization blocked")
    if not isinstance(plan, OptimizationPlan):
        raise TypeError("plan must be an OptimizationPlan")

    parameter_sets = generate_candidates(artifact, plan)
    config = ExperimentConfig(
        runs=plan.replications,
        base_seed=execution_base_seed,
        continue_on_error=True,
        parameter_sets=parameter_sets,
    )
    result = execute_artifact(artifact, config)
    if fingerprint_result(result) != result.result_fingerprint:
        raise ValueError("M9 optimization execution result failed integrity verification")

    grouped = {item.name: [] for item in parameter_sets}
    for run in result.runs:
        if run.parameter_set not in grouped:
            raise ValueError(f"M9 returned an unexpected parameter set {run.parameter_set!r}")
        grouped[run.parameter_set].append(run)

    summaries: list[CandidateSummary] = []
    warnings: list[str] = []
    for parameter_set in parameter_sets:
        runs = grouped[parameter_set.name]
        successful = sum(run.status is RunStatus.COMPLETED for run in runs)
        failed = len(runs) - successful
        objective_values = _numeric_metric_means(runs, plan.objective.metric_name)
        objective_mean = statistics.fmean(objective_values) if objective_values else None
        objective_stddev = statistics.pstdev(objective_values) if objective_values else None
        constraint_results: list[ConstraintEvaluation] = []
        constraints_available = True
        for constraint in plan.constraints:
            values = _numeric_metric_means(runs, constraint.metric_name)
            mean = statistics.fmean(values) if len(values) == plan.replications else None
            evaluation = _evaluate_constraint(constraint, mean)
            constraint_results.append(evaluation)
            if mean is None:
                constraints_available = False

        complete = (
            len(runs) == plan.replications
            and successful == plan.replications
            and len(objective_values) == plan.replications
            and constraints_available
        )
        constraints_pass = all(item.satisfied for item in constraint_results)
        feasible = complete and constraints_pass
        if not complete:
            status = "incomplete"
        elif not constraints_pass:
            status = "constraint_failed"
        else:
            status = "complete"
        parameters = {item.target_path: item.value for item in parameter_set.overrides}
        summaries.append(CandidateSummary(
            parameter_set=parameter_set.name,
            parameters=parameters,
            total_runs=len(runs),
            successful_runs=successful,
            failed_runs=failed,
            objective_mean=objective_mean,
            objective_population_stddev=objective_stddev,
            objective_sample_size=len(objective_values),
            feasible=feasible,
            status=status,
            constraints=tuple(constraint_results),
        ))
        if failed:
            warnings.append(f"Candidate {parameter_set.name!r} had {failed} failed M9 run(s); it was not eligible for selection.")
        if len(objective_values) != successful:
            warnings.append(f"Candidate {parameter_set.name!r} did not produce objective metric {plan.objective.metric_name!r} in every successful run.")
        for evaluation in constraint_results:
            if evaluation.measured_mean is None:
                warnings.append(f"Candidate {parameter_set.name!r} could not evaluate constraint metric {evaluation.metric_name!r}.")

    feasible_candidates = [item for item in summaries if item.feasible]
    if plan.objective.direction == "minimize":
        best = min(feasible_candidates, key=lambda item: item.objective_mean) if feasible_candidates else None
    else:
        best = max(feasible_candidates, key=lambda item: item.objective_mean) if feasible_candidates else None

    baseline = next((item for item in summaries if item.parameter_set == "baseline"), None)
    improvement = None
    if best is not None and baseline is not None and baseline.feasible:
        if plan.objective.direction == "minimize":
            improvement = baseline.objective_mean - best.objective_mean
        else:
            improvement = best.objective_mean - baseline.objective_mean

    if not feasible_candidates:
        warnings.append("No candidate satisfied all execution-completeness and output-constraint requirements.")
    if artifact.paradigm.value == "agent_based":
        warnings.append(
            "ABM replications use M9's sequential seeds across candidates; comparisons are not paired common-random-number experiments."
        )
    elif plan.replications > 1:
        warnings.append(
            f"The {artifact.paradigm.value} backend is deterministic in its current version; repeated replications do not represent independent stochastic samples."
        )
    warnings.append(
        "Optimization ranks outcomes conditional on this M8 model, search bounds, objective, constraints and execution settings; it does not establish real-world validity or causation."
    )

    provisional = OptimizationReport(
        schema_version=1,
        optimization_id=f"optimization-{uuid.uuid4().hex}",
        created_at=_now(),
        artifact_id=artifact.artifact_id,
        artifact_fingerprint=artifact.artifact_fingerprint,
        project_id=artifact.project_id,
        project_title=artifact.project_title,
        revision_id=artifact.revision_id,
        revision_version=artifact.revision_version,
        paradigm=artifact.paradigm.value,
        backend_name=artifact.backend_name,
        algorithm="uniform_random_search_v1",
        plan=plan,
        experiment_id=result.experiment_id,
        experiment_fingerprint=result.result_fingerprint,
        candidates=tuple(summaries),
        baseline_parameter_set=(baseline.parameter_set if baseline is not None else None),
        best_parameter_set=(best.parameter_set if best is not None else None),
        objective_improvement=improvement,
        warnings=tuple(dict.fromkeys(warnings)),
        report_fingerprint="pending",
    )
    report = replace(provisional, report_fingerprint=fingerprint_report(provisional))
    return result, report


__all__ = ["optimize_parameters"]
