from dataclasses import replace

from compilation import (
    BindingSource, CompilationParadigm, CompilationProfile, ElementBinding,
    IssueSeverity, compile_profile, verify_artifact,
)
from readiness.models import ReadinessStatus
from simulations.abm.model import AgentModel
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.des.model import Scenario
from tests.compilation.helpers import abm_profile, des_profile
from tests.readiness.helpers import abm_project, des_project


def codes(result):
    return {issue.code for issue in result.issues}


def test_compiles_valid_des_profile_to_native_simulation_specification():
    project = des_project()
    result = compile_profile(project, des_profile(project))
    assert result.is_ready
    assert isinstance(result.native_specification, SimulationSpecification)
    assert result.native_specification.paradigm is SimulationParadigm.DISCRETE_EVENT
    assert isinstance(result.native_specification.model, Scenario)
    assert result.artifact.backend_name == "DES V1 / SimPy backend"
    assert result.artifact.m7_readiness_status == "ready_for_implementation_planning"
    assert result.artifact.paradigm_fit == "strong_fit"
    assert "M8_COMPILE_SUCCESS" in codes(result)


def test_compiles_valid_abm_profile_and_runs_semantic_validation():
    project = abm_project()
    result = compile_profile(project, abm_profile(project))
    assert result.is_ready
    assert isinstance(result.native_specification.model, AgentModel)
    assert result.native_specification.paradigm is SimulationParadigm.AGENT_BASED


def test_does_not_execute_simulation_during_compilation():
    result = compile_profile(des_project(), des_profile())
    assert result.is_ready
    assert result.native_specification is not None
    assert not hasattr(result, "execution_result")


def test_rejects_profile_for_stale_revision():
    project = des_project()
    profile = replace(des_profile(project), revision_id="old-revision")
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "M8_STALE_REVISION" in codes(result)


def test_rejects_profile_for_different_project():
    project = des_project()
    profile = replace(des_profile(project), project_id="another-project")
    result = compile_profile(project, profile)
    assert "M8_PROJECT_MISMATCH" in codes(result)


def test_rejects_assessment_only_mathematical_backend():
    project = des_project()
    profile = replace(des_profile(project), paradigm=CompilationParadigm.MATHEMATICAL)
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "M8_BACKEND_NOT_IMPLEMENTED" in codes(result)


def test_blocks_when_m7_readiness_gate_is_not_met():
    project = des_project()
    profile = replace(des_profile(project), paradigm=CompilationParadigm.AGENT_BASED)
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "M8_READINESS_GATE_NOT_MET" in codes(result)


def test_requires_at_least_one_conceptual_binding():
    project = des_project()
    profile = replace(des_profile(project), bindings=tuple(
        item for item in des_profile(project).bindings if item.source is BindingSource.USER_PARAMETER
    ))
    result = compile_profile(project, profile)
    assert "M8_NO_CONCEPTUAL_BINDINGS" in codes(result)


def test_requires_at_least_one_mechanism_binding():
    project = des_project()
    profile = replace(des_profile(project), bindings=tuple(
        item for item in des_profile(project).bindings if "service" not in item.element_ids
    ))
    result = compile_profile(project, profile)
    assert "M8_NO_MECHANISM_BINDING" in codes(result)


def test_rejects_unknown_conceptual_element_id():
    project = des_project()
    profile = replace(des_profile(project), bindings=(
        ElementBinding("resources[0]", BindingSource.CONCEPTUAL_ELEMENT, ("not-real",), "unknown"),
    ) + des_profile(project).bindings[1:])
    result = compile_profile(project, profile)
    assert "M8_UNKNOWN_SOURCE_ELEMENT" in codes(result)


def test_rejects_binding_to_missing_target_path():
    project = des_project()
    profile = replace(des_profile(project), bindings=(
        ElementBinding("jobs[99].stages[0]", BindingSource.CONCEPTUAL_ELEMENT, ("service",), "bad path"),
    ) + des_profile(project).bindings[1:])
    result = compile_profile(project, profile)
    assert "M8_BINDING_TARGET_NOT_FOUND" in codes(result)


def test_rejects_invalid_binding_target_path_syntax():
    project = des_project()
    profile = replace(des_profile(project), bindings=(
        ElementBinding("resources[*].name", BindingSource.CONCEPTUAL_ELEMENT, ("machine",), "wildcard unsupported"),
    ) + des_profile(project).bindings[1:])
    result = compile_profile(project, profile)
    assert "M8_BINDING_TARGET_NOT_FOUND" in codes(result)


def test_unmapped_concepts_are_reported_as_warnings_not_silently_ignored():
    project = abm_project()
    result = compile_profile(project, abm_profile(project))
    assert result.is_ready
    assert any(item.code == "M8_UNMAPPED_CONCEPT" and item.severity is IssueSeverity.WARNING for item in result.warnings)


def test_invalid_des_model_data_is_rejected_by_native_schema():
    project = des_project()
    profile = replace(des_profile(project), model_data={
        "name": "Bad",
        "resources": [{"name": "Machine", "capacity": 0}],
        "jobs": [{"entity_id": "job-1", "arrival_time": 0, "stages": [{"resource_name": "Machine", "service_duration": 5}]}],
    })
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "M8_TARGET_MODEL_INVALID" in codes(result)


def test_invalid_abm_behaviour_is_rejected_by_semantic_validation():
    project = abm_project()
    raw = dict(abm_profile(project).model_data)
    raw["behaviours"] = [{
        "rule_id": "bad-rule", "agent_type": "Person",
        "condition": {"type": "agent_state_is", "state": "active"},
        "actions": [{"type": "increment_attribute", "attribute": "missing", "amount": 1}],
        "probability": 1.0,
    }]
    profile = replace(abm_profile(project), model_data=raw)
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "MISSING_INCREMENT_ATTRIBUTE" in codes(result)


def test_artifact_fingerprint_is_verifiable():
    result = compile_profile(des_project(), des_profile())
    assert result.is_ready
    assert verify_artifact(result.artifact)


def test_compilation_artifact_is_revision_bound():
    project = des_project()
    result = compile_profile(project, des_profile(project))
    assert result.artifact.project_id == project.id
    assert result.artifact.revision_id == project.current_revision_id
    assert result.artifact.revision_version == project.current_revision.version


def test_user_parameters_need_explanatory_notes():
    import pytest
    with pytest.raises(ValueError, match="require a note"):
        ElementBinding("jobs[0].arrival_time", BindingSource.USER_PARAMETER, (), "")


def test_conceptual_binding_requires_element_ids():
    import pytest
    with pytest.raises(ValueError, match="require at least one"):
        ElementBinding("jobs[0]", BindingSource.CONCEPTUAL_ELEMENT, (), "")


def test_duplicate_binding_paths_rejected_at_profile_construction():
    import pytest
    project = des_project()
    profile = des_profile(project)
    with pytest.raises(ValueError, match="one binding"):
        replace(profile, bindings=profile.bindings + (profile.bindings[0],))


def test_boolean_is_not_accepted_as_numeric_des_parameter_by_target_validation():
    project = des_project()
    raw = dict(des_profile(project).model_data)
    raw["resources"] = [{"name": "Machine", "capacity": True}]
    result = compile_profile(project, replace(des_profile(project), model_data=raw))
    assert not result.is_ready
    assert "M8_TARGET_MODEL_INVALID" in codes(result)
