# Milestone 9 — Controlled Simulation Execution and Result Capture

## Summary

M9 adds the execution boundary after M8 compilation. It loads and verifies an
M8 artifact, reconstructs the corresponding native model, applies explicit
experiment settings, runs only a supported backend, and saves traceable JSON
results associated with the exact conceptual revision and compilation
artifact.

## Delivered

- New `execution/` package with experiment configuration, run records,
  experiment result contracts, controlled runner and strict serializer.
- Verification of M8 model and whole-artifact SHA-256 fingerprints before any
  execution begins.
- DES V1 and ABM V1 dispatch through their existing execution backends.
- ABM seed selection from an explicit experiment base seed or the compiled
  model seed; consecutive deterministic seed assignment across all runs.
- Named parameter sets that vary only exact fields already marked as
  `user_parameter` in the M8 artifact; every variant is re-parsed before any
  run starts and the source model remains unchanged.
- Replications per parameter set, with a maximum of 100 total executions.
- Explicit rejection of unseeded ABM execution where reproducibility cannot be
  guaranteed.
- Explicit representation of DES V1 as deterministic and seed-free.
- Per-run capture of normalized metrics, elapsed wall-clock time, UTC
  timestamps, seed, parameter-set name and applied values, plus success/failure
  details.
- DES event log, entity metrics and resource metrics capture.
- ABM population history, state/attribute snapshots, rule-evaluation trace and
  final state counts capture.
- Continue-on-error behavior with bounded error details and aggregate
  `completed` / `partial` / `failed` experiment status.
- Execution bounds of 1–100 runs and a 500,000-record estimated trace budget.
- SHA-256 integrity verification for saved experiment result JSON and atomic
  result-file writes.
- CLI option 9 for controlled execution and option 10 for result inspection.
- 24 focused M9 tests and architecture/test documentation.

## Design choices

M9 consumes the saved M8 artifact instead of recompiling the conceptual
project. This prevents the execution step from silently changing the target
model or the revision to which its provenance refers. The original conceptual
project and M8 artifact are read-only inputs.

The DES backend currently has deterministic V1 semantics and no random-seed
interface. M9 does not add meaningless seed metadata to that backend. ABM V1
already uses Python's seeded random generator, so the experiment runner can
reliably assign a seed to every run.

The output retains the full native trace rather than only aggregate metrics.
This provides the underlying events and state transitions needed for a later
analysis and visualization milestone.

## Verification performed in this build environment

- Python bytecode compilation passed for the new execution package, modified
  DES backend and CLI.
- 333 tests passed across M9 execution/serialization, ABM, M8 compilation,
  conceptual modeling, AI-assisted interpretation, knowledge mapping,
  readiness and shared-core test packages.
- Seeded ABM repeatability, consecutive seed allocation, missing-seed
  rejection, M8 artifact tamper rejection, readiness gate, trace budget,
  failed/partial-run capture, DES trace serialization and result
  round-trip/integrity checks passed.
- CLI smoke test completed two seeded ABM runs, saved the result and loaded it
  through option 10 with result-integrity verification.
- Full DES execution could not be run in this environment because the declared
  `simpy` dependency is not installed and package installation is unavailable
  here. DES execution is still wired to the existing `SimPyBackend`; the
  project's Windows environment should run the full suite with
  `python -m pip install -r requirements-dev.txt` before accepting M9.

## Scope boundary

M9 executes a supplied valid model; it does not claim that the model is
scientifically correct. The previously included decentralized community
resource-cooperation conceptual example remains blocked by its M7 readiness
questions and is not modified or bypassed by this milestone. Execution tests
use the valid ABM fixture and deterministic DES fixture from the M8 test suite.

Statistical comparison across saved runs, automatic parameter-grid generation,
sensitivity analysis, visualization and scientific interpretation remain
follow-on work. M9 supports explicit named parameter sets but does not
automatically generate a full grid or analyze statistical distributions.
