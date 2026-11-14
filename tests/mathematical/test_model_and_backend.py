import math

import pytest

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.mathematical import MathematicalBackend, MathematicalModelError, mathematical_model_from_dict


def exponential_model(solver="rk4"):
    return {
        "schema_version": 1,
        "name": "Exponential growth",
        "time": {"start": 0, "end": 2, "step": 0.1, "unit": "time"},
        "solver": solver,
        "variables": [
            {"name": "population", "initial_value": 2, "derivative": "growth_rate * population", "unit": "people"}
        ],
        "parameters": [{"name": "growth_rate", "value": 0.5, "unit": "1/time"}],
    }


def execute(data):
    model = mathematical_model_from_dict(data)
    spec = SimulationSpecification(model.name, SimulationParadigm.MATHEMATICAL, model)
    return MathematicalBackend().execute(spec)


def test_rk4_solves_exponential_growth_with_expected_accuracy():
    result = execute(exponential_model())
    native = result.native_result
    assert result.paradigm is SimulationParadigm.MATHEMATICAL
    assert native.solver == "rk4"
    assert native.steps == 20
    assert native.snapshots[0].values["population"] == 2.0
    assert native.snapshots[-1].time == 2.0
    assert native.snapshots[-1].values["population"] == pytest.approx(2 * math.exp(1), rel=1e-7)
    assert result.backend_name == "Mathematical V1 / Fixed-Step ODE backend"


@pytest.mark.parametrize("solver, tolerance", [("euler", 0.14), ("heun", 0.0025), ("rk4", 3e-7)])
def test_integrators_have_expected_convergence_quality(solver, tolerance):
    result = execute(exponential_model(solver))
    actual = result.native_result.snapshots[-1].values["population"]
    expected = 2 * math.exp(1)
    assert abs(actual - expected) < tolerance


def test_final_step_is_clipped_to_reach_non_aligned_end_time():
    data = exponential_model()
    data["time"] = {"start": 0, "end": 1.05, "step": 0.2}
    result = execute(data).native_result
    assert result.snapshots[-1].time == pytest.approx(1.05)
    assert result.steps == 6


def test_coupled_system_uses_simultaneous_state_values():
    data = {
        "name": "Two-state transfer",
        "time": {"start": 0, "end": 1, "step": 0.01},
        "solver": "rk4",
        "variables": [
            {"name": "water_a", "initial_value": 100, "derivative": "-rate * water_a + rate * water_b"},
            {"name": "water_b", "initial_value": 0, "derivative": "rate * water_a - rate * water_b"},
        ],
        "parameters": [{"name": "rate", "value": 0.4}],
    }
    result = execute(data).native_result
    final = result.snapshots[-1].values
    assert final["water_a"] + final["water_b"] == pytest.approx(100.0, abs=1e-9)
    assert final["water_a"] < 100
    assert final["water_b"] > 0


@pytest.mark.parametrize("expression", [
    "__import__('os').system('whoami')",
    "population.__class__",
    "open('secret.txt')",
    "[x for x in population]",
    "unknown_rate * population",
])
def test_rejects_unsafe_or_unknown_expression_syntax(expression):
    data = exponential_model()
    data["variables"][0]["derivative"] = expression
    with pytest.raises(MathematicalModelError):
        mathematical_model_from_dict(data)


def test_rejects_invalid_time_solver_and_step_budget():
    data = exponential_model()
    data["time"]["step"] = 0
    with pytest.raises(MathematicalModelError, match="step"):
        mathematical_model_from_dict(data)
    data = exponential_model()
    data["solver"] = "adaptive"
    with pytest.raises(MathematicalModelError, match="solver"):
        mathematical_model_from_dict(data)
    data = exponential_model()
    data["max_steps"] = 2
    with pytest.raises(MathematicalModelError, match="exceeding max_steps"):
        mathematical_model_from_dict(data)


def test_runtime_numerical_error_is_reported_with_variable_and_time():
    data = exponential_model()
    data["variables"][0]["derivative"] = "population / (time - time)"
    with pytest.raises(MathematicalModelError, match="population.*time"):
        execute(data)


def test_metrics_include_step_count_and_variable_summary():
    result = execute(exponential_model())
    metrics = {item.name: item.value for item in result.metrics}
    assert metrics["step_count"] == 20
    assert metrics["population.initial"] == 2.0
    assert metrics["population.final"] == pytest.approx(2 * math.exp(1), rel=1e-7)
    assert metrics["population.maximum"] == metrics["population.final"]


def test_bundled_sir_scenario_preserves_total_population():
    import json
    from pathlib import Path

    scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "mathematical" / "sir_rk4.json"
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    final = execute(raw).native_result.snapshots[-1].values
    assert sum(final.values()) == pytest.approx(1000.0, abs=1e-8)
    assert final["infected"] > 0
    assert final["recovered"] > 0


def test_backend_revalidates_directly_constructed_model_objects():
    from simulations.mathematical import MathematicalModel, MathematicalVariable

    unsafe = MathematicalModel(
        name="Unsafe", time_start=0, time_end=1, time_step=0.1, solver="rk4",
        variables=(MathematicalVariable("x", 1.0, "__import__('os')"),),
        parameters=(),
    )
    specification = SimulationSpecification("Unsafe", SimulationParadigm.MATHEMATICAL, unsafe)
    with pytest.raises(MathematicalModelError, match="unsupported function"):
        MathematicalBackend().execute(specification)
