# Milestone 24 — Cross-Engine Experiment Orchestration

## Delivered

M24 adds a suite plan that groups 2–20 independently compiled M8 artifacts
and executes each through the shared M9 runner. Members can specify
replications, ABM base seeds, continue-on-error behaviour and explicitly
bound parameter sets. The complete suite is limited to 100 requested M9
executions.

The engine verifies M8 artifacts, restricts relative artifact paths to a
configured artifact root (including symlink resolution), persists separate
fingerprinted M9 results, and aggregates numeric and categorical metrics by
member and parameter set. A failed member is recorded while later members
continue.

An optional comparison contract supports ranking only when a numeric metric
name and unit match exactly, all requested replications completed, and the
plan provides a semantic definition of the observable. The report records
that name/unit matching does not prove conceptual equivalence.

## Integration

- Reuses M8 artifact integrity verification and M9 execution/persistence.
- Supports all five M9 backends by dispatching through the existing executor.
- Adds strict M24 plan/report serialization, report fingerprint verification
  and CSV export.
- Adds standalone `python -m orchestration.cli` and main CLI options 20/21.
- Does not alter M8 artifacts, project revisions or engine execution code.

## V1 boundaries

Sequential orchestration only; no distributed execution, coupled co-simulation,
automatic metric mapping, multi-objective ranking or automatic semantic
validation. DES members require SimPy. The sample suite is a template and
requires user-supplied M8 artifacts beneath its configured artifact root.

## Verification

See `M24_TEST_REPORT.md` for actual focused and regression results. Complete
Windows verification remains required before committing M24.
