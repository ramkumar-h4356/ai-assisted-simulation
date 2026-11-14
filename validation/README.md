# M26 — Simulation Model Verification and Validation

M26 verifies the integrity and native schema of an M8 compiled model, checks a linked M9 execution result or runs the model through M9, inspects paradigm-specific traces and evaluates safe declarative invariants.

## Quick start

1. Create an M8 artifact and save it under `outputs/m8_artifacts/`.
2. Copy `scenarios/validation/plan_template.json` and replace the `artifact_path` placeholder with the actual filename. The standard main-menu M8 workflow writes artifacts directly under `outputs/`; keep the path relative to the selected artifact root.
3. Add invariants that are explicitly justified by the model. The included example is for a system-dynamics SIR model and checks population conservation.
4. Run:

```powershell
python -m validation.cli --plan scenarios/validation/plan_template.json --artifact-root . --output-dir outputs/validation
```

Inspect a report:

```powershell
python -m validation.cli --inspect outputs/validation/<report>.json
```

## Verification versus validation

- **Verification** asks whether the executable model and its recorded outputs are internally consistent with their declared specification: integrity fingerprints, native parser validation, initial-state consistency, trace shape, finite values and ordered simulation time.
- **Validation** evaluates user-declared behavioral invariants over the M9 trace. It is conditional on the model, assumptions, parameters, solver, time step and available evidence.
- **Repeatability** re-executes the exact artifact with the same M9 configuration and compares modeled outputs while excluding wall-clock metadata.

Passing M26 does not prove scientific truth, empirical fit or causal correctness. External empirical validation remains dependent on suitable independent evidence and expert review.

## Safe invariant path grammar

Use dotted object keys and `[]` to expand list items. Example: `time_series[].stocks.susceptible`. M26 does not evaluate Python or arbitrary expressions.

Supported `check_type` values:

- `non_negative`: every selected value must be greater than or equal to `-tolerance`.
- `bounds`: every selected value must lie within declared `minimum` and/or `maximum`.
- `monotonic`: selected numeric values must satisfy `direction` (`increasing`, `decreasing`, `nondecreasing`, `nonincreasing`).
- `conserved_sum`: each selected object must contain `fields` whose sum equals `expected_value` within `tolerance`.

## Plan options

`artifact_path` is required and must be a normalized relative path. `execution_result_path` may refer to a saved M9 result; otherwise `execute_if_missing` must be true and M26 executes through M9. `execution_runs` is bounded to 1–20. For ABM repeatability, the compiled model must contain a random seed or the plan must provide `execution_base_seed`.
