import json
from dataclasses import replace

import pytest

from execution import ExperimentConfig, execute_artifact
from experimentation import (
    AnalysisSerializationError, analyze_results, dumps_report, export_summary_csv,
    load_report, loads_report, save_report,
)
from tests.execution.helpers import abm_artifact


def _report():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=44))
    return analyze_results((result,))


def test_analysis_report_json_round_trip_and_atomic_save(tmp_path):
    report = _report()
    restored = loads_report(dumps_report(report))
    assert restored == report
    path = save_report(report, tmp_path / "analysis.json")
    assert load_report(path) == report
    assert not path.with_name(path.name + ".tmp").exists()


def test_analysis_report_rejects_tampering_and_unknown_fields():
    report = _report()
    raw = json.loads(dumps_report(report))
    raw["project_title"] = "tampered"
    with pytest.raises(AnalysisSerializationError, match="fingerprint"):
        loads_report(json.dumps(raw))
    raw = json.loads(dumps_report(report))
    raw["unexpected"] = 1
    with pytest.raises(AnalysisSerializationError, match="unknown field"):
        loads_report(json.dumps(raw))


def test_summary_csv_export_contains_metric_rows(tmp_path):
    report = _report()
    path = export_summary_csv(report, tmp_path / "summary.csv")
    text = path.read_text(encoding="utf-8")
    assert "parameter_set" in text
    assert "steps_completed" in text


def test_report_round_trip_preserves_factor_levels_and_deltas():
    from experimentation import GridFactor, run_parameter_sweep

    _, report = run_parameter_sweep(
        abm_artifact(),
        (GridFactor("termination.value", (2, 4)),),
        runs=2,
        base_seed=600,
    )
    restored = loads_report(dumps_report(report))
    assert restored == report
    assert restored.factors[0].baseline_value == 10
    assert any(level.deltas_vs_baseline for level in restored.factors[0].levels if level.value == 2)


def test_report_round_trip_preserves_categorical_metric_counts():
    from dataclasses import replace
    from execution import MetricRecord
    from execution.serialization import fingerprint_result

    result = execute_result_with_categories()
    report = analyze_results((result,))
    restored = loads_report(dumps_report(report))
    metric = next(item for item in restored.variants[0].metrics if item.metric_name == "category")
    assert {item.value: item.count for item in metric.categories} == {"A": 1, "B": 1}


def execute_result_with_categories():
    from execution import ExperimentConfig, execute_artifact
    from tests.execution.helpers import abm_artifact
    from dataclasses import replace
    from execution import MetricRecord
    from execution.serialization import fingerprint_result

    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=55))
    runs = tuple(
        replace(run, metrics=(MetricRecord("category", "A" if index == 0 else "B"),))
        for index, run in enumerate(result.runs)
    )
    result = replace(result, runs=runs, result_fingerprint="pending")
    return replace(result, result_fingerprint=fingerprint_result(result))
