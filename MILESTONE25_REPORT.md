# Milestone 25 — Advanced Experiment Analytics and Results Intelligence

## Delivered

M25 adds a separate analytics layer over saved, integrity-verified M10, M11, M23 and M24 reports. It does not rerun M9 or change the original experiment results.

Implemented:

- Exact-match source adapters for M10 parameter-sweep variants, M11 uncertainty distributions, M23 optimization candidates and M24 member/parameter-set aggregates.
- Provenance preservation through source report fingerprints, artifact IDs/fingerprints, project/revision lineage, paradigms and M9 experiment IDs.
- Student-t confidence intervals for group means from source-reported aggregate statistics.
- Welch independent-group comparisons with degrees of freedom, p-values and confidence intervals for the mean difference.
- Hedges' g effect size and Holm-Bonferroni multiple-comparison adjustment within each metric.
- Findings for low sample size, unobserved runs, high relative variability, best observed means, adjusted-significant and not-detected differences.
- Optional multi-objective Pareto frontier when at least two directed metrics are available for the same group set.
- Strict plan/report JSON, source/report fingerprint verification, path containment, atomic writes and CSV export.
- Standalone CLI and main-menu options 22–23.

## Verification status

- M25 tests: 13 passed.
- M10/M11/M23/M24/workbench/web API regression: 88 passed.
- M19 DES replay regression: 20 passed.
- Broader suite excluding `tests/des`: 567 passed.
- Python compilation and standalone CLI help: passed.

The packaging container does not include `simpy` or `groq`, so full-suite verification remains for the Windows environment. No commit has been created by the assistant.

## Boundaries

M25 relies on source summary statistics, not raw observations. Welch's independence and approximate-normality assumptions cannot be verified from those summaries. Cross-model semantic equivalence is user-declared. The analysis is about simulated results; it does not establish causality, real-world probabilities or theory validity.
