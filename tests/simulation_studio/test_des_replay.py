from dataclasses import replace
from types import SimpleNamespace

import pytest

from compilation import CompilationParadigm, compile_profile
from execution import ExperimentConfig, ExperimentResult, ExperimentStatus, RunRecord, RunStatus
from execution.runner import _capture_trace
from execution.serialization import fingerprint_result
from simulation_studio import ReplayError, build_des_run_replay
from tests.compilation.helpers import des_profile
from tests.readiness.helpers import des_project


def _compiled_des():
    project = des_project()
    profile = des_profile(project)
    model_data = dict(profile.model_data)
    model_data["resources"] = [{"name": "Machine", "capacity": 1}]
    model_data["jobs"] = [
        {
            "entity_id": "job-A",
            "arrival_time": 0,
            "stages": [{"resource_name": "Machine", "service_duration": 4}],
        },
        {
            "entity_id": "job-B",
            "arrival_time": 1,
            "stages": [{"resource_name": "Machine", "service_duration": 2}],
        },
    ]
    profile = replace(profile, model_data=model_data)
    compilation = compile_profile(project, profile)
    assert compilation.is_ready
    return compilation.artifact


def _synthetic_result(compilation, *, include_m19_fields=True):
    events = [
        SimpleNamespace(time=0, entity_id="job-A", event_type="arrived", resource_name="Machine"),
        SimpleNamespace(time=0, entity_id="job-A", event_type="service_started", resource_name="Machine"),
        SimpleNamespace(time=1, entity_id="job-B", event_type="arrived", resource_name="Machine"),
        SimpleNamespace(time=4, entity_id="job-A", event_type="service_completed", resource_name="Machine"),
        SimpleNamespace(time=4, entity_id="job-B", event_type="service_started", resource_name="Machine"),
        SimpleNamespace(time=6, entity_id="job-B", event_type="service_completed", resource_name="Machine"),
    ]
    native_result = SimpleNamespace(
        events=events,
        entity_metrics=[
            SimpleNamespace(entity_id="job-A", arrival_time=0, completion_time=4, waiting_time=0, service_time=4, time_in_system=4),
            SimpleNamespace(entity_id="job-B", arrival_time=1, completion_time=6, waiting_time=3, service_time=2, time_in_system=5),
        ],
        resource_metrics=[
            SimpleNamespace(resource_name="Machine", completed_services=2, average_waiting_time=1.5,
                            average_service_time=3.0, utilization=100.0),
        ],
        resource_capacities=(("Machine", 1),),
    )
    trace = _capture_trace(native_result, CompilationParadigm.DISCRETE_EVENT)
    if not include_m19_fields:
        trace.pop("resource_capacities")
        trace.pop("replay")

    run = RunRecord(
        run_index=1,
        status=RunStatus.COMPLETED,
        seed=None,
        parameter_set="baseline",
        parameters={},
        started_at="2026-11-14T10:00:00+00:00",
        finished_at="2026-11-14T10:00:01+00:00",
        elapsed_seconds=1.0,
        metrics=(),
        trace=trace,
    )
    result = ExperimentResult(
        schema_version=1,
        experiment_id="m19-test-experiment",
        created_at="2026-11-14T10:00:00+00:00",
        artifact_id=compilation.artifact_id,
        artifact_fingerprint=compilation.artifact_fingerprint,
        project_id=compilation.project_id,
        project_title=compilation.project_title,
        revision_id=compilation.revision_id,
        revision_version=compilation.revision_version,
        paradigm=CompilationParadigm.DISCRETE_EVENT.value,
        backend_name=compilation.backend_name,
        config=ExperimentConfig(runs=1),
        status=ExperimentStatus.COMPLETED,
        runs=(run,),
        result_fingerprint="pending",
    )
    return replace(result, result_fingerprint=fingerprint_result(result))


def test_m9_trace_capture_persists_replay_projection_and_resource_capacities():
    compilation = _compiled_des()
    result = _synthetic_result(compilation)
    run = result.runs[0]
    assert run.trace["resource_capacities"] == {"Machine": 1}
    assert run.trace["replay"]["summary"]["completed_entity_count"] == 2
    assert run.trace["replay"]["resources"][0]["peak_queue_length"] == 1

    replay = build_des_run_replay(result, compilation)
    assert replay["lineage"]["run_index"] == 1
    assert replay["lineage"]["project_id"] == result.project_id
    assert replay["entities"][1]["entity_id"] == "job-B"
    assert replay["entities"][1]["waiting_time"] == 3.0


def test_des_replay_supports_pre_m19_m9_results_using_linked_m8_capacities():
    compilation = _compiled_des()
    result = _synthetic_result(compilation, include_m19_fields=False)
    replay = build_des_run_replay(result, compilation)
    assert replay["resources"][0]["capacity"] == 1
    assert replay["entities"][1]["waiting_time"] == 3.0


def test_des_replay_rejects_mismatched_compilation_provenance():
    compilation = _compiled_des()
    result = _synthetic_result(compilation)
    other_project = des_project()
    other_profile = replace(des_profile(other_project), profile_id="other-profile")
    other_compilation = compile_profile(other_project, other_profile).artifact
    with pytest.raises(ReplayError, match="provenance do not match"):
        build_des_run_replay(result, other_compilation)


def test_des_replay_rejects_missing_or_failed_runs():
    compilation = _compiled_des()
    result = _synthetic_result(compilation)
    with pytest.raises(ReplayError, match="does not exist"):
        build_des_run_replay(result, compilation, run_index=2)

    failed_run = replace(result.runs[0], status=RunStatus.FAILED,
                         error_type="RuntimeError", error_message="test failure")
    changed = replace(result, runs=(failed_run,), status=ExperimentStatus.FAILED, result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    with pytest.raises(ReplayError, match="did not complete"):
        build_des_run_replay(changed, compilation)


def test_des_replay_detects_corrupt_stored_projection():
    compilation = _compiled_des()
    result = _synthetic_result(compilation)
    run = result.runs[0]
    trace = dict(run.trace)
    trace["replay"] = dict(trace["replay"])
    trace["replay"]["duration"] = 999
    changed_run = replace(run, trace=trace)
    changed = replace(result, runs=(changed_run,), result_fingerprint="pending")
    changed = replace(changed, result_fingerprint=fingerprint_result(changed))
    with pytest.raises(ReplayError, match="does not match"):
        build_des_run_replay(changed, compilation)
