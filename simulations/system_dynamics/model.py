"""Validated contracts for stock-and-flow system dynamics models (M22)."""
from __future__ import annotations

from dataclasses import dataclass
import ast
import math
import re
from typing import Any

from simulations.mathematical.model import (
    MathematicalModelError,
    _identifier,
    parse_expression,
)


@dataclass(frozen=True, slots=True)
class Stock:
    name: str
    initial_value: float
    unit: str | None = None
    minimum: float | None = None


@dataclass(frozen=True, slots=True)
class Flow:
    name: str
    source_stock: str | None
    target_stock: str | None
    rate_expression: str
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class Auxiliary:
    name: str
    expression: str
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    value: float
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class SystemDynamicsModel:
    name: str
    time_start: float
    time_end: float
    time_step: float
    solver: str
    stocks: tuple[Stock, ...]
    flows: tuple[Flow, ...]
    auxiliaries: tuple[Auxiliary, ...]
    auxiliary_order: tuple[str, ...]
    parameters: tuple[Parameter, ...]
    time_unit: str | None = None
    max_steps: int = 200_000

    @property
    def estimated_steps(self) -> int:
        return max(1, math.ceil((self.time_end - self.time_start) / self.time_step))


class SystemDynamicsModelError(ValueError):
    """Raised when a stock-flow model is invalid or unsafe to execute."""


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SystemDynamicsModelError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SystemDynamicsModelError(f"{path} must be finite")
    return result


def _optional_unit(value: Any, path: str) -> str | None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise SystemDynamicsModelError(f"{path} must be a non-empty string or null")
    return value


def system_dynamics_model_from_dict(raw: Any) -> SystemDynamicsModel:
    """Parse the strict, portable M22 JSON model format."""
    if not isinstance(raw, dict):
        raise SystemDynamicsModelError("model_data must be a JSON object")
    allowed = {"schema_version", "name", "description", "time", "solver", "stocks", "flows", "auxiliaries", "parameters", "max_steps"}
    unknown = set(raw) - allowed
    if unknown:
        raise SystemDynamicsModelError(f"model_data contains unknown field(s): {', '.join(sorted(unknown))}")
    schema_version = raw.get("schema_version", 1)
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise SystemDynamicsModelError("schema_version must be integer 1")
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        raise SystemDynamicsModelError("name must be a non-empty string")
    if not isinstance(raw.get("description", ""), str):
        raise SystemDynamicsModelError("description must be a string")

    time_data = raw.get("time")
    if not isinstance(time_data, dict) or set(time_data) - {"start", "end", "step", "unit"}:
        raise SystemDynamicsModelError("time must contain start, end, step and optional unit")
    start = _number(time_data.get("start"), "time.start")
    end = _number(time_data.get("end"), "time.end")
    step = _number(time_data.get("step"), "time.step")
    if end <= start:
        raise SystemDynamicsModelError("time.end must be greater than time.start")
    if step <= 0 or not math.isfinite(end - start):
        raise SystemDynamicsModelError("time.step must be positive and time duration finite")
    time_unit = _optional_unit(time_data.get("unit"), "time.unit")

    solver = raw.get("solver", "rk4")
    if not isinstance(solver, str) or solver not in {"euler", "heun", "rk4"}:
        raise SystemDynamicsModelError("solver must be one of: euler, heun, rk4")

    stocks_raw = raw.get("stocks")
    flows_raw = raw.get("flows")
    auxiliaries_raw = raw.get("auxiliaries", [])
    parameters_raw = raw.get("parameters", [])
    if not isinstance(stocks_raw, list) or not stocks_raw:
        raise SystemDynamicsModelError("stocks must be a non-empty array")
    if not isinstance(flows_raw, list) or not flows_raw:
        raise SystemDynamicsModelError("flows must be a non-empty array")
    if not isinstance(auxiliaries_raw, list) or not isinstance(parameters_raw, list):
        raise SystemDynamicsModelError("auxiliaries and parameters must be arrays")

    symbols: set[str] = set()
    stocks: list[Stock] = []
    for index, item in enumerate(stocks_raw):
        path = f"stocks[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "initial_value", "unit", "minimum"}:
            raise SystemDynamicsModelError(f"{path} has unsupported fields or is not an object")
        name = _identifier(item.get("name"), f"{path}.name")
        if name in symbols:
            raise SystemDynamicsModelError(f"Duplicate model identifier {name!r}")
        symbols.add(name)
        minimum = None if item.get("minimum") is None else _number(item["minimum"], f"{path}.minimum")
        initial = _number(item.get("initial_value"), f"{path}.initial_value")
        if minimum is not None and initial < minimum:
            raise SystemDynamicsModelError(f"{path}.initial_value must be greater than or equal to minimum")
        stocks.append(Stock(name, initial, _optional_unit(item.get("unit"), f"{path}.unit"), minimum))

    parameters: list[Parameter] = []
    for index, item in enumerate(parameters_raw):
        path = f"parameters[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "value", "unit"}:
            raise SystemDynamicsModelError(f"{path} has unsupported fields or is not an object")
        name = _identifier(item.get("name"), f"{path}.name")
        if name in symbols:
            raise SystemDynamicsModelError(f"Duplicate model identifier {name!r}")
        symbols.add(name)
        parameters.append(Parameter(name, _number(item.get("value"), f"{path}.value"), _optional_unit(item.get("unit"), f"{path}.unit")))

    auxiliaries: list[Auxiliary] = []
    for index, item in enumerate(auxiliaries_raw):
        path = f"auxiliaries[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "expression", "unit"}:
            raise SystemDynamicsModelError(f"{path} has unsupported fields or is not an object")
        name = _identifier(item.get("name"), f"{path}.name")
        if name in symbols:
            raise SystemDynamicsModelError(f"Duplicate model identifier {name!r}")
        symbols.add(name)
        expression = item.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise SystemDynamicsModelError(f"{path}.expression must be a non-empty expression")
        auxiliaries.append(Auxiliary(name, expression, _optional_unit(item.get("unit"), f"{path}.unit")))

    stock_names = {item.name for item in stocks}
    parameter_names = {item.name for item in parameters}
    auxiliary_names = {item.name for item in auxiliaries}
    allowed_names = stock_names | parameter_names | auxiliary_names | {"t", "time", "pi", "e"}

    auxiliary_trees: dict[str, ast.Expression] = {}
    for index, item in enumerate(auxiliaries):
        auxiliary_trees[item.name] = parse_expression(item.expression, path=f"auxiliaries[{index}].expression", allowed_names=allowed_names)

    # Topologically order auxiliary equations; circular definitions are rejected.
    dependencies: dict[str, set[str]] = {}
    for item in auxiliaries:
        dependencies[item.name] = {
            node.id for node in ast.walk(auxiliary_trees[item.name])
            if isinstance(node, ast.Name) and node.id in auxiliary_names
        }
    order: list[str] = []
    pending = {name: set(values) for name, values in dependencies.items()}
    while pending:
        ready = sorted(name for name, values in pending.items() if not values)
        if not ready:
            raise SystemDynamicsModelError("auxiliary expressions contain a circular dependency")
        for name in ready:
            order.append(name)
            pending.pop(name)
        for values in pending.values():
            values.difference_update(ready)

    flows: list[Flow] = []
    flow_names: set[str] = set()
    for index, item in enumerate(flows_raw):
        path = f"flows[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "source_stock", "target_stock", "rate_expression", "unit"}:
            raise SystemDynamicsModelError(f"{path} has unsupported fields or is not an object")
        name = _identifier(item.get("name"), f"{path}.name")
        if name in flow_names:
            raise SystemDynamicsModelError(f"Duplicate flow name {name!r}")
        flow_names.add(name)
        source = item.get("source_stock")
        target = item.get("target_stock")
        if source is not None and not isinstance(source, str):
            raise SystemDynamicsModelError(f"{path}.source_stock must be a stock name or null")
        if target is not None and not isinstance(target, str):
            raise SystemDynamicsModelError(f"{path}.target_stock must be a stock name or null")
        if source is not None and source not in stock_names:
            raise SystemDynamicsModelError(f"{path}.source_stock must name a declared stock or be null")
        if target is not None and target not in stock_names:
            raise SystemDynamicsModelError(f"{path}.target_stock must name a declared stock or be null")
        if source is None and target is None:
            raise SystemDynamicsModelError(f"{path} must connect at least one stock")
        if source == target and source is not None:
            raise SystemDynamicsModelError(f"{path} cannot use the same source and target stock")
        rate = item.get("rate_expression")
        parse_expression(rate, path=f"{path}.rate_expression", allowed_names=allowed_names)
        flows.append(Flow(name, source, target, rate, _optional_unit(item.get("unit"), f"{path}.unit")))

    max_steps = raw.get("max_steps", 200_000)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 500_000:
        raise SystemDynamicsModelError("max_steps must be an integer between 1 and 500000")
    model = SystemDynamicsModel(
        raw["name"].strip(), start, end, step, solver, tuple(stocks), tuple(flows),
        tuple(auxiliaries), tuple(order), tuple(parameters), time_unit, max_steps,
    )
    if model.estimated_steps > model.max_steps:
        raise SystemDynamicsModelError(
            f"time settings require {model.estimated_steps:,} steps, exceeding max_steps={model.max_steps:,}"
        )
    return model
