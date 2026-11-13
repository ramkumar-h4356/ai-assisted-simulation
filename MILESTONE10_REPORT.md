# Milestone 10 — Experiment Design and Comparative Analysis

## Summary

M10 adds parameter-sweep construction and descriptive comparative analysis on
top of the existing M8 compilation and M9 execution contracts. It leaves the
compiled artifact and simulation engines unchanged.

## Delivered

- `experimentation/` package with validated `GridFactor` and analysis report
  contracts.
- Bounded Cartesian parameter-grid generation using only exact M8
  `user_parameter` bindings.
- Optional baseline variant populated from the source M8 artifact's current
  parameter values; duplicate baseline combinations are skipped.
- M9 execution orchestration with the existing maximum of 100 total runs.
- Analysis of one or more M9 results, with strict same-artifact and same-revision
  provenance checks.
- Per-variant run counts, numeric descriptive statistics and categorical
  frequency counts.
- Deterministic trace-derived metrics: ABM final-snapshot numeric attribute
  summaries by agent type, DES mean entity timing summaries and per-resource
  utilization/waiting/service summaries.
- Numeric baseline deltas and percent changes where defined.
- Marginal factor-level summaries and comparisons with the baseline level.
- Failure and interpretation warnings, including multi-factor interaction and
  unpaired ABM seed limitations.
- Strict, fingerprinted M10 JSON persistence and CSV export.
- CLI option 11 for sweep design/execution/analysis and option 12 for report
  inspection.
- Dedicated tests for grid validation, analysis, provenance, failures,
  statistics, serialization, tamper detection and CSV output.

## Verification in this build environment

- M10 focused tests: 24 passed.
- Combined offline-compatible project suites (M10, M9 execution, ABM, M8
  compilation, conceptual, idea assistant, knowledge, readiness and core):
  357 passed.
- The tests execute the existing ABM backend for end-to-end parameter sweeps.
- Grid validation, M8 binding restrictions, baseline insertion, Cartesian
  generation, analysis aggregation, baseline deltas, result-provenance checks,
  failure handling, report round-trip, tamper detection and CSV export pass.
- A full `python -m pytest -q` collection attempt reports 9 import errors
  because this build container does not have `simpy` or `groq` installed.
  Therefore the complete legacy DES/AI-dependent test suite and a real SimPy
  parameter sweep could not be verified here. The user's Windows environment
  should run the full project suite after extracting this milestone.

## Scope boundary

M10 does not add inferential statistical tests, confidence intervals,
optimization, automatic parameter discovery, common-random-number pairing,
causal inference or scientific validation. Parameter grids must be explicitly
specified by the user and must target fields already marked as M8
`user_parameter` bindings. Mathematical and data-driven backends remain
unimplemented.
