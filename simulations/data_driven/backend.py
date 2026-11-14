"""Deterministic ridge-VAR(p) fitting, holdout evaluation and forecasting."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from simulations.core.backend import SimulationExecutionResult, SimulationMetric
from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.data_driven.model import (
    DataDrivenModel, DataDrivenModelError, data_driven_model_from_dict,
)


@dataclass(frozen=True, slots=True)
class DataDrivenSnapshot:
    time: float
    values: dict[str, float]


@dataclass(frozen=True, slots=True)
class DataDrivenPrediction:
    time: float
    actual: dict[str, float]
    predicted: dict[str, float]
    persistence_baseline: dict[str, float]


@dataclass(frozen=True, slots=True)
class DataDrivenExecution:
    model_name: str
    method: str
    dataset_reference_id: str
    time_unit: str
    time_step: float
    variables: tuple[str, ...]
    lag_order: int
    ridge: float
    training_samples: int
    holdout_samples: int
    evaluation_strategy: str
    forecast_horizon: int
    coefficients: dict[str, dict[str, float]]
    evaluation_metrics: dict[str, dict[str, float]]
    holdout_predictions: tuple[DataDrivenPrediction, ...]
    forecast: tuple[DataDrivenSnapshot, ...]


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a small dense system using Gaussian elimination with pivoting."""
    size = len(vector)
    augmented = [list(row) + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-14:
            raise DataDrivenModelError(
                "VAR regression is singular; increase ridge regularization or provide more varied observations"
            )
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        for item in range(column, size + 1):
            augmented[column][item] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            for item in range(column, size + 1):
                augmented[row][item] -= factor * augmented[column][item]
    result = [augmented[index][size] for index in range(size)]
    if any(not math.isfinite(value) for value in result):
        raise DataDrivenModelError("VAR regression produced non-finite coefficients")
    return result


def _feature_vector(history: Sequence[Sequence[float]], lag_order: int) -> list[float]:
    features: list[float] = []
    for lag in range(1, lag_order + 1):
        features.extend(history[-lag])
    return features


def _fit_equation(
    rows: list[list[float]], targets: list[float], ridge: float,
) -> tuple[float, list[float]]:
    """Fit a standardized ridge-linear equation and return original-scale terms."""
    feature_count = len(rows[0])
    means = [sum(row[column] for row in rows) / len(rows) for column in range(feature_count)]
    scales = []
    for column, mean in enumerate(means):
        variance = sum((row[column] - mean) ** 2 for row in rows) / len(rows)
        scale = math.sqrt(variance)
        scales.append(scale if scale > 1e-12 else 1.0)
    target_mean = sum(targets) / len(targets)
    target_variance = sum((value - target_mean) ** 2 for value in targets) / len(targets)
    target_scale = math.sqrt(target_variance) or 1.0

    standardized = [
        [1.0] + [(row[column] - means[column]) / scales[column] for column in range(feature_count)]
        for row in rows
    ]
    normalized_targets = [(value - target_mean) / target_scale for value in targets]
    dimension = feature_count + 1
    gram = [[0.0] * dimension for _ in range(dimension)]
    right = [0.0] * dimension
    for row, target in zip(standardized, normalized_targets):
        for left in range(dimension):
            right[left] += row[left] * target
            for column in range(dimension):
                gram[left][column] += row[left] * row[column]
    for index in range(1, dimension):
        gram[index][index] += ridge
    normalized_coefficients = _solve(gram, right)

    slopes = [
        target_scale * normalized_coefficients[index + 1] / scales[index]
        for index in range(feature_count)
    ]
    intercept = target_mean + target_scale * normalized_coefficients[0] - sum(
        slopes[index] * means[index] for index in range(feature_count)
    )
    if not math.isfinite(intercept) or any(not math.isfinite(item) for item in slopes):
        raise DataDrivenModelError("VAR regression produced non-finite original-scale coefficients")
    return intercept, slopes


def _predict(features: Sequence[float], intercept: float, slopes: Sequence[float]) -> float:
    value = intercept + sum(feature * coefficient for feature, coefficient in zip(features, slopes))
    if not math.isfinite(value):
        raise DataDrivenModelError("VAR prediction became non-finite")
    if abs(value) > 1e15:
        raise DataDrivenModelError("VAR prediction exceeded the supported magnitude limit (1e15)")
    return value


def _fit_metrics(actual: list[float], predicted: list[float], baseline: list[float]) -> dict[str, float]:
    count = len(actual)
    mae = sum(abs(left - right) for left, right in zip(actual, predicted)) / count
    rmse = math.sqrt(sum((left - right) ** 2 for left, right in zip(actual, predicted)) / count)
    naive_mae = sum(abs(left - right) for left, right in zip(actual, baseline)) / count
    naive_rmse = math.sqrt(sum((left - right) ** 2 for left, right in zip(actual, baseline)) / count)
    mean = sum(actual) / count
    total = sum((item - mean) ** 2 for item in actual)
    residual = sum((left - right) ** 2 for left, right in zip(actual, predicted))
    r_squared = 1.0 - residual / total if total > 1e-15 else (1.0 if residual <= 1e-15 else 0.0)
    return {
        "mae": mae, "rmse": rmse, "r_squared": r_squared,
        "persistence_mae": naive_mae, "persistence_rmse": naive_rmse,
    }


class DataDrivenBackend:
    """Fit and execute a transparent autoregressive VAR(p) forecasting model."""

    name = "Data-Driven V1 / Ridge VAR(p) backend"
    paradigm = SimulationParadigm.DATA_DRIVEN

    def execute(self, specification: SimulationSpecification) -> SimulationExecutionResult:
        if not isinstance(specification, SimulationSpecification):
            raise TypeError("specification must be a SimulationSpecification")
        if specification.paradigm is not self.paradigm:
            raise ValueError("DataDrivenBackend requires a data_driven specification")
        raw = specification.model
        if isinstance(raw, DataDrivenModel):
            raw = {
                "schema_version": 1, "name": raw.name,
                "dataset_reference_id": raw.dataset_reference_id,
                "time_field": raw.time_field, "time_unit": raw.time_unit,
                "variables": list(raw.variables),
                "observations": [
                    {raw.time_field: item.timestamp, **dict(zip(raw.variables, item.values))}
                    for item in raw.observations
                ],
                "lag_order": raw.lag_order, "train_fraction": raw.train_fraction,
                "forecast_horizon": raw.forecast_horizon, "ridge": raw.ridge,
            }
        model = data_driven_model_from_dict(raw)
        variables = model.variables
        observations = model.observations
        lag_order = model.lag_order
        split_index = lag_order + model.training_samples

        training_rows: list[list[float]] = []
        targets_by_variable: dict[str, list[float]] = {name: [] for name in variables}
        for target_index in range(lag_order, split_index):
            history = [item.values for item in observations[:target_index]]
            features = _feature_vector(history, lag_order)
            training_rows.append(features)
            for variable_index, variable in enumerate(variables):
                targets_by_variable[variable].append(observations[target_index].values[variable_index])

        fitted: dict[str, tuple[float, list[float]]] = {}
        coefficients: dict[str, dict[str, float]] = {}
        feature_names = [
            f"lag_{lag}.{variable}"
            for lag in range(1, lag_order + 1)
            for variable in variables
        ]
        for variable in variables:
            intercept, slopes = _fit_equation(training_rows, targets_by_variable[variable], model.ridge)
            fitted[variable] = (intercept, slopes)
            coefficients[variable] = {"intercept": intercept, **dict(zip(feature_names, slopes))}

        holdout_predictions: list[DataDrivenPrediction] = []
        actual_by_variable = {name: [] for name in variables}
        predicted_by_variable = {name: [] for name in variables}
        baseline_by_variable = {name: [] for name in variables}
        for target_index in range(split_index, len(observations)):
            features = _feature_vector([item.values for item in observations[:target_index]], lag_order)
            predicted = {
                variable: _predict(features, *fitted[variable])
                for variable in variables
            }
            actual = dict(zip(variables, observations[target_index].values))
            baseline = dict(zip(variables, observations[target_index - 1].values))
            holdout_predictions.append(DataDrivenPrediction(
                observations[target_index].timestamp, actual, predicted, baseline,
            ))
            for variable in variables:
                actual_by_variable[variable].append(actual[variable])
                predicted_by_variable[variable].append(predicted[variable])
                baseline_by_variable[variable].append(baseline[variable])

        evaluation = {
            variable: _fit_metrics(
                actual_by_variable[variable], predicted_by_variable[variable], baseline_by_variable[variable],
            )
            for variable in variables
        }

        history = [list(item.values) for item in observations[-lag_order:]]
        forecast: list[DataDrivenSnapshot] = []
        last_time = observations[-1].timestamp
        for offset in range(1, model.forecast_horizon + 1):
            features = _feature_vector(history, lag_order)
            values = {
                variable: _predict(features, *fitted[variable])
                for variable in variables
            }
            ordered_values = [values[variable] for variable in variables]
            history.append(ordered_values)
            forecast.append(DataDrivenSnapshot(
                last_time + offset * model.time_step, values,
            ))

        native = DataDrivenExecution(
            model_name=model.name, method="ridge_var", dataset_reference_id=model.dataset_reference_id,
            time_unit=model.time_unit, time_step=model.time_step, variables=variables,
            lag_order=lag_order, ridge=model.ridge, training_samples=model.training_samples,
            holdout_samples=model.holdout_samples,
            evaluation_strategy="one_step_walk_forward_with_observed_history",
            forecast_horizon=model.forecast_horizon,
            coefficients=coefficients, evaluation_metrics=evaluation,
            holdout_predictions=tuple(holdout_predictions), forecast=tuple(forecast),
        )
        metrics: list[SimulationMetric] = [
            SimulationMetric("training_samples", model.training_samples, "observations"),
            SimulationMetric("holdout_samples", model.holdout_samples, "observations"),
            SimulationMetric("forecast_horizon", model.forecast_horizon, "steps"),
        ]
        for variable, values in evaluation.items():
            for metric_name, value in values.items():
                metrics.append(SimulationMetric(f"{variable}.{metric_name}", value))
            metrics.append(SimulationMetric(f"{variable}.forecast_final", forecast[-1].values[variable]))
        return SimulationExecutionResult(
            specification_name=specification.name, paradigm=self.paradigm,
            backend_name=self.name, metrics=tuple(metrics), native_result=native,
        )
