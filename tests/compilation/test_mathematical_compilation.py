from dataclasses import replace

from compilation import CompilationParadigm, compile_profile
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.mathematical import MathematicalModel
from tests.compilation.helpers import mathematical_profile
from tests.readiness.helpers import mathematical_project


def test_compiles_math_profile_with_quantitative_relationship_binding():
    project = mathematical_project()
    result = compile_profile(project, mathematical_profile(project))
    assert result.is_ready, result.issues
    assert result.native_specification.paradigm is SimulationParadigm.MATHEMATICAL
    assert isinstance(result.native_specification, SimulationSpecification)
    assert isinstance(result.native_specification.model, MathematicalModel)
    assert result.artifact.paradigm is CompilationParadigm.MATHEMATICAL
    assert result.artifact.backend_name == "Mathematical V1 / Fixed-Step ODE backend"
    assert result.artifact.m7_readiness_status == "ready_for_implementation_planning"


def test_math_compilation_requires_a_bound_governing_relationship_or_mechanism():
    project = mathematical_project()
    profile = mathematical_profile(project)
    profile = replace(profile, bindings=tuple(item for item in profile.bindings if "balance" not in item.element_ids))
    result = compile_profile(project, profile)
    assert not result.is_ready
    assert "M8_NO_GOVERNING_RELATION_BINDING" in {item.code for item in result.errors}


def test_math_compilation_rejects_expression_with_unknown_identifier():
    project = mathematical_project()
    profile = mathematical_profile(project)
    data = dict(profile.model_data)
    variables = [dict(item) for item in data["variables"]]
    variables[0]["derivative"] = "missing_rate * supply"
    data["variables"] = variables
    result = compile_profile(project, replace(profile, model_data=data))
    assert not result.is_ready
    assert "M8_TARGET_MODEL_INVALID" in {item.code for item in result.errors}
