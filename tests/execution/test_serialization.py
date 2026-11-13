import json

import pytest

from execution import (
    ExperimentConfig, ExperimentSerializationError, execute_artifact,
    load_result, loads_result, save_result,
)
from execution.serialization import result_to_dict
from tests.execution.helpers import abm_artifact


def test_experiment_result_json_round_trip(tmp_path):
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=15))
    path = save_result(result, tmp_path / "experiment.json")

    loaded = load_result(path)
    assert loaded == result
    assert loaded.result_fingerprint == result.result_fingerprint


def test_result_tampering_is_detected():
    result = execute_artifact(abm_artifact())
    raw = result_to_dict(result)
    raw["runs"][0]["metrics"][0]["value"] += 100

    with pytest.raises(ExperimentSerializationError, match="fingerprint"):
        loads_result(json.dumps(raw))


def test_result_schema_rejects_unknown_fields():
    result = execute_artifact(abm_artifact())
    raw = result_to_dict(result)
    raw["unexpected"] = True

    with pytest.raises(ExperimentSerializationError, match="unknown field"):
        loads_result(json.dumps(raw))


def test_failed_runs_round_trip_with_error_details(monkeypatch, tmp_path):
    import execution.runner as runner

    monkeypatch.setattr(runner, "_execute_once", lambda *args: (_ for _ in ()).throw(RuntimeError("controlled failure")))
    result = execute_artifact(abm_artifact())
    path = save_result(result, tmp_path / "failed.json")
    loaded = load_result(path)

    assert loaded.runs[0].status.value == "failed"
    assert loaded.runs[0].error_type == "RuntimeError"
    assert loaded.runs[0].error_message == "controlled failure"


def test_parameter_sweep_configuration_and_run_values_round_trip(tmp_path):
    from execution import ParameterOverride, ParameterSet

    artifact = abm_artifact()
    config = ExperimentConfig(
        runs=2,
        base_seed=25,
        parameter_sets=(ParameterSet("short-horizon", (
            ParameterOverride("termination.value", 3),
        )),),
    )
    result = execute_artifact(artifact, config)
    path = save_result(result, tmp_path / "sweep.json")
    loaded = load_result(path)

    assert loaded.config.parameter_sets == config.parameter_sets
    assert loaded.config.total_runs == 2
    assert loaded.runs[0].parameter_set == "short-horizon"
    assert loaded.runs[0].parameters == {"termination.value": 3}
    assert loaded.runs[0].trace["history"][-1]["step"] == 3
