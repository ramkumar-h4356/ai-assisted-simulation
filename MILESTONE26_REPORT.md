# Milestone 26 — Simulation Model Verification and Validation

## Summary

M26 introduces a dedicated verification-and-validation layer that sits after M8 compilation and M9 execution. It does not replace the simulation engines or create a second execution system: all model execution remains delegated to M9.

## Delivered capabilities

1. **M8 artifact verification** — checks model/artifact fingerprints and rebuilds the model through the native M9 parser.
2. **M9 execution provenance** — verifies that the result belongs to the exact M8 artifact and fingerprint selected by the plan.
3. **Trace verification** — checks completion, finite values, paradigm-specific structure, chronological ordering, initial-state consistency and fixed-step time grids where supported.
4. **Declarative invariants** — evaluates non-negative, bounds, monotonic and conserved-sum requirements over safe trace paths. Plans cannot execute arbitrary Python expressions.
5. **Repeatability** — optionally reruns using the exact stored M9 experiment configuration and compares stable modeled outputs while excluding timestamps and wall-clock metadata.
6. **Fingerprint reports** — serializes checks and evidence into a strict JSON report with integrity fingerprint and CSV export.
7. **M13 workspace integration** — registers a Validation Report artifact and requires its exact M8 compilation and M9 execution parents to be present in the workspace.
8. **Entry points** — standalone `python -m validation.cli` and main application options 24 (run) and 25 (inspect).

## Scope boundaries

Verification, behavioral validation and empirical validation are different activities. M26 V1 verifies the internal consistency of the executable specification, saved execution and selected invariants. It does not automatically calibrate against real-world observations, prove causality, certify scientific theories, perform formal proofs, or establish numerical convergence. DES initial-state validation is not defined by the current M9 trace contract and is explicitly reported as skipped; DES trace chronology is still checked.

## Test status

See `M26_TEST_REPORT.md`. The packaging environment reports 14 M26 tests passed and one DES integration test skipped because SimPy is unavailable; the broad non-DES suite reports 581 passed and one skipped; DES replay regressions report 20 passed. Python compilation and CLI help checks pass. The complete suite must be run in the Windows environment because the packaging container lacks `simpy` and `groq`.

## Installation

Use `M26_Updates.zip` to update an existing M25 repository. Follow `M26_APPLY_STEPS.txt`; do not use the complete project snapshot to overwrite an existing repository.
