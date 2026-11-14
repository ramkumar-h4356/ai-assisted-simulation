from dataclasses import replace

import pytest

from compilation import dumps_artifact, loads_artifact, verify_artifact
from execution import ExperimentConfig, ParameterOverride, ParameterSet, execute_artifact, dumps_result, loads_result
from tests.compilation.helpers import mathematical_profile
from tests.readiness.helpers import mathematical_project
from compilation import compile_profile


def math_artifact():
    project = mathematical_project()
    result = compile_profile(project, mathematical_profile(project))
    assert result.is_ready, result.issues
    return result.artifact


def test_math_artifact_runs_through_m9_and_captures_time_series():
    artifact = math_artifact()
    restored = loads_artifact(dumps_artifact(artifact))
    assert verify_artifact(restored)
    result = execute_artifact(restored)
    assert result.status.value == "completed"
    assert result.paradigm == "mathematical"
    run = result.runs[0]
    assert run.status.value == "completed"
    assert run.seed is None
    assert run.trace["solver"] == "rk4"
    assert len(run.trace["time_series"]) == 51
    assert run.trace["time_series"][0]["time"] == 0
    assert run.trace["time_series"][-1]["time"] == 5
    assert run.trace["summaries"]["supply"]["final"] < 100


def test_math_results_round_trip_through_fingerprinted_json():
    result = execute_artifact(math_artifact())
    restored = loads_result(dumps_result(result))
    assert restored.result_fingerprint == result.result_fingerprint
    assert restored.runs[0].trace == result.runs[0].trace


def test_math_parameter_sweep_changes_only_declared_parameter_values():
    artifact = math_artifact()
    config = ExperimentConfig(parameter_sets=(
        ParameterSet("slow-adjustment", (ParameterOverride("parameters[0].value", 0.02),)),
        ParameterSet("fast-adjustment", (ParameterOverride("parameters[0].value", 0.08),)),
    ))
    result = execute_artifact(artifact, config)
    assert result.status.value == "completed"
    assert len(result.runs) == 2
    assert result.runs[0].parameters == {"parameters[0].value": 0.02}
    assert result.runs[1].parameters == {"parameters[0].value": 0.08}
    assert result.runs[0].trace["summaries"]["supply"]["final"] != result.runs[1].trace["summaries"]["supply"]["final"]
    assert artifact.model_data["parameters"][0]["value"] == 0.05


def test_math_execution_rejects_random_seed_configuration():
    with pytest.raises(ValueError, match="does not consume random seeds"):
        execute_artifact(math_artifact(), ExperimentConfig(base_seed=1))


def test_math_trace_size_guard_blocks_unreasonably_large_runs():
    artifact = math_artifact()
    data = dict(artifact.model_data)
    data["time"] = {"start": 0, "end": 100, "step": 0.0001}
    # Keep the artifact fingerprint internally consistent to exercise runner validation.
    from compilation.compiler import fingerprint_artifact, fingerprint_model
    from dataclasses import replace
    candidate = replace(artifact, model_data=data, model_fingerprint=fingerprint_model(artifact.paradigm, data), artifact_fingerprint="pending")
    candidate = replace(candidate, artifact_fingerprint=fingerprint_artifact(candidate))
    with pytest.raises(ValueError, match="max_steps|trace size"):
        execute_artifact(candidate)
