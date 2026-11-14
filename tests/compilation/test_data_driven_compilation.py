from dataclasses import replace

from compilation import CompilationParadigm, compile_profile, verify_artifact
from tests.compilation.helpers import data_driven_profile
from tests.readiness.helpers import data_project


def test_data_driven_profile_compiles_against_dataset_evidence_and_m7_readiness():
    project = data_project()
    result = compile_profile(project, data_driven_profile(project))
    assert result.is_ready, result.issues
    assert result.artifact.paradigm is CompilationParadigm.DATA_DRIVEN
    assert result.artifact.backend_name == "Data-Driven V1 / Ridge VAR(p) backend"
    assert result.native_specification.paradigm.value == "data_driven"
    assert verify_artifact(result.artifact)

def test_data_driven_compilation_rejects_unbound_dataset_reference():
    project = data_project()
    profile = data_driven_profile(project)
    profile = replace(profile, bindings=tuple(item for item in profile.bindings if item.target_path != "dataset_reference_id"))
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert any(item.code == "M8_DATASET_REFERENCE_NOT_BOUND" for item in result.issues)

def test_data_driven_compilation_rejects_wrong_dataset_reference_id():
    project = data_project()
    profile = data_driven_profile(project)
    data = dict(profile.model_data)
    data["dataset_reference_id"] = "unregistered-dataset"
    result = compile_profile(project, replace(profile, model_data=data))
    assert not result.is_ready
    assert any(item.code in {"M8_DATASET_REFERENCE_NOT_BOUND", "M8_TARGET_MODEL_INVALID"} for item in result.issues)
