# M20 Architecture — Mathematical Simulation Engine

## Purpose

M20 adds a deterministic fixed-step ordinary differential equation (ODE) execution paradigm to the existing simulation workbench. It closes the earlier gap where M7 could assess mathematical suitability but M8/M9 had no mathematical execution backend.

The engine accepts explicit, user-authored equations. It does not infer equations from prose, infer causality from data, or decide whether a scientific theory is valid.

## Execution flow

1. **Conceptual revision (M4–M6):** preserve the original idea, concepts, properties, relationships, mechanisms, assumptions and evidence. A mathematical model needs measurable variables and an explicit governing quantitative relationship.
2. **Readiness (M7):** the mathematical paradigm is reported as implemented. Explicit quantitative relationships can satisfy the governing-rule check when the project does not separately express that rule as a prose mechanism. A set of numeric properties alone remains insufficient.
3. **Compilation (M8):** a mathematical profile maps at least one target field to a conceptual element and maps a governing equation to a quantitative relationship or an operational mechanism. The target JSON is validated against the M20 schema, and model plus provenance fingerprints are persisted in the artifact.
4. **Execution (M9):** M9 verifies the M8 artifact before dispatching to `MathematicalBackend`. The run is deterministic, rejects random seeds, applies only explicitly bound parameter overrides, and stores the time-series trace and summary metrics in the normal experiment-result envelope.
5. **Workspace (M13):** `builtin.mathematical.v1` is available through the extension registry and the workspace lifecycle. Existing project/revision lineage and integrity controls remain in force.

## Main components

- `simulations/mathematical/model.py`: portable schema parsing, scalar/finite-value checks, identifier validation, solver/time bounds and safe expression AST validation.
- `simulations/mathematical/backend.py`: numerical derivative evaluation, coupled-state integration, fixed-step Euler, Heun and RK4, time-series snapshots and final summaries.
- `compilation/compiler.py`: mathematical paradigm mapping, native model validation, provenance binding rules and backend identity.
- `execution/runner.py`: integrity-checked backend dispatch, mathematical trace serialization, trace budget estimation and deterministic-run guard.
- `workbench/extensions.py`: controlled mathematical backend registration for the project workspace.

## Numerical semantics

Each variable stores its current value and an explicit derivative expression representing `d(variable)/dt`. At each solver stage, all derivatives are evaluated against the same intermediate system state. This is important for coupled systems: a variable's derivative at an RK4/Heun stage must not see another variable already advanced to a different stage state.

The configured step is fixed. The final interval is shortened when necessary so the integration ends exactly at `time.end`. The schema defaults to 200,000 steps and caps a model at 500,000 steps. M9 separately enforces its experiment-wide trace-record budget.

Supported methods:

- Euler: first-order explicit method.
- Heun: second-order explicit trapezoidal method.
- RK4: classical fourth-order Runge–Kutta method.

## Expression security

User equations are parsed into Python's expression AST and evaluated by a constrained interpreter. The accepted grammar is limited to numeric constants, known variable/parameter names, `t`/`time`, `pi`/`e`, approved arithmetic operators and an allow-list of scalar math functions. Attribute access, indexing, imports, comprehensions, assignments, boolean expressions, unknown identifiers and keyword arguments are rejected. The system does not use `eval`, `exec` or dynamic imports to execute model text. Exponent magnitude is bounded.

## Trace contract

M9 stores:

- solver name, start/end time and time unit;
- number of steps and variable-unit metadata;
- a time-series array containing each saved time and all variable values at that time;
- per-variable initial, final, minimum and maximum summaries.

These data remain inside the existing integrity-checked M9 result format and can be consumed by future visualization milestones.

## Example

`scenarios/mathematical/sir_rk4.json` is an illustrative three-variable SIR ODE system. It is a software example with placeholder parameters, not a fitted model, epidemiological estimate or public-health recommendation. Run it with:

```powershell
python -m simulations.mathematical.demo
```

## Explicit limitations

M20 does not add adaptive step-size control, stiff-system solvers, differential-algebraic equations, delay differential equations, partial differential equations, symbolic algebra, equation discovery from natural language, dataset-based causal discovery, parameter calibration, uncertainty analysis specific to ODE solver error, or scientific validation. M12's dedicated mathematical time-series dashboard is also outside this milestone; M20 persists numerical traces but does not add a dedicated visualization screen.
