from dataclasses import replace

import pytest

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.data_driven import (
    DataDrivenBackend, DataDrivenModelError, data_driven_model_from_dict,
)


def make_data():
    x, y = 5.0, 3.0
    rows = []
    for time in range(60):
        rows.append({"time": float(time), "x": x, "y": y})
        x, y = 0.72 * x + 0.08 * y + 1.5, 0.18 * x + 0.68 * y + 0.8
    return {
        "schema_version": 1, "name": "Coupled synthetic series",
        "dataset_reference_id": "dataset-1", "time_field": "time", "time_unit": "days",
        "variables": ["x", "y"], "observations": rows, "lag_order": 1,
        "train_fraction": 0.75, "forecast_horizon": 8, "ridge": 1e-6,
    }

def run(raw=None):
    raw = raw or make_data()
    return DataDrivenBackend().execute(SimulationSpecification("VAR test", SimulationParadigm.DATA_DRIVEN, raw))

def test_model_parser_accepts_valid_regular_multivariate_series():
    model = data_driven_model_from_dict(make_data())
    assert model.variables == ("x", "y")
    assert model.training_samples == 44
    assert model.holdout_samples == 15
    assert model.time_step == 1.0

def test_var_backend_fits_holdout_and_recursive_forecast():
    result = run()
    execution = result.native_result
    assert result.paradigm is SimulationParadigm.DATA_DRIVEN
    assert execution.method == "ridge_var"
    assert execution.training_samples == 44
    assert execution.holdout_samples == 15
    assert execution.evaluation_strategy == "one_step_walk_forward_with_observed_history"
    assert len(execution.holdout_predictions) == 15
    assert len(execution.forecast) == 8
    assert execution.forecast[0].time == 60.0
    assert execution.forecast[-1].time == 67.0
    assert execution.evaluation_metrics["x"]["rmse"] < 0.05
    assert execution.evaluation_metrics["y"]["rmse"] < 0.05
    assert result.metrics

def test_backend_is_deterministic():
    first = run().native_result
    second = run().native_result
    assert first.coefficients == second.coefficients
    assert first.holdout_predictions == second.holdout_predictions
    assert first.forecast == second.forecast

def test_rejects_irregular_time_series():
    raw = make_data()
    raw["observations"][10]["time"] += 0.5
    with pytest.raises(DataDrivenModelError, match="regularly spaced"):
        data_driven_model_from_dict(raw)

def test_rejects_non_finite_values_and_missing_columns():
    raw = make_data()
    raw["observations"][3]["x"] = float("nan")
    with pytest.raises(DataDrivenModelError, match="finite"):
        data_driven_model_from_dict(raw)
    raw = make_data()
    del raw["observations"][3]["y"]
    with pytest.raises(DataDrivenModelError, match="missing field"):
        data_driven_model_from_dict(raw)

def test_rejects_unsupported_variable_explosion_and_bad_controls():
    raw = make_data()
    raw["lag_order"] = 9
    with pytest.raises(DataDrivenModelError, match="lag_order"):
        data_driven_model_from_dict(raw)
    raw = make_data()
    raw["train_fraction"] = 0.2
    with pytest.raises(DataDrivenModelError, match="train_fraction"):
        data_driven_model_from_dict(raw)

def test_rejects_model_for_another_paradigm():
    specification = SimulationSpecification("wrong", SimulationParadigm.MATHEMATICAL, make_data())
    with pytest.raises(ValueError, match="data_driven"):
        DataDrivenBackend().execute(specification)


def test_csv_import_selects_columns_and_reuses_the_model_validator(tmp_path):
    from simulations.data_driven import load_csv_model_data

    source = tmp_path / "series.csv"
    x, y = 5.0, 3.0
    lines = ["time,x,y,unused"]
    for time in range(60):
        lines.append(f"{time},{x},{y},ignored")
        x, y = 0.72 * x + 0.08 * y + 1.5, 0.18 * x + 0.68 * y + 0.8
    source.write_text("\n".join(lines), encoding="utf-8")
    model_data = load_csv_model_data(
        source, name="CSV series", dataset_reference_id="dataset-1",
        time_field="time", time_unit="days", variables=("x", "y"),
        forecast_horizon=3,
    )
    assert len(model_data["observations"]) == 60
    assert set(model_data["observations"][0]) == {"time", "x", "y"}
    assert data_driven_model_from_dict(model_data).forecast_horizon == 3


def test_csv_import_rejects_missing_fields_and_non_numeric_values(tmp_path):
    from simulations.data_driven import load_csv_model_data

    source = tmp_path / "bad.csv"
    source.write_text("time,x\n0,1\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required column"):
        load_csv_model_data(
            source, name="bad", dataset_reference_id="dataset", time_field="time",
            time_unit="day", variables=("x", "y"),
        )


def test_rejects_boolean_schema_version():
    raw = make_data()
    raw["schema_version"] = True
    with pytest.raises(DataDrivenModelError, match="schema_version"):
        data_driven_model_from_dict(raw)


def test_csv_import_rejects_duplicate_or_invalid_selected_column_names(tmp_path):
    from simulations.data_driven import load_csv_model_data

    source = tmp_path / "series.csv"
    source.write_text("time,x,y\n" + "\n".join(f"{i},{i},{i + 1}" for i in range(60)), encoding="utf-8")
    common = dict(
        path=source, name="series", dataset_reference_id="dataset-1",
        time_field="time", time_unit="days",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_csv_model_data(**common, variables=("x", "x"))
    with pytest.raises(ValueError, match="column-name strings"):
        load_csv_model_data(**common, variables=("x", []))
