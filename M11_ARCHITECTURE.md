# M11 Architecture — Sensitivity, Uncertainty and Robustness Analysis

## 1. Objective

M11 extends the M8–M10 workflow with explicit input uncertainty propagation,
exploratory parameter-sensitivity screening, and user-defined robustness
criteria. It does not replace the M9 execution backend or M10's discrete
grid-based comparative analysis.

M11 V1 uses a reproducible Monte Carlo design. It draws one parameter vector
per sample from distributions specified by the user, executes exactly one M9
run for each vector, then analyzes the verified result. It supports numeric
M8 fields explicitly bound as `user_parameter`.

## 2. Architecture

```text
Verified M8 artifact + M11 plan JSON
             |
             v
Validate numeric user_parameter bindings and distribution types
             |
             v
Seeded Monte Carlo input sampling (3–100 samples)
             |
             v
M9 ExperimentConfig: one parameter set / one run per sample
             |
             v
M9 saved execution result (fingerprinted)
             |
             v
M11 integrity + exact provenance + sample-vector verification
             |
             +--> output distribution summaries (mean, SD, median, P05/P95, min/max)
             +--> Spearman rank-correlation sensitivity screening
             +--> user-defined robustness threshold evaluation
             |
             v
Fingerprint + JSON report + CSV export
```

### `uncertainty/models.py`

Defines immutable contracts for uncertain input distributions, robustness
criteria, the bounded uncertainty plan, output distribution summaries,
Spearman sensitivity scores, criterion results and the complete provenance-
bound M11 report.

### `uncertainty/sampling.py`

Validates the M8 artifact fingerprint and exact `user_parameter` binding
paths. Supports uniform and triangular distributions. Integer model fields
receive integer samples; floating-point fields receive floating-point samples.
Overlapping fields, non-numeric targets, type mismatches and unbound paths are
rejected. `sampling_seed` reproduces the exact sample vectors.

### `uncertainty/analysis.py`

M11 requires one M9 execution per planned input vector. It verifies the M9
fingerprint, artifact/revision/backend provenance, and exact sampled parameter
vectors before analysis. Failed runs are counted but excluded from metric
summaries. Numeric metric distributions include mean, population standard
deviation, median, interpolated 5th/95th percentiles, minimum and maximum.
Sensitivity uses Spearman rank correlation between each sampled numeric input
and each numeric output metric; absolute coefficient ranks parameters per
metric. User-defined `<=`, `>=` and `between` criteria are evaluated both
individually and jointly where metric data are available.

### `uncertainty/serialization.py`

Provides strict M11 plan loading, strict JSON report parsing, SHA-256 report
fingerprint verification, atomic writes and CSV export. A fingerprint detects
content changes; it is not an author signature or proof of source authenticity.

### CLI

- Option 13: select an M8 artifact and M11 plan, review distributions and
  thresholds, run bounded Monte Carlo samples through M9, save the M9 result,
  then save M11 JSON and CSV outputs.
- Option 14: inspect an integrity-verified M11 JSON report.

## 3. Plan schema

A plan contains `sample_count` (3–100), `sampling_seed`, `parameters`, and
optional `criteria`. Each parameter has an exact `target_path`, `distribution`
(`uniform` or `triangular`), finite `lower` and `upper` bounds, and a `mode`
only for triangular distributions. Bound and mode types must match the target
M8 model field. Only numeric values are accepted.

Each optional criterion contains a numeric `metric_name`, `operator` (`<=`,
`>=`, or `between`), `threshold`, and `upper_threshold` for `between`.

See `scenarios/uncertainty/plan_example.json`. Its paths are illustrative and
must be checked against the selected artifact's actual M8 bindings.

## 4. Statistical interpretation and limitations

- Output distributions describe the selected model under the specified input
distributions and execution settings. They do not describe real-world
uncertainty unless those distributions are empirically justified.
- ABM results include both sampled input variation and stochastic run-to-run
variation. M11 V1 does not separate those sources. It uses sequential M9 seeds
and does not use paired common-random-number designs.
- Spearman rho is a monotonic association screening statistic, not a causal
sensitivity index. It can miss non-monotonic effects and interactions; the
finite-sample ranking can be unstable, especially below 20 samples.
- Robustness fractions are observed proportions for the finite tested sample,
not calibrated probabilities or a guarantee outside the tested distributions
and bounds.
- Failed executions are excluded from output distributions and sensitivity
scores. The number of failures is retained and warnings are emitted.
- M11 V1 is capped at 100 M9 executions, matching the current M9 experiment
budget. Only existing DES V1 and ABM V1 backends can execute.
- M11 does not infer uncertainty distributions, invent robustness thresholds,
prove a hypothesis, or assess whether the conceptual idea is true.

## 5. API example

```python
from compilation import load_artifact
from uncertainty import (
    RobustnessCriterion, UncertainParameter, UncertaintyPlan,
    run_uncertainty_analysis, save_report, export_summary_csv,
)

artifact = load_artifact("outputs/model_m8_agent_based_specification.json")
plan = UncertaintyPlan(
    sample_count=30,
    sampling_seed=20261113,
    parameters=(
        UncertainParameter("agents[0].attributes.trust", "uniform", 0.0, 1.0),
    ),
    criteria=(
        RobustnessCriterion("derived:abm:Person:contributions:sum", ">=", 10.0),
    ),
)
result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=400)
save_report(report, "outputs/model_m11_uncertainty_report.json")
export_summary_csv(report, "outputs/model_m11_uncertainty_report.csv")
```
