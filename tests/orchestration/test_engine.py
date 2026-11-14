from compilation import compile_profile, save_artifact
from execution import load_result
from orchestration import (
    ExperimentSuitePlan, SuiteComparison, SuiteMember, execute_suite,
)
from tests.compilation.helpers import mathematical_profile
from tests.readiness.helpers import mathematical_project
from tests.execution.helpers import abm_artifact
from tests.readiness.helpers import abm_project
from tests.compilation.helpers import abm_profile
from dataclasses import replace


def _math_artifact():
    project = mathematical_project()
    result = compile_profile(project, mathematical_profile(project))
    assert result.is_ready, result.issues
    return result.artifact


def _abm_horizon_artifact(horizon):
    project = abm_project()
    profile = abm_profile(project)
    data = dict(profile.model_data)
    data["termination"] = dict(data["termination"])
    data["termination"]["value"] = horizon
    result = compile_profile(project, replace(profile, model_data=data))
    assert result.is_ready, result.issues
    return result.artifact


def test_suite_runs_heterogeneous_artifacts_through_m9_and_persists_each_result(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    save_artifact(abm_artifact(), artifacts / "abm.json")
    save_artifact(_math_artifact(), artifacts / "math.json")
    plan = ExperimentSuitePlan(
        1, "ABM and mathematical models",
        (
            SuiteMember("agents", "Agent model", "abm.json", runs=2, base_seed=200),
            SuiteMember("equations", "Equation model", "math.json", runs=1),
        ),
    )
    output = tmp_path / "results"
    report = execute_suite(plan, artifact_root=artifacts, output_dir=output)

    assert report.status == "completed"
    assert [member.paradigm for member in report.members] == ["agent_based", "mathematical"]
    assert all(member.experiment_fingerprint for member in report.members)
    assert all((output / member.result_file).exists() for member in report.members)
    assert all(load_result(output / member.result_file).result_fingerprint == member.experiment_fingerprint for member in report.members)
    assert report.ranking == ()
    assert any("No cross-member ranking" in warning for warning in report.warnings)


def test_suite_supports_all_available_non_des_m9_backends(tmp_path):
    from tests.compilation.helpers import data_driven_profile
    from tests.readiness.helpers import data_project
    from tests.compilation.test_system_dynamics_compilation import system_dynamics_profile
    from tests.readiness.test_system_dynamics_readiness import system_dynamics_project

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    data_project_value = data_project()
    data_compiled = compile_profile(data_project_value, data_driven_profile(data_project_value))
    assert data_compiled.is_ready, data_compiled.issues

    sd_project = system_dynamics_project()
    sd_compiled = compile_profile(sd_project, system_dynamics_profile(sd_project))
    assert sd_compiled.is_ready, sd_compiled.issues

    save_artifact(abm_artifact(), artifacts / "abm.json")
    save_artifact(_math_artifact(), artifacts / "math.json")
    save_artifact(data_compiled.artifact, artifacts / "data.json")
    save_artifact(sd_compiled.artifact, artifacts / "sd.json")
    plan = ExperimentSuitePlan(
        1, "Four-engine suite",
        (
            SuiteMember("abm", "Agent-based", "abm.json", base_seed=10),
            SuiteMember("math", "Mathematical", "math.json"),
            SuiteMember("data", "Data-driven", "data.json"),
            SuiteMember("sd", "System dynamics", "sd.json"),
        ),
    )
    report = execute_suite(plan, artifact_root=artifacts, output_dir=tmp_path / "out")
    assert report.status == "completed"
    assert {member.paradigm for member in report.members} == {
        "agent_based", "mathematical", "data_driven", "system_dynamics"
    }


def test_symlinked_artifact_cannot_escape_configured_artifact_root(tmp_path):
    import pytest

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (artifacts / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are not available on this platform")
    plan = ExperimentSuitePlan(
        1, "Symlink boundary suite",
        (SuiteMember("one", "One", "linked/outside.json"), SuiteMember("two", "Two", "linked/other.json")),
    )
    report = execute_suite(plan, artifact_root=artifacts, output_dir=tmp_path / "out")
    assert report.status == "failed"
    assert all(item.error_type == "ValueError" for item in report.members)
    assert all("escapes" in (item.error_message or "") for item in report.members)


def test_comparison_ranks_only_complete_groups_with_matching_numeric_metric_and_unit(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    save_artifact(_abm_horizon_artifact(3), artifacts / "short.json")
    save_artifact(_abm_horizon_artifact(7), artifacts / "long.json")
    plan = ExperimentSuitePlan(
        1, "Comparable step-count experiment",
        (
            SuiteMember("short", "Short horizon", "short.json", runs=2, base_seed=30),
            SuiteMember("long", "Long horizon", "long.json", runs=2, base_seed=40),
        ),
        comparison=SuiteComparison(
            "steps_completed", "steps",
            "Number of simulation steps completed before the configured horizon",
            "maximize",
        ),
    )
    report = execute_suite(plan, artifact_root=artifacts, output_dir=tmp_path / "out")
    assert report.status == "completed"
    assert len(report.ranking) == 2
    assert report.ranking[0].member_id == "long"
    assert report.ranking[0].mean > report.ranking[1].mean
    assert any("semantic_definition" in warning for warning in report.warnings)


def test_missing_member_is_recorded_and_other_member_continues(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    save_artifact(abm_artifact(), artifacts / "good.json")
    plan = ExperimentSuitePlan(
        1, "Partial suite",
        (
            SuiteMember("missing", "Missing artifact", "missing.json"),
            SuiteMember("good", "Good artifact", "good.json", base_seed=4),
        ),
    )
    report = execute_suite(plan, artifact_root=artifacts, output_dir=tmp_path / "out")
    assert report.status == "partial"
    assert report.members[0].status == "failed"
    assert report.members[0].error_type
    assert report.members[1].status == "completed"
    assert any("missing failed" in warning for warning in report.warnings)


def test_missing_artifact_paths_are_recorded_without_aborting_other_members(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    plan = ExperimentSuitePlan(
        1, "Safe path suite",
        (SuiteMember("one", "One", "one.json"), SuiteMember("two", "Two", "two.json")),
    )
    report = execute_suite(plan, artifact_root=artifacts, output_dir=tmp_path / "out")
    assert report.status == "failed"
    assert all("OSError" in (item.error_type or "") for item in report.members)


def test_plan_parameter_override_is_applied_by_m9_not_mutated_in_suite_layer(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    save_artifact(_abm_horizon_artifact(5), artifacts / "base.json")
    from execution import ParameterOverride, ParameterSet
    member = SuiteMember(
        "controlled", "Controlled horizon", "base.json", base_seed=15,
        parameter_sets=(ParameterSet("baseline", ()), ParameterSet("short", (ParameterOverride("termination.value", 2),))),
    )
    second = SuiteMember("replica", "Replica model", "base.json", base_seed=20)
    report = execute_suite(
        ExperimentSuitePlan(1, "Parameter-set suite", (member, second)),
        artifact_root=artifacts, output_dir=tmp_path / "out",
    )
    assert report.status == "completed"
    assert report.members[0].total_runs == 2
    assert {item.parameter_set for item in report.members[0].metrics if item.metric_name == "steps_completed"} == {"baseline", "short"}
