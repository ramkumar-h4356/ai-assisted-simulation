# M9 Architecture — Controlled Simulation Execution and Result Capture

## 1. Objective

M9 executes only a validated, integrity-checked M8 compilation artifact. It
provides bounded experiment settings, seeded ABM replications, deterministic
DES runs, structured traces, failure records and result persistence. It does
not reinterpret the theory, alter the M8 artifact, or claim that a successful
simulation proves the theory.

Supported execution targets remain limited to:

- DES V1 through the existing SimPy backend.
- ABM V1 through the existing native agent-based backend.

Mathematical and data-driven paradigms remain unexecutable until their model
contracts and backends are implemented.

## 2. Execution flow

```text
Saved M8 artifact
       |
       v
Strict M8 JSON load + SHA-256 integrity check
       |
       v
Check readiness metadata and supported paradigm
       |
       v
Rebuild native DES Scenario or ABM AgentModel
       |
       v
Check optional parameter sets against exact M8 user_parameter bindings
       |
       v
Create fresh model variants and re-parse/re-validate each variant
       |
       v
Check total execution count and estimated trace budget
       |
       v
For each parameter set and replication:
  - assign a reproducible ABM seed, or no seed for deterministic DES
  - execute through the existing paradigm backend
  - capture backend metrics and native trace
  - record timing or a bounded failure description
       |
       v
Link each run to artifact ID, artifact fingerprint,
project ID, conceptual revision and version
       |
       v
Fingerprint + atomically persist M9 result JSON
```

## 3. Package responsibilities

### `execution/models.py`

Defines validated contracts for `ExperimentConfig`, `MetricRecord`,
`RunRecord`, and `ExperimentResult`. Run counts are restricted to 1–100.
Trace data is copied into finite JSON-compatible values. Failed runs preserve a
bounded exception type and message without storing stack traces.

### `execution/runner.py`

Verifies the M8 artifact fingerprints before execution, reconstructs the
native target model through the existing strict parsers, and dispatches only
to an implemented backend. It does not accept arbitrary Python callbacks,
expressions or executable source from the artifact.

An experiment is rejected when its M7 metadata does not record
`ready_for_implementation_planning`, its artifact integrity check fails, its
paradigm is unsupported, its random-seed requirements are unmet, or its
estimated trace exceeds the configured internal safety budget.

### `execution/serialization.py`

Provides strict JSON decoding, result fingerprint validation and atomic file
replacement. Loading a modified result fails integrity verification.

### DES trace extension

`ScenarioResult` now retains the existing runtime event sequence in an `events`
field. The field has an empty-tuple default so existing positional construction
remains compatible. M9 serializes arrivals, service starts and completions,
plus entity and resource metrics.

### `main.py`

Option 9 loads a recent or selected M8 artifact, gathers bounded experiment
settings and executes it. Option 10 loads and verifies a saved M9 result and
prints a compact summary. Detailed event logs and agent histories remain in
the JSON result file.

## 4. Reproducibility and random seeds

ABM V1 uses `random.Random(model.random_seed)`. M9 uses an explicit
`ExperimentConfig.base_seed` when supplied; otherwise it uses the seed stored
in the compiled ABM model. Run `i` receives `base_seed + i - 1`. A compiled ABM
with no seed must be supplied one before M9 will execute it.

DES V1 has no stochastic behavior or random-number-generator input. Repeated
DES runs therefore repeat the same deterministic scenario. M9 records a null
seed and rejects a supplied base seed instead of pretending that the DES
backend consumed it.

## 5. Explicit parameter variation

`ExperimentConfig.parameter_sets` can contain named groups of scalar
`ParameterOverride` values. A path can be changed only when the exact path is
listed in the M8 artifact as a `user_parameter` binding. Fields bound to
conceptual elements are not eligible for variation. The runner also rejects
missing paths, overlapping paths, scalar type changes and attempts to override
`random_seed` (which is controlled by the experiment seed schedule).

Each parameter-set variant is applied to a fresh copy of the M8 model data and
re-parsed by the native model parser before any execution begins. The original
M8 artifact is not changed. `runs` means replications per parameter set;
`runs × parameter-set count` is limited to 100 total executions. When no sets
are supplied, M9 executes one `baseline` set with no overrides.

## 6. Captured outputs

Each successful run stores:

- Backend-neutral metrics and units.
- DES: ordered runtime events, per-entity metrics and per-resource metrics.
- ABM: the initial and per-step population snapshots, each agent's state and
  attributes, rule-evaluation outcomes and final state counts.
- Run number, parameter-set name and exact parameter overrides, effective
  seed (if applicable), UTC start/end timestamps and elapsed wall-clock
  duration.

A failed run stores an empty trace and metrics plus its exception type and a
message limited to 2,000 characters. By default the experiment continues after
a run failure so later seeded runs can still be inspected. The overall result
is `completed`, `partial` or `failed` according to the recorded runs.

## 7. Bounds and integrity

- 1–100 runs per experiment.
- Estimated trace record budget: 500,000 records per experiment.
- Artifact ID and whole-artifact fingerprint are included in every result.
- Project ID, title, exact conceptual revision ID and revision version are
  copied from the M8 artifact.
- M9 result JSON has a SHA-256 integrity fingerprint; loading verifies it.
- Result files are written to a temporary sibling and atomically replaced.

The fingerprints detect accidental or unreviewed content changes; they are
not digital signatures and do not establish who created an artifact.

## 8. Non-goals and limitations

M9 does not infer parameter values, automatically generate a parameter grid,
optimize scenarios, compare statistical confidence intervals, perform
sensitivity analysis, or establish empirical validity. Parameter changes are
limited to explicit user-supplied values at M8 `user_parameter` paths. A run
only reports what the supplied model and settings produced.
The result trace is a machine-readable record, not yet a visualization or
scientific interpretation layer. Simulation budgets are record-count guards,
not hard wall-clock timeouts.

## 9. Next step

A following milestone can provide experiment comparison and analysis across
saved M9 runs: distribution summaries, automatic parameter-grid generation,
sensitivity analysis, visual comparison and interpretation while maintaining
the same provenance links and uncertainty boundaries.
