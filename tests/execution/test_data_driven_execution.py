from dataclasses import replace

import pytest

from compilation import compile_profile, dumps_artifact, loads_artifact, verify_artifact
from execution import (
    ExperimentConfig, ExperimentStatus, ParameterOverride, ParameterSet,
    dumps_result, execute_artifact, loads_result,
)
from tests.compilation.helpers import data_driven_profile
from tests.readiness.helpers import data_project


def artifact():
    project = data_project()
    result = compile_profile(project, data_driven_profile(project))
    assert result.is_ready, result.issues
    return result.artifact

def test_data_driven_artifact_executes_through_m9_and_captures_forecast_trace():
    compiled = loads_artifact(dumps_artifact(artifact()))
    assert verify_artifact(compiled)
    result = execute_artifact(compiled)
    assert result.status is ExperimentStatus.COMPLETED
    assert result.paradigm == "data_driven"
    trace = result.runs[0].trace
    assert trace["method"] == "ridge_var"
    assert trace["dataset_reference_id"] == "dataset-ref"
    assert trace["evaluation_strategy"] == "one_step_walk_forward_with_observed_history"
    assert len(trace["holdout_predictions"]) == 15
    assert len(trace["forecast"]) == 6
    assert trace["forecast"][-1]["time"] == 65.0

def test_data_driven_result_round_trips_with_fingerprint():
    result = execute_artifact(artifact())
    loaded = loads_result(dumps_result(result))
    assert loaded.result_fingerprint == result.result_fingerprint
    assert loaded.runs[0].trace == result.runs[0].trace

def test_data_driven_parameter_sets_can_change_declared_horizon_and_ridge():
    result = execute_artifact(artifact(), ExperimentConfig(parameter_sets=(
        ParameterSet("short", (ParameterOverride("forecast_horizon", 2),)),
        ParameterSet("long", (ParameterOverride("forecast_horizon", 4),)),
    )))
    assert result.status is ExperimentStatus.COMPLETED
    assert len(result.runs[0].trace["forecast"]) == 2
    assert len(result.runs[1].trace["forecast"]) == 4

def test_data_driven_execution_rejects_random_seed_configuration():
    with pytest.raises(ValueError, match="does not consume random seeds"):
        execute_artifact(artifact(), ExperimentConfig(base_seed=1))

def test_data_driven_execution_rejects_tampered_artifact():
    compiled = artifact()
    data = dict(compiled.model_data)
    data["name"] = "tampered"
    tampered = replace(compiled, model_data=data)
    with pytest.raises(ValueError, match="integrity verification failed"):
        execute_artifact(tampered)
