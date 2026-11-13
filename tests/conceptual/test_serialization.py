import json

import pytest

from conceptual import (
    IdeaSerializationError, dumps_idea_project, idea_project_from_dict,
    idea_project_to_dict, loads_idea_project, load_idea_project, save_idea_project,
)
from tests.conceptual.helpers import make_project


def test_json_round_trip_preserves_all_revision_data():
    project = make_project()
    restored = loads_idea_project(dumps_idea_project(project))
    assert restored == project
    assert restored.original_statement == project.original_statement
    assert restored.current_revision.concepts[0].origin.value == "user_defined"


def test_serialized_enums_are_strings_and_tuples_are_arrays():
    raw = idea_project_to_dict(make_project())
    concept = raw["revisions"][1]["concepts"][0]
    assert concept["kind"] == "actor"
    assert isinstance(raw["revisions"], list)
    assert isinstance(raw["revisions"][1]["concepts"], list)


def test_unknown_project_field_is_rejected():
    raw = idea_project_to_dict(make_project())
    raw["future_field"] = "unsupported"
    with pytest.raises(IdeaSerializationError, match="unsupported field"):
        idea_project_from_dict(raw)


def test_missing_project_field_is_rejected():
    raw = idea_project_to_dict(make_project())
    raw.pop("original_statement")
    with pytest.raises(IdeaSerializationError, match="missing required"):
        idea_project_from_dict(raw)


def test_invalid_enum_value_is_rejected():
    raw = idea_project_to_dict(make_project())
    raw["revisions"][1]["concepts"][0]["origin"] = "imaginary_source"
    with pytest.raises(IdeaSerializationError, match="invalid value"):
        idea_project_from_dict(raw)


def test_json_array_for_nested_objects_is_required():
    raw = idea_project_to_dict(make_project())
    raw["revisions"] = "not-an-array"
    with pytest.raises(IdeaSerializationError, match="JSON array"):
        idea_project_from_dict(raw)


def test_json_array_for_reference_tuples_is_required():
    from conceptual import Mechanism
    raw = idea_project_to_dict(make_project())
    raw["revisions"][1]["mechanisms"] = [{
        "id": "m", "name": "M", "description": "", "input_concept_ids": "not-list",
        "output_concept_ids": [], "trigger_description": "", "effect_description": "",
        "operational_definition": "", "status": "proposed",
    }]
    with pytest.raises(IdeaSerializationError, match="JSON array"):
        idea_project_from_dict(raw)


def test_invalid_json_is_reported():
    with pytest.raises(IdeaSerializationError, match="Invalid JSON"):
        loads_idea_project("{not json")


def test_save_and_load_project(tmp_path):
    path = save_idea_project(make_project(), tmp_path / "nested" / "project.json")
    assert path.exists()
    assert load_idea_project(path) == make_project()


def test_load_missing_file_reports_path(tmp_path):
    with pytest.raises(OSError, match="Could not read"):
        load_idea_project(tmp_path / "missing.json")


def test_serialization_rejects_non_finite_json_values():
    raw = idea_project_to_dict(make_project())
    raw["custom"] = float("nan")
    with pytest.raises(ValueError):
        json.dumps(raw, allow_nan=False)


def test_older_json_without_optional_working_statement_uses_default():
    raw = idea_project_to_dict(make_project())
    for revision in raw["revisions"]:
        revision.pop("working_statement", None)
    restored = idea_project_from_dict(raw)
    assert restored.current_revision.working_statement == ""


def test_included_theory_example_loads_and_retains_open_questions():
    from pathlib import Path
    from conceptual import validate_idea_project
    example_path = Path(__file__).resolve().parents[2] / "scenarios" / "conceptual" / "decentralized_resource_cooperation.json"
    project = load_idea_project(example_path)
    report = validate_idea_project(project)
    assert report.is_valid
    assert project.original_statement
    assert project.current_revision.working_statement
    assert len(project.current_revision.concepts) >= 3
    assert project.current_revision.mappings
    assert project.current_revision.open_questions
