# M24 Cross-Engine Experiment Orchestration

M24 runs multiple integrity-verified M8 artifacts in one bounded suite using
the existing M9 execution service. It preserves a separate M9 result for every
suite member and generates a suite-level report, metric CSV and optional
cross-member ranking.

## Run from the repository root

```powershell
python -m orchestration.cli --plan scenarios/orchestration/cross_engine_suite.json --artifact-root . --output-dir outputs
```

The sample plan is a template. Put the five corresponding M8 artifact JSON
files under `outputs/m8_artifacts/`, or edit the plan to point to your own
artifacts. The artifact root is the only permitted base directory for those
relative paths. Absolute paths, `..` segments and symlinks escaping the root
are rejected.

## Comparison contract

A comparison is optional. When enabled, it selects a numeric M9 metric by
exact metric name and exact unit, and requires the user to provide a semantic
definition of the observable that is intended to be equivalent across the
models. Only complete parameter-set groups with all requested replications
and a matching numeric metric are ranked. Matching a name and unit alone is
not proof of semantic equivalence; the report retains this caveat.

## Limits

A suite has 2–20 members and a global cap of 100 requested M9 executions.
Each member can include multiple explicitly bound M9 parameter sets and
replications. A failed artifact/member is recorded and does not prevent later
members from running. DES artifacts require the SimPy dependency. M24 does
not change simulation equations or replace M10 grid sweeps, M11 uncertainty
analysis or M23 optimization.
