import json

import pytest

from tests.execution.helpers import abm_artifact
from uncertainty import (
    RobustnessCriterion, UncertainParameter, UncertaintyPlan,
    UncertaintySerializationError, export_summary_csv, load_plan, load_report,
    loads_report, plan_from_dict, report_to_dict, run_uncertainty_analysis,
    save_report,
)


def make_report():
    return run_uncertainty_analysis(
        abm_artifact(),
        UncertaintyPlan(
            6, 17,
            (UncertainParameter("agents[0].attributes.trust", "triangular", 0.0, 1.0, 0.7),),
            (RobustnessCriterion("steps_completed", ">=", 5.0),),
        ),
        execution_base_seed=90,
    )[1]


def test_m11_report_json_round_trip_and_fingerprint(tmp_path):
    report = make_report()
    destination = tmp_path / "m11.json"
    save_report(report, destination)
    restored = load_report(destination)
    assert restored == report
    assert loads_report(destination.read_text(encoding="utf-8")) == report


def test_m11_report_tampering_is_detected():
    raw = report_to_dict(make_report())
    raw["sample_count"] += 1
    with pytest.raises(UncertaintySerializationError, match="fingerprint"):
        loads_report(json.dumps(raw))


def test_m11_plan_parser_is_strict_and_loads_file(tmp_path):
    raw = {
        "sample_count": 5,
        "sampling_seed": 9,
        "parameters": [{"target_path": "x", "distribution": "uniform", "lower": 0.0, "upper": 1.0, "mode": None}],
        "criteria": [],
    }
    plan = plan_from_dict(raw)
    assert plan == UncertaintyPlan(5, 9, (UncertainParameter("x", "uniform", 0.0, 1.0),), ())
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_plan(path) == plan
    raw["extra"] = True
    with pytest.raises(UncertaintySerializationError, match="unknown field"):
        plan_from_dict(raw)


def test_m11_plan_allows_omitted_optional_criteria_mode_and_upper_threshold():
    raw = {
        "sample_count": 5,
        "sampling_seed": 9,
        "parameters": [{"target_path": "x", "distribution": "uniform", "lower": 0.0, "upper": 1.0}],
    }
    plan = plan_from_dict(raw)
    assert plan.criteria == ()
    assert plan.parameters[0].mode is None


def test_m11_csv_export_includes_distributions_sensitivity_and_robustness(tmp_path):
    report = make_report()
    path = tmp_path / "m11.csv"
    export_summary_csv(report, path)
    content = path.read_text(encoding="utf-8")
    assert "metric_distribution" in content
    assert "sensitivity" in content
    assert "robustness_criterion" in content
