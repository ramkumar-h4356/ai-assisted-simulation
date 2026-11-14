# Data-driven simulation backend (M21)

M21 adds a deterministic, explicit VAR(p) forecasting workflow for regularly
spaced multivariate numeric observations.

## Model contract

An M8 profile's `model_data` contains:

- `dataset_reference_id`: the ID of a `DATASET` evidence reference in the exact
  conceptual revision. M8 requires a conceptual binding to that ID.
- `time_field` and `time_unit`: a numeric, strictly increasing, regularly
  spaced time index and its unit.
- `variables`: 1–12 numeric series names.
- `observations`: 8–10,000 rows. Every row contains the time field and every
  variable, with finite numeric values and no missing values.
- `lag_order`: 1–8 prior rows used as predictor inputs.
- `train_fraction`: chronological training share (0.5–0.95).
- `forecast_horizon`: recursive forecast length (1–500).
- `ridge`: non-negative regularization strength (default `1e-6`).

The total lag-feature count is limited to 24. Data is validated before
compilation and again before execution. The input observations are embedded in
the M8 artifact, so artifacts are portable and do not depend on a local path
remaining available after compilation.

## CSV import

Use the explicit CSV helper from a script or notebook:

```python
from simulations.data_driven import load_csv_model_data

model_data = load_csv_model_data(
    r"D:\datasets\observations.csv",
    name="Observed system",
    dataset_reference_id="dataset-reference-id-from-M4",
    time_field="time_index",
    time_unit="days",
    variables=("rainfall", "temperature"),
    lag_order=2,
    train_fraction=0.8,
    forecast_horizon=7,
)
```

The importer reads only the explicitly named local file, enforces a 10 MiB file
limit and a 10,000-row limit, selects only the requested columns and reuses the
same model validator as JSON input. Time and model fields must be numeric in V1.
The source file path is not persisted in the model.

## Execution and interpretation

`DataDrivenBackend` fits one ridge-linear equation per output series using the
lagged values of all selected series. The last portion of the observations is
held out chronologically and evaluated using one-step walk-forward predictions
with the actual prior observations available at each test point. The final
forecast is recursive: each predicted row becomes input to the next step.

Output includes fitted intercepts and coefficients, holdout predictions,
MAE/RMSE/R-squared and persistence-baseline errors, plus the forecast series.
The M9 artifact and result fingerprints preserve model and result integrity.

This is a predictive statistical model, not a causal model. Coefficients and
forecast performance do not prove causal relationships, scientific validity
or real-world generalization. The holdout is one chronological segment and is
not a substitute for repeated backtesting, external validation or uncertainty
analysis. V1 does not support irregular timestamps, missing-value imputation,
categorical variables, exogenous future features or data-driven M12 rendering.
