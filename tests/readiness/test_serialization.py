import json

import pytest

from readiness import (
    Paradigm, ReadinessSerializationError, assess_readiness, dumps_report,
    load_report, loads_report, report_to_dict, save_report,
)
from tests.readiness.helpers import des_project


def test_report_json_round_trip_preserves_assessments_and_clarifications():
    report = assess_readiness(des_project(), selected_paradigm=Paradigm.DISCRETE_EVENT)
    restored = loads_report(dumps_report(report))
    assert restored == report
    assert restored.assessment_for(Paradigm.DISCRETE_EVENT).fit == report.assessment_for(Paradigm.DISCRETE_EVENT).fit


def test_report_can_be_saved_and_loaded(tmp_path):
    report = assess_readiness(des_project())
    path = save_report(report, tmp_path / "nested" / "report.json")
    assert path.exists()
    assert load_report(path) == report


def test_unknown_top_level_fields_are_rejected():
    raw = report_to_dict(assess_readiness(des_project()))
    raw["unrecognized"] = True
    with pytest.raises(ReadinessSerializationError, match="unknown field"):
        loads_report(json.dumps(raw))


def test_unknown_nested_fields_are_rejected():
    raw = report_to_dict(assess_readiness(des_project()))
    raw["paradigm_assessments"][0]["surprise"] = 1
    with pytest.raises(ReadinessSerializationError, match="unknown field"):
        loads_report(json.dumps(raw))


def test_invalid_enum_is_rejected():
    raw = report_to_dict(assess_readiness(des_project()))
    raw["status"] = "certainly_true"
    with pytest.raises(ReadinessSerializationError, match="invalid"):
        loads_report(json.dumps(raw))


def test_malformed_json_is_rejected():
    with pytest.raises(ReadinessSerializationError, match="Invalid readiness JSON"):
        loads_report("{nope")
