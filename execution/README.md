# M9 Execution API

## Quick start

```python
from compilation import load_artifact
from execution import ExperimentConfig, execute_artifact, save_result

artifact = load_artifact("outputs/my-project_m8_agent_based_specification.json")
result = execute_artifact(
    artifact,
    ExperimentConfig(runs=5, base_seed=100),
)
save_result(result, "outputs/my-project_m9_execution.json")
```

For ABM, `base_seed` is optional only when the compiled model already has a
`random_seed`. Run seeds are consecutive: 100, 101, 102, and so on. An ABM
without either seed is rejected. DES V1 is deterministic, so its `base_seed`
must remain unset and each run records `seed: null`.

## Result structure

`ExperimentResult` stores the M8 artifact ID and fingerprint, project and
revision provenance, selected paradigm/backend, the bounded experiment
configuration, overall outcome and a tuple of `RunRecord` objects. Each run
contains backend-neutral metrics, elapsed wall-clock duration, timestamps and
a structured trace. Failed runs contain an error type and bounded message.

DES traces store events, entity metrics and resource metrics. ABM traces store
step snapshots for every agent, rule-evaluation records and final state counts.

## Limits and safeguards

- Replications per parameter set are from 1 through 100, and the total number
  of executions across sets cannot exceed 100.
- The runner estimates trace size and blocks experiments above 500,000 records.
- The M8 artifact must pass its stored model and artifact fingerprints and must
  carry `ready_for_implementation_planning` readiness metadata.
- Mathematical and data-driven execution is rejected until their backends
  exist.
- Result JSON is fingerprinted, strictly decoded and atomically written.

The result fingerprint detects changes to the saved record; it is not a
cryptographic author signature. The trace-size check is not a wall-clock
execution timeout.

## CLI

- Option 9: execute a recent or explicitly selected M8 artifact.
- Option 10: inspect a recent or explicitly selected M9 result.

Execution never edits the conceptual project or source M8 artifact.
