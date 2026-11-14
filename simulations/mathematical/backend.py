"""Deterministic fixed-step ODE integration without dynamic code execution."""

from __future__ import annotations

import ast
from functools import lru_cache
from dataclasses import dataclass
import math
from typing import Mapping

from simulations.core.backend import SimulationExecutionResult, SimulationMetric
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.mathematical.model import (
    MathematicalModel, MathematicalModelError, mathematical_model_from_dict,
)


_FUNCTIONS = {
    "abs": abs, "ceil": math.ceil, "cos": math.cos, "exp": math.exp,
    "floor": math.floor, "log": math.log, "log10": math.log10,
    "max": max, "min": min, "sin": math.sin, "sqrt": math.sqrt,
    "tan": math.tan,
}
_BINARY_OPERATORS = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Pow: lambda left, right: left ** right,
    ast.Mod: lambda left, right: left % right,
}
_UNARY_OPERATORS = {ast.UAdd: lambda value: +value, ast.USub: lambda value: -value}


@dataclass(frozen=True, slots=True)
class MathematicalSnapshot:
    time: float
    values: dict[str, float]


@dataclass(frozen=True, slots=True)
class MathematicalExecution:
    model_name: str
    solver: str
    start_time: float
    end_time: float
    time_unit: str | None
    steps: int
    snapshots: tuple[MathematicalSnapshot, ...]
    variable_units: dict[str, str | None]
    summaries: dict[str, dict[str, float]]


def _evaluate(node: ast.AST, names: Mapping[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, names)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return math.pi
        if node.id == "e":
            return math.e
        return float(names[node.id])
    if isinstance(node, ast.BinOp):
        operation = _BINARY_OPERATORS[type(node.op)]
        if isinstance(node.op, ast.Pow):
            exponent = _evaluate(node.right, names)
            if abs(exponent) > 100:
                raise MathematicalModelError("Exponent magnitude exceeds the supported limit of 100")
            return float(operation(_evaluate(node.left, names), exponent))
        return float(operation(_evaluate(node.left, names), _evaluate(node.right, names)))
    if isinstance(node, ast.UnaryOp):
        return float(_UNARY_OPERATORS[type(node.op)](_evaluate(node.operand, names)))
    if isinstance(node, ast.Call):
        function = _FUNCTIONS[node.func.id]
        return float(function(*(_evaluate(argument, names) for argument in node.args)))
    raise MathematicalModelError(f"Unsupported expression node: {type(node).__name__}")


@lru_cache(maxsize=512)
def _expression_tree(source: str) -> ast.Expression:
    return ast.parse(source, mode="eval")


def _derivatives(model: MathematicalModel, time_value: float, state: Mapping[str, float]) -> dict[str, float]:
    environment: dict[str, float] = {item.name: item.value for item in model.parameters}
    environment.update(state)
    environment["t"] = time_value
    environment["time"] = time_value
    derivatives: dict[str, float] = {}
    for variable in model.variables:
        tree = ast.parse(variable.derivative, mode="eval")
        try:
            value = _evaluate(tree, environment)
        except (ArithmeticError, OverflowError, ValueError, TypeError) as error:
            raise MathematicalModelError(
                f"Could not evaluate derivative for {variable.name!r} at time {time_value:g}: {error}"
            ) from error
        if not math.isfinite(value):
            raise MathematicalModelError(
                f"Derivative for {variable.name!r} became non-finite at time {time_value:g}"
            )
        derivatives[variable.name] = value
    return derivatives


def _offset(state: Mapping[str, float], slope: Mapping[str, float], factor: float) -> dict[str, float]:
    return {name: state[name] + factor * slope[name] for name in state}


def _advance(model: MathematicalModel, time_value: float, state: dict[str, float], step: float) -> dict[str, float]:
    k1 = _derivatives(model, time_value, state)
    if model.solver == "euler":
        result = _offset(state, k1, step)
    elif model.solver == "heun":
        predicted = _offset(state, k1, step)
        k2 = _derivatives(model, time_value + step, predicted)
        result = {name: state[name] + step * (k1[name] + k2[name]) / 2.0 for name in state}
    else:  # Classical fourth-order Runge-Kutta.
        k2 = _derivatives(model, time_value + step / 2.0, _offset(state, k1, step / 2.0))
        k3 = _derivatives(model, time_value + step / 2.0, _offset(state, k2, step / 2.0))
        k4 = _derivatives(model, time_value + step, _offset(state, k3, step))
        result = {
            name: state[name] + step * (k1[name] + 2 * k2[name] + 2 * k3[name] + k4[name]) / 6.0
            for name in state
        }
    for name, value in result.items():
        if not math.isfinite(value):
            raise MathematicalModelError(f"Variable {name!r} became non-finite at time {time_value + step:g}")
    return result


class MathematicalBackend:
    """Run deterministic fixed-step ODE models using Euler, Heun or RK4."""

    name = "Mathematical V1 / Fixed-Step ODE backend"
    paradigm = SimulationParadigm.MATHEMATICAL

    def execute(self, specification: SimulationSpecification) -> SimulationExecutionResult:
        if not isinstance(specification, SimulationSpecification):
            raise TypeError("specification must be a SimulationSpecification")
        if specification.paradigm is not self.paradigm:
            raise ValueError("MathematicalBackend requires a mathematical specification")
        model = specification.model
        if isinstance(model, dict):
            model = mathematical_model_from_dict(model)
        if isinstance(model, MathematicalModel):
            # Re-validate even directly constructed dataclasses so callers cannot
            # bypass the expression allow-list or integration safety limits.
            model = mathematical_model_from_dict({
                "schema_version": 1, "name": model.name,
                "time": {"start": model.time_start, "end": model.time_end, "step": model.time_step, "unit": model.time_unit},
                "solver": model.solver, "max_steps": model.max_steps,
                "variables": [
                    {"name": item.name, "initial_value": item.initial_value, "derivative": item.derivative, "unit": item.unit}
                    for item in model.variables
                ],
                "parameters": [
                    {"name": item.name, "value": item.value, "unit": item.unit}
                    for item in model.parameters
                ],
            })
        if not isinstance(model, MathematicalModel):
            raise TypeError("specification.model must be MathematicalModel or a model-data object")

        state = {item.name: item.initial_value for item in model.variables}
        snapshots: list[MathematicalSnapshot] = [MathematicalSnapshot(model.time_start, dict(state))]
        current_time = model.time_start
        for step_index in range(model.estimated_steps):
            target_time = min(model.time_start + (step_index + 1) * model.time_step, model.time_end)
            step_size = target_time - current_time
            if step_size <= 0:
                break
            state = _advance(model, current_time, state, step_size)
            current_time = target_time
            snapshots.append(MathematicalSnapshot(current_time, dict(state)))
        if not math.isclose(current_time, model.time_end, rel_tol=1e-12, abs_tol=1e-12):
            raise MathematicalModelError("Numerical integration did not reach the requested end time")

        summaries: dict[str, dict[str, float]] = {}
        metrics = [
            SimulationMetric("step_count", len(snapshots) - 1, "steps"),
            SimulationMetric("duration", model.time_end - model.time_start, model.time_unit),
        ]
        for variable in model.variables:
            values = [snapshot.values[variable.name] for snapshot in snapshots]
            summary = {
                "initial": values[0], "final": values[-1],
                "minimum": min(values), "maximum": max(values),
            }
            summaries[variable.name] = summary
            for metric_name, metric_value in summary.items():
                metrics.append(SimulationMetric(f"{variable.name}.{metric_name}", metric_value, variable.unit))

        native = MathematicalExecution(
            model_name=model.name, solver=model.solver,
            start_time=model.time_start, end_time=model.time_end,
            time_unit=model.time_unit, steps=len(snapshots) - 1,
            snapshots=tuple(snapshots),
            variable_units={item.name: item.unit for item in model.variables},
            summaries=summaries,
        )
        return SimulationExecutionResult(
            specification_name=specification.name,
            paradigm=self.paradigm, backend_name=self.name,
            metrics=tuple(metrics), native_result=native,
        )
