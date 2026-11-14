# M26 Architecture — Simulation Model Verification and Validation

## 1. Objective

M26 adds an explicit verification-and-validation layer after model compilation and execution. It checks whether an M8 executable specification is internally valid, whether an M9 execution is traceable to that exact specification, whether the saved trace is structurally and numerically consistent, and whether user-declared behavioral invariants hold.

M26 deliberately distinguishes:

- **Verification:** did we build and execute the model according to its declared executable specification?
- **Behavioral validation:** do the recorded behaviors satisfy the declared invariant(s) or checks?
- **Empirical validation:** does the model sufficiently represent an observed real-world system? This requires independent empirical evidence, data-quality assessment and domain review. M26 V1 does not claim to automate or prove this.

## 2. Pipeline

```text
M26 validation plan
        |
        v
Resolve normalized relative paths under artifact root
        |
        v
Load M8 artifact (strict schema + artifact/model fingerprints)
        |
        +--> Rebuild native model with the M9 paradigm parser
        |
        v
Load an explicitly supplied M9 result OR execute through M9
        |
        v
Verify exact M8 artifact/result lineage
        |
        v
Check execution status, finite trace, paradigm trace structure,
chronological order, initial-state consistency and fixed-step grid
        |
        v
Evaluate safe declarative invariants against each completed run
        |
        +--> Optional second M9 execution with the same configuration
        |    Compare modeled metrics/traces; exclude timestamps and wall time
        |
        v
Fingerprint M26 JSON report + export checks CSV
        |
        v
Optional import to M13 workspace with exact M8/M9 parent checks
```

## 3. Built-in verification checks

| Check | Verification behavior |
|---|---|
| `artifact_integrity` | Recompute M8 model and artifact fingerprints |
| `model_schema` | Rebuild the native model through the existing M9 parser for its paradigm |
| `execution_lineage` | Require the M9 result to reference the exact M8 artifact ID and fingerprint |
| `execution_completed` | Require all recorded runs to complete |
| `trace_finite` | Reject non-finite or unsupported trace values |
| `trace_shape` | Require the paradigm's expected trace collections |
| `time_order` | Require event times / time-series coordinates / ABM steps to be nondecreasing |
| `time_grid` | For mathematical and system-dynamics models, compare recorded steps/snapshots with M8 start/end/step |
| `initial_conditions` | Compare the M9 initial snapshot with M8 variable/stock/agent/data declarations where exposed by the trace contract |
| `repeatability` | Optionally execute the same M8 artifact again with the same M9 config and compare modeled outputs within tolerance |

For DES, the current V1 trace contract supports chronological event checks; an explicit entity/resource initial-state comparison is not defined and is reported as skipped. Data-driven checks verify its dataset reference and variable list; forecasts remain predictive rather than causal.

## 4. Declarative invariant operators

M26 does not execute Python or arbitrary expressions supplied by a validation plan. It uses a small, auditable trace-path grammar: dotted object keys plus `[]` to expand list items. Example: `time_series[].stocks.susceptible`.

| `check_type` | Required inputs | Meaning |
|---|---|---|
| `non_negative` | `trace_path`, optional `tolerance` | Every selected number is at least `-tolerance` |
| `bounds` | `trace_path`, one or both of `minimum`/`maximum` | Every selected number is inside the declared bounds within tolerance |
| `monotonic` | `trace_path`, `direction` | Values are increasing, decreasing, nondecreasing or nonincreasing |
| `conserved_sum` | `trace_path` resolving to objects, `fields`, `expected_value` | Selected fields sum to the expected constant at each observation |

Each invariant is applied independently to every completed M9 run. Missing paths, nonnumeric values, or empty selections fail closed.

## 5. Repeatability

When enabled, M26 re-executes the exact M8 artifact using the original M9 `ExperimentConfig`. It compares paradigm, run status, seeds, parameter values, metrics, trace and error details. It excludes `started_at`, `finished_at`, elapsed wall time and experiment IDs. ABM repeatability uses the recorded seed configuration; an ABM model without a usable seed cannot pass M9's reproducibility requirements.

Repeatability is evidence of deterministic replay under the recorded setup. It does not establish model validity.

## 6. Provenance and M13 integration

An M26 report preserves project/revision, paradigm, M8 artifact ID/fingerprint, M9 experiment ID/result fingerprint and optional repeatability evidence. The M13 workspace recognizes `validation_report` and validates the M26 report fingerprint. Import is accepted only when the exact M8 compilation artifact and M9 result are already linked in that workspace. The workspace workflow now includes a dedicated Model Verification and Validation stage.

## 7. CLI and application entry points

```powershell
python -m validation.cli --help
python -m validation.cli --plan scenarios/validation/plan_template.json --artifact-root . --output-dir outputs/validation
python -m validation.cli --inspect outputs/validation/<report>.json
```

The main application adds option 24 to run M26 and option 25 to inspect a saved report. M13 artifact import exposes the M26 Validation Report type.

## 8. Safety and scope

- Paths in plans must be normalized relative paths and are resolved under an explicit root.
- M8 loading verifies fingerprints before execution.
- M9 owns all simulation execution; M26 does not create a parallel execution engine.
- Trace invariants are declarative and use no `eval` or arbitrary code execution.
- Execution runs are bounded to 20 per validation plan.
- Reports are strict-schema JSON with a content fingerprint and CSV check export.
- V1 does not implement automated empirical calibration, statistical goodness-of-fit selection, causal discovery, formal proofs, sensitivity convergence analysis or domain-specific expert certification.

## 9. Acceptance criteria

1. Tampered or malformed M8 artifacts are rejected by M8 loading/verification.
2. Valid M8 models pass their native M9 parser.
3. M9 results must link to the exact M8 artifact.
4. Trace structure, finite values, order, initial state and fixed-step grid are checked where supported.
5. Declared invariants evaluate per run and fail closed on invalid paths or values.
6. Repeatability compares stable outputs under the same M9 configuration.
7. M26 reports round-trip with fingerprint verification and CSV export.
8. M13 accepts a validation report only with exact M8/M9 parents.
9. Existing milestone tests remain green.
