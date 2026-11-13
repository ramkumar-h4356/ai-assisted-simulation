"""Execute integrity-verified M8 artifacts through implemented DES/ABM backends."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import time
import uuid
from typing import Any

from compilation.compiler import verify_artifact
from compilation.models import CompilationArtifact, CompilationParadigm
from simulations.core.specification import SimulationParadigm, SimulationSpecification

from execution.models import (
    ExperimentConfig, ExperimentResult, ExperimentStatus, MetricRecord,
    ParameterSet, RunRecord, RunStatus,
)

MAX_TRACE_RECORDS_PER_EXPERIMENT = 500_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_model(artifact: CompilationArtifact, model_data: dict[str, Any] | None = None) -> Any:
    """Rebuild the native model from the M8 payload or one approved variant."""
    data = artifact.model_data if model_data is None else model_data
    if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT:
        from simulations.des.schema import scenario_from_dict
        return scenario_from_dict(data)
    if artifact.paradigm is CompilationParadigm.AGENT_BASED:
        from simulations.abm.schema import agent_model_from_dict
        from simulations.abm.validation import validate_agent_model
        model = agent_model_from_dict(data)
        validation = validate_agent_model(model)
        if validation.errors:
            details = "; ".join(f"{item.code}: {item.message}" for item in validation.errors)
            raise ValueError(f"ABM parameter variant failed semantic validation: {details}")
        return model
    raise ValueError(
        f"M9 cannot execute {artifact.paradigm.value}; only DES and ABM backends are implemented"
    )


def _simulation_paradigm(artifact: CompilationArtifact) -> SimulationParadigm:
    if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT:
        return SimulationParadigm.DISCRETE_EVENT
    if artifact.paradigm is CompilationParadigm.AGENT_BASED:
        return SimulationParadigm.AGENT_BASED
    raise ValueError(f"Unsupported execution paradigm: {artifact.paradigm.value}")


def _estimate_trace_records(artifact: CompilationArtifact, model_data: dict[str, Any] | None = None) -> int:
    data = artifact.model_data if model_data is None else model_data
    if artifact.paradigm is CompilationParadigm.AGENT_BASED:
        agents = len(data.get("agents", []))
        steps = data.get("termination", {}).get("value", 0)
        rules = len(data.get("behaviours", []))
        return agents * (steps + 1) + agents * steps * rules
    if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT:
        stage_count = 0
        for job in data.get("jobs", []):
            stages = job.get("stages")
            stage_count += len(stages) if stages else 1
        entity_count = len(data.get("jobs", []))
        return stage_count * 3 + entity_count + len(data.get("resources", []))
    return 0


def _path_tokens(path: str) -> list[str | int] | None:
    import re
    pattern = re.compile(r"(?:^|\.)([A-Za-z_][A-Za-z0-9_-]*)|\[(0|[1-9][0-9]*)\]")
    tokens: list[str | int] = []
    cursor = 0
    for match in pattern.finditer(path):
        if match.start() != cursor:
            return None
        tokens.append(match.group(1) if match.group(1) is not None else int(match.group(2)))
        cursor = match.end()
    return tokens if tokens and cursor == len(path) else None


def _read_path(data: Any, tokens: list[str | int]) -> Any:
    current = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise ValueError("parameter target path does not exist in model_data")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise ValueError("parameter target path does not exist in model_data")
            current = current[token]
    return current


def _write_path(data: Any, tokens: list[str | int], value: Any) -> None:
    parent = _read_path(data, tokens[:-1])
    final = tokens[-1]
    if isinstance(final, int):
        if not isinstance(parent, list) or final >= len(parent):
            raise ValueError("parameter target path does not exist in model_data")
        parent[final] = value
    else:
        if not isinstance(parent, dict) or final not in parent:
            raise ValueError("parameter target path does not exist in model_data")
        parent[final] = value


def _apply_parameter_set(
    artifact: CompilationArtifact,
    parameter_set: ParameterSet,
) -> dict[str, Any]:
    """Apply only exact paths declared as user-supplied parameters in M8."""
    import json
    from compilation.models import BindingSource

    data = json.loads(json.dumps(artifact.model_data, ensure_ascii=False, allow_nan=False))
    allowed_paths = {
        binding.target_path
        for binding in artifact.bindings
        if binding.source is BindingSource.USER_PARAMETER
    }
    parsed_paths: list[tuple[str, list[str | int]]] = []
    for override in parameter_set.overrides:
        if override.target_path not in allowed_paths:
            raise ValueError(
                f"Parameter path {override.target_path!r} is not an explicitly bound M8 user_parameter; "
                "only documented experiment parameters can be varied"
            )
        tokens = _path_tokens(override.target_path)
        if tokens is None:
            raise ValueError(f"Invalid parameter target path: {override.target_path!r}")
        if "random_seed" in tokens:
            raise ValueError("random_seed is controlled by ExperimentConfig and cannot be overridden as a model parameter")
        current = _read_path(data, tokens)
        if type(current) is not type(override.value):
            raise ValueError(
                f"Parameter {override.target_path!r} expects a {type(current).__name__} value, "
                f"not {type(override.value).__name__}"
            )
        for previous_path, previous_tokens in parsed_paths:
            common = min(len(tokens), len(previous_tokens))
            if tokens[:common] == previous_tokens[:common]:
                raise ValueError(
                    f"Parameter paths {previous_path!r} and {override.target_path!r} overlap"
                )
        parsed_paths.append((override.target_path, tokens))
        _write_path(data, tokens, override.value)
    return data


def _json_safe(value: Any) -> Any:
    """Convert a scalar/container tree to finite, JSON-compatible values."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Simulation produced a non-finite numeric value")
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value") and isinstance(value.value, (str, int, float, bool)):
        return _json_safe(value.value)
    raise TypeError(f"Cannot serialize simulation trace value of type {type(value).__name__}")


def _capture_trace(native_result: Any, paradigm: CompilationParadigm) -> dict[str, Any]:
    if paradigm is CompilationParadigm.AGENT_BASED:
        history = []
        for snapshot in native_result.history:
            history.append({
                "step": snapshot.step,
                "agents": [
                    {
                        "id": agent.identifier,
                        "agent_type": agent.agent_type,
                        "state": agent.state,
                        "attributes": dict(agent.attributes),
                    }
                    for agent in snapshot.agents
                ],
            })
        evaluations = [
            {
                "step": item.step,
                "agent_id": item.agent_id,
                "rule_id": item.rule_id,
                "condition_matched": item.condition_matched,
                "probability_passed": item.probability_passed,
                "actions_applied": item.actions_applied,
                "state_before": item.state_before,
                "state_after": item.state_after,
            }
            for item in native_result.rule_evaluations
        ]
        return _json_safe({
            "history": history,
            "rule_evaluations": evaluations,
            "final_state_counts": dict(native_result.final_state_counts),
        })

    if paradigm is CompilationParadigm.DISCRETE_EVENT:
        events = [
            {
                "time": event.time,
                "entity_id": event.entity_id,
                "event_type": event.event_type,
                "resource_name": event.resource_name,
            }
            for event in native_result.events
        ]
        entities = [
            {
                "entity_id": item.entity_id,
                "arrival_time": item.arrival_time,
                "completion_time": item.completion_time,
                "waiting_time": item.waiting_time,
                "service_time": item.service_time,
                "time_in_system": item.time_in_system,
            }
            for item in native_result.entity_metrics
        ]
        resources = [
            {
                "resource_name": item.resource_name,
                "completed_services": item.completed_services,
                "average_waiting_time": item.average_waiting_time,
                "average_service_time": item.average_service_time,
                "utilization": item.utilization,
            }
            for item in native_result.resource_metrics
        ]
        return _json_safe({"events": events, "entities": entities, "resources": resources})

    raise ValueError(f"No trace serializer for {paradigm.value}")


def _execute_once(
    artifact: CompilationArtifact,
    native_model: Any,
    model_data: dict[str, Any],
    seed: int | None,
) -> tuple[tuple[MetricRecord, ...], dict[str, Any]]:
    paradigm = _simulation_paradigm(artifact)
    model = replace(native_model, random_seed=seed) if artifact.paradigm is CompilationParadigm.AGENT_BASED else native_model
    specification = SimulationSpecification(
        name=str(model_data.get("name", artifact.project_title)),
        paradigm=paradigm,
        model=model,
    )
    if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT:
        # Import lazily: an ABM-only user does not need the optional SimPy package.
        from simulations.des.backend import SimPyBackend
        execution = SimPyBackend().execute(specification)
    elif artifact.paradigm is CompilationParadigm.AGENT_BASED:
        from simulations.abm.backend import AgentBasedBackend
        execution = AgentBasedBackend().execute(specification)
    else:
        raise ValueError(f"No backend is implemented for {artifact.paradigm.value}")

    metrics = tuple(MetricRecord(item.name, item.value, item.unit) for item in execution.metrics)
    trace = _capture_trace(execution.native_result, artifact.paradigm)
    return metrics, trace


def execute_artifact(
    artifact: CompilationArtifact,
    config: ExperimentConfig | None = None,
) -> ExperimentResult:
    """Run one or more controlled executions linked to a verified M8 artifact.

    For ABM, seeds are ``base_seed + run_index - 1``. When ``base_seed`` is not
    supplied, the compiled model's random_seed is used as the base. A seeded
    ABM is required for reproducible execution. DES V1 is deterministic and
    rejects a seed because it does not use one.
    """
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed; execution blocked")
    settings = config or ExperimentConfig()
    if not isinstance(settings, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    if artifact.m7_readiness_status != "ready_for_implementation_planning":
        raise ValueError("M8 artifact does not record the required M7 readiness status")
    expected_backends = {
        CompilationParadigm.DISCRETE_EVENT: "DES V1 / SimPy backend",
        CompilationParadigm.AGENT_BASED: "ABM V1 backend",
    }
    if artifact.paradigm not in expected_backends:
        raise ValueError(f"M9 does not implement the {artifact.paradigm.value} paradigm")
    if artifact.backend_name != expected_backends[artifact.paradigm]:
        raise ValueError(
            f"M8 artifact backend mismatch for {artifact.paradigm.value}: "
            f"expected {expected_backends[artifact.paradigm]!r}, got {artifact.backend_name!r}"
        )
    if artifact.paradigm is CompilationParadigm.DISCRETE_EVENT and settings.base_seed is not None:
        raise ValueError("DES V1 is deterministic and does not consume random seeds; omit base_seed")

    base_seed = settings.base_seed
    parameter_sets = settings.parameter_sets or (ParameterSet("baseline"),)
    prepared_variants: list[tuple[ParameterSet, dict[str, Any], Any]] = []
    estimated = 0
    for parameter_set in parameter_sets:
        variant_data = _apply_parameter_set(artifact, parameter_set)
        variant_model = _parse_model(artifact, variant_data)
        prepared_variants.append((parameter_set, variant_data, variant_model))
        estimated += _estimate_trace_records(artifact, variant_data) * settings.runs

    if artifact.paradigm is CompilationParadigm.AGENT_BASED:
        if base_seed is None:
            base_seed = prepared_variants[0][2].random_seed
        if base_seed is None:
            raise ValueError("ABM execution requires a reproducible seed: set base_seed in ExperimentConfig or define random_seed in the compiled model")

    if estimated > MAX_TRACE_RECORDS_PER_EXPERIMENT:
        raise ValueError(
            f"Estimated trace size ({estimated:,} records) exceeds the M9 safety limit "
            f"of {MAX_TRACE_RECORDS_PER_EXPERIMENT:,}; reduce runs or model size"
        )

    records: list[RunRecord] = []
    global_run_index = 0
    for parameter_set, variant_data, variant_model in prepared_variants:
        parameter_values = {item.target_path: item.value for item in parameter_set.overrides}
        for _replication in range(1, settings.runs + 1):
            global_run_index += 1
            seed = base_seed + global_run_index - 1 if artifact.paradigm is CompilationParadigm.AGENT_BASED else None
            started_at = _now()
            start_clock = time.perf_counter()
            try:
                metrics, trace = _execute_once(artifact, variant_model, variant_data, seed)
                elapsed = time.perf_counter() - start_clock
                records.append(RunRecord(
                    run_index=global_run_index,
                    status=RunStatus.COMPLETED,
                    seed=seed,
                    parameter_set=parameter_set.name,
                    parameters=parameter_values,
                    started_at=started_at,
                    finished_at=_now(),
                    elapsed_seconds=elapsed,
                    metrics=metrics,
                    trace=trace,
                ))
            except Exception as error:  # Persist a bounded, user-readable failure record.
                elapsed = time.perf_counter() - start_clock
                records.append(RunRecord(
                    run_index=global_run_index,
                    status=RunStatus.FAILED,
                    seed=seed,
                    parameter_set=parameter_set.name,
                    parameters=parameter_values,
                    started_at=started_at,
                    finished_at=_now(),
                    elapsed_seconds=elapsed,
                    metrics=(),
                    trace={},
                    error_type=type(error).__name__,
                    error_message=str(error)[:2000] or type(error).__name__,
                ))
                if not settings.continue_on_error:
                    break
        if records and records[-1].status is RunStatus.FAILED and not settings.continue_on_error:
            break

    successes = sum(item.status is RunStatus.COMPLETED for item in records)
    if successes == len(records) and len(records) == settings.total_runs:
        status = ExperimentStatus.COMPLETED
    elif successes == 0:
        status = ExperimentStatus.FAILED
    else:
        status = ExperimentStatus.PARTIAL

    from execution.serialization import fingerprint_result
    pending = ExperimentResult(
        schema_version=1,
        experiment_id="m9-" + uuid.uuid4().hex,
        created_at=_now(),
        artifact_id=artifact.artifact_id,
        artifact_fingerprint=artifact.artifact_fingerprint,
        project_id=artifact.project_id,
        project_title=artifact.project_title,
        revision_id=artifact.revision_id,
        revision_version=artifact.revision_version,
        paradigm=artifact.paradigm.value,
        backend_name=artifact.backend_name,
        config=settings,
        status=status,
        runs=tuple(records),
        result_fingerprint="pending",
    )
    return replace(pending, result_fingerprint=fingerprint_result(pending))


def execute_artifact_file(path: str, config: ExperimentConfig | None = None) -> ExperimentResult:
    """Load and verify an M8 artifact file before executing it."""
    from compilation.serialization import load_artifact
    return execute_artifact(load_artifact(path), config)
