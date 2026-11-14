# M22 Architecture — System Dynamics Simulation Engine

## Purpose

M22 adds a deterministic stock-and-flow execution paradigm to the AI-Assisted
Simulation Workbench. It represents accumulated quantities as **stocks**,
transfers as directed **flows**, and derived quantities as optional
**auxiliaries**. The engine is an additional backend; it does not replace DES,
ABM, mathematical, or data-driven simulation.

## Model contract

A schema-version-1 model contains:

- `time`: finite start/end values, a positive fixed time step, and an optional
  time-unit label;
- `solver`: `euler`, `heun`, or `rk4` (defaults to `rk4`);
- `stocks`: unique identifiers, initial numeric values, optional unit labels,
  and optional lower bounds;
- `flows`: unique names, a non-negative rate expression, and a source and/or
  target stock; `null` source/target denotes transfer to/from the external
  environment;
- `auxiliaries`: optional named equations derived from stocks, parameters,
  time, and other auxiliaries;
- `parameters`: named numeric constants; and
- `max_steps`: an execution guard with a bounded maximum.

At least one stock and one flow are required. A flow must connect at least one
stock and cannot transfer a stock to itself. Identifiers are validated and
expressions are parsed using the restricted M20 mathematical expression
language. Attribute access, indexing, imports, and arbitrary Python execution
are not part of the expression language. Auxiliary dependencies are
Topologically ordered; cyclic auxiliary definitions are rejected.

## Numerical execution

`SystemDynamicsBackend` performs fixed-step integration with Euler, Heun, or
fourth-order Runge–Kutta (RK4). For every step it evaluates auxiliary values,
flow rates, and stock derivatives. A source stock loses the flow rate and a
target stock gains it. Rates must be finite, non-negative, and within the
execution magnitude guard. Optional stock minimums are checked after each
integration step; the engine raises a validation error instead of silently
clipping an invalid stock value. The last step is shortened when necessary to
land exactly on the requested end time.

The native result contains timestamped stock, auxiliary, and flow-rate
snapshots; stock initial/final/minimum/maximum summaries; and cumulative flow
estimates integrated using the trapezoidal rule. M9 serializes the trace into
its normal execution result and preserves the result fingerprint. M10
parameter overrides/sweeps work through the normal parameter paths.

## Workbench integration

- **M7 readiness:** `system_dynamics` has a dedicated assessment for stock and
  flow structure, accumulation, temporal basis, and feedback signals. It
  reports missing definitions rather than assuming that a diagram is a
  validated theory.
- **M8 compilation:** a dedicated compilation paradigm validates the target
  model, creates a common simulation specification, and verifies conceptual
  element/parameter bindings and artifact provenance.
- **M9 execution:** the runner selects `SystemDynamicsBackend`, checks backend
  identity, applies parameter overrides, captures time-series traces, and
  serializes results.
- **M13 extension registry:** `builtin.system_dynamics.v1` exposes validation,
  compilation, execution, and result validation using the common adapter
  interface.
- **M14 web workbench:** the readiness API schema and browser paradigm
  selector accept `system_dynamics`.
- **CLI:** the local CLI exposes the paradigm for readiness and compilation.

## Demonstration

`scenarios/system_dynamics/sir_stock_flow.json` and
`python -m simulations.system_dynamics.demo` provide an illustrative SIR
stock-flow model. It demonstrates susceptible-to-infected and
infected-to-recovered flows. It is a synthetic example with invented
parameters, not empirical validation of disease dynamics.

## V1 boundaries

M22 deliberately does not yet implement delay structures, table/lookup
functions, stochastic flows, hybrid event coupling, automatic feedback-loop
discovery, dimensional unit algebra, adaptive or stiff solvers, partial
differential equations, or a dedicated interactive stock-flow diagram UI.
A model passing schema and execution checks is not thereby scientifically or
empirically validated. Feedback structure must be represented explicitly in
the conceptual model and approved equations.
