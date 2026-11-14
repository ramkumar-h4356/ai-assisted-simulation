# M16 Test and Verification Report

**Milestone:** M16 — Spatial ABM
**Verification date:** 2026-11-14
**Project:** AI-Assisted Simulation Workbench

## Results in the build environment

| Check | Result | Notes |
|---|---:|---|
| ABM + execution + replay + web API focused tests | **182 passed** | `tests/webapp`, `tests/simulation_studio`, `tests/abm`, `tests/execution` |
| Non-DES regression suite | **423 passed** | `tests/des` excluded because this build environment does not have SimPy and Groq installed |
| Python bytecode compilation | **Passed** | `python -m compileall -q .` |
| Browser JavaScript syntax | **Passed** | `node --check webapp/static/app.js` |
| Spatial example execution | **Passed** | Five-step example produced coordinate changes and expected neighbour awareness state |
| Full DES suite in this environment | **Not run** | DES test modules require SimPy and Groq, which were unavailable in this build environment |
| Browser visual QA | **Not performed** | The spatial API-to-replay integration is tested; interactive browser rendering should be checked locally |

## Exact commands and observed results

Focused spatial/replay/API suite:

```bash
python -m pytest -q tests/webapp tests/simulation_studio tests/abm tests/execution
```

```text
182 passed
```

Regression suite outside the DES-specific tests:

```bash
python -m pytest -q --ignore=tests/des
```

```text
423 passed, 1 warning
```

Static checks:

```bash
python -m compileall -q .
node --check webapp/static/app.js
```

Both commands exited successfully. The one pytest warning in the non-DES suite is generated intentionally by a duplicate ZIP member test.

## User-environment verification still required

The full suite was not executed in the build environment. The user's Windows environment previously passed the complete M15 suite with SimPy and Groq installed; M16 must now be verified there using `python -m pytest -q` after applying the update. Browser visual acceptance should also be checked in the user's browser.
