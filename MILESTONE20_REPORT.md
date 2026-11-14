# Milestone 20 — Mathematical Simulation Engine

## Objective

Implement a first executable mathematical paradigm so the platform can move beyond the existing DES and ABM execution backends. M20 provides fixed-step ODE simulation with explicit equations and connects it to the established workbench lifecycle.

## Delivered

- New mathematical model package with strict portable JSON schema and validation.
- Safe expression parser/interpreter that does not execute model text as Python code.
- Euler, Heun and classical RK4 solvers.
- Correct coupled-system stage evaluation using simultaneous intermediate states.
- Time-series snapshots, variable summaries and deterministic numerical execution.
- M7 mathematical readiness status updated to implemented, with explicit quantitative relationships accepted as governing rules.
- M8 mathematical compilation with schema validation, conceptual provenance binding and integrity fingerprints.
- M9 mathematical backend dispatch, verified artifact execution, parameter override handling, bounded time-series traces and saved results.
- M13 controlled extension registration for `builtin.mathematical.v1`.
- Illustrative SIR scenario, CLI demo, documentation and integration/regression tests.

## Verification

- 88 focused integration tests passed.
- 482 tests passed with `tests/des` excluded.
- 20 M19 DES replay regression tests passed.
- SIR demo completed 240 RK4 steps to 60 days; the total state remained 1000.000000.
- Full-suite collection in the build environment was blocked by missing existing `simpy` and `groq` dependencies. Windows full-suite verification is required before commit.

## Not included

Adaptive/stiff solvers, PDE/DAE/delay systems, symbolic equation discovery, calibration, automated causal inference, scientific validation, and a dedicated mathematical M12 dashboard are not part of M20.
