# M10 Experimentation API

M10 builds bounded parameter grids for verified M8 artifacts, runs them through
M9 and analyzes the resulting saved experiment records.

## Create and run a parameter sweep

```python
from compilation import load_artifact
from experimentation import GridFactor, run_parameter_sweep, save_report, export_summary_csv
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
export_summary_csv(report, "outputs/model_m10_analysis.csv")
```

A `GridFactor` must refer to an exact scalar target path included in the M8
artifact's `user_parameter` bindings. The level values must preserve the
existing scalar type. The current model value can be included as a separate
`baseline` variant. The Cartesian design is capped at 100 total M9 executions
including replications.

## Compare multiple M9 results

```python
from execution import load_result
from experimentation import analyze_results

report = analyze_results((
    load_result("outputs/experiment_a_m9_execution.json"),
    load_result("outputs/experiment_b_m9_execution.json"),
))
```

Every input must have the same M8 artifact ID/fingerprint, project/revision,
paradigm and backend. Result fingerprints are recalculated before analysis.

## Statistics

Numeric metrics include sample size, mean, population standard deviation,
median, minimum and maximum. Categorical metrics include value counts. M10
also derives ABM final-snapshot numeric attribute summaries by agent type and
DES entity/resource summaries from the M9 traces. ABM attribute summaries use
the final recorded population snapshot, not an average across simulation time.
Numeric mean differences and percentage changes are reported against a chosen
baseline variant/level when available. Failed runs remain in run counts and
warnings, but are not used to compute metric statistics.

These outputs are descriptive rather than inferential. M10 does not calculate
p-values or confidence intervals, optimize parameters, or establish empirical
validity. See `M10_ARCHITECTURE.md` for interpretation limits and CLI behavior.
