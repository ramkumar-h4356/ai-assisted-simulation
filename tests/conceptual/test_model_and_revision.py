from dataclasses import FrozenInstanceError, replace

import pytest

from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus, IdeaRevision,
    append_revision, create_idea_project, revise_idea_project,
)
from tests.conceptual.helpers import make_project


def test_create_project_preserves_original_statement_and_starts_at_version_one():
    project = create_idea_project(
        "New idea", "Original words", project_id="p", revision_id="r1",
        created_at="2026-11-13T01:00:00+00:00",
    )
    assert project.original_statement == "Original words"
    assert project.current_revision.version == 1
    assert project.current_revision.parent_revision_id is None
    assert len(project.revisions) == 1


def test_revision_appends_snapshot_without_mutating_previous_revision():
    project = make_project()
    first = project.revisions[0]
    current = project.current_revision
    updated = revise_idea_project(
        project, change_summary="Add another concept", revision_id="revision-3",
        created_at="2026-11-13T01:10:00+00:00",
        concepts=current.concepts + (
            Concept("resource", "Resource", ConceptKind.RESOURCE),
        ),
    )
    assert len(updated.revisions) == 3
    assert updated.revisions[0] is first
    assert len(updated.revisions[1].concepts) == 1
    assert len(updated.current_revision.concepts) == 2
    assert updated.current_revision.parent_revision_id == current.id
    assert updated.original_statement == project.original_statement
    assert project.current_revision.id == "revision-2"


def test_revision_can_be_refined_without_rewriting_source_statement():
    project = make_project()
    refined = revise_idea_project(
        project, change_summary="Clarify theory wording", revision_id="revision-3",
    )
    assert refined.original_statement == "The original user statement must never be overwritten."


def test_revision_can_explicitly_clear_a_component_group():
    project = make_project()
    updated = revise_idea_project(
        project, change_summary="Clear concepts", concepts=(), revision_id="revision-3",
    )
    assert updated.current_revision.concepts == ()
    assert project.current_revision.concepts


def test_append_revision_rejects_non_sequential_version():
    project = make_project()
    with pytest.raises(ValueError, match="increment"):
        append_revision(project, replace(project.current_revision, id="r3", version=9, parent_revision_id="revision-2"))


def test_append_revision_rejects_wrong_parent():
    project = make_project()
    with pytest.raises(ValueError, match="parent"):
        append_revision(project, replace(project.current_revision, id="r3", version=3, parent_revision_id="revision-1"))


def test_append_revision_rejects_reused_revision_id():
    project = make_project()
    with pytest.raises(ValueError, match="already exists"):
        append_revision(project, replace(project.current_revision, version=3, parent_revision_id="revision-2"))


def test_revision_rejects_invalid_component_collection_type():
    with pytest.raises(TypeError):
        IdeaRevision("r", 1, "2026-11-13T00:00:00+00:00", "start", concepts="not-a-tuple")


def test_conceptual_elements_are_immutable():
    concept = Concept("c", "Concept")
    with pytest.raises(FrozenInstanceError):
        concept.name = "Changed"


def test_mechanism_converts_mutable_sequence_to_immutable_tuple():
    from conceptual import Mechanism
    values = ["a", "b"]
    mechanism = Mechanism("m", "Mechanism", input_concept_ids=values)
    values.append("c")
    assert mechanism.input_concept_ids == ("a", "b")


def test_mechanism_rejects_blank_concept_reference():
    from conceptual import Mechanism
    with pytest.raises(ValueError):
        Mechanism("m", "Mechanism", input_concept_ids=(" ",))


def test_open_question_requires_boolean_blocking_flag():
    from conceptual import OpenQuestion
    with pytest.raises(TypeError):
        OpenQuestion("q", "Question?", blocking=1)


def test_project_rejects_mutable_revision_list_by_copying_to_tuple():
    from conceptual import IdeaProject, IdeaRevision
    revisions = [IdeaRevision("r1", 1, "2026-11-13T00:00:00+00:00", "start")]
    project = IdeaProject("p", "Project", "Idea", "r1", revisions)
    revisions.clear()
    assert len(project.revisions) == 1
    assert isinstance(project.revisions, tuple)


def test_revision_factory_rejects_unknown_component_name():
    with pytest.raises(TypeError, match="Unknown revision component"):
        revise_idea_project(make_project(), change_summary="x", mystery=())


def test_working_statement_can_evolve_while_original_statement_is_preserved():
    project = make_project()
    updated = revise_idea_project(
        project,
        change_summary="Clarify the condition under which cooperation improves efficiency.",
        working_statement="Cooperation may improve resource allocation when local trust is sufficient and resources are scarce.",
        revision_id="revision-3",
    )
    assert updated.original_statement == project.original_statement
    assert updated.current_revision.working_statement.startswith("Cooperation may improve")
    assert project.current_revision.working_statement == project.original_statement
    assert updated.revisions[1].working_statement == project.revisions[1].working_statement


def test_revision_helpers_require_project_and_revision_types():
    with pytest.raises(TypeError, match="IdeaProject"):
        append_revision({}, object())
    with pytest.raises(TypeError, match="IdeaProject"):
        revise_idea_project({}, change_summary="no project")
