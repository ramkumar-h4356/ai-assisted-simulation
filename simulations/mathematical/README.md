# M20 — Mathematical Simulation Engine

M20 adds deterministic fixed-step ordinary differential equation (ODE) simulation and plugs it into the shared M7/M8/M9/M13 workbench lifecycle.

## Model format

```json
{
  "schema_version": 1,
  "name": "Exponential growth",
  "time": {"start": 0, "end": 10, "step": 0.1, "unit": "days"},
  "solver": "rk4",
  "variables": [
    {"name": "population", "initial_value": 100, "derivative": "growth_rate * population", "unit": "people"}
  ],
  "parameters": [
    {"name": "growth_rate", "value": 0.02, "unit": "1/day"}
  ]
}
```

The derivative expression is the right-hand side of `d(variable)/dt`. Each variable is updated from the same intermediate system state at every solver stage, so coupled systems use simultaneous ODE semantics. `t` and `time` refer to the current simulation time.

## Solvers

- `euler`: first-order explicit Euler method.
- `heun`: second-order improved Euler / explicit trapezoidal method.
- `rk4`: classical fourth-order Runge–Kutta method (default).

The configured step is fixed except the final step, which is clipped to end exactly at the requested end time. The model defaults to `max_steps: 200000`; the schema permits at most 500000 steps. M9 applies its separate 500000-record experiment trace budget as well.

## Safe expressions

Expressions are parsed and checked against a strict AST allow-list. Supported numeric operators are `+`, `-`, `*`, `/`, `**` and `%`; unary `+` and `-`; and the functions `abs`, `ceil`, `cos`, `exp`, `floor`, `log`, `log10`, `max`, `min`, `sin`, `sqrt` and `tan`, plus constants `pi` and `e`. Unknown identifiers, attribute access, indexing, imports, comprehensions, assignments, boolean expressions and keyword arguments are rejected. Evaluation does not call `eval`, `exec` or dynamically import user-supplied code. Exponent magnitude is bounded to 100.

## Workbench integration

- M7 reports the mathematical backend as implemented. A mathematical readiness gate can use an explicit quantitative relationship even when the conceptual project has no separate prose mechanism.
- M8 validates the model with `mathematical_model_from_dict`, requires at least one conceptual binding and a binding from a quantitative relationship or operational mechanism to a governing equation, and fingerprints the exact model data.
- M9 executes verified mathematical artifacts, captures the complete time series and summary metrics, and only allows parameter overrides on explicitly bound `user_parameter` paths.
- M13 registers `builtin.mathematical.v1` in the controlled extension registry. The same workspace lineage and artifact integrity controls apply.

## Example

Run the illustrative SIR model:

```powershell
python -m simulations.mathematical.demo
```

The values in `scenarios/mathematical/sir_rk4.json` are demonstration placeholders, not fitted epidemiological estimates or public-health advice.

## Boundaries

M20 does not implement adaptive or stiff solvers, algebraic equation systems, delay differential equations, partial differential equations, symbolic equation discovery, automatic causal inference, calibration against empirical data, or scientific validation. M12's dedicated mathematical time-series dashboard is not included in this milestone; the result trace is persisted for downstream visualization work.
