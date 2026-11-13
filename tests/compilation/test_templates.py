from compilation import CompilationParadigm, create_profile_template
from tests.compilation.helpers import abm_profile
from tests.readiness.helpers import abm_project, des_project


def test_des_profile_template_is_revision_bound_and_intentionally_uncompiled():
    project = des_project()
    template = create_profile_template(project, CompilationParadigm.DISCRETE_EVENT)
    assert template["project_id"] == project.id
    assert template["revision_id"] == project.current_revision_id
    assert template["bindings"] == []
    assert template["model_data"]["jobs"][0]["arrival_time"] is None


def test_abm_profile_template_is_revision_bound_and_requires_user_edits():
    project = abm_project()
    template = create_profile_template(project, CompilationParadigm.AGENT_BASED)
    assert template["paradigm"] == "agent_based"
    assert template["model_data"]["termination"]["value"] is None
    assert template["bindings"] == []


def test_profile_json_schema_is_valid_json_and_declares_supported_paradigms():
    import json
    from pathlib import Path

    schema_path = Path(__file__).resolve().parents[2] / "compilation" / "profile.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["type"] == "object"
    assert schema["properties"]["paradigm"]["enum"] == ["discrete_event", "agent_based"]
