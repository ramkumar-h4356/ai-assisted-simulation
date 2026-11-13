# M11 Uncertainty Analysis API

The `uncertainty/` package implements reproducible Monte Carlo parameter
sampling, output uncertainty summaries, Spearman rank-correlation sensitivity
screening and user-defined robustness criteria. It consumes M8 artifacts and
executes sampled variants through the existing M9 runner.

## Main API

- `UncertainParameter(target_path, distribution, lower, upper, mode=None)`:
  numeric parameter bounds. `uniform` and `triangular` are supported.
- `RobustnessCriterion(metric_name, operator, threshold, upper_threshold=None)`:
  optional `<=`, `>=` or `between` output acceptance criterion.
- `UncertaintyPlan(sample_count, sampling_seed, parameters, criteria=())`:
  3–100 reproducible parameter samples.
- `generate_parameter_samples(artifact, plan)` validates exact M8 bindings and
  generates seeded M9 `ParameterSet` objects.
- `run_uncertainty_analysis(artifact, plan, execution_base_seed=None)` executes
  one M9 run per sample and returns `(ExperimentResult, UncertaintyReport)`.
- `analyze_uncertainty(artifact, plan, result)` rechecks provenance, integrity
  and sample vectors before building the report.
- `save_report`, `load_report` and `export_summary_csv` persist and inspect the
  fingerprinted report.

See `scenarios/uncertainty/plan_example.json` and `M11_ARCHITECTURE.md` for the
plan format, CLI workflow and statistical caveats.
