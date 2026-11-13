from dataclasses import replace

import pytest

from compilation.compiler import fingerprint_artifact
from execution import (
    ExperimentConfig, ExperimentStatus, RunStatus, execute_artifact,
)
from execution.runner import MAX_TRACE_RECORDS_PER_EXPERIMENT
from tests.execution.helpers import abm_artifact, des_artifact


def test_abm_executes_multiple_runs_with_consecutive_seeds_and_full_trace():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=3, base_seed=21))

    assert result.status is ExperimentStatus.COMPLETED
    assert [run.seed for run in result.runs] == [21, 22, 23]
    assert all(run.status is RunStatus.COMPLETED for run in result.runs)
    assert result.runs[0].trace["history"][0]["step"] == 0
    assert result.runs[0].trace["history"][-1]["step"] == 10
    assert result.runs[0].trace["rule_evaluations"]
    assert result.runs[0].trace["final_state_counts"]


def test_seeded_abm_execution_is_reproducible_across_experiment_replays():
    artifact = abm_artifact(probability=0.5)
    config = ExperimentConfig(runs=4, base_seed=900)

    first = execute_artifact(artifact, config)
    second = execute_artifact(artifact, config)

    assert [item.seed for item in first.runs] == [item.seed for item in second.runs]
    assert [item.trace for item in first.runs] == [item.trace for item in second.runs]
    assert [item.metrics for item in first.runs] == [item.metrics for item in second.runs]


def test_abm_uses_compiled_seed_when_experiment_seed_is_omitted():
    result = execute_artifact(abm_artifact(seed=42))
    assert result.runs[0].seed == 42


def test_abm_requires_a_seed_for_reproducibility():
    with pytest.raises(ValueError, match="requires a reproducible seed"):
        execute_artifact(abm_artifact(seed=None))


def test_des_rejects_a_seed_because_des_v1_is_deterministic():
    with pytest.raises(ValueError, match="does not consume random seeds"):
        execute_artifact(des_artifact(), ExperimentConfig(base_seed=5))


def test_execution_rejects_tampered_m8_artifact():
    artifact = abm_artifact()
    changed = dict(artifact.model_data)
    changed["name"] = "tampered"
    tampered = replace(artifact, model_data=changed)
    with pytest.raises(ValueError, match="integrity verification failed"):
        execute_artifact(tampered)


def test_execution_rejects_artifact_without_m7_implementation_readiness():
    artifact = abm_artifact()
    changed = replace(artifact, m7_readiness_status="needs_clarification")
    changed = replace(changed, artifact_fingerprint=fingerprint_artifact(changed))
    with pytest.raises(ValueError, match="required M7 readiness status"):
        execute_artifact(changed)


def test_execution_enforces_run_count_bound():
    with pytest.raises(ValueError, match="between 1 and 100"):
        ExperimentConfig(runs=101)


def test_execution_enforces_estimated_trace_budget():
    artifact = abm_artifact()
    # Replace the validated artifact with a correctly fingerprinted but oversized
    # model payload to exercise the deterministic resource guard before execution.
    from compilation.compiler import fingerprint_model
    data = dict(artifact.model_data)
    data["termination"] = {"type": "max_steps", "value": MAX_TRACE_RECORDS_PER_EXPERIMENT}
    changed = replace(artifact, model_data=data, model_fingerprint=fingerprint_model(artifact.paradigm, data))
    changed = replace(changed, artifact_fingerprint=fingerprint_artifact(changed))
    with pytest.raises(ValueError, match="safety limit"):
        execute_artifact(changed)


def test_des_execution_creates_failed_run_record_when_simpy_is_unavailable(monkeypatch):
    import execution.runner as runner

    def unavailable(*args, **kwargs):
        raise ModuleNotFoundError("simpy is not installed")

    monkeypatch.setattr(runner, "_execute_once", unavailable)
    result = execute_artifact(des_artifact())
    assert result.status is ExperimentStatus.FAILED
    assert result.runs[0].status is RunStatus.FAILED
    assert result.runs[0].error_type == "ModuleNotFoundError"
    assert "simpy" in result.runs[0].error_message


def test_continuation_after_failure_produces_partial_experiment(monkeypatch):
    import execution.runner as runner

    calls = {"count": 0}

    def one_failure_then_success(*args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("first run failed")
        return (), {"history": [], "rule_evaluations": [], "final_state_counts": {}}

    monkeypatch.setattr(runner, "_execute_once", one_failure_then_success)
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=1))

    assert result.status is ExperimentStatus.PARTIAL
    assert [run.status for run in result.runs] == [RunStatus.FAILED, RunStatus.COMPLETED]
    assert [run.seed for run in result.runs] == [1, 2]


def test_continue_on_error_false_stops_after_first_failed_run(monkeypatch):
    import execution.runner as runner

    calls = {"count": 0}

    def always_fail(*args):
        calls["count"] += 1
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(runner, "_execute_once", always_fail)
    result = execute_artifact(
        abm_artifact(),
        ExperimentConfig(runs=4, base_seed=1, continue_on_error=False),
    )

    assert result.status is ExperimentStatus.FAILED
    assert len(result.runs) == 1
    assert calls["count"] == 1


def test_des_trace_serializer_preserves_event_and_metric_details():
    from types import SimpleNamespace
    from compilation.models import CompilationParadigm
    from execution.runner import _capture_trace

    native = SimpleNamespace(
        events=(
            SimpleNamespace(time=0.0, entity_id="job-1", event_type="arrived", resource_name="machine"),
            SimpleNamespace(time=0.0, entity_id="job-1", event_type="service_started", resource_name="machine"),
            SimpleNamespace(time=5.0, entity_id="job-1", event_type="service_completed", resource_name="machine"),
        ),
        entity_metrics=(SimpleNamespace(
            entity_id="job-1", arrival_time=0, completion_time=5,
            waiting_time=0, service_time=5, time_in_system=5,
        ),),
        resource_metrics=(SimpleNamespace(
            resource_name="machine", completed_services=1,
            average_waiting_time=0.0, average_service_time=5.0, utilization=100.0,
        ),),
    )
    trace = _capture_trace(native, CompilationParadigm.DISCRETE_EVENT)

    assert [event["event_type"] for event in trace["events"]] == [
        "arrived", "service_started", "service_completed"
    ]
    assert trace["entities"][0]["time_in_system"] == 5
    assert trace["resources"][0]["utilization"] == 100


def test_parameter_sets_vary_only_explicit_m8_user_parameters_and_keep_provenance():
    from execution import ParameterOverride, ParameterSet

    artifact = abm_artifact()
    config = ExperimentConfig(
        runs=2,
        base_seed=100,
        parameter_sets=(
            ParameterSet("lower-trust", (
                ParameterOverride("agents[0].attributes.trust", 0.2),
                ParameterOverride("termination.value", 3),
            )),
            ParameterSet("higher-trust", (
                ParameterOverride("agents[0].attributes.trust", 0.9),
                ParameterOverride("termination.value", 3),
            )),
        ),
    )

    result = execute_artifact(artifact, config)

    assert result.status is ExperimentStatus.COMPLETED
    assert len(result.runs) == 4
    assert [run.seed for run in result.runs] == [100, 101, 102, 103]
    assert [run.parameter_set for run in result.runs] == [
        "lower-trust", "lower-trust", "higher-trust", "higher-trust"
    ]
    assert result.runs[0].parameters["agents[0].attributes.trust"] == 0.2
    assert result.runs[0].trace["history"][0]["agents"][0]["attributes"]["trust"] == 0.2
    assert result.runs[0].trace["history"][-1]["step"] == 3
    assert artifact.model_data["agents"][0]["attributes"]["trust"] == 0.8


def test_parameter_set_cannot_override_unbound_or_conceptual_fields():
    from execution import ParameterOverride, ParameterSet

    config = ExperimentConfig(parameter_sets=(ParameterSet(
        "unauthorized", (ParameterOverride("agents[1].state", "inactive"),)
    ),))
    with pytest.raises(ValueError, match="not an explicitly bound M8 user_parameter"):
        execute_artifact(abm_artifact(), config)


def test_parameter_override_must_preserve_existing_scalar_type():
    from execution import ParameterOverride, ParameterSet

    config = ExperimentConfig(parameter_sets=(ParameterSet(
        "invalid-horizon", (ParameterOverride("termination.value", 2.5),)
    ),))
    with pytest.raises(ValueError, match="expects a int value"):
        execute_artifact(abm_artifact(), config)


def test_parameter_set_count_and_replications_respect_total_run_limit():
    from execution import ParameterSet

    parameter_sets = tuple(ParameterSet(f"set-{index}") for index in range(11))
    with pytest.raises(ValueError, match="100 total executions"):
        ExperimentConfig(runs=10, parameter_sets=parameter_sets)


def test_des_parameter_set_updates_only_bound_user_parameter_on_a_fresh_model(monkeypatch):
    import execution.runner as runner
    from execution import ParameterOverride, ParameterSet

    seen = []

    def fake_execution(artifact, native_model, model_data, seed):
        seen.append((native_model.resources[0].capacity, seed))
        return (), {"events": [], "entities": [], "resources": []}

    monkeypatch.setattr(runner, "_execute_once", fake_execution)
    artifact = des_artifact()
    config = ExperimentConfig(parameter_sets=(ParameterSet(
        "higher-capacity", (ParameterOverride("resources[0].capacity", 3),)
    ),))
    result = execute_artifact(artifact, config)

    assert result.status is ExperimentStatus.COMPLETED
    assert seen == [(3, None)]
    assert result.runs[0].parameters == {"resources[0].capacity": 3}
    assert artifact.model_data["resources"][0]["capacity"] == 2


def test_invalid_parameter_variant_is_rejected_before_any_run_starts(monkeypatch):
    import execution.runner as runner
    from execution import ParameterOverride, ParameterSet

    def should_not_execute(*args):
        raise AssertionError("execution must not start for an invalid parameter set")

    monkeypatch.setattr(runner, "_execute_once", should_not_execute)
    config = ExperimentConfig(parameter_sets=(ParameterSet(
        "zero-horizon", (ParameterOverride("termination.value", 0),)
    ),))
    with pytest.raises(ValueError):
        execute_artifact(abm_artifact(), config)
