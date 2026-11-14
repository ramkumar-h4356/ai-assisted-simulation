"""Validated contracts for deterministic data-driven time-series models.

M21 implements a small, explicit VAR(p) contract. It forecasts observed
variables jointly from their lagged values. It does not infer causal rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class DataDrivenModelError(ValueError):
    """Raised when a data-driven model is invalid or unsafe to execute."""


@dataclass(frozen=True, slots=True)
class DataDrivenObservation:
    timestamp: float
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DataDrivenModel:
    name: str
    dataset_reference_id: str
    time_field: str
    time_unit: str
    variables: tuple[str, ...]
    observations: tuple[DataDrivenObservation, ...]
    lag_order: int
    train_fraction: float
    forecast_horizon: int
    ridge: float

    @property
    def time_step(self) -> float:
        return self.observations[1].timestamp - self.observations[0].timestamp

    @property
    def feature_count(self) -> int:
        return len(self.variables) * self.lag_order

    @property
    def sample_count(self) -> int:
        return len(self.observations) - self.lag_order

    @property
    def training_samples(self) -> int:
        return math.floor(self.sample_count * self.train_fraction)

    @property
    def holdout_samples(self) -> int:
        return self.sample_count - self.training_samples


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataDrivenModelError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise DataDrivenModelError(f"{path} must be finite")
    return result


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DataDrivenModelError(f"{path} must be a valid identifier")
    return value


def data_driven_model_from_dict(raw: Any) -> DataDrivenModel:
    """Parse and validate the portable M21 model-data format."""
    if not isinstance(raw, dict):
        raise DataDrivenModelError("model_data must be a JSON object")
    allowed = {
        "schema_version", "name", "dataset_reference_id", "time_field", "time_unit",
        "variables", "observations", "lag_order", "train_fraction",
        "forecast_horizon", "ridge", "description",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise DataDrivenModelError(
            f"model_data contains unknown field(s): {', '.join(sorted(unknown))}"
        )
    schema_version = raw.get("schema_version", 1)
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise DataDrivenModelError("schema_version must be the integer 1")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise DataDrivenModelError("name must be a non-empty string")
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise DataDrivenModelError("description must be a string")

    dataset_reference_id = raw.get("dataset_reference_id")
    if not isinstance(dataset_reference_id, str) or not dataset_reference_id.strip():
        raise DataDrivenModelError("dataset_reference_id must identify a conceptual dataset reference")
    if len(dataset_reference_id) > 200:
        raise DataDrivenModelError("dataset_reference_id must not exceed 200 characters")

    time_field = _identifier(raw.get("time_field"), "time_field")
    time_unit = raw.get("time_unit")
    if not isinstance(time_unit, str) or not time_unit.strip():
        raise DataDrivenModelError("time_unit must be a non-empty string")

    variables_raw = raw.get("variables")
    if not isinstance(variables_raw, list) or not 1 <= len(variables_raw) <= 12:
        raise DataDrivenModelError("variables must be an array containing 1 to 12 variable names")
    variables = tuple(_identifier(item, f"variables[{index}]") for index, item in enumerate(variables_raw))
    if len(variables) != len(set(variables)):
        raise DataDrivenModelError("variables must not contain duplicates")
    if time_field in variables:
        raise DataDrivenModelError("time_field must not also be a model variable")

    observations_raw = raw.get("observations")
    if not isinstance(observations_raw, list) or not 8 <= len(observations_raw) <= 10_000:
        raise DataDrivenModelError("observations must contain between 8 and 10000 rows")
    required_fields = {time_field, *variables}
    observations: list[DataDrivenObservation] = []
    for row_index, row in enumerate(observations_raw):
        path = f"observations[{row_index}]"
        if not isinstance(row, dict):
            raise DataDrivenModelError(f"{path} must be an object")
        missing = required_fields - set(row)
        extra = set(row) - required_fields
        if missing:
            raise DataDrivenModelError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
        if extra:
            raise DataDrivenModelError(f"{path} contains unexpected field(s): {', '.join(sorted(extra))}")
        timestamp = _number(row[time_field], f"{path}.{time_field}")
        values = tuple(_number(row[variable], f"{path}.{variable}") for variable in variables)
        if observations and timestamp <= observations[-1].timestamp:
            raise DataDrivenModelError("observation timestamps must be strictly increasing")
        observations.append(DataDrivenObservation(timestamp, values))

    step = observations[1].timestamp - observations[0].timestamp
    if step <= 0:
        raise DataDrivenModelError("observation time step must be positive")
    for index, item in enumerate(observations[2:], start=2):
        current_step = item.timestamp - observations[index - 1].timestamp
        if not math.isclose(current_step, step, rel_tol=1e-7, abs_tol=1e-9):
            raise DataDrivenModelError(
                "observations must be regularly spaced; irregular time series are not supported by VAR V1"
            )

    lag_order = raw.get("lag_order", 1)
    if isinstance(lag_order, bool) or not isinstance(lag_order, int) or not 1 <= lag_order <= 8:
        raise DataDrivenModelError("lag_order must be an integer between 1 and 8")
    feature_count = len(variables) * lag_order
    if feature_count > 24:
        raise DataDrivenModelError("lag_order multiplied by variable count must not exceed 24")

    train_fraction = _number(raw.get("train_fraction", 0.8), "train_fraction")
    if not 0.5 <= train_fraction <= 0.95:
        raise DataDrivenModelError("train_fraction must be between 0.5 and 0.95")
    forecast_horizon = raw.get("forecast_horizon", 5)
    if isinstance(forecast_horizon, bool) or not isinstance(forecast_horizon, int) or not 1 <= forecast_horizon <= 500:
        raise DataDrivenModelError("forecast_horizon must be an integer between 1 and 500")
    ridge = _number(raw.get("ridge", 1e-6), "ridge")
    if not 0 <= ridge <= 1_000_000:
        raise DataDrivenModelError("ridge must be between 0 and 1000000")

    sample_count = len(observations) - lag_order
    training_samples = math.floor(sample_count * train_fraction)
    holdout_samples = sample_count - training_samples
    if training_samples <= feature_count:
        raise DataDrivenModelError(
            f"training split must contain more than {feature_count} samples for {feature_count} lag features"
        )
    if holdout_samples < 1:
        raise DataDrivenModelError("training split must leave at least one holdout sample")

    return DataDrivenModel(
        name=name.strip(), dataset_reference_id=dataset_reference_id.strip(),
        time_field=time_field, time_unit=time_unit.strip(), variables=variables,
        observations=tuple(observations), lag_order=lag_order,
        train_fraction=train_fraction, forecast_horizon=forecast_horizon, ridge=ridge,
    )
