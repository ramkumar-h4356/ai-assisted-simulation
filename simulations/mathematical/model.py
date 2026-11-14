"""Validated model contracts for deterministic mathematical simulation."""

from __future__ import annotations

from dataclasses import dataclass
import ast
import math
import re
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_RESERVED_NAMES = {"t", "time", "pi", "e"}
_ALLOWED_FUNCTIONS = {
    "abs", "ceil", "cos", "exp", "floor", "log", "log10", "max",
    "min", "sin", "sqrt", "tan",
}
_ALLOWED_CONSTANTS = {"pi", "e"}
_ALLOWED_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)


class MathematicalModelError(ValueError):
    """Raised when a mathematical model is invalid or unsafe to execute."""


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MathematicalModelError(f"{path} must be a numeric value")
    result = float(value)
    if not math.isfinite(result):
        raise MathematicalModelError(f"{path} must be finite")
    return result


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise MathematicalModelError(f"{path} must be a valid identifier")
    if value in _RESERVED_NAMES or value in _ALLOWED_FUNCTIONS:
        raise MathematicalModelError(f"{path} uses reserved identifier {value!r}")
    return value


def _validate_expression_node(node: ast.AST, *, path: str, allowed_names: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _validate_expression_node(node.body, path=path, allowed_names=allowed_names)
        return
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise MathematicalModelError(f"{path} may contain only numeric constants")
        if not math.isfinite(float(node.value)):
            raise MathematicalModelError(f"{path} contains a non-finite constant")
        return
    if isinstance(node, ast.Name):
        if node.id not in allowed_names:
            raise MathematicalModelError(f"{path} references unknown name {node.id!r}")
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINARY):
        _validate_expression_node(node.left, path=path, allowed_names=allowed_names)
        _validate_expression_node(node.right, path=path, allowed_names=allowed_names)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY):
        _validate_expression_node(node.operand, path=path, allowed_names=allowed_names)
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function_name = node.func.id
        if function_name not in _ALLOWED_FUNCTIONS:
            raise MathematicalModelError(f"{path} calls unsupported function {function_name!r}")
        if node.keywords:
            raise MathematicalModelError(f"{path} does not allow keyword arguments")
        if function_name in {"abs", "ceil", "floor", "exp", "log", "log10", "sin", "cos", "tan", "sqrt"} and len(node.args) != 1:
            raise MathematicalModelError(f"{path}: {function_name}() expects one argument")
        if function_name in {"min", "max"} and not node.args:
            raise MathematicalModelError(f"{path}: {function_name}() requires at least one argument")
        for argument in node.args:
            _validate_expression_node(argument, path=path, allowed_names=allowed_names)
        return
    raise MathematicalModelError(
        f"{path} contains unsupported expression syntax ({type(node).__name__})"
    )


def parse_expression(expression: Any, *, path: str, allowed_names: set[str]) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        raise MathematicalModelError(f"{path} must be a non-empty expression string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise MathematicalModelError(f"{path} has invalid expression syntax: {error.msg}") from error
    _validate_expression_node(tree, path=path, allowed_names=allowed_names)
    return tree


@dataclass(frozen=True, slots=True)
class MathematicalVariable:
    name: str
    initial_value: float
    derivative: str
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class MathematicalParameter:
    name: str
    value: float
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class MathematicalModel:
    name: str
    time_start: float
    time_end: float
    time_step: float
    solver: str
    variables: tuple[MathematicalVariable, ...]
    parameters: tuple[MathematicalParameter, ...]
    time_unit: str | None = None
    max_steps: int = 200_000

    @property
    def estimated_steps(self) -> int:
        return max(1, math.ceil((self.time_end - self.time_start) / self.time_step))


def mathematical_model_from_dict(raw: Any) -> MathematicalModel:
    """Parse and fully validate the portable M20 JSON model format."""
    if not isinstance(raw, dict):
        raise MathematicalModelError("model_data must be a JSON object")
    allowed_top = {"schema_version", "name", "description", "time", "solver", "variables", "parameters", "max_steps"}
    unknown = set(raw) - allowed_top
    if unknown:
        raise MathematicalModelError(f"model_data contains unknown field(s): {', '.join(sorted(unknown))}")
    if raw.get("schema_version", 1) != 1:
        raise MathematicalModelError("schema_version must be 1")
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise MathematicalModelError("description must be a string")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise MathematicalModelError("name must be a non-empty string")

    time_data = raw.get("time")
    if not isinstance(time_data, dict):
        raise MathematicalModelError("time must be an object with start, end and step")
    if set(time_data) - {"start", "end", "step", "unit"}:
        raise MathematicalModelError("time contains unsupported fields")
    start = _finite_number(time_data.get("start"), "time.start")
    end = _finite_number(time_data.get("end"), "time.end")
    step = _finite_number(time_data.get("step"), "time.step")
    if end <= start:
        raise MathematicalModelError("time.end must be greater than time.start")
    if step <= 0:
        raise MathematicalModelError("time.step must be greater than zero")
    if not math.isfinite(end - start):
        raise MathematicalModelError("time duration must be finite")
    time_unit = time_data.get("unit")
    if time_unit is not None and not isinstance(time_unit, str):
        raise MathematicalModelError("time.unit must be a string or null")

    solver = raw.get("solver", "rk4")
    if not isinstance(solver, str) or solver not in {"euler", "heun", "rk4"}:
        raise MathematicalModelError("solver must be one of: euler, heun, rk4")

    variables_raw = raw.get("variables")
    parameters_raw = raw.get("parameters", [])
    if not isinstance(variables_raw, list) or not variables_raw:
        raise MathematicalModelError("variables must be a non-empty array")
    if not isinstance(parameters_raw, list):
        raise MathematicalModelError("parameters must be an array")

    variables: list[MathematicalVariable] = []
    parameters: list[MathematicalParameter] = []
    names: set[str] = set()

    for index, item in enumerate(variables_raw):
        path = f"variables[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "initial_value", "derivative", "unit"}:
            raise MathematicalModelError(f"{path} must contain name, initial_value, derivative and optional unit")
        variable_name = _identifier(item.get("name"), f"{path}.name")
        if variable_name in names:
            raise MathematicalModelError(f"Duplicate model identifier {variable_name!r}")
        names.add(variable_name)
        derivative = item.get("derivative")
        if not isinstance(derivative, str) or not derivative.strip():
            raise MathematicalModelError(f"{path}.derivative must be a non-empty expression string")
        unit = item.get("unit")
        if unit is not None and not isinstance(unit, str):
            raise MathematicalModelError(f"{path}.unit must be a string or null")
        variables.append(MathematicalVariable(
            variable_name, _finite_number(item.get("initial_value"), f"{path}.initial_value"), derivative, unit
        ))

    for index, item in enumerate(parameters_raw):
        path = f"parameters[{index}]"
        if not isinstance(item, dict) or set(item) - {"name", "value", "unit"}:
            raise MathematicalModelError(f"{path} must contain name, value and optional unit")
        parameter_name = _identifier(item.get("name"), f"{path}.name")
        if parameter_name in names:
            raise MathematicalModelError(f"Duplicate model identifier {parameter_name!r}")
        names.add(parameter_name)
        unit = item.get("unit")
        if unit is not None and not isinstance(unit, str):
            raise MathematicalModelError(f"{path}.unit must be a string or null")
        parameters.append(MathematicalParameter(
            parameter_name, _finite_number(item.get("value"), f"{path}.value"), unit
        ))

    available_names = names | _ALLOWED_CONSTANTS | {"t", "time"}
    for index, variable in enumerate(variables):
        parse_expression(variable.derivative, path=f"variables[{index}].derivative", allowed_names=available_names)

    max_steps = raw.get("max_steps", 200_000)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 500_000:
        raise MathematicalModelError("max_steps must be an integer between 1 and 500000")

    model = MathematicalModel(
        name=name.strip(), time_start=start, time_end=end, time_step=step,
        solver=solver, variables=tuple(variables), parameters=tuple(parameters),
        time_unit=time_unit, max_steps=max_steps,
    )
    if model.estimated_steps > model.max_steps:
        raise MathematicalModelError(
            f"time settings require {model.estimated_steps:,} steps, exceeding max_steps={model.max_steps:,}"
        )
    return model
