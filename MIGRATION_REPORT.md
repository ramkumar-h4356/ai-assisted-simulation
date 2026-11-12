# Migration Report — AI-Assisted Simulation Workbench

## Summary

The original migration retained the existing DES behavior and public class/function contracts while modules and imports were consolidated. ABM Milestone 1 was added afterward: it defines the ABM model contract and validator but does not yet include an execution engine. Mathematical and data-driven simulation engines remain future work.

- Original direct modules under `simulations/`: 21 Python files.
- New active implementation modules across `simulations/core/` and `simulations/des/`: 13 Python files (excluding package initializers).
- Existing test cases preserved and relocated: 135 collected cases, plus 27 unittest subtests.
- No actual `.env`, API key, `.git` directory, virtual environment, or cache was included in the output archive.

## New structure

```text
simulations/
  core/
    specification.py    Common paradigm and simulation specification
    backend.py          Shared backend protocol and normalized results
    registry.py         Backend registration and lookup
  des/
    model.py            Entity, Resource, service stages, jobs and Scenario
    runtime.py          SimPy event engine and event-derived metrics
    interpreter.py      Groq interpretation and refinement
    representation.py   Scenario IR and provenance/uncertainty records
    schema.py           Executable scenario JSON and IR parsing
    processing.py       Clarification, defaults and ID normalization
    validation.py       Deterministic requirements validation
    compiler.py         ScenarioIR-to-executable-model compiler
    backend.py          Scenario execution, comparison and SimPy adapter
    pipeline.py         End-to-end DES orchestration
  abm/                  Agent-Based model contract and validation; engine planned next
  mathematical/         Reserved for future Equation-to-Simulation
  data_driven/          Reserved for future Dataset-to-Simulation

tests/
  core/                 Shared architecture tests
  des/                  DES tests
scripts/
  check_groq_connection.py
```

## Original-to-new mapping

| Original module | New location | Notes |
|---|---|---|
| `simulation_spec.py` | `core/specification.py` | Shared simulation specification and paradigm enum |
| `simulation_backend.py` | `core/backend.py` | Backend protocol, metric and execution-result contracts |
| `backend_registry.py` | `core/registry.py` | Shared backend registry |
| `entity.py`, `resource.py`, domain classes from `scenario.py` | `des/model.py` | Consolidated DES domain models |
| `engine.py`, `metrics.py` | `des/runtime.py` | Runtime engine and event-based metric calculations |
| `ai_interpreter.py` | `des/interpreter.py` | Groq prompt and API behavior preserved |
| `scenario_ir.py`, `scenario_understanding.py` | `des/representation.py` | Hierarchical IR, facts, origins and uncertainties |
| `model_schema.py`, `scenario_ir_schema.py` | `des/schema.py` | Both JSON parsing paths retained; private parser helpers renamed to avoid collisions |
| `clarification_manager.py`, `default_manager.py`, `scenario_normalizer.py` | `des/processing.py` | Clarification questions, model merging, explicit defaults and generated IDs |
| `requirements.py` | `des/validation.py` | Validation statuses and rules preserved |
| `scenario_compiler.py` | `des/compiler.py` | Compilation behavior preserved |
| `simpy_backend.py` and scenario runner functions | `des/backend.py` | Scenario execution and backend adapter consolidated |
| `pipeline.py` | `des/pipeline.py` | Workflow preserved; imports updated |

The three embedded `test_*` helper functions found at the bottom of the original `scenario_understanding.py` were removed from production code. Equivalent tests already exist in `tests/des/test_scenario_understanding.py` and remain in the suite.

## Other changes

- `main.py` imports the new DES pipeline, models and backend locations; CLI behavior is unchanged.
- Tests were moved to `tests/core/` and `tests/des/`. Assertions and test bodies were retained; import paths and monkeypatch targets were updated.
- The manual `test_groq.py` connectivity script was moved to `scripts/check_groq_connection.py` so pytest does not treat a manual integration script as a test module.
- Added `requirements.txt` and `requirements-dev.txt` for reproducible dependency installation.
- Added `.env.example` with a placeholder only. Copy it to `.env` and add the user's own key.
- Updated `.gitignore` for pytest caches and Python caches.
- Updated `README.md` with the reorganized architecture and setup steps.
- Temporary review files were removed from the project package.

## Verification performed in this environment

| Check | Result |
|---|---|
| Python compilation (`python -m compileall -q .`) | Passed |
| Pytest collection and execution | 135 passed; 27 subtests passed |
| CLI option 2 (one-machine versus two-machine comparison) | Ran successfully; one-machine completion 10.00, two-machine completion 6.00 |
| Stale imports referencing the removed flat module locations | No matches found |
| Duplicate top-level classes/functions after consolidation | No duplicates detected |
| Secret and cache scan of final package | `.env`, `.git`, bytecode and caches excluded from archive |

### Important test-environment limitation

This execution environment did not have the real `simpy`, `groq`, or `python-dotenv` packages installed, and network access prevented installing them. For the 135-test run, temporary test-only import/runtime compatibility stubs were supplied from outside the project directory; they are **not included** in the archive. Therefore, the test result verifies the refactored imports, application logic and expected engine interactions against that test shim, but it is not a final integration test against the actual SimPy distribution or a live Groq API.

Before replacing the working project, install the real dependencies on the user's machine and run:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The original project and its Git history should be kept until those commands pass locally.

## Git and environment preservation

The archive intentionally excludes `.git` and `.env`:

- Copy the existing `.git` directory from the backed-up project into the reorganized project to preserve Git history and remotes.
- Copy the existing `.env` file into the reorganized project to preserve the local Groq key. Do not commit it.
- Keep the original project backup until the new copy passes tests and the CLI check on the local machine.

## ABM Milestone 1 addendum (2026-11-12)

The project now includes the initial ABM model contract and deterministic validator in `simulations/abm/`. The implementation supports immutable agents and environment attributes, static relationships, declarative conditions/actions, sequential declaration-order activation metadata, maximum-step termination, probability parameters and optional random seeds. It does not yet execute models; the ABM engine is the next milestone.

Dedicated tests were added under `tests/abm/`. See `ABM_MILESTONE1_REPORT.md` for the model contract, validation boundaries and test results.

### User-side verification before ABM Milestone 1

The user ran the reorganized application on Windows with the actual installed dependencies and reported **135 tests passed**. The user also ran the Groq-to-SimPy clinic CLI scenario successfully; the two-patient sequential-resource example completed at simulation time 12.00.
