from dataclasses import replace
import pytest

from compilation import compile_profile, dumps_artifact, loads_artifact, verify_artifact
from execution import (
    ExperimentConfig, ExperimentStatus, ParameterOverride, ParameterSet,
    dumps_result, execute_artifact, loads_result,
)
from tests.compilation.test_system_dynamics_compilation import system_dynamics_profile
from tests.readiness.test_system_dynamics_readiness import system_dynamics_project
from workbench.extensions import create_builtin_registry


def artifact():
    project = system_dynamics_project()
    compiled = compile_profile(project, system_dynamics_profile(project))
    assert compiled.is_ready, compiled.issues
    return compiled.artifact


def test_system_dynamics_artifact_executes_through_m9_and_saves_stock_flow_trace():
    compiled = loads_artifact(dumps_artifact(artifact()))
    assert verify_artifact(compiled)
    result = execute_artifact(compiled)
    assert result.status is ExperimentStatus.COMPLETED
    assert result.paradigm == "system_dynamics"
    trace = result.runs[0].trace
    assert trace["solver"] == "rk4"
    assert trace["steps"] == 400
    assert len(trace["time_series"]) == 401
    assert trace["time_series"][-1]["stocks"]["susceptible"] < 990
    assert trace["time_series"][-1]["auxiliaries"]["population"] == pytest.approx(1000)
    assert trace["total_flow"]["infection"] > 0


def test_system_dynamics_result_round_trips_with_fingerprint():
    result = execute_artifact(artifact())
    restored = loads_result(dumps_result(result))
    assert restored.result_fingerprint == result.result_fingerprint
    assert restored.runs[0].trace == result.runs[0].trace


def test_parameter_sweep_changes_flow_rates_without_mutating_compiled_artifact():
    compiled = artifact()
    result = execute_artifact(compiled, ExperimentConfig(parameter_sets=(
        ParameterSet("slower-infection", (ParameterOverride("parameters[0].value", 0.15),)),
        ParameterSet("faster-infection", (ParameterOverride("parameters[0].value", 0.45),)),
    )))
    assert result.status is ExperimentStatus.COMPLETED
    low = result.runs[0].trace["summaries"]["infected"]["maximum"]
    high = result.runs[1].trace["summaries"]["infected"]["maximum"]
    assert high > low
    assert compiled.model_data["parameters"][0]["value"] == 0.30


def test_system_dynamics_rejects_random_seed_configuration():
    with pytest.raises(ValueError, match="does not consume random seeds"):
        execute_artifact(artifact(), ExperimentConfig(base_seed=10))


def test_system_dynamics_execution_rejects_tampered_artifact():
    compiled = artifact()
    altered = dict(compiled.model_data)
    altered["name"] = "tampered"
    with pytest.raises(ValueError, match="integrity verification failed"):
        execute_artifact(replace(compiled, model_data=altered))


def test_m13_system_dynamics_extension_compiles_executes_and_validates_saved_result():
    project = system_dynamics_project()
    adapter = create_builtin_registry().for_paradigm("system_dynamics")
    assessment, report = adapter.validate(project, project.current_revision_id)
    assert report.status.value == "ready_for_implementation_planning"
    assert assessment.backend_status.value == "implemented"
    compiled = adapter.compile(project, project.current_revision_id, system_dynamics_profile(project))
    assert compiled.is_ready, compiled.issues
    result = adapter.execute(compiled.artifact, None)
    payload = adapter.serialize_result(result)
    restored = adapter.validate_result(payload)
    assert restored.result_fingerprint == result.result_fingerprint
    assert restored.runs[0].trace["time_series"][-1]["stocks"]["recovered"] > 900
