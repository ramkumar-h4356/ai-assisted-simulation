import json

import pytest

from execution import ParameterOverride, ParameterSet
from orchestration import (
    ExperimentSuitePlan, SuiteComparison, SuiteMember,
    export_summary_csv, loads_plan, loads_report, plan_to_dict, save_report,
)
from orchestration.serialization import dumps_report


def _plan():
    return ExperimentSuitePlan(
        schema_version=1,
        suite_name="Small cross-engine suite",
        members=(
            SuiteMember("first", "First model", "artifacts/first.json"),
            SuiteMember("second", "Second model", "artifacts/second.json", runs=2, base_seed=10),
        ),
        comparison=SuiteComparison(
            metric_name="outcome", unit="people",
            semantic_definition="Final number of people in the defined target state",
            direction="maximize",
        ),
    )


def test_suite_plan_round_trip_and_strict_unknown_field_validation():
    plan = _plan()
    raw = plan_to_dict(plan)
    assert loads_plan(json.dumps(raw)) == plan
    raw["unsafe_extra"] = True
    with pytest.raises(ValueError, match="unknown"):
        loads_plan(json.dumps(raw))


def test_suite_member_rejects_absolute_and_traversal_paths():
    with pytest.raises(ValueError, match="relative path"):
        SuiteMember("bad", "Bad path", "../outside.json")
    with pytest.raises(ValueError, match="relative path"):
        SuiteMember("bad", "Bad path", "C:/outside.json")


def test_suite_plan_enforces_global_m9_execution_budget():
    members = tuple(
        SuiteMember(f"m{index}", f"Model {index}", f"artifacts/{index}.json", runs=25)
        for index in range(1, 6)
    )
    with pytest.raises(ValueError, match="global M9 budget"):
        ExperimentSuitePlan(1, "Too large", members)


def test_suite_plan_supports_parameter_sets_and_checks_member_budget():
    sets = tuple(
        ParameterSet(f"p{index}", (ParameterOverride("model.value", float(index)),))
        for index in range(1, 4)
    )
    member = SuiteMember("x", "X", "x.json", runs=2, parameter_sets=sets)
    plan = ExperimentSuitePlan(
        1, "Parameter variant suite",
        (member, SuiteMember("y", "Y", "y.json")),
    )
    assert plan.total_executions == 7


def test_report_round_trip_and_tampering_rejection(tmp_path):
    from orchestration import execute_suite
    from tests.execution.helpers import abm_artifact
    from compilation import save_artifact

    root = tmp_path / "artifacts"
    root.mkdir()
    save_artifact(abm_artifact(), root / "first.json")
    save_artifact(abm_artifact(seed=9), root / "second.json")
    plan = ExperimentSuitePlan(
        1, "Round-trip suite",
        (SuiteMember("first", "First", "first.json", base_seed=1),
         SuiteMember("second", "Second", "second.json", base_seed=2)),
    )
    report = execute_suite(plan, artifact_root=root, output_dir=tmp_path / "out")
    path = save_report(report, tmp_path / "report.json")
    assert loads_report(path.read_text(encoding="utf-8")) == report
    raw = json.loads(dumps_report(report))
    raw["warnings"].append("tampered")
    with pytest.raises(ValueError, match="fingerprint"):
        loads_report(json.dumps(raw))
    csv_path = export_summary_csv(report, tmp_path / "metrics.csv")
    assert csv_path.exists() and "member_id" in csv_path.read_text(encoding="utf-8").splitlines()[0]
