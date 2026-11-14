"""M26 structural, behavioral and reproducibility checks for M8/M9 models."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
from typing import Any

from compilation import CompilationParadigm, load_artifact, verify_artifact
from execution import ExperimentConfig, ExperimentResult, execute_artifact, load_result
from execution.models import ExperimentStatus, RunStatus
from execution.runner import _parse_model
from validation.models import InvariantSpec, ValidationCheck, ValidationPlan, ValidationReport


class ValidationError(ValueError):
    """Raised when an M26 plan cannot be safely evaluated."""


_LIMITS = (
    "Verification checks internal consistency, schema validity, execution trace integrity and declared invariants; it does not prove that a model represents reality.",
    "Behavioral validation is conditional on the compiled model, selected parameters, initial conditions, solver, time step and evidence supplied by the user.",
    "Repeatability demonstrates reproducibility under identical recorded settings; it does not establish empirical validity or causality.",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _resolve_relative(root: str | Path, relative: str) -> Path:
    base = Path(root).expanduser().resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as error:
        raise ValidationError(f"Path escapes its selected root: {relative!r}") from error
    return candidate


def _check(check_id: str, category: str, status: str, message: str, **details) -> ValidationCheck:
    return ValidationCheck(check_id, category, status, message, details)


def _finite_tree(value: Any, path: str = "trace") -> list[str]:
    errors: list[str] = []
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return errors
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(path)
        return errors
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_finite_tree(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_finite_tree(item, f"{path}[{index}]"))
    else:
        errors.append(path)
    return errors


def _path_tokens(path: str) -> list[tuple[str, bool]]:
    if not isinstance(path, str) or not path:
        raise ValueError("trace_path must be a non-empty string")
    tokens: list[tuple[str, bool]] = []
    cursor = 0
    pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)(\[\])?")
    for match in pattern.finditer(path):
        if match.start() != cursor:
            raise ValueError(f"Invalid trace path syntax: {path!r}")
        tokens.append((match.group(1), bool(match.group(2))))
        cursor = match.end()
        if cursor < len(path) and path[cursor] == ".":
            cursor += 1
    if cursor != len(path) or not tokens:
        raise ValueError(f"Invalid trace path syntax: {path!r}")
    return tokens


def _extract_path(root: Any, path: str) -> list[Any]:
    tokens = _path_tokens(path)
    current = [root]
    for key, expand in tokens:
        next_values: list[Any] = []
        for item in current:
            if not isinstance(item, dict) or key not in item:
                raise ValueError(f"Trace path {path!r} is missing key {key!r}")
            value = item[key]
            if expand:
                if not isinstance(value, list):
                    raise ValueError(f"Trace path {path!r} expected a list at {key!r}")
                next_values.extend(value)
            else:
                next_values.append(value)
        current = next_values
    if not current:
        raise ValueError(f"Trace path {path!r} resolved to no values")
    # A path that resolves directly to a list is treated as a numeric series.
    flattened: list[Any] = []
    for item in current:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)
    return flattened


def _numeric_values(values: list[Any], path: str) -> list[float]:
    result: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Trace path {path!r} contains a non-finite/non-numeric value at item {index}")
        result.append(float(value))
    return result


def _evaluate_invariant(spec: InvariantSpec, trace: dict[str, Any], run_index: int) -> ValidationCheck:
    check_id = f"invariant:{spec.check_id}:run-{run_index}"
    try:
        values = _extract_path(trace, spec.trace_path)
        if spec.check_type == "conserved_sum":
            if any(not isinstance(item, dict) for item in values):
                raise ValueError("conserved_sum path must resolve to objects")
            sums = []
            for index, item in enumerate(values):
                missing = [field for field in spec.fields if field not in item]
                if missing:
                    raise ValueError(f"conserved_sum item {index} is missing fields: {', '.join(missing)}")
                nums = _numeric_values([item[field] for field in spec.fields], spec.trace_path)
                sums.append(sum(nums))
            deviations = [abs(value - float(spec.expected_value)) for value in sums]
            worst = max(deviations, default=0.0)
            passed = all(value <= spec.tolerance for value in deviations)
            return _check(check_id, "behavioral_invariant", "passed" if passed else "failed",
                          "Declared conserved-sum invariant holds." if passed else "Declared conserved-sum invariant was violated.",
                          sample_count=len(sums), expected=spec.expected_value, maximum_absolute_deviation=worst,
                          tolerance=spec.tolerance, fields=list(spec.fields))

        numeric = _numeric_values(values, spec.trace_path)
        if spec.check_type == "non_negative":
            minimum = min(numeric)
            passed = minimum >= -spec.tolerance
            return _check(check_id, "behavioral_invariant", "passed" if passed else "failed",
                          "All values are non-negative within tolerance." if passed else "A negative value violates the declared invariant.",
                          sample_count=len(numeric), minimum_observed=minimum, tolerance=spec.tolerance)
        if spec.check_type == "bounds":
            observed_min, observed_max = min(numeric), max(numeric)
            passed = (spec.minimum is None or observed_min >= spec.minimum - spec.tolerance) and (spec.maximum is None or observed_max <= spec.maximum + spec.tolerance)
            return _check(check_id, "behavioral_invariant", "passed" if passed else "failed",
                          "All values satisfy declared bounds." if passed else "One or more values fall outside the declared bounds.",
                          sample_count=len(numeric), minimum_observed=observed_min, maximum_observed=observed_max,
                          minimum_expected=spec.minimum, maximum_expected=spec.maximum, tolerance=spec.tolerance)
        if spec.check_type == "monotonic":
            if len(numeric) < 2:
                raise ValueError("monotonic check requires at least two numeric observations")
            pairs = list(zip(numeric, numeric[1:]))
            if spec.direction == "increasing":
                passed = all(right > left + spec.tolerance for left, right in pairs)
            elif spec.direction == "decreasing":
                passed = all(right < left - spec.tolerance for left, right in pairs)
            elif spec.direction == "nondecreasing":
                passed = all(right >= left - spec.tolerance for left, right in pairs)
            else:
                passed = all(right <= left + spec.tolerance for left, right in pairs)
            return _check(check_id, "behavioral_invariant", "passed" if passed else "failed",
                          f"Series satisfies {spec.direction} ordering." if passed else f"Series violates {spec.direction} ordering.",
                          sample_count=len(numeric), direction=spec.direction, tolerance=spec.tolerance)
    except (TypeError, ValueError) as error:
        return _check(check_id, "behavioral_invariant", "failed", str(error), trace_path=spec.trace_path)
    return _check(check_id, "behavioral_invariant", "failed", "Unsupported invariant type.")


def _stable_run_projection(result: ExperimentResult) -> dict[str, Any]:
    """Exclude clocks and wall-time while retaining all modeled results."""
    return {
        "artifact_id": result.artifact_id,
        "artifact_fingerprint": result.artifact_fingerprint,
        "paradigm": result.paradigm,
        "status": result.status.value,
        "runs": [
            {
                "status": run.status.value,
                "seed": run.seed,
                "parameter_set": run.parameter_set,
                "parameters": run.parameters,
                "metrics": [{"name": item.name, "value": item.value, "unit": item.unit} for item in run.metrics],
                "trace": run.trace,
                "error_type": run.error_type,
                "error_message": run.error_message,
            }
            for run in result.runs
        ],
    }


def _baseline_trace_checks(artifact, result: ExperimentResult) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    if result.status is not ExperimentStatus.COMPLETED:
        checks.append(_check("execution_completed", "execution", "failed", f"M9 experiment status is {result.status.value}.", status=result.status.value))
    else:
        checks.append(_check("execution_completed", "execution", "passed", "All recorded M9 executions completed successfully.", runs=len(result.runs)))
    expected_shapes = {
        CompilationParadigm.DISCRETE_EVENT: "events",
        CompilationParadigm.AGENT_BASED: "history",
        CompilationParadigm.MATHEMATICAL: "time_series",
        CompilationParadigm.DATA_DRIVEN: "forecast",
        CompilationParadigm.SYSTEM_DYNAMICS: "time_series",
    }
    finite_issues: list[str] = []
    shape_issues: list[str] = []
    ordered_issues: list[str] = []
    for run in result.runs:
        if run.status is not RunStatus.COMPLETED:
            shape_issues.append(f"run {run.run_index} did not complete")
            continue
        finite_issues.extend(_finite_tree(run.trace, f"run[{run.run_index}].trace"))
        key = expected_shapes[artifact.paradigm]
        series = run.trace.get(key)
        if not isinstance(series, list) or not series:
            shape_issues.append(f"run {run.run_index} trace has no non-empty {key!r} list")
            continue
        if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT:
            times = [item.get("time") for item in series if isinstance(item, dict)]
        elif artifact.paradigm is CompilationParadigm.AGENT_BASED:
            times = [item.get("step") for item in series if isinstance(item, dict)]
        else:
            times = [item.get("time") for item in series if isinstance(item, dict)]
        try:
            times = _numeric_values(times, key)
            if any(right < left for left, right in zip(times, times[1:])):
                ordered_issues.append(f"run {run.run_index} {key} timestamps are not nondecreasing")
        except ValueError as error:
            ordered_issues.append(f"run {run.run_index}: {error}")

    checks.append(_check("trace_finite", "trace_integrity", "failed" if finite_issues else "passed",
                         "Trace contains only finite JSON values." if not finite_issues else "Trace contains invalid/non-finite values.",
                         issue_count=len(finite_issues), examples=finite_issues[:10]))
    checks.append(_check("trace_shape", "trace_integrity", "failed" if shape_issues else "passed",
                         "Trace contains the expected paradigm-specific structure." if not shape_issues else "Trace structure is incomplete.",
                         issue_count=len(shape_issues), examples=shape_issues[:10]))
    checks.append(_check("time_order", "behavioral_verification", "failed" if ordered_issues else "passed",
                         "Recorded simulation time/steps are nondecreasing." if not ordered_issues else "Recorded simulation time/steps are out of order.",
                         issue_count=len(ordered_issues), examples=ordered_issues[:10]))

    grid_issues: list[str] = []
    if artifact.paradigm in {CompilationParadigm.MATHEMATICAL, CompilationParadigm.SYSTEM_DYNAMICS}:
        time_data = artifact.model_data.get("time", {})
        start, end, step = float(time_data.get("start", 0.0)), float(time_data.get("end", 0.0)), float(time_data.get("step", 0.0))
        expected_steps = max(1, math.ceil((end - start) / step)) if step > 0 else 0
        for run in result.runs:
            if run.status is not RunStatus.COMPLETED:
                continue
            series_key = "time_series"
            observed = len(run.trace.get(series_key, []))
            recorded_steps = run.trace.get("steps")
            if observed != expected_steps + 1 or recorded_steps != expected_steps:
                grid_issues.append(
                    f"run {run.run_index}: expected {expected_steps} steps/{expected_steps + 1} snapshots, "
                    f"found {recorded_steps!r} steps/{observed} snapshots"
                )
        checks.append(_check("time_grid", "numerical_verification", "failed" if grid_issues else "passed",
                             "Recorded time grid matches the M8 start/end/step specification." if not grid_issues else "Recorded time grid does not match the M8 specification.",
                             expected_steps=expected_steps, issue_count=len(grid_issues), examples=grid_issues[:10]))
    else:
        checks.append(_check("time_grid", "numerical_verification", "skipped",
                             "A fixed-step numeric time grid is not defined for this execution paradigm."))

    # Validate initial conditions against the exact M8 specification where a
    # paradigm exposes a comparable initial snapshot.
    initial_issues: list[str] = []
    for run in result.runs:
        if run.status is not RunStatus.COMPLETED:
            continue
        try:
            if artifact.paradigm is CompilationParadigm.MATHEMATICAL:
                first = run.trace["time_series"][0]["values"]
                for variable in artifact.model_data.get("variables", []):
                    name = variable["name"]
                    if name not in first or not math.isclose(float(first[name]), float(variable["initial_value"]), rel_tol=1e-10, abs_tol=1e-10):
                        initial_issues.append(f"run {run.run_index}: initial value mismatch for {name}")
            elif artifact.paradigm is CompilationParadigm.SYSTEM_DYNAMICS:
                first = run.trace["time_series"][0]["stocks"]
                for stock in artifact.model_data.get("stocks", []):
                    name = stock["name"]
                    if name not in first or not math.isclose(float(first[name]), float(stock["initial_value"]), rel_tol=1e-10, abs_tol=1e-10):
                        initial_issues.append(f"run {run.run_index}: initial stock mismatch for {name}")
            elif artifact.paradigm is CompilationParadigm.DATA_DRIVEN:
                if run.trace.get("dataset_reference_id") != artifact.model_data.get("dataset_reference_id"):
                    initial_issues.append(f"run {run.run_index}: dataset reference does not match M8 model")
                if tuple(run.trace.get("variables", ())) != tuple(artifact.model_data.get("variables", ())):
                    initial_issues.append(f"run {run.run_index}: data-driven variable list does not match M8 model")
            elif artifact.paradigm is CompilationParadigm.AGENT_BASED:
                first_ids = {item.get("id") for item in run.trace["history"][0].get("agents", [])}
                expected_ids = {item.get("reference") for item in artifact.model_data.get("agents", [])}
                if first_ids != expected_ids:
                    initial_issues.append(f"run {run.run_index}: initial agent identities do not match M8 model")
        except (KeyError, TypeError, ValueError, IndexError) as error:
            initial_issues.append(f"run {run.run_index}: cannot verify initial conditions ({error})")
    if artifact.paradigm in {CompilationParadigm.MATHEMATICAL, CompilationParadigm.SYSTEM_DYNAMICS, CompilationParadigm.DATA_DRIVEN, CompilationParadigm.AGENT_BASED}:
        checks.append(_check("initial_conditions", "behavioral_verification", "failed" if initial_issues else "passed",
                             "Recorded initial state is consistent with the compiled M8 model." if not initial_issues else "Recorded initial state differs from the compiled M8 model.",
                             issue_count=len(initial_issues), examples=initial_issues[:10]))
    else:
        checks.append(_check("initial_conditions", "behavioral_verification", "skipped",
                             "Initial-condition comparison is not defined for this paradigm's current M9 trace contract."))
    return checks


def _assemble_report(plan: ValidationPlan, artifact, checks: list[ValidationCheck],
                     result: ExperimentResult | None = None,
                     repeat_result: ExperimentResult | None = None) -> ValidationReport:
    failed = sum(item.status == "failed" for item in checks)
    warnings = sum(item.status == "warning" for item in checks)
    overall = "failed" if failed else "passed_with_warnings" if warnings else "passed"
    pending = ValidationReport(
        schema_version=1, validation_id="m26-" + uuid.uuid4().hex, created_at=_now(),
        validation_name=plan.validation_name, overall_status=overall,
        artifact_id=artifact.artifact_id, artifact_fingerprint=artifact.artifact_fingerprint,
        model_fingerprint=artifact.model_fingerprint, project_id=artifact.project_id,
        revision_id=artifact.revision_id, paradigm=artifact.paradigm.value,
        backend_name=artifact.backend_name,
        experiment_id=result.experiment_id if result else None,
        result_fingerprint=result.result_fingerprint if result else None,
        repeatability_experiment_id=repeat_result.experiment_id if repeat_result else None,
        repeatability_result_fingerprint=repeat_result.result_fingerprint if repeat_result else None,
        checks=tuple(checks), interpretation_limits=_LIMITS, report_fingerprint="pending",
    )
    return replace(pending, report_fingerprint=fingerprint_report(pending))


def validate_model(
    plan: ValidationPlan,
    *,
    artifact_root: str | Path = ".",
    output_dir: str | Path = "outputs/validation",
) -> ValidationReport:
    """Verify an M8 artifact, execute/load its M9 evidence, and evaluate invariants."""
    if not isinstance(plan, ValidationPlan):
        raise TypeError("plan must be a ValidationPlan")
    artifact_path = _resolve_relative(artifact_root, plan.artifact_path)
    artifact = load_artifact(artifact_path)
    checks: list[ValidationCheck] = []

    checks.append(_check("artifact_integrity", "integrity", "passed" if verify_artifact(artifact) else "failed",
                         "M8 artifact model and artifact fingerprints are valid." if verify_artifact(artifact) else "M8 artifact fingerprint verification failed.",
                         artifact_fingerprint=artifact.artifact_fingerprint, model_fingerprint=artifact.model_fingerprint))
    model_schema_valid = True
    try:
        _parse_model(artifact)
        checks.append(_check("model_schema", "structural_verification", "passed",
                             "The M8 model payload passes its registered native parser/schema validation.", paradigm=artifact.paradigm.value))
    except Exception as error:
        model_schema_valid = False
        checks.append(_check("model_schema", "structural_verification", "failed",
                             f"Native model validation failed: {type(error).__name__}: {error}"))

    if not model_schema_valid and not plan.execution_result_path:
        checks.append(_check("execution_evidence", "execution", "skipped",
                             "Execution was blocked because the M8 model failed native schema validation."))
        if plan.repeatability_check:
            checks.append(_check("repeatability", "reproducibility", "skipped",
                                 "Repeatability was not attempted because a valid model execution could not be produced."))
        return _assemble_report(plan, artifact, checks)

    if plan.execution_result_path:
        result_path = _resolve_relative(artifact_root, plan.execution_result_path)
        result = load_result(result_path)
    else:
        config = ExperimentConfig(runs=plan.execution_runs, base_seed=plan.execution_base_seed, continue_on_error=False)
        result = execute_artifact(artifact, config)
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        from execution import save_result
        result_path = output / f"m26-evidence-{uuid.uuid4().hex}.json"
        save_result(result, result_path)

    linked = result.artifact_id == artifact.artifact_id and result.artifact_fingerprint == artifact.artifact_fingerprint
    checks.append(_check("execution_lineage", "provenance", "passed" if linked else "failed",
                         "M9 result is linked to the exact M8 artifact." if linked else "M9 result does not reference the exact M8 artifact.",
                         result_artifact_id=result.artifact_id, result_artifact_fingerprint=result.artifact_fingerprint))
    checks.extend(_baseline_trace_checks(artifact, result))

    for invariant in plan.invariants:
        for run in result.runs:
            if run.status is RunStatus.COMPLETED:
                checks.append(_evaluate_invariant(invariant, run.trace, run.run_index))

    repeat_result = None
    if plan.repeatability_check:
        repeat_result = execute_artifact(artifact, result.config)
        baseline = _stable_run_projection(result)
        repeated = _stable_run_projection(repeat_result)
        # Tolerance-aware comparison is applied to canonical trace/metric values.
        identical = _approximately_equal(baseline, repeated, float(plan.repeatability_tolerance))
        checks.append(_check("repeatability", "reproducibility", "passed" if identical else "failed",
                             "Repeated execution reproduced the same modeled metrics and trace within tolerance." if identical else "Repeated execution differed from the original result beyond tolerance.",
                             tolerance=plan.repeatability_tolerance, original_experiment_id=result.experiment_id,
                             repeated_experiment_id=repeat_result.experiment_id))
    else:
        checks.append(_check("repeatability", "reproducibility", "skipped",
                             "Repeatability was not requested in this validation plan."))

    return _assemble_report(plan, artifact, checks, result, repeat_result)


def _approximately_equal(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_approximately_equal(left[key], right[key], tolerance) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_approximately_equal(a, b, tolerance) for a, b in zip(left, right))
    return left == right


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "validation_id": report.validation_id,
        "created_at": report.created_at,
        "validation_name": report.validation_name,
        "overall_status": report.overall_status,
        "artifact_id": report.artifact_id,
        "artifact_fingerprint": report.artifact_fingerprint,
        "model_fingerprint": report.model_fingerprint,
        "project_id": report.project_id,
        "revision_id": report.revision_id,
        "paradigm": report.paradigm,
        "backend_name": report.backend_name,
        "experiment_id": report.experiment_id,
        "result_fingerprint": report.result_fingerprint,
        "repeatability_experiment_id": report.repeatability_experiment_id,
        "repeatability_result_fingerprint": report.repeatability_result_fingerprint,
        "checks": [{"check_id": item.check_id, "category": item.category, "status": item.status,
                    "message": item.message, "details": item.details} for item in report.checks],
        "interpretation_limits": list(report.interpretation_limits),
        "report_fingerprint": report.report_fingerprint,
    }


def fingerprint_report(report: ValidationReport) -> str:
    payload = report_to_dict(report)
    payload["report_fingerprint"] = "pending"
    return _fingerprint(payload)
