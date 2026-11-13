# M7 Test Report

## Focused tests

- **23 passed** in the M7-only test group.
- Coverage includes all four paradigm evaluators, backend-availability labels, multi-paradigm recommendations, invalid projects, clarification generation, revision traceability, non-mutation, selected-paradigm readiness and strict JSON serialization.

## Broader integration tests

- **279 passed** across the conceptual, knowledge, idea-assistant, core, ABM and readiness test groups.
- Python compilation of the project completed successfully.
- `python -m readiness.demo` completed and produced an assessment report for the included decentralized resource-cooperation scenario.
- CLI option 7 was smoke-tested with the included scenario; the menu loaded, all four assessments printed, and a report was saved.

## Full-suite limitation in this environment

The full `python -m pytest -q` collection could not run because this workspace does not have the existing DES dependencies `simpy` and `groq`. Collection stopped with nine import errors in DES test modules. Installing `requirements-dev.txt` was attempted, but this workspace has no package-index network access. This is an environment limitation, not a reported test failure in M7. The complete M1–M7 suite must be verified in the user's Windows environment using:

```powershell
python -m pytest -q
```

No full-suite pass count is claimed until that command completes successfully in the target environment.
