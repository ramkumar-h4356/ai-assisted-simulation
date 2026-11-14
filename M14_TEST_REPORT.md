# M14 Test and Verification Report

**Milestone:** M14 — Local Browser Workbench
**Verification date:** 2026-11-14
**Project:** AI-Assisted Simulation Workbench

## Result summary

| Check | Result | Notes |
|---|---:|---|
| Focused M14 + M13 workbench tests | **19 passed** | Browser/API CRUD, upload limits, ABM M7–M12 workflow, dashboard preview/export, M13 workspace and artifact-path regression tests |
| Non-DES regression suite | **404 passed** | `tests/des` excluded because this build container does not have `simpy` or `groq` installed |
| Python bytecode compilation | **Passed** | `python -m compileall -q .` |
| Browser JavaScript syntax | **Passed** | `node --check webapp/static/app.js` |
| Full test suite | **Not run to completion** | DES/Groq modules cannot be collected without `simpy` and `groq`; package installation was blocked by unavailable network/DNS in this build environment |
| Live Groq API | **Not tested** | Requires user credentials and network access |
| Windows-native test execution | **Not performed here** | The long temporary path was diagnosed from the user's Windows traceback and changed to a short same-directory temporary filename; user should rerun the full local suite on Windows |

## Exact commands

Focused tests:

```bash
python -m pytest -q tests/webapp tests/workbench
```

Observed result:

```text
19 passed, 1 warning
```

Non-DES suite:

```bash
python -m pytest -q --ignore=tests/des
```

Observed result:

```text
404 passed, 1 warning
```

Syntax checks:

```bash
python -m compileall -q .
node --check webapp/static/app.js
```

Both exited successfully.

## Warning explanation

The single pytest warning is emitted by the existing ZIP safety test when it deliberately constructs an archive with duplicate entry names. The warning is part of the malicious-input fixture and is not a runtime warning.

## Full-suite limitation

A full `pytest` collection was attempted before M14 implementation, but 9 DES test modules could not be imported because `groq` and `simpy` were absent in this container. Installing them was attempted but outbound package-index DNS/network access was unavailable. Therefore, no full-suite pass is claimed. The user's Windows environment previously reported those packages installed; the updated source should be tested there using the complete suite.

## Subsequent Windows verification (user environment)

After applying the M14.1 ZIP-import staging-path correction, the user ran the complete suite on Windows with the required `simpy` and `groq` dependencies installed. The reported result was:

```text
531 passed, 2 warnings, 27 subtests passed
```

This confirms the M14 baseline and the Windows ZIP-import regression fix in the user's environment. M15 adds five replay unit tests and extends the browser/API integration test; the M15 full suite still needs to be run in that Windows environment.
