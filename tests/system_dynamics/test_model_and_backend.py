from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.system_dynamics import (
    SystemDynamicsBackend, SystemDynamicsModelError, system_dynamics_model_from_dict,
)


SCENARIO = Path(__file__).resolve().parents[2] / "scenarios" / "system_dynamics" / "sir_stock_flow.json"


def sir_model_data():
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


def run_model(raw):
    model = system_dynamics_model_from_dict(raw)
    return SystemDynamicsBackend().execute(
        SimulationSpecification(model.name, SimulationParadigm.SYSTEM_DYNAMICS, model)
    ).native_result


def test_sir_stock_flow_conserves_population_and_records_time_series():
    result = run_model(sir_model_data())
    assert len(result.snapshots) == 401
    final = result.snapshots[-1]
    assert final.time == 80.0
    assert sum(final.stocks.values()) == pytest.approx(1000.0, abs=1e-8)
    assert final.stocks["infected"] < 10.0
    assert final.stocks["recovered"] > 900.0
    assert result.total_flow["infection"] > 0
    assert result.total_flow["recovery"] > 0
    assert final.auxiliaries["population"] == pytest.approx(1000.0)


def test_transfer_flow_conserves_total_stock_with_heun():
    raw = {
        "schema_version": 1, "name": "Warehouse transfer",
        "time": {"start": 0, "end": 10, "step": 0.25, "unit": "days"},
        "solver": "heun",
        "stocks": [
            {"name": "warehouse", "initial_value": 100, "minimum": 0, "unit": "units"},
            {"name": "store", "initial_value": 0, "minimum": 0, "unit": "units"},
        ],
        "flows": [{"name": "shipment", "source_stock": "warehouse", "target_stock": "store", "rate_expression": "rate * warehouse", "unit": "units/day"}],
        "parameters": [{"name": "rate", "value": 0.1, "unit": "1/day"}],
        "auxiliaries": [],
    }
    result = run_model(raw)
    assert result.snapshots[-1].stocks["warehouse"] == pytest.approx(100 * math.exp(-1.0), rel=2e-3)
    assert result.snapshots[-1].stocks["warehouse"] + result.snapshots[-1].stocks["store"] == pytest.approx(100.0, abs=1e-8)


def test_euler_solver_is_supported():
    raw = {
        "name": "External inflow", "time": {"start": 0, "end": 2, "step": 1},
        "solver": "euler", "stocks": [{"name": "water", "initial_value": 1}],
        "flows": [{"name": "rain", "source_stock": None, "target_stock": "water", "rate_expression": "2"}],
    }
    result = run_model(raw)
    assert [item.stocks["water"] for item in result.snapshots] == [1.0, 3.0, 5.0]


def test_rejects_circular_auxiliary_equations():
    raw = sir_model_data()
    raw["auxiliaries"] = [
        {"name": "a", "expression": "b + 1"},
        {"name": "b", "expression": "a + 1"},
    ]
    with pytest.raises(SystemDynamicsModelError, match="circular dependency"):
        system_dynamics_model_from_dict(raw)


@pytest.mark.parametrize("expression", ["__import__('os')", "stocks[0]", "susceptible.__class__", "unknown + 1"])
def test_rejects_unsafe_or_unknown_expressions(expression):
    raw = sir_model_data()
    raw["flows"][0]["rate_expression"] = expression
    with pytest.raises(ValueError):
        system_dynamics_model_from_dict(raw)


def test_rejects_negative_flow_rate_at_execution():
    raw = {
        "name": "Bad drain", "time": {"start": 0, "end": 1, "step": 1},
        "stocks": [{"name": "water", "initial_value": 5}],
        "flows": [{"name": "bad", "source_stock": "water", "target_stock": None, "rate_expression": "-1"}],
    }
    with pytest.raises(SystemDynamicsModelError, match="non-negative"):
        run_model(raw)


def test_stock_minimum_is_enforced_without_silent_clipping():
    raw = {
        "name": "Overdraw", "time": {"start": 0, "end": 1, "step": 1},
        "stocks": [{"name": "water", "initial_value": 1, "minimum": 0}],
        "flows": [{"name": "drain", "source_stock": "water", "target_stock": None, "rate_expression": "2"}],
    }
    with pytest.raises(SystemDynamicsModelError, match="fell below its minimum"):
        run_model(raw)


def test_rejects_wrong_paradigm_and_bad_time_limits():
    model = system_dynamics_model_from_dict(sir_model_data())
    with pytest.raises(ValueError, match="requires a system_dynamics"):
        SystemDynamicsBackend().execute(SimulationSpecification("wrong", SimulationParadigm.MATHEMATICAL, model))
    raw = sir_model_data()
    raw["time"]["step"] = 0
    with pytest.raises(SystemDynamicsModelError, match="positive"):
        system_dynamics_model_from_dict(raw)
