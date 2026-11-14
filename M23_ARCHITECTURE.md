# M23 Architecture — Objective-Driven Simulation Optimization

## Objective and relationship to M10/M11

M23 introduces a bounded, reproducible search over approved numeric M8 model
parameters. It evaluates each candidate through the existing M9 executor and
selects the best candidate against one user-selected metric, subject to
optional metric constraints.

M23 does not replace earlier experimentation capabilities:

- M10 evaluates explicit Cartesian parameter grids and provides descriptive
  comparisons. It does not optimize.
- M11 samples declared input distributions and assesses uncertainty,
  sensitivity and user-defined robustness thresholds.
- M23 searches parameter bounds with an explicit objective and constraints.

## Architecture

```text
Verified M8 artifact + user-authored M23 plan
                |
                v
Validate exact numeric user_parameter bindings and bounds
                |
                v
Seeded uniform random candidate generation (+ optional baseline)
                |
                v
Enforce 100-run M9 execution budget
                |
                v
Existing M9 execute_artifact(artifact, ExperimentConfig)
                |
                v
Verify M9 result fingerprint and exact candidate grouping
                |
                v
Per-candidate objective/constraint means across replications
                |
                +--> retain failed/incomplete candidates, but mark ineligible
                +--> select best feasible candidate by min/max objective
                +--> compare with baseline where both are feasible
                |
                v
Fingerprint + M23 JSON report + candidate CSV
```

### `optimization/models.py`

Defines immutable contracts for search bounds, one objective, optional output
constraints, bounded plans, candidate summaries, constraint evaluations and
the provenance-bound report. Bounds retain the exact numeric type of their M8
scalar field. The plan enforces the M9 limit of at most 100 total executions.

### `optimization/search.py`

Verifies the M8 artifact fingerprint and each exact `user_parameter` binding.
It rejects missing/overlapping paths, conceptual bindings, non-numeric fields,
type changes, invalid bounds and an out-of-range baseline. A seeded
`random.Random` samples integer intervals inclusively and float intervals
uniformly. Duplicate vectors are discarded; candidate names and ordering are
stable for a fixed plan seed. A baseline candidate is optional.

### `optimization/engine.py`

Converts candidates to M9 `ParameterSet` values and executes them with the
existing `execute_artifact` service. It verifies the resulting M9 fingerprint
and groups runs by the exact generated parameter-set names. Metrics include
backend metrics and the deterministic trace-derived metrics already used by
M10. For each candidate, objective and constraint values are averaged over
all requested replications. A candidate is eligible only when all requested
runs complete and every requested metric is present in each run. Constraints
are applied to their candidate-level metric means. The selected candidate is
the minimum/maximum objective among feasible candidates. Improvement over the
baseline is reported only when the baseline is itself feasible.

### `optimization/serialization.py`

Provides strict plan parsing, report JSON round-tripping, SHA-256 content
fingerprints, atomic persistence and CSV export. The fingerprint detects
content changes; it is not a cryptographic author signature.

### CLI and integration

The main CLI exposes option 18 for optimization and option 19 for inspecting
M23 reports. `python -m optimization.cli` offers a non-interactive equivalent.
The optimizer calls the common M9 execution service, so the same orchestration
works with every M9 backend currently registered: DES, ABM, mathematical,
data-driven and system dynamics. It does not add new simulation semantics to
those engines or alter their model artifacts. The M13 extension registry and
M14 web UI remain the authoritative compilation/readiness/execution flows;
M23 V1 exposes optimization from the project-level CLI and Python API.

## Plan format

See `scenarios/optimization/abm_random_search_plan.json`. The sample searches
`agents[0].attributes.trust` and `termination.value` for an ABM profile and
maximizes `derived:abm:Person:contributions:sum`. It is illustrative only; the
paths and metric must match the selected M8 artifact/backend.

A plan includes:

- `search_parameters`: one or more `{target_path, lower, upper}` objects;
- `objective`: `{metric_name, direction}`, where direction is `minimize` or
  `maximize`;
- `candidate_count`: number of random candidates, excluding baseline;
- `replications`: M9 runs per candidate;
- `search_seed`: seed for candidate generation;
- `include_baseline`: whether to run the compiled parameter values; and
- `constraints`: optional metric constraints using `<=`, `>=` or `between`.

The baseline must lie inside all search bounds. Search fields are scalar
numeric model fields explicitly bound as M8 `user_parameter` values. The plan
does not permit conceptual-element overrides.

## Verification and limitations

M23 V1 is single-objective uniform random search. It provides no guarantee of
global optimality and does not automatically infer bounds or objectives. A
candidate is excluded if any requested run fails or an objective/constraint
metric is missing. The M9 budget limits plans to 100 executions including
replications and baseline.

ABM replications use M9's sequential seeds; they are not paired common-random-
number comparisons. Repeated runs of current deterministic DES, mathematical,
data-driven and system dynamics V1 engines repeat the same run and should
normally be configured with one replication. M23 results are conditional on
the selected model and user plan. They do not establish scientific truth,
real-world optimality or causal validity.
