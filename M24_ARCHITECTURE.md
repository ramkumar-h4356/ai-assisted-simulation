# M24 Architecture — Cross-Engine Experiment Orchestration

## Objective

M24 provides a bounded suite-level layer for executing and reviewing multiple
independently compiled M8 artifacts across the existing M9 backends: DES, ABM,
mathematical, data-driven and system dynamics. It does not merge model
semantics. Each model remains an independent M8/M9 provenance chain.

## Workflow

```text
M24 suite plan + artifact root
             |
             v
Validate 2-20 members and global 100-run budget
             |
             v
Resolve relative artifact paths inside artifact root
             |
             v
Load and fingerprint-verify each M8 artifact
             |
             v
Execute each member through existing M9 execute_artifact
             |
             +--> save separate M9 result JSON per member
             |
             v
Aggregate numeric/categorical metrics by member and parameter set
             |
             v
Optional exact-name/exact-unit comparison with user semantic definition
             |
             v
Fingerprint M24 report + export metric CSV
```

## Contracts

- `SuiteMember` identifies one M8 artifact, run count, optional ABM seed,
  continue-on-error setting and optional M9 parameter sets.
- `ExperimentSuitePlan` accepts 2–20 members and caps all requested M9 runs
  across the suite at 100.
- `SuiteComparison` is optional. When present it requires a metric name, exact
  unit, direction and a user-authored semantic definition.
- `SuiteMemberSummary` preserves artifact ID/fingerprint, project/revision,
  paradigm/backend, M9 experiment ID/fingerprint, result filename, status,
  run counts and metric aggregates.
- `ExperimentSuiteReport` preserves plan order and contains per-member
  summaries, optional ranking, warnings and a SHA-256 content fingerprint.

## Execution and safety

M24 calls `compilation.load_artifact` and `execution.execute_artifact`; it does
not reproduce compilation validation or backend invocation. Each M9 result
is persisted using M9's fingerprint-checked `save_result`. Artifact paths are
relative to an explicit artifact root. Normalized `..` segments, absolute
paths, Windows drive paths and resolved symlinks escaping the root are
rejected. A member exception is captured as a failed member summary and
subsequent members continue. Failure to persist an M9 result aborts suite
reporting rather than pretending that result provenance was saved.

Numeric metrics receive mean and population standard deviation. Categorical
metrics receive value counts. Metrics with inconsistent units or types across
replications are omitted from aggregates. Comparison ranking includes only
completed groups where the requested metric is numeric, the exact unit
matches and every requested replication provided the metric. A plan's
semantic definition is a user assertion, not an automated proof of
comparability; the report repeats this limitation.

## Relationship to prior milestones

- M9 remains the only execution path.
- M10 still performs Cartesian parameter grid sweeps for a single artifact.
- M11 still performs uncertainty, sensitivity and robustness analysis.
- M23 still performs objective-driven parameter optimization for a single
  artifact. M24 can place separate optimized M8 artifacts into one suite, but
  it does not combine or rerun M23 optimizers.
- M13 retains workspace/project provenance; M24 adds suite-level provenance
  without altering project revisions or compilation artifacts.

## V1 boundaries

M24 is sequential, not distributed. It does not automatically align metrics
across paradigms, infer semantic equivalence, synchronize model clocks,
exchange state between engines, or perform coupled co-simulation. Member
artifacts are compiled before the suite and remain immutable. DES members need
SimPy. Cross-model rankings are only meaningful when the user-authored metric
semantic definition truly describes the same observable for each compared
model. A ranking does not prove causal validity or real-world truth.
