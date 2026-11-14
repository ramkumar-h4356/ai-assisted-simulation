"""Deterministic stock-and-flow system dynamics execution (M22)."""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Mapping

from simulations.core.backend import SimulationExecutionResult, SimulationMetric
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.mathematical.backend import _evaluate
from simulations.system_dynamics.model import (
    Flow, Stock, SystemDynamicsModel, SystemDynamicsModelError,
    system_dynamics_model_from_dict,
)


@dataclass(frozen=True, slots=True)
class SystemDynamicsSnapshot:
    time: float
    stocks: dict[str, float]
    auxiliaries: dict[str, float]
    flow_rates: dict[str, float]


@dataclass(frozen=True, slots=True)
class SystemDynamicsExecution:
    model_name: str
    solver: str
    start_time: float
    end_time: float
    time_step: float
    time_unit: str | None
    steps: int
    stock_units: dict[str, str | None]
    flow_units: dict[str, str | None]
    snapshots: tuple[SystemDynamicsSnapshot, ...]
    summaries: dict[str, dict[str, float]]
    total_flow: dict[str, float]


def _environment(model: SystemDynamicsModel, time_value: float, state: Mapping[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    names: dict[str, float] = {item.name: item.value for item in model.parameters}
    names.update(state)
    names["t"] = time_value
    names["time"] = time_value
    names["pi"] = math.pi
    names["e"] = math.e
    auxiliaries: dict[str, float] = {}
    auxiliary_by_name = {item.name: item for item in model.auxiliaries}
    try:
        for name in model.auxiliary_order:
            item = auxiliary_by_name[name]
            value = float(_evaluate(ast.parse(item.expression, mode="eval"), names))
            if not math.isfinite(value):
                raise SystemDynamicsModelError(f"Auxiliary {name!r} became non-finite at time {time_value:g}")
            names[name] = value
            auxiliaries[name] = value
    except (ArithmeticError, OverflowError, ValueError, TypeError, KeyError) as error:
        if isinstance(error, SystemDynamicsModelError):
            raise
        raise SystemDynamicsModelError(f"Could not evaluate auxiliary expression at time {time_value:g}: {error}") from error
    return names, auxiliaries


def _flows_and_derivatives(model: SystemDynamicsModel, time_value: float, state: Mapping[str, float]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    names, auxiliaries = _environment(model, time_value, state)
    rates: dict[str, float] = {}
    derivatives = {item.name: 0.0 for item in model.stocks}
    for flow in model.flows:
        try:
            rate = float(_evaluate(ast.parse(flow.rate_expression, mode="eval"), names))
        except (ArithmeticError, OverflowError, ValueError, TypeError, KeyError) as error:
            raise SystemDynamicsModelError(f"Could not evaluate flow {flow.name!r} at time {time_value:g}: {error}") from error
        if not math.isfinite(rate) or abs(rate) > 1e15:
            raise SystemDynamicsModelError(f"Flow {flow.name!r} produced a non-finite or excessive rate at time {time_value:g}")
        if rate < 0:
            raise SystemDynamicsModelError(f"Flow {flow.name!r} must be non-negative; use source/target direction to represent sign")
        rates[flow.name] = rate
        if flow.source_stock is not None:
            derivatives[flow.source_stock] -= rate
        if flow.target_stock is not None:
            derivatives[flow.target_stock] += rate
    return rates, auxiliaries, derivatives


def _shift(state: Mapping[str, float], slope: Mapping[str, float], factor: float) -> dict[str, float]:
    return {name: state[name] + factor * slope[name] for name in state}


def _advance(model: SystemDynamicsModel, time_value: float, state: dict[str, float], step: float) -> dict[str, float]:
    _, _, k1 = _flows_and_derivatives(model, time_value, state)
    if model.solver == "euler":
        result = _shift(state, k1, step)
    elif model.solver == "heun":
        predicted = _shift(state, k1, step)
        _, _, k2 = _flows_and_derivatives(model, time_value + step, predicted)
        result = {name: state[name] + step * (k1[name] + k2[name]) / 2 for name in state}
    else:
        _, _, k2 = _flows_and_derivatives(model, time_value + step / 2, _shift(state, k1, step / 2))
        _, _, k3 = _flows_and_derivatives(model, time_value + step / 2, _shift(state, k2, step / 2))
        _, _, k4 = _flows_and_derivatives(model, time_value + step, _shift(state, k3, step))
        result = {
            name: state[name] + step * (k1[name] + 2 * k2[name] + 2 * k3[name] + k4[name]) / 6
            for name in state
        }
    for stock in model.stocks:
        value = result[stock.name]
        if not math.isfinite(value) or abs(value) > 1e15:
            raise SystemDynamicsModelError(f"Stock {stock.name!r} became non-finite or excessive at time {time_value + step:g}")
        if stock.minimum is not None and value < stock.minimum - 1e-9:
            raise SystemDynamicsModelError(
                f"Stock {stock.name!r} fell below its minimum ({stock.minimum:g}) at time {time_value + step:g}; reduce the time step or revise the flow assumptions"
            )
    return result


class SystemDynamicsBackend:
    """Execute stock-and-flow models using fixed-step Euler, Heun or RK4."""
    name = "System Dynamics V1 / Stock-and-Flow backend"
    paradigm = SimulationParadigm.SYSTEM_DYNAMICS

    def execute(self, specification: SimulationSpecification) -> SimulationExecutionResult:
        if not isinstance(specification, SimulationSpecification):
            raise TypeError("specification must be a SimulationSpecification")
        if specification.paradigm is not self.paradigm:
            raise ValueError("SystemDynamicsBackend requires a system_dynamics specification")
        raw = specification.model
        if isinstance(raw, SystemDynamicsModel):
            raw = {
                "schema_version": 1, "name": raw.name,
                "time": {"start": raw.time_start, "end": raw.time_end, "step": raw.time_step, "unit": raw.time_unit},
                "solver": raw.solver, "max_steps": raw.max_steps,
                "stocks": [{"name": item.name, "initial_value": item.initial_value, "unit": item.unit, "minimum": item.minimum} for item in raw.stocks],
                "flows": [{"name": item.name, "source_stock": item.source_stock, "target_stock": item.target_stock, "rate_expression": item.rate_expression, "unit": item.unit} for item in raw.flows],
                "auxiliaries": [{"name": item.name, "expression": item.expression, "unit": item.unit} for item in raw.auxiliaries],
                "parameters": [{"name": item.name, "value": item.value, "unit": item.unit} for item in raw.parameters],
            }
        model = system_dynamics_model_from_dict(raw)
        state = {item.name: item.initial_value for item in model.stocks}
        rates, auxiliaries, _ = _flows_and_derivatives(model, model.time_start, state)
        snapshots = [SystemDynamicsSnapshot(model.time_start, dict(state), auxiliaries, rates)]
        total_flow = {item.name: 0.0 for item in model.flows}
        current_time = model.time_start
        for step_index in range(model.estimated_steps):
            target_time = min(model.time_start + (step_index + 1) * model.time_step, model.time_end)
            step_size = target_time - current_time
            if step_size <= 0:
                break
            previous_rates = rates
            state = _advance(model, current_time, state, step_size)
            current_time = target_time
            rates, auxiliaries, _ = _flows_and_derivatives(model, current_time, state)
            for flow in model.flows:
                # Trapezoidal integration gives a consistent cumulative flow estimate.
                total_flow[flow.name] += (previous_rates[flow.name] + rates[flow.name]) * step_size / 2
            snapshots.append(SystemDynamicsSnapshot(current_time, dict(state), auxiliaries, rates))
        if not math.isclose(current_time, model.time_end, rel_tol=1e-12, abs_tol=1e-12):
            raise SystemDynamicsModelError("Integration did not reach the requested end time")

        summaries: dict[str, dict[str, float]] = {}
        metrics: list[SimulationMetric] = [
            SimulationMetric("step_count", len(snapshots) - 1, "steps"),
            SimulationMetric("duration", model.time_end - model.time_start, model.time_unit),
        ]
        for stock in model.stocks:
            values = [item.stocks[stock.name] for item in snapshots]
            summaries[stock.name] = {"initial": values[0], "final": values[-1], "minimum": min(values), "maximum": max(values)}
            for key, value in summaries[stock.name].items():
                metrics.append(SimulationMetric(f"stock.{stock.name}.{key}", value, stock.unit))
        for flow in model.flows:
            metrics.append(SimulationMetric(f"flow.{flow.name}.cumulative", total_flow[flow.name], flow.unit))
            metrics.append(SimulationMetric(f"flow.{flow.name}.final_rate", snapshots[-1].flow_rates[flow.name], flow.unit))

        native = SystemDynamicsExecution(
            model_name=model.name, solver=model.solver, start_time=model.time_start,
            end_time=model.time_end, time_step=model.time_step, time_unit=model.time_unit,
            steps=len(snapshots) - 1,
            stock_units={item.name: item.unit for item in model.stocks},
            flow_units={item.name: item.unit for item in model.flows},
            snapshots=tuple(snapshots), summaries=summaries, total_flow=total_flow,
        )
        return SimulationExecutionResult(
            specification_name=specification.name, paradigm=self.paradigm,
            backend_name=self.name, metrics=tuple(metrics), native_result=native,
        )
