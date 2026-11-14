# M25 Architecture — Advanced Experiment Analytics and Results Intelligence

## 1. Objective

M25 turns prior experiment reports into an integrity-checked statistical review. It reads M10 parameter-sweep reports, M11 uncertainty reports, M23 optimization reports and M24 cross-engine suite reports. It does not rerun simulations, mutate source reports or reinterpret model mechanisms.

M25 provides:

- Student-t confidence intervals for metric means where sample size and variance permit estimation.
- Independent-group Welch t comparisons using reported sufficient statistics.
- Hedges' g effect-size estimates with heuristic magnitude labels.
- Holm-Bonferroni adjusted p-values within each declared metric.
- Data-quality findings for low sample sizes, incomplete observations and high relative variability.
- Direction-aware observed-mean findings and optional multi-objective Pareto frontiers.
- Source report fingerprints, M8 artifact lineage and M9 experiment IDs in the final report.
- Fingerprinted JSON and spreadsheet-friendly CSV outputs.

## 2. Workflow

```text
M25 analytics plan + source root
              |
              v
Resolve each relative report path inside source root
              |
              v
Load M10 / M11 / M23 / M24 using each milestone's strict fingerprint verifier
              |
              v
Adapt source reports to common numeric group statistics
              |
              v
Check metric name, exact unit, semantic definition and provenance
              |
              +--> group confidence intervals and data-quality diagnostics
              |
              +--> pairwise Welch tests, Hedges' g and Holm correction
              |
              +--> optional direction-aware Pareto frontier
              |
              v
Evidence-backed findings + explicit interpretation limitations
              |
              v
Fingerprint M25 JSON report + export CSV
```

## 3. Modules

### `analytics/models.py`

Defines immutable contracts for `AnalyticsSource`, `MetricDefinition`, `AnalyticsPlan`, `SourceEvidence`, `GroupStatistic`, `PairwiseComparison`, `ObjectiveValue`, `ParetoEntry`, `Insight` and `AnalyticsReport`.

The plan supports 1–20 source reports and 1–10 declared metrics. The pairwise budget is bounded at 2,000 candidate pairs. The confidence level must equal `1 - alpha`. Each declared metric requires an exact name, an exact unit (or `null`) and a user-written semantic definition of at least 12 characters.

### `analytics/sources.py`

Loads source reports through their existing M10/M11/M23/M24 `load_report` functions. Those loaders recalculate each source report's SHA-256 fingerprint. M25 resolves relative paths under an explicit root and rejects path traversal and symlinks that escape that root.

The adapters preserve artifact, project, revision, paradigm and experiment lineage. M10 creates one group per parameter-set variant. M11 creates one uncertainty-sample group per output distribution. M23 creates one group per optimization candidate using the declared objective. M24 creates one group per suite member and parameter set. Only exact metric-name and unit matches are retained.

M23 does not record objective units. An M23 objective can therefore only be included with an M25 metric definition whose `unit` is `null`. If an M25 direction is specified as `minimize` or `maximize`, it must agree with the M23 optimization objective direction; `observe` leaves the M23 direction out of direction-aware ranking.

### `analytics/statistics.py`

Implements the regularized incomplete beta function, Student-t cumulative distribution and critical values using the Python standard library. It also implements:

- Student-t confidence intervals for group means.
- Welch's unequal-variance independent-samples t statistic, degrees of freedom, two-sided p-value and confidence interval for the difference (group B minus group A).
- Hedges' g with the small-sample correction.
- Holm-Bonferroni adjusted p-values.

When a group has fewer than two observations, a confidence interval is not emitted. Pairwise comparisons are skipped when either sample standard deviation cannot be estimated or the combined standard error is zero.

M10/M11/M23/M24 reports store population standard deviations. For sample size `n > 1`, M25 converts the reported population standard deviation `sigma` to sample standard deviation `s = sigma * sqrt(n / (n - 1))`, then calculates standard error and confidence intervals. For `n = 1`, sample uncertainty is not estimable.

### `analytics/analysis.py`

Loads and adapts each source, rejects duplicate source report fingerprints, constructs group statistics, and analyzes requested metrics. Welch comparisons are made for matching declared metric definitions. A cross-source pair that shares one or more M9 experiment IDs is skipped to avoid obvious double counting. The M24 adapter also records an ABM base-seed key; groups sharing that exact key are skipped because common-random-number or paired structure cannot be reconstructed from aggregate summaries. Holm correction is applied to the candidate pairwise tests separately within each metric.

Pareto analysis is performed only when at least two metrics have a `minimize` or `maximize` direction and a group has every directed objective. A group is Pareto-optimal when no other eligible group is at least as good on every objective and strictly better on at least one.

Insights are generated from recorded values and configured thresholds; they do not assert an underlying cause.

### `analytics/serialization.py`

Provides strict plan/report JSON parsing, SHA-256 report fingerprint verification, atomic persistence and CSV export. A fingerprint detects content changes; it is not a cryptographic author signature.

### `analytics/cli.py`

Supports generating an M25 report from a plan and inspecting an integrity-verified M25 report.

## 4. Plan format

The editable template is `scenarios/analytics/plan_template.json`. It contains source slots for M10, M11, M23 and M24. Replace report paths with files that exist under `--source-root`, and edit metric names and units to exactly match those source reports.

Example invocation:

```powershell
python -m analytics.cli --plan scenarios/analytics/plan_template.json --source-root . --output-dir outputs/analytics
```

Inspect an existing report:

```powershell
python -m analytics.cli --inspect outputs/analytics/m25-..._report.json
```

The main menu provides option 22 to run M25 and option 23 to inspect a saved M25 report.

## 5. Interpretation and limitations

- M25 consumes aggregate statistics rather than raw observations. It cannot check distribution shape, outliers, independence, pairing or serial dependence from the source summaries.
- Welch testing assumes independent samples and approximately normal sampling distributions. These assumptions cannot be verified using only source means, standard deviations and sample sizes.
- M25 skips cross-source group pairs that share an M9 experiment ID. This avoids an obvious duplicate-evidence case but does not prove independence for all other pairs.
- M24 metrics can originate from different simulation paradigms. Matching names and units is insufficient; the semantic definition is a user assertion, not a machine-verified equivalence proof.
- M11 uncertainty outputs can combine input-distribution variation with stochastic simulation variation. M25 does not separate these components.
- M23 objective values have no unit metadata in the M23 schema; M25 requires `unit: null` for that source.
- Hedges' g magnitude categories use conventional heuristics. They are not universal practical-significance thresholds.
- A non-significant result is not evidence of equivalence. A significant simulated difference is not a causal effect, real-world probability or proof of theory validity.
- Pareto optimality is relative only to the groups and objectives included in the plan.

## 6. Relationship to prior milestones

- M10 continues to run single-artifact Cartesian parameter sweeps and descriptive summaries.
- M11 continues to propagate input uncertainty and screen sensitivity/robustness.
- M23 continues to search parameter values for a declared objective.
- M24 continues to execute multi-artifact cross-engine suites.
- M25 consumes their persisted reports and adds a separate statistical interpretation layer. It does not replace or modify those milestones.
