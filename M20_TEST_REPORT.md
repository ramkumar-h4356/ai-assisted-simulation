# M20 Test Report — Mathematical Simulation Engine

## Verification performed in the build environment

| Test group | Result |
|---|---:|
| M20 model/backend, M7 readiness, M8 compilation, M9 execution and M13 workspace integration | **88 passed** |
| Broader suite excluding `tests/des` | **482 passed** |
| M19 DES replay regression tests | **20 passed** |
| Mathematical SIR demo | **Completed; population sum remained 1000.000000** |

The 88-test focused run covered:

```powershell
python -m pytest -q tests/mathematical tests/compilation/test_mathematical_compilation.py tests/compilation/test_compiler.py tests/execution/test_mathematical_execution.py tests/readiness/test_engine.py tests/core/test_simulation_architecture.py tests/workbench/test_workspace.py
```

The broader non-DES run used:

```powershell
python -m pytest -q --ignore=tests/des
```

M19 replay regression was checked with:

```powershell
python -m pytest -q tests/des/test_replay.py tests/simulation_studio/test_des_replay.py
```

Demo output:

```text
Model: SIR infectious-disease dynamics
Solver: rk4; steps: 240
Final time: 60 days
Final state:
  susceptible: 68.313778
  infected: 40.488400
  recovered: 891.197822
Population conservation (S + I + R): 1000.000000
```

## Full-suite limitation in this build environment

A full `python -m pytest -q` collection was attempted but could not complete because this build container does not have the existing project dependencies `simpy` and `groq` installed. Nine DES test modules failed collection with `ModuleNotFoundError` for those packages. This is an environment/dependency limitation, not a reported M20 test failure. The full suite must be run in the user's Windows virtual environment, which previously had the dependencies needed to run the M19 full suite.

The focused M20 and wider non-DES runs emitted one warning from the existing test that intentionally constructs a ZIP with a duplicate normalized path. That warning is expected for the rejection test.

## Windows verification requested

After applying the update, run:

```powershell
python -m pytest -q tests/mathematical
python -m pytest -q tests/compilation/test_mathematical_compilation.py tests/compilation/test_compiler.py
python -m pytest -q tests/execution/test_mathematical_execution.py
python -m pytest -q tests/workbench/test_workspace.py
python -m simulations.mathematical.demo
python -m pytest -q
```

Do not commit M20 until the Windows results have been reviewed. The final full-suite count may differ if the local branch has additional tests or dependencies.
