# M10 Architecture — Experiment Design and Comparative Analysis

## 1. Objective

M10 turns the controlled M9 execution records into repeatable parameter-sweep
experiments and provenance-aware comparative summaries. It does not change the
M8 model artifact, M9 runner, DES engine or ABM engine.

M10 currently supports:

- Cartesian parameter grids over scalar M8 fields explicitly bound as
  `user_parameter`.
- Optional baseline execution using the exact values already stored in the
  compiled M8 artifact.
- Bounded replications through the existing M9 execution service.
- Descriptive statistics per parameter-set variant.
- Numeric deltas against a named baseline, including percentage change when
  the baseline mean is non-zero.
- Marginal factor-level summaries for each varied parameter.
- Comparison of multiple M9 results, provided they refer to the same exact M8
  artifact and conceptual revision.
- Integrity-checked JSON reports and spreadsheet-friendly CSV summaries.

## 2. Architecture

```text
Verified M8 artifact
       |
       v
M10 GridFactor definitions
       |
       v
Validate exact user_parameter bindings, scalar types and target paths
       |
       v
Build bounded Cartesian parameter sets (+ optional compiled baseline)
       |
       v
Existing M9 execute_artifact(artifact, ExperimentConfig)
       |
       v
Saved M9 result JSON (full traces, metrics, seeds, provenance)
       |
       +------ optional additional M9 results from the same M8 artifact
       |
       v
M10 analyze_results(...)
       |
       +--> summaries per named parameter set
       +--> baseline metric deltas
       +--> marginal summaries per factor value
       +--> limitations / failure warnings
       |
       v
Fingerprint + save M10 JSON and export CSV
```

### `experimentation/models.py`

Defines immutable contracts for grid factors, numeric/categorical metric
summaries, baseline deltas, variant summaries, factor-level summaries and the
revision-bound analysis report. Numeric summaries include sample size, mean,
population standard deviation, median, minimum and maximum. Categorical
metrics are summarized as counts. M10 also derives additional metrics from the
stored traces: ABM final-snapshot numeric agent-attribute mean/sum/minimum/
maximum by agent type, DES entity-level mean waiting/service/time-in-system,
and per-resource utilization and waiting/service metrics. These derived values
use only data retained in the M9 trace.

### `experimentation/grid.py`

Validates the M8 artifact fingerprint and the explicit M8 `user_parameter`
binding list. It accepts only exact, existing scalar paths and level values of
the same Python/JSON scalar type as the compiled baseline. It rejects path
traversal outside the declared model structure, duplicate/overlapping factors,
conceptual-element fields, non-finite values and oversized Cartesian grids.

The optional `baseline` variant writes the current M8 values explicitly into
the run provenance. If the Cartesian levels already contain that exact
combination, it is not executed twice.

### `experimentation/analysis.py`

Consumes M9 result objects only after recalculating and checking each result
fingerprint. Every input must share the same artifact ID and fingerprint,
project, conceptual revision, paradigm and backend. Duplicate experiment IDs
and conflicting definitions for a named parameter set are rejected.

Failed runs remain counted but are excluded from metric aggregation. Metric
units and value types must remain consistent across variants. Numeric metrics
are summarized descriptively; categorical metrics are reported as frequency
counts. Variant-level deltas compare each variant's metric mean with the
selected baseline variant's mean. Factor-level summaries pool successful runs
at each observed factor value and compare to the corresponding baseline level
when one is available. ABM attribute metrics use the final recorded population
snapshot, not a time average across all snapshots.

### `experimentation/serialization.py`

Provides strict JSON parsing, SHA-256 report fingerprint verification, atomic
writes and CSV export. A fingerprint detects content changes; it is not a
cryptographic author signature.

### CLI

- Option 11: generate and run a parameter sweep from a JSON grid-factor file,
  optionally add earlier M9 results from the same exact M8 artifact, then save
  M10 JSON and CSV analysis.
- Option 12: inspect an integrity-verified M10 report.

## 3. Grid-factor file

The CLI expects a top-level JSON array. Example for an ABM artifact whose M8
profile explicitly binds both paths as user parameters:

```json
[
  {
    "target_path": "agents[0].attributes.trust",
    "levels": [0.2, 0.5, 0.8]
  },
  {
    "target_path": "termination.value",
    "levels": [5, 10, 15]
  }
]
```

The example is illustrative only. The path names and scalar types must match
the selected artifact's actual model data and M8 `user_parameter` bindings.
M10 never guesses a parameter mapping from a conceptual idea.

## 4. Limits

- The Cartesian design is limited to at most 100 total M9 executions. M10
  reduces the allowed number of variants automatically based on replications.
- Only scalar parameters with exact M8 `user_parameter` bindings are varied.
- The existing M9 trace-record budget and backend limits still apply.
- Only implemented DES V1 and ABM V1 M9 backends can be executed.
- All results combined into one report must refer to the same exact M8 artifact
  and conceptual revision.
- Numeric and categorical summaries use successful runs only; failed runs are
  still shown in variant run counts and warnings.

## 5. Statistical interpretation and limitations

M10 provides descriptive summaries, not inferential statistics. It does not
calculate p-values, confidence intervals, Bayesian posteriors, optimize
parameters or establish real-world validity. Standard deviation is the
population standard deviation of the observed successful runs, not an
uncertainty interval for a population parameter.

Factor-level summaries are marginal means across other varied factors. With
multiple factors, interactions are not separately estimated. The report warns
about this. M9 currently allocates consecutive ABM seeds across all parameter
variants rather than pairing common random-number streams across variants;
M10 warns that ABM comparisons are therefore unpaired and should be treated as
descriptive.

A difference in simulated outcomes describes what changed under the specified
model and experiment settings. It is not, by itself, evidence that the same
relationship holds in the real world or that a conceptual theory is true.

## 6. API example

```python
from compilation import load_artifact
from experimentation import GridFactor, run_parameter_sweep, save_report
from execution import save_result

artifact = load_artifact("outputs/model_m8_agent_based_specification.json")
result, report = run_parameter_sweep(
    artifact,
    (GridFactor("termination.value", (5, 10, 15)),),
    runs=5,
    base_seed=100,
)
save_result(result, "outputs/model_m9_sweep_execution.json")
save_report(report, "outputs/model_m10_analysis.json")
```
