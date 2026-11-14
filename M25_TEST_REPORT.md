# M25 Test Report

## Focused M25 suite

`python -m pytest -q tests/analytics`

- **13 passed**
- Covers source-model validation, path containment, duplicate report rejection, M10/M11/M23/M24 source adapters, Student-t intervals, Welch comparisons, Hedges' g, Holm correction, Pareto dominance and M25 JSON/CSV integrity round trips.

## Regression verification in the packaging environment

`python -m pytest -q tests/experimentation tests/uncertainty tests/optimization tests/orchestration tests/workbench tests/webapp`

- **88 passed, 1 warning**
- The warning is the existing intentional duplicate-ZIP-path test fixture warning.

`python -m pytest -q tests/des/test_replay.py tests/simulation_studio/test_des_replay.py`

- **20 passed**

`python -m pytest -q --ignore=tests/des`

- **567 passed, 1 warning**
- The DES engine test directory was excluded because `simpy` is not installed in this packaging container. The explicit M19 replay regression tests above did run and pass.

## Tooling checks

- `python -m compileall -q main.py analytics` — passed.
- `python -m analytics.cli --help` — passed; CLI options loaded successfully.

## Environment limitation

A full `python -m pytest -q` run was not claimed in this packaging container. `simpy` and `groq` are unavailable here, and the full test collection includes dependency-bound DES/AI modules. Run the complete suite in the project's Windows environment, where M24 and the earlier milestones were previously verified.
