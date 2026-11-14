# M21 Architecture — Data-Driven Simulation and Time-Series Forecasting

## 1. Objective

M21 adds an executable data-driven paradigm to the simulation workbench. Its
first backend is a deterministic ridge-regularized vector autoregression
(VAR(p)) for regularly spaced, complete, multivariate numeric time series.
It is designed to forecast observed variables jointly from their lagged
values and to preserve the dataset's conceptual provenance through M7, M8,
M9 and the M13 workspace extension registry.

M21 is predictive, not causal. Statistical associations in the fitted model
are not automatically converted into mechanisms, rules or scientific claims.
The backend does not prove or validate the theory that motivated the dataset.

## 2. End-to-end flow

```text
M4 conceptual revision
  - DATASET evidence reference
  - at least two numeric properties with units
  - temporal property
            |
            v
M7 data-driven readiness
  - strong/possible qualitative fit
  - dataset metadata is not file validation
  - no causal mechanism is manufactured
            |
            v
User-approved M8 CompilationProfile
  - exact project and revision IDs
  - dataset_reference_id bound to exact DATASET evidence ID
  - regular numeric observations embedded in model_data
  - explicit time field, variables, lag and forecast controls
            |
            v
M8 strict provenance + native schema validation
            |
            v
Integrity-checked CompilationArtifact
            |
            v
M9 deterministic DataDrivenBackend
  - chronological train/holdout partition
  - ridge VAR(p) fit
  - one-step walk-forward holdout evaluation
  - recursive future forecast
            |
            v
M9 metrics + forecast trace + fingerprints
            |
            v
M13 workspace built-in Data-Driven V1 extension
```

## 3. Model contract

`simulations/data_driven/model.py` defines the immutable `DataDrivenModel` and
`DataDrivenObservation` contracts plus `data_driven_model_from_dict`.

The version-1 `model_data` object contains:

- `schema_version`: integer `1`.
- `name`: non-empty model name.
- `dataset_reference_id`: ID of a DATASET evidence reference in the exact M4
  revision selected by M8.
- `time_field` and `time_unit`: identifier for the numeric time/index column
  and its unit.
- `variables`: 1–12 unique numeric series names. The time field cannot also
  be a model variable.
- `observations`: 8–10,000 rows. Each row contains exactly the time field and
  every selected variable; all values must be finite numbers.
- `lag_order`: integer 1–8, with total lag features (`variables × lag_order`)
  limited to 24.
- `train_fraction`: chronological training fraction from 0.5 to 0.95.
- `forecast_horizon`: integer 1–500.
- `ridge`: regularization strength from 0 to 1,000,000; default `1e-6`.

Observations must have strictly increasing and regularly spaced numeric time
indices. Irregular sampling, missing values and categorical inputs are not
silently repaired; they are rejected by the V1 parser.

## 4. CSV ingestion

`simulations/data_driven/csv_io.py` exposes `load_csv_model_data(...)` for an
explicitly selected local CSV path. The user/script names the time column and
model columns. The helper:

- limits the CSV to 10 MiB and 10,000 data rows;
- requires a unique header row and all selected columns;
- rejects missing/extra row cells, empty values and non-numeric selected data;
- selects only the named columns;
- passes the constructed object through the canonical model validator; and
- returns portable model data with observations embedded, without retaining
  the original filesystem path.

No remote URL fetching, automatic filesystem discovery or automatic variable
selection is performed.

## 5. VAR(p) method and evaluation semantics

For a vector of observed variables \(x_t\), the backend estimates an equation
for each output variable using the lagged vector of all selected variables:

\[
 x_t = c + A_1 x_{t-1} + A_2 x_{t-2} + \cdots + A_p x_{t-p} + \epsilon_t.
\]

M21 fits each output equation using ridge-regularized linear least squares.
Predictors and target are standardized during fitting; the returned
coefficients and intercept are transformed back to the original units. The
small dense normal-equation system is solved with Gaussian elimination and
partial pivoting. A numerical singularity or non-finite/unsupported magnitude
causes a bounded model error rather than an invalid trace.

The chronological split is formed after the initial lag window. The first
`floor((n - p) × train_fraction)` target rows are used for fitting. The
remaining target rows are held out. Holdout evaluation is **one-step
walk-forward with observed history**: each prediction uses the actual prior
observations available before that target time. The persistence baseline
predicts the previous observed value for each variable.

After holdout evaluation, the future forecast begins with the final `p`
observed rows. Forecasts are **recursive**: each newly predicted row becomes
input to the next forecast step. The M9 trace records the explicit evaluation
strategy string so this distinction is visible to downstream consumers.

## 6. Output and reproducibility

`DataDrivenBackend` returns:

- fitted intercept and lag coefficients for every output variable;
- training and holdout sample counts;
- MAE, RMSE and R-squared on the chronological holdout;
- persistence-baseline MAE and RMSE;
- actual/predicted/baseline rows for each holdout timestamp;
- recursive forecast points with time and variable values; and
- dataset reference, time step, lag order, ridge strength and evaluation
  strategy metadata.

M9 serializes the model output into its normal result trace and fingerprints
both the source compilation artifact and the result. Data-Driven V1 is
deterministic and does not consume a random seed; M9 rejects an experiment
base seed for this paradigm. Parameter overrides are permitted only at exact
M8 `user_parameter` paths, such as an explicitly declared forecast horizon.

The M13 extension registry contains `builtin.data_driven.v1` with the normal
validate, compile, execute, serialize-result and validate-result lifecycle
capabilities. The registry remains explicit; arbitrary third-party code is
not dynamically loaded.

## 7. Readiness and provenance boundaries

M7's data-driven evaluator requires dataset-typed evidence, at least two
numeric properties and a temporal property for a strong qualitative fit.
It also reports that dataset accessibility and data quality have not been
verified at the conceptual-assessment stage. A data-driven readiness path
does not require a causal operational mechanism because M21 estimates
predictive associations only. If the conceptual revision contains an
unresolved mechanism, M7 can still expose it as a non-blocking clarification
for this selected paradigm; it does not block forecasting readiness.

M8 checks that `dataset_reference_id` matches the ID of a DATASET evidence
reference in the exact selected revision and that the corresponding profile
binding points to that reference. The compiled artifact embeds validated
observations, making execution independent of the original CSV path. A
citation or evidence reference alone is not substituted for the actual
observations.

## 8. Safety and limits

- Pure Python implementation; no NumPy, pandas or scikit-learn runtime
  dependency is required for the M21 VAR backend.
- Input size is bounded by row, variable, feature and horizon limits.
- Arbitrary code, expressions and external file paths are not executed by the
  backend.
- Values and generated predictions must be finite; excessive forecast
  magnitudes are rejected.
- V1 does not support irregular timestamps, imputation, categorical values,
  exogenous future variables, probabilistic intervals, adaptive model
  selection, automatic feature discovery or causal identification.
- The holdout is a single chronological segment; it is not repeated
  backtesting or external validation.
- M21 stores forecast traces in M9 results. Dedicated M12 data-driven
  dashboard adapters are not included in this milestone.
- A successful fit does not establish causal direction, scientific validity
  or generalization to future regimes or other datasets.

## 9. Main additions and integration points

- `simulations/data_driven/model.py`: strict model parser and immutable data
  contracts.
- `simulations/data_driven/backend.py`: ridge VAR(p), holdout metrics and
  recursive forecast.
- `simulations/data_driven/csv_io.py`: bounded explicit CSV ingestion.
- `simulations/data_driven/demo.py`: synthetic example runner.
- `readiness/engine.py`: M7 data-driven backend availability and readiness
  exception for dataset-grounded predictive models.
- `compilation/compiler.py`: M8 data-driven validation, exact dataset
  reference binding and native specification creation.
- `execution/runner.py`: M9 execution dispatch, deterministic seed policy,
  trace budget and trace serialization.
- `workbench/extensions.py`: M13 Data-Driven V1 lifecycle adapter.
