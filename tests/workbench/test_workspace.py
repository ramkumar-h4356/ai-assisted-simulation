from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from conceptual import save_idea_project
from readiness import assess_readiness, save_report
from workbench import (
    ArtifactType, WorkspaceConflictError, WorkspaceError, WorkspaceIntegrityError,
    WorkspaceManager, create_builtin_registry,
)
from tests.readiness.helpers import abm_project, des_project


def _create_project_file(tmp_path: Path):
    project = des_project()
    source = tmp_path / "idea_project.json"
    save_idea_project(project, source)
    return project, source


def test_create_workspace_import_idea_project_and_reopen(tmp_path):
    project, source = _create_project_file(tmp_path)
    manager = WorkspaceManager(tmp_path / "workspaces")
    workspace = manager.create("Hospital Flow", project.original_statement)

    record = workspace.add_artifact(source, ArtifactType.IDEA_PROJECT)
    reopened = manager.open(workspace.workspace_id)

    assert record.metadata["project_id"] == project.id
    assert reopened.manifest.idea_project_id == project.id
    assert reopened.artifact_path(record.artifact_id).read_bytes() == source.read_bytes()
    assert reopened.verify_artifacts()[0].valid
    assert reopened.workflow_stages()[0].status.value == "completed"
    assert reopened.workflow_stages()[1].status.value == "completed"


def test_rejects_idea_project_with_different_original_statement(tmp_path):
    project, source = _create_project_file(tmp_path)
    workspace = WorkspaceManager(tmp_path / "workspaces").create("Different", "A different original idea")

    with pytest.raises(WorkspaceConflictError, match="original_statement"):
        workspace.add_artifact(source, ArtifactType.IDEA_PROJECT)


def test_rejects_project_scoped_artifact_before_conceptual_project(tmp_path):
    project, _source = _create_project_file(tmp_path)
    readiness = assess_readiness(project)
    readiness_path = tmp_path / "readiness.json"
    save_report(readiness, readiness_path)
    workspace = WorkspaceManager(tmp_path / "workspaces").create("No model yet", project.original_statement)

    with pytest.raises(WorkspaceConflictError, match="conceptual idea project"):
        workspace.add_artifact(readiness_path, ArtifactType.READINESS_REPORT)


def test_readiness_artifact_must_match_workspace_project(tmp_path):
    project, source = _create_project_file(tmp_path)
    other = replace(abm_project(), id="idea-other")
    report = assess_readiness(other)
    readiness_path = tmp_path / "readiness.json"
    save_report(report, readiness_path)
    workspace = WorkspaceManager(tmp_path / "workspaces").create("Hospital Flow", project.original_statement)
    workspace.add_artifact(source, ArtifactType.IDEA_PROJECT)

    with pytest.raises(WorkspaceConflictError, match="does not match workspace"):
        workspace.add_artifact(readiness_path, ArtifactType.READINESS_REPORT)


def test_workspace_export_import_is_portable_and_integrity_checked(tmp_path):
    project, source = _create_project_file(tmp_path)
    manager = WorkspaceManager(tmp_path / "workspaces")
    workspace = manager.create("Portable Example", project.original_statement)
    workspace.add_artifact(source, ArtifactType.IDEA_PROJECT)
    archive = workspace.export_zip(tmp_path / "portable_workspace.zip")

    imported = WorkspaceManager(tmp_path / "imported").import_zip(archive)

    assert imported.workspace_id == workspace.workspace_id
    assert imported.manifest.title == "Portable Example"
    assert len(imported.artifacts()) == 1
    assert all(item.valid for item in imported.verify_artifacts())


def test_detects_artifact_tampering_and_refuses_export(tmp_path):
    project, source = _create_project_file(tmp_path)
    workspace = WorkspaceManager(tmp_path / "workspaces").create("Tamper Test", project.original_statement)
    record = workspace.add_artifact(source, ArtifactType.IDEA_PROJECT)
    stored = workspace.artifact_path(record.artifact_id)
    stored.write_text("tampered", encoding="utf-8")

    verification = workspace.verify_artifacts()
    assert not verification[0].valid
    with pytest.raises(WorkspaceIntegrityError, match="invalid artifacts"):
        workspace.export_zip(tmp_path / "should_not_exist.zip")


def test_manifest_rejects_unknown_fields_and_duplicate_artifact_ids():
    from workbench.serialization import loads_manifest, WorkspaceSerializationError

    base = {
        "schema_version": 1, "workspace_id": "ws-0123456789ab", "title": "T",
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
        "original_idea": "Idea", "idea_project_id": None, "artifacts": [], "activity": [],
    }
    with pytest.raises(WorkspaceSerializationError, match="unknown field"):
        loads_manifest(json.dumps({**base, "unexpected": True}))


def test_builtin_extension_registry_contains_working_des_and_abm_adapters():
    registry = create_builtin_registry()
    assert {item.paradigm for item in registry.descriptors} == {"discrete_event", "agent_based"}
    assert registry.get("builtin.des.v1").descriptor.model_schema_versions == ("m8-des-v1",)
    assert registry.for_paradigm("agent_based").descriptor.extension_id == "builtin.abm.v1"


def test_extension_registry_rejects_duplicate_paradigms():
    from workbench import ExtensionDescriptor, ExtensionRegistry

    class FakeExtension:
        descriptor = ExtensionDescriptor(
            extension_id="fake.one", display_name="Fake", version="1.0", paradigm="custom",
            model_schema_versions=("1",),
            capabilities=("validate", "compile", "execute", "serialize_result", "validate_result"),
        )

        def validate(self, *args): pass
        def compile(self, *args): pass
        def execute(self, *args): pass
        def serialize_result(self, *args): return b"{}"
        def validate_result(self, *args): return {}

    registry = ExtensionRegistry()
    registry.register(FakeExtension())
    with pytest.raises(ValueError, match="already registered for paradigm"):
        other = FakeExtension()
        other.descriptor = ExtensionDescriptor(
            extension_id="fake.two", display_name="Fake 2", version="1.0", paradigm="custom",
            model_schema_versions=("1",),
            capabilities=("validate", "compile", "execute", "serialize_result", "validate_result"),
        )
        registry.register(other)


def test_end_to_end_abm_workflow_runs_inside_one_workspace(tmp_path):
    from compilation import save_profile
    from conceptual import save_idea_project
    from tests.compilation.helpers import abm_profile
    from tests.readiness.helpers import abm_project
    from workbench import WorkbenchService

    project = abm_project()
    manager = WorkspaceManager(tmp_path / "workspaces")
    workspace = manager.create("Community Cooperation", project.original_statement)
    idea_path = tmp_path / "idea_project.json"
    save_idea_project(project, idea_path)
    workspace.add_artifact(idea_path, ArtifactType.IDEA_PROJECT)

    service = WorkbenchService(workspace)
    readiness, readiness_record = service.assess("agent_based")
    assert readiness.can_begin_implementation_planning

    profile_path = tmp_path / "abm_profile.json"
    save_profile(abm_profile(project), profile_path)
    profile_record = workspace.add_artifact(profile_path, ArtifactType.COMPILATION_PROFILE)
    compilation, compilation_record = service.compile(profile_record.artifact_id)
    assert compilation.is_ready
    assert compilation_record is not None

    plan_path = tmp_path / "uncertainty_plan.json"
    plan_path.write_text(json.dumps({
        "sample_count": 5,
        "sampling_seed": 19,
        "parameters": [{
            "target_path": "agents[0].attributes.trust",
            "distribution": "uniform", "lower": 0.0, "upper": 1.0,
        }],
    }), encoding="utf-8")
    plan_record = workspace.add_artifact(plan_path, ArtifactType.UNCERTAINTY_PLAN)
    result, uncertainty_report, result_record, uncertainty_record = service.uncertainty_analysis(
        compilation_record.artifact_id, plan_record.artifact_id, execution_base_seed=20,
    )
    analysis_report, analysis_record = service.analyze_result(result_record.artifact_id)
    bundle, bundle_record, html_record = service.build_visualization(
        result_record.artifact_id,
        analysis_artifact_id=analysis_record.artifact_id,
        uncertainty_artifact_id=uncertainty_record.artifact_id,
    )

    assert result.status.value == "completed"
    assert uncertainty_report.experiment_id == result.experiment_id
    assert analysis_report.input_experiment_ids == (result.experiment_id,)
    assert bundle.experiment_id == result.experiment_id
    assert html_record.relative_path.endswith(".html")
    assert len(workspace.artifacts()) == 10
    assert all(item.valid for item in service.verify())
    assert workspace.overview().stages[-1].status.value == "completed"

    archive = workspace.export_zip(tmp_path / "complete_abm_workspace.zip")
    imported = WorkspaceManager(tmp_path / "restored").import_zip(archive)
    assert len(imported.artifacts()) == 10
    assert all(item.valid for item in imported.verify_artifacts())
    assert imported.workflow_stages()[-1].status.value == "completed"


def test_original_idea_copy_is_checked_when_workspace_is_reopened(tmp_path):
    manager = WorkspaceManager(tmp_path / "workspaces")
    workspace = manager.create("Immutable source", "The original statement remains unchanged.")
    (workspace.directory / "original_idea.md").write_text("silently edited\n", encoding="utf-8")

    with pytest.raises(WorkspaceIntegrityError, match="immutable original idea"):
        manager.open(workspace.workspace_id)


def test_zip_import_rejects_traversal_entries(tmp_path):
    import zipfile

    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("workspace-root/workspace.json", "{}")
        output.writestr("workspace-root/../outside.txt", "not allowed")

    with pytest.raises(WorkspaceError, match="unsafe path"):
        WorkspaceManager(tmp_path / "imported").import_zip(archive)
    assert not (tmp_path / "outside.txt").exists()


def test_zip_import_rejects_duplicate_normalized_paths(tmp_path):
    import zipfile

    archive = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("workspace-root/file.txt", "first")
        output.writestr("workspace-root/file.txt", "second")

    with pytest.raises(WorkspaceError, match="duplicate paths"):
        WorkspaceManager(tmp_path / "imported").import_zip(archive)


def test_m6_formalization_runs_inside_workspace_and_persists_project_and_session(tmp_path):
    from idea_assistant.service import IdeaAssistantService
    from tests.idea_assistant.helpers import draft_copy
    from workbench import WorkbenchService

    class StubInterpreter:
        def interpret(self, request, *, knowledge_context=()):
            return draft_copy()

        def refine(self, request, current_draft, clarification_history, *, knowledge_context=()):
            return draft_copy()

    idea = "The community members access a shared resource."
    workspace = WorkspaceManager(tmp_path / "workspaces").create("M6 integrated", idea)
    service = WorkbenchService(workspace)
    result, project_record, session_record = service.formalize_idea(interpreter=StubInterpreter())

    assert result.project.original_statement == idea
    assert result.validation_report.is_valid
    assert project_record.artifact_type == ArtifactType.IDEA_PROJECT.value
    assert session_record.artifact_type == ArtifactType.IDEA_SESSION.value
    assert workspace.manifest.idea_project_id == result.project.id
    assert workspace.workflow_stages()[1].status.value == "completed"
    assert workspace.workflow_stages()[2].status.value == "completed"
    assert service.current_idea_project() == result.project

    with pytest.raises(WorkspaceConflictError, match="already has a conceptual project"):
        service.formalize_idea(interpreter=StubInterpreter())


def test_m5_mapping_runs_inside_workspace_and_preserves_review_history(tmp_path):
    from conceptual import load_idea_project, save_idea_project
    from conceptual.model import EvidenceReference, MappingType, ReferenceType, ReviewStatus
    from knowledge import KnowledgeBase, KnowledgeDocument, save_knowledge_base
    from workbench import WorkbenchService

    project = abm_project()
    idea_path = tmp_path / "idea.json"
    save_idea_project(project, idea_path)
    knowledge_base = KnowledgeBase(
        "kb-workbench", "Workbench test corpus", (
            KnowledgeDocument(
                id="doc-resource-governance", title="Governing shared resources",
                content="Community members cooperate to govern access to a shared resource through agreed allocation rules.",
                reference=EvidenceReference(
                    id="ref-resource-governance", title="Shared resource governance",
                    reference_type=ReferenceType.ARTICLE, uri="https://example.org/resource-governance",
                    publisher="Example Research Group", published_year=2024,
                ),
                domains=("commons",), keywords=("shared resource", "community", "cooperation"),
                concept_labels=("collective resource governance",),
            ),
        ),
    )
    knowledge_path = tmp_path / "knowledge.json"
    save_knowledge_base(knowledge_base, knowledge_path)

    workspace = WorkspaceManager(tmp_path / "workspaces").create("M5 integrated", project.original_statement)
    workspace.add_artifact(idea_path, ArtifactType.IDEA_PROJECT)
    knowledge_record = workspace.add_artifact(knowledge_path, ArtifactType.KNOWLEDGE_BASE)
    service = WorkbenchService(workspace)

    candidates = service.suggest_mappings("resource", query="shared resource community cooperation")
    assert candidates
    updated, mapping_record = service.record_mapping_candidate(candidates[0], mapping_type=MappingType.ANALOGOUS)
    mapping = updated.current_revision.mappings[-1]
    assert mapping.review_status is ReviewStatus.UNREVIEWED
    assert mapping_record.metadata["mapping_count"] == 1
    assert workspace.workflow_stages()[3].status.value == "completed"

    reviewed, reviewed_record = service.review_mapping(
        mapping.id, ReviewStatus.ACCEPTED, reviewer_note="Reviewed against the cited source."
    )
    assert reviewed.current_revision.version == updated.current_revision.version + 1
    assert reviewed.current_revision.mappings[-1].review_status is ReviewStatus.ACCEPTED
    assert len(reviewed.revisions) == len(project.revisions) + 2
    assert reviewed_record.metadata["mapping_count"] == 1
    assert workspace.artifact_path(knowledge_record.artifact_id).is_file()
    assert all(item.valid for item in service.verify())
