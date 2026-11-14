"""Bounded CSV ingestion for explicit user-selected M21 datasets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from simulations.data_driven.model import data_driven_model_from_dict


MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 10_000


def load_csv_model_data(
    path: str | Path,
    *,
    name: str,
    dataset_reference_id: str,
    time_field: str,
    time_unit: str,
    variables: Sequence[str],
    lag_order: int = 1,
    train_fraction: float = 0.8,
    forecast_horizon: int = 5,
    ridge: float = 1e-6,
) -> dict:
    """Read an explicitly selected local CSV and return validated M21 model data.

    The CSV is read once and its selected numeric columns are embedded in the
    returned model-data dictionary. The source path is not persisted. Remote
    URLs and automatic filesystem discovery are deliberately unsupported.
    """
    if isinstance(variables, (str, bytes)) or not isinstance(variables, Sequence) or not variables:
        raise ValueError("variables must be a non-empty sequence of column names")
    variables = tuple(variables)
    if any(not isinstance(item, str) or not item.strip() for item in variables):
        raise ValueError("variables must contain non-empty column-name strings")
    if len(variables) != len(set(variables)):
        raise ValueError("variables must not contain duplicate column names")
    if not isinstance(time_field, str) or not time_field.strip():
        raise ValueError("time_field must be a non-empty string")
    if time_field in variables:
        raise ValueError("time_field must not also be a model variable")
    source = Path(path)
    try:
        if not source.is_file():
            raise ValueError(f"CSV dataset is not a file: {source}")
        size = source.stat().st_size
        if size > MAX_CSV_BYTES:
            raise ValueError(f"CSV dataset exceeds the {MAX_CSV_BYTES:,}-byte ingestion limit")
        if size == 0:
            raise ValueError("CSV dataset is empty")
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if not headers:
                raise ValueError("CSV dataset must include a header row")
            if len(headers) != len(set(headers)):
                raise ValueError("CSV header names must be unique")
            required = {time_field, *variables}
            missing = required - set(headers)
            if missing:
                raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
            rows = []
            for row_index, row in enumerate(reader, start=2):
                if row_index - 1 > MAX_CSV_ROWS:
                    raise ValueError(f"CSV dataset exceeds the {MAX_CSV_ROWS:,}-row ingestion limit")
                if None in row or any(row.get(column) is None for column in required):
                    raise ValueError(f"CSV row {row_index} has missing or excess columns")
                converted = {}
                for column in (time_field, *variables):
                    raw_value = row[column].strip()
                    if not raw_value:
                        raise ValueError(f"CSV row {row_index} has an empty value for {column!r}")
                    try:
                        converted[column] = float(raw_value)
                    except ValueError as error:
                        raise ValueError(
                            f"CSV row {row_index} value for {column!r} is not numeric"
                        ) from error
                rows.append(converted)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError(f"Could not read CSV dataset: {error}") from error

    model_data = {
        "schema_version": 1,
        "name": name,
        "dataset_reference_id": dataset_reference_id,
        "time_field": time_field,
        "time_unit": time_unit,
        "variables": list(variables),
        "observations": rows,
        "lag_order": lag_order,
        "train_fraction": train_fraction,
        "forecast_horizon": forecast_horizon,
        "ridge": ridge,
    }
    # Reuse the canonical parser so CSV and JSON inputs have identical rules.
    data_driven_model_from_dict(model_data)
    return model_data
