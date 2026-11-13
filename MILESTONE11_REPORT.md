# Milestone 11 — Sensitivity, Uncertainty and Robustness Analysis

## Delivered

M11 adds a reproducible Monte Carlo analysis layer on top of M8 artifacts and
the M9 execution service. Users declare numeric input distributions and
optional output acceptance criteria. The system samples explicit M8
`user_parameter` fields, executes one model run per sample, and creates a
provenance-bound uncertainty report.

### Capabilities

1. Uniform and triangular sampling for numeric integer or floating-point
   model parameters.
2. Reproducible input vectors using an explicit sampling seed.
3. Bounded 3–100 sample execution through the existing M9 DES/ABM backends.
4. Output distributions: mean, population standard deviation, median,
   interpolated P05/P95 and observed range.
5. Spearman rank correlation sensitivity screening and per-metric absolute-
   rho ranking.
6. User-defined `<=`, `>=` and `between` robustness criteria, individually
   and jointly evaluated.
7. Integrity-checked M9 input results, exact M8 artifact/revision provenance,
   sample-vector verification, M11 JSON fingerprints and CSV exports.
8. CLI option 13 to run and option 14 to inspect M11 reports.

## Validation status

The M11-specific tests cover deterministic sample reproduction, distribution
bounds and type preservation, strict M8 parameter bindings, end-to-end ABM
execution, output distributions, sensitivity association, robustness
criteria, failed-run handling, provenance and tamper detection, strict plan
parsing, JSON round-trip and CSV output.

M11-focused tests: 16 passed. The combined offline-compatible integration
suites: 373 passed in 1.09 seconds. The M11 CLI was smoke-tested end to end,
including M9 result persistence, M11 report/CSV persistence and integrity-
verified inspection.

The complete unfiltered suite still needs Windows verification. This build environment lacks `simpy` and `groq`, so nine legacy DES/AI test modules fail collection here and cannot be claimed as passed. The exact local test output is recorded in `M11_TEST_REPORT.md`.

## Scientific limitations

M11 V1 does not prove theory correctness. For ABM, observed output variation
contains both input uncertainty and stochastic execution variation. Spearman
rho is an exploratory monotonic-association screen, not a causal or global
variance-based sensitivity index. Robustness fractions are empirical sample
proportions under user-defined criteria and the finite sampling plan.
