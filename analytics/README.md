# M25 Advanced Experiment Analytics

M25 reads saved, integrity-verified M10, M11, M23 and M24 reports. It does not rerun simulations or mutate their source artifacts.

## Capabilities

- Converts source-reported means and population standard deviations to sample-statistic form where the sample size permits it.
- Computes Student-t confidence intervals for group means.
- Computes independent-group Welch t comparisons, confidence intervals for the mean difference, Hedges' g effect sizes, and Holm-Bonferroni adjusted p-values.
- Identifies low sample sizes, incomplete observations, high relative variability, best observed means, and adjusted-significant / not-detected differences.
- Computes a Pareto frontier when at least two directed objectives are defined and complete metric sets exist for a group.
- Preserves source report fingerprints, artifact identifiers and experiment lineage, and writes a fingerprinted JSON report plus CSV export.

## Plan

See `scenarios/analytics/plan_template.json`. Paths are relative to `--source-root`, must remain inside that root, and each source must be an integrity-valid report of the declared type (`m10`, `m11`, `m23`, or `m24`). Metric names and units must match exactly. Each metric needs a user-written semantic definition of at least 12 characters. Direction can be `minimize`, `maximize`, or `observe`.

## Run

```powershell
python -m analytics.cli --plan scenarios/analytics/plan_template.json --source-root . --output-dir outputs/analytics
```

The template is intentionally not executable until the report paths and metric definitions are adjusted to existing outputs. Inspect a report with:

```powershell
python -m analytics.cli --inspect outputs/analytics/m25-..._report.json
```

## Statistical interpretation

M25 operates on sufficient summary statistics, not raw observations. For groups with at least two observations, it converts the reported population standard deviation to a sample standard deviation using `s = sigma * sqrt(n/(n-1))`. Welch's independent-samples t method is used for pairwise comparisons, followed by Holm-Bonferroni correction within each metric. Hedges' g is reported as a standardized effect-size estimate. Confidence intervals use Student's t critical values.

The test assumptions of independent observations and approximately normal sampling distributions cannot be verified from aggregate reports. Comparisons between different reports or simulation paradigms depend on the user's explicit semantic definitions; equal metric names and units do not prove semantic equivalence. Overlapping M9 experiment IDs across different source reports are skipped to reduce double counting. Statistical differences in simulated outcomes are not causal effects or real-world validation. M11 distributions can combine input uncertainty and stochastic variation. Effect-size labels use conventional heuristics and should not be treated as decision thresholds.

The package intentionally uses only the Python standard library; no SciPy or external statistical service is required.
