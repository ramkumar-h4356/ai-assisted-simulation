from dataclasses import replace
import json

import pytest

from execution import RunStatus
from optimization import (
    MetricConstraint, OptimizationObjective, OptimizationPlan,
    SearchParameter, export_summary_csv, load_report, loads_report,
    optimize_parameters, save_report,
)
from optimization.serialization import dumps_report, loads_plan, plan_to_dict
from tests.execution.helpers import abm_artifact


def _plan(*, impossible=False):
    return OptimizationPlan(
        search_parameters=(
            SearchParameter("agents[0].attributes.trust", 0.0, 1.0),
            SearchParameter("termination.value", 1, 10),
        ),
        objective=OptimizationObjective("derived:abm:Person:contributions:sum", "maximize"),
        candidate_count=4,
        replications=2,
        search_seed=123,
        include_baseline=True,
        constraints=(MetricConstraint(
            "derived:abm:Person:contributions:sum", ">=", 1_000_000.0 if impossible else 0.0
        ),),
    )


def test_optimizer_executes_through_m9_ranks_feasible_candidates_and_preserves_provenance(tmp_path):
    artifact = abm_artifact()
    result, report = optimize_parameters(artifact, _plan(), execution_base_seed=500)

    assert len(result.runs) == 10
    assert all(run.status is RunStatus.COMPLETED for run in result.runs)
    assert report.artifact_id == artifact.artifact_id
    assert report.artifact_fingerprint == artifact.artifact_fingerprint
    assert report.experiment_id == result.experiment_id
    assert report.experiment_fingerprint == result.result_fingerprint
    assert len(report.candidates) == 5
    assert report.best_parameter_set is not None
    assert next(item for item in report.candidates if item.parameter_set == report.best_parameter_set).feasible
    assert all(item.feasible for item in report.candidates)
    assert any("not paired common-random-number" in warning for warning in report.warnings)

    report_path = save_report(report, tmp_path / "optimization.json")
    csv_path = export_summary_csv(report, tmp_path / "optimization.csv")
    loaded = load_report(report_path)
    assert loaded == report
    assert csv_path.read_text(encoding="utf-8").count("\n") == 6
    assert loads_report(dumps_report(report)) == report


def test_optimizer_records_no_feasible_candidate_when_constraint_rejects_all():
    _, report = optimize_parameters(abm_artifact(), _plan(impossible=True), execution_base_seed=7)
    assert report.best_parameter_set is None
    assert report.objective_improvement is None
    assert all(not item.feasible and item.status == "constraint_failed" for item in report.candidates)
    assert any("No candidate satisfied" in warning for warning in report.warnings)


def test_plan_json_round_trip_is_strict_and_rejects_unknown_keys():
    plan = _plan()
    assert loads_plan(json.dumps(plan_to_dict(plan))) == plan
    raw = plan_to_dict(plan)
    raw["unexpected"] = True
    with pytest.raises(ValueError, match="unknown"):
        loads_plan(json.dumps(raw))


def test_report_integrity_rejects_tampering():
    _, report = optimize_parameters(abm_artifact(), _plan(), execution_base_seed=19)
    raw = json.loads(dumps_report(report))
    raw["warnings"].append("tampered content")
    with pytest.raises(ValueError, match="fingerprint"):
        loads_report(json.dumps(raw))


def test_optimizer_uses_the_same_m9_pipeline_for_system_dynamics_artifacts():
    from compilation import compile_profile
    from tests.compilation.test_system_dynamics_compilation import system_dynamics_profile
    from tests.readiness.test_system_dynamics_readiness import system_dynamics_project

    project = system_dynamics_project()
    compiled = compile_profile(project, system_dynamics_profile(project))
    assert compiled.is_ready, compiled.issues
    plan = OptimizationPlan(
        search_parameters=(SearchParameter("parameters[0].value", 0.1, 0.5),),
        objective=OptimizationObjective("stock.infected.maximum", "maximize"),
        candidate_count=3,
        replications=1,
        search_seed=9,
        include_baseline=True,
        constraints=(MetricConstraint("stock.recovered.final", ">=", 0.0),),
    )
    result, report = optimize_parameters(compiled.artifact, plan)
    assert result.paradigm == "system_dynamics"
    assert len(result.runs) == 4
    assert report.best_parameter_set is not None
    assert all(item.feasible for item in report.candidates)
    assert any(item.objective_mean is not None for item in report.candidates)


def test_optimizer_supports_mathematical_and_data_driven_m9_backends():
    from compilation import compile_profile
    from tests.compilation.helpers import mathematical_profile, data_driven_profile
    from tests.readiness.helpers import mathematical_project, data_project

    math_project = mathematical_project()
    math_compiled = compile_profile(math_project, mathematical_profile(math_project))
    assert math_compiled.is_ready, math_compiled.issues
    math_plan = OptimizationPlan(
        search_parameters=(SearchParameter("parameters[0].value", 0.01, 0.10),),
        objective=OptimizationObjective("supply.final", "maximize"),
        candidate_count=2, replications=1, search_seed=3, include_baseline=True,
    )
    math_result, math_report = optimize_parameters(math_compiled.artifact, math_plan)
    assert math_result.paradigm == "mathematical"
    assert math_report.best_parameter_set is not None

    data_project_value = data_project()
    data_compiled = compile_profile(data_project_value, data_driven_profile(data_project_value))
    assert data_compiled.is_ready, data_compiled.issues
    data_plan = OptimizationPlan(
        search_parameters=(SearchParameter("ridge", 1e-8, 0.1),),
        objective=OptimizationObjective("rainfall.rmse", "minimize"),
        candidate_count=2, replications=1, search_seed=4, include_baseline=True,
    )
    data_result, data_report = optimize_parameters(data_compiled.artifact, data_plan)
    assert data_result.paradigm == "data_driven"
    assert data_report.best_parameter_set is not None


def test_plan_json_uses_safe_defaults_for_optional_fields():
    raw = {
        "search_parameters": [{"target_path": "termination.value", "lower": 1, "upper": 5}],
        "objective": {"metric_name": "steps_completed"},
    }
    plan = loads_plan(json.dumps(raw))
    assert plan.candidate_count == 20
    assert plan.replications == 1
    assert plan.include_baseline is True
    assert plan.objective.direction == "minimize"
