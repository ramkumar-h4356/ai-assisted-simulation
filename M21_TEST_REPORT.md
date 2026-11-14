# M21 Test Report — Data-Driven Simulation Engine

## Verification environment

The M21 implementation was tested in the packaging container using Python
3.13. The test environment does not include the optional `simpy` or `groq`
packages required by the older DES engine/interpreter test modules.

## Results

- `python -m compileall -q simulations/data_driven readiness compilation execution workbench main.py` — passed.
- Integration regression selection covering data-driven, readiness, compilation, execution, core, workbench, simulation-studio replay and mathematical tests — **162 passed, 1 warning**.
- `python -m pytest -q --ignore=tests/des` — **505 passed, 1 warning**.
- `python -m pytest -q tests/des/test_replay.py` — **15 passed**.
- `python -m simulations.data_driven.demo` — completed and emitted holdout metrics plus a seven-step forecast.

The broad `--ignore=tests/des` run intentionally excludes the DES test directory
because this packaging environment does not have `simpy` and `groq`. The
separate M19 DES replay tests are pure trace-projection tests and passed
independently.

## Full-suite collection limitation

`python -m pytest -q` was attempted. Collection stopped with nine import errors:

- `ModuleNotFoundError: No module named 'groq'` in the DES AI interpreter and pipeline tests.
- `ModuleNotFoundError: No module named 'simpy'` in the DES runtime/backend tests.

These are missing environment dependencies, not failing M21 assertions. The
user's Windows environment should run the full suite after applying M21.

## Coverage delivered

- strict model schema and numeric/time-series validation;
- regular sampling and bounds for variables, observations, lags, training
  fraction, forecast horizon and ridge strength;
- deterministic ridge-VAR fit, coefficient generation, holdout metrics,
  persistence baseline and recursive forecast;
- explicit CSV column selection, file/row bounds and shared model validation;
- M7 data-driven readiness and implemented backend status;
- M8 exact DATASET evidence-reference binding and artifact integrity;
- M9 deterministic execution, parameter overrides, trace serialization and
  result fingerprint round-trip;
- M13 extension registration and end-to-end workspace workflow;
- M19 replay and M20 mathematical regression selections.

## Interpretation of the demo

The bundled demonstration is synthetic and generated from a deterministic
coupled process. Its near-perfect fit is a code-path demonstration only; it is
not evidence of forecasting performance on real data.
