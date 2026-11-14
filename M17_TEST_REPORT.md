# M17 Test and Verification Report

**Milestone:** M17 — Advanced Spatial Mechanics
**API version:** 17.0.0
**Project:** AI-Assisted Simulation Workbench

## Results in the build environment

| Check | Result | Notes |
|---|---:|---|
| M17 advanced spatial tests | **16 passed** | Obstacles, collision, slide, movement budgets, A*, no-path, wrap, validation, M9 trace and replay |
| ABM + execution + replay + web API focused suite | **199 passed** | `tests/abm`, `tests/simulation_studio`, `tests/execution`, `tests/webapp` |
| Non-DES regression suite | **440 passed** | `tests/des` excluded because SimPy and Groq are unavailable in this build environment |
| Python bytecode compilation | **Passed** | `python -m compileall -q .` |
| Browser JavaScript syntax | **Passed** | `node --check webapp/static/app.js` |
| Obstacle navigation scenario | **Passed** | Final position `(18, 10)`, 12 movement events |
| Full DES suite in this environment | **Not run** | Test collection requires `simpy` and `groq`; package installation could not reach the package index |
| Browser visual QA | **Not performed** | M17 does not change the UI; inspect new event data after local application if desired |

## Commands

Focused M17 integration suite:

```bash
python -m pytest -q tests/abm tests/simulation_studio tests/execution tests/webapp
```

Expected build result:

```text
199 passed
```

Non-DES regression suite:

```bash
python -m pytest -q --ignore=tests/des
```

Observed build result:

```text
440 passed, 1 warning
```

Static checks:

```bash
python -m compileall -q .
node --check webapp/static/app.js
```

Both exited successfully. The single pytest warning is emitted intentionally by the duplicate ZIP member rejection test.

## Full-suite limitation

The build container does not have SimPy or Groq installed. An installation attempt failed because the package index could not be resolved. As a result, importing DES test modules failed during collection. This is an environment limitation, not evidence that DES tests pass or fail. The user's Windows environment previously had these dependencies installed; run `python -m pytest -q` there after applying M17.
