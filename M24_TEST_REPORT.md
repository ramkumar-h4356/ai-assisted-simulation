# M24 Test Report — Cross-Engine Experiment Orchestration

## Focused tests

Command:

```powershell
python -m pytest -q tests/orchestration
```

Result: **12 passed**.

Coverage includes validated suite contracts, exact M9 execution budget,
relative-path restrictions (including symlink escape prevention), strict plan
JSON, report round-trip and tamper detection, numeric/categorical aggregation,
partial-member handling, comparison metric/unit matching, and real M9
execution using ABM, mathematical, data-driven and system-dynamics artifacts.

## Regression tests

| Command/scope | Result |
|---|---:|
| `tests/experimentation tests/optimization tests/uncertainty tests/workbench tests/webapp` | 76 passed |
| `tests/des/test_replay.py tests/simulation_studio/test_des_replay.py` | 20 passed |
| Entire test tree excluding `tests/des` | 554 passed |

`python -m compileall -q main.py orchestration` passed. The standalone CLI
`python -m orchestration.cli --help` displayed its supported arguments.

## Full-suite collection boundary

A complete `python -m pytest -q` run could not be collected in the packaging
container. Nine DES test modules require packages that are not installed in
this environment:

- `simpy` is required by the DES runtime/backend tests.
- `groq` is required by the DES AI interpreter/pipeline tests.

The M19 DES replay tests do not require those runtime dependencies and passed
(20 tests). The complete Windows suite remains required to confirm M24 in the
user's project environment, where these dependencies are already available.

## Warning

The non-DES regression run emitted one intentional duplicate-ZIP-path warning
from the test that verifies duplicate normalized workspace paths are rejected.
