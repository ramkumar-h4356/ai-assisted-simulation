from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from compilation import compile_profile, save_artifact
from execution import execute_artifact, save_result
from tests.compilation.helpers import abm_profile, mathematical_profile, data_driven_profile
from tests.readiness.helpers import abm_project, mathematical_project, data_project
from tests.compilation.test_system_dynamics_compilation import system_dynamics_profile
from tests.readiness.test_system_dynamics_readiness import system_dynamics_project
from validation import (
    InvariantSpec, ValidationPlan, load_report, save_report, export_check_csv, validate_model,
)
from validation.serialization import ValidationSerializationError, loads_report


def _compiled(project, profile):
    result = compile_profile(project, profile)
    assert result.is_ready, result.issues
    return result.artifact


def test_math_validation_runs_through_m9_checks_initial_conditions_and_repeatability(tmp_path):
    artifact = _compiled(mathematical_project(), mathematical_profile())
    save_artifact(artifact, tmp_path / "math.json")
    plan = ValidationPlan(
        schema_version=1, validation_name="Math repeatability", artifact_path="math.json",
        repeatability_check=True,
        invariants=(InvariantSpec("supply-positive", "non_negative", "time_series[].values.supply"),),
    )
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    assert report.overall_status == "passed"
    assert report.paradigm == "mathematical"
    assert report.experiment_id and report.repeatability_experiment_id
    assert {item.check_id for item in report.checks} >= {
        "artifact_integrity", "model_schema", "execution_lineage", "trace_finite",
        "trace_shape", "time_order", "initial_conditions", "repeatability",
        "invariant:supply-positive:run-1",
    }
    assert all(item.status != "failed" for item in report.checks)


def test_system_dynamics_conservation_invariant_passes(tmp_path):
    # system_dynamics_profile is project-bound; compile against the same project
    project = system_dynamics_project()
    artifact = _compiled(project, system_dynamics_profile(project))
    save_artifact(artifact, tmp_path / "sir.json")
    plan = ValidationPlan(
        1, "SIR conservation", "sir.json",
        invariants=(InvariantSpec(
            "population", "conserved_sum", "time_series[].stocks",
            fields=("susceptible", "infected", "recovered"), expected_value=1000.0, tolerance=1e-7,
        ),),
    )
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    conservation = next(item for item in report.checks if item.check_id == "invariant:population:run-1")
    assert conservation.status == "passed"
    assert report.overall_status == "passed"


def test_abm_repeatability_uses_same_seeded_m9_configuration(tmp_path):
    artifact = _compiled(abm_project(), abm_profile())
    save_artifact(artifact, tmp_path / "abm.json")
    plan = ValidationPlan(1, "ABM deterministic repeat", "abm.json", repeatability_check=True)
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    check = next(item for item in report.checks if item.check_id == "repeatability")
    assert check.status == "passed"


def test_supplied_m9_result_must_match_exact_m8_artifact(tmp_path):
    artifact = _compiled(mathematical_project(), mathematical_profile())
    other_artifact = _compiled(mathematical_project(), replace(mathematical_profile(), model_data={
        **mathematical_profile().model_data,
        "time": {"start": 0.0, "end": 4.0, "step": 0.1, "unit": "days"},
    }))
    save_artifact(artifact, tmp_path / "artifact.json")
    save_result(execute_artifact(other_artifact), tmp_path / "other_result.json")
    plan = ValidationPlan(
        1, "Mismatch", "artifact.json", execution_result_path="other_result.json",
        execute_if_missing=False,
    )
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    check = next(item for item in report.checks if item.check_id == "execution_lineage")
    assert check.status == "failed"
    assert report.overall_status == "failed"


def test_validation_report_round_trip_and_csv_export(tmp_path):
    artifact = _compiled(mathematical_project(), mathematical_profile())
    save_artifact(artifact, tmp_path / "artifact.json")
    report = validate_model(ValidationPlan(1, "Round trip", "artifact.json"), artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    path = save_report(report, tmp_path / "report.json")
    restored = load_report(path)
    assert restored.report_fingerprint == report.report_fingerprint
    csv_path = export_check_csv(report, tmp_path / "checks.csv")
    assert csv_path.read_text(encoding="utf-8-sig").startswith("check_id,category,status")


def test_validation_report_tampering_is_rejected(tmp_path):
    artifact = _compiled(mathematical_project(), mathematical_profile())
    save_artifact(artifact, tmp_path / "artifact.json")
    report = validate_model(ValidationPlan(1, "Tamper", "artifact.json"), artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    raw = json.loads(json.dumps(__import__("validation.engine", fromlist=["report_to_dict"]).report_to_dict(report)))
    raw["overall_status"] = "failed"
    with pytest.raises(ValidationSerializationError, match="fingerprint"):
        loads_report(json.dumps(raw))


def test_data_driven_validation_confirms_dataset_binding(tmp_path):
    artifact = _compiled(data_project(), data_driven_profile())
    save_artifact(artifact, tmp_path / "data.json")
    report = validate_model(ValidationPlan(1, "Data validation", "data.json"), artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    initial = next(item for item in report.checks if item.check_id == "initial_conditions")
    assert initial.status == "passed"


def test_m26_report_is_a_first_class_workspace_artifact_with_exact_lineage(tmp_path):
    from conceptual import save_idea_project
    from readiness import Paradigm, assess_readiness, save_report as save_readiness_report
    from workbench import ArtifactType, WorkspaceManager, validate_artifact

    project = mathematical_project()
    artifact = _compiled(project, mathematical_profile(project))
    result = execute_artifact(artifact)
    save_artifact(artifact, tmp_path / "m8.json")
    save_result(result, tmp_path / "m9.json")
    plan = ValidationPlan(
        1, "Workspace lineage", "m8.json", execution_result_path="m9.json", execute_if_missing=False,
    )
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    report_path = save_report(report, tmp_path / "m26.json")
    assert validate_artifact(report_path, ArtifactType.VALIDATION_REPORT)["artifact_id"] == artifact.artifact_id

    idea_path = tmp_path / "idea.json"
    save_idea_project(project, idea_path)
    readiness = assess_readiness(project, selected_paradigm=Paradigm.MATHEMATICAL)
    readiness_path = tmp_path / "readiness.json"
    save_readiness_report(readiness, readiness_path)

    manager = WorkspaceManager(tmp_path / "workspaces")
    workspace = manager.create("M26 lineage", project.original_statement)
    workspace.add_artifact(idea_path, ArtifactType.IDEA_PROJECT)
    workspace.add_artifact(readiness_path, ArtifactType.READINESS_REPORT)
    workspace.add_artifact(tmp_path / "m8.json", ArtifactType.COMPILATION_ARTIFACT)
    workspace.add_artifact(tmp_path / "m9.json", ArtifactType.EXECUTION_RESULT)
    stored = workspace.add_artifact(report_path, ArtifactType.VALIDATION_REPORT)
    assert stored.metadata["artifact_fingerprint"] == artifact.artifact_fingerprint
    assert stored.metadata["result_fingerprint"] == result.result_fingerprint
    assert any(stage.key == "verification_validation" and stage.status.value == "completed" for stage in workspace.workflow_stages())


def test_invalid_native_model_is_reported_without_attempting_m9_execution(tmp_path):
    from compilation.compiler import fingerprint_artifact, fingerprint_model
    from dataclasses import replace

    artifact = _compiled(mathematical_project(), mathematical_profile())
    raw = json.loads(json.dumps(artifact.model_data))
    raw["variables"][0]["derivative"] = "__import__('os')"
    altered = replace(
        artifact, model_data=raw,
        model_fingerprint=fingerprint_model(artifact.paradigm, raw),
        artifact_fingerprint="pending",
    )
    altered = replace(altered, artifact_fingerprint=fingerprint_artifact(altered))
    save_artifact(altered, tmp_path / "invalid-but-fingerprinted.json")
    report = validate_model(
        ValidationPlan(1, "Reject unsafe expression", "invalid-but-fingerprinted.json"),
        artifact_root=tmp_path, output_dir=tmp_path / "outputs",
    )
    schema = next(item for item in report.checks if item.check_id == "model_schema")
    execution = next(item for item in report.checks if item.check_id == "execution_evidence")
    assert schema.status == "failed"
    assert execution.status == "skipped"
    assert report.experiment_id is None
    assert report.overall_status == "failed"
