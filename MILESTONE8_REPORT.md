# Milestone 8 — Implementation Report

## Summary

M8 implements a traceable compilation layer between the paradigm-independent
conceptual model and the currently supported executable simulation models.
It compiles explicit user-approved profiles into the existing DES V1 and ABM
V1 model contracts, after M7 readiness checks and provenance validation.

## Delivered

- `compilation/` package with public profile, binding, diagnostic, artifact and
  result contracts.
- Explicit `CompilationProfile` bound to project ID, current revision ID and
  selected paradigm.
- Path-level `ElementBinding` records for conceptual source elements and
  separately documented experiment parameters.
- M7 implementation-planning gate for the selected paradigm.
- Stale revision/project checks and source element reference validation.
- Target-path validation with dotted keys and numeric list indexes; wildcard
  paths are intentionally unsupported.
- A requirement for at least one conceptual element and one mechanism binding.
- DES compilation through the existing `scenario_from_dict` parser.
- ABM compilation through the existing `agent_model_from_dict` parser and
  `validate_agent_model` semantic checks.
- Explicit rejection for mathematical/data-driven compilation while their
  execution engines remain unimplemented.
- Revision-bound portable artifacts with M7 decision metadata and SHA-256
  target-model and whole-artifact integrity fingerprints.
- Strict profile/artifact JSON serialization and integrity verification on
  artifact load.
- CLI option 8 and editable, intentionally incomplete DES/ABM profile
  templates.
- Offline demo compiling both a queueing DES specification and a cooperation
  ABM specification without executing either model.
- 30 focused M8 tests.

## Design choices

M8 intentionally does not infer numeric values, initial states, populations,
arrival schedules, capacities or behaviour rules from prose. These choices
can materially change an experiment and must be explicit. The compiler checks
whether they form a valid supported model and records how target fields relate
to the conceptual revision or user-stated experiment parameters.

The compiler also distinguishes a conceptual model from one experiment
profile. Unmapped ideas are surfaced as warnings rather than forcing every
concept into every simulation. At least one mechanism must be mapped so that a
profile cannot compile only the entities and omit the theory's operative rule.

## Verification performed in this environment

- 30 M8-specific tests passed.
- 309 combined tests passed across compilation, conceptual, knowledge,
  idea-assistant, readiness, ABM and core packages.
- Python compilation passed for the project and M8 tests.
- Offline demo compiled both DES and ABM artifacts.
- CLI option 8 appeared in the main menu smoke test.
- Full test collection was attempted, but DES tests could not be collected in
  this environment because the `groq` and `simpy` packages are unavailable.
  The Windows environment should run the complete suite after installing the
  project's declared requirements.

## Scope boundary

No simulation was executed. Execution orchestration, experiment comparison,
parameter sensitivity and result interpretation remain future milestones.
