# Milestone 21 — Data-Driven Simulation Engine

## Delivered

M21 adds an executable, deterministic data-driven simulation backend based on
ridge-regularized VAR(p) forecasting of regularly spaced multivariate numeric
time series.

The milestone includes a strict immutable model contract, bounded explicit
CSV ingestion, chronological training/holdout evaluation, one-step walk-forward
predictions, persistence-baseline metrics, recursive future forecasts, M9
trace serialization, exact dataset-evidence provenance binding, M7 readiness
integration, M8 compilation integration and a built-in M13 lifecycle adapter.
A synthetic coupled-series scenario and runnable demo are included.

## Files and integration

See `M21_ARCHITECTURE.md` for the full contract, equations, data flow, output
semantics, safety constraints and limitations. `M21_TEST_REPORT.md` records
build-container verification and the optional-dependency limitation for the
full DES suite. `M21_APPLY_STEPS.txt` contains Windows installation and test
commands.

## Important boundaries

M21 is a predictive model family. Estimated VAR coefficients are statistical
associations and are not automatically causal rules, mechanisms or physical
laws. M7 does not validate the actual dataset file; M8 requires the user to
provide selected observations and bind them to the exact DATASET evidence
reference. CSV values are embedded in the compiled artifact for portability.

V1 requires complete, regularly spaced numeric observations. It does not
provide imputation, categorical/exogenous variables, probabilistic forecast
intervals, automatic feature selection, causal discovery or dedicated M12
visualization. A single chronological holdout is not external validation or
repeated backtesting.

## Verification status

M21's focused integration suite and broad non-DES regression suite passed in
the packaging container. Full-suite collection was blocked only because the
container lacked the optional `simpy` and `groq` dependencies. The Windows
repository must run the complete test suite before M21 is committed.
