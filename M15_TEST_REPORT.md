# M15 Test and Verification Report

**Milestone:** M15 — Interactive ABM 2D State Replay
**Verification date:** 2026-11-14
**Project:** AI-Assisted Simulation Workbench

## Result summary

| Check | Result | Notes |
|---|---:|---|
| M15 + M14 web/API + workspace focused tests | **24 passed** | ABM scene construction, deterministic replay, exact M8/M9 lineage, selected run validation, API integration, browser shell and M13 workspace regression |
| Non-DES regression suite | **409 passed** | `tests/des` excluded because this build environment does not have `simpy` or `groq` installed |
| Python bytecode compilation | **Passed** | `python -m compileall -q .` |
| Browser JavaScript syntax | **Passed** | `node --check webapp/static/app.js` |
| Full DES suite | **Not run** | DES test modules cannot be collected without `simpy` and `groq` in this build environment |
| Browser visual QA | **Not performed** | API and JavaScript syntax tests pass; local interactive rendering should be checked on the user's Windows browser |

## Exact commands

Focused suite:

```bash
python -m pytest -q tests/simulation_studio tests/webapp tests/workbench/test_workspace.py tests/workbench/test_artifact_temp_path.py
```

Observed result:

```text
24 passed, 1 warning
```

Non-DES regression suite:

```bash
python -m pytest -q --ignore=tests/des
```

Observed result:

```text
409 passed, 1 warning
```

Syntax checks:

```bash
python -m compileall -q .
node --check webapp/static/app.js
```

Both exited successfully.

## Warning

The one warning is emitted by the existing ZIP safety test while it deliberately creates an archive with duplicate entry names. It is expected from the test fixture and is not a replay or runtime warning.

## Full-suite limitation

The build environment does not contain `simpy` or `groq`, so the DES test modules were excluded from the non-DES regression run. The user's Windows M14 baseline had already passed with all dependencies installed; the M15 patch should be validated there with the full test suite.
