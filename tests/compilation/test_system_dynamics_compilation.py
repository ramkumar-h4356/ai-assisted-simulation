from dataclasses import replace
import json
from pathlib import Path

from compilation import BindingSource, CompilationParadigm, CompilationProfile, ElementBinding, compile_profile, create_profile_template, verify_artifact
from simulations.core.specification import SimulationParadigm
from simulations.system_dynamics import SystemDynamicsModel
from tests.readiness.test_system_dynamics_readiness import system_dynamics_project


SCENARIO = Path(__file__).resolve().parents[2] / "scenarios" / "system_dynamics" / "sir_stock_flow.json"


def system_dynamics_profile(project=None):
    project = project or system_dynamics_project()
    data = json.loads(SCENARIO.read_text(encoding="utf-8"))
    return CompilationProfile(
        profile_id="sir-system-dynamics-profile",
        project_id=project.id,
        revision_id=project.current_revision_id,
        paradigm=CompilationParadigm.SYSTEM_DYNAMICS,
        model_data=data,
        bindings=(
            ElementBinding("stocks[0]", BindingSource.CONCEPTUAL_ELEMENT, ("susceptible",), "Susceptible population stock."),
            ElementBinding("stocks[1]", BindingSource.CONCEPTUAL_ELEMENT, ("infected",), "Infected population stock."),
            ElementBinding("stocks[2]", BindingSource.CONCEPTUAL_ELEMENT, ("recovered",), "Recovered population stock."),
            ElementBinding("flows[0]", BindingSource.CONCEPTUAL_ELEMENT, ("infection",), "Operational infection transfer mechanism."),
            ElementBinding("flows[1]", BindingSource.CONCEPTUAL_ELEMENT, ("recovery",), "Operational recovery transfer mechanism."),
            ElementBinding("parameters[0].value", BindingSource.USER_PARAMETER, (), "Illustrative infection-rate parameter for the demonstration."),
            ElementBinding("parameters[1].value", BindingSource.USER_PARAMETER, (), "Illustrative recovery-rate parameter for the demonstration."),
        ),
    )


def test_system_dynamics_compiles_with_readiness_and_provenance():
    project = system_dynamics_project()
    result = compile_profile(project, system_dynamics_profile(project))
    assert result.is_ready, result.issues
    assert result.artifact.paradigm is CompilationParadigm.SYSTEM_DYNAMICS
    assert result.artifact.backend_name == "System Dynamics V1 / Stock-and-Flow backend"
    assert result.native_specification.paradigm is SimulationParadigm.SYSTEM_DYNAMICS
    assert isinstance(result.native_specification.model, SystemDynamicsModel)
    assert verify_artifact(result.artifact)


def test_system_dynamics_requires_a_bound_stock_flow_mechanism_or_relationship():
    project = system_dynamics_project()
    profile = system_dynamics_profile(project)
    bindings = tuple(item for item in profile.bindings if item.target_path not in {"flows[0]", "flows[1]"})
    result = compile_profile(project, replace(profile, bindings=bindings))
    assert not result.is_ready
    assert "M8_NO_STOCK_FLOW_BINDING" in {item.code for item in result.errors}


def test_system_dynamics_rejects_unknown_flow_expression_names():
    project = system_dynamics_project()
    profile = system_dynamics_profile(project)
    model_data = dict(profile.model_data)
    model_data["flows"] = [dict(item) for item in model_data["flows"]]
    model_data["flows"][0]["rate_expression"] = "unknown_rate * susceptible"
    result = compile_profile(project, replace(profile, model_data=model_data))
    assert not result.is_ready
    assert "M8_TARGET_MODEL_INVALID" in {item.code for item in result.errors}


def test_system_dynamics_profile_template_exposes_stock_flow_contract():
    project = system_dynamics_project()
    template = create_profile_template(project, CompilationParadigm.SYSTEM_DYNAMICS)
    assert template["paradigm"] == "system_dynamics"
    assert template["model_data"]["stocks"]
    assert template["model_data"]["flows"]
